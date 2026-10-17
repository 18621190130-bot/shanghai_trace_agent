from .helpers import baseline_repository, PRE_PHASE2_5_PATH
import unittest
from unittest.mock import patch

from tools.demos.demo import render_plan
from src import POIRepository, RouteEngine, RouteRequest, RouteEntryService
from src.llm_client import MockLLMClient
from src.mock_examples import candidate
from . import test_phase2_quality as quality


class PreferredRichnessTests(unittest.TestCase):
    def fixture(self, interests, experiences=(), offset=.003, budget=180):
        return quality.UtilizationQualityTests.fixture(self, interests, experiences, offset, budget)

    def test_preferred_minimum_allows_three_quality_stops(self):
        engine, req, core, extra = self.fixture(['local_life'], offset=.03)
        plan = engine.generate_route(req)
        self.assertEqual(plan.status, 'success')
        self.assertEqual(plan.richness_target['min_stops'], 4)
        self.assertEqual(len(plan.ordered_pois), 3)
        self.assertFalse(plan.richness_target_met)
        self.assertTrue(any('Preferred route richness' in w and 'route-quality gate' in w for w in plan.warnings))

    def test_four_good_candidates_still_meet_richness(self):
        engine, req, core, extra = self.fixture(['architecture', 'local_life'])
        plan = engine.generate_route(req)
        self.assertEqual(plan.status, 'success')
        self.assertEqual(len(plan.ordered_pois), 4)
        self.assertTrue(plan.richness_target_met)
        self.assertIn('richness_expansion', [p.selection_reason for p in plan.ordered_pois])

    def test_actual_120_min_architecture_local_life_remains_rich_and_compact(self):
        plan = RouteEngine(baseline_repository()).generate_route(RouteRequest(120,
            interest_tags=['architecture', 'local_life']))
        self.assertEqual(plan.status, 'success')
        self.assertGreaterEqual(len(plan.ordered_pois), 3)
        self.assertTrue(plan.richness_target_met)
        self.assertLess(plan.estimated_max_single_leg_km, 1)
        self.assertTrue(all('architecture' in p.matched_tags['interest_tags'] and
                            'local_life' in p.matched_tags['interest_tags'] for p in plan.ordered_pois))

    def test_primary_expansion_calls_shared_gate_before_minimum(self):
        engine, req, core, extra = self.fixture(['local_life'], offset=.03)
        with patch.object(engine, 'is_candidate_worth_adding', wraps=engine.is_candidate_worth_adding) as gate:
            with patch.object(engine, '_improve_utilization', side_effect=lambda route, *args: route):
                plan = engine.generate_route(req)
        attempted = [c for c in gate.call_args_list if c.args[0].id == extra.id and c.args[1]]
        self.assertTrue(attempted)
        self.assertTrue(any(len(c.args[1]) < 4 for c in attempted))
        self.assertNotIn(extra.id, [p.poi_id for p in plan.ordered_pois])

    def test_time_filling_uses_same_gate(self):
        engine, req, core, extra = self.fixture(['architecture', 'local_life'])
        with patch.object(engine, 'is_candidate_worth_adding', return_value=False) as gate:
            trial = engine._improve_utilization(core, core + [extra], req, core[0].zone_id, None, 4)
        self.assertTrue(gate.called)
        self.assertNotIn(extra.id, [p.id for p in trial])

    def test_time_fill_reason_tracks_newly_selected_id(self):
        engine, req, core, extra = self.fixture(['architecture', 'local_life'])
        real_gate = engine.is_candidate_worth_adding
        def only_refinement(candidate, route, trial, request, zone, start):
            # Force a known stage transition to verify bookkeeping rather than geometry.
            import inspect
            return (any(f.function == '_improve_utilization' for f in inspect.stack())
                    and real_gate(candidate, route, trial, request, zone, start)) if candidate.id == extra.id else real_gate(candidate, route, trial, request, zone, start)
        with patch.object(engine, 'is_candidate_worth_adding', side_effect=only_refinement):
            plan = engine.generate_route(req)
        selected = next(p for p in plan.ordered_pois if p.poi_id == extra.id)
        self.assertEqual(selected.selection_reason, 'time_fill')

    def test_must_go_bypasses_quality_and_has_reason(self):
        engine, req, core, extra = self.fixture(['local_life'], offset=.03)
        req.must_go_poi_ids = [extra.id]
        plan = engine.generate_route(req)
        self.assertEqual(plan.status, 'success')
        self.assertEqual(next(p.selection_reason for p in plan.ordered_pois if p.poi_id == extra.id), 'must_go')
        self.assertTrue(all(p.selection_reason in {'core_match', 'must_go', 'richness_expansion', 'time_fill'}
                            for p in plan.ordered_pois))
        self.assertTrue(all('selection_reason' in p for p in plan.to_dict()['ordered_pois']))

    def test_near_weak_candidate_cannot_fill_richness(self):
        engine, req, core, extra = self.fixture(['local_life'], offset=.0015)
        plan = engine.generate_route(req)
        self.assertEqual(len(plan.ordered_pois), 3)
        self.assertFalse(plan.richness_target_met)
        self.assertNotIn(extra.id, [p.poi_id for p in plan.ordered_pois])

    def test_replacement_cannot_hide_far_candidate_cost(self):
        engine = RouteEngine(baseline_repository())
        req = RouteRequest(180, interest_tags=['local_life'])
        core = [engine.visits.resolve(engine.repository.get_poi_by_id(pid), req) for pid in ['p11', 'p2', 'p12']]
        extra = engine.visits.resolve(engine.repository.get_poi_by_id('p33'), req)
        trial = engine._shortest_order([core[0], core[1], extra], None)
        self.assertFalse(engine.is_candidate_worth_adding(extra, core, trial, req, core[0].zone_id, None))

    def test_cli_explains_unmet_richness_and_each_selection(self):
        engine, req, core, extra = self.fixture(['local_life'], offset=.03)
        plan = engine.generate_route(req)
        rendered = render_plan('Route', plan, engine.repository)
        self.assertIn('Preferred Richness: 4–5 stops', rendered)
        self.assertIn('Actual Stops: 3', rendered)
        self.assertIn('Preferred Richness Met: False', rendered)
        self.assertIn('route-quality gate', rendered)
        self.assertEqual(rendered.count('Selection Reason:'), 3)
        self.assertEqual(rendered.count('Preferred Richness:'), 1)

    def test_live_parse_variant_without_experience_tag_is_also_gated(self):
        service = RouteEntryService(baseline_repository(), MockLLMClient(responses=[candidate(
            available_minutes=150, interest_tags=['local_life'], avoid_tags=['museum_visit'])]))
        result = service.generate(service.parse_plan(quality.A))
        self.assertEqual(result.status, 'success')
        self.assertNotIn('p33', [p.poi_id for p in result.route_plan.ordered_pois])
