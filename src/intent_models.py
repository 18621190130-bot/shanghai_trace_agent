"""Unified entry contracts; JSON schemas are exported for clients and providers."""

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from .models import RoutePlan, RequestValidationError


class RouteMode(StrEnum):
    PLAN_FOR_ME = "plan_for_me"
    PLACES_IN_MIND = "places_in_mind"
    SURPRISE_ME = "surprise_me"


class FeasibilityAction(StrEnum):
    EXTEND_TIME = "EXTEND_TIME"
    HELP_ME_CHOOSE = "HELP_ME_CHOOSE"
    EDIT_PLACES = "EDIT_PLACES"


@dataclass
class ClarificationOption:
    label: str
    value: str | int


@dataclass
class ClarificationRequest:
    field: str
    question: str
    input_type: str
    options: list[ClarificationOption] = field(default_factory=list)
    required: bool = True
    max_choices: int | None = None


@dataclass
class RouteIntent:
    route_mode: RouteMode
    start_location_text: str | None = None
    start_lat: float | None = None
    start_lng: float | None = None
    start_coordinate_system: str = "GCJ-02"
    available_minutes: int | None = None
    interest_tags: list[str] = field(default_factory=list)
    experience_tags: list[str] = field(default_factory=list)
    culture_tags: list[str] = field(default_factory=list)
    avoid_tags: list[str] = field(default_factory=list)
    avoid_poi_ids: list[str] = field(default_factory=list)
    unresolved_negative_preferences: list[str] = field(default_factory=list)
    travel_pace: str = "standard"
    must_go_poi_ids: list[str] = field(default_factory=list)
    preferred_zone: str | None = None
    max_walking_km: float | None = None
    visit_mode_overrides: dict[str, str] = field(default_factory=dict)
    surprise_seed: int = 0
    needs_clarification: bool = False
    missing_fields: list[str] = field(default_factory=list)
    clarification_requests: list[ClarificationRequest] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Semantic provenance only; frozen route scoring still consumes taxonomy lists.
    semantic_concepts: list[dict] = field(default_factory=list)
    start_poi_id: str | None = None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise RequestValidationError("RouteIntent must be an object")
        try:
            data = dict(value)
            data["route_mode"] = RouteMode(data["route_mode"])
            data["clarification_requests"] = [ClarificationRequest(
                **{**q, "options": [ClarificationOption(**o) for o in q.get("options", [])]})
                for q in data.get("clarification_requests", [])]
            return cls(**data)
        except (TypeError, ValueError, KeyError) as exc:
            raise RequestValidationError("Invalid RouteIntent object") from exc


@dataclass
class FeasibilitySuggestion:
    action: FeasibilityAction
    label: str


@dataclass
class FeasibilityResult:
    feasible: bool
    estimated_minimum_minutes: float | None
    estimated_distance_km: float | None
    involved_zones: list[str]
    cross_zone_required: bool
    walking_only_feasible: bool
    warnings: list[str] = field(default_factory=list)
    suggestions: list[FeasibilitySuggestion] = field(default_factory=list)
    status: str = "feasible"
    minimum_is_exact: bool = True
    required_poi_ids: list[str] = field(default_factory=list)
    spatial_spread_km: float | None = None
    ordered_required_poi_ids: list[str] = field(default_factory=list)
    estimated_candidate_minutes: float | None = None


@dataclass
class SuggestedSubset:
    keep_poi_ids: list[str]
    remove_poi_ids: list[str]
    estimated_minutes: float
    reason: str
    original_poi_ids: list[str]


@dataclass
class RouteQualityAssessment:
    status: str
    minimum_required_stops: int = 3
    minimum_viable: bool = False
    reasons: list[str] = field(default_factory=list)
    available_minutes: int = 0
    actual_stops: int = 0
    preferred_min_stops: int | None = None
    time_utilization_ratio: float = 0.0
    remaining_minutes: float = 0.0
    candidate_availability: dict[str, int] = field(default_factory=dict)
    question: str | None = None
    options: list[ClarificationOption] = field(default_factory=list)
    clarification_applied: bool = False
    preference_broadening: str | None = None


@dataclass
class EntryResult:
    status: str
    intent: RouteIntent
    route_plan: RoutePlan | None = None
    feasibility: FeasibilityResult | None = None
    surprise_theme: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    route_quality: RouteQualityAssessment | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        if self.route_plan is not None:
            result["route_plan"] = self.route_plan.to_dict()
        return result
