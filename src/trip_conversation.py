"""Controlled trip turns; proposals never write state or generate routes."""
from dataclasses import asdict, dataclass

from .llm_client import LLMClientError, redact_diagnostic
from .trip_commands import (TripCommandError, TripCommandParser, TripCommandProposal,
                            TripPOIResolver, minimal_context, normalize_proposal)
from .trip_replanning import ReplanningCoordinator, ReplanReason
from .trip_state import TripStateDelta, TripStateError, snapshot
from .trip_store import StaleStateConflict, TripService


@dataclass
class TripTurnResult:
    status: str
    command_type: str | None = None
    parsed_command: dict | None = None
    core_action_result: dict | None = None
    replan_result: dict | None = None
    read_result: dict | None = None
    clarification: dict | None = None
    user_facing_summary: dict | None = None
    state_revision: int | None = None
    error_code: str | None = None
    mutation_result: dict | None = None
    nlu_trace: dict | None = None
    core_action_results: list | None = None

    def to_dict(self):
        return snapshot(asdict(self))


class InMemoryTripConversationStore:
    """Pending commands only; persistent conversation storage is DEFERRED."""
    def __init__(self):
        self._pending = {}

    def get(self, trip_id):
        return snapshot(self._pending[trip_id]) if trip_id in self._pending else None

    def set(self, trip_id, pending):
        self._pending[trip_id] = snapshot(pending)

    def clear(self, trip_id):
        self._pending.pop(trip_id, None)


FAILURE_SUMMARIES = {
    'infeasible_must_go': "I couldn't add this stop while keeping your current time and route constraints.",
    'must_go_conflict': 'That stop was explicitly skipped; it was not restored.',
    'composition_gap': 'Your new preferences leave too few suitable stops to preserve the City Walk structure.',
    'insufficient_remaining_route': 'No suitable continuation passed the remaining-time and journey checks.',
    'invalid_delta': 'The proposed changes did not pass the existing trip validation.',
    'invalid_state': 'This trip is not available for the requested operation.',
    'stale_state_conflict': 'The trip changed during this turn. Please retry against the latest saved state.',
    'engine_failure': 'The planning result could not be generated or validated. Staged changes were not saved.',
}


class ReplanExplanationBuilder:
    def __init__(self, repository):
        self.repository = repository

    def stops(self, ids):
        return [{'poi_id': pid, 'name': self.repository.get_poi_by_id(pid).name_en,
                 'name_zh': self.repository.get_poi_by_id(pid).name_zh} for pid in ids]

    def build(self, record, versions):
        if record is None:
            return dict(headline='No route changes yet', reasons=[], added_stops=[], removed_stops=[], kept_stops=[])
        if record['diagnostics'].get('mutation_scope'):
            return dict(record['diagnostics'], headline='Route updated', reason=record['reason'],
                        version=record['new_route_version_id'], replan_id=record['replan_id'],
                        reasons=['Requested changes: ' + ', '.join(a.replace('_', ' ').lower() for a in record['diagnostics'].get('actions', [])) + '.'])
        index = {v['version_id']: v for v in versions}
        excluded = set(record['visited_at_replan'] + record['skipped_at_replan'])
        old = [s['poi_id'] for s in index[record['old_route_version_id']]['route_snapshot']['ordered_pois']
               if s['poi_id'] not in excluded]
        new = [s['poi_id'] for s in index[record['new_route_version_id']]['route_snapshot']['ordered_pois']]
        delta, reasons = record['delta'], []
        effective = record['effective_remaining_minutes']
        if effective < record['state_before']['remaining_minutes']:
            reasons.append(f'Remaining time was reduced to {effective:g} minutes.')
        if delta.get('pace'):reasons.append('Visit pace changed to ' + delta['pace'] + ' using existing visit-time estimates.')
        for key, template in (
            ('add_interest_tags', 'Added interests: {}.'), ('remove_interest_tags', 'Removed interests: {}.'),
            ('add_avoid_tags', 'Excluded from future stops: {}.'), ('remove_avoid_tags', 'Removed avoidance: {}.')):
            if delta.get(key):reasons.append(template.format(', '.join(delta[key])))
        if delta.get('add_must_go_poi_ids'):
            names = [s['name'] for s in self.stops(delta['add_must_go_poi_ids'])]
            reasons.append('Requested must-go stops: ' + ', '.join(names) + '.')
        if record['reason'] == 'stop_skipped':reasons.append('A saved skip was applied before replanning.')
        if not reasons:reasons.append('The remaining route was recalculated under the saved trip constraints.')
        return dict(headline='Route updated', replan_id=record['replan_id'], reason=record['reason'],
                    version=record['new_route_version_id'], reasons=reasons,
                    added_stops=self.stops([pid for pid in new if pid not in old]),
                    removed_stops=self.stops([pid for pid in old if pid not in new]),
                    kept_stops=self.stops([pid for pid in new if pid in old]),
                    change_basis='Previous executable future stops versus new future stops; visited/skipped are separate facts.',
                    geometry='DEFERRED TO PHASE 3B MAP ROUTING')


