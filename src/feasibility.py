"""Required-stop preflight, independent of optional recommendations.

Distances use the same configured estimate as Phase 1. For <=12 required
points, Held-Karp solves the shortest open path exactly in this estimate model.
Larger sets use a spanning-tree lower bound and a nearest-neighbor candidate.
"""

import copy
import itertools
import math
from functools import lru_cache

from .geo_utils import haversine_km, to_gcj02
from .intent_adapter import intent_to_route_request
from .intent_models import FeasibilityResult, FeasibilitySuggestion, FeasibilityAction, SuggestedSubset
from .models import RequestValidationError
from .visit_planner import VisitPlanner


class FeasibilityChecker:
    def __init__(self, repository, transfer_spread_km=3.0):
        self.repo = repository
        self.factor = repository.defaults["walking_distance_factor"]
        self.speed = repository.defaults["walking_speed_m_per_min"]
        self.buffer = repository.defaults["route_buffer_minutes"]
        # Conservative product guard, not a measured transport requirement.
        self.transfer_spread_km = transfer_spread_km

    def distance(self, a, b):
        return haversine_km(a, b) * self.factor

    def shortest_path(self, pois, start):
        n = len(pois)
        if not n:
            return 0.0, [], True, 0.0
        legs = [[self.distance(a.coordinates, b.coordinates) for b in pois] for a in pois]
        approaches = [0.0 if start is None else self.distance(start, p.coordinates) for p in pois]
        if n <= 12:
            @lru_cache(None)
            def solve(mask, last):
                previous_mask = mask ^ (1 << last)
                if not previous_mask:
                    return approaches[last], (last,)
                return min((solve(previous_mask, j)[0] + legs[j][last], solve(previous_mask, j)[1] + (last,))
                           for j in range(n) if previous_mask & (1 << j))
            distance, order = min(solve((1 << n)-1, j) for j in range(n))
            return distance, [pois[j].id for j in order], True, distance
        # A lower bound is not reported as a proved feasible route.
        points = [p.coordinates for p in pois] + ([] if start is None else [start])
        seen, remaining, lower = [points[0]], points[1:], 0.0
        while remaining:
            edge, idx = min((self.distance(a, b), i) for a in seen for i, b in enumerate(remaining))
            lower += edge
            seen.append(remaining.pop(idx))
        candidates = []
        for first in range(n):
            remaining = set(range(n)) - {first}
            order, distance = [first], approaches[first]
            while remaining:
                nxt = min(remaining, key=lambda j: (legs[order[-1]][j], pois[j].id))
                distance += legs[order[-1]][nxt]
                order.append(nxt)
                remaining.remove(nxt)
            candidates.append((distance, tuple(pois[i].id for i in order)))
        upper, order = min(candidates)
        return lower, list(order), False, upper

    def check(self, intent):
        req = intent_to_route_request(intent)
        ids = list(intent.must_go_poi_ids)
        if not ids:
            raise RequestValidationError("Feasibility check needs selected places")
        pois = [self.repo.get_poi_by_id(pid) for pid in ids]
        if any(p is None for p in pois):
            raise RequestValidationError("Unknown must-go place")
        zones = sorted({p.zone_id for p in pois})
        cross = len(zones) > 1
        actions = [FeasibilitySuggestion(action, label) for action, label in (
            (FeasibilityAction.EXTEND_TIME, "Extend my time"),
            (FeasibilityAction.HELP_ME_CHOOSE, "Keep my time and help me choose"),
            (FeasibilityAction.EDIT_PLACES, "Edit selected places"))]
        if any(p.coordinates is None for p in pois):
            return FeasibilityResult(False, None, None, zones, cross, False,
                ["Selected place has no usable coordinate; no distance can be claimed."], actions,
                "missing_coordinates", False, ids)
        start = None if req.start_lat is None else to_gcj02(req.start_lat, req.start_lng, req.start_coordinate_system)
        lower, order, exact, upper = self.shortest_path(pois, start)
        spread = max((self.distance(a.coordinates, b.coordinates) for a, b in itertools.combinations(pois, 2)), default=0)
        interzone_spread = max((self.distance(a.coordinates, b.coordinates) for a, b in itertools.combinations(pois, 2)
                               if a.zone_id != b.zone_id), default=0)
        planner = VisitPlanner()
        visits = [planner.resolve(p, req) for p in pois]
        minimum_stay = math.fsum((planner.budget_fallback(v, req) or v).stay_minutes for v in visits)
        minimum = minimum_stay + lower * 1000 / self.speed + self.buffer
        candidate = minimum_stay + upper * 1000 / self.speed + self.buffer
        transfer = cross and interzone_spread > self.transfer_spread_km
        budget_fits = candidate <= req.available_minutes and (req.max_walking_km is None or upper <= req.max_walking_km)
        feasible = budget_fits and not transfer
        warnings = ["Distances and visit times are planning estimates; no street routing or transport times."]
        if req.start_lat is None:
            warnings.append("No start supplied: arrival before the first selected stop is excluded.")
        if transfer:
            warnings.append("This route would require a transfer between areas under the conservative Phase 2 walking-only policy. No transfer duration is modeled.")
        if not budget_fits:
            warnings.append(f"Your selected places cannot fit the checked walking estimate into {req.available_minutes} minutes / the walking-distance budget.")
        if minimum_stay < sum(v.stay_minutes for v in visits):
            warnings.append("Minimum time permits existing full_visit-to-walk_stop budget fallback; final selected modes will be shown by Route Engine.")
        if not exact:
            warnings.append("Above 12 selected places: minimum is a lower bound, and the candidate is heuristic.")
        if transfer:
            status = "transfer_required"
        elif feasible:
            status = "feasible"
        elif exact or minimum > req.available_minutes or (req.max_walking_km is not None and lower > req.max_walking_km):
            status = "infeasible"
        else:
            status = "search_inconclusive"
        return FeasibilityResult(feasible, minimum, lower, zones, cross, feasible, warnings,
            [] if feasible else actions, status, exact, ids, spread, order, candidate)

    def suggest_subsets(self, intent, action, priority_poi_ids=None):
        if action != FeasibilityAction.HELP_ME_CHOOSE:
            raise RequestValidationError("Subset suggestions require the user's HELP_ME_CHOOSE selection")
        original = list(intent.must_go_poi_ids)
        priority = priority_poi_ids or []
        if any(pid not in original for pid in priority):
            raise RequestValidationError("Priority places must come from the original selection")
        groups = {}
        for pid in original:
            groups.setdefault(self.repo.get_poi_by_id(pid).zone_id, []).append(pid)
        candidates = []
        for group in groups.values():
            # Catalog has at most eight points per zone; bound future larger inputs.
            for size in range(min(8, len(group)), 0, -1):
                found = False
                for keep in itertools.combinations(group[:12], size):
                    trial = copy.deepcopy(intent)
                    trial.must_go_poi_ids = list(keep)
                    check = self.check(trial)
                    if not check.feasible:
                        continue
                    found = True
                    coverage = len({tag for pid in keep for tag in self.repo.get_poi_by_id(pid).interest_tags})
                    priority_score = sum(len(priority)-priority.index(pid) for pid in keep if pid in priority)
                    proposal = SuggestedSubset(list(keep), [p for p in original if p not in keep],
                        check.estimated_candidate_minutes, "Keeps a feasible, geographically continuous same-zone selection; preserves more chosen places, then explicit priorities and complementary interests.", original)
                    candidates.append(((-len(keep), -priority_score, -coverage, proposal.estimated_minutes, tuple(keep)), proposal))
                if found:
                    break
        return [proposal for _, proposal in sorted(candidates, key=lambda item: item[0])[:3]]

    def confirm_subset(self, intent, proposal, *, confirmed=False):
        if confirmed is not True:
            raise RequestValidationError("Explicit user confirmation is required to replace must-go places")
        original = intent.must_go_poi_ids
        keep, remove = proposal.keep_poi_ids, proposal.remove_poi_ids
        if (original != proposal.original_poi_ids or not keep or len(set(keep)) != len(keep) or
                len(set(remove)) != len(remove) or set(keep) & set(remove) or set(keep+remove) != set(original)):
            raise RequestValidationError("Stale or invalid subset; original selection is unchanged")
        updated = copy.deepcopy(intent)
        updated.must_go_poi_ids = list(keep)
        updated.visit_mode_overrides = {pid: mode for pid, mode in updated.visit_mode_overrides.items() if pid in keep}
        if not self.check(updated).feasible:
            raise RequestValidationError("Subset no longer fits; original selection is unchanged")
        return updated
