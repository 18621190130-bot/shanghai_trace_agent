"""UI-independent trip progress around existing RoutePlan/RouteIntent snapshots.

No planning, location inference, provider calls or automatic wall-clock timing.
Public snapshots are defensive copies; transitions are the only progress writes.
"""
import copy
import json
import math
from collections import Counter
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4

from .models import RoutePlan, RouteStop
from .intent_models import RouteIntent


class TripStateError(ValueError):
    """Invalid snapshot, state transition or trip operation."""


class TripStatus(StrEnum):
    PLANNED = 'PLANNED'
    ACTIVE = 'ACTIVE'
    REPLANNING = 'REPLANNING'  # Reserved; no transition API in this phase.
    COMPLETED = 'COMPLETED'
    ABANDONED = 'ABANDONED'


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def snapshot(value):
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise TripStateError('Snapshot must be finite JSON data') from exc


def nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise TripStateError(label + ' must be a nonempty string')
    return value


def minutes(value):
    try:
        valid = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and value >= 0
    except OverflowError:
        valid = False
    if not valid:
        raise TripStateError('Minutes must be finite and nonnegative')
    return value


def timestamp(value):
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError('timezone required')
        return result
    except (ValueError, TypeError) as exc:
        raise TripStateError('Timestamp must be timezone-aware ISO 8601') from exc


@dataclass(frozen=True)
class TripEvent:
    event_id: str
    timestamp: str
    event_type: str
    payload: dict

    def to_dict(self):
        return snapshot(asdict(self))


@dataclass(frozen=True)
class RouteVersion:
    version_id: str
    route_snapshot: dict
    created_at: str
    reason: str
    parent_version_id: str | None = None
    effective_remaining_minutes: float | None = None

    def to_dict(self):
        return snapshot(asdict(self))


@dataclass(frozen=True)
class ReplanRecord:
    """Committed replan audit; legacy version-name aliases remain compatible."""
    reason: str
    old_route_version: str
    new_route_version: str
    state_before: dict
    state_after: dict
    timestamp: str
    replan_id: str | None = None
    old_route_version_id: str | None = None
    new_route_version_id: str | None = None
    delta: dict = field(default_factory=dict)
    effective_remaining_minutes: float | None = None
    visited_at_replan: list = field(default_factory=list)
    skipped_at_replan: list = field(default_factory=list)
    diagnostics: dict = field(default_factory=dict)

    def to_dict(self):
        for value in (self.reason, self.old_route_version, self.new_route_version):
            nonempty(value, 'Replan record identifier/reason')
        timestamp(self.timestamp)
        if not isinstance(self.state_before, dict) or not isinstance(self.state_after, dict):
            raise TripStateError('Replan state snapshots must be objects')
        return snapshot(asdict(self))


