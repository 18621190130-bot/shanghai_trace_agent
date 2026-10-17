"""Application state machine joining existing initial planning and trip services."""
import copy
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from uuid import uuid4

from .intent_models import RouteIntent
from .llm_client import LLMClientError, redact_diagnostic
from .models import RequestValidationError
from .route_entry import RouteEntryService
from .trip_conversation import ConversationalTripService
from .trip_state import TripStateError, snapshot, utc_now
from .trip_store import InMemoryTripStore, StaleStateConflict, TripService


class SessionPhase(StrEnum):
    NEW = 'NEW'
    PLANNING = 'PLANNING'
    AWAITING_INITIAL_CLARIFICATION = 'AWAITING_INITIAL_CLARIFICATION'
    ROUTE_READY = 'ROUTE_READY'
    ACTIVE_TRIP = 'ACTIVE_TRIP'
    AWAITING_TRIP_CLARIFICATION = 'AWAITING_TRIP_CLARIFICATION'
    COMPLETED = 'COMPLETED'
    ABANDONED = 'ABANDONED'


@dataclass
class TripAgentSession:
    session_id: str
    session_phase: str = SessionPhase.NEW
    planning_context: dict = field(default_factory=dict)
    pending_initial_clarification: dict | None = None
    trip_id: str | None = None
    created_at: str = ''
    updated_at: str = ''

    def to_dict(self):
        return snapshot(asdict(self))


class InMemoryTripAgentSessionStore:
    """Navigation/planning context only; journey facts stay in TripStore."""
    def __init__(self):self._sessions = {}

    def create(self, session):
        if session.session_id in self._sessions:raise ValueError('Session already exists')
        self._sessions[session.session_id] = copy.deepcopy(session)

    def get(self, session_id):
        if session_id not in self._sessions:raise KeyError('Session not found')
        return copy.deepcopy(self._sessions[session_id])

    def save(self, session):
        if session.session_id not in self._sessions:raise KeyError('Session not found')
        self._sessions[session.session_id] = copy.deepcopy(session)

    def delete(self, session_id):
        if session_id not in self._sessions:raise KeyError('Session not found')
        del self._sessions[session_id]


@dataclass
class AgentTurnResult:
    status: str
    session_phase: str
    message_type: str
    session_id: str
    trip_id: str | None = None
    planning_result: dict | None = None
    trip_turn_result: dict | None = None
    route: dict | None = None
    clarification: dict | None = None
    trip_status: str | None = None
    user_facing_summary: dict = field(default_factory=dict)
    available_actions: list = field(default_factory=list)
    progress: dict | None = None
    trip_summary: dict | None = None
    read_result: dict | None = None
    route_updated: bool = False
    replan_explanation: dict | None = None
    route_change: dict | None = None
    error_code: str | None = None
    mutation_result: dict | None = None
    nlu_trace: dict | None = None

    def to_dict(self):return snapshot(asdict(self))


class InitialPlanToTripBridge:
    def __init__(self, core):self.core = core

    def create(self, session, result):
        if result.status != 'success' or result.route_plan is None or result.route_plan.status != 'success':
            raise TripStateError('Only accepted successful initial routes can create a trip')
        tid = session.trip_id or 'trip-' + session.session_id
        try:trip = self.core.get_trip(tid)
        except KeyError:
            trip = self.core.create_trip(result.route_plan, result.intent, trip_id=tid)
        if trip.original_route != snapshot(result.route_plan.to_dict()) or trip.original_intent != snapshot(result.intent.to_dict()):
            raise TripStateError('An existing session trip cannot be replaced by a different initial plan')
        session.trip_id = trip.trip_id
        return trip


START = {'start', 'start trip', "let's go", "i'm ready", '开始', '开始路线'}
ABANDON = {'end trip', 'stop the trip', "i'm done for today", 'abandon', 'abandon trip', '结束行程'}
SHORT_READS = {'show route': 'show_current_route', 'show final route': 'show_current_route',
               'show original route': 'show_original_route', 'show history': 'show_route_history',
               'show trip summary': 'show_trip_summary', 'summary': 'show_trip_summary'}


