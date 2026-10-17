"""Deterministic insertion planner with explicit feasibility semantics."""

import copy
import itertools
import math
from statistics import median
from collections import Counter
from dataclasses import asdict
from collections.abc import Mapping

from .geo_utils import haversine_km, to_gcj02
from .models import RequestValidationError, RouteNode, RoutePlan, RouteRequest, SelectedVisit
from .poi_repository import TAG_GROUPS
from .recommendation_engine import RecommendationEngine
from .visit_planner import VisitPlanner
from .route_composition import composition_assessment


def _finite(value, label, low, high=None, positive=False):
    try:
        finite = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise RequestValidationError(f"{label}: expected a finite number")
    if value < low or (high is not None and value > high) or (positive and value == 0):
        raise RequestValidationError(f"{label}: out of range")


class RouteEngine:
    # Shared relative policy for optional expansion, not navigation constraints.
    CANDIDATE_QUALITY = {
        "minimum_tag_ratio": .5,
        "minimum_quality": .6,
        "minimum_score_ratio": .6,
        "leg_growth_weight": .2,
        "marginal_walking_weight": .2,
    }
    def __init__(self, repository):
        self.repository = repository
        self.recommendation = RecommendationEngine(repository)
        self.defaults = dict(repository.defaults)
        self.factor = self.defaults["walking_distance_factor"]
        self.speed = self.defaults["walking_speed_m_per_min"]
        self.buffer = self.defaults["route_buffer_minutes"]
        self.visits = VisitPlanner()

    def _validate(self, value):
        try:
            if isinstance(value, RouteRequest):
                request = copy.deepcopy(value)
            elif isinstance(value, Mapping):
                request = RouteRequest(**dict(value))
            else:
                raise RequestValidationError("Expected RouteRequest or a structured object")
        except TypeError as exc:
            raise RequestValidationError(str(exc)) from exc
        if type(request.available_minutes) is not int or request.available_minutes <= 0:
            raise RequestValidationError("available_minutes: expected a positive integer")
        if request.route_mode not in ('plan_for_me', 'surprise_me', 'places_in_mind'):
            raise RequestValidationError('invalid route_mode')
        _finite(request.available_minutes, "available_minutes", 0, positive=True)
        if (request.start_lat is None) != (request.start_lng is None):
            raise RequestValidationError("start_lat and start_lng must be supplied together")
        if request.start_lat is not None:
            _finite(request.start_lat, "start_lat", -90, 90)
            _finite(request.start_lng, "start_lng", -180, 180)
        if request.start_coordinate_system not in ("WGS84", "GCJ-02"):
            raise RequestValidationError("start_coordinate_system: expected WGS84 or GCJ-02")
        if request.max_walking_km is not None:
            _finite(request.max_walking_km, "max_walking_km", 0, positive=True)
        if type(request.avoid_crowds) is not bool:
            raise RequestValidationError("avoid_crowds: expected boolean")
        if request.environment_preference not in (None, "indoor", "outdoor", "mixed"):
            raise RequestValidationError("environment_preference: expected indoor, outdoor, mixed or null")
        if request.travel_pace not in ("quick", "standard", "deep"):
            raise RequestValidationError("travel_pace: expected quick, standard or deep")
        for flag in ("willing_to_buy_tickets", "allow_mode_downgrade"):
            if type(getattr(request, flag)) is not bool:
                raise RequestValidationError(f"{flag}: expected boolean")
        if not isinstance(request.visit_mode_overrides, dict):
            raise RequestValidationError("visit_mode_overrides: expected a POI-ID to mode object")
        for pid, mode in request.visit_mode_overrides.items():
            poi = self.repository.get_poi_by_id(pid)
            if poi is None:
                raise RequestValidationError(f"Unknown visit_mode_overrides POI: {pid}")
            if mode not in ("walk_stop", "full_visit") or mode not in poi.visit_profile.supported_modes:
                raise RequestValidationError(f"Unsupported visit mode for {pid}: {mode}")
        if request.preferred_zone is not None and request.preferred_zone not in self.repository.zone_order:
            raise RequestValidationError(f"Unknown preferred_zone: {request.preferred_zone}")
        for group in (*TAG_GROUPS, "must_go_poi_ids", "full_visit_unavailable_poi_ids"):
            values = getattr(request, group)
            if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
                raise RequestValidationError(f"{group}: expected a list of strings")
            values = sorted(set(values))
            for val in values:
                if group in ("must_go_poi_ids", "full_visit_unavailable_poi_ids"):
                    if self.repository.get_poi_by_id(val) is None:
                        raise RequestValidationError(f"Unknown {group} POI: {val}")
                    if not self.repository.get_poi_by_id(val).counts_as_route_stop:
                        raise RequestValidationError(f'Internal entity cannot be a route stop: {val}')
                elif val not in self.repository.taxonomy[group]:
                    raise RequestValidationError(f"Unknown {group}: {val}")
            setattr(request, group, values)
        for name in ("avoid_tags", "avoid_poi_ids"):
            values = getattr(request, name)
            allowed = ({tag for tags in self.repository.taxonomy.values() for tag in tags}
                       if name == "avoid_tags" else {p.id for p in self.repository.get_all_pois()})
            if not isinstance(values, list) or any(not isinstance(v, str) or v not in allowed for v in values):
                raise RequestValidationError(f"{name}: invalid list or unknown value")
            setattr(request, name, sorted(set(values)))
        return request

    def _avoided(self, poi, request):
        return poi.id in request.avoid_poi_ids or bool(set(request.avoid_tags) &
            {tag for group in TAG_GROUPS for tag in getattr(poi, group)})

    def is_candidate_worth_adding(self, candidate, core_route, trial, req, zone, start):
        """Compare a new optional stop with the existing core, not a score constant.

        Tag benefit is relative to the core's median positive tag score. Geometry
        supplies bounded relative penalties; a long leg is never an absolute veto.
        Marginal walking is relative to the core's existing visit+walking cost.
        The core is fixed throughout refinement so weak candidates cannot lower
        their own reference quality. Explicit must-go stops bypass the policy.
        """
        if candidate.id in req.must_go_poi_ids:
            return True
        if candidate.zone_id != zone or not self._relevant(candidate, req) or self._avoided(candidate, req):
            return False
        if not core_route or not any(getattr(req, g) for g in TAG_GROUPS):
            return True  # A feasible seed or a request with no expressed tag preference.
        scores = [self.recommendation.tag_score(p, req) for p in core_route]
        positive = [score for score in scores if score > 0]
        if not positive:
            return self.recommendation.tag_score(candidate, req) > 0
        tag_ratio = self.recommendation.tag_score(candidate, req) / median(positive)
        # Supporting preferences are bonuses, not a denominator that can veto
        # an otherwise strong core-interest match.
        interest_weight = self.recommendation.weights["interest_tag_match"]
        # Opt-in West Bund uses the same OR semantics as _relevant: one real core
        # theme is sufficient. Multi-theme bonus still ranks candidates but cannot
        # turn the best seed's number of tags into an implicit AND admission rule.
        core_or = zone in self.defaults.get('route_composition_enabled_zones', [])
        def core_interest_score(p):
            matches = len(set(p.interest_tags) & set(req.interest_tags))
            return (int(matches > 0) if core_or else matches) * interest_weight
        core_interest_scores = [core_interest_score(p) for p in core_route if core_interest_score(p) > 0]
        if core_interest_scores:
            tag_ratio = max(tag_ratio, core_interest_score(candidate) / median(core_interest_scores))
        policy = self.CANDIDATE_QUALITY
        if tag_ratio < policy["minimum_tag_ratio"]:
            return False
        # Existing scoring distinguishes equal-tag candidates by marginal movement.
        # Compare against the core's existing leg scores, never an absolute cutoff.
        core_scores = [self.recommendation.score(p, req, zone, leg)
                       for p, leg in zip(core_route, self._legs(core_route, start))
                       if self.recommendation.tag_score(p, req) > 0]
        # Replacement searches must not hide a candidate's cost by deleting core stops.
        insertion = self._shortest_order(core_route + [candidate], start)
        added_distance = max(0.0, self._metrics(insertion, start)[0] - self._metrics(core_route, start)[0])
        reference_score = median(core_scores)
        score_ratio = (self.recommendation.score(candidate, req, zone, added_distance) / reference_score
                       if reference_score > 0 else 1.0)
        if core_interest_scores:
            core_request = copy.deepcopy(req)
            core_request.experience_tags = []
            core_request.culture_tags = []
            if core_or:
                # Compare a genuinely shared requested theme, never same-zone alone.
                shared = sorted(set(candidate.interest_tags) & set(req.interest_tags))
                if shared:
                    core_request.interest_tags = [shared[0]]
            reference_scores = [self.recommendation.score(p, core_request, zone, leg)
                for p, leg in zip(core_route, self._legs(core_route, start))
                if (self.recommendation.tag_score(p, core_request) > 0 if core_or else core_interest_score(p) > 0)]
            core_reference = median(reference_scores) if reference_scores else 0
            if core_reference > 0:
                score_ratio = max(score_ratio, self.recommendation.score(candidate, core_request, zone, added_distance) / core_reference)
        if score_ratio < policy["minimum_score_ratio"]:
            return False
        _, base_walk, base_stay, _ = self._metrics(core_route, start)
        _, trial_walk, _, _ = self._metrics(trial, start)
        base_leg = max(self._legs(core_route, start), default=0.0)
        trial_leg = max(self._legs(trial, start), default=0.0)
        # With a zero-length core, compare movement cost with its visit duration;
        # do not treat every nonzero insertion as an infinitely large jump.
        leg_reference = base_leg or median(p.stay_minutes for p in core_route) * self.speed / 1000
        leg_growth = min(1.0, max(0.0, trial_leg-base_leg) / leg_reference)
        marginal_walk = min(1.0, max(0.0, trial_walk-base_walk) / (base_walk+base_stay))
        quality = (tag_ratio - policy["leg_growth_weight"] * leg_growth
                   - policy["marginal_walking_weight"] * marginal_walk)
        return quality >= policy["minimum_quality"]

    def is_worth_adding_for_utilization(self, candidate, core_route, trial, req, zone, start):
        """Compatibility alias; both expansion stages use the same policy."""
        return self.is_candidate_worth_adding(candidate, core_route, trial, req, zone, start)

    def _improve_utilization(self, route, candidates, req, zone, start, cap):
        """Bounded same-zone refinement only for underused preference routes.

        Keep well-used results unchanged. Geometry uses existing ordering/metrics;
        no single-leg constraint or navigation behavior is introduced here.
        """
        if self._metrics(route, start)[3] / req.available_minutes >= .65 or not any(getattr(req, g) for g in TAG_GROUPS):
            return route
        required = [p for p in route if p.id in req.must_go_poi_ids]
        optional = [p for p in candidates if p.zone_id == zone and p.id not in req.must_go_poi_ids and self._relevant(p, req)]
        # Current catalog has <=8 POIs per zone. Bound refinement for future growth.
        optional = sorted(optional, key=lambda p: (-self.recommendation.tag_score(p, req), p.id))[:8]
        if len(required) > cap or cap > 5:
            return route
        options = []
        original_ids = {p.id for p in route}
        original_total = self._metrics(route, start)[3]
        for count in range(max(0, len(route)-len(required)), min(cap-len(required), len(optional))+1):
            for subset in itertools.combinations(optional, count):
                selected = required + list(subset)
                if not selected:
                    continue
                ordered = self._shortest_order(selected, start)
                mode_choices = []
                for visit in ordered:
                    modes = [visit]
                    fallback = self.visits.budget_fallback(visit, req)
                    if fallback is not None:
                        modes.append(fallback)
                    if (visit.id not in req.visit_mode_overrides and visit.selected_visit_mode == "walk_stop"
                            and "full_visit" in visit.visit_profile.supported_modes):
                        expanded_request = copy.deepcopy(req)
                        expanded_request.visit_mode_overrides[visit.id] = "full_visit"
                        expanded = self.visits.resolve(visit.poi, expanded_request)
                        if expanded is not None and expanded.selected_visit_mode == "full_visit":
                            modes.append(SelectedVisit(visit.poi, "full_visit", req.travel_pace, visit.requested_visit_mode))
                    mode_choices.append(modes)
                for visits in itertools.product(*mode_choices):
                    trial = list(visits)
                    if not self._fits(trial, req, start):
                        continue
                    distance, _, _, total = self._metrics(trial, start)
                    ratio = total / req.available_minutes
                    if total <= original_total:
                        continue
                    if any(not self.is_candidate_worth_adding(p, route, trial, req, zone, start)
                           for p in trial if p.id not in original_ids):
                        continue
                    # Relevance, continuity and richer experience precede the soft time band.
                    relevance = sum(self.recommendation.tag_score(p, req) for p in trial) / len(trial)
                    options.append(((-relevance, distance, -len(trial), abs(ratio-.85),
                                     tuple((p.id, p.selected_visit_mode) for p in trial)), trial))
            if any(.70 <= self._metrics(trial, start)[3]/req.available_minutes <= .95 for _, trial in options):
                # A useful 70–95% route exists at this stop count; do not add more stops.
                break
        return min(options, key=lambda item: item[0])[1] if options else route

    def _distance(self, a, b):
        return haversine_km(a, b) * self.factor

    def _legs(self, route, start):
        previous = start
        legs = []
        for poi in route:
            legs.append(0.0 if previous is None else self._distance(previous, poi.coordinates))
            previous = poi.coordinates
        return legs

    def _metrics(self, route, start):
        distance = math.fsum(self._legs(route, start))
        walking = distance * 1000 / self.speed
        stay = math.fsum(p.stay_minutes for p in route)
        total = stay + walking + self.buffer
        return distance, walking, stay, total

    def _fits(self, route, request, start):
        distance, _, _, total = self._metrics(route, start)
        return total <= request.available_minutes and (request.max_walking_km is None or distance <= request.max_walking_km)

    def _zone_score(self, zone, candidates, request, start):
        pois = [p for p in candidates if p.zone_id == zone]
        if not pois:
            return -math.inf
        scores = sorted((self.recommendation.tag_score(p, request) for p in pois), reverse=True)
        score = sum(scores[:self.defaults["max_pois_default"]])
        if start is not None:
            score -= min(self._distance(start, p.coordinates) for p in pois) * self.recommendation.weights["distance_penalty_per_km"]
        return score

    def _choose_zone(self, candidates, required, request, start):
        zones = [z for z in self.repository.zone_order if any(p.zone_id == z for p in candidates)]
        if required:
            counts = Counter(p.zone_id for p in required)
            if request.preferred_zone in counts:
                return request.preferred_zone, "Primary zone follows your preference within the must-go zones."
            zone = min(counts, key=lambda z: (-counts[z], -self._zone_score(z, candidates, request, start), z))
            return zone, "Primary zone follows must-go stops; tag affinity breaks ties."
        if request.preferred_zone is not None:
            return request.preferred_zone, "Primary zone follows your explicit preference."
        has_tags = any(getattr(request, g) for g in TAG_GROUPS)
        if has_tags:
            zone = min(zones, key=lambda z: (-self._zone_score(z, candidates, request, start), z))
            return zone, "Primary zone maximizes eligible top-five tag affinity minus estimated approach-distance penalty."
        if start is not None:
            zone = min(zones, key=lambda z: (min(self._distance(start, p.coordinates) for p in candidates if p.zone_id == z), z))
            return zone, "With no requested tags, the nearest eligible zone is selected."
        default_zone = self.defaults.get("default_walk_zone", "wukang_fuxing_xujiahui")
        zone = default_zone if default_zone in zones else sorted(zones)[0]
        return zone, "With no tags, start or zone preference, the configured Wukang–Fuxing–Xujiahui zone is the default when available."

    def _richness_target(self, request):
        for target in self.defaults.get("richness_targets", []):
            if request.available_minutes <= target["max_minutes"]:
                return {"min_stops": target["min_stops"], "max_stops": target["max_stops"]}
        return None

    def _relevant(self, poi, request):
        # Same-zone bonus alone must never make an unrelated optional stop relevant.
        if request.interest_tags:
            return bool(set(poi.interest_tags) & set(request.interest_tags))
        if request.experience_tags or request.culture_tags:
            return self.recommendation.tag_score(poi, request) > 0
        return True

    def _shortest_order(self, route, start):
        if len(route) <= 8:
            return list(min(itertools.permutations(route),
                            key=lambda r: (self._metrics(r, start)[0], tuple(p.id for p in r)))) if route else []
        return self._order_required(route, start)

    def _composition_enabled(self, req, zone):
        return (zone in self.defaults.get('route_composition_enabled_zones', [])
                and req.route_mode in ('plan_for_me', 'surprise_me'))

    def _repair_composition(self, route, candidates, req, zone, start, cap):
        """Bounded single-stop replacement/insertion through existing quality/budget gates."""
        if composition_assessment(route, True)['route_composition_passed']:
            return route
        options = []
        relevant = [p for p in candidates if p.zone_id == zone and self._relevant(p, req)
                    and p.id not in {v.id for v in route}]
        for candidate in relevant:
            bases = [route] if len(route) < cap else []
            bases += [route[:i] + route[i+1:] for i, p in enumerate(route) if p.id not in req.must_go_poi_ids]
            for base in bases:
                trial = self._shortest_order(base + [candidate], start)
                if len(trial) < 3 or not composition_assessment(trial, True)['route_composition_passed']:
                    continue
                if not self._fits(trial, req, start) or not self.is_candidate_worth_adding(candidate, base, trial, req, zone, start):
                    continue
                relevance = sum(self.recommendation.tag_score(p, req) for p in trial) / len(trial)
                options.append(((-relevance, self._metrics(trial, start)[0], tuple(p.id for p in trial)), trial))
        return min(options, key=lambda x: x[0])[1] if options else route

    def _budget_downgrade_required(self, route, request, start):
        """Keep default/explicit visits unless the whole required route does not fit."""
        if self._fits(route, request, start):
            return route
        alternatives = []
        for index, visit in enumerate(route):
            fallback = self.visits.budget_fallback(visit, request)
            if fallback is not None:
                saving = visit.stay_minutes - fallback.stay_minutes
                alternatives.append(((visit.id in request.visit_mode_overrides, -saving, visit.id), index, fallback))
        adjusted = list(route)
        for _, index, fallback in sorted(alternatives):
            adjusted[index] = fallback
            if self._fits(adjusted, request, start):
                break
        return adjusted

    def _order_required(self, required, start):
        """Nearest neighbor from deterministic seeds, then open-path 2-opt."""
        if not required:
            return []
        seeds = [None] if start is not None else sorted(required, key=lambda p: p.id)
        routes = []
        for seed in seeds:
            route = [] if seed is None else [seed]
            remaining = [p for p in required if p != seed]
            previous = start if seed is None else seed.coordinates
            while remaining:
                poi = min(remaining, key=lambda p: (self._distance(previous, p.coordinates), p.id))
                route.append(poi)
                remaining.remove(poi)
                previous = poi.coordinates
            while True:
                before = self._metrics(route, start)[0]
                alternatives = [route[:i] + list(reversed(route[i:j])) + route[j:]
                                for i in range(len(route)) for j in range(i + 2, len(route) + 1)]
                if not alternatives:
                    break
                best = min(alternatives, key=lambda r: (self._metrics(r, start)[0], tuple(p.id for p in r)))
                if self._metrics(best, start)[0] >= before - 1e-12:
                    break
                route = best
            routes.append(route)
        return min(routes, key=lambda r: (self._metrics(r, start)[0], tuple(p.id for p in r)))

    def _required_lower_distance(self, required, start):
        """MST is a lower bound on any open walk connecting all required points."""
        points = [p.coordinates for p in required]
        if start is not None:
            points.append(start)
        if len(points) < 2:
            return 0.0
        seen, remaining, total = [points[0]], list(points[1:]), 0.0
        while remaining:
            edge, index = min((self._distance(a, b), i) for a in seen for i, b in enumerate(remaining))
            total += edge
            seen.append(remaining.pop(index))
        return total

    def check_opening_constraints(self, poi):
        """Extension seam: Phase 1 does not parse date-dependent opening text."""
        return "opening_status_unverified"

    def generate_route(self, request):
        original = asdict(request) if isinstance(request, RouteRequest) else copy.deepcopy(request)
        try:
            req = self._validate(request)
        except RequestValidationError as exc:
            return RoutePlan("validation_error", original, errors=[str(exc)],
                             explanation="The structured request is invalid; no route was generated.")
        start = None if req.start_lat is None else to_gcj02(req.start_lat, req.start_lng, req.start_coordinate_system)
        scope = ("Provided start to final stop's departure; approach walking included; no return journey."
                 if start is not None else "First stop's arrival to final stop's departure; approach to the first stop excluded; no return journey.")
        warnings = ["estimated_geometry: approximate coordinates and a constant detour factor; not verified street navigation.",
                    "walking_distance_scope: approach and inter-stop legs only; movement inside each POI is not separately modeled.",
                    "opening_status_unverified: opening text is not parsed; only request-supplied full_visit unavailability is applied."]
        missing = self.repository.get_missing_coordinate_ids()
        if missing:
            warnings.append("exclude_from_distance_based_route: " + ", ".join(missing))
        if start is not None and req.start_coordinate_system == "WGS84":
            warnings.append("start_coordinate_conversion: WGS84 converted approximately to GCJ-02 in memory.")
        all_pois = [p for p in self.repository.get_all_pois() if p.counts_as_route_stop]
        raw_required = [self.repository.get_poi_by_id(pid) for pid in req.must_go_poi_ids]
        resolved = {p.id: self.visits.resolve(p, req) for p in all_pois}
        candidates = [resolved[p.id] for p in all_pois if p.coordinates is not None and resolved[p.id] is not None
                      and (p.id in req.must_go_poi_ids or not self._avoided(p, req))]
        for poi in raw_required:
            if self._avoided(poi, req):
                warnings.append(f"negative_preference_overridden_by_must_go: {poi.id}; explicit must-go takes priority.")
        cross = len({p.zone_id for p in raw_required}) > 1
        if cross:
            warnings.append("cross_zone_required: inter-zone movement is estimated entirely on foot; no transit is included.")
        warnings.append("cross_zone_transfer_penalty_inactive: configured symbolic penalty is not assigned an arbitrary numeric value.")

        def failure(status, reason, zone=None, suggestions=None):
            return RoutePlan(status, original, selected_zone=zone, cross_zone_required=cross,
                             warnings=list(warnings), errors=[reason], explanation=reason,
                             time_budget_scope=scope,
                             richness_target=self._richness_target(req), richness_target_met=False,
                             relaxation_suggestions=suggestions or ["Increase the time or walking-distance budget, or revise must-go requirements."])

        missing_required = [p.id for p in raw_required if p.coordinates is None]
        if missing_required:
            return failure("infeasible", "Must-go POIs lack usable coordinates: " + ", ".join(missing_required),
                           suggestions=["Provide verified coordinates for these POIs, or explicitly remove them from must-go requirements."])
        blocked_required = [p.id for p in raw_required if resolved[p.id] is None]
        if blocked_required:
            return failure("infeasible", "Required full_visit is unavailable and no allowed walk_stop fallback exists: " + ", ".join(blocked_required),
                           suggestions=["Change the access/ticket preference only if appropriate, choose another visit time, or explicitly revise must-go requirements."])
        required = [resolved[p.id] for p in raw_required]
        blocked_optional = [p.id for p in all_pois if resolved[p.id] is None and p.id not in req.must_go_poi_ids]
        if blocked_optional:
            warnings.append("full_visit_unavailable_without_allowed_fallback: " + ", ".join(blocked_optional))
        if not candidates:
            return failure("infeasible", "No eligible POIs have usable coordinates and compatible access/avoidance preferences.",
                           suggestions=["Review the selected preferences, access restrictions or catalog coordinates."])
        zone, zone_reason = self._choose_zone(candidates, required, req, start)
        if req.preferred_zone is not None and req.preferred_zone != zone:
            warnings.append(f"preferred_zone_unfulfilled: {req.preferred_zone}; must-go requirements take priority.")
        minimum_required = [self.visits.budget_fallback(p, req) or p for p in required]
        stay_lower = math.fsum(p.stay_minutes for p in minimum_required) + self.buffer
        distance_lower = self._required_lower_distance(required, start)
        if stay_lower + distance_lower * 1000 / self.speed > req.available_minutes:
            return failure("infeasible", f"Proven required-time lower bound is {stay_lower + distance_lower * 1000 / self.speed:.2f} estimated minutes, exceeding {req.available_minutes}.", zone)
        if req.max_walking_km is not None and distance_lower > req.max_walking_km:
            return failure("infeasible", f"Proven required-distance lower bound is {distance_lower:.3f} estimated km, exceeding {req.max_walking_km}.", zone)
        route = self._order_required(required, start)
        if required and not self._fits(route, req, start):
            # Geometry is independent of visit duration: optimize order before downgrading.
            if len(required) <= 8:
                route = self._shortest_order(route, start)
            route = self._budget_downgrade_required(route, req, start)
            if not self._fits(route, req, start):
                if len(required) <= 8:
                    return failure("infeasible", "All must-go visit orders and the minimum allowed mode durations were checked; none satisfies the estimated budgets.", zone)
                return failure("no_feasible_route_found", "The deterministic heuristic did not find a must-go order within the budgets, even with allowed mode fallback; impossibility was not proven.", zone)
        optional = [p for p in candidates if p.zone_id == zone and p.id not in req.must_go_poi_ids and self._relevant(p, req)]
        explicit_only = req.route_mode == 'places_in_mind' and zone in self.defaults.get('route_composition_enabled_zones', [])
        if explicit_only:
            optional = []
        if not required and not optional:
            return failure("infeasible", "No eligible POIs matched the current zone, interests and avoidance preferences.", zone,
                           suggestions=["Broaden one preference, allow a compatible theme, or broaden the selected area."])
        cap = max(self.defaults["max_pois_default"], len(required))
        richness = self._richness_target(req)
        # Aim at the upper end of the soft range without suppressing required stops.
        if richness is not None:
            cap = max(len(required), min(cap, richness["max_stops"]))
        selection_reasons = {p.id: "must_go" for p in required}
        quality_rejected = False
        while optional and len(route) < cap:
            current_distance = self._metrics(route, start)[0]
            options = []
            for poi in optional:
                insertions = [route[:i] + [poi] + route[i:] for i in range(len(route) + 1)]
                trials = [self._shortest_order(r, start) if len(r) <= 5 else r for r in insertions]
                feasible = [r for r in trials if self._fits(r, req, start)]
                if not feasible:
                    fallback = self.visits.budget_fallback(poi, req)
                    if fallback is not None:
                        insertions = [route[:i] + [fallback] + route[i:] for i in range(len(route) + 1)]
                        trials = [self._shortest_order(r, start) if len(r) <= 5 else r for r in insertions]
                        feasible = [r for r in trials if self._fits(r, req, start)]
                if not feasible:
                    continue
                trial = min(feasible, key=lambda r: (self._metrics(r, start)[0], tuple(p.id for p in r)))
                effective = next(p for p in trial if p.id == poi.id)
                if not self.is_candidate_worth_adding(effective, route, trial, req, zone, start):
                    quality_rejected = True
                    continue
                added = max(0.0, self._metrics(trial, start)[0] - current_distance)
                score = self.recommendation.score(poi, req, zone, added)
                environment, crowd = self.recommendation.preference_key(effective, req)
                options.append(((-score, environment, crowd, added, poi.id), trial, poi))
            if not options:
                break
            reason = "core_match" if not route or richness is None else "richness_expansion"
            _, route, chosen = min(options, key=lambda option: option[0])
            selection_reasons[chosen.id] = reason
            optional.remove(chosen)
        if not route:
            # Every eligible single-stop route was checked in the insertion loop.
            return failure("infeasible", "No eligible single-stop route in the selected zone fits the estimated budgets.", zone)
        if not explicit_only:
            route = self._improve_utilization(route, candidates, req, zone, start, cap)
        composition_enabled = self._composition_enabled(req, zone)
        if composition_enabled:
            before_composition = {p.id for p in route}
            route = self._repair_composition(route, candidates, req, zone, start, cap)
            for poi in route:
                if poi.id not in before_composition:
                    selection_reasons[poi.id] = 'composition_repair'
        composition = composition_assessment(route, composition_enabled)
        # Tie-break only among equal-distance permutations: geometry outranks soft composition.
        if composition_enabled and not composition['transition_soft_preference_passed'] and len(route) <= 5:
            distance = self._metrics(route, start)[0]
            equivalent = [list(p) for p in itertools.permutations(route)
                          if abs(self._metrics(p, start)[0] - distance) < 1e-9]
            route = min(equivalent, key=lambda p: (composition_assessment(p, True)['longest_transition_run'], tuple(x.id for x in p)))
            composition = composition_assessment(route, True)
        for poi in route:
            if poi.id not in selection_reasons:
                selection_reasons[poi.id] = "time_fill"
        # A selected Core start is a destination contract, not just an origin coordinate.
        if req.start_poi_id:
            first = next((p for p in route if p.id == req.start_poi_id), None)
            if first is None:return failure('no_feasible_route_found', 'Selected start must be included.', zone)
            route = [first] + [p for p in route if p.id != req.start_poi_id]
        # Defensive final verification after all insertions and ordering.
        if not self._fits(route, req, start) or not set(req.must_go_poi_ids).issubset({p.id for p in route}):
            return failure("no_feasible_route_found", "Final hard-constraint verification failed.", zone)
        nodes = []
        for poi, leg in zip(route, self._legs(route, start)):
            if poi.selected_visit_mode == "full_visit" and poi.requested_visit_mode == "walk_stop":
                warnings.append(f"visit_mode_expanded_for_time_utilization: {poi.id}; walk_stop -> full_visit; still a product planning estimate.")
            if poi.downgrade_reason:
                warnings.append(f"visit_mode_downgraded: {poi.id}: {poi.requested_visit_mode} -> {poi.selected_visit_mode}; {poi.downgrade_reason}.")
                if poi.downgrade_reason == "full_visit_unavailable":
                    warnings.append(f"walk_stop_access_unverified: {poi.id}; exterior access is assumed for this fallback, not checked live.")
            if poi.selected_visit_mode in poi.pending_calibration_modes:
                warnings.append(f"visit_time_pending_manual_calibration: {poi.id} {poi.selected_visit_mode}; product estimate.")
            if poi.poi_type in ("street", "district"):
                warnings.append(f"representative_coordinate: {poi.id}; this anchor is not the whole area's unique location or entry/exit.")
            if poi.coordinate_note and "Needs manual coordinate review" in poi.coordinate_note:
                warnings.append(f"coordinate_pending_manual_review: {poi.id}; {poi.coordinate_note}")
            if poi.original_coordinate_system.startswith("WGS84"):
                warnings.append(f"coordinate_conversion: {poi.id} converted approximately from WGS84 to GCJ-02 in memory.")
            if poi.crowd_level is None:
                warnings.append(f"crowd_level_unknown: {poi.id}; low crowd is not guaranteed.")
            if req.environment_preference not in (None, "mixed") and poi.environment != req.environment_preference:
                warnings.append(f"environment_preference_unfulfilled: {poi.id} is {poi.environment}, requested {req.environment_preference}.")
            if poi.ticket_required is None or poi.reservation_required is None:
                warnings.append(f"entry_requirements_unverified: {poi.id}; unknown does not mean free or reservation-free.")
            if poi.ticket_required is True:
                warnings.append(f"ticket_required: {poi.id}; ticket cost and availability are not checked.")
            if poi.reservation_required is True and poi.selected_visit_mode == "full_visit":
                warnings.append(f"reservation_required: {poi.id}; reservation availability is not checked.")
            nodes.append(RouteNode(
                poi_id=poi.id, display_order=poi.display_order, poi_type=poi.poi_type,
                name_zh=poi.name_zh, name_en=poi.name_en, walk_zone=poi.zone_id,
                estimated_stay_minutes=poi.stay_minutes, estimated_distance_from_previous_stop_km=leg,
                estimated_walking_minutes=leg * 1000 / self.speed,
                recommendation_score=self.recommendation.score(poi, req, zone, leg),
                matched_tags=self.recommendation.matched_tags(poi, req),
                reason_for_recommendation=(self.recommendation.explanation(poi, req, zone)
                                          + f" Visit mode: {poi.selected_visit_mode}; pace: {poi.travel_pace}."
                                          + (f" Downgraded because: {poi.downgrade_reason}." if poi.downgrade_reason else "")),
                must_go=poi.id in req.must_go_poi_ids, opening_status=self.check_opening_constraints(poi),
                selected_visit_mode=poi.selected_visit_mode, travel_pace=poi.travel_pace,
                requested_visit_mode=poi.requested_visit_mode, downgrade_reason=poi.downgrade_reason,
                original_opening_hours=poi.opening_hours, ticket_required=poi.ticket_required,
                reservation_required=poi.reservation_required if poi.selected_visit_mode == "full_visit" else False,
                estimated_coordinates=poi.coordinates,
                original_coordinates=poi.original_coordinates, original_coordinate_system=poi.original_coordinate_system,
                visit_scope=poi.visit_scope, selection_reason=selection_reasons[poi.id],
                effective_primary_role=poi.effective_primary_role))
        richness_met = None if richness is None else richness["min_stops"] <= len(route) <= richness["max_stops"]
        if richness_met is False:
            reason = ("additional candidates failed the route-quality gate"
                      if len(route) < richness['min_stops'] and quality_rejected else
                      "eligible candidates, access, time or walking budgets limited expansion"
                      if len(route) < richness['min_stops'] else "explicit must-go stops exceed the preferred maximum")
            warnings.append(f"richness_target_unmet: Preferred route richness was not reached because {reason}. "
                            f"Preferred {richness['min_stops']}-{richness['max_stops']} stops; actual {len(route)}. This is a soft preference, not a failure.")
        distance, walking, stay, total = self._metrics(route, start)
        utilization = total / req.available_minutes
        max_leg = max(self._legs(route, start), default=0.0)
        long_leg = max_leg > 2.0
        if utilization < .65:
            warnings.append("Limited matching POIs prevented fuller use of the available time within the checked candidate quality, modes, same-zone pool and stop cap.")
        if long_leg:
            warnings.append("Estimated geometry suggests a long walking leg; real street routing has not yet been verified. DEFERRED TO MAP API PHASE.")
        status = 'composition_failure' if composition_enabled and len(route) >= 3 and not composition['route_composition_passed'] else 'success'
        return RoutePlan(status, original, selected_zone=zone, ordered_pois=nodes, cross_zone_required=cross,
                         composition_diagnostics=composition,
                         errors=[composition['failure_reason']] if status == 'composition_failure' else [],
                         total_estimated_distance_km=distance, total_estimated_walking_minutes=walking,
                         total_stay_minutes=stay, buffer_minutes=self.buffer, total_estimated_minutes=total,
                         remaining_minutes=req.available_minutes - total, warnings=warnings,
                         time_utilization_ratio=utilization, estimated_max_single_leg_km=max_leg,
                         long_estimated_leg_warning=long_leg,
                         richness_target=richness, richness_target_met=richness_met,
                         explanation=zone_reason + " Must-go stops are retained; optional expansion uses a shared relative route-quality gate before score-ranked feasible insertion with geographic reordering. Richness and utilization are soft preferences. Selected mode and pace determine stay time. Every accepted route is rechecked against both budgets.",
                         time_budget_scope=scope)
