from .helpers import baseline_repository, PRE_PHASE2_5_PATH
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from src import POIRepository, RouteEngine, RouteRequest, RouteEntryService
from src.llm_client import MockLLMClient
from src.mock_examples import PLAN_EXAMPLES
from .helpers import subset, write_repository

ROOT = Path(__file__).resolve().parents[1]
A = "I have two and a half hours. I want local neighborhoods and I'd rather avoid museums."
B = "I want to see the more authentic side of Shanghai."


class UtilizationQualityTests(unittest.TestCase):
    def fixture(self, interests, experiences=(), offset=.003, budget=180):
        raw = json.loads((PRE_PHASE2_5_PATH).read_text(encoding='utf-8'))
        pois = [next(p for p in raw['pois'] if p['id'] == pid)
                for pid in ('p2', 'p11', 'p12', 'p33')]
        for index, poi in enumerate(pois):
            longitude = 121.44 + (index*.001 if index < 3 else offset)
            poi['location'].update(lat=31.20, lng=longitude, representative_lat=31.20,
                                   representative_lng=longitude, coordinate_system='GCJ-02')
            poi['tags']['interest_tags'] = ['architecture', 'local_life'] if index < 3 else list(interests)
            poi['tags']['experience_tags'] = [] if index < 3 else list(experiences)
            poi['tags']['culture_tags'] = []
            poi['visit_profile'] = {'default_mode': 'walk_stop', 'supported_modes': ['walk_stop'],
                                    'modes': {'walk_stop': dict(quick=5, standard=5 if index < 3 else 30, deep=30)}}
            poi['visit_mode_details'] = {'walk_stop': {'environment': 'outdoor', 'ticket_required': False,
                                                       'scope': 'Test exterior visit'}}
            poi['visit_profile_calibration']['pending_manual_calibration_modes'] = []
        engine = RouteEngine(write_repository(self, subset(raw, pois)))
        req = RouteRequest(available_minutes=budget, interest_tags=['architecture', 'local_life'],
                           experience_tags=['neighborhood_walk'])
        visits = [engine.visits.resolve(p, req) for p in engine.repository.get_all_pois()]
        return engine, req, visits[:3], visits[3]

    def worth(self, engine, req, core, candidate):
        trial = engine._shortest_order(core + [candidate], None)
        return engine.is_worth_adding_for_utilization(candidate, core, trial, req, core[0].zone_id, None)

    def refine(self, engine, req, core, candidate):
        return engine._improve_utilization(core, core + [candidate], req, core[0].zone_id, None, 4)

    def test_weak_far_candidate_cannot_fill_time(self):
        engine, req, core, candidate = self.fixture(['local_life'], offset=.03)
        self.assertFalse(self.worth(engine, req, core, candidate))
        self.assertEqual(self.refine(engine, req, core, candidate), core)
        self.assertLess(engine._metrics(core, None)[3]/req.available_minutes, .65)

    def test_strong_near_candidate_improves_utilization(self):
        engine, req, core, candidate = self.fixture(['architecture', 'local_life'])
        self.assertTrue(self.worth(engine, req, core, candidate))
        trial = self.refine(engine, req, core, candidate)
        self.assertIn(candidate.id, [p.id for p in trial])
        self.assertGreater(engine._metrics(trial, None)[3], engine._metrics(core, None)[3])

    def test_strong_far_candidate_has_no_absolute_leg_veto(self):
        engine, req, core, candidate = self.fixture(['architecture', 'local_life'], offset=.03)
        trial = engine._shortest_order(core + [candidate], None)
        self.assertGreater(max(engine._legs(trial, None)), 2)
        self.assertTrue(self.worth(engine, req, core, candidate))
        self.assertIn(candidate.id, [p.id for p in self.refine(engine, req, core, candidate)])

    def test_near_but_weak_candidate_is_rejected(self):
        engine, req, core, candidate = self.fixture(['local_life'], offset=.0015)
        self.assertFalse(self.worth(engine, req, core, candidate))
        self.assertEqual(self.refine(engine, req, core, candidate), core)

    def test_moderate_near_candidate_is_allowed(self):
        engine, req, core, candidate = self.fixture(['local_life'], ['neighborhood_walk'], offset=.0015)
        self.assertTrue(self.worth(engine, req, core, candidate))
        self.assertIn(candidate.id, [p.id for p in self.refine(engine, req, core, candidate)])

    def test_good_improvement_below_seventy_percent_is_accepted(self):
        engine, req, core, candidate = self.fixture(['architecture', 'local_life'], budget=120)
        trial = self.refine(engine, req, core, candidate)
        self.assertIn(candidate.id, [p.id for p in trial])
        self.assertLess(engine._metrics(trial, None)[3]/req.available_minutes, .70)
        self.assertGreater(engine._metrics(trial, None)[3], engine._metrics(core, None)[3])

    def test_relative_quality_does_not_depend_on_score_scale(self):
        engine, req, core, candidate = self.fixture(['local_life'], ['neighborhood_walk'], offset=.0015)
        before = self.worth(engine, req, core, candidate)
        for key in engine.recommendation.weights:
            engine.recommendation.weights[key] *= 100
        self.assertEqual(self.worth(engine, req, core, candidate), before)

    def test_refinement_is_deterministic(self):
        engine, req, core, candidate = self.fixture(['architecture', 'local_life'])
        outputs = [[(p.id, p.selected_visit_mode) for p in self.refine(engine, req, core, candidate)]
                   for _ in range(5)]
        self.assertTrue(all(o == outputs[0] for o in outputs))

    def test_actual_case_A_rejects_book_stop_and_warns(self):
        service = RouteEntryService(baseline_repository(), MockLLMClient(fixtures=PLAN_EXAMPLES))
        intent = service.parse_plan(A)
        plan = service.generate(intent).route_plan
        self.assertNotIn('p33', [p.poi_id for p in plan.ordered_pois])
        self.assertLess(plan.time_utilization_ratio, .65)
        self.assertTrue(any('Limited matching POIs' in w for w in plan.warnings))
        self.assertEqual(intent.avoid_tags, ['museum_visit'])

    def test_actual_case_B_book_stop_rejected_in_both_stages(self):
        service = RouteEntryService(baseline_repository(), MockLLMClient(fixtures=PLAN_EXAMPLES))
        intent = service.answer_clarification(service.parse_plan(B), 'available_minutes', '3 hours')
        engine = RouteEngine(baseline_repository())
        from src import intent_to_route_request
        request = intent_to_route_request(intent)
        normal = engine.generate_route(request)
        with patch.object(engine, '_improve_utilization', side_effect=lambda route, *args: route):
            primary = engine.generate_route(request)
        self.assertEqual([p.poi_id for p in normal.ordered_pois], [p.poi_id for p in primary.ordered_pois])
        self.assertNotIn('p33', [p.poi_id for p in primary.ordered_pois])
        self.assertFalse(normal.richness_target_met)
        self.assertEqual(intent.available_minutes, 180)
        self.assertEqual(intent.interest_tags, ['local_life'])