class TripAgentService:
    def __init__(self, repository, client, *, trip_store=None, session_store=None, clock=utc_now):
        self.repository, self.client, self.clock = repository, client, clock
        self.trip_store = trip_store if trip_store is not None else InMemoryTripStore(clock=clock)
        self.sessions = session_store if session_store is not None else InMemoryTripAgentSessionStore()
        self.entry = RouteEntryService(repository, client)
        self.core = TripService(self.trip_store, clock=clock)
        self.conversation = ConversationalTripService(self.trip_store, repository, client, trip_service=self.core)
        self.bridge = InitialPlanToTripBridge(self.core)

    def create_session(self, *, session_id=None):
        at = self.clock()
        session = TripAgentSession(session_id or str(uuid4()), created_at=at, updated_at=at)
        self.sessions.create(session)
        return self.sessions.get(session.session_id)

    def _save(self, session):
        session.updated_at = self.clock();self.sessions.save(session)

    def _sync(self, session):
        if not session.trip_id:return None
        trip = self.trip_store.get(session.trip_id)
        phase = {'PLANNED': SessionPhase.ROUTE_READY, 'ACTIVE': SessionPhase.ACTIVE_TRIP,
                 'COMPLETED': SessionPhase.COMPLETED, 'ABANDONED': SessionPhase.ABANDONED}[trip.status]
        if phase == SessionPhase.ACTIVE_TRIP and self.conversation.conversations.get(trip.trip_id):
            phase = SessionPhase.AWAITING_TRIP_CLARIFICATION
        if phase in (SessionPhase.COMPLETED, SessionPhase.ABANDONED):
            self.conversation.conversations.clear(trip.trip_id)
        session.session_phase = phase
        return trip

    def _poi(self, pid):
        poi = self.repository.get_poi_by_id(pid)
        return dict(poi_id=pid, name=poi.name_en, name_zh=poi.name_zh) if poi else None

    def get_trip_summary(self, session_id):
        session = self.sessions.get(session_id)
        if not session.trip_id:raise TripStateError('No trip exists yet')
        trip = self.trip_store.get(session.trip_id)
        return dict(status=trip.status, original_route=trip.original_route, current_route=trip.active_route,
                    visited=[self._poi(pid) for pid in trip.visited_poi_ids], skipped=[self._poi(pid) for pid in trip.skipped_poi_ids],
                    route_version_count=len(trip.route_versions), current_route_version=trip.route_versions[-1]['version_id'],
                    replan_count=len(trip.replan_history), replan_reasons=[r['reason'] for r in trip.replan_history],
                    original_minutes=trip.original_minutes, elapsed_minutes=trip.elapsed_minutes, remaining_minutes=trip.remaining_minutes)

    def _result(self, session, status, message_type='notice', **fields):
        trip = self._sync(session)
        actions = {
            SessionPhase.NEW: ['initial_request'], SessionPhase.PLANNING: [],
            SessionPhase.AWAITING_INITIAL_CLARIFICATION: ['answer', 'cancel'],
            SessionPhase.ROUTE_READY: ['start_trip', 'show_route', 'show_original_route', 'cancel'],
            SessionPhase.ACTIVE_TRIP: ['complete_stop', 'skip_stop', 'remove_place', 'add_place', 'add_must_go', 'replace_place',
                                      'reorder_place', 'change_preferences', 'set_time_target', 'set_hard_time_limit', 'full_replan',
                                      'show_route', 'show_history', 'show_progress', 'abandon'],
            SessionPhase.AWAITING_TRIP_CLARIFICATION: ['answer', 'cancel', 'abandon'],
            SessionPhase.COMPLETED: ['show_original_route', 'show_final_route', 'show_history', 'show_trip_summary'],
            SessionPhase.ABANDONED: ['show_original_route', 'show_final_route', 'show_history', 'show_trip_summary'],
        }
        self._save(session)
        progress = None
        if trip:
            progress = dict(trip_status=trip.status, visited_count=len(trip.visited_poi_ids),
                            skipped_count=len(trip.skipped_poi_ids), remaining_count=len(trip.remaining_poi_ids),
                            current_stop=self._poi(trip.current_poi_id), remaining_minutes=trip.remaining_minutes,
                            current_route_version=trip.route_versions[-1]['version_id'])
        fields.setdefault('user_facing_summary', {'headline': status.replace('_', ' ')})
        if status == 'stale_state_conflict':
            fields['user_facing_summary'] = {'headline': 'The trip changed while this request was being processed. Please try again using the latest route.'}
        if trip and trip.status in ('COMPLETED', 'ABANDONED'):
            fields.setdefault('trip_summary', self.get_trip_summary(session.session_id))
        return AgentTurnResult(status, session.session_phase, message_type, session.session_id, session.trip_id,
                               trip_status=trip.status if trip else None, available_actions=actions[session.session_phase], progress=progress, **fields)

    def accept_initial_result(self, session_id, result):
        """Formal generated-result bridge, also used by all three entry modes."""
        session = self.sessions.get(session_id)
        trip = self.bridge.create(session, result)
        session.planning_context = {};session.pending_initial_clarification = None
        return self._result(session, 'route_ready' if trip.status == 'PLANNED' else 'no_change', 'initial_route',
                            planning_result=result.to_dict(), route=trip.active_route,
                            user_facing_summary={'headline': 'Your route is ready. Type start when you are ready.'})

    def plan_from_intent(self, session_id, intent):
        """Use the existing formal entry for Places/Surprise; no new chat syntax."""
        session = self.sessions.get(session_id)
        if session.trip_id:return self._result(session, 'invalid_state', error_code='trip_already_exists')
        session.session_phase = SessionPhase.PLANNING;self._save(session)
        try:return self._planning_result(session, self.entry.generate(intent))
        except (ValueError, LLMClientError) as exc:return self._planning_error(session, exc, SessionPhase.NEW)

    def _planning_result(self, session, result):
        if result.status == 'success':return self.accept_initial_result(session.session_id, result)
        if result.status in ('needs_clarification', 'needs_route_quality_clarification'):
            session.session_phase = SessionPhase.AWAITING_INITIAL_CLARIFICATION
            session.planning_context = {'intent': copy.deepcopy(result.intent)}
            if result.status == 'needs_route_quality_clarification':
                session.pending_initial_clarification = {'kind': 'route_quality', 'result': copy.deepcopy(result)}
                clarification = dict(question=result.route_quality.question,
                                     options=[asdict(o) for o in result.route_quality.options])
            else:
                session.pending_initial_clarification = {'kind': 'fields'}
                clarification = dict(questions=[asdict(q) for q in result.intent.clarification_requests])
            return self._result(session, 'needs_clarification', 'initial_clarification',
                                planning_result=result.to_dict(), clarification=clarification)
        session.session_phase = SessionPhase.NEW;session.planning_context = {};session.pending_initial_clarification = None
        return self._result(session, result.status, 'planning_error', planning_result=result.to_dict(),
                            error_code=result.status, user_facing_summary={'headline': 'No accepted initial route was produced. You can revise the request.'})

    def _planning_error(self, session, exc, return_phase):
        session.session_phase = return_phase
        status = 'provider_error' if isinstance(exc, LLMClientError) else 'invalid_input'
        return self._result(session, status, 'planning_error', error_code=exc.kind if isinstance(exc, LLMClientError) else status,
                            user_facing_summary={'headline': redact_diagnostic(str(exc))})

    def _answer_initial(self, session, text):
        pending = session.pending_initial_clarification
        if pending['kind'] == 'route_quality':
            return self.entry.answer_route_quality_clarification(pending['result'], text)
        intent = session.planning_context['intent']
        questions = intent.clarification_requests
        if len(questions) == 1:
            merged = self.entry.answer_clarification(intent, questions[0].field, text)
        else:
            # One extraction, consume ONLY fields already being asked, then use
            # the existing clarification layer to validate the combined answer.
            try:
                answer = self.entry.clarification.parse_answer_text(intent, questions[0].field, text)
                merged = self.entry.clarification.answer(intent, {questions[0].field: answer})
            except ValueError:
                parsed = self.entry.parse_plan(text)
                answers = {q.field: copy.deepcopy(getattr(parsed, q.field)) for q in questions
                           if getattr(parsed, q.field) not in (None, [])}
                if not answers:raise RequestValidationError('Answer one of the currently asked fields')
                merged = copy.deepcopy(intent)
                for name in ('avoid_tags', 'avoid_poi_ids', 'unresolved_negative_preferences'):
                    setattr(merged, name, list(dict.fromkeys(getattr(merged, name) + getattr(parsed, name))))
                merged = self.entry.clarification.answer(merged, answers)
        return self.entry.generate(merged)

    def _read(self, session, query):
        if query == 'show_trip_summary':value = self.get_trip_summary(session.session_id)
        elif query == 'show_original_route':value = self.core.get_original_route(session.trip_id)
        elif query == 'show_current_route':value = dict(route=self.core.get_current_route(session.trip_id),
                                                       remaining_stops=self.core.get_remaining_stops(session.trip_id))
        else:value = self.core.get_route_history(session.trip_id)
        route = value if query == 'show_original_route' else value['route'] if query == 'show_current_route' else None
        return self._result(session, 'success_query', 'read_query', read_result={'query_type': query, 'value': value}, route=route)

    def handle_turn(self, session_id, user_text):
        session = self.sessions.get(session_id)
        if not isinstance(user_text, str) or not user_text.strip():
            return self._result(session, 'invalid_input', error_code='invalid_input')
        text = user_text.strip();key = text.casefold().rstrip('.!。！')
        trip = self._sync(session)
        if session.session_phase == SessionPhase.PLANNING:return self._result(session, 'planning_in_progress')
        if session.session_phase == SessionPhase.AWAITING_INITIAL_CLARIFICATION and key in ('cancel', '取消'):
            session.session_phase = SessionPhase.NEW;session.planning_context = {};session.pending_initial_clarification = None
            return self._result(session, 'cancelled', user_facing_summary={'headline': 'Initial clarification cancelled; no trip was created.'})
        if session.session_phase in (SessionPhase.NEW, SessionPhase.AWAITING_INITIAL_CLARIFICATION):
            previous = session.session_phase
            session.session_phase = SessionPhase.PLANNING;self._save(session)
            try:
                result = self._answer_initial(session, text) if previous == SessionPhase.AWAITING_INITIAL_CLARIFICATION else self.entry.generate(self.entry.parse_plan(text))
                return self._planning_result(session, result)
            except (LLMClientError, ValueError) as exc:return self._planning_error(session, exc, previous)
        if key in START:
            if trip.status == 'PLANNED':
                try:self.core.start_trip(trip.trip_id)
                except StaleStateConflict:return self._result(session, 'stale_state_conflict', error_code='stale_state_conflict')
                except TripStateError:return self._result(session, 'invalid_state', error_code='invalid_state')
                return self._result(session, 'trip_started', 'trip_started', user_facing_summary={'headline': 'Trip started.'})
            return self._result(session, 'no_change' if trip.status == 'ACTIVE' else 'invalid_state',
                                user_facing_summary={'headline': 'Already active.' if trip.status == 'ACTIVE' else 'Ended trips cannot be restarted.'})
        if key in SHORT_READS:return self._read(session, SHORT_READS[key])
        if key in ABANDON or (key in ('cancel', '取消') and trip.status == 'PLANNED'):
            try:
                if trip.status == 'PLANNED':self.core.cancel_planned_trip(trip.trip_id)
                elif trip.status == 'ACTIVE':self.core.abandon_trip(trip.trip_id)
                else:return self._result(session, 'invalid_state', error_code='mutations_not_allowed')
            except StaleStateConflict:return self._result(session, 'stale_state_conflict', error_code='stale_state_conflict')
            except TripStateError:return self._result(session, 'invalid_state', error_code='invalid_state')
            self.conversation.conversations.clear(trip.trip_id)
            return self._result(session, 'trip_abandoned', 'trip_summary', user_facing_summary={'headline': 'Trip abandoned. Remaining stops were not marked visited or skipped.'})
        result = self.conversation.handle_turn(trip.trip_id, text, read_only=trip.status != 'ACTIVE')
        after = self.trip_store.get(trip.trip_id)
        fields = dict(trip_turn_result=result.to_dict(), clarification=result.clarification,
                      user_facing_summary=result.user_facing_summary, read_result=result.read_result, error_code=result.error_code,
                      mutation_result=result.mutation_result, nlu_trace=result.nlu_trace)
        if result.core_action_result and result.core_action_result['action'] == 'complete_stop':
            fields['user_facing_summary'] = dict(result.user_facing_summary, completed_stop=self._poi(result.core_action_result['poi_id']),
                                                 next_stop=self._poi(after.current_poi_id), remaining_count=len(after.remaining_poi_ids),
                                                 remaining_minutes=after.remaining_minutes, trip_status=after.status)
            fields['user_facing_summary']['headline'] = 'Trip completed.' if after.status == 'COMPLETED' else 'Stop completed.'
        if result.replan_result and result.replan_result['committed']:
            r = result.replan_result;explanation = result.user_facing_summary
            fields.update(route_updated=True, replan_explanation=explanation, route=after.active_route,
                          route_change=dict(old_version=r['old_route_version_id'], new_version=r['new_route_version_id'],
                                            reason=r['reason'], effective_remaining_minutes=r['effective_remaining_minutes'],
                                            added_stops=explanation['added_stops'], removed_stops=explanation['removed_stops'],
                                            kept_stops=explanation['kept_stops'], new_current_stop=self._poi(after.current_poi_id),
                                            remaining_stops=after.get_remaining_stops()))
        if result.mutation_result:
            m = result.mutation_result
            fields.update(route_updated=True, replan_explanation=result.user_facing_summary, route=after.active_route,
                          route_change=dict(m, reason=m['mutation_scope'], effective_remaining_minutes=after.remaining_minutes,
                                            new_current_stop=self._poi(after.current_poi_id), remaining_stops=after.get_remaining_stops()))
        if result.read_result:
            query, value = result.read_result['query_type'], result.read_result['value']
            if query == 'show_original_route':fields['route'] = value
            elif query == 'show_current_route':fields['route'] = value['route']
        return self._result(session, result.status, 'trip_summary' if after.status == 'COMPLETED' else 'trip_turn', **fields)
