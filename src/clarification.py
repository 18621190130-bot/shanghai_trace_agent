"""Validate input and ask at most two necessary questions per round."""

import copy
import math
import re

from .intent_models import RouteMode, ClarificationOption, ClarificationRequest
from .models import RequestValidationError
from .poi_repository import TAG_GROUPS


class ClarificationLayer:
    def __init__(self, repository, resolver):
        self.repo, self.resolver = repository, resolver

    def prepare(self, intent):
        value = copy.deepcopy(intent)
        try:
            value.route_mode = RouteMode(value.route_mode)
        except (ValueError, TypeError) as exc:
            raise RequestValidationError("Unknown route_mode") from exc
        if value.available_minutes is not None and (type(value.available_minutes) is not int or value.available_minutes <= 0):
            raise RequestValidationError("available_minutes must be a positive integer")
        if value.travel_pace not in ("quick", "standard", "deep"):
            raise RequestValidationError("Invalid travel_pace")
        if type(value.surprise_seed) is not int:
            raise RequestValidationError("surprise_seed must be an integer")
        for name in ("start_location_text", "preferred_zone"):
            item = getattr(value, name)
            if item is not None and (not isinstance(item, str) or not item.strip()):
                raise RequestValidationError(f"{name} must be nonempty text or null")
        if value.preferred_zone is not None and value.preferred_zone not in self.repo.zone_order:
            raise RequestValidationError("Unknown preferred_zone")
        if value.start_coordinate_system not in ("WGS84", "GCJ-02"):
            raise RequestValidationError("Invalid start_coordinate_system")
        if (value.start_lat is None) != (value.start_lng is None):
            raise RequestValidationError("Supply both start coordinates")
        for name, limit in (("start_lat", 90), ("start_lng", 180), ("max_walking_km", None)):
            item = getattr(value, name)
            if item is not None and (isinstance(item, bool) or not isinstance(item, (int, float)) or
                                     not math.isfinite(item) or (limit is not None and abs(item) > limit) or
                                     (limit is None and item <= 0)):
                raise RequestValidationError(f"Invalid {name}")
        for group in (*TAG_GROUPS, "must_go_poi_ids"):
            items = getattr(value, group)
            if not isinstance(items, list) or any(not isinstance(t, str) for t in items):
                raise RequestValidationError(f"{group} must be a list of strings")
            valid = self.repo.taxonomy[group] if group in TAG_GROUPS else {p.id for p in self.repo.get_all_pois()}
            if any(t not in valid for t in items):
                raise RequestValidationError(f"Unknown value in {group}")
            setattr(value, group, list(dict.fromkeys(items)))
        vocabulary = {t for tags in self.repo.taxonomy.values() for t in tags}
        for name, allowed in (("avoid_tags", vocabulary), ("avoid_poi_ids", {p.id for p in self.repo.get_all_pois()})):
            items = getattr(value, name)
            if not isinstance(items, list) or any(not isinstance(t, str) or t not in allowed for t in items):
                raise RequestValidationError(f"Unknown value or invalid list in {name}")
            setattr(value, name, list(dict.fromkeys(items)))
        if (not isinstance(value.unresolved_negative_preferences, list) or
                any(not isinstance(t, str) or not t.strip() for t in value.unresolved_negative_preferences)):
            raise RequestValidationError("unresolved_negative_preferences must contain nonempty text")
        if not isinstance(value.visit_mode_overrides, dict):
            raise RequestValidationError("visit_mode_overrides must be an object")
        for pid, mode in value.visit_mode_overrides.items():
            p = self.repo.get_poi_by_id(pid)
            if p is None or mode not in p.visit_profile.supported_modes:
                raise RequestValidationError("Unsupported visit_mode_overrides")
        # Derived state is rebuilt, never trusted from a client or LLM.
        value.warnings, value.missing_fields, value.clarification_requests = [], [], []
        value.warnings.extend("unresolved_negative_preference: " + text + "; cannot be enforced as a reliable constraint."
                              for text in value.unresolved_negative_preferences)
        if value.start_location_text:
            resolved = self.resolver.resolve(value.start_location_text)
            value.warnings.extend(resolved.warnings)
            if resolved.coordinates and value.start_lat is None:
                value.start_lat, value.start_lng = resolved.coordinates
                value.start_coordinate_system = "GCJ-02"
        if value.start_poi_id:
            poi = self.repo.get_poi_by_id(value.start_poi_id)
            if poi is None or not poi.counts_as_route_stop or (value.preferred_zone and poi.zone_id != value.preferred_zone):
                raise RequestValidationError('Invalid start destination')
            value.start_lat, value.start_lng = poi.coordinates
            value.start_coordinate_system = 'GCJ-02'
            value.preferred_zone = poi.zone_id
            if value.start_poi_id not in value.must_go_poi_ids:value.must_go_poi_ids.insert(0, value.start_poi_id)
        if value.route_mode == RouteMode.PLACES_IN_MIND and value.available_minutes is None and value.must_go_poi_ids:
            # Derive a sufficient planning estimate from selected visits and a feasible path.
            # No user duration constraint and no arbitrary hidden 180-minute cap.
            from .geo_utils import haversine_km
            points = [self.repo.get_poi_by_id(pid) for pid in value.must_go_poi_ids]
            distance = sum(haversine_km(a.coordinates, b.coordinates) for a,b in zip(points, points[1:]))
            if value.start_lat is not None:
                from .geo_utils import to_gcj02
                distance += haversine_km(to_gcj02(value.start_lat,value.start_lng,value.start_coordinate_system),points[0].coordinates)
            stay = sum(p.visit_profile.stay_for(value.visit_mode_overrides.get(p.id,p.visit_profile.default_mode),value.travel_pace) for p in points)
            value.available_minutes = max(1, math.ceil(stay + distance*self.repo.defaults['walking_distance_factor']*1000/self.repo.defaults['walking_speed_m_per_min'] + self.repo.defaults['route_buffer_minutes']))
        questions = []
        if value.available_minutes is None:
            questions.append(ClarificationRequest("available_minutes", "How long would you like to walk?", "single_choice",
                [ClarificationOption(label, minutes) for label, minutes in
                 (("1.5 hours", 90), ("2 hours", 120), ("3 hours", 180), ("Half day", 240))]))
        if value.route_mode == RouteMode.PLAN_FOR_ME and not any(getattr(value, g) for g in TAG_GROUPS):
            questions.append(ClarificationRequest("interest_tags", "What are you most interested in?", "multi_choice",
                [ClarificationOption(tag.replace("_", " ").title(), tag) for tag in self.repo.taxonomy["interest_tags"]], max_choices=3))
        if value.route_mode == RouteMode.PLACES_IN_MIND and not value.must_go_poi_ids:
            questions.append(ClarificationRequest("must_go_poi_ids", "Which places would you like to visit?", "multi_choice",
                [ClarificationOption(f"#{p.display_order} {p.name_en}", p.id) for p in self.repo.get_all_pois()]))
        needs_start = (value.route_mode == RouteMode.SURPRISE_ME and not value.preferred_zone) or bool(value.start_location_text)
        if needs_start and value.start_lat is None:
            questions.append(ClarificationRequest("start_location_text", "Where would you like to start?", "location",
                [ClarificationOption(z["name_en"], z["name_en"]) for z in self.repo.get_raw_data()["metadata"]["walk_zones"]]))
        value.missing_fields = [q.field for q in questions]
        value.clarification_requests = questions[:2]
        value.needs_clarification = bool(questions)
        return value

    def answer(self, intent, answers):
        current = self.prepare(intent)
        allowed = {q.field: q for q in current.clarification_requests}
        if not isinstance(answers, dict) or not set(answers).issubset(allowed):
            raise RequestValidationError("Answer only the current clarification fields")
        for name, answer in answers.items():
            question = allowed[name]
            if question.max_choices is not None and (not isinstance(answer, list) or len(answer) > question.max_choices):
                raise RequestValidationError("Too many choices or invalid multi-choice answer")
            setattr(current, name, answer)
        return self.prepare(current)

    def parse_answer_text(self, intent, field, text):
        """Parse only bounded choice/number inputs, not general natural language.

        Unknown prose goes to the intent parser as a patch to this question,
        never becomes a fresh session.
        """
        questions = {q.field: q for q in self.prepare(intent).clarification_requests}
        if field not in questions:
            raise RequestValidationError("Answer only a current clarification question")
        question = questions[field]
        text = text.strip()
        if field == "available_minutes":
            if text.isdigit():
                number = int(text)
                return question.options[number-1].value if 1 <= number <= len(question.options) else number
            match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?|m)", text, re.IGNORECASE)
            if match:
                minutes = float(match[1]) * (60 if match[2].lower().startswith('h') else 1)
                if math.isfinite(minutes) and minutes.is_integer() and minutes > 0:
                    return int(minutes)
            raise ValueError("Enter a time option, minutes, or e.g. 3 hours")
        if field == "start_location_text":
            if text.isdigit() and 1 <= int(text) <= len(question.options):
                return question.options[int(text)-1].value
            return text
        if field == "must_go_poi_ids":
            values = [v.strip() for v in text.split(';') if v.strip()]
            return self.resolver.select_pois([int(v.lstrip('#')) if v.lstrip('#').isdigit() else v for v in values])
        if field in TAG_GROUPS:
            values = []
            for token in re.split(r",|&|\band\b", text, flags=re.IGNORECASE):
                key = "_".join(token.strip().casefold().split())
                if key.isdigit() and 1 <= int(key) <= len(question.options):
                    key = question.options[int(key)-1].value
                if key not in self.repo.taxonomy[field]:
                    raise ValueError("Preference wording requires structured LLM extraction")
                if key not in values:
                    values.append(key)
            return values
        raise ValueError("Unsupported text answer")