@dataclass
class TripStateDelta:
    """Validated future input contract. There is deliberately no apply method."""
    remaining_minutes: float | None = None
    pace: str | None = None
    add_interest_tags: list[str] = field(default_factory=list)
    remove_interest_tags: list[str] = field(default_factory=list)
    add_avoid_tags: list[str] = field(default_factory=list)
    remove_avoid_tags: list[str] = field(default_factory=list)
    add_must_go_poi_ids: list[str] = field(default_factory=list)
    skip_poi_ids: list[str] = field(default_factory=list)
    request_replan: bool = False

    @staticmethod
    def schema():
        arrays = ('add_interest_tags', 'remove_interest_tags', 'add_avoid_tags',
                  'remove_avoid_tags', 'add_must_go_poi_ids', 'skip_poi_ids')
        return dict(type='object', additionalProperties=False, properties={
            'remaining_minutes': {'type': ['number', 'null'], 'minimum': 0},
            'pace': {'enum': [None, 'quick', 'standard', 'deep']},
            'request_replan': {'type': 'boolean'},
            **{key: {'type': 'array', 'items': {'type': 'string', 'minLength': 1}, 'uniqueItems': True} for key in arrays}})

    def validate(self, *, taxonomy=None, allowed_poi_ids=None):
        if self.remaining_minutes is not None:
            minutes(self.remaining_minutes)
        if self.pace not in (None, 'quick', 'standard', 'deep') or type(self.request_replan) is not bool:
            raise TripStateError('Invalid delta pace or request_replan')
        for key in ('add_interest_tags', 'remove_interest_tags', 'add_avoid_tags',
                    'remove_avoid_tags', 'add_must_go_poi_ids', 'skip_poi_ids'):
            values = getattr(self, key)
            if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
                raise TripStateError(key + ' must be a list of nonempty strings')
            if len(values) != len(set(values)):
                raise TripStateError(key + ' contains duplicates')
        for a, b in (('add_interest_tags', 'remove_interest_tags'), ('add_avoid_tags', 'remove_avoid_tags'), ('add_must_go_poi_ids', 'skip_poi_ids')):
            if set(getattr(self, a)) & set(getattr(self, b)):
                raise TripStateError('Conflicting delta fields: ' + a + '/' + b)
        if taxonomy is not None:
            interests = set(taxonomy['interest_tags'])
            all_tags = set().union(*(set(values) for values in taxonomy.values()))
            if (set(self.add_interest_tags + self.remove_interest_tags) - interests or
                    set(self.add_avoid_tags + self.remove_avoid_tags) - all_tags):
                raise TripStateError('Unknown delta taxonomy tag')
        if allowed_poi_ids is not None and set(self.add_must_go_poi_ids + self.skip_poi_ids) - set(allowed_poi_ids):
            raise TripStateError('Unknown delta POI ID')
        return self

    def to_dict(self):
        self.validate()
        return snapshot(asdict(self))

    @classmethod
    def from_dict(cls, value, **validation):
        if not isinstance(value, dict) or set(value) - {f.name for f in fields(cls)}:
            raise TripStateError('Invalid or unknown delta fields')
        try:
            return cls(**snapshot(value)).validate(**validation)
        except TypeError as exc:
            raise TripStateError('Invalid delta') from exc


def validate_plan(value, *, allow_empty=False):
    """Reuse existing dataclass shapes, without re-running planning rules."""
    if not isinstance(value, dict) or value.get('status') != 'success':
        raise TripStateError('Trip requires a successful RoutePlan')
    stops = value.get('ordered_pois')
    if not isinstance(stops, list) or (not stops and not allow_empty):
        raise TripStateError('Trip requires a nonempty route')
    try:
        parsed = []
        for stop in stops:
            data = copy.deepcopy(stop)
            for alias, canonical in (('estimated_distance_from_previous', 'estimated_distance_from_previous_stop_km'),
                                     ('estimated_walking_minutes_from_previous', 'estimated_walking_minutes')):
                if alias in data and data.pop(alias) != data[canonical]:
                    raise TripStateError('Inconsistent RouteStop compatibility alias')
            parsed.append(RouteStop(**data))
        RoutePlan(**{**value, 'ordered_pois': parsed})
        ids = [nonempty(stop.poi_id, 'poi_id') for stop in parsed]
        if len(ids) != len(set(ids)):
            raise TripStateError('Duplicate route POI IDs')
        if any(stop.effective_primary_role not in (None, 'anchor', 'supporting_stop', 'transition_stop') for stop in parsed):
            raise TripStateError('Unknown stop role')
        request = value['request']
        if not isinstance(request, dict):
            raise TripStateError('RoutePlan.request must be its serialized request')
        minutes(request['available_minutes'])
    except (TypeError, KeyError, AttributeError) as exc:
        raise TripStateError('Invalid existing RoutePlan/RouteStop snapshot') from exc
    return ids


