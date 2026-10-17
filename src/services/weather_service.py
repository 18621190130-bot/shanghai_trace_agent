"""Weather location resolution and bounded TTL caches, independent of TripStore."""
import copy
import re
from dataclasses import replace
from ..walking_models import Location
from ..weather_models import CurrentWeather, WeatherForecast
from ..providers.base import ExternalProviderError, ProviderResponseError, ProviderUnavailableError
from .ttl_cache import TTLCache


def snapshot(value):
    return copy.deepcopy(value.to_dict() if hasattr(value, 'to_dict') else value)


class WeatherService:
    def __init__(self, provider, repository, locations, *, current_cache=None, forecast_cache=None):
        self.provider, self.repository, self.locations = provider, repository, locations
        self.current_cache = current_cache if current_cache is not None else TTLCache(600)
        self.forecast_cache = forecast_cache if forecast_cache is not None else TTLCache(1800)

    def _origin(self, current_location, current_core_poi_id, trip_state, route_version):
        if current_location is not None:
            return current_location, 'CURRENT_LOCATION', None
        trip = snapshot(trip_state) if trip_state is not None else {}
        pid = current_core_poi_id or trip.get('current_poi_id')
        source = 'CURRENT_CORE'
        if not pid:
            version = snapshot(route_version) if route_version is not None else {}
            route = version.get('route_snapshot', trip.get('active_route', {}))
            excluded = set(trip.get('visited_poi_ids', []) + trip.get('skipped_poi_ids', []))
            pid = next((s['poi_id'] for s in route.get('ordered_pois', []) if s['poi_id'] not in excluded), None)
            source = 'NEXT_UNVISITED_CORE'
        if not pid:
            raise ProviderUnavailableError()
        poi = self.repository.get_poi_by_id(pid)
        if poi is None or not poi.coordinates:
            raise ProviderUnavailableError()
        # Production Repository exposes effective GCJ02 routing coordinates.
        return Location(*poi.coordinates, 'GCJ02'), source, pid

    def _get(self, forecast, current_location, current_core_poi_id, trip_state, route_version):
        model = WeatherForecast if forecast else CurrentWeather
        context = {}
        try:
            location, source, pid = self._origin(current_location, current_core_poi_id, trip_state, route_version)
            context.update(origin_source=source, origin_core_poi_id=pid)
            resolved = self.locations.reverse_geocode(location)
            context['resolved_location'] = resolved.to_dict()
            if resolved.live_data_status == 'UNAVAILABLE':
                result = model(**context, error_code=resolved.error_code or 'provider_unavailable')
                return result
            if not isinstance(resolved.adcode, str) or not re.fullmatch(r'\d{6}', resolved.adcode):
                raise ProviderResponseError()
            provider_name = getattr(self.provider, 'provider', 'amap')
            if not isinstance(provider_name, str):
                provider_name = 'amap'
            key = (provider_name, resolved.adcode, 'forecast' if forecast else 'current')
            cache = self.forecast_cache if forecast else self.current_cache
            result = cache.get(key)
            hit = result is not None
            if result is None:
                if self.provider is None:
                    raise ProviderUnavailableError()
                method = self.provider.get_weather_forecast if forecast else self.provider.get_current_weather
                result = method(resolved.adcode)
                if not isinstance(result, model) or result.data_status not in ('AVAILABLE', 'PARTIAL'):
                    raise ProviderResponseError()
                cache.set(key, result)
            return replace(result, cache_hit=hit, **context)
        except Exception as exc:
            return model(**context, error_code=exc.code if isinstance(exc, ExternalProviderError) else 'provider_response_invalid')

    def get_current_weather(self, current_location=None, *, current_core_poi_id=None, trip_state=None, route_version=None):
        return self._get(False, current_location, current_core_poi_id, trip_state, route_version)

    def get_weather_forecast(self, current_location=None, *, current_core_poi_id=None, trip_state=None, route_version=None):
        return self._get(True, current_location, current_core_poi_id, trip_state, route_version)
