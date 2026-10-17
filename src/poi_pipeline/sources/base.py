"""Bounded HTTP transport with secret-free cache, replay and isolated errors."""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class SourceError(RuntimeError):
    pass


class Source(ABC):
    name = "source"

    def __init__(self, http):
        self.http = http
        self.errors = []

    def error(self, label, exc):
        # Exception messages may contain a keyed request URL. Never persist them.
        self.errors.append(dict(source=self.name, request=label, error_type=type(exc).__name__,
                                status="partial_source_failure"))

    @abstractmethod
    def collect(self):
        """Yield RawCandidate records; retain successful pages after any failure."""


class CachedHTTP:
    def __init__(self, cache_dir, *, timeout=20, retries=2, min_interval=1.1,
                 offline=False, retry_failed=False, opener=None, sleeper=time.sleep, max_response_bytes=4_000_000):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout, self.retries, self.min_interval = timeout, retries, min_interval
        self.offline, self.opener, self.sleep = offline, opener or urllib.request.urlopen, sleeper
        self.retry_failed = retry_failed
        self.max_response_bytes = max_response_bytes
        self.last_request = {}

    def get(self, source, url, params=None, *, secret_params=None, transform=None, cache_variant="json-v1"):
        params = params or {}
        if any(k.lower() in ("key", "token", "api_key", "authorization") for k in params):
            raise ValueError("Credentials must use secret_params")
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.query or parsed.username or parsed.password:
            raise ValueError("Use a plain HTTPS endpoint and separate request parameters")
        identity = dict(source=source, url=url, parameters=params, variant=cache_variant)
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        path = self.cache_dir / (digest + ".json")
        failure_path = self.cache_dir / (digest + ".failure.json")
        if path.exists():
            cached = json.loads(path.read_text(encoding="utf-8"))
            payload_hash = hashlib.sha256(json.dumps(cached["response"], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            if payload_hash != cached["response_hash"]:
                raise SourceError("cache_integrity_failure")
            return cached
        if failure_path.exists() and (self.offline or not self.retry_failed):
            raise SourceError("cached_request_failure")
        if self.offline:
            raise SourceError("offline_cache_miss")
        for attempt in range(self.retries + 1):
            delay = self.min_interval - (time.monotonic() - self.last_request.get(parsed.netloc, 0))
            if delay > 0:
                self.sleep(delay)
            self.last_request[parsed.netloc] = time.monotonic()
            query = urllib.parse.urlencode(dict(params, **(secret_params or {})))
            request = urllib.request.Request(url + ("?" + query if query else ""),
                        headers={"User-Agent": "ShanghaiTrace-Research-Pilot/0.1", "Accept": "application/json,text/html"})
            try:
                with self.opener(request, timeout=self.timeout) as response:
                    body = response.read(self.max_response_bytes + 1)
                    if len(body) > self.max_response_bytes:
                        raise SourceError("response_size_limit")
                    charset = response.headers.get_content_charset() or "utf-8"
                    decoded = body.decode(charset, errors="replace")
                payload = transform(decoded) if transform else json.loads(decoded)
                # Redact even a provider response that echoes credentials.
                encoded = json.dumps(payload, ensure_ascii=False)
                for secret in (secret_params or {}).values():
                    if secret:
                        encoded = encoded.replace(str(secret), "[REDACTED]")
                payload = json.loads(encoded)
                cached = dict(identity, retrieved_at=utc_now(), response=payload,
                    response_hash=hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
                temp = path.with_suffix(".tmp")
                temp.write_text(json.dumps(cached, ensure_ascii=False, indent=2), encoding="utf-8")
                temp.replace(path)
                return cached
            except (OSError, ValueError, SourceError) as exc:
                retryable = not isinstance(exc, urllib.error.HTTPError) or exc.code in (408, 429, 500, 502, 503, 504)
                if attempt == self.retries or not retryable:
                    failure_path.write_text(json.dumps(dict(identity, retrieved_at=utc_now(),
                        status="request_failed", error_type=type(exc).__name__,
                        http_status=exc.code if isinstance(exc, urllib.error.HTTPError) else None,
                        attempts=attempt + 1), ensure_ascii=False, indent=2), encoding="utf-8")
                    raise SourceError(type(exc).__name__) from None
                self.sleep(min(8, 2 ** attempt))
        raise SourceError("request_failed")
