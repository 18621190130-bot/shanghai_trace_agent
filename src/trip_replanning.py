"""Deterministic staged adaptation to the existing planning authority; no LLM."""
import copy
import math
from collections import Counter
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from .intent_models import RouteIntent
from .intent_adapter import intent_to_route_request
from .models import SelectedVisit
from .poi_repository import POIRepository, TAG_GROUPS
from .route_engine import RouteEngine
from .trip_state import TripStateDelta, TripStateError, TripStatus, snapshot, validate_plan
from .trip_store import StaleStateConflict


class ReplanReason(StrEnum):
    MANUAL = 'manual_replan'
    TIME_REDUCED = 'time_reduced'
    PREFERENCE_CHANGED = 'preference_changed'
    AVOIDANCE_CHANGED = 'avoidance_changed'
    MUST_GO_ADDED = 'must_go_added'
    STOP_SKIPPED = 'stop_skipped'


@dataclass
class RemainingRouteRequest:
    zone: str
    remaining_minutes: float
    current_intent: dict
    excluded_poi_ids: list
    must_go_remaining: list
    logical_origin: dict
    journey_context: dict
    replan_reason: str

    def to_dict(self):
        return snapshot(asdict(self))

    def to_route_request(self):
        intent = RouteIntent.from_dict(self.current_intent)
        intent.available_minutes = math.floor(self.remaining_minutes)
        intent.preferred_zone = self.zone
        intent.start_lat, intent.start_lng = self.logical_origin['coordinates']
        intent.start_coordinate_system = 'GCJ-02'
        intent.start_poi_id = None
        intent.must_go_poi_ids = list(self.must_go_remaining)
        intent.avoid_poi_ids = sorted(set(intent.avoid_poi_ids) | set(self.excluded_poi_ids))
        return intent_to_route_request(intent)


@dataclass
class ReplanResult:
    status: str
    old_route_version_id: str | None = None
    new_route_version_id: str | None = None
    proposed_route: dict | None = None
    effective_remaining_minutes: float | None = None
    reason: str | None = None
    diagnostics: dict = field(default_factory=dict)
    committed: bool = False

    def to_dict(self):
        return snapshot(asdict(self))


class InTripPolicy:
    @staticmethod
    def assess(context, roles, *, user_shortened=False):
        visited = context['visited_stop_count'];remaining = len(roles)
        total = visited + remaining
        shortened = visited == 1 and remaining == 1 and user_shortened
        minimum = remaining > 0 and (total >= 3 or shortened)
        counts = Counter(context['visited_roles'] + roles)
        composition = counts['anchor'] >= 1 and counts['anchor'] + counts['supporting_stop'] >= 2
        return dict(minimum_passed=minimum, composition_passed=composition, shortened=shortened,
                    visited_stop_count=visited, remaining_stop_count=remaining, total_journey_stop_count=total,
                    effective_journey_role_counts=dict(counts), basis='visited plus proposed future; skipped do not count')


class ContinuationRouteEngine(RouteEngine):
    """Only defer final composition to journey policy when progress exists.

    All candidate matching, quality, insertion, scoring, time/distance and modes
    stay inherited. Initial/no-visited requests use the ordinary engine unchanged.
    """
    def __init__(self, repository, journey_context):
        super().__init__(repository)
        self.journey_context = journey_context

    def _composition_enabled(self, req, zone):
        if self.journey_context['visited_stop_count']:
            return False
        return super()._composition_enabled(req, zone)

    def generate_route(self, request):
        plan = super().generate_route(request)
        context = self.journey_context
        if (context['visited_stop_count'] and not context['has_visited_anchor'] and plan.status == 'success'
                and not InTripPolicy.assess(context, [s.effective_primary_role for s in plan.ordered_pois])['composition_passed']):
            # Ask the existing authority for its bounded composition repair.
            # Never manufacture a route or relax hard constraints in the adapter.
            repaired = RouteEngine(self.repository).generate_route(request)
            if repaired.status == 'success' and InTripPolicy.assess(
                    context, [s.effective_primary_role for s in repaired.ordered_pois])['composition_passed']:
                return repaired
        return plan


