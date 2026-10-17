import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.trip_semantics_fixture import build_agent
from tools.demos.trip_agent_demo import full_journey
from src.intent_models import RouteIntent, RouteMode
from src.llm_client import DeepSeekLLMClient, MockLLMClient
from src.trip_agent import TripAgentService, InMemoryTripAgentSessionStore, TripAgentSession
from src.trip_agent_fixtures import AGENT_FIXTURES, FULL_JOURNEY_INITIAL, INITIAL_EXAMPLE, INITIAL_CLARIFICATION
from src.trip_state import TripState, TripStateError


class TripAgentTests(unittest.TestCase):
    def setUp(self):
        self.agent = build_agent();self.sid = self.agent.create_session(session_id='integration').session_id

    def turn(self, text):return self.agent.handle_turn(self.sid, text)
    def state(self):return self.agent.trip_store.get(self.agent.sessions.get(self.sid).trip_id)
    def ready(self):
        r = self.turn(FULL_JOURNEY_INITIAL);self.assertEqual(r.status, 'route_ready', r.to_dict());return r
    def active(self):self.ready();self.turn('start')
    def progress(self):self.active();self.turn("I've finished this stop.")
    def unchanged(self, text, status=None):
        before = self.state().to_dict();result = self.turn(text)
        if status:self.assertEqual(result.status, status, result.to_dict())
        self.assertEqual(before, self.state().to_dict());return result

    def test_01_initial_real_engine_authority(self):
        with patch.object(self.agent.entry.engine, 'generate_route', wraps=self.agent.entry.engine.generate_route) as engine:
            r = self.ready();self.assertGreater(engine.call_count, 0)
        self.assertEqual(r.session_phase, 'ROUTE_READY');self.assertEqual(self.state().status, 'PLANNED')
        self.assertEqual(r.route, self.state().original_route);self.assertEqual(len(self.state().route_versions), 1)

    def test_02_required_initial_example(self):
        self.assertEqual(self.turn(INITIAL_EXAMPLE).status, 'route_ready')

    def test_03_compound_initial_clarification(self):
        self.assertEqual(self.turn('I want to explore Shanghai.').session_phase, 'AWAITING_INITIAL_CLARIFICATION')
        self.assertIsNone(self.agent.sessions.get(self.sid).trip_id)
        r = self.turn(INITIAL_CLARIFICATION);self.assertEqual(r.status, 'route_ready', r.to_dict())
        self.assertEqual(self.state().original_minutes, 180)
        self.assertIn('local_life', self.state().original_intent['interest_tags'])
        self.assertEqual([c['user_text'] for c in self.agent.client.calls], ['I want to explore Shanghai.', INITIAL_CLARIFICATION])

    def test_04_cancel_initial_without_trip(self):
        self.turn('I want to explore Shanghai.');r = self.turn('cancel')
        self.assertEqual(r.session_phase, 'NEW');self.assertIsNone(r.trip_id)
        self.assertEqual(self.agent.trip_store._snapshots, {})

    def test_05_provider_initial_failure_retry(self):
        self.assertEqual(self.turn('unlisted initial input').status, 'provider_error')
        self.assertEqual(self.agent.trip_store._snapshots, {});self.ready()

    def test_06_blank_input_no_provider(self):
        self.assertEqual(self.turn(' ').status, 'invalid_input');self.assertEqual(self.agent.client.calls, [])

    def test_07_bridge_idempotent_same_snapshot(self):
        result = self.agent.entry.generate(self.agent.entry.parse_plan(FULL_JOURNEY_INITIAL))
        a = self.agent.accept_initial_result(self.sid, result);before = self.state().to_dict()
        b = self.agent.accept_initial_result(self.sid, result)
        self.assertEqual(a.trip_id, b.trip_id);self.assertEqual(before, self.state().to_dict())
        self.assertEqual(len(self.agent.trip_store._snapshots), 1)

    def test_08_unsuccessful_initial_never_creates_trip(self):
        intent = RouteIntent(RouteMode.PLAN_FOR_ME, available_minutes=1, interest_tags=['architecture'])
        r = self.agent.plan_from_intent(self.sid, intent)
        self.assertNotEqual(r.status, 'route_ready');self.assertIsNone(r.trip_id)

    def test_09_ready_read_and_preference_rejection(self):
        self.ready();self.unchanged('show route', 'success_query')
        self.unchanged('Actually, I only have two hours now.', 'not_applicable')
        self.assertEqual(self.state().status, 'PLANNED')

    def test_10_planned_complete_rejected(self):
        self.ready();self.unchanged("I've finished this stop.", 'not_applicable')

    def test_11_planned_cancel_replays_no_start(self):
        self.ready();r = self.turn('cancel');self.assertEqual(r.session_phase, 'ABANDONED')
        state = self.state();self.assertNotIn('trip_started', [e['event_type'] for e in state.event_history])
        self.assertEqual(TripState.from_dict(state.to_dict()).to_dict(), state.to_dict())
        self.unchanged('start', 'invalid_state')

    def test_12_start_and_repeat_preserve_progress(self):
        self.progress();self.agent.core.update_elapsed_time(self.state().trip_id, 10)
        self.unchanged('start', 'no_change')

    def test_13_complete_payload(self):
        self.active();pid = self.state().current_poi_id;r = self.turn("I've finished this stop.")
        self.assertEqual(r.user_facing_summary['completed_stop']['poi_id'], pid)
        self.assertEqual(r.user_facing_summary['remaining_count'], len(self.state().remaining_poi_ids))
        self.assertEqual(r.user_facing_summary['next_stop']['poi_id'], self.state().current_poi_id)

    def test_14_skip_and_replan_contract(self):
        self.progress();pid = self.state().current_poi_id;r = self.turn('Skip this place.')
        self.assertTrue(r.route_updated, r.to_dict());self.assertIn(pid, self.state().skipped_poi_ids)
        self.assertEqual(r.route_change['new_version'], 'v2');self.assertEqual(r.route, self.state().active_route)

    def test_15_full_same_session_v123_completion(self):
        trace = full_journey();trip = trace['final_trip']
        self.assertEqual(trip['status'], 'COMPLETED');self.assertEqual(trace['final_session']['session_phase'], 'COMPLETED')
        self.assertEqual([v['version_id'] for v in trip['route_versions']], ['v1', 'v2'])
        time_turn = next(t for t in trace['turns'] if t['user_text'] == 'I only have one hour left.')
        self.assertEqual(time_turn['result']['status'], 'state_conflict')
        self.assertGreater(time_turn['result']['nlu_trace']['conflict_diagnostics']['minimum_feasible_minutes'], 60)
        self.assertEqual({t['result']['session_id'] for t in trace['turns']}, {trace['session_id']})
        self.assertEqual({t['result']['trip_id'] for t in trace['turns']}, {trace['trip_id']})
        self.assertEqual(trip['original_route'], trace['turns'][0]['result']['route'])

    def test_16_history_original_why_readonly(self):
        self.progress();self.turn('Skip this place.');self.turn('I only have one hour left.')
        for text in ('Why did you change my route?', 'What changes have been made to my route?', 'Show me my original route.', 'show route'):
            with patch.object(self.agent.entry.engine, 'generate_route', side_effect=AssertionError('query engine')):
                self.unchanged(text, 'success_query')
        self.assertEqual(self.turn('show original route').route, self.state().original_route)

    def test_17_terminal_completed_readonly(self):
        self.active()
        while self.state().status == 'ACTIVE':self.turn("I've finished this stop.")
        for text in ('summary', 'show original route', 'show final route', 'show history'):
            r = self.unchanged(text, 'success_query');self.assertIsNotNone(r.trip_summary)
        self.unchanged('start', 'invalid_state');self.unchanged('I only have one hour left.', 'not_applicable')

    def test_18_abandon_remaining_undisposed(self):
        self.progress();before = self.state();r = self.turn("I'm done for today.")
        self.assertEqual(r.session_phase, 'ABANDONED');self.assertEqual(before.remaining_poi_ids, self.state().remaining_poi_ids)
        self.assertEqual(before.visited_poi_ids, self.state().visited_poi_ids)
        self.unchanged('show history', 'success_query');self.unchanged('Skip this place.', 'not_applicable')

    def test_19_trip_clarification_separate_cancel(self):
        self.active();r = self.unchanged('I want to visit the old residence.', 'ambiguous_target')
        self.assertEqual(r.session_phase, 'AWAITING_TRIP_CLARIFICATION')
        self.assertIsNone(self.agent.sessions.get(self.sid).pending_initial_clarification)
        self.assertEqual(self.unchanged('cancel', 'cancelled').session_phase, 'ACTIVE_TRIP')

    def test_20_stale_pending_does_not_commit(self):
        self.active();self.turn('I want to visit the old residence.')
        self.agent.core.update_elapsed_time(self.state().trip_id, 10)
        r = self.unchanged('1', 'stale_state_conflict');self.assertEqual(r.session_phase, 'ACTIVE_TRIP')

    def test_21_provider_trip_failure_unchanged(self):
        self.active();self.unchanged('unlisted trip wording', 'provider_error')

    def test_22_compound_and_must_go(self):
        self.progress()
        before = self.state().to_dict()
        r = self.turn("I'm a little tired, I only have one hour left, and I don't want to visit museums anymore.")
        self.assertEqual(r.status, 'state_conflict', r.status)
        self.assertGreater(r.nlu_trace['conflict_diagnostics']['minimum_feasible_minutes'], 60)
        self.assertEqual(self.state().to_dict(), before)

    def test_23_same_zone_must_go(self):
        self.progress();r = self.turn('I really want to visit West Bund Art Center.')
        self.assertEqual(r.status, 'success_mutated', r.status)
        self.assertIn('p36', self.state().must_go_remaining)

    def test_24_all_three_modes_real_entry_lifecycle(self):
        for mode in RouteMode:
            with self.subTest(mode=mode):
                a = build_agent();sid = a.create_session().session_id
                if mode == RouteMode.PLAN_FOR_ME:r = a.handle_turn(sid, FULL_JOURNEY_INITIAL)
                else:
                    intent = RouteIntent(mode, start_location_text='West Bund', available_minutes=180, preferred_zone='west_bund',
                                         must_go_poi_ids=['p29', 'p38', 'p42'] if mode == RouteMode.PLACES_IN_MIND else [], surprise_seed=42)
                    r = a.plan_from_intent(sid, intent)
                self.assertEqual(r.status, 'route_ready', r.to_dict());a.handle_turn(sid, 'start')
                self.assertEqual(a.handle_turn(sid, "I've finished this stop.").status, 'success_core_action')
                self.assertEqual(a.handle_turn(sid, 'Actually, I only have two hours now.').status, 'success_mutated')
                self.assertEqual(a.handle_turn(sid, 'show original route').route, a.trip_store.get(r.trip_id).original_route)

    def test_25_session_store_copy_isolation_crud(self):
        store = InMemoryTripAgentSessionStore();s = TripAgentSession('isolation');store.create(s)
        s.planning_context['bad'] = True;self.assertEqual(store.get(s.session_id).planning_context, {})
        loaded = store.get(s.session_id);loaded.planning_context['saved'] = True;store.save(loaded)
        loaded.planning_context.clear();self.assertEqual(store.get(s.session_id).planning_context, {'saved': True})
        store.delete(s.session_id)
        with self.assertRaises(KeyError):store.get(s.session_id)

    def test_26_live_missing_key_no_network(self):
        a = build_agent(live=True);sid = a.create_session().session_id
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': ''}), patch('urllib.request.urlopen', side_effect=AssertionError('network')):
            r = a.handle_turn(sid, INITIAL_EXAMPLE)
        self.assertEqual(r.status, 'provider_error');self.assertEqual(r.error_code, 'configuration_error')
        self.assertEqual(a.trip_store._snapshots, {})

    def test_27_cli_scenario_json(self):
        proc = subprocess.run([sys.executable, 'tools/demos/trip_agent_demo.py', '--mock', '--scenario', 'full_journey', '--json'], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['final_trip']['status'], 'COMPLETED')

    def test_28_production58_calibrated_frozen(self):
        self.assertEqual(hashlib.sha256(Path('data/pois.json').read_bytes()).hexdigest(), 'e580f86656255fac52b459b499570c5df1d89e8c12e897026d623b62cea7bcea')

    def test_29_fresh_store_each_turn(self):
        self.active();self.agent.core.complete_stop(self.state().trip_id, self.state().current_poi_id)
        r = self.turn('show route');self.assertEqual(r.progress['visited_count'], 1)

    def test_30_cas_during_provider(self):
        self.active();original = self.agent.client.structured_parse
        def racing(**kwargs):
            value = original(**kwargs);self.agent.core.update_elapsed_time(self.state().trip_id, 10);return value
        with patch.object(self.agent.client, 'structured_parse', side_effect=racing):
            r = self.turn("I've finished this stop.")
        self.assertEqual(r.status, 'stale_state_conflict');self.assertEqual(self.state().visited_poi_ids, [])

    def test_31_initial_quality_clarification_declined(self):
        intent = RouteIntent(RouteMode.PLAN_FOR_ME, available_minutes=180, preferred_zone='west_bund', interest_tags=['literature'], avoid_tags=['museum_visit'])
        r = self.agent.plan_from_intent(self.sid, intent)
        self.assertEqual(r.session_phase, 'AWAITING_INITIAL_CLARIFICATION');self.assertIsNone(r.trip_id)
        self.assertEqual(self.agent.sessions.get(self.sid).pending_initial_clarification['kind'], 'route_quality')
        calls = len(self.agent.client.calls);r = self.turn('strict')
        self.assertEqual(r.status, 'insufficient_route');self.assertIsNone(r.trip_id)
        self.assertEqual(calls, len(self.agent.client.calls))

    def test_32_trip_clarification_named_choice_no_provider(self):
        self.active();r = self.turn('I want to visit the old residence.')
        choice = r.clarification['options'][1]['name'];calls = len(self.agent.client.calls)
        result = self.turn(choice)
        self.assertIn(result.status, ('success_mutated', 'state_conflict'))
        self.assertEqual(calls, len(self.agent.client.calls));self.assertEqual(result.session_phase, 'ACTIVE_TRIP')
        self.assertIsNone(self.agent.conversation.conversations.get(self.state().trip_id))

    def test_33_soft_time_keeps_remaining_route(self):
        self.turn(INITIAL_EXAMPLE);self.turn('start');self.turn("I've finished this stop.")
        self.turn('Skip this place.')
        before = self.state().remaining_poi_ids
        r = self.turn("I'd like to spend about another hour, but there's no rush.")
        self.assertEqual(r.status, 'success_mutated');self.assertEqual(before, self.state().remaining_poi_ids)
        self.assertIsNotNone(r.mutation_result['time_warning'])

    def test_34_skip_and_soft_time_retains_other_stops(self):
        self.active();pid = self.state().current_poi_id
        r = self.turn('Skip this place, and I only have 45 minutes left.')
        self.assertEqual(r.status, 'success_mutated');self.assertIn(pid, self.state().skipped_poi_ids)
        self.assertEqual(r.mutation_result['added_stops'], [])
        self.assertEqual(self.state().remaining_minutes, 45);self.assertEqual(len(self.state().route_versions), 2)

    def test_35_cli_explicit_auto_start(self):
        proc = subprocess.run([sys.executable, 'tools/demos/trip_agent_demo.py', '--mock', '--auto-start', '--json'],
                              input=FULL_JOURNEY_INITIAL + '\nquit\n', capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        results = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual([r['trip_status'] for r in results], ['PLANNED', 'ACTIVE'])


if __name__ == '__main__':unittest.main()
