from .helpers import baseline_repository, PRE_PHASE2_5_PATH
import contextlib
import copy
import io
import json
import unittest
from unittest.mock import patch

from tools.demos.route_entry_demo import main, render_result
from src import POIRepository, RouteEngine, RouteRequest, RouteEntryService, RouteIntent, RouteMode
from src.intent_schema import route_intent_schema, validate_json
from src.llm_client import MockLLMClient
from src.mock_examples import candidate
from src.models import RequestValidationError
from src.route_quality import needs_route_quality_clarification
from .helpers import subset, write_repository


class FinalRepairTests(unittest.TestCase):
    def setUp(self):
        self.repo = baseline_repository()
        self.service = RouteEntryService(self.repo)

    def sparse_service(self):
        raw = self.repo.get_raw_data()
        pois = [p for p in raw['pois'] if p['id'] == 'p2']
        return RouteEntryService(write_repository(self, subset(raw, pois)))

    def sparse_intent(self):
        return RouteIntent(RouteMode.PLAN_FOR_ME, available_minutes=180,
                           interest_tags=['local_life'], experience_tags=['local_atmosphere'])

    def test_core_interest_survives_missing_supporting_preferences(self):
        intent = self.sparse_intent()
        result = self.service.generate(intent)
        self.assertEqual(result.status, 'success')
        self.assertEqual({p.poi_id for p in result.route_plan.ordered_pois}, {'p2', 'p11', 'p12'})
        self.assertEqual(result.route_quality.status, 'passed')
        self.assertEqual(result.intent.experience_tags, ['local_atmosphere'])
        for pid in ('p11', 'p12'):
            self.assertNotIn('local_atmosphere', self.repo.get_poi_by_id(pid).experience_tags)

    def test_multiple_supporting_bonuses_do_not_veto_core_match(self):
        intent = self.sparse_intent()
        intent.experience_tags = ['local_atmosphere', 'street_scene', 'social_observation']
        intent.culture_tags = ['public_life']
        result = self.service.generate(intent)
        self.assertEqual(result.status, 'success')
        self.assertTrue({'p11', 'p12'}.issubset({p.poi_id for p in result.route_plan.ordered_pois}))

    def test_weak_far_candidate_still_rejected(self):
        result = self.service.generate(self.sparse_intent())
        self.assertNotIn('p33', [p.poi_id for p in result.route_plan.ordered_pois])
        self.assertLess(result.route_plan.estimated_max_single_leg_km, 1)

    def test_nineteen_percent_route_requires_quality_clarification(self):
        result = self.sparse_service().generate(self.sparse_intent())
        self.assertEqual(result.status, 'needs_route_quality_clarification')
        self.assertEqual(result.route_plan.status, 'success')
        self.assertFalse(result.intent.needs_clarification)
        self.assertEqual(result.intent.missing_fields, [])
        self.assertAlmostEqual(result.route_plan.time_utilization_ratio, 35/180)
        self.assertIn('insufficient_viable_stops', result.route_quality.reasons)
        self.assertEqual(result.route_quality.candidate_availability['eligible_same_zone'], 1)

    def test_fifty_two_percent_three_stops_do_not_prompt(self):
        result = self.service.generate(RouteIntent(RouteMode.PLAN_FOR_ME, available_minutes=150,
            interest_tags=['local_life'], experience_tags=['neighborhood_walk'], avoid_tags=['museum_visit']))
        self.assertEqual(result.status, 'success')
        self.assertEqual(result.route_quality.status, 'passed')
        self.assertAlmostEqual(result.route_plan.time_utilization_ratio, .5217565318166824)
        self.assertNotIn('p33', [p.poi_id for p in result.route_plan.ordered_pois])
        self.assertTrue(all('museum_visit' not in self.repo.get_poi_by_id(p.poi_id).experience_tags
                            for p in result.route_plan.ordered_pois))

    def test_sixty_five_percent_three_stops_do_not_prompt(self):
        result = self.service.generate(RouteIntent(RouteMode.PLAN_FOR_ME, available_minutes=120,
            interest_tags=['architecture', 'local_life']))
        self.assertEqual(result.status, 'success')
        self.assertEqual(len(result.route_plan.ordered_pois), 3)
        self.assertEqual(result.route_quality.status, 'passed')

    def test_short_budget_still_requires_three_city_walk_anchors(self):
        intent = self.sparse_intent()
        intent.available_minutes = 90
        result = self.sparse_service().generate(intent)
        self.assertEqual(result.status, 'needs_route_quality_clarification')
        self.assertEqual(result.route_quality.status, 'clarification_required')

    def test_single_long_visit_is_not_a_complete_city_walk(self):
        intent = self.sparse_intent()
        plan = RouteEngine(self.repo).generate_route(RouteRequest(180, must_go_poi_ids=['p2']))
        plan.ordered_pois = plan.ordered_pois[:1]
        plan.remaining_minutes = 15
        plan.time_utilization_ratio = 165/180
        self.assertTrue(needs_route_quality_clarification(intent, plan, {'eligible_same_zone': 5}))

    def test_keep_strict_preserves_intent_and_does_not_replan(self):
        service = self.sparse_service()
        initial = service.generate(self.sparse_intent())
        before = copy.deepcopy(initial.intent.to_dict())
        with patch.object(service.engine, 'generate_route', wraps=service.engine.generate_route) as planner:
            final = service.answer_route_quality_clarification(initial, 'strict')
        self.assertEqual(final.status, 'insufficient_route')
        self.assertEqual(final.intent.to_dict(), before)
        self.assertEqual(planner.call_count, 0)
        self.assertEqual(final.route_quality.preference_broadening, 'declined')
        self.assertTrue(final.route_quality.clarification_applied)
        self.assertTrue(any('intentionally short' in w for w in final.warnings))
        self.assertFalse(initial.route_quality.clarification_applied)

    def test_broadening_merges_all_state_and_replans_once(self):
        raw = self.repo.get_raw_data()
        service = RouteEntryService(write_repository(self, subset(raw, [p for p in raw['pois'] if p['id'] in ('p2', 'p13')])))
        intent = self.sparse_intent()
        intent.avoid_tags = ['museum_visit']
        intent.avoid_poi_ids = ['p2']
        intent.must_go_poi_ids = ['p2']
        intent.travel_pace = 'quick'
        intent.preferred_zone = 'wukang_fuxing_xujiahui'
        intent.max_walking_km = 4
        intent.start_lat, intent.start_lng = 31.2128, 121.4592
        intent.visit_mode_overrides = {'p2': 'walk_stop'}
        initial = service.generate(intent)
        with patch.object(service.engine, 'generate_route', wraps=service.engine.generate_route) as planner:
            final = service.answer_route_quality_clarification(initial, 'Add historic architecture')
        self.assertEqual(planner.call_count, 1)
        self.assertEqual(final.status, 'insufficient_route')
        self.assertEqual(final.intent.interest_tags, ['local_life', 'architecture'])
        for field in ('experience_tags', 'culture_tags', 'available_minutes', 'travel_pace', 'preferred_zone',
                      'max_walking_km', 'start_lat', 'start_lng', 'must_go_poi_ids', 'avoid_tags', 'avoid_poi_ids',
                      'visit_mode_overrides'):
            self.assertEqual(getattr(final.intent, field), getattr(initial.intent, field))
        validate_json(final.intent.to_dict(), route_intent_schema(service.repo))

    def test_no_second_quality_question_even_if_replan_remains_sparse(self):
        service = self.sparse_service()
        final = service.answer_route_quality_clarification(service.generate(self.sparse_intent()), '2')
        self.assertEqual(len(final.route_plan.ordered_pois), 1)
        self.assertEqual(final.status, 'insufficient_route')
        self.assertEqual(final.route_quality.options, [])
        self.assertIsNone(final.route_quality.question)
        with self.assertRaises(RequestValidationError):
            service.answer_route_quality_clarification(final, '2')

    def test_broadening_can_recover_real_additional_candidates(self):
        service = self.service
        # Inject only the anomalous first plan; re-planning uses the real inventory.
        poor_plan = self.sparse_service().generate(self.sparse_intent()).route_plan
        with patch.object(service.engine, 'generate_route', return_value=poor_plan):
            pending = service.generate(self.sparse_intent())
        self.assertEqual(len(pending.route_plan.ordered_pois), 1)
        self.assertEqual(pending.status, 'needs_route_quality_clarification')
        final = service.answer_route_quality_clarification(pending, 'architecture')
        self.assertEqual(final.status, 'success')
        self.assertGreaterEqual(len(final.route_plan.ordered_pois), 3)
        self.assertEqual(final.intent.interest_tags, ['local_life', 'architecture'])
        self.assertEqual(final.route_quality.actual_stops, len(final.route_plan.ordered_pois))

    def test_negative_tag_conflicts_are_not_offered_as_broadening(self):
        intent = self.sparse_intent()
        intent.avoid_tags = ['architecture', 'history']
        # p2 has architecture; explicit must-go retains it despite the negative tag.
        intent.must_go_poi_ids = ['p2']
        service = self.sparse_service()
        result = service.generate(intent)
        values = [o.value for o in result.route_quality.options]
        self.assertNotIn('architecture', values)
        self.assertNotIn('history', values)
        final = service.answer_route_quality_clarification(result, 'strict')
        self.assertEqual(final.intent.avoid_tags, intent.avoid_tags)

    def test_invalid_answer_keeps_pending_result(self):
        service = self.sparse_service()
        result = service.generate(self.sparse_intent())
        before = result.to_dict()
        with self.assertRaises(RequestValidationError):
            service.answer_route_quality_clarification(result, 'invent a tag')
        self.assertEqual(result.to_dict(), before)

    def test_places_entry_does_not_acquire_plan_for_me_question(self):
        intent = self.sparse_intent()
        intent.route_mode = RouteMode.PLACES_IN_MIND
        intent.must_go_poi_ids = ['p2']
        result = self.sparse_service().generate(intent)
        self.assertEqual(result.status, 'success')
        self.assertIsNone(result.route_quality)

    def test_cli_handles_missing_time_then_quality_prompt_once(self):
        service = self.sparse_service()
        client = MockLLMClient(responses=[candidate(interest_tags=['local_life'], experience_tags=['local_atmosphere'])])
        output = io.StringIO()
        with patch('tools.demos.route_entry_demo.POIRepository', return_value=service.repo), \
                patch('tools.demos.route_entry_demo.DeepSeekLLMClient', return_value=client), \
                patch('sys.stdin', io.StringIO('3\narchitecture\n')), contextlib.redirect_stdout(output):
            code = main(['--mode', 'plan_for_me', '--text', 'authentic'], live=True)
        rendered = output.getvalue()
        self.assertEqual(code, 1)
        self.assertEqual(rendered.count('Would you like to broaden'), 1)
        self.assertIn('Route Quality Clarification Applied: True', rendered)
        self.assertIn('Preference Broadening: architecture', rendered)
        self.assertIn('Selection Reason:', rendered)
        self.assertEqual(len(client.calls), 1)

    def test_json_exposes_quality_question_without_reading_stdin(self):
        service = self.sparse_service()
        client = MockLLMClient(responses=[candidate(available_minutes=180, interest_tags=['local_life'])])
        output = io.StringIO()
        with patch('tools.demos.route_entry_demo.POIRepository', return_value=service.repo), \
                patch('tools.demos.route_entry_demo.DeepSeekLLMClient', return_value=client), \
                patch('builtins.input', side_effect=AssertionError('No interactive JSON input')), \
                contextlib.redirect_stdout(output):
            code = main(['--mode', 'plan_for_me', '--text', 'local', '--json'], live=True)
        self.assertEqual(code, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload['status'], 'needs_route_quality_clarification')
        self.assertEqual(payload['route_quality']['status'], 'clarification_required')
        self.assertFalse(payload['intent']['needs_clarification'])
