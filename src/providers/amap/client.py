"""Shared bounded HTTPS transport; safe, classified provider failures."""
import json
import os
import socket
import math
import time
from threading import Lock
import urllib.error
import urllib.parse
import urllib.request

from ..base import (ProviderQuotaError, ProviderResponseError,
                    ProviderTimeoutError, ProviderUnavailableError)


class AmapClient:
    BASE_URL = 'https://restapi.amap.com'
    MAX_RESPONSE_BYTES = 4 * 1024 * 1024

    def __init__(self, *, timeout_s=5, opener=None, min_interval_s=.5,
                 clock=time.monotonic, sleeper=time.sleep):
        if not isinstance(timeout_s, (int, float)) or not math.isfinite(timeout_s) or timeout_s <= 0:
            raise ValueError('Timeout must be finite and positive')
        self.timeout_s = timeout_s
        if not math.isfinite(min_interval_s) or min_interval_s < 0:
            raise ValueError('Request interval must be finite and nonnegative')
        self.min_interval_s, self._clock, self._sleeper = min_interval_s, clock, sleeper
        self._last_request_at = None
        self._pace_lock = Lock()
        self._opener = opener or urllib.request.urlopen
        self._key = os.environ.get('AMAP_WEB_SERVICE_KEY', '').strip()

    def redact_text(self, value):
        return value.replace(self._key, '[REDACTED]') if self._key else value

    def get(self, path, parameters):
        if not self._key:
            raise ProviderUnavailableError()
        if not path.startswith(('/v3/', '/v5/')) or '?' in path:
            raise ValueError('Expected an Amap API path')
        query = urllib.parse.urlencode({**parameters, 'key': self._key, 'output': 'JSON'})
        request = urllib.request.Request(self.BASE_URL + path + '?' + query)
        with self._pace_lock:
            if self._last_request_at is not None:
                delay = self.min_interval_s - (self._clock() - self._last_request_at)
                if delay > 0:
                    self._sleeper(delay)
            self._last_request_at = self._clock()
        error = None
        payload = None
        try:
            with self._opener(request, timeout=self.timeout_s) as response:
                status = getattr(response, 'status', 200)
                if status == 429:
                    error = ProviderQuotaError()
                elif isinstance(status, int) and status >= 400:
                    error = ProviderUnavailableError()
                else:
                    body = response.read(self.MAX_RESPONSE_BYTES + 1)
                    if len(body) > self.MAX_RESPONSE_BYTES:
                        error = ProviderResponseError()
                    else:
                        payload = json.loads(body)
        except (TimeoutError, socket.timeout):
            error = ProviderTimeoutError()
        except urllib.error.HTTPError as exc:
            error = ProviderQuotaError() if exc.code == 429 else ProviderUnavailableError()
        except urllib.error.URLError as exc:
            error = ProviderTimeoutError() if isinstance(exc.reason, TimeoutError) else ProviderUnavailableError()
        except (ValueError, UnicodeError, TypeError):
            error = ProviderResponseError()
        except OSError:
            error = ProviderUnavailableError()
        # Raise outside except: even exception context contains no raw transport URL.
        if error:
            raise error
        if not isinstance(payload, dict):
            raise ProviderResponseError()
        if str(payload.get('status')) != '1':
            code = str(payload.get('infocode', ''))
            if code in ('10003', '10004', '10010', '10014', '10015', '10019', '10020', '10021',
                        '10029', '10044', '10045', '40000', '40003'):
                raise ProviderQuotaError()
            if code == '10002':
                raise ProviderTimeoutError()
            raise ProviderUnavailableError()
        return payload