class TripState:
    """Logical progress. current_poi_id is NOT a GPS position.

    All skipped => remains ACTIVE until explicit abandon. If at least one stop
    was visited and none remain, auto-complete. Explicit skip waives an active
    must-go obligation, recorded on the skip event and in journey context.
    """
    def __init__(self, data, clock=utc_now):
        self._data = data
        self._clock = clock

    @classmethod
    def create(cls, route_plan, route_intent, *, trip_id=None, created_at=None, clock=utc_now):
        if not isinstance(route_plan, RoutePlan) or not isinstance(route_intent, RouteIntent):
            raise TripStateError('create requires existing RoutePlan and RouteIntent models')
        route = snapshot(route_plan.to_dict())
        intent = snapshot(route_intent.to_dict())
        ids = validate_plan(route)
        RouteIntent.from_dict(intent)
        budget = minutes(intent.get('available_minutes'))
        if intent.get('needs_clarification') or budget != route['request']['available_minutes']:
            raise TripStateError('Initial intent must be resolved and match the plan time budget')
        must_go = intent.get('must_go_poi_ids')
        if not isinstance(must_go, list) or any(not isinstance(p, str) for p in must_go) or set(must_go) - set(ids):
            raise TripStateError('Intent must-go stops must exist in the initial route')
        if not isinstance(intent.get('avoid_tags'), list) or any(not isinstance(t, str) for t in intent['avoid_tags']):
            raise TripStateError('Invalid intent avoid_tags')
        trip_id = nonempty(trip_id if trip_id is not None else str(uuid4()), 'trip_id')
        at = created_at if created_at is not None else clock()
        timestamp(at)
        data = dict(trip_id=trip_id, original_intent=intent, current_intent=copy.deepcopy(intent),
                    original_route=route, active_route=copy.deepcopy(route),
                    route_versions=[RouteVersion('v1', copy.deepcopy(route), at, 'initial_plan').to_dict()],
                    visited_poi_ids=[], skipped_poi_ids=[], original_minutes=budget, elapsed_minutes=0,
                    status=TripStatus.PLANNED.value, created_at=at, updated_at=at, event_history=[], replan_history=[])
        return cls(data, clock)

    # Copies protect original snapshots, history and progress from reference writes.
    def __getattr__(self, key):
        if key.startswith('_'):
            raise AttributeError(key)
        data = object.__getattribute__(self, '_data')
        if key in data:
            return copy.deepcopy(data[key])
        raise AttributeError(key)

    def __setattr__(self, key, value):
        if not key.startswith('_'):
            raise AttributeError('Trip fields are read-only views; use a state operation')
        object.__setattr__(self, key, value)

    @property
    def remaining_poi_ids(self):
        excluded = set(self.excluded_poi_ids)
        return [s['poi_id'] for s in self._data['active_route']['ordered_pois'] if s['poi_id'] not in excluded]

    @property
    def current_poi_id(self):
        remaining = self.remaining_poi_ids
        return remaining[0] if self.status == TripStatus.ACTIVE and remaining else None

    @property
    def excluded_poi_ids(self):
        excluded = set(self.visited_poi_ids + self.skipped_poi_ids)
        return [s['poi_id'] for s in self._known_stops() if s['poi_id'] in excluded]

    def _known_stops(self):
        known = {}
        for version in self.route_versions:
            for stop in version['route_snapshot']['ordered_pois']:
                known[stop['poi_id']] = stop
        return list(known.values())

    @property
    def state_revision(self):
        return len(self._data['event_history']) + 1

    @property
    def must_go_remaining(self):
        required = set(self.current_intent['must_go_poi_ids']) | {s['poi_id'] for s in self.active_route['ordered_pois'] if s['must_go']}
        return [p for p in self.remaining_poi_ids if p in required]

    @property
    def avoid_tags(self):
        return self.current_intent['avoid_tags']

    @property
    def remaining_minutes(self):
        policy = self._data.get('interaction_policy')
        if policy:
            deadline = policy.get('hard_deadline') if policy['time_constraint_mode'] == 'hard' else policy['target_deadline']
            return max(0, deadline - self.elapsed_minutes)
        deadline = self._data.get('remaining_budget_deadline', self.original_minutes)
        return max(0, min(self.original_minutes, deadline) - self.elapsed_minutes)

    @property
    def time_constraint_mode(self):
        return self._data.get('interaction_policy', {}).get('time_constraint_mode', 'soft')

    @property
    def time_target_minutes(self):
        return max(0, self._data.get('interaction_policy', {}).get('target_deadline', self.original_minutes) - self.elapsed_minutes)

    def _at(self, value):
        at = value if value is not None else self._clock()
        if timestamp(at) < timestamp(self.updated_at):
            raise TripStateError('Trip timestamp cannot move backwards')
        return at

    def _event(self, kind, payload, at):
        event = TripEvent(f'{self.trip_id}:e{len(self._data["event_history"])+1}', at, kind, payload)
        self._data['event_history'].append(event.to_dict())
        self._data['updated_at'] = at

    def _active(self):
        if self.status != TripStatus.ACTIVE:
            raise TripStateError('Operation requires ACTIVE trip; current status=' + self.status)

    def start_trip(self, *, timestamp=None):
        if self.status == TripStatus.ACTIVE:
            return False
        if self.status != TripStatus.PLANNED:
            raise TripStateError('Only PLANNED trips can start')
        validate_plan(self._data['original_route'])
        at = self._at(timestamp)
        self._data['status'] = TripStatus.ACTIVE.value
        self._event('trip_started', {}, at)
        return True

    def _stop(self, poi_id, action, timestamp):
        nonempty(poi_id, 'poi_id')
        if poi_id not in [s['poi_id'] for s in self._known_stops()]:
            raise TripStateError('Unknown route stop: ' + poi_id)
        target, other = ('visited_poi_ids', 'skipped_poi_ids') if action == 'completed' else ('skipped_poi_ids', 'visited_poi_ids')
        if poi_id in self._data[other]:
            raise TripStateError('Stop already has conflicting visited/skipped disposition')
        if poi_id in self._data[target]:
            return False  # Retry, including after auto-completion, never appends events.
        if poi_id not in self.remaining_poi_ids:
            raise TripStateError('Stop is not in the active remaining route')
        self._active()
        at = self._at(timestamp)
        was_required = poi_id in self.must_go_remaining
        self._data[target].append(poi_id)
        self._event('stop_' + action, dict(poi_id=poi_id, was_must_go=was_required), at)
        if not self.remaining_poi_ids and self.visited_poi_ids:
            self._data['status'] = TripStatus.COMPLETED.value
            self._event('trip_completed', dict(visited_count=len(self.visited_poi_ids), skipped_count=len(self.skipped_poi_ids)), at)
        return True

    def complete_stop(self, poi_id, *, timestamp=None):
        return self._stop(poi_id, 'completed', timestamp)

    def skip_stop(self, poi_id, *, timestamp=None):
        return self._stop(poi_id, 'skipped', timestamp)

    def update_elapsed_time(self, value, *, timestamp=None):
        self._active()
        minutes(value)
        if value < self.elapsed_minutes:
            raise TripStateError('Elapsed time cannot decrease')
        if value == self.elapsed_minutes:
            return False
        at = self._at(timestamp)
        self._data['elapsed_minutes'] = value
        self._event('elapsed_time_updated', dict(elapsed_minutes=value), at)
        return True

    def abandon_trip(self, *, timestamp=None):
        if self.status == TripStatus.ABANDONED:
            return False
        self._active()
        at = self._at(timestamp)
        self._data['status'] = TripStatus.ABANDONED.value
        self._event('trip_abandoned', {}, at)
        return True

    def cancel_planned_trip(self, *, timestamp=None):
        """Explicit pre-start cancellation; never fabricate a start or visits."""
        if self.status == TripStatus.ABANDONED:
            return False
        if self.status != TripStatus.PLANNED:
            raise TripStateError('Only PLANNED trips can be cancelled before start')
        at = self._at(timestamp)
        self._data['status'] = TripStatus.ABANDONED.value
        self._event('planned_trip_cancelled', {}, at)
        return True

    def get_original_route(self):
        return self.original_route

    def get_replan_excluded_poi_ids(self):
        """Global visited union skipped, including stops in historical versions."""
        return self.excluded_poi_ids

    def get_active_route(self):
        """Full current plan; progress is a separate view, not new sequence."""
        return self.active_route

    def get_remaining_stops(self):
        ids = set(self.remaining_poi_ids)
        return [s for s in self.active_route['ordered_pois'] if s['poi_id'] in ids]

    def get_journey_context(self):
        stops = self._known_stops()
        visited = [s['effective_primary_role'] for s in stops if s['poi_id'] in self.visited_poi_ids]
        remaining = [s['effective_primary_role'] for s in self.get_remaining_stops()]
        return dict(visited_roles=visited, remaining_roles=remaining, visited_role_counts=dict(Counter(visited)),
                    remaining_role_counts=dict(Counter(remaining)), visited_stop_count=len(visited),
                    remaining_stop_count=len(remaining), has_visited_anchor='anchor' in visited,
                    has_visited_anchor_or_supporting_count=sum(r in ('anchor', 'supporting_stop') for r in visited),
                    skipped_must_go_ids=[e['payload']['poi_id'] for e in self.event_history if e['event_type']=='stop_skipped' and e['payload']['was_must_go']])

    def to_dict(self):
        return snapshot(dict(self._data, remaining_poi_ids=self.remaining_poi_ids, current_poi_id=self.current_poi_id,
                             must_go_remaining=self.must_go_remaining, avoid_tags=self.avoid_tags, remaining_minutes=self.remaining_minutes,
                             state_revision=self.state_revision))

    def commit_replan(self, route, intent, *, reason, effective_minutes, delta, diagnostics, timestamp=None):
        """Apply a fully staged proposal on a detached state; caller must CAS save."""
        self._active()
        ids = validate_plan(route)
        staged = snapshot(intent)
        RouteIntent.from_dict(staged)
        minutes(effective_minutes)
        if effective_minutes > self.remaining_minutes or set(ids) & set(self.excluded_poi_ids):
            raise TripStateError('Replan budget/exclusion invariant violation')
        if route['request']['available_minutes'] > effective_minutes or route['total_estimated_minutes'] > effective_minutes:
            raise TripStateError('Replan request exceeds effective budget')
        if set(staged['must_go_poi_ids']) - set(self.excluded_poi_ids) - set(ids):
            raise TripStateError('Replan dropped a remaining must-go')
        at = self._at(timestamp)
        payload = snapshot(dict(route=route, intent=staged, reason=nonempty(reason, 'reason'), effective_minutes=effective_minutes,
                                delta=delta, diagnostics=diagnostics))
        before = dict(version=self.route_versions[-1]['version_id'], elapsed_minutes=self.elapsed_minutes,
                      remaining_minutes=self.remaining_minutes, current_intent=self.current_intent)
        old = self.route_versions[-1]['version_id'];new = 'v'+str(len(self.route_versions)+1)
        self._data['active_route'] = payload['route']
        self._data['current_intent'] = payload['intent']
        self._data['remaining_budget_deadline'] = self.elapsed_minutes + effective_minutes
        self._data['route_versions'].append(RouteVersion(new, payload['route'], at, reason, old, effective_minutes).to_dict())
        after = dict(version=new, elapsed_minutes=self.elapsed_minutes, remaining_minutes=self.remaining_minutes,
                     current_intent=self.current_intent)
        record = ReplanRecord(reason, old, new, before, after, at, replan_id=f'{self.trip_id}:r{len(self.replan_history)+1}',
                              old_route_version_id=old, new_route_version_id=new, delta=payload['delta'],
                              effective_remaining_minutes=effective_minutes, visited_at_replan=self.visited_poi_ids,
                              skipped_at_replan=self.skipped_poi_ids, diagnostics=payload['diagnostics'])
        self._data['replan_history'].append(record.to_dict())
        self._event('route_replanned', dict(payload, old_version=old, new_version=new), at)

    def commit_mutation(self, route, intent, policy, *, reason, diagnostics, allow_terminal_disposition=False, timestamp=None):
        """Append an audited restricted edit, including a legitimately empty future.

        Soft target is independent of the legacy hard-budget replan contract.
        Caller stages Core facts and this edit on one detached copy, then CAS.
        """
        if self.status != 'ACTIVE':
            if not (allow_terminal_disposition and self.status == 'COMPLETED' and not route['ordered_pois']):
                raise TripStateError('Mutation requires ACTIVE trip')
        ids = validate_plan(route, allow_empty=True)
        RouteIntent.from_dict(intent)
        if set(ids) & set(self.excluded_poi_ids):raise TripStateError('Future route contains a disposed stop')
        if policy['time_constraint_mode'] not in ('soft', 'hard'):raise TripStateError('Invalid time mode')
        minutes(policy['target_deadline'])
        if policy['time_constraint_mode'] == 'hard':
            minutes(policy['hard_deadline'])
            if route['total_estimated_minutes'] > max(0, policy['hard_deadline'] - self.elapsed_minutes) + 1e-6:
                raise TripStateError('Mutation exceeds explicit hard deadline')
        if set(intent['must_go_poi_ids']) - set(ids):raise TripStateError('Mutation dropped an explicit must-go')
        at = self._at(timestamp);old = self.route_versions[-1]['version_id'];new = 'v' + str(len(self.route_versions) + 1)
        before = dict(version=old, elapsed_minutes=self.elapsed_minutes, remaining_minutes=self.remaining_minutes, current_intent=self.current_intent)
        payload = snapshot(dict(route=route, intent=intent, policy=policy, reason=reason, diagnostics=diagnostics,
                                allow_terminal_disposition=allow_terminal_disposition))
        self._data['active_route'] = payload['route'];self._data['current_intent'] = payload['intent']
        self._data['interaction_policy'] = payload['policy']
        self._data['route_versions'].append(RouteVersion(new, payload['route'], at, reason, old, self.remaining_minutes).to_dict())
        after = dict(version=new, elapsed_minutes=self.elapsed_minutes, remaining_minutes=self.remaining_minutes, current_intent=self.current_intent)
        record = ReplanRecord(reason, old, new, before, after, at,
                             replan_id=f'{self.trip_id}:r{len(self.replan_history)+1}', old_route_version_id=old,
                             new_route_version_id=new, effective_remaining_minutes=self.remaining_minutes,
                             visited_at_replan=self.visited_poi_ids, skipped_at_replan=self.skipped_poi_ids,
                             delta={}, diagnostics=payload['diagnostics'])
        self._data['replan_history'].append(record.to_dict())
        self._event('route_mutated', dict(payload, old_version=old, new_version=new), at)
        if not ids and self.visited_poi_ids and self.status == 'ACTIVE':
            self._data['status'] = 'COMPLETED'
            self._event('trip_completed', dict(visited_count=len(self.visited_poi_ids), skipped_count=len(self.skipped_poi_ids)), at)

    @classmethod
    def from_dict(cls, value, *, clock=utc_now):
        """Replay append-only events and reject drift/tampered derived fields.

        Snapshots are consistency-checked, not cryptographically authenticated.
        Includes committed replan events and upgrades legacy 3A-1 snapshots.
        """
        try:
            raw = snapshot(value)
            raw.setdefault('state_revision', len(raw['event_history'])+1)
            if len(raw['route_versions']) == 1 and not raw['replan_history']:
                raw['route_versions'][0].setdefault('parent_version_id', None)
                raw['route_versions'][0].setdefault('effective_remaining_minutes', None)
            route = raw['original_route']
            validate_plan(route)
            stops = []
            for row in route['ordered_pois']:
                row = {k: v for k, v in row.items() if k not in ('estimated_distance_from_previous', 'estimated_walking_minutes_from_previous')}
                stops.append(RouteStop(**row))
            plan = RoutePlan(**{**route, 'ordered_pois': stops})
            trip = cls.create(plan, RouteIntent.from_dict(raw['original_intent']), trip_id=raw['trip_id'], created_at=raw['created_at'], clock=clock)
            for event in raw['event_history']:
                kind, payload, at = event['event_type'], event['payload'], event['timestamp']
                if kind == 'trip_started':
                    trip.start_trip(timestamp=at)
                elif kind == 'stop_completed':
                    trip.complete_stop(payload['poi_id'], timestamp=at)
                elif kind == 'stop_skipped':
                    trip.skip_stop(payload['poi_id'], timestamp=at)
                elif kind == 'elapsed_time_updated':
                    trip.update_elapsed_time(payload['elapsed_minutes'], timestamp=at)
                elif kind == 'trip_abandoned':
                    trip.abandon_trip(timestamp=at)
                elif kind == 'planned_trip_cancelled':
                    trip.cancel_planned_trip(timestamp=at)
                elif kind == 'route_replanned':
                    trip.commit_replan(payload['route'], payload['intent'], reason=payload['reason'],
                                       effective_minutes=payload['effective_minutes'], delta=payload['delta'],
                                       diagnostics=payload['diagnostics'], timestamp=at)
                elif kind == 'route_mutated':
                    trip.commit_mutation(payload['route'], payload['intent'], payload['policy'], reason=payload['reason'],
                                         diagnostics=payload['diagnostics'], allow_terminal_disposition=payload['allow_terminal_disposition'], timestamp=at)
                elif kind != 'trip_completed':
                    raise TripStateError('Unsupported trip event: ' + str(kind))
                # trip_completed is generated by the final disposition, never
                # accepted as an arbitrary independent state transition.
            if trip.to_dict() != raw:
                raise TripStateError('Trip snapshot/event/derived-field invariant mismatch')
            return trip
        except (TypeError, KeyError, AttributeError, ValueError) as exc:
            if isinstance(exc, TripStateError):
                raise
            raise TripStateError('Invalid TripState snapshot') from exc