def logical_origin(trip, repository):
    # Most recent version containing a visit; choose its last visited route stop,
    # not event order, and never pretend this is a measured physical location.
    for version in reversed(trip.route_versions):
        visited = [s for s in version['route_snapshot']['ordered_pois'] if s['poi_id'] in trip.visited_poi_ids]
        if visited:
            poi = repository.get_poi_by_id(visited[-1]['poi_id'])
            return dict(poi_id=poi.id, coordinates=list(poi.coordinates), basis='last visited in latest applicable route order; approximate, not GPS')
    current = repository.get_poi_by_id(trip.current_poi_id)
    if current is not None:
        return dict(poi_id=current.id, coordinates=list(current.coordinates), basis='logical current stop; approximate, not GPS')
    raise TripStateError('No logical origin available')


class ReplanningCoordinator:
    def __init__(self, store, repository=None, *, engine_factory=ContinuationRouteEngine, walking_service=None):
        self.store = store
        self.repository = repository if repository is not None else POIRepository()
        self.engine_factory = engine_factory
        from .services.walking_route_service import default_walking_service
        self.walking_service = walking_service if walking_service is not None else default_walking_service()

    def replan(self, trip_id, delta=None, *, primary_reason=ReplanReason.MANUAL, expected_revision=None, must_go_overrides_avoid=False, mutation_scope=None):
        try:
            trip = self.store.get(trip_id)
        except (KeyError, TripStateError) as exc:
            return ReplanResult('invalid_state', diagnostics={'error': str(exc)})
        old = trip.route_versions[-1]['version_id']
        result = ReplanResult('invalid_delta', old_route_version_id=old)
        if expected_revision is not None and trip.state_revision != expected_revision:
            result.status = 'stale_state_conflict';return result
        if trip.status != TripStatus.ACTIVE:
            result.status = 'invalid_state';return result
        if not trip.remaining_poi_ids:
            result.status = 'insufficient_remaining_route'
            result.diagnostics['error'] = 'No active remaining stops; do not manufacture a new trip'
            return result
        try:
            reason = ReplanReason(primary_reason).value;result.reason = reason
            raw = delta.to_dict() if isinstance(delta, TripStateDelta) else (delta if delta is not None else {'request_replan': True})
            delta = TripStateDelta.from_dict(raw, taxonomy=self.repository.taxonomy,
                                            allowed_poi_ids=[p.id for p in self.repository.get_all_pois()])
            if delta.skip_poi_ids:
                raise TripStateError('Save explicit skip_stop first; skip is not a staged replan change')
            if not delta.request_replan:
                result.status = 'no_change';result.diagnostics['error'] = 'request_replan is false; no delta committed';return result
        except (ValueError, TypeError) as exc:
            result.diagnostics['error'] = str(exc);return result
        revision = trip.state_revision
        staged = trip.current_intent
        for key, add, remove in (('interest_tags', delta.add_interest_tags, delta.remove_interest_tags),
                                  ('avoid_tags', delta.add_avoid_tags, delta.remove_avoid_tags)):
            retained = [tag for tag in staged[key] if tag not in remove]
            staged[key] = retained + sorted(set(add) - set(retained))
        if delta.pace is not None:staged['travel_pace'] = delta.pace
        effective = trip.remaining_minutes if delta.remaining_minutes is None else min(trip.remaining_minutes, delta.remaining_minutes)
        result.effective_remaining_minutes = effective
        if math.floor(effective) <= 0:
            result.status = 'insufficient_remaining_route';return result
        zone = trip.active_route['selected_zone'] or staged['preferred_zone']
        if zone is None:zone = trip.get_remaining_stops()[0]['walk_zone']
        must_go = set(trip.must_go_remaining)
        satisfied = []
        raw_index = {p['id']: p for p in self.repository.get_raw_data()['pois']}
        for pid in delta.add_must_go_poi_ids:
            if pid in trip.skipped_poi_ids:
                result.status = 'must_go_conflict';result.diagnostics['poi_id'] = pid;return result
            if pid in trip.visited_poi_ids:
                satisfied.append(pid);continue
            p = self.repository.get_poi_by_id(pid)
            if not p.counts_as_route_stop or not raw_index[pid].get('route_selectable', True):
                result.status = 'infeasible_must_go';result.diagnostics['error'] = 'Internal/non-selectable must-go';return result
            must_go.add(pid)
        staged['must_go_poi_ids'] = sorted(must_go)
        for pid in must_go:
            p = self.repository.get_poi_by_id(pid)
            tags = {t for group in TAG_GROUPS for t in getattr(p, group)}
            if p.zone_id != zone or pid in staged['avoid_poi_ids'] or (not must_go_overrides_avoid and tags & set(staged['avoid_tags'])):
                result.status = 'infeasible_must_go';result.diagnostics['error'] = 'Must-go conflicts with fixed zone or future avoidance';return result
        context = trip.get_journey_context()
        try:
            remaining = RemainingRouteRequest(zone, effective, staged, trip.get_replan_excluded_poi_ids(), sorted(must_go),
                                              logical_origin(trip, self.repository), context, reason)
            request = remaining.to_route_request()
            # Preserve plan-only hard constraints not represented by RouteIntent.
            for name in ('avoid_crowds', 'environment_preference', 'full_visit_unavailable_poi_ids', 'willing_to_buy_tickets', 'allow_mode_downgrade'):
                if name in trip.active_route['request']:setattr(request, name, copy.deepcopy(trip.active_route['request'][name]))
            engine = self.engine_factory(self.repository, context)
            plan = engine.generate_route(request)
            result.proposed_route = snapshot(plan.to_dict())
            result.diagnostics.update(remaining_request=remaining.to_dict(), already_satisfied_must_go=satisfied,
                                      engine_status=plan.status, engine_errors=plan.errors,
                                      geometry='Final route hydration before snapshot commit', budget_floor_minutes=request.available_minutes)
        except Exception as exc:
            result.status = 'engine_failure';result.diagnostics['error'] = f'{type(exc).__name__}: {exc}';return result
        if plan.status != 'success':
            result.status = 'composition_gap' if plan.status == 'composition_failure' else ('infeasible_must_go' if must_go else 'insufficient_remaining_route')
            return result
        try:
            ids = validate_plan(result.proposed_route)
            if plan.request != asdict(request) or plan.selected_zone != zone:
                raise TripStateError('Proposed request/zone differs from staged constraints')
            if set(ids) & set(trip.excluded_poi_ids) or not must_go <= set(ids):
                raise TripStateError('Future route violates excluded/must-go IDs')
            visits = []
            for stop in plan.ordered_pois:
                p = self.repository.get_poi_by_id(stop.poi_id)
                if p is None or not p.counts_as_route_stop or not raw_index[p.id].get('route_selectable', True):
                    raise TripStateError('Unknown/internal/non-selectable proposed stop')
                if p.zone_id != zone or (engine._avoided(p, request) and not (must_go_overrides_avoid and p.id in must_go)):
                    raise TripStateError('Future route violates zone/avoidance')
                if p.id not in must_go and not engine._relevant(p, request):
                    raise TripStateError('Unrelated optional filler')
                if stop.effective_primary_role != p.effective_primary_role or list(stop.estimated_coordinates) != list(p.coordinates):
                    raise TripStateError('Proposed identity/role/coordinates changed')
                if stop.estimated_stay_minutes != p.visit_profile.stay_for(stop.selected_visit_mode, request.travel_pace):
                    raise TripStateError('Proposed stay duration changed')
                visits.append(SelectedVisit(p, stop.selected_visit_mode, request.travel_pace, stop.requested_visit_mode))
            start = tuple(remaining.logical_origin['coordinates'])
            if not engine._fits(visits, request, start) or plan.total_estimated_minutes > effective:
                raise TripStateError('Future route exceeds time/distance budget')
            metrics = engine._metrics(visits, start)
            reported = (plan.total_estimated_distance_km, plan.total_estimated_walking_minutes,
                        plan.total_stay_minutes, plan.total_estimated_minutes)
            if any(abs(a-b) > 1e-6 for a, b in zip(metrics, reported)):
                raise TripStateError('Proposed budget diagnostics inconsistent')
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            result.status = 'engine_failure';result.diagnostics['error'] = str(exc);return result
        user_shortened = bool(effective < trip.remaining_minutes or trip.skipped_poi_ids or delta.add_avoid_tags or
                              delta.remove_interest_tags or delta.add_interest_tags or delta.pace)
        policy = InTripPolicy.assess(context, [s.effective_primary_role for s in plan.ordered_pois], user_shortened=user_shortened)
        result.diagnostics['in_trip_policy'] = policy
        if not policy['minimum_passed']:
            result.status = 'insufficient_remaining_route';return result
        if not policy['composition_passed']:
            result.status = 'composition_gap';return result
        staged['available_minutes'] = request.available_minutes
        old_stops = trip.get_remaining_stops()
        if mutation_scope == 'FULL_REPLAN':
            from .route_mutation import RouteMutationService
            diff = RouteMutationService(self.repository).diff(old_stops, result.proposed_route['ordered_pois'])
            result.diagnostics.update(diff, mutation_scope='FULL_REPLAN', action_scopes=['FULL_REPLAN'],
                                      old_version=old, new_version='v'+str(len(trip.route_versions)+1),
                                      estimated_minutes=plan.total_estimated_minutes, target_minutes=trip.time_target_minutes,
                                      time_constraint_mode=trip.time_constraint_mode, time_warning=None, actions=['FULL_REPLAN'])
            result.diagnostics['hard_limit_minutes'] = trip.remaining_minutes if trip.time_constraint_mode == 'hard' else None
            if plan.total_estimated_minutes > trip.time_target_minutes:
                result.diagnostics['time_warning'] = dict(estimated_minutes=plan.total_estimated_minutes, target_minutes=trip.time_target_minutes,
                                                          estimated_overrun_minutes=plan.total_estimated_minutes-trip.time_target_minutes, severity='warning')
            for name in ('added', 'removed', 'kept', 'reordered'):
                result.diagnostics[name+'_stops'] = [dict(poi_id=pid, name=self.repository.get_poi_by_id(pid).name_en,
                                                         name_zh=self.repository.get_poi_by_id(pid).name_zh) for pid in diff[name+'_ids']]
        def route_key(stops):return [(s['poi_id'], s['selected_visit_mode'], s['travel_pace']) for s in stops]
        # Ignore estimated leg/ranking changes if the executable sequence/modes,
        # constraints and actual future budget are identical.
        same_intent = copy.deepcopy(staged);same_intent['available_minutes'] = trip.current_intent['available_minutes']
        if route_key(old_stops) == route_key(result.proposed_route['ordered_pois']) and same_intent == trip.current_intent and effective == trip.remaining_minutes:
            result.status = 'no_change';return result
        try:
            result.proposed_route = snapshot(self.walking_service.hydrate_dict(result.proposed_route))
            trip.commit_replan(result.proposed_route, staged, reason=reason, effective_minutes=effective,
                               delta=delta.to_dict(), diagnostics=result.diagnostics)
            self.store.save_if_revision(trip, revision)
        except StaleStateConflict:
            result.status = 'stale_state_conflict';return result
        except Exception as exc:
            result.status = 'engine_failure';result.diagnostics['error'] = f'commit: {type(exc).__name__}: {exc}';return result
        result.committed = True
        result.new_route_version_id = trip.route_versions[-1]['version_id']
        result.status = 'success_shortened' if policy['shortened'] else 'success'
        return result
