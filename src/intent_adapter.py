"""The only RouteIntent-to-RouteRequest mapping, used by all three modes."""

import copy

from .models import RouteRequest, RequestValidationError
from .intent_models import RouteMode


def intent_to_route_request(intent):
    if intent.needs_clarification or intent.available_minutes is None:
        raise RequestValidationError("Complete required clarification before routing")
    if type(intent.available_minutes) is not int or intent.available_minutes <= 0:
        raise RequestValidationError("available_minutes must be a positive integer")
    if intent.route_mode == RouteMode.PLAN_FOR_ME and not any((intent.interest_tags, intent.experience_tags, intent.culture_tags)):
        raise RequestValidationError("Plan for me requires at least one existing preference tag")
    if intent.route_mode == RouteMode.PLACES_IN_MIND and not intent.must_go_poi_ids:
        raise RequestValidationError("Places in mind requires selected places")
    if intent.route_mode == RouteMode.SURPRISE_ME and (intent.start_lat is None or intent.start_lng is None):
        raise RequestValidationError("Surprise me requires a usable start")
    if intent.route_mode not in tuple(RouteMode):
        raise RequestValidationError("Unknown route_mode")
    return RouteRequest(route_mode=str(intent.route_mode), **{name: copy.deepcopy(getattr(intent, name)) for name in (
        "available_minutes", "start_poi_id", "start_lat", "start_lng", "start_coordinate_system", "interest_tags",
        "experience_tags", "culture_tags", "avoid_tags", "avoid_poi_ids", "travel_pace", "must_go_poi_ids", "preferred_zone",
        "max_walking_km", "visit_mode_overrides")})
