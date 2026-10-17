"""Provider-neutral walking DTOs. Geometry is GCJ02 [longitude, latitude]."""
from dataclasses import asdict, dataclass, field
from enum import StrEnum
import math


class CoordinateSystem(StrEnum):
    WGS84 = 'WGS84'
    GCJ02 = 'GCJ02'


@dataclass(frozen=True)
class Location:
    lat: float
    lng: float
    coordinate_system: str

    def __post_init__(self):
        system = {'GCJ-02': 'GCJ02'}.get(self.coordinate_system, self.coordinate_system)
        if system not in ('GCJ02', 'WGS84'):
            raise ValueError('Unsupported coordinate system')
        for value, limit in ((self.lat, 90), (self.lng, 180)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > limit:
                raise ValueError('Location requires finite coordinates in range')
        object.__setattr__(self, 'coordinate_system', system)

    def amap_value(self):
        return f'{self.lng:.6f},{self.lat:.6f}'


class WalkingDataStatus(StrEnum):
    AVAILABLE = 'AVAILABLE'
    FALLBACK_ESTIMATE = 'FALLBACK_ESTIMATE'
    UNAVAILABLE = 'UNAVAILABLE'


@dataclass(frozen=True)
class WalkingStep:
    instruction: str | None
    road: str | None
    distance_m: float | None
    duration_s: float | None
    polyline: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True)
class WalkingRouteResult:
    origin: Location
    destination: Location
    distance_m: float
    duration_s: float
    steps: tuple[WalkingStep, ...]
    polyline: tuple[tuple[float, float], ...]
    provider: str
    fetched_at: str


@dataclass
class WalkingLeg:
    from_poi_id: str | None
    to_poi_id: str
    from_name: str
    to_name: str
    origin: Location | None
    destination: Location | None
    distance_m: float | None
    duration_s: float | None
    steps: tuple[WalkingStep, ...] = ()
    polyline: tuple[tuple[float, float], ...] = ()
    data_source: str = 'planning_estimate'
    status: str = WalkingDataStatus.FALLBACK_ESTIMATE
    fetched_at: str | None = None
    cache_hit: bool = False
    fallback_used: bool = True
    error_code: str | None = None


@dataclass
class RouteWalking:
    status: str
    total_distance_m: float | None
    total_duration_s: float | None
    legs: list[WalkingLeg] = field(default_factory=list)
    geometry: tuple[tuple[float, float], ...] = ()
    coordinate_system: str = 'GCJ02'
    geometry_complete: bool = False
    # Partial fallback geometry must not be drawn as a continuous road line.
    geometry_segments: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def merge_geometry(parts):
    points = []
    for part in parts:
        for point in part:
            if not points or points[-1] != point:
                points.append(point)
    return tuple(points)
