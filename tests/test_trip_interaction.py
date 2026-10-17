"""Minimal-edit properties, protocol boundaries, and offline corpus checks.

Mock corpus checks are not live model accuracy; human live eval is separate.
"""
import copy
import hashlib
import io
import json
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools.evaluation.nlu_live_eval import evaluate, signature, CONTEXT
from tests.trip_semantics_fixture import build_agent
from tools.demos.trip_agent_demo import AgentResponseRenderer
from src.intent_models import RouteIntent, RouteMode
from src.llm_client import LLMClientError, MockLLMClient
from src.poi_repository import POIRepository
from src.trip_actions import ActionPOIResolver, ActionParseError, TripActionParser, action_schema
from src.trip_action_fixtures import ACTION_FIXTURES, ACCEPTANCE_CASES, action, utterance
from src.trip_agent_fixtures import FULL_JOURNEY_INITIAL
from src.trip_state import TripState, TripStateError


class MutationTests(unittest.TestCase):
    def setUp(self):
        self.agent = build_agent();self.sid = self.agent.create_session().session_id
        self.agent.handle_turn(self.sid, FULL_JOURNEY_INITIAL);self.agent.handle_turn(self.sid, 'start')
        self.executor = self.agent.conversation.actions

    def state(self):return self.agent.trip_store.get(self.agent.sessions.get(self.sid).trip_id)
    def ids(self):return self.state().remaining_poi_ids
    def turn(self, text):return self.agent.handle_turn(self.sid, text)
    def act(self, *actions):
        self.agent.client.responses = [utterance(*actions)]
        return self.turn('A paraphrased user request interpreted by the supplied mock proposal.')
    def add(self, name='West Bund Museum', must=False):
        r = self.act(action('ADD_MUST_GO' if must else 'ADD_PLACE', target_mentions=[name]))
        self.assertEqual(r.status, 'success_mutated', r.user_facing_summary);return r
    def unchanged(self, *actions, status):
        before = self.state().to_dict();r = self.act(*actions)
        self.assertEqual(r.status, status, r.user_facing_summary);self.assertEqual(before, self.state().to_dict());return r

    def test_01_live_case_skip_never_refills_or_reorders(self):
        before = self.ids();pid = before[0]
        with patch.object(self.agent.conversation.coordinator, 'replan', side_effect=AssertionError('skip full replan')):
            r = self.turn('Skip this place.')
        self.assertEqual(self.ids(), before[1:]);self.assertEqual(r.mutation_result['added_stops'], [])
        self.assertEqual(r.mutation_result['removed_ids'], [pid]);self.assertIn(pid, self.state().skipped_poi_ids)
        self.assertEqual(r.mutation_result['mutation_scope'], 'REMOVE_ONLY')

    def test_02_live_named_remove_not_category(self):
        self.add();before = self.ids();r = self.turn("I don't want to go to West Bund Museum anymore.")
        self.assertEqual(self.ids(), [p for p in before if p != 'p28'])
        self.assertEqual(r.status, 'success_mutated');self.assertNotIn('museum_visit', self.state().avoid_tags)
        self.assertNotIn('p28', self.state().skipped_poi_ids)

    def test_03_add_preserves_entire_existing_subsequence(self):
        before = self.ids();r = self.add()
        self.assertEqual([p for p in self.ids() if p in before], before)
        self.assertEqual(set(self.ids())-set(before), {'p28'});self.assertEqual(r.mutation_result['removed_stops'], [])

    def test_04_add_long_museum_soft_overrun(self):
        self.act(action('REMOVE_PLACE', target_mentions=['Long Museum']))
        self.act(action('SET_TIME_TARGET', time_value_minutes=30))
        before = self.ids();r = self.turn('Add Long Museum to my route.')
        self.assertEqual([p for p in self.ids() if p in before], before);self.assertIn('p5', self.ids())
        warning = r.mutation_result['time_warning'];self.assertGreater(warning['estimated_overrun_minutes'], 0)
        self.assertAlmostEqual(warning['estimated_overrun_minutes'], warning['estimated_minutes']-30)

    def test_05_strong_must_go_keeps_existing_under_soft(self):
        self.act(action('SET_TIME_TARGET', time_value_minutes=30));before = self.ids();r = self.add(must=True)
        self.assertIn('p28', self.state().must_go_remaining)
        self.assertEqual([p for p in self.ids() if p in before], before);self.assertIsNotNone(r.mutation_result['time_warning'])

    def test_06_normal_add_is_not_must_go(self):
        self.add();self.assertNotIn('p28', self.state().must_go_remaining)

    def test_07_revisit_explicit_unsupported_not_noop(self):
        self.turn("I've finished this stop.");before = self.state().to_dict()
        r = self.turn('I want to visit TANK Shanghai again.')
        self.assertEqual(r.status, 'revisit_not_supported');self.assertEqual(before, self.state().to_dict())

    def test_08_plain_add_visited_not_silent_noop(self):
        self.turn("I've finished this stop.")
        self.unchanged(action('ADD_PLACE', target_mentions=['TANK Shanghai']), status='revisit_not_supported')

    def test_09_replace_exactly_one_no_other_changes(self):
        before = self.ids();r = self.turn('Skip this place and find me another one.')
        self.assertEqual(r.mutation_result['mutation_scope'], 'REPLACE_TARGETED')
        self.assertEqual(len(set(self.ids())-set(before)), 1);self.assertEqual(len(set(before)-set(self.ids())), 1)
        self.assertEqual(self.ids()[1:], before[1:]);self.assertEqual(self.state().skipped_poi_ids, [])

    def test_10_named_replacement_keeps_slot(self):
        before = self.ids();r = self.act(action('REPLACE_PLACE', target_mentions=['Beipiao Wharf Crane'], secondary_target_mentions=['West Bund Museum']))
        self.assertEqual(self.ids(), [before[0], 'p28', before[2]]);self.assertEqual(r.status, 'success_mutated')

    def test_11_reorder_changes_only_order(self):
        before = self.ids();r = self.turn('Can we go to Long Museum next?')
        self.assertEqual(self.ids(), ['p5'] + [p for p in before if p != 'p5'])
        self.assertEqual(r.mutation_result['added_stops'], []);self.assertEqual(r.mutation_result['removed_stops'], [])
        self.assertGreater(r.mutation_result['reordered_stop_count'], 0)

    def test_12_move_before_and_after(self):
        self.add();r = self.act(action('MOVE_PLACE_BEFORE', target_mentions=['Long Museum'], secondary_target_mentions=['West Bund Museum']))
        self.assertEqual(r.status, 'success_mutated');self.assertLess(self.ids().index('p5'), self.ids().index('p28'))
        r = self.act(action('MOVE_PLACE_AFTER', target_mentions=['Long Museum'], secondary_target_mentions=['West Bund Museum']))
        self.assertEqual(r.status, 'success_mutated');self.assertGreater(self.ids().index('p5'), self.ids().index('p28'))

    def test_13_move_missing_does_not_insert(self):
        self.unchanged(action('MOVE_PLACE_NEXT', target_mentions=['West Bund Museum']), status='not_applicable')

    def test_14_move_last(self):
        before = self.ids();r = self.act(action('MOVE_PLACE_AFTER', target_mentions=['TANK Shanghai'], position_relation='last'))
        self.assertEqual(self.ids(), before[1:]+before[:1]);self.assertEqual(r.status, 'success_mutated')

    def test_15_soft_only_time_never_deletes(self):
        before = self.ids();r = self.turn("I'd like to spend about another hour, but there's no rush.")
        self.assertEqual(self.ids(), before);self.assertEqual(self.state().time_constraint_mode, 'soft')
        self.assertEqual(r.mutation_result['target_minutes'], 60);self.assertIsNotNone(r.mutation_result['time_warning'])

    def test_16_hard_time_can_compress_without_refill(self):
        before = self.ids();r = self.turn('I must finish within one hour.')
        self.assertEqual(r.status, 'success_mutated');self.assertEqual(self.state().time_constraint_mode, 'hard')
        self.assertLessEqual(self.state().active_route['total_estimated_minutes'], 60)
        self.assertTrue(set(self.ids()) < set(before));self.assertEqual(r.mutation_result['added_stops'], [])

    def test_17_hard_limit_keeps_must_or_conflicts(self):
        self.act(action('ADD_MUST_GO', target_mentions=['Long Museum']))
        self.unchanged(action('SET_HARD_TIME_LIMIT', time_value_minutes=1), status='state_conflict')
        self.assertIn('p5', self.state().must_go_remaining)

    def test_18_soft_time_can_increase_target(self):
        r = self.act(action('SET_TIME_TARGET', time_value_minutes=300))
        self.assertEqual(self.state().remaining_minutes, 300);self.assertEqual(r.mutation_result['target_minutes'], 300)

    def test_19_soft_target_does_not_relax_saved_hard_limit(self):
        self.turn('I must finish within one hour.');before = self.ids()
        r = self.act(action('SET_TIME_TARGET', time_value_minutes=180))
        self.assertEqual(r.mutation_result['time_constraint_mode'], 'hard');self.assertEqual(self.ids(), before)
        self.assertEqual(self.state().remaining_minutes, 60)

    def test_20_full_replan_explicitly_calls_original_coordinator_once(self):
        with patch.object(self.agent.conversation.coordinator, 'replan', wraps=self.agent.conversation.coordinator.replan) as coordinator:
            r = self.turn('Replan the remaining route completely.')
        self.assertEqual(coordinator.call_count, 1);self.assertEqual(r.status, 'success_replanned')
        self.assertEqual(r.nlu_trace['mutation_scope'], ['FULL_REPLAN'])

    def test_21_no_coordinator_for_all_local_changes(self):
        with patch.object(self.agent.conversation.coordinator, 'replan', side_effect=AssertionError('unauthorized full replan')):
            self.add();self.turn('I only have one hour left.');self.turn('Can we go to Long Museum next?')
            self.turn('Skip this place.');self.act(action('SET_PACE', pace='deep'))

    def test_22_category_avoid_no_refill(self):
        self.add();before = self.ids();r = self.turn("I don't want museums anymore.")
        expected = [p for p in before if 'museum_visit' not in self.executor.mutations.tags(p)]
        self.assertEqual(self.ids(), expected);self.assertEqual(r.mutation_result['added_stops'], [])
        self.assertIn('museum_visit', self.state().avoid_tags)

    def test_23_specific_category_misclassification_is_resolved_before_execution(self):
        self.add();r = self.act(action('ADD_AVOID', preference_concepts=['West Bund Museum'], preference_tags=['museum_visit']))
        self.assertEqual(r.status, 'success_mutated');self.assertNotIn('p28', self.ids())
        self.assertNotIn('museum_visit', self.state().avoid_tags);self.assertIn('p5', self.ids())

    def test_24_negation_exception_must_go_overrides_avoid(self):
        self.add();r = self.turn("I don't want museums, but I still want Long Museum.")
        self.assertEqual(r.status, 'success_mutated');self.assertIn('p5', self.ids());self.assertIn('p5', self.state().must_go_remaining)
        self.assertNotIn('p28', self.ids());self.assertIn('museum_visit', self.state().avoid_tags)

    def test_25_remove_avoid_does_not_refill(self):
        self.turn("I don't want museums anymore.");before = self.ids();r = self.turn('Actually, museums are fine again.')
        self.assertEqual(self.ids(), before);self.assertNotIn('museum_visit', self.state().avoid_tags)
        self.assertEqual(r.mutation_result['added_stops'], [])

    def test_26_removed_place_can_be_added_back(self):
        self.add();self.turn("I don't want West Bund Museum anymore.");r = self.turn('Actually, keep West Bund Museum.')
        self.assertEqual(r.status, 'success_mutated');self.assertIn('p28', self.ids())

    def test_27_skipped_restore_requires_explicit_confirmation(self):
        self.turn('Skip this place.');before = self.state().to_dict()
        r = self.act(action('ADD_PLACE', target_mentions=['TANK Shanghai']))
        self.assertEqual(r.status, 'ambiguous_intent');self.assertEqual(r.clarification['reason'], 'previously_skipped')
        r = self.turn('1');self.assertEqual(r.status, 'unsupported_action');self.assertEqual(before, self.state().to_dict())

    def test_28_compound_deterministic_remove_insert_order(self):
        before = self.ids();r = self.turn('Remove this stop and put Long Museum next.')
        self.assertEqual(r.status, 'success_mutated');self.assertEqual(self.ids(), ['p5', 'p43'])
        self.assertNotIn(before[0], self.ids());self.assertEqual(r.mutation_result['added_stops'], [])

    def test_29_order_of_model_actions_does_not_change_execution_priority(self):
        r = self.act(action('MOVE_PLACE_NEXT', target_mentions=['West Bund Museum']),
                     action('ADD_PLACE', target_mentions=['West Bund Museum']), action('REMOVE_PLACE', target_mentions=['TANK Shanghai']))
        self.assertEqual(r.status, 'success_mutated');self.assertEqual(self.ids()[0], 'p28');self.assertNotIn('p29', self.ids())

    def test_30_failed_compound_is_atomic(self):
        self.unchanged(action('SKIP_PLACE', target_mentions=['this place']), action('ADD_PLACE', target_mentions=['Wukang Mansion']), status='state_conflict')
        self.assertEqual(self.state().skipped_poi_ids, [])

    def test_31_original_history_and_mutation_replay(self):
        original = self.state().original_route;self.turn('Skip this place.');self.add();self.turn('I only have one hour left.')
        state = self.state();self.assertEqual(state.original_route, original)
        self.assertEqual(TripState.from_dict(state.to_dict()).to_dict(), state.to_dict())
        self.assertEqual(len(state.route_versions), 4)
        raw = state.to_dict();raw['active_route']['ordered_pois'].reverse()
        with self.assertRaises(TripStateError):TripState.from_dict(raw)

    def test_32_why_is_latest_change_and_readonly(self):
        self.turn('Skip this place.');before = self.state().to_dict()
        r = self.turn('Why did you change my route?')
        self.assertEqual(r.user_facing_summary['headline'], 'Latest route change')
        self.assertEqual(r.read_result['value']['removed_ids'], ['p29']);self.assertEqual(before, self.state().to_dict())

    def test_33_multiple_queries_are_not_silently_dropped(self):
        before = self.state().to_dict();r = self.act(action('SHOW_ORIGINAL_ROUTE'), action('SHOW_CURRENT_ROUTE'))
        self.assertEqual(r.status, 'success_query');self.assertEqual(len(r.read_result['value']), 2)
        self.assertEqual(before, self.state().to_dict())

    def test_34_empty_route_skip_does_not_refill(self):
        self.turn("I've finished this stop.");self.turn('Skip this place.');r = self.turn('Skip this place.')
        self.assertEqual(r.session_phase, 'COMPLETED');self.assertEqual(self.ids(), [])
        self.assertEqual(r.mutation_result['added_stops'], []);self.assertEqual(self.state().active_route['ordered_pois'], [])
        self.assertEqual(TripState.from_dict(self.state().to_dict()).status, 'COMPLETED')

    def test_35_positive_preference_adds_only_matching_destination(self):
        before = self.ids();r = self.act(action('ADD_INTEREST', preference_tags=['art']))
        self.assertEqual(r.status, 'success_mutated');self.assertEqual([p for p in self.ids() if p in before], before)
        self.assertLessEqual(len(set(self.ids())-set(before)), 1)
        for pid in set(self.ids())-set(before):self.assertIn('art', self.executor.mutations.tags(pid))

    def test_36_actual_semantic_noop_does_not_version(self):
        self.unchanged(action('ADD_INTEREST', preference_tags=['architecture']), status='no_change')
        self.unchanged(action('ADD_PLACE', target_mentions=['Long Museum']), status='no_change')

    def test_37_unresolved_or_ambiguous_not_invalid_command(self):
        self.unchanged(action('ADD_PLACE', target_mentions=['Imaginary Tower']), status='ambiguous_target')
        self.unchanged(action('REMOVE_PLACE', target_mentions=['the museum']), status='ambiguous_target')

    def test_38_numeric_duration_clarification_no_provider(self):
        r = self.turn("I'd like to finish earlier.");self.assertEqual(r.status, 'needs_duration_clarification')
        before = self.ids();calls = len(self.agent.client.calls);r = self.turn('45')
        self.assertEqual(r.status, 'success_mutated');self.assertEqual(self.ids(), before)
        self.assertEqual(len(self.agent.client.calls), calls);self.assertEqual(self.state().remaining_minutes, 45)

    def test_39_dwell_recognized_not_invalid(self):
        before = self.state().to_dict();r = self.turn('I want to stay here longer.')
        self.assertEqual(r.status, 'needs_duration_clarification');r = self.turn('20')
        self.assertEqual(r.status, 'unsupported_action');self.assertEqual(before, self.state().to_dict())

    def test_40_pace_changes_estimates_not_destinations(self):
        before = self.ids();r = self.act(action('SET_PACE', pace='deep'))
        self.assertEqual(self.ids(), before);self.assertEqual(r.status, 'success_mutated')
        for stop in self.state().get_remaining_stops():
            p = self.agent.repository.get_poi_by_id(stop['poi_id'])
            self.assertEqual(stop['estimated_stay_minutes'], p.visit_profile.stay_for(stop['selected_visit_mode'], 'deep'))

    def test_41_cas_during_mutation_rejects_staged_edit(self):
        before = self.ids();original = self.executor.mutations.build_route
        def race(*args, **kwargs):
            route = original(*args, **kwargs);self.agent.core.update_elapsed_time(self.state().trip_id, 10);return route
        with patch.object(self.executor.mutations, 'build_route', side_effect=race):r = self.turn('Skip this place.')
        self.assertEqual(r.status, 'stale_state_conflict');self.assertEqual(self.ids(), before)
        self.assertEqual(self.state().skipped_poi_ids, []);self.assertEqual(self.state().elapsed_minutes, 10)

    def test_42_trace_opt_in_normal_output_is_clean(self):
        r = self.turn('Skip this place.').to_dict();out = io.StringIO()
        with redirect_stdout(out):AgentResponseRenderer().render(r)
        self.assertNotIn('Raw provider', out.getvalue());self.assertNotIn('state_revision', out.getvalue())
        with redirect_stdout(out):AgentResponseRenderer(trace_nlu=True).render(r)
        self.assertIn('[10] Route diff / warnings', out.getvalue())

    def test_43_missing_raw_target_asks_not_noop(self):
        self.unchanged(action('REMOVE_PLACE'), status='ambiguous_target')

    def test_44_terminal_mutation_rejected(self):
        self.turn("I'm done for today.");self.unchanged(action('ADD_PLACE', target_mentions=['West Bund Museum']), status='not_applicable')

    def test_45_read_with_mutation_is_ambiguous(self):
        self.unchanged(action('SHOW_CURRENT_ROUTE'), action('SKIP_PLACE', target_mentions=['this place']), status='ambiguous_intent')

    def test_46_full_replan_without_authorization_is_ambiguous(self):
        self.unchanged(action('FULL_REPLAN'), status='ambiguous_intent')

    def test_47_invalid_schema_never_writes_state(self):
        before = self.state().to_dict();raw = utterance(action('ADD_PLACE', target_mentions=['Long Museum']));raw['poi_id'] = 'p5'
        self.agent.client.responses = [raw];r = self.turn('structured attack')
        self.assertEqual(r.status, 'invalid_command');self.assertEqual(before, self.state().to_dict())

    def test_48_malformed_provider_bounded_format_repair(self):
        before = self.state().to_dict();calls = len(self.agent.client.calls)
        self.agent.client.responses = ['{', '{'];r = self.turn('unfinished provider document')
        self.assertEqual(r.status, 'parse_error');self.assertEqual(len(self.agent.client.calls)-calls, 2)
        self.assertEqual(r.nlu_trace['failure_stage'], 'schema');self.assertEqual(before, self.state().to_dict())

    def test_49_no_keyword_gating_of_valid_common_remove(self):
        self.agent.client.responses = [utterance(action('REMOVE_PLACE', target_mentions=['this stop']))]
        r = self.turn('This one can go.')
        self.assertEqual(r.status, 'success_mutated');self.assertEqual(r.mutation_result['added_stops'], [])

    def test_50_production_and_original_engine_protected(self):
        self.assertEqual(hashlib.sha256(Path('data/pois.json').read_bytes()).hexdigest(), 'e580f86656255fac52b459b499570c5df1d89e8c12e897026d623b62cea7bcea')
        baseline = json.loads(Path('examples/trip_interaction/protected_before.json').read_text(encoding='utf-8'))
        engine = Path('src/route_engine.py').read_text(encoding='utf-8')
        # Authorized start-POI contract extension; all pre-existing engine code stays frozen.
        start = engine.index('        # A selected Core start')
        end = engine.index('        # Defensive final verification', start)
        original = engine[:start] + engine[end:]
        self.assertIn(baseline['src\\route_engine.py'], [hashlib.sha256(original.encode()).hexdigest(), hashlib.sha256(original.replace('\n','\r\n').encode()).hexdigest()])

    def test_51_more_existing_interest_is_not_a_noop(self):
        before = self.ids();r = self.turn("I'd like more architecture.")
        self.assertEqual(r.status, 'success_mutated');self.assertEqual(len(set(self.ids())-set(before)), 1)
        self.assertEqual([p for p in self.ids() if p in before], before)
        self.assertEqual(r.mutation_result['removed_stops'], [])

    def test_52_three_action_museum_compound_keeps_unrelated_stops(self):
        self.act(action('REMOVE_PLACE', target_mentions=['Long Museum']));self.add()
        self.act(action('MOVE_PLACE_NEXT', target_mentions=['West Bund Museum']))
        before = self.ids();r = self.turn("Skip this museum, add Long Museum, and I'd like more architecture.")
        self.assertEqual(r.status, 'success_mutated');self.assertIn('p28', self.state().skipped_poi_ids)
        self.assertIn('p5', self.ids());self.assertEqual([p for p in self.ids() if p in before], [p for p in before if p != 'p28'])
        self.assertEqual(len(r.trip_turn_result['parsed_command']['actions']), 3)

    def test_53_hard_add_does_not_silently_drop_requested_target(self):
        self.turn('I must finish within one hour.')
        r = self.act(action('ADD_MUST_GO', target_mentions=['Long Museum']))
        self.assertIn(r.status, ('success_mutated', 'state_conflict'))
        if r.status == 'success_mutated':self.assertIn('p5', self.ids())

    def test_54_empty_provider_action_array_does_not_crash(self):
        before = self.state().to_dict();self.agent.client.responses = [dict(actions=[], needs_clarification=False, clarification_reason=None)]
        r = self.turn('Empty protocol array');self.assertEqual(r.status, 'parse_error');self.assertEqual(before, self.state().to_dict())

    def test_55_full_failure_reports_already_committed_local_edit(self):
        from src.trip_replanning import ReplanResult
        pid = self.ids()[0]
        with patch.object(self.agent.conversation.coordinator, 'replan', return_value=ReplanResult('engine_failure')):
            r = self.act(action('SKIP_PLACE', target_mentions=['this place']), action('FULL_REPLAN', explicit_replan=True))
        self.assertEqual(r.status, 'state_conflict');self.assertTrue(r.route_updated)
        self.assertIn(pid, self.state().skipped_poi_ids);self.assertEqual(r.mutation_result['removed_ids'], [pid])
        self.assertIn('was saved', r.user_facing_summary['headline'])

    def test_56_lifecycle_provider_race_is_cas_protected(self):
        original = self.agent.client.structured_parse
        def racing(**kwargs):
            value = original(**kwargs);self.agent.core.update_elapsed_time(self.state().trip_id, 10);return value
        with patch.object(self.agent.client, 'structured_parse', side_effect=racing):r = self.act(action('ABANDON_TRIP'))
        self.assertEqual(r.status, 'stale_state_conflict');self.assertEqual(self.state().status, 'ACTIVE')

    def test_57_complete_skip_compound_reports_both_facts(self):
        r = self.act(action('COMPLETE_STOP', target_mentions=['TANK Shanghai']), action('SKIP_PLACE', target_mentions=['Beipiao Wharf Crane']))
        self.assertEqual(r.status, 'success_mutated');self.assertEqual(len(r.trip_turn_result['core_action_results']), 2)
        self.assertEqual(r.user_facing_summary['completed_stop']['poi_id'], 'p29')
        self.assertEqual(r.mutation_result['removed_ids'], ['p43']);self.assertEqual(self.ids(), ['p5'])

    def test_58_hard_compression_minimizes_visit_mode_changes_before_deletion(self):
        agent = build_agent();sid = agent.create_session().session_id
        intent = agent.entry.parse_plan(FULL_JOURNEY_INITIAL)
        intent.visit_mode_overrides = {'p28': 'full_visit', 'p5': 'full_visit'}
        self.assertEqual(agent.plan_from_intent(sid, intent).status, 'route_ready');agent.handle_turn(sid, 'start')
        agent.client.responses = [utterance(action('ADD_PLACE', target_mentions=['West Bund Museum']))]
        self.assertEqual(agent.handle_turn(sid, 'Include this museum.').status, 'success_mutated')
        trip = agent.trip_store.get(agent.sessions.get(sid).trip_id);mutations = agent.conversation.actions.mutations
        stops = trip.get_remaining_stops();request = mutations.request(trip, trip.current_intent)
        savings = [v.stay_minutes - f.stay_minutes for v in mutations.visits(stops, trip.current_intent)
                   if (f := mutations.engine.visits.budget_fallback(v, request)) is not None]
        self.assertGreaterEqual(len(savings), 2)
        budget = mutations.metrics(trip, stops, trip.current_intent)[3] - max(savings) + .001
        agent.client.responses = [utterance(action('SET_HARD_TIME_LIMIT', time_value_minutes=budget))]
        result = agent.handle_turn(sid, 'Fit the explicit duration.')
        self.assertEqual(result.status, 'success_mutated');after = agent.trip_store.get(trip.trip_id).get_remaining_stops()
        self.assertEqual([s['poi_id'] for s in after], [s['poi_id'] for s in stops])
        self.assertEqual(sum(a['selected_visit_mode'] != b['selected_visit_mode'] for a,b in zip(stops,after)), 1)

    def test_59_read_and_provider_error_preserve_pending_target(self):
        self.act(action('REMOVE_PLACE', target_mentions=['the museum']))
        pending = self.agent.conversation.conversations.get(self.state().trip_id)
        self.assertIsNotNone(pending)
        self.turn('Why did you change my route?')
        self.assertEqual(self.agent.conversation.conversations.get(self.state().trip_id), pending)
        self.turn('Unknown wording without a mock fixture')
        self.assertEqual(self.agent.conversation.conversations.get(self.state().trip_id), pending)


