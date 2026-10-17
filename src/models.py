"""Public request/result models. No LLM or third-party runtime dependencies."""

from dataclasses import asdict, dataclass, field
from typing import Any


class DataValidationError(ValueError):
    """The knowledge base cannot safely be loaded."""


class RequestValidationError(ValueError):
    """Structured input is invalid."""


@dataclass
class RouteRequest:
    available_minutes: int
    start_lat: float | None = None
    start_lng: float | None = None
    start_coordinate_system: str = "GCJ-02"
    interest_tags: list[str] = field(default_factory=list)
    experience_tags: list[str] = field(default_factory=list)
    culture_tags: list[str] = field(default_factory=list)
    must_go_poi_ids: list[str] = field(default_factory=list)
    preferred_zone: str | None = None
    max_walking_km: float | None = None
    avoid_crowds: bool = False
    environment_preference: str | None = None
    travel_pace: str = "standard"
    visit_mode_overrides: dict[str, str] = field(default_factory=dict)
    full_visit_unavailable_poi_ids: list[str] = field(default_factory=list)
    willing_to_buy_tickets: bool = True
    allow_mode_downgrade: bool = True
    avoid_tags: list[str] = field(default_factory=list)
    avoid_poi_ids: list[str] = field(default_factory=list)
    route_mode: str = "plan_for_me"
    start_poi_id: str | None = None


@dataclass(frozen=True)
class VisitTimes:
    quick: float
    standard: float
    deep: float

    def for_pace(self, pace: str) -> float:
        return getattr(self, pace)


@dataclass(frozen=True)
class VisitProfile:
    default_mode: str
    supported_modes: tuple[str, ...]
    modes: dict[str, VisitTimes]

    def stay_for(self, mode: str, pace: str) -> float:
        return self.modes[mode].for_pace(pace)


@dataclass(frozen=True)
class POI:
    id: str
    display_order: int
    poi_type: str
    name_zh: str
    name_en: str
    zone_id: str
    zone_name_en: str
    zone_name_zh: str
    interest_tags: tuple[str, ...]
    experience_tags: tuple[str, ...]
    culture_tags: tuple[str, ...]
    coordinates: tuple[float, float] | None
    original_coordinates: tuple[float | None, float | None]
    original_coordinate_system: str
    visit_profile: VisitProfile
    visit_mode_details: dict[str, dict]
    pending_calibration_modes: tuple[str, ...]
    coordinate_note: str | None
    environment: str
    crowd_level: str | None
    opening_hours: str | None
    ticket_required: bool | None
    reservation_required: bool | None
    route_role_primary: str | None = None
    route_role_eligible: tuple[str, ...] = ()
    counts_as_route_stop: bool = True

    @property
    def effective_primary_role(self):
        return self.route_role_primary

    @property
    def stay_minutes(self):
        """Convenience for the default standard visit; routing uses SelectedVisit."""
        return self.visit_profile.stay_for(self.visit_profile.default_mode, "standard")


@dataclass(frozen=True)
class SelectedVisit:
    poi: POI
    selected_visit_mode: str
    travel_pace: str
    requested_visit_mode: str
    downgrade_reason: str | None = None

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "poi"), name)

    @property
    def stay_minutes(self):
        return self.poi.visit_profile.stay_for(self.selected_visit_mode, self.travel_pace)

    @property
    def environment(self):
        return self.poi.visit_mode_details[self.selected_visit_mode]["environment"]

    @property
    def ticket_required(self):
        return self.poi.visit_mode_details[self.selected_visit_mode]["ticket_required"]

    @property
    def visit_scope(self):
        return self.poi.visit_mode_details[self.selected_visit_mode]["scope"]


@dataclass
class RouteStop:
    poi_id: str
    display_order: int
    poi_type: str
    name_zh: str
    name_en: str
    walk_zone: str
    estimated_stay_minutes: float
    estimated_distance_from_previous_stop_km: float
    estimated_walking_minutes: float
    recommendation_score: float
    matched_tags: dict[str, list[str]]
    reason_for_recommendation: str
    must_go: bool
    selected_visit_mode: str
    travel_pace: str
    requested_visit_mode: str
    downgrade_reason: str | None = None
    opening_status: str = "opening_status_unverified"
    original_opening_hours: str | None = None
    ticket_required: bool | None = None
    reservation_required: bool | None = None
    coordinate_system: str = "GCJ-02"
    estimated_coordinates: tuple[float, float] | None = None
    original_coordinates: tuple[float | None, float | None] | None = None
    original_coordinate_system: str | None = None
    visit_scope: str | None = None
    selection_reason: str = "core_match"
    effective_primary_role: str | None = None

    @property
    def id(self):
        return self.poi_id

    @property
    def estimated_distance_from_previous(self):
        return self.estimated_distance_from_previous_stop_km

    @property
    def estimated_walking_minutes_from_previous(self):
        return self.estimated_walking_minutes


# Compatibility name for existing Python consumers; serialized identity is poi_id.
RouteNode = RouteStop


@dataclass
class RoutePlan:
    status: str
    request: Any
    selected_zone: str | None = None
    ordered_pois: list[RouteNode] = field(default_factory=list)
    cross_zone_required: bool = False
    total_estimated_distance_km: float | None = None
    total_estimated_walking_minutes: float | None = None
    total_stay_minutes: float | None = None
    buffer_minutes: float | None = None
    total_estimated_minutes: float | None = None
    remaining_minutes: float | None = None
    warnings: list[str] = field(default_factory=list)
    explanation: str = ""
    errors: list[str] = field(default_factory=list)
    relaxation_suggestions: list[str] = field(default_factory=list)
    time_budget_scope: str = "Start to final stop's departure; no return journey."
    distance_method: str = "estimated: Haversine × configured walking_distance_factor"
    scoring_distance_basis: str = "Insertion ranking: added route distance; final node score: previous leg distance."
    richness_target: dict[str, int] | None = None
    richness_target_met: bool | None = None
    time_utilization_ratio: float | None = None
    estimated_max_single_leg_km: float | None = None
    long_estimated_leg_warning: bool = False
    composition_diagnostics: dict = field(default_factory=dict)
    planning_distance_m: float | None = None
    planning_duration_min: float | None = None
    walking_distance_m: float | None = None
    walking_duration_s: float | None = None
    walking_legs: list = field(default_factory=list)
    route_geometry: tuple = ()
    walking_data_status: str = 'UNAVAILABLE'
    walking: dict | None = None

    def to_dict(self) -> dict:
        result = asdict(self)
        for stop in result["ordered_pois"]:
            stop["estimated_distance_from_previous"] = stop["estimated_distance_from_previous_stop_km"]
            stop["estimated_walking_minutes_from_previous"] = stop["estimated_walking_minutes"]
        return result
