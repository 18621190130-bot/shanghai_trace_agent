from typing import Protocol
from ..walking_models import Location, WalkingRouteResult


class ExternalProviderError(RuntimeError):
    code = 'provider_error'

    def __init__(self):
        # Fixed diagnostics only: never retain raw URLs, bodies or credentials.
        super().__init__(self.code)


class ProviderUnavailableError(ExternalProviderError):
    code = 'provider_unavailable'


class ProviderTimeoutError(ProviderUnavailableError):
    code = 'provider_timeout'


class ProviderResponseError(ExternalProviderError):
    code = 'provider_response_invalid'


class ProviderQuotaError(ExternalProviderError):
    code = 'provider_quota_exceeded'


class WalkingRouteProvider(Protocol):
    def get_walking_route(self, origin: Location, destination: Location) -> WalkingRouteResult: ...