class ActionProtocolTests(unittest.TestCase):
    def setUp(self):self.repository = POIRepository();self.resolver = ActionPOIResolver(self.repository)

    def test_alias_identity_not_fuzzy_threshold_relaxation(self):
        for name, pid in [('West-Bund Museum', 'p28'), ('west bund museum', 'p28'), ('西岸美术馆', 'p28'),
                          ('tank shanghai', 'p29'), ('west bund art centre', 'p36'), ('Long Museum', 'p5')]:
            self.assertEqual(self.resolver.resolve(name).get('poi_id'), pid, name)
        self.assertEqual(self.resolver.resolve('A completely invented place')['status'], 'not_found')

    def test_trace_redacts_provider_credentials(self):
        from src.trip_action_rendering import safe_trace
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'task-secret'}):
            data = safe_trace({'raw': {'Authorization': 'Bearer task-secret', 'system_prompt': 'hidden'}, 'user_text': 'task-secret sk-examplekey'})
        output = json.dumps(data);self.assertNotIn('task-secret', output);self.assertNotIn('hidden', output);self.assertNotIn('Bearer', output)

    def test_harness_does_not_execute_trip_or_route_engine(self):
        with patch('src.route_engine.RouteEngine.generate_route', side_effect=AssertionError('harness planning')), patch('src.trip_store.TripService.create_trip', side_effect=AssertionError('harness trip')):
            report = evaluate(MockLLMClient(fixtures=ACTION_FIXTURES))
        self.assertEqual(report['case_count'], len(ACCEPTANCE_CASES));self.assertEqual(report['passed'], len(ACCEPTANCE_CASES))
        self.assertTrue(report['thresholds_passed'])

    def test_provider_failure_stops_live_eval_without_retrying_all_cases(self):
        class FailedProvider:
            calls = 0
            def structured_parse(self, **kwargs):self.calls += 1;raise LLMClientError('Unavailable')
        client = FailedProvider();report = evaluate(client)
        self.assertEqual(client.calls, 1);self.assertFalse(report['thresholds_passed']);self.assertEqual(report['cases'][1]['status'], 'NOT_RUN')

    def test_relative_refs_use_visible_remaining_sequence(self):
        agent = build_agent();sid = agent.create_session().session_id
        agent.handle_turn(sid, FULL_JOURNEY_INITIAL);agent.handle_turn(sid, 'start')
        trip = agent.trip_store.get(agent.sessions.get(sid).trip_id)
        self.assertEqual(self.resolver.resolve('the second stop', trip)['poi_id'], trip.remaining_poi_ids[1])
        self.assertEqual(self.resolver.resolve('the final stop', trip)['poi_id'], trip.remaining_poi_ids[-1])
        self.assertEqual(self.resolver.resolve('next stop', trip)['poi_id'], trip.current_poi_id)

    def test_missing_target_confirmation_consumes_slot_without_provider(self):
        agent = build_agent();sid = agent.create_session().session_id
        agent.handle_turn(sid, FULL_JOURNEY_INITIAL);agent.handle_turn(sid, 'start')
        agent.client.responses = [utterance(action('REMOVE_PLACE'))]
        result = agent.handle_turn(sid, 'Leave one destination out.');self.assertEqual(result.status, 'ambiguous_target')
        calls = len(agent.client.calls);result = agent.handle_turn(sid, 'Beipiao Wharf Crane')
        self.assertEqual(result.status, 'success_mutated');self.assertEqual(len(agent.client.calls), calls)


def corpus_test(category):
    def run(self):
        parser = TripActionParser(self.repository, MockLLMClient(fixtures=ACTION_FIXTURES))
        for case in [c for c in ACCEPTANCE_CASES if c['category'] == category]:
            with self.subTest(text=case['text']):
                result = parser.parse(case['text'], CONTEXT).to_dict()
                self.assertEqual(signature(result, self.resolver), signature(case['expected'], self.resolver))
                self.assertEqual(parser.last_trace['semantic_validation'], 'passed')
    return run


for category in sorted({c['category'] for c in ACCEPTANCE_CASES}):
    setattr(ActionProtocolTests, 'test_corpus_' + category.lower(), corpus_test(category))


if __name__ == '__main__':unittest.main()
