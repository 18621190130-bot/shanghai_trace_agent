import contextlib
import io
import json
import os
import unittest
import urllib.error
from unittest.mock import patch

from tools.demos.route_entry_demo import main
from src import POIRepository, RouteEntryService
from src.intent_schema import candidate_schema
from src.llm_client import DeepSeekLLMClient, LLMClientError, MockLLMClient, parse_provider_json
from src.mock_examples import candidate
from src.models import RequestValidationError


class DeepSeekProviderTests(unittest.TestCase):
    def response(self, content='{}', finish='stop', **extra):
        return io.BytesIO(json.dumps(dict(choices=[dict(finish_reason=finish,
            message=dict(content=content, **extra))], model='deepseek-flash')).encode())

    def call(self):
        return DeepSeekLLMClient().structured_parse(system_prompt='Return JSON', user_text='hello', schema={})

    def test_intent_extraction_disables_thinking_without_increasing_token_budget(self):
        with patch.dict(os.environ, DEEPSEEK_API_KEY='test-secret'), \
                patch('urllib.request.urlopen', return_value=self.response()) as network:
            self.call()
        body = json.loads(network.call_args.args[0].data)
        self.assertEqual(body['thinking'], {'type': 'disabled'})
        self.assertEqual(body['max_tokens'], 1200)
        self.assertEqual(body['response_format'], {'type': 'json_object'})
        self.assertEqual(network.call_count, 1)

    def test_truncation_reports_actual_finish_and_raw_content_without_retry(self):
        output = io.StringIO()
        with patch.dict(os.environ, DEEPSEEK_API_KEY='test-secret', DEEPSEEK_DEBUG='1'), \
                patch('urllib.request.urlopen', return_value=self.response('{"partial":', 'length', reasoning_content='abc')) as network, \
                contextlib.redirect_stderr(output):
            with self.assertRaises(LLMClientError) as raised:
                self.call()
        self.assertEqual(raised.exception.kind, 'output_truncated')
        self.assertEqual(raised.exception.finish_reason, 'length')
        self.assertEqual(network.call_count, 1)
        records = [json.loads(line) for line in output.getvalue().splitlines()]
        raw = next(r for r in records if r['stage'] == 'api_response')
        self.assertEqual(raw['raw_message_content'], '{"partial":')
        self.assertEqual(raw['reasoning_content_characters'], 3)

    def test_http_error_keeps_type_and_does_not_become_validation_error(self):
        body = io.BytesIO(json.dumps(dict(error=dict(type='authentication_error', code='invalid_api_key', message='bad key'))).encode())
        error = urllib.error.HTTPError('https://api.deepseek.com', 401, 'Unauthorized', {}, body)
        output = io.StringIO()
        with patch.dict(os.environ, DEEPSEEK_API_KEY='test-secret'), \
                patch('urllib.request.urlopen', side_effect=error), contextlib.redirect_stderr(output):
            code = main(['--mode','plan_for_me','--text','hello'], live=True)
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(payload['status'], 'provider_error')
        self.assertEqual(payload['http_status'], 401)
        self.assertIn('authentication_error', payload['errors'][0])

    def test_network_error_preserves_its_category(self):
        with patch.dict(os.environ, DEEPSEEK_API_KEY='test-secret'), \
                patch('urllib.request.urlopen', side_effect=urllib.error.URLError('offline')):
            with self.assertRaises(LLMClientError) as raised:
                self.call()
        self.assertEqual(raised.exception.kind, 'network_error')

    def test_empty_content_is_content_extraction_failure(self):
        with patch.dict(os.environ, DEEPSEEK_API_KEY='test-secret'), \
                patch('urllib.request.urlopen', return_value=self.response(None)):
            with self.assertRaises(LLMClientError) as raised:
                self.call()
        self.assertEqual(raised.exception.kind, 'empty_content')
        self.assertEqual(raised.exception.stage, 'content_extraction')

    def test_bad_http_json_is_not_schema_validation_failure(self):
        with patch.dict(os.environ, DEEPSEEK_API_KEY='test-secret'), \
                patch('urllib.request.urlopen', return_value=io.BytesIO(b'<html>bad gateway</html>')):
            with self.assertRaises(LLMClientError) as raised:
                self.call()
        self.assertEqual(raised.exception.kind, 'response_format_error')

    def test_missing_envelope_fields_are_contract_error(self):
        with patch.dict(os.environ, DEEPSEEK_API_KEY='test-secret'), \
                patch('urllib.request.urlopen', return_value=io.BytesIO(b'{"choices":[]}')):
            with self.assertRaises(LLMClientError) as raised:
                self.call()
        self.assertEqual(raised.exception.kind, 'response_contract_error')

    def test_content_filter_is_not_misreported_as_truncation(self):
        with patch.dict(os.environ, DEEPSEEK_API_KEY='test-secret'), \
                patch('urllib.request.urlopen', return_value=self.response('', 'content_filter')):
            with self.assertRaises(LLMClientError) as raised:
                self.call()
        self.assertEqual(raised.exception.kind, 'provider_finish_error')
        self.assertEqual(raised.exception.finish_reason, 'content_filter')

    def test_debug_redacts_key_and_is_disabled_by_default(self):
        key = 'sk-test-api-key'
        output = io.StringIO()
        with patch.dict(os.environ, DEEPSEEK_API_KEY=key, DEEPSEEK_DEBUG='1'), \
                patch('urllib.request.urlopen', return_value=self.response(json.dumps(dict(secret=key)))), \
                contextlib.redirect_stderr(output):
            self.call()
        self.assertNotIn(key, output.getvalue())
        self.assertIn('[REDACTED]', output.getvalue())
        silent = io.StringIO()
        with patch.dict(os.environ, DEEPSEEK_API_KEY=key, DEEPSEEK_DEBUG='0'), \
                patch('urllib.request.urlopen', return_value=self.response()), contextlib.redirect_stderr(silent):
            self.call()
        self.assertEqual(silent.getvalue(), '')

    def test_complete_json_or_fence_or_prose_keeps_strict_field_validation(self):
        data = candidate(available_minutes=150, interest_tags=['shopping_lifestyle', 'modern_city'])
        for text in (json.dumps(data), '```json\n'+json.dumps(data)+'\n```', 'Here is the JSON:\n'+json.dumps(data)+'\nDone.'):
            service = RouteEntryService(POIRepository(), MockLLMClient(responses=[text]))
            intent = service.parse_plan('shopping and modern city')
            self.assertEqual(intent.available_minutes, 150)
        with self.assertRaises(RequestValidationError):
            RouteEntryService(POIRepository(), MockLLMClient(fixtures={'bad': '```json\n{}\n```'})).parse_plan('bad')

    def test_partial_or_ambiguous_objects_are_not_repaired(self):
        for text in ('{"a":', '{"a": 1} {"b": 2}', '{"broken": {"ok": 1}'):
            with self.assertRaises(json.JSONDecodeError):
                parse_provider_json(text)

    def test_unified_patch_semantic_metadata_was_not_added_to_required_fields(self):
        schema = candidate_schema(POIRepository())
        self.assertNotIn('semantic_concepts', schema['required'])
        self.assertEqual(set(schema['required']), set(candidate()))

    def test_debug_identifies_missing_and_unknown_schema_fields(self):
        output = io.StringIO()
        service = RouteEntryService(POIRepository(), MockLLMClient(fixtures={'bad': {'available_minutes':150, 'made_up': True}}))
        with patch.dict(os.environ, DEEPSEEK_DEBUG='1'), contextlib.redirect_stderr(output), self.assertRaises(RequestValidationError):
            service.parse_plan('bad')
        diagnostics = [json.loads(line) for line in output.getvalue().splitlines()]
        check = next(d for d in diagnostics if d['stage'] == 'candidate_schema')
        self.assertIn('interest_tags', check['missing_fields'])
        self.assertEqual(check['unknown_fields'], ['made_up'])
