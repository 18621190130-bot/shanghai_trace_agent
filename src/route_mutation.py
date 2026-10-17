"""Restricted edits of an accepted sequence using existing engine geometry/visits.

No discovery/refill/global optimization: only FULL_REPLAN delegates Coordinator.
"""
import copy
import itertools
from dataclasses import asdict

from .intent_adapter import intent_to_route_request
from .intent_models import RouteIntent
from .models import SelectedVisit
from .poi_repository import TAG_GROUPS
from .route_engine import RouteEngine
from .trip_replanning import logical_origin
from .trip_state import snapshot


class MutationError(ValueError):
    def __init__(self, status, message, diagnostics=None):
        self.status = status;self.diagnostics = diagnostics;super().__init__(message)


class RouteMutationService:
    def __init__(self, repository, *, walking_service=None):
        self.repository = repository
        self.engine = RouteEngine(repository)
        from .services.walking_route_service import default_walking_service
        self.walking_service = walking_service if walking_service is not None else default_walking_service()

    @staticmethod
    def ids(stops):return [s['poi_id'] for s in stops]

    def tags(self, pid):
        poi = self.repository.get_poi_by_id(pid)
        return {t for g in TAG_GROUPS for t in getattr(poi, g)}

    def request(self, trip, intent):
        request = intent_to_route_request(RouteIntent.from_dict(intent))
        request.start_poi_id = None  # An in-trip edit starts at logical progress, not the original Core start.
        request.available_minutes = max(1, int(trip.time_target_minutes))
        request.preferred_zone = trip.active_route['selected_zone']
        request.start_lat, request.start_lng = logical_origin(trip, self.repository)['coordinates']
        for name in ('avoid_crowds', 'environment_preference', 'full_visit_unavailable_poi_ids', 'willing_to_buy_tickets', 'allow_mode_downgrade'):
            if name in trip.active_route['request']:setattr(request, name, copy.deepcopy(trip.active_route['request'][name]))
        return request

    def visits(self, stops, intent):
        return [SelectedVisit(self.repository.get_poi_by_id(s['poi_id']), s['selected_visit_mode'],
                              intent['travel_pace'], s['requested_visit_mode']) for s in stops]

    def metrics(self, trip, stops, intent):
        if not stops:return (0, 0, 0, 0)
        return self.engine._metrics(self.visits(stops, intent), logical_origin(trip, self.repository)['coordinates'])

    def remaining_metrics(self, trip, stops, intent):
        distance, walking, stay, total = self.metrics(trip, stops, intent)
        return dict(stops=len(stops), duration_minutes=round(total, 2), walking_km=round(distance, 4),
                    walking_minutes=round(walking, 2), basis='common_planning_estimate')

    def shorten(self, trip, stops, intent, goal):
        # Bounded deletion trials preserve modes, must-go destinations and relative order.
        # Compare using the SAME engine/origin on both sides, never provider vs Haversine.
        old = self.metrics(trip, stops, intent)
        protected = set(intent['must_go_poi_ids'])
        options = []
        for i, stop in enumerate(stops):
            if len(stops) <= 1 or stop['poi_id'] in protected:continue
            trial = stops[:i] + stops[i+1:]
            metric = self.metrics(trip, trial, intent)
            improves = (metric[0] < old[0]-0.001 if goal == 'walking' else
                        len(trial) < len(stops) if goal == 'stops' else
                        metric[3] < old[3]-0.1 and metric[0] <= old[0]+0.001)
            if improves:options.append((metric[0] if goal == 'walking' else metric[3], stop['poi_id'], trial))
        return min(options, key=lambda row: row[:2])[2] if options else stops

    def add_matching(self, trip, stops, intent, count, tags=()):
        request = self.request(trip, intent)
        ranked = sorted((p for p in self.repository.get_pois_by_zone(trip.active_route['selected_zone'])
                         if p.id not in self.ids(stops) and p.id not in trip.excluded_poi_ids
                         and p.counts_as_route_stop and not self.engine._avoided(p, request)
                         and (not tags or self.tags(p.id) & set(tags))),
                        key=lambda p: (-self.engine.recommendation.score(p, request, p.zone_id, 0), p.id))
        added = []
        for poi in ranked:
            if len(added) == count:break
            try:
                stop = self.candidate(trip, poi.id, intent)
                trial = self.insert_only(trip, stops, stop, intent)
                if request.max_walking_km is not None and self.metrics(trip, trial, intent)[0] > request.max_walking_km:continue
                if trip.time_constraint_mode == 'hard' and self.metrics(trip, trial, intent)[3] > trip.remaining_minutes:continue
                stops = trial;added.append(poi.id)
            except MutationError:continue
        return stops, added

    def remove_only(self, stops, pid):
        return [s for s in stops if s['poi_id'] != pid]

    def candidate(self, trip, pid, intent, *, must_go=False):
        poi = self.repository.get_poi_by_id(pid)
        if poi is None or not poi.counts_as_route_stop:raise MutationError('not_applicable', 'Not a route-selectable production destination')
        if poi.zone_id != trip.active_route['selected_zone']:raise MutationError('state_conflict', 'The destination is outside this trip zone')
        if pid in trip.visited_poi_ids:raise MutationError('revisit_not_supported', 'A second visit occurrence is not supported')
        if pid in trip.skipped_poi_ids:raise MutationError('state_conflict', 'This destination was explicitly skipped')
        if not must_go and (pid in intent['avoid_poi_ids'] or self.tags(pid) & set(intent['avoid_tags'])):
            raise MutationError('state_conflict', 'The requested destination conflicts with saved avoidance; explicitly allow it or mark it must-go')
        # Existing authority materializes exactly ONE named destination. No refill.
        request = self.request(trip, intent);request.route_mode = 'places_in_mind'
        request.must_go_poi_ids = [pid];request.available_minutes = 100000
        request.avoid_tags = [];request.avoid_poi_ids = [];request.max_walking_km = None
        plan = self.engine.generate_route(request)
        if plan.status != 'success' or self.ids([s.to_dict() if hasattr(s, 'to_dict') else asdict(s) for s in plan.ordered_pois]) != [pid]:
            raise MutationError('not_applicable', 'The existing engine could not materialize this destination safely')
        stop = snapshot(plan.to_dict()['ordered_pois'][0]);stop['must_go'] = must_go
        stop['selection_reason'] = 'explicit_insert';return stop

    def insert_only(self, trip, stops, stop, intent):
        if stop['poi_id'] in self.ids(stops):return stops
        # Keep the relative order of every accepted stop; choose one insertion slot.
        trials = [stops[:i] + [stop] + stops[i:] for i in range(len(stops) + 1)]
        return min(enumerate(trials), key=lambda row: (self.metrics(trip, row[1], intent)[0], row[0]))[1]

    def replace_targeted(self, trip, stops, target, intent, replacement=None):
        ids = self.ids(stops)
        if target not in ids:raise MutationError('not_applicable', 'Replacement target is not on the future route')
        if replacement:
            if replacement in ids:raise MutationError('state_conflict', 'Replacement is already on the route')
            stop = self.candidate(trip, replacement, intent)
        else:
            candidates = []
            request = self.request(trip, intent)
            source = self.repository.get_poi_by_id(target)
            for p in self.repository.get_pois_by_zone(source.zone_id):
                if p.id in ids or p.id in trip.excluded_poi_ids or not p.counts_as_route_stop or self.engine._avoided(p, request):continue
                overlap = len(self.tags(p.id) & self.tags(target))
                if not overlap:continue
                candidates.append((p.effective_primary_role != source.effective_primary_role, -overlap,
                                   -self.engine.recommendation.score(p, request, source.zone_id, self.engine._distance(source.coordinates, p.coordinates)), p.id))
            stop = None
            for row in sorted(candidates):
                try:stop = self.candidate(trip, row[-1], intent);break
                except MutationError:continue
            if stop is None:raise MutationError('not_applicable', 'No safe matching replacement is available')
        result = list(stops);result[ids.index(target)] = stop;return result

    def reorder_only(self, stops, pid, relation, reference=None):
        ids = self.ids(stops)
        if pid not in ids:raise MutationError('not_applicable', 'Ordering does not add destinations; add it first')
        if reference == pid:raise MutationError('state_conflict', 'A destination cannot be placed before/after itself')
        stop = stops[ids.index(pid)];result = [s for s in stops if s['poi_id'] != pid]
        if relation == 'next':index = 0
        elif relation == 'last':index = len(result)
        else:
            if reference not in self.ids(result):raise MutationError('not_applicable', 'Ordering reference is not on the future route')
            index = self.ids(result).index(reference) + (relation == 'after')
        return result[:index] + [stop] + result[index:]

    def compress(self, trip, stops, intent, budget, *, required_ids=()):
        if self.metrics(trip, stops, intent)[3] <= budget:return stops
        request = self.request(trip, intent)
        attempts = 0
        def fit_modes(trial):
            nonlocal attempts
            attempts += 1
            if attempts > 10000:raise MutationError('state_conflict', 'Too many possible compressions; please choose stops to remove')
            if self.metrics(trip, trial, intent)[3] <= budget:return (0, trial)
            fallbacks = [(i, self.engine.visits.budget_fallback(v, request)) for i, v in enumerate(self.visits(trial, intent))]
            fallbacks = [(i, v) for i, v in fallbacks if v is not None]
            # Preserve destinations first, then change as few visit modes as needed.
            for count in range(1, len(fallbacks)+1):
                for choices in itertools.combinations(fallbacks, count):
                    attempts += 1
                    if attempts > 10000:raise MutationError('state_conflict', 'Too many possible compressions; please choose stops to remove')
                    candidate = copy.deepcopy(trial)
                    for index, fallback in choices:
                        candidate[index].update(selected_visit_mode=fallback.selected_visit_mode, downgrade_reason=fallback.downgrade_reason,
                                                visit_scope=fallback.visit_scope, ticket_required=fallback.ticket_required,
                                                reservation_required=False if fallback.selected_visit_mode == 'walk_stop' else fallback.reservation_required)
                    if self.metrics(trip, candidate, intent)[3] <= budget:return (count, candidate)
            return None
        fitted = fit_modes(stops)
        if fitted:return fitted[1]
        protected = set(intent['must_go_poi_ids']) | set(required_ids)
        optional = [i for i, s in enumerate(stops) if s['poi_id'] not in protected]
        # Hard limit explicitly authorizes deletion. Minimize deletion count, never refill/reorder.
        for count in range(1, len(optional) + 1):
            feasible = []
            for remove in itertools.combinations(optional, count):
                trial = [s for i, s in enumerate(stops) if i not in remove]
                fitted = fit_modes(trial) if trial else None
                if fitted:feasible.append((fitted[0], self.metrics(trip, fitted[1], intent)[0], tuple(remove), fitted[1]))
            if feasible:return min(feasible, key=lambda row: row[:3])[3]
        raise MutationError('state_conflict', 'The explicit hard deadline cannot retain the required destinations')

    def hard_conflict_diagnostics(self, trip, stops, intent, budget, *, required_ids=(), search_exhausted=False, preserve_order=False):
        """Explain existing compression constraints without changing its decisions.

        With additive stays and metric legs, deleting optional stops cannot increase
        the length of the protected subsequence. No protected stop: the nonempty
        route minimum is the cheapest single future stop, not an empty route.
        """
        must = set(intent['must_go_poi_ids']);explicit = set(required_ids)
        protected = [];removable = []
        for stop in stops:
            pid = stop['poi_id'];poi = self.repository.get_poi_by_id(pid)
            row = dict(poi_id=pid, name=poi.name_en, name_zh=poi.name_zh)
            reasons = (['must_go'] if pid in must else []) + (['explicitly_added_this_turn'] if pid in explicit else [])
            if reasons:protected.append(dict(row, protection_reason=reasons[0], protection_reasons=reasons))
            else:removable.append(row)
        request = self.request(trip, intent)
        def minimum(trial):
            trial = copy.deepcopy(trial)
            for stop, visit in zip(trial, self.visits(trial, intent)):
                fallback = self.engine.visits.budget_fallback(visit, request)
                if fallback is not None:stop['selected_visit_mode'] = fallback.selected_visit_mode
            return self.metrics(trip, trial, intent)[3]
        required = [s for s in stops if s['poi_id'] in must | explicit]
        minimum_minutes = minimum(required) if required else min((minimum([s]) for s in stops), default=0)
        if search_exhausted or preserve_order:reason = 'no_feasible_compression'
        elif protected:
            must_stops = [s for s in stops if s['poi_id'] in must]
            reason = 'must_go_exceeds_limit' if must_stops and minimum(must_stops) > budget else 'protected_stops_exceed_limit'
        else:reason = 'minimum_route_exceeds_limit'
        blocking = ['hard_remaining_limit']
        blocking += list(dict.fromkeys(r for p in protected for r in p['protection_reasons']))
        if not required and stops:blocking.append('nonempty_remaining_route')
        if preserve_order:blocking.append('explicit_requested_order')
        if search_exhausted:blocking.append('compression_search_limit')
        return dict(constraint_type='hard_remaining_limit', hard_limit_minutes=budget,
                    minimum_feasible_minutes=minimum_minutes, minimum_is_estimate=True,
                    minimum_basis='existing visit profiles, allowed budget fallback, approximate geometry, route buffer',
                    protected_stops=protected, removable_stops=removable, blocking_constraints=blocking,
                    reason_code=reason, blocking_reason=reason)

    def build_route(self, trip, stops, intent, policy):
        route = trip.active_route;request = self.request(trip, intent)
        target = max(0, policy['target_deadline'] - trip.elapsed_minutes)
        request.available_minutes = max(1, int(target));request.must_go_poi_ids = list(intent['must_go_poi_ids'])
        route['request'] = asdict(request)
        visits = self.visits(stops, intent);origin = logical_origin(trip, self.repository)['coordinates']
        for stop, visit, leg in zip(stops, visits, self.engine._legs(visits, origin)):
            stop['travel_pace'] = intent['travel_pace'];stop['estimated_stay_minutes'] = visit.stay_minutes
            stop['estimated_distance_from_previous_stop_km'] = stop['estimated_distance_from_previous'] = leg
            stop['estimated_walking_minutes'] = stop['estimated_walking_minutes_from_previous'] = leg * 1000 / self.engine.speed
            stop['must_go'] = stop['poi_id'] in intent['must_go_poi_ids']
            stop['matched_tags'] = self.engine.recommendation.matched_tags(visit, request)
            stop['recommendation_score'] = self.engine.recommendation.score(visit, request, route['selected_zone'], leg)
            stop['reason_for_recommendation'] = self.engine.recommendation.explanation(visit, request, route['selected_zone']) + f" Visit mode: {visit.selected_visit_mode}; pace: {intent['travel_pace']}."
        distance, walking, stay, total = self.metrics(trip, stops, intent)
        if request.max_walking_km is not None and distance > request.max_walking_km:
            raise MutationError('state_conflict', 'This edit exceeds the saved walking-distance constraint')
        route.update(ordered_pois=stops, total_estimated_distance_km=distance, total_estimated_walking_minutes=walking,
                     total_stay_minutes=stay, total_estimated_minutes=total, buffer_minutes=self.engine.buffer if stops else 0,
                     remaining_minutes=target-total, time_utilization_ratio=total/target if target else None,
                     estimated_max_single_leg_km=max(self.engine._legs(visits, origin), default=0),
                     explanation='Restricted user edit; existing stops and order preserved except explicitly requested changes. Estimates use existing RouteEngine geometry and visit profiles.',
                     richness_target=None, richness_target_met=None, composition_diagnostics={'basis': 'accepted route edited by user; no automatic composition refill'},
                     warnings=['Approximate geometry and product visit estimates; not GPS or real map routing.'])
        route['long_estimated_leg_warning'] = route['estimated_max_single_leg_km'] > 2
        return snapshot(self.walking_service.hydrate_dict(route))

    def diff(self, before, after):
        old, new = self.ids(before), self.ids(after)
        kept = [pid for pid in new if pid in old]
        old_kept = [pid for pid in old if pid in new]
        reordered = [pid for i, pid in enumerate(kept) if old_kept[i] != pid]
        return dict(added_ids=[p for p in new if p not in old], removed_ids=[p for p in old if p not in new],
                    kept_ids=kept, reordered_ids=reordered, retained_stop_count=len(kept), removed_stop_count=len(set(old)-set(new)),
                    added_stop_count=len(set(new)-set(old)), reordered_stop_count=len(reordered),
                    route_preservation_ratio=len(kept)/len(old) if old else 1)
