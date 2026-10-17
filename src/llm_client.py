"""One real provider and an explicit fixture mock; neither plans routes."""

import copy
import json
import os
import re
import sys
import urllib.error
import urllib.request
from abc import ABC, abstractmethod


class LLMClientError(RuntimeError):
    def __init__(self, message, *, kind='provider_error', stage='api_response', http_status=None, finish_reason=None):
        super().__init__(redact_diagnostic(message))
        self.kind, self.stage = kind, stage
        self.http_status, self.finish_reason = http_status, finish_reason


def redact_diagnostic(value):
    if isinstance(value, dict):
        return {k: redact_diagnostic(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_diagnostic(v) for v in value]
    if isinstance(value, str):
        key = os.environ.get('DEEPSEEK_API_KEY')
        if key:
            value = value.replace(key, '[REDACTED]')
        return re.sub(r'\bsk-[A-Za-z0-9_-]+', '[REDACTED]', value)
    return value


def provider_debug(stage, **fields):
    if os.environ.get('DEEPSEEK_DEBUG') == '1':
        print(json.dumps(redact_diagnostic(dict(diagnostic='deepseek', stage=stage, **fields)),
                         ensure_ascii=False), file=sys.stderr)


def parse_provider_json(content):
    """Accept one intact JSON document, optionally fenced or surrounded by prose.

    Never repair truncation, merge multiple objects, or fill missing fields.
    """
    if not isinstance(content, str):
        return content
    stripped = content.strip()
    fence = re.fullmatch(r'```(?:json)?\s*(.*?)\s*```', stripped, re.I | re.S)
    if fence:
        stripped = fence.group(1)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as original:
        start = stripped.find('{')
        if start < 0:
            raise original
        value, end = json.JSONDecoder().raw_decode(stripped, start)
        if not isinstance(value, dict) or any(c in stripped[end:] for c in '{}'):
            raise original
        return value


class LLMClient(ABC):
    @abstractmethod
    def structured_parse(self, *, system_prompt, user_text, schema, validation_feedback=None):
        """Return a JSON string/object candidate, never a route."""


class DeepSeekLLMClient(LLMClient):
    def __init__(self, *, timeout=30, model=None, max_tokens=1200):
        self.timeout = timeout
        self.model = model or os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
        self.max_tokens = max_tokens
        self.last_response_metadata = None

    def structured_parse(self, *, system_prompt, user_text, schema, validation_feedback=None):
        self.last_response_metadata = None
        key = os.environ.get("DEEPSEEK_API_KEY")
        if not key or key == "your_key_here":
            provider_debug('configuration', provider='deepseek', model=self.model, success=False, key_present=False)
            raise LLMClientError("Set DEEPSEEK_API_KEY in the process environment before using live mode",
                                 kind='configuration_error', stage='configuration')
        instructions = system_prompt + "\nJSON Schema:\n" + json.dumps(schema, ensure_ascii=False)
        if validation_feedback:
            instructions += "\nPrevious candidate failed validation: " + validation_feedback
        body = {"model": self.model, "messages": [{"role": "system", "content": instructions},
                {"role": "user", "content": user_text}], "response_format": {"type": "json_object"},
                "temperature": 0, "max_tokens": self.max_tokens, "stream": False,
                "thinking": {"type": "disabled"}}
        request = urllib.request.Request("https://api.deepseek.com/chat/completions",
            data=json.dumps(body).encode("utf-8"), headers={"Authorization": "Bearer " + key,
            "Content-Type": "application/json"}, method="POST")
        provider_debug('request', provider='deepseek', model=self.model, max_tokens=body['max_tokens'],
                       thinking=body['thinking']['type'], required_fields=schema.get('required', []))
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                http_status = getattr(response, 'status', None) or 200
                raw = response.read()
        except urllib.error.HTTPError as exc:
            error = {}
            try:
                payload = json.loads(exc.read(8192))
                error = payload.get('error', {})
                if not isinstance(error, dict):
                    error = {}
            except (OSError, ValueError, TypeError, AttributeError):
                pass
            finally:
                exc.close()
            provider_debug('api_response', provider='deepseek', model=self.model, http_status=exc.code,
                           success=False, error={k: error.get(k) for k in ('type', 'code', 'message')})
            raise LLMClientError(f"DeepSeek request failed (HTTP {exc.code}; type={error.get('type') or 'http_error'}; code={error.get('code') or 'unknown'})",
                                 kind='http_error', http_status=exc.code) from None
        except OSError as exc:
            provider_debug('api_response', provider='deepseek', model=self.model, success=False,
                           error_type=type(exc).__name__)
            raise LLMClientError(f"DeepSeek network request failed ({type(exc).__name__})", kind='network_error') from None
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError, TypeError):
            provider_debug('api_response', http_status=http_status, success=False, error_type='invalid_response_json')
            raise LLMClientError('DeepSeek HTTP response was not valid JSON', kind='response_format_error', http_status=http_status) from None
        if isinstance(result, dict) and result.get('error'):
            provider_debug('api_response', http_status=http_status, success=False, error=result['error'])
            raise LLMClientError('DeepSeek returned a provider error object', kind='provider_api_error', http_status=http_status)
        try:
            choice = result['choices'][0]
            message = choice['message']
            finish_reason = choice.get('finish_reason')
            content = message.get('content')
        except (KeyError, IndexError, TypeError, AttributeError):
            provider_debug('content_extraction', http_status=http_status, success=False, error_type='missing_choices_or_message')
            raise LLMClientError('DeepSeek response lacked choices/message', kind='response_contract_error',
                                 stage='content_extraction', http_status=http_status) from None
        provider_debug('api_response', provider='deepseek', model=result.get('model', self.model), http_status=http_status,
                       success=True, finish_reason=finish_reason, raw_message_content=content,
                       reasoning_content_characters=len(message.get('reasoning_content') or ''), usage=result.get('usage'))
        self.last_response_metadata = {"model": result.get('model', self.model),
                                       "finish_reason": finish_reason, "usage": result.get('usage')}
        if finish_reason != 'stop':
            kind = 'output_truncated' if finish_reason == 'length' else 'provider_finish_error'
            raise LLMClientError(f'DeepSeek completion did not finish normally (finish_reason={finish_reason!r})',
                                 kind=kind, finish_reason=finish_reason, http_status=http_status)
        if not isinstance(content, str) or not content.strip():
            provider_debug('content_extraction', success=False, error_type='empty_or_non_string_content')
            raise LLMClientError('DeepSeek completed without nonempty message.content', kind='empty_content',
                                 stage='content_extraction', http_status=http_status, finish_reason=finish_reason)
        provider_debug('content_extraction', success=True)
        return content


class MockLLMClient(LLMClient):
    """Exact fixtures or queued responses, with no NLP claim and no network fallback."""
    def __init__(self, fixtures=None, responses=None):
        self.fixtures = copy.deepcopy(fixtures or {})
        self.responses = copy.deepcopy(responses or [])
        self.calls = []

    def structured_parse(self, *, system_prompt, user_text, schema, validation_feedback=None):
        self.calls.append({"user_text": user_text, "validation_feedback": validation_feedback})
        if self.responses:
            return self.responses.pop(0)
        if user_text not in self.fixtures:
            raise LLMClientError("No mock fixture for this text; use a documented sample or explicit live mode")
        return copy.deepcopy(self.fixtures[user_text])
