from dataclasses import dataclass
import math
from ..geo_utils import haversine_km
from ..walking_models import Location
from ..world_models import ProximityResult, ArrivalStatus


@dataclass(frozen=True)
class ProximityConfig:
    arrival_threshold_m: float = 60
    near_threshold_m: float = 200

    def __post_init__(self):
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in
               (self.arrival_threshold_m,self.near_threshold_m)) or not 0 <= self.arrival_threshold_m < self.near_threshold_m:
            raise ValueError('Require finite 0 <= arrival threshold < near threshold')


class ProximityService:
    def __init__(self, location_service, config=None):
        self.locations = location_service
        self.config = config if config is not None else ProximityConfig()

    def check_arrival(self, current, target_poi):
        if target_poi.coordinates is None:raise ValueError('Target POI has no usable coordinates')
        origin = self.locations.normalize_location_for_amap(current)
        # Repository coordinates already conform to the frozen GCJ-02 contract.
        target = Location(*target_poi.coordinates, 'GCJ02')
        distance = haversine_km((origin.lat,origin.lng),(target.lat,target.lng))*1000
        cfg = self.config
        status = ArrivalStatus.ARRIVED if distance <= cfg.arrival_threshold_m else ArrivalStatus.NEAR if distance <= cfg.near_threshold_m else ArrivalStatus.FAR
        return ProximityResult(origin,target_poi.id,target,distance,status,cfg.arrival_threshold_m,cfg.near_threshold_m)

    def distance_to_poi(self, current, target_poi):
        return self.check_arrival(current,target_poi).distance_m
