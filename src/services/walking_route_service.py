"""Final-sequence hydration, bounded leg cache and per-leg estimate fallback."""
import copy
import math
import os
import time
from collections import OrderedDict
from threading import RLock

from ..walking_models import Location, WalkingLeg, RouteWalking, WalkingDataStatus, merge_geometry
from ..providers.base import ExternalProviderError, ProviderUnavailableError


class WalkingRouteService:
    def __init__(self, provider=None, *, ttl_s=3600, max_entries=512, clock=time.monotonic):
        if not math.isfinite(ttl_s) or ttl_s <= 0 or type(max_entries) is not int or max_entries <= 0:
            raise ValueError('Cache bounds must be positive')
        self.provider = provider
        self.ttl_s, self.max_entries, self.clock = ttl_s, max_entries, clock
        self._cache = OrderedDict()
        self._lock = RLock()

    @classmethod
    def from_environment(cls):
        from ..providers.amap import AmapClient, AmapWalkingProvider
        return cls(AmapWalkingProvider(AmapClient()))

    def normalize_location_for_amap(self, location):
        if location.coordinate_system == 'GCJ02':
            return location
        normalize = getattr(self.provider, 'normalize_location_for_amap', None)
        if normalize is None:
            raise ProviderUnavailableError()
        return normalize(location)

    def _get(self, origin, destination):
        # Direction and datum matter. The provider is scoped to this cache instance.
        key = ('walking',) + tuple((p.coordinate_system, round(p.lat, 6), round(p.lng, 6))
                                  for p in (origin, destination))
        with self._lock:
            cached = self._cache.get(key)
            if cached and self.clock() < cached[0]:
                self._cache.move_to_end(key)
                return copy.deepcopy(cached[1]), True
            self._cache.pop(key, None)
        if self.provider is None:
            raise ProviderUnavailableError()
        result = self.provider.get_walking_route(origin, destination)
        if (not math.isfinite(result.distance_m) or result.distance_m < 0 or
                not math.isfinite(result.duration_s) or result.duration_s < 0 or
                not result.steps or not result.polyline or
                result.origin.coordinate_system != 'GCJ02' or result.destination.coordinate_system != 'GCJ02'):
            from ..providers.base import ProviderResponseError
            raise ProviderResponseError()
        with self._lock:
            self._cache[key] = (self.clock() + self.ttl_s, copy.deepcopy(result))
            while len(self._cache) > self.max_entries:
                self._cache.popitem(last=False)
        return copy.deepcopy(result), False

    def get_walking_route(self, origin, destination):
        return self._get(origin, destination)[0]

    @staticmethod
    def _location(stop):
        point = stop.get('estimated_coordinates')
        return Location(point[0], point[1], stop['coordinate_system']) if point else None

    @staticmethod
    def _estimate(value, multiplier):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            return None
        return value * multiplier

    def hydrate_dict(self, route):
        output = copy.deepcopy(route)
        stops = output['ordered_pois']
        request = output['request']
        previous = None
        if request.get('start_lat') is not None:
            previous = dict(poi_id=None, name_en='Route origin',
                            estimated_coordinates=[request['start_lat'], request['start_lng']],
                            coordinate_system=request.get('start_coordinate_system', 'GCJ-02'))
        legs = []
        for stop in stops:
            if previous is not None:
                origin = destination = None
                leg = WalkingLeg(previous['poi_id'], stop['poi_id'], previous['name_en'], stop['name_en'],
                                 None, None,
                                 self._estimate(stop.get('estimated_distance_from_previous_stop_km'), 1000),
                                 self._estimate(stop.get('estimated_walking_minutes'), 60))
                try:
                    origin, destination = self._location(previous), self._location(stop)
                    leg.origin, leg.destination = origin, destination
                    if origin is None or destination is None:
                        raise ProviderUnavailableError()
                    result, hit = self._get(origin, destination)
                    leg.origin, leg.destination = result.origin, result.destination
                    leg.distance_m, leg.duration_s = result.distance_m, result.duration_s
                    leg.steps, leg.polyline = result.steps, result.polyline
                    leg.data_source, leg.fetched_at = result.provider, result.fetched_at
                    leg.status, leg.cache_hit, leg.fallback_used = WalkingDataStatus.AVAILABLE, hit, False
                except Exception as exc:
                    # Boundary protects route snapshots even against a faulty future provider.
                    leg.error_code = exc.code if isinstance(exc, ExternalProviderError) else 'provider_response_invalid'
                    if leg.distance_m is None or leg.duration_s is None:
                        leg.status = WalkingDataStatus.UNAVAILABLE
                legs.append(leg)
            previous = stop
        status = (WalkingDataStatus.UNAVAILABLE if any(l.status == WalkingDataStatus.UNAVAILABLE for l in legs)
                  else WalkingDataStatus.FALLBACK_ESTIMATE if any(l.fallback_used for l in legs)
                  else WalkingDataStatus.AVAILABLE)
        complete = all(l.status == WalkingDataStatus.AVAILABLE for l in legs)
        walking = RouteWalking(status,
                               sum(l.distance_m for l in legs) if status != WalkingDataStatus.UNAVAILABLE else None,
                               sum(l.duration_s for l in legs) if status != WalkingDataStatus.UNAVAILABLE else None,
                               legs, merge_geometry(l.polyline for l in legs) if complete else (),
                               geometry_complete=complete,
                               geometry_segments=[l.polyline for l in legs])
        output.update(planning_distance_m=self._estimate(output.get('total_estimated_distance_km'), 1000),
                      planning_duration_min=output.get('total_estimated_walking_minutes'),
                      walking_distance_m=walking.total_distance_m, walking_duration_s=walking.total_duration_s,
                      walking_legs=walking.to_dict()['legs'], route_geometry=walking.geometry,
                      walking_data_status=status, walking=walking.to_dict())
        return output

    def hydrate_walking_route(self, plan):
        from ..models import RoutePlan, RouteStop
        if plan.status != 'success':
            return copy.deepcopy(plan)
        data = self.hydrate_dict(plan.to_dict())
        for stop in data['ordered_pois']:
            stop.pop('estimated_distance_from_previous', None)
            stop.pop('estimated_walking_minutes_from_previous', None)
        data['ordered_pois'] = [RouteStop(**s) for s in data['ordered_pois']]
        return RoutePlan(**data)


_default_service = None
_default_key = None


def default_walking_service():
    """Reuse leg cache across route entry, direct routes and replan."""
    global _default_service, _default_key
    key = os.environ.get('AMAP_WEB_SERVICE_KEY', '')
    if _default_service is None or key != _default_key:
        _default_key = key
        _default_service = WalkingRouteService.from_environment() if key.strip() else WalkingRouteService()
    return _default_service
