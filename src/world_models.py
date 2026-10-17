"""Read-only world observations; reuse the frozen Location coordinate contract."""
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from .walking_models import Location

SHANGHAI = timezone(timedelta(hours=8), 'Asia/Shanghai')


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class LiveDataStatus(StrEnum):
    AVAILABLE = 'AVAILABLE'
    PARTIAL = 'PARTIAL'
    UNAVAILABLE = 'UNAVAILABLE'


class OpenStatus(StrEnum):
    OPEN = 'OPEN'
    CLOSED = 'CLOSED'
    UNKNOWN = 'UNKNOWN'
    NOT_APPLICABLE = 'NOT_APPLICABLE'


class MappingStatus(StrEnum):
    MATCHED = 'MATCHED'
    AMBIGUOUS = 'AMBIGUOUS'
    NOT_FOUND = 'NOT_FOUND'


class LiveInfoApplicability(StrEnum):
    FULL = 'FULL'
    LIMITED = 'LIMITED'
    NOT_APPLICABLE = 'NOT_APPLICABLE'


class ArrivalStatus(StrEnum):
    FAR = 'FAR'
    NEAR = 'NEAR'
    ARRIVED = 'ARRIVED'


class WorldDTO:
    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class ResolvedLocation(WorldDTO):
    location: Location
    formatted_address: str | None = None
    province: str | None = None
    city: str | None = None
    district: str | None = None
    township: str | None = None
    adcode: str | None = None
    street: str | None = None
    street_number: str | None = None
    provider: str = 'amap'
    fetched_at: str | None = None
    live_data_status: str = LiveDataStatus.UNAVAILABLE
    cache_hit: bool = False
    error_code: str | None = None


@dataclass(frozen=True)
class PoiLiveInfo(WorldDTO):
    provider_id: str | None = None
    core_poi_id: str | None = None
    provider: str = 'amap'
    name: str | None = None
    address: str | None = None
    location: Location | None = None
    tel: str | None = None
    opentime_today: str | None = None
    opentime_week: str | None = None
    rating: float | None = None
    cost: float | None = None
    tags: tuple[str, ...] | None = None
    poi_type: str | None = None
    fetched_at: str | None = None
    live_data_status: str = LiveDataStatus.UNAVAILABLE
    open_status: str = OpenStatus.UNKNOWN
    mapping_status: str | None = None
    identity_mapping_status: str | None = None
    live_info_applicability: str | None = None
    cache_hit: bool = False
    status_evaluated_at: str | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class PoiCandidate(WorldDTO):
    provider_id: str
    name: str
    location: Location
    district: str | None = None
    address: str | None = None
    poi_type: str | None = None


@dataclass(frozen=True)
class ProximityResult(WorldDTO):
    current_location: Location
    target_poi_id: str
    target_location: Location
    distance_m: float
    status: str
    arrival_threshold_m: float
    near_threshold_m: float
