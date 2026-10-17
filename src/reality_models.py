from dataclasses import dataclass, field
from enum import StrEnum
from .world_models import WorldDTO


class RealityStatus(StrEnum):
    OK = 'OK'
    WARNING = 'WARNING'
    PARTIAL = 'PARTIAL'
    UNAVAILABLE = 'UNAVAILABLE'


class WarningCode(StrEnum):
    LIVE_ROUTE_EXCEEDS_BUDGET = 'LIVE_ROUTE_EXCEEDS_BUDGET'
    POI_CLOSED = 'POI_CLOSED'
    POI_MAY_CLOSE_BEFORE_ARRIVAL = 'POI_MAY_CLOSE_BEFORE_ARRIVAL'
    OPENING_HOURS_UNKNOWN = 'OPENING_HOURS_UNKNOWN'
    WEATHER_RISK = 'WEATHER_RISK'
    LIVE_ROUTE_DATA_UNAVAILABLE = 'LIVE_ROUTE_DATA_UNAVAILABLE'
    WEATHER_DATA_UNAVAILABLE = 'WEATHER_DATA_UNAVAILABLE'


@dataclass(frozen=True)
class RealityWarning(WorldDTO):
    code: str
    severity: str
    message: str
    details: dict = field(default_factory=dict)
    poi_id: str | None = None
    leg_index: int | None = None
    source: str = 'route_reality_check'
    confidence: str = 'HIGH'


@dataclass(frozen=True)
class RealityCheckResult(WorldDTO):
    checked_at: str
    route_version: str
    status: str
    warnings: tuple[RealityWarning, ...] = ()
    weather: dict | None = None
    metrics: dict = field(default_factory=dict)
    data_quality: dict = field(default_factory=dict)
