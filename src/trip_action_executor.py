"""Staged action execution and clarification; no natural-language phrase rules."""
import copy

from .llm_client import LLMClientError, redact_diagnostic
from .route_mutation import MutationError, RouteMutationService
from .trip_actions import (ActionParseError, ActionPOIResolver, READ_ACTIONS, SCOPES, TARGET_ACTIONS,
                           TripActionParser, TripActionProposal, TripUtteranceProposal)
from .trip_commands import explicit_minutes, minimal_context
from .trip_state import TripStateError, snapshot
from .trip_store import StaleStateConflict
from .trip_action_rendering import safe_trace

PRIORITY = {'COMPLETE_STOP': 0, 'SKIP_PLACE': 1, 'REMOVE_PLACE': 1, 'REPLACE_PLACE': 1,
            'ADD_PLACE': 2, 'ADD_MUST_GO': 2, 'REVISIT_PLACE': 2,
            'ADD_INTEREST': 3, 'REMOVE_INTEREST': 3, 'ADD_AVOID': 3, 'REMOVE_AVOID': 3, 'SET_PACE': 3,
            'MOVE_PLACE_NEXT': 4, 'MOVE_PLACE_BEFORE': 4, 'MOVE_PLACE_AFTER': 4,
            'ADD_MATCHING_STOPS': 4, 'SHORTEN_ROUTE': 5, 'SET_TIME_TARGET': 5, 'SET_HARD_TIME_LIMIT': 5, 'FULL_REPLAN': 6}


