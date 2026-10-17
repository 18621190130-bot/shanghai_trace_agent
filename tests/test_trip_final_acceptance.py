"""Final time semantics and factual conflict diagnostics; offline only."""
import ast
import copy
import hashlib
import io
import itertools
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tests.trip_semantics_fixture import build_agent
from tools.demos.trip_agent_demo import AgentResponseRenderer
from src.trip_agent_fixtures import FULL_JOURNEY_INITIAL
from src.trip_action_fixtures import ACTION_FIXTURES, action, utterance
from src.trip_actions import TripActionParser, PROMPT
from src.llm_client import MockLLMClient
from src.poi_repository import POIRepository
from src.trip_action_rendering import render_nlu_trace


class FinalTimeTests(unittest.TestCase):
    def setUp(self):
        self.agent = build_agent();self.sid = self.agent.create_session().session_id
        self.agent.handle_turn(self.sid, FULL_JOURNEY_INITIAL);self.agent.handle_turn(self.sid, 'start')
        self.mutations = self.agent.conversation.actions.mutations

    def state(self):return self.agent.trip_store.get(self.agent.sessions.get(self.sid).trip_id)
    def act(self, *actions):
        self.agent.client.responses = [utterance(*actions)]
        return self.agent.handle_turn(self.sid, 'A supplied offline semantic proposal.')

    def test_remaining_limit_compresses_ordinary_stops(self):
        before = self.state().remaining_poi_ids
        result = self.agent.handle_turn(self.sid, 'I only have one hour left.')
        self.assertEqual(result.status, 'success_mutated')
        self.assertEqual(self.state().time_constraint_mode, 'hard')
        self.assertEqual(result.mutation_result['hard_limit_minutes'], 60)
        self.assertLessEqual(self.state().active_route['total_estimated_minutes'], 60)
        self.assertTrue(set(self.state().remaining_poi_ids) < set(before))
        self.assertEqual(result.mutation_result['added_stops'], [])

    def test_soft_no_rush_preserves_all_stops(self):
        before = self.state().remaining_poi_ids
        result = self.agent.handle_turn(self.sid, "I'd like to spend about another hour, but there's no rush.")
        self.assertEqual(result.status, 'success_mutated');self.assertEqual(self.state().remaining_poi_ids, before)
        self.assertEqual(result.mutation_result['time_constraint_mode'], 'soft')
        self.assertGreater(result.mutation_result['time_warning']['estimated_overrun_minutes'], 0)

    def test_initial_target_and_adding_overrun_do_not_create_hard_limit(self):
        self.assertEqual(self.state().original_intent['available_minutes'], 180)
        before = self.state().remaining_poi_ids
        result = self.act(action('ADD_PLACE', target_mentions=['West Bund Museum']))
        self.assertEqual(result.status, 'success_mutated')
        self.assertEqual([p for p in self.state().remaining_poi_ids if p in before], before)
        self.assertGreater(result.mutation_result['estimated_minutes'], 180)
        self.assertIsNotNone(result.mutation_result['time_warning'])
        self.assertIsNone(result.mutation_result['hard_limit_minutes'])

    def test_skip_and_remove_never_refill(self):
        before = self.state().remaining_poi_ids
        with patch.object(self.agent.conversation.coordinator, 'replan', side_effect=AssertionError('refill')):
            skipped = self.act(action('SKIP_PLACE', target_mentions=['this place']))
            removed = self.act(action('REMOVE_PLACE', target_mentions=['Long Museum']))
        self.assertEqual(self.state().remaining_poi_ids, [p for p in before if p not in ('p29', 'p5')])
        self.assertEqual(skipped.mutation_result['added_stops'], []);self.assertEqual(removed.mutation_result['added_stops'], [])

    def test_must_go_conflict_is_atomic_and_identifies_real_blocker(self):
        self.act(action('ADD_MUST_GO', target_mentions=['Long Museum']))
        before = self.state().to_dict()
        result = self.act(action('SET_HARD_TIME_LIMIT', time_value_minutes=20))
        self.assertEqual(result.status, 'state_conflict');self.assertEqual(self.state().to_dict(), before)
        d = result.nlu_trace['conflict_diagnostics']
        self.assertEqual(d['reason_code'], 'must_go_exceeds_limit');self.assertEqual(d['hard_limit_minutes'], 20)
        self.assertGreater(d['minimum_feasible_minutes'], 20)
        self.assertEqual([(s['poi_id'], s['protection_reason']) for s in d['protected_stops']], [('p5', 'must_go')])
        self.assertEqual({s['poi_id'] for s in d['removable_stops']}, {'p29', 'p43'})
        self.assertEqual(d, result.user_facing_summary['conflict_diagnostics'])

    def test_ordinary_30_minute_conflict_reports_exact_native_minimum(self):
        before = self.state().to_dict();result = self.act(action('SET_HARD_TIME_LIMIT', time_value_minutes=30))
        self.assertEqual(result.status, 'state_conflict');self.assertEqual(before, self.state().to_dict())
        d = result.nlu_trace['conflict_diagnostics']
        self.assertEqual(d['protected_stops'], []);self.assertEqual(len(d['removable_stops']), 3)
        self.assertEqual(d['reason_code'], 'minimum_route_exceeds_limit')
        self.assertAlmostEqual(d['minimum_feasible_minutes'], 40);self.assertGreater(d['minimum_feasible_minutes'], 30)

    def test_current_logical_stop_is_not_implicitly_protected(self):
        trip = self.state();d = self.mutations.hard_conflict_diagnostics(trip, trip.get_remaining_stops(), trip.current_intent, 20)
        self.assertIn(trip.current_poi_id, [s['poi_id'] for s in d['removable_stops']]);self.assertEqual(d['protected_stops'], [])

    def test_explicit_add_same_turn_conflict_has_distinct_protection_reason(self):
        before = self.state().to_dict()
        result = self.act(action('ADD_PLACE', target_mentions=['West Bund Museum']), action('SET_HARD_TIME_LIMIT', time_value_minutes=1))
        self.assertEqual(result.status, 'state_conflict');self.assertEqual(before, self.state().to_dict())
        d = result.nlu_trace['conflict_diagnostics'];self.assertEqual(d['reason_code'], 'protected_stops_exceed_limit')
        self.assertEqual([(s['poi_id'], s['protection_reason']) for s in d['protected_stops']], [('p28', 'explicitly_added_this_turn')])

    def test_diagnostic_minimum_matches_exhaustive_existing_modes_and_subsets(self):
        trip = self.state();stops = trip.get_remaining_stops();intent = trip.current_intent
        self.act(action('ADD_MUST_GO', target_mentions=['Long Museum']))
        trip = self.state();intent = trip.current_intent;request = self.mutations.request(trip, intent)
        estimates = []
        for n in range(1, len(stops)+1):
            for subset in itertools.combinations(stops, n):
                if not set(intent['must_go_poi_ids']) <= {s['poi_id'] for s in subset}:continue
                options = []
                for stop, visit in zip(subset, self.mutations.visits(subset, intent)):
                    alternative = self.mutations.engine.visits.budget_fallback(visit, request)
                    options.append([stop['selected_visit_mode']] + ([alternative.selected_visit_mode] if alternative else []))
                for modes in itertools.product(*options):
                    trial = copy.deepcopy(subset)
                    for stop, mode in zip(trial, modes):stop['selected_visit_mode'] = mode
                    estimates.append(self.mutations.metrics(trip, trial, intent)[3])
        d = self.mutations.hard_conflict_diagnostics(trip, stops, intent, 1)
        self.assertAlmostEqual(d['minimum_feasible_minutes'], min(estimates))

    def test_shared_trace_adds_stage_11_only_on_conflict(self):
        result = self.act(action('SET_HARD_TIME_LIMIT', time_value_minutes=1))
        stream = io.StringIO()
        with redirect_stdout(stream):render_nlu_trace(result.nlu_trace)
        text = stream.getvalue();self.assertIn('[11] Conflict diagnostics:', text)
        for field in ('hard_limit_minutes', 'minimum_feasible_minutes', 'protected_stops', 'removable_stops', 'blocking_reason'):
            self.assertIn(field, text)

    def test_normal_renderer_explains_time_and_names_without_internal_diagnostics(self):
        self.act(action('ADD_MUST_GO', target_mentions=['Long Museum']))
        result = self.act(action('SET_HARD_TIME_LIMIT', time_value_minutes=20))
        stream = io.StringIO()
        with redirect_stdout(stream):AgentResponseRenderer().render(result.to_dict())
        text = stream.getvalue();self.assertIn('Long Museum', text);self.assertIn('must-go', text)
        self.assertIn('20 minutes', text);self.assertIn('shortest feasible', text)
        self.assertNotIn('poi_id', text);self.assertNotIn('protected_stops', text)

    def test_compression_algorithm_ast_is_unchanged(self):
        tree = ast.parse(Path('src/route_mutation.py').read_text(encoding='utf-8'))
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'compress')
        self.assertEqual(ast.dump(node, include_attributes=False), Path('examples/trip_final_acceptance/compression_before.txt').read_text(encoding='utf-8'))

    def test_production_hash_unchanged(self):
        self.assertEqual(hashlib.sha256(Path('data/pois.json').read_bytes()).hexdigest(), 'e580f86656255fac52b459b499570c5df1d89e8c12e897026d623b62cea7bcea')


