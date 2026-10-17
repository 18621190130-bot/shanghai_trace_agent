from dataclasses import replace
from ..walking_models import Location
from ..world_models import ResolvedLocation
from ..providers.base import ExternalProviderError, ProviderUnavailableError, ProviderResponseError
from .ttl_cache import TTLCache


def current_location(value):
    if isinstance(value, Location):return value
    if not isinstance(value, dict) or set(value) != {'lat','lng','coordinate_system'}:
        raise ValueError('Current location requires lat, lng and coordinate_system')
    return Location(**value)


class LocationService:
    def __init__(self, provider, normalizer, *, ttl_s=1800, cache=None):
        self.provider, self.normalizer = provider, normalizer
        self.cache = cache if cache is not None else TTLCache(ttl_s)
        self.conversion_cache = TTLCache(3600)

    def normalize_location_for_amap(self, value):
        location = current_location(value)
        if location.coordinate_system == 'GCJ02':return location
        key = (location.coordinate_system, round(location.lat,6), round(location.lng,6))
        cached = self.conversion_cache.get(key)
        if cached is not None:return cached
        if self.normalizer is None:raise ProviderUnavailableError()
        result = self.normalizer(location)
        if not isinstance(result, Location) or result.coordinate_system != 'GCJ02':raise ProviderResponseError()
        self.conversion_cache.set(key, result)
        return result

    def reverse_geocode(self, value):
        location = current_location(value)  # Invalid input is rejected rather than silently unavailable.
        try:
            location = self.normalize_location_for_amap(location)
            key = ('amap','regeo', round(location.lat,6), round(location.lng,6))
            cached = self.cache.get(key)
            if cached is not None:return replace(cached, cache_hit=True)
            if self.provider is None:raise ProviderUnavailableError()
            result = self.provider.reverse_geocode(location)
            if not isinstance(result, ResolvedLocation) or result.live_data_status == 'UNAVAILABLE':raise ProviderResponseError()
            self.cache.set(key,result)
            return result
        except Exception as exc:
            return ResolvedLocation(location, error_code=exc.code if isinstance(exc,ExternalProviderError) else 'provider_response_invalid')