class TripActionExecutor:
    def __init__(self, service, client):
        self.service = service;self.repository = service.repository;self.store = service.store
        self.parser = TripActionParser(self.repository, client);self.resolver = ActionPOIResolver(self.repository)
        self.mutations = RouteMutationService(self.repository, walking_service=service.coordinator.walking_service);self.trace = {}

    def result(self, tid, status, **fields):
        self.trace['execution_result'] = status
        if status in ('success_mutated', 'success_core_action', 'success_query', 'no_change', 'trip_started', 'trip_abandoned', 'cancelled'):
            self.trace['domain_validation'] = 'passed'
        if status not in ('success_mutated', 'success_core_action', 'success_query', 'no_change', 'trip_started', 'trip_abandoned', 'cancelled'):
            self.trace.setdefault('failure_stage', None)
            if not self.trace['failure_stage']:self.trace['failure_stage'] = 'domain_validation'
        fields.setdefault('nlu_trace', safe_trace(self.trace))
        return self.service._result(tid, status, **fields)

    def clarify(self, trip, proposal, *, reason, question, options=None, location=None, kind='target'):
        options = options or []
        pending = dict(kind=kind, proposal=proposal.to_dict(), revision=trip.state_revision, options=options, location=location)
        self.service.conversations.set(trip.trip_id, pending)
        status = 'needs_duration_clarification' if kind == 'duration' else 'ambiguous_target' if kind == 'target' else 'ambiguous_intent'
        self.trace['failure_stage'] = 'resolution' if kind == 'target' else 'semantic_validation'
        return self.result(trip.trip_id, status, parsed_command=proposal.to_dict(),
                           clarification=dict(reason=reason, question=question, options=options),
                           user_facing_summary={'headline': question})

    def handle_turn(self, tid, text, *, read_only=False):
        self.trace = {'user_text': redact_diagnostic(text), 'raw_provider_proposals': [], 'parsed_actions': None,
                      'normalized_actions': None, 'poi_resolution': [], 'semantic_validation': None,
                      'domain_validation': None, 'mutation_scope': [], 'execution_result': None,
                      'route_diff': None, 'warnings': [], 'failure_stage': None}
        try:trip = self.store.get(tid)
        except (KeyError, TripStateError):return self.result(tid, 'not_applicable', error_code='trip_not_found')
        pending = self.service.conversations.get(tid)
        key = text.strip().casefold() if isinstance(text, str) else ''
        if key in ('cancel', '取消'):
            self.service.conversations.clear(tid)
            return self.result(tid, 'cancelled' if pending else 'not_applicable', user_facing_summary={'headline': 'Clarification cancelled.' if pending else 'There is no pending clarification.'})
        proposal = None
        if pending:
            if pending['revision'] != trip.state_revision:
                self.service.conversations.clear(tid)
                return self.result(tid, 'stale_state_conflict', error_code='stale_state_conflict')
            proposal = TripUtteranceProposal([TripActionProposal(**a) for a in pending['proposal']['actions']])
            options = pending['options']
            chosen = None
            for i, option in enumerate(options):
                if key in (str(i+1), chr(97+i), option.get('name', '').casefold(), option['label'].casefold()):chosen = option
            if chosen is None and pending['kind'] == 'target':
                answer = self.resolver.resolve(text, trip)
                if answer['status'] == 'resolved':chosen = dict(name=self.repository.get_poi_by_id(answer['poi_id']).name_en)
            if pending['kind'] == 'restore' and chosen:
                self.service.conversations.clear(tid)
                return self.result(tid, 'unsupported_action' if chosen['label'] == 'Add it back' else 'cancelled',
                                   error_code='skipped_restore_not_supported' if chosen['label'] == 'Add it back' else None,
                                   user_facing_summary={'headline': 'The skipped fact is preserved. Restoring a skipped visit occurrence is not supported yet.' if chosen['label'] == 'Add it back' else 'Kept the skipped destination off the route.'})
            if pending['kind'] == 'duration':
                values = explicit_minutes(text)
                if not values:
                    try:values = {float(text)}
                    except (ValueError, TypeError):pass
                if len(values) == 1:
                    proposal.actions[pending['location'][0]].time_value_minutes = next(iter(values))
                    if proposal.actions[pending['location'][0]].action_type == 'DWELL_LONGER':
                        self.service.conversations.clear(tid)
                        return self.result(tid, 'unsupported_action', error_code='dynamic_dwell_not_supported', user_facing_summary={'headline': 'Your requested dwell duration was understood; per-stop dynamic dwell is not supported by the current visit contract.'})
                else:proposal = None
            elif chosen and pending['kind'] == 'target':
                action, field, index = pending['location'];mentions = getattr(proposal.actions[action], field)
                if index == len(mentions):mentions.append(chosen['name'])
                else:mentions[index] = chosen['name']
            elif not chosen:proposal = None
            self.service.conversations.clear(tid)
        if proposal is not None:
            from .trip_actions import action_schema, normalize_actions
            from .intent_schema import validate_json
            try:validate_json(proposal.to_dict(), action_schema(self.repository));proposal = normalize_actions(proposal)
            except (ValueError, TypeError):return self.result(tid, 'parse_error', error_code='invalid_clarification_answer')
        if proposal is None:
            context = minimal_context(trip, self.repository)
            context['visible_remaining_route'] = [dict(en=s['name_en'], zh=s['name_zh']) for s in trip.get_remaining_stops()]
            context['time_constraint_mode'] = trip.time_constraint_mode
            try:proposal = self.parser.parse(text, context)
            except LLMClientError as exc:
                if pending:self.service.conversations.set(tid, pending)
                self.trace.update(self.parser.last_trace)
                return self.result(tid, 'provider_error', error_code=exc.kind, user_facing_summary={'headline': 'The provider did not return an action.', 'provider_error': redact_diagnostic(str(exc))})
            except ActionParseError as exc:
                if pending:self.service.conversations.set(tid, pending)
                self.trace.update(self.parser.last_trace)
                return self.result(tid, exc.status, error_code=exc.status, user_facing_summary={'headline': str(exc)})
            self.trace.update(self.parser.last_trace)
        if self.trace['parsed_actions'] is None:self.trace['parsed_actions'] = proposal.to_dict()
        self.trace['normalized_actions'] = proposal.to_dict()
        self.trace['semantic_validation'] = 'passed'
        if proposal.needs_clarification:
            duration = proposal.clarification_reason == 'duration_required'
            index = next((i for i, a in enumerate(proposal.actions) if a.action_type in ('SET_TIME_TARGET', 'SET_HARD_TIME_LIMIT')), 0)
            if proposal.clarification_reason == 'target_required':
                index = next(i for i, a in enumerate(proposal.actions) if a.action_type in TARGET_ACTIONS and not a.target_mentions)
                return self.clarify(trip, proposal, reason='target_required', question='Which destination do you mean?',
                                    kind='target', location=[index, 'target_mentions', 0])
            return self.clarify(trip, proposal, reason=proposal.clarification_reason,
                                question='Roughly how many more minutes would you like to spend?' if duration else 'Which action or destination do you mean?',
                                kind='duration' if duration else 'intent', location=[index] if duration else None)
        types = [a.action_type for a in proposal.actions]
        if pending and all(a in READ_ACTIONS for a in types):self.service.conversations.set(tid, pending)
        if read_only or trip.status != 'ACTIVE':
            if not all(a in READ_ACTIONS or a in ('START_TRIP', 'ABANDON_TRIP') for a in types):
                return self.result(tid, 'not_applicable', error_code='mutations_not_allowed', user_facing_summary={'headline': 'Only read queries are available before start or after the trip ends.'})
        if 'UNSUPPORTED' in types:return self.result(tid, 'unsupported_action', error_code='unsupported_action', user_facing_summary={'headline': 'The requested capability is not supported.'})
        if 'DWELL_LONGER' in types:
            index = types.index('DWELL_LONGER')
            return self.clarify(trip, proposal, reason='dwell_duration_required', question='How much longer would you like to stay? Dynamic per-stop dwell requires a duration and is not yet supported.',
                                kind='duration', location=[index])
        if all(a in READ_ACTIONS for a in types):return self.read(trip, proposal)
        if any(a in ('START_TRIP', 'ABANDON_TRIP', 'CANCEL') for a in types):
            self.trace['mutation_scope'] = ['CORE_PROGRESS']
            if len(types) != 1:return self.clarify(trip, proposal, reason='lifecycle_compound', question='Start/end the trip separately from route changes.', kind='intent')
            try:
                if types[0] == 'START_TRIP':
                    if trip.status == 'ACTIVE':return self.result(tid, 'no_change', user_facing_summary={'headline': 'The trip is already active.'})
                    if trip.status != 'PLANNED':raise MutationError('not_applicable', 'Ended trips cannot be restarted')
                    self.service.core.start_trip(tid, expected_revision=trip.state_revision);return self.result(tid, 'trip_started')
                if types[0] == 'ABANDON_TRIP':
                    if trip.status == 'PLANNED':self.service.core.cancel_planned_trip(tid, expected_revision=trip.state_revision)
                    elif trip.status == 'ACTIVE':self.service.core.abandon_trip(tid, expected_revision=trip.state_revision)
                    else:raise MutationError('not_applicable', 'The trip has already ended')
                    return self.result(tid, 'trip_abandoned')
                return self.result(tid, 'not_applicable', error_code='no_pending_clarification')
            except StaleStateConflict:return self.result(tid, 'stale_state_conflict', error_code='stale_state_conflict')
            except (TripStateError, MutationError) as exc:return self.result(tid, 'not_applicable', user_facing_summary={'headline': str(exc)})
        resolved = []
        # Finite entity normalization: unique POI concepts take precedence over categories.
        for i, a in enumerate(proposal.actions):
            if a.action_type in ('ADD_AVOID', 'ADD_INTEREST') and len(a.preference_concepts) == 1:
                specific = self.resolver.resolve(a.preference_concepts[0])
                if specific['status'] == 'resolved':
                    a.target_mentions = list(a.preference_concepts);a.preference_tags = [];a.preference_concepts = []
                    a.request_matching_insert = False
                    a.action_type = 'REMOVE_PLACE' if a.action_type == 'ADD_AVOID' else 'ADD_PLACE'
            item = dict(action=a, target_ids=[], secondary_ids=[])
            for field, dest in (('target_mentions', 'target_ids'), ('secondary_target_mentions', 'secondary_ids')):
                for j, mention in enumerate(getattr(a, field)):
                    r = self.resolver.resolve(mention, trip)
                    self.trace['poi_resolution'].append(dict(mention=mention, result=r))
                    if r['status'] != 'resolved':
                        return self.clarify(trip, proposal, reason=r['status'], question='Which production destination do you mean?', options=r['options'], location=[i, field, j])
                    item[dest].append(r['poi_id'])
            resolved.append(item)
        self.trace['normalized_actions'] = proposal.to_dict()
        self.trace['mutation_scope'] = list(dict.fromkeys(SCOPES.get(a.action_type, 'PREFERENCE_ADJUST') for a in proposal.actions))
        if any(item['action'].action_type == 'REVISIT_PLACE' for item in resolved):
            self.trace['mutation_scope'] = ['INSERT_ONLY']
            return self.result(tid, 'revisit_not_supported', parsed_command=proposal.to_dict(), error_code='revisit_not_supported',
                               user_facing_summary={'headline': 'Revisit was understood. This trip records one visit per destination; a second visit occurrence is not supported.'})
        for item in resolved:
            if item['action'].action_type in ('ADD_PLACE', 'ADD_MUST_GO'):
                if any(pid in trip.visited_poi_ids for pid in item['target_ids']):
                    return self.result(tid, 'revisit_not_supported', error_code='revisit_not_supported', user_facing_summary={'headline': 'That destination was already visited. Adding a second visit occurrence is not supported.'})
                if any(pid in trip.skipped_poi_ids for pid in item['target_ids']):
                    return self.clarify(trip, proposal, reason='previously_skipped', question='You previously skipped this stop. Do you want to add it back? Restoring a visit occurrence is not supported yet.',
                                        options=[{'label': 'Add it back'}, {'label': 'Keep it skipped'}], kind='restore')
        try:return self.execute(trip, proposal, resolved)
        except StaleStateConflict:
            return self.result(tid, 'stale_state_conflict', error_code='stale_state_conflict', user_facing_summary={'headline': 'The trip changed. Please try again using the latest route.'})
        except (MutationError, TripStateError) as exc:
            status = exc.status if isinstance(exc, MutationError) else 'state_conflict'
            summary = {'headline': str(exc)}
            if status == 'state_conflict':
                diagnostics = getattr(exc, 'diagnostics', None) or dict(constraint_type='domain_constraint', hard_limit_minutes=None,
                    minimum_feasible_minutes=None, protected_stops=[], removable_stops=[], blocking_constraints=[str(exc)],
                    reason_code='other_domain_constraint', blocking_reason=str(exc))
                self.trace['conflict_diagnostics'] = diagnostics
                summary['conflict_diagnostics'] = diagnostics
                if diagnostics['constraint_type'] == 'hard_remaining_limit':
                    from .trip_action_rendering import conflict_summary
                    summary.update(conflict_summary(diagnostics))
            return self.result(tid, status, error_code=status, parsed_command=proposal.to_dict(), user_facing_summary=summary)

    def read(self, trip, proposal):
        if len(proposal.actions) > 1:
            values = [self.read(trip, TripUtteranceProposal([a])).read_result for a in proposal.actions]
            return self.result(trip.trip_id, 'success_query', read_result={'query_type': 'multiple_read_queries', 'value': values},
                               user_facing_summary={'headline': 'Requested route information'}, parsed_command=proposal.to_dict())
        action = proposal.actions[0].action_type;tid = trip.trip_id
        query = {'SHOW_CURRENT_ROUTE': 'show_current_route', 'SHOW_ORIGINAL_ROUTE': 'show_original_route',
                 'SHOW_ROUTE_HISTORY': 'show_route_history', 'WHY_LATEST_REPLAN': 'why_latest_replan', 'SHOW_PROGRESS': 'show_progress'}[action]
        if action == 'SHOW_CURRENT_ROUTE':value = dict(route=trip.active_route, remaining_stops=trip.get_remaining_stops())
        elif action == 'SHOW_ORIGINAL_ROUTE':value = trip.original_route
        elif action == 'SHOW_ROUTE_HISTORY':value = self.service.core.get_route_history(tid)
        elif action == 'WHY_LATEST_REPLAN':
            value = self.service.explanations.build(self.service.core.get_latest_replan_summary(tid), self.service.core.get_route_history(tid))
            value['headline'] = 'Latest route change' if trip.replan_history else 'No route changes yet'
        else:value = dict(visited_count=len(trip.visited_poi_ids), skipped_count=len(trip.skipped_poi_ids), remaining_count=len(trip.remaining_poi_ids),
                         remaining_minutes=trip.remaining_minutes, current_poi_id=trip.current_poi_id, trip_status=trip.status,
                         current_stop=self.service.explanations.stops([trip.current_poi_id])[0] if trip.current_poi_id else None)
        self.trace['mutation_scope'] = ['READ_ONLY'];self.trace['domain_validation'] = 'passed'
        return self.result(tid, 'success_query', command_type='read_query', parsed_command=proposal.to_dict(), read_result=dict(query_type=query, value=value),
                           user_facing_summary=value if action == 'WHY_LATEST_REPLAN' else {'headline': query.replace('_', ' ')})

    def execute(self, trip, proposal, resolved):
        tid = trip.trip_id;revision = trip.state_revision;before_state = trip.to_dict()
        before = trip.get_remaining_stops();stops = copy.deepcopy(before);intent = trip.current_intent
        policy = copy.deepcopy(trip._data.get('interaction_policy', dict(time_constraint_mode='soft', target_deadline=trip.elapsed_minutes + trip.time_target_minutes, hard_deadline=None)))
        core_result = None;core_results = [];mutations = False;explicit_inserted = set();completed_now = set()
        requested_count = 0;matched_added = [];reduction_goals = []
        for item in sorted(resolved, key=lambda row: PRIORITY.get(row['action'].action_type, 7)):
            a = item['action'];kind = a.action_type
            if kind == 'COMPLETE_STOP':
                if len(item['target_ids']) != 1:raise MutationError('ambiguous_intent', 'Complete one stop at a time')
                pid = item['target_ids'][0]
                if pid not in trip.remaining_poi_ids:raise MutationError('not_applicable', 'This destination is not an executable future stop')
                trip.complete_stop(pid);stops = [s for s in stops if s['poi_id'] != pid]
                core_result = dict(action='complete_stop', poi_id=pid, changed=True, saved=True)
                core_results.append(core_result);completed_now.add(pid)
            elif kind in ('SKIP_PLACE', 'REMOVE_PLACE'):
                for pid in item['target_ids']:
                    if pid not in self.mutations.ids(stops):raise MutationError('not_applicable', 'Removal target is not on the future route')
                    if kind == 'SKIP_PLACE':
                        trip.skip_stop(pid);core_result = dict(action='skip_stop', poi_id=pid, changed=True, saved=True);core_results.append(core_result)
                    stops = self.mutations.remove_only(stops, pid)
                    intent['must_go_poi_ids'] = [p for p in intent['must_go_poi_ids'] if p != pid]
                mutations = True
            elif kind in ('ADD_PLACE', 'ADD_MUST_GO'):
                for pid in item['target_ids']:
                    explicit_inserted.add(pid)
                    if pid not in self.mutations.ids(stops):
                        stop = self.mutations.candidate(trip, pid, intent, must_go=kind == 'ADD_MUST_GO')
                        stops = self.mutations.insert_only(trip, stops, stop, intent);mutations = True
                    if kind == 'ADD_MUST_GO' and pid not in intent['must_go_poi_ids']:intent['must_go_poi_ids'].append(pid);mutations = True
            elif kind == 'REPLACE_PLACE':
                if len(item['target_ids']) != 1:raise MutationError('ambiguous_intent', 'Replace exactly one target')
                target = item['target_ids'][0]
                target_index = self.mutations.ids(stops).index(target) if target in self.mutations.ids(stops) else None
                stops = self.mutations.replace_targeted(trip, stops, target, intent, item['secondary_ids'][0] if item['secondary_ids'] else None)
                explicit_inserted.add(stops[target_index]['poi_id'])
                if target in intent['must_go_poi_ids']:
                    intent['must_go_poi_ids'].remove(target)
                    intent['must_go_poi_ids'].append(stops[target_index]['poi_id'])
                mutations = True
            elif kind in ('ADD_INTEREST', 'REMOVE_INTEREST', 'ADD_AVOID', 'REMOVE_AVOID'):
                if not a.preference_tags:raise MutationError('ambiguous_intent', 'Which preference should change?')
                if kind in ('ADD_AVOID', 'REMOVE_AVOID'):groups = [('avoid_tags', a.preference_tags)]
                else:groups = [(g, [t for t in a.preference_tags if t in self.repository.taxonomy[g]]) for g in ('interest_tags', 'experience_tags', 'culture_tags')]
                new_tags = []
                for group, tags in groups:
                    if kind.startswith('ADD'):new_tags += [t for t in tags if t not in intent[group]];intent[group] = list(dict.fromkeys(intent[group]+tags))
                    else:intent[group] = [t for t in intent[group] if t not in tags]
                if kind == 'ADD_AVOID':
                    stops = [s for s in stops if s['poi_id'] in intent['must_go_poi_ids'] or not (self.mutations.tags(s['poi_id']) & set(intent['avoid_tags']))]
                matching_tags = list(dict.fromkeys(new_tags + (a.preference_tags if a.request_matching_insert else [])))
                if kind == 'ADD_INTEREST' and matching_tags:
                    count = a.requested_count or 1
                    stops, added = self.mutations.add_matching(trip, stops, intent, count, matching_tags)
                    if a.request_matching_insert or a.requested_count:
                        requested_count += count;matched_added.extend(added);explicit_inserted.update(added)
            elif kind == 'ADD_MATCHING_STOPS':
                count = a.requested_count or 1;requested_count += count
                stops, added = self.mutations.add_matching(trip, stops, intent, count, a.preference_tags)
                matched_added.extend(added);explicit_inserted.update(added)
            elif kind == 'SHORTEN_ROUTE':
                goal = a.reduction_goal or 'easier';reduction_goals.append(goal)
                stops = self.mutations.shorten(trip, stops, intent, goal)
            elif kind == 'SET_PACE':intent['travel_pace'] = a.pace
            elif kind in ('MOVE_PLACE_NEXT', 'MOVE_PLACE_BEFORE', 'MOVE_PLACE_AFTER'):
                if len(item['target_ids']) != 1:raise MutationError('ambiguous_intent', 'Order one destination at a time')
                relation = a.position_relation or {'MOVE_PLACE_NEXT': 'next', 'MOVE_PLACE_BEFORE': 'before', 'MOVE_PLACE_AFTER': 'after'}[kind]
                stops = self.mutations.reorder_only(stops, item['target_ids'][0], relation, item['secondary_ids'][0] if item['secondary_ids'] else None)
            elif kind in ('SET_TIME_TARGET', 'SET_HARD_TIME_LIMIT'):
                if a.time_value_minutes is None:raise MutationError('ambiguous_intent', 'A duration is required')
                policy['target_deadline'] = trip.elapsed_minutes + a.time_value_minutes
                if kind == 'SET_HARD_TIME_LIMIT':policy.update(time_constraint_mode='hard', hard_deadline=trip.elapsed_minutes+a.time_value_minutes)
            elif kind == 'FULL_REPLAN':pass
            else:raise MutationError('unsupported_action', 'Recognized action is not executable')
        # Exception must-go overrides a category avoidance regardless of utterance ordering.
        must = set(intent['must_go_poi_ids']) - set(trip.excluded_poi_ids)
        if any(a.action_type != 'COMPLETE_STOP' for a in proposal.actions):
            intent['must_go_poi_ids'] = [pid for pid in self.mutations.ids(stops) if pid in must]
        if policy['time_constraint_mode'] == 'hard':
            budget = max(0, policy['hard_deadline']-trip.elapsed_minutes)
            if any(a.action_type.startswith('MOVE_PLACE') for a in proposal.actions) and self.mutations.metrics(trip, stops, intent)[3] > budget:
                raise MutationError('state_conflict', 'The requested order exceeds the hard deadline; choose a longer limit or remove stops',
                    self.mutations.hard_conflict_diagnostics(trip, stops, intent, budget, required_ids=explicit_inserted, preserve_order=True))
            try:stops = self.mutations.compress(trip, stops, intent, budget, required_ids=explicit_inserted)
            except MutationError as exc:
                exc.diagnostics = self.mutations.hard_conflict_diagnostics(trip, stops, intent, budget, required_ids=explicit_inserted,
                    search_exhausted='Too many possible compressions' in str(exc))
                raise
        if reduction_goals:
            old = self.mutations.metrics(trip, before, trip.current_intent)
            new = self.mutations.metrics(trip, stops, intent)
            for goal in reduction_goals:
                improved = (new[0] < old[0]-0.001 if goal == 'walking' else len(stops) < len(before) if goal == 'stops'
                            else new[3] < old[3]-0.1 and new[0] <= old[0]+0.001)
                if not improved:
                    if self.store.get(tid).state_revision != revision:raise StaleStateConflict('stale_state_conflict')
                    return self.result(tid, 'no_change', parsed_command=proposal.to_dict(), error_code='protected_or_no_improvement',
                        user_facing_summary={'headline': 'No shorter feasible route was found while preserving your required stops. Your route is unchanged.'})
        mutation_needed = mutations or intent != trip.current_intent or self.mutations.ids(stops) != self.mutations.ids(trip.get_remaining_stops()) or policy != trip._data.get('interaction_policy', dict(time_constraint_mode='soft', target_deadline=trip.elapsed_minutes+trip.time_target_minutes, hard_deadline=None))
        if mutation_needed:
            route = self.mutations.build_route(trip, stops, intent, policy)
            diff = self.mutations.diff([s for s in before if s['poi_id'] not in completed_now], stops)
            target = max(0, policy['target_deadline']-trip.elapsed_minutes);estimated = route['total_estimated_minutes']
            warning = dict(estimated_minutes=estimated, target_minutes=target, estimated_overrun_minutes=estimated-target, severity='warning') if estimated > target else None
            scopes = self.trace['mutation_scope'];route_scopes = [s for s in scopes if s != 'CORE_PROGRESS']
            scope = route_scopes[0] if len(route_scopes) == 1 else 'PREFERENCE_ADJUST'
            payload = dict(mutation_scope=scope, action_scopes=scopes, estimated_minutes=estimated, target_minutes=target,
                           time_constraint_mode=policy['time_constraint_mode'], time_warning=warning,
                           hard_limit_minutes=max(0, policy['hard_deadline']-trip.elapsed_minutes) if policy['time_constraint_mode'] == 'hard' else None,
                           actions=[a.action_type for a in proposal.actions], **diff)
            for name in ('added', 'removed', 'kept', 'reordered'):payload[name+'_stops'] = self.service.explanations.stops(diff[name+'_ids'])
            payload.update(before_metrics=self.mutations.remaining_metrics(trip, before, trip.current_intent),
                           after_metrics=self.mutations.remaining_metrics(trip, stops, intent),
                           requested_count=requested_count or None, actual_added_count=len(matched_added),
                           execution_status='PARTIALLY_APPLIED' if requested_count > len(matched_added) else 'APPLIED',
                           reason_code='candidate_shortage' if requested_count > len(matched_added) else 'verified_change',
                           preserved_must_go_ids=[pid for pid in intent['must_go_poi_ids'] if pid in self.mutations.ids(stops)],
                           interpreted_intent=proposal.to_dict(), request_text=self.trace.get('user_text', ''),
                           visit_mode_changes=[dict(poi_id=b['poi_id'], before=b['selected_visit_mode'], after=n['selected_visit_mode'])
                               for b in before for n in stops if b['poi_id']==n['poi_id'] and b['selected_visit_mode']!=n['selected_visit_mode']])
            payload['old_version'] = trip.route_versions[-1]['version_id']
            payload['new_version'] = 'v'+str(len(trip.route_versions)+1)
            trip.commit_mutation(route, intent, policy, reason=scope, diagnostics=payload, allow_terminal_disposition=trip.status == 'COMPLETED')
            self.store.save_if_revision(trip, revision)
            self.trace['domain_validation'] = 'passed';self.trace['route_diff'] = payload;self.trace['warnings'] = [warning] if warning else []
            result = self.result(tid, 'success_mutated', command_type='route_mutation', parsed_command=proposal.to_dict(), core_action_result=core_results[0] if core_results else None,
                                 core_action_results=core_results,
                                 mutation_result=payload, user_facing_summary=dict(headline='Route updated', reasons=[a.action_type.replace('_',' ').lower() for a in proposal.actions], **payload))
        elif trip.to_dict() != before_state:
            self.store.save_if_revision(trip, revision);self.trace['domain_validation'] = 'passed'
            result = self.result(tid, 'success_core_action', command_type='core_action', parsed_command=proposal.to_dict(), core_action_result=core_results[0] if core_results else None,
                                 core_action_results=core_results,
                                 user_facing_summary={'headline': 'Stop completed.'})
        else:
            # Even a semantic no-op must validate the interpreted snapshot revision.
            if self.store.get(tid).state_revision != revision:raise StaleStateConflict('stale_state_conflict')
            result = self.result(tid, 'no_change', parsed_command=proposal.to_dict(), user_facing_summary={'headline': 'No eligible additional stops are available under your saved constraints.' if requested_count else 'Your request is already reflected in the saved plan.'}, error_code='candidate_shortage' if requested_count else None)
        if any(a.action_type == 'FULL_REPLAN' for a in proposal.actions):
            current = self.store.get(tid)
            if current.state_revision != (trip.state_revision):raise StaleStateConflict('stale_state_conflict')
            replan = self.service.coordinator.replan(tid, expected_revision=current.state_revision, must_go_overrides_avoid=True, mutation_scope='FULL_REPLAN')
            self.trace['mutation_scope'] = ['FULL_REPLAN'];self.trace['domain_validation'] = replan.status
            if replan.committed:
                record = self.service.core.get_latest_replan_summary(tid)
                summary = self.service.explanations.build(record, self.service.core.get_route_history(tid))
                payload = {k: v for k, v in replan.diagnostics.items() if k in ('mutation_scope', 'action_scopes', 'old_version', 'new_version',
                           'added_stops', 'removed_stops', 'kept_stops', 'reordered_stops', 'estimated_minutes', 'target_minutes',
                           'time_constraint_mode', 'time_warning', 'retained_stop_count', 'removed_stop_count', 'added_stop_count',
                           'reordered_stop_count', 'route_preservation_ratio', 'added_ids', 'removed_ids', 'kept_ids', 'reordered_ids', 'hard_limit_minutes')}
                self.trace['route_diff'] = payload
                return self.result(tid, 'success_replanned', replan_result=replan.to_dict(), mutation_result=payload, user_facing_summary=summary)
            local_changed = result.status in ('success_mutated', 'success_core_action')
            final_status = result.status if replan.status == 'no_change' and local_changed else 'no_change' if replan.status == 'no_change' else 'stale_state_conflict' if replan.status == 'stale_state_conflict' else 'state_conflict'
            return self.result(tid, final_status, replan_result=replan.to_dict(), mutation_result=result.mutation_result,
                               core_action_result=result.core_action_result, core_action_results=result.core_action_results,
                               error_code=None if replan.status == 'no_change' else replan.status,
                               user_facing_summary={'headline': ('Your explicit local change was saved. ' if local_changed else '') +
                                                   ('The full replan made no additional change.' if replan.status == 'no_change' else 'The full replan could not satisfy the saved constraints.')})
        return result