class ConversationalTripService:
    def __init__(self, store, repository, client, *, trip_service=None, coordinator=None, conversation_store=None, legacy_protocol=False):
        self.store, self.repository = store, repository
        self.core = trip_service if trip_service is not None else TripService(store)
        self.coordinator = coordinator if coordinator is not None else ReplanningCoordinator(store, repository)
        self.parser = TripCommandParser(repository, client)
        self.resolver = TripPOIResolver(repository)
        self.conversations = conversation_store if conversation_store is not None else InMemoryTripConversationStore()
        self.explanations = ReplanExplanationBuilder(repository)
        self.legacy_protocol = legacy_protocol
        from .trip_action_executor import TripActionExecutor
        self.actions = TripActionExecutor(self, client)

    def _result(self, trip_id, status, **fields):
        try:revision = self.store.get(trip_id).state_revision
        except KeyError:revision = None
        fields.setdefault('user_facing_summary', dict(headline=FAILURE_SUMMARIES.get(status, status.replace('_', ' '))))
        return TripTurnResult(status, state_revision=revision, **fields)

    def _clarify(self, trip, proposal, text, resolution=None, *, field=None, index=None):
        resolution = resolution or {'status': 'vague_change', 'options': []}
        reason = resolution['status']
        if field == 'place_reference' and not resolution['options']:
            resolution['options'] = [{'label': self.repository.get_poi_by_id(pid).name_en,
                                      'name': self.repository.get_poi_by_id(pid).name_en, 'poi_id': pid}
                                     for pid in trip.remaining_poi_ids[:3]]
        options = resolution['options']
        clarification = dict(status='needs_clarification', reason=reason,
                             question='Which catalog place do you mean?' if field else 'What explicit time, pace or preference change would you like?',
                             options=options, pending_command=proposal.to_dict())
        self.conversations.set(trip.trip_id, dict(proposal=proposal.to_dict(), text=text,
                                                field=field, index=index, options=options, revision=trip.state_revision))
        return self._result(trip.trip_id, 'needs_clarification', command_type=proposal.command_type,
                            parsed_command=proposal.to_dict(), clarification=clarification,
                            user_facing_summary={'headline': clarification['question']})

    def handle_turn(self, trip_id, user_text, *, read_only=False):
        if not self.legacy_protocol:
            return self.actions.handle_turn(trip_id, user_text, read_only=read_only)
        return self._handle_legacy_turn(trip_id, user_text, read_only=read_only)

    def _handle_legacy_turn(self, trip_id, user_text, *, read_only=False):
        try:trip = self.store.get(trip_id)
        except (KeyError, TripStateError):return self._result(trip_id, 'invalid_state', error_code='invalid_state')
        pending = self.conversations.get(trip_id)
        if pending and isinstance(user_text, str) and user_text.strip().casefold() in ('cancel', '取消'):
            self.conversations.clear(trip_id)
            return self._result(trip_id, 'no_change', user_facing_summary={'headline': 'Pending clarification cancelled; trip unchanged.'})
        if pending and pending['revision'] != trip.state_revision:
            self.conversations.clear(trip_id)
            return self._result(trip_id, 'stale_state_conflict', error_code='stale_state_conflict')
        if pending and pending['field']:
            answer = user_text.strip() if isinstance(user_text, str) else ''
            option_answer = answer.rstrip('.。)')
            options = pending['options'];choice = None
            if option_answer.isdigit() and 1 <= int(option_answer) <= len(options):choice = options[int(option_answer)-1]
            elif len(option_answer) == 1 and 'A' <= option_answer.upper() <= 'Z' and ord(option_answer.upper())-65 < len(options):
                choice = options[ord(option_answer.upper())-65]
            else:
                resolved = self.resolver.resolve(answer, trip)
                if resolved['status'] == 'resolved' and (not options or resolved['poi_id'] in {o['poi_id'] for o in options}):
                    choice = resolved['options'][0]
            if not choice:
                return self._clarify(trip, TripCommandProposal(**pending['proposal']), pending['text'],
                                     {'status': 'ambiguous_place', 'options': options}, field=pending['field'], index=pending['index'])
            proposal = TripCommandProposal(**pending['proposal'])
            if pending['field'] == 'place_reference':proposal.place_reference = choice['name']
            else:proposal.must_go_place_mentions[pending['index']] = choice['name']
            proposal.needs_clarification = False
            text = pending['text'] + '\nConfirmed place: ' + choice['name']
            self.conversations.clear(trip_id)
        else:
            try:proposal = self.parser.parse(user_text, minimal_context(trip, self.repository))
            except LLMClientError as exc:
                return self._result(trip_id, 'provider_error', error_code=exc.kind,
                                    user_facing_summary={'headline': 'The language provider did not return a usable command.',
                                                         'provider_error': redact_diagnostic(str(exc)), 'stage': exc.stage})
            except TripCommandError as exc:
                return self._result(trip_id, exc.status, error_code=exc.status,
                                    user_facing_summary={'headline': 'No trip operation was executed.', 'validation': str(exc)})
            text = user_text
            if pending:self.conversations.clear(trip_id)
        return self._execute(trip, proposal, text, read_only=read_only)

    def _execute(self, trip, proposal, text, *, read_only=False):
        tid = trip.trip_id
        try:p = normalize_proposal(proposal, text, self.repository)
        except (TripCommandError, TripStateError) as exc:
            return self._result(tid, 'invalid_command', error_code='invalid_command',
                                user_facing_summary={'headline': 'No trip operation was executed.', 'validation': str(exc)})
        fields = dict(command_type=p.command_type, parsed_command=p.to_dict())
        if read_only and p.command_type != 'read_query':
            return self._result(tid, 'invalid_state', error_code='mutations_not_allowed',
                                user_facing_summary={'headline': 'Only read queries are allowed before start or after the trip ends.'}, **fields)
        if p.command_type == 'unsupported':return self._result(tid, 'unsupported', **fields)
        if p.needs_clarification or p.command_type == 'ambiguous':
            return self._clarify(trip, p, text, field='place_reference' if p.clarification_reason == 'missing_place_reference' else None)
        if p.command_type == 'read_query':
            if p.read_query == 'show_original_route':value = self.core.get_original_route(tid)
            elif p.read_query == 'show_current_route':
                value = dict(route=self.core.get_current_route(tid), remaining_stops=self.core.get_remaining_stops(tid))
            elif p.read_query == 'show_route_history':value = self.core.get_route_history(tid)
            else:
                value = self.explanations.build(self.core.get_latest_replan_summary(tid), self.core.get_route_history(tid))
            return self._result(tid, 'success_query', read_result={'query_type': p.read_query, 'value': value},
                                user_facing_summary=value if p.read_query == 'why_latest_replan' else {'headline': p.read_query.replace('_', ' ')}, **fields)
        must = []
        for index, mention in enumerate(p.must_go_place_mentions):
            resolution = self.resolver.resolve(mention, trip)
            if resolution['status'] in ('ambiguous', 'not_found'):
                return self._clarify(trip, p, text, resolution, field='must_go_place_mentions', index=index)
            if resolution['status'] != 'resolved':return self._result(tid, 'invalid_command', error_code='invalid_for_trip', **fields)
            if resolution['poi_id'] not in must:must.append(resolution['poi_id'])
        target = None
        if p.core_action and p.core_action != 'update_elapsed_time':
            resolution = self.resolver.resolve(p.place_reference, trip)
            if resolution['status'] in ('ambiguous', 'not_found'):
                return self._clarify(trip, p, text, resolution, field='place_reference')
            if resolution['status'] != 'resolved':return self._result(tid, 'invalid_command', error_code='invalid_for_trip', **fields)
            target = resolution['poi_id']
        # Normalize effective changes before any Core write; a repeated preference
        # assertion is a read-like no-op, not a request for a fresh route version.
        current = trip.current_intent
        delta = TripStateDelta(
            remaining_minutes=p.remaining_minutes if p.remaining_minutes is not None and p.remaining_minutes < trip.remaining_minutes else None,
            pace=p.pace if p.pace != current['travel_pace'] else None,
            add_interest_tags=[t for t in p.add_interest_tags if t not in current['interest_tags']],
            remove_interest_tags=[t for t in p.remove_interest_tags if t in current['interest_tags']],
            add_avoid_tags=[t for t in p.add_avoid_tags if t not in current['avoid_tags']],
            remove_avoid_tags=[t for t in p.remove_avoid_tags if t in current['avoid_tags']],
            add_must_go_poi_ids=[pid for pid in must if pid not in trip.must_go_remaining and pid not in trip.visited_poi_ids],
            request_replan=True)
        try:delta.validate(taxonomy=self.repository.taxonomy, allowed_poi_ids=[q.id for q in self.repository.get_all_pois()])
        except TripStateError:return self._result(tid, 'invalid_command', error_code='invalid_delta', **fields)
        changes = any(v not in (None, []) for k, v in delta.to_dict().items() if k not in ('request_replan', 'skip_poi_ids'))
        if self.store.get(tid).state_revision != trip.state_revision:
            return self._result(tid, 'stale_state_conflict', error_code='stale_state_conflict', **fields)
        core_result = None
        if p.core_action:
            try:
                core_result = self.core.apply_core_action(tid, p.core_action, poi_id=target,
                                                         elapsed_minutes=p.elapsed_minutes, expected_revision=trip.state_revision)
                trip = self.store.get(tid)
            except StaleStateConflict:return self._result(tid, 'stale_state_conflict', error_code='stale_state_conflict', **fields)
            except TripStateError:
                return self._result(tid, 'invalid_command', error_code='core_action_conflict',
                                    user_facing_summary={'headline': 'That Core action conflicts with saved progress or the active route.'}, **fields)
        fields['core_action_result'] = core_result
        # Repeated assertions do not call the coordinator; explicit manual replan
        # with no supplied preference change still reaches the existing authority.
        do_replan = changes or (p.request_replan and (p.core_action == 'skip_stop' or not p.has_changes()))
        if not do_replan:
            status = 'success_core_action' if core_result and core_result['changed'] else 'no_change'
            return self._result(tid, status, **fields)
        reason = (ReplanReason.STOP_SKIPPED if p.core_action == 'skip_stop' else ReplanReason.TIME_REDUCED if delta.remaining_minutes is not None
                  else ReplanReason.MUST_GO_ADDED if delta.add_must_go_poi_ids else ReplanReason.AVOIDANCE_CHANGED if delta.add_avoid_tags or delta.remove_avoid_tags
                  else ReplanReason.PREFERENCE_CHANGED if changes else ReplanReason.MANUAL)
        result = self.coordinator.replan(tid, delta, primary_reason=reason, expected_revision=trip.state_revision)
        fields['replan_result'] = result.to_dict()
        if result.committed:
            latest = self.store.get(tid)
            explanation = self.explanations.build(latest.replan_history[-1], latest.route_versions)
            return self._result(tid, 'success_replanned', user_facing_summary=explanation, **fields)
        status = 'no_change' if result.status == 'no_change' else 'stale_state_conflict' if result.status == 'stale_state_conflict' else 'replan_failed'
        summary = dict(headline=FAILURE_SUMMARIES.get(result.status, result.status), error_code=result.status,
                       core_action_saved=bool(core_result and core_result['saved']), staged_changes_saved=False)
        return self._result(tid, status, error_code=None if status == 'no_change' else result.status,
                            user_facing_summary=summary, **fields)