class TimeLanguageProtocolTests(unittest.TestCase):
    def assert_intent(self, text, kind, minutes):
        parser = TripActionParser(POIRepository(), MockLLMClient(fixtures=ACTION_FIXTURES))
        result = parser.parse(text, {}).actions[0]
        self.assertEqual(result.action_type, kind);self.assertEqual(result.time_value_minutes, minutes)
        self.assertEqual(result.time_constraint_mode, 'hard' if kind == 'SET_HARD_TIME_LIMIT' else 'soft')


def language_case(text, kind, minutes):
    def test(self):self.assert_intent(text, kind, minutes)
    return test


for i, (text, minutes) in enumerate([
    ('I only have one hour left.', 60), ('I have one hour left.', 60), ("I've only got 45 minutes left.", 45),
    ('I have another 30 minutes before I need to go.', 30), ('I can only stay another hour.', 60),
    ('我只剩一个小时了。', 60), ('我还有四十分钟就要走了。', 40), ('最多只能再逛半小时。', 30),
]):
    setattr(TimeLanguageProtocolTests, f'test_hard_remaining_{i+1}', language_case(text, 'SET_HARD_TIME_LIMIT', minutes))
for i, text in enumerate(["I'd like to spend about another hour.", "Let's aim for around one hour.",
                         "Maybe another hour, but there's no rush.", '我想再逛大概一个小时。', '最好控制在一小时左右，不过不用赶。']):
    setattr(TimeLanguageProtocolTests, f'test_soft_duration_{i+1}', language_case(text, 'SET_TIME_TARGET', 60))


if __name__ == '__main__':unittest.main()
