import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from src.poi_repository import POIRepository
from src.models import RouteRequest, DataValidationError
from src.route_engine import RouteEngine
from src.route_composition import composition_assessment
from src.route_entry import RouteEntryService
from src.intent_models import RouteIntent, RouteMode
from src.llm_client import MockLLMClient
from src.mock_examples import candidate
from src.poi_pipeline.candidate_kb import build_candidate_kb, NEW_IDS
from src.west_bund_regression import run_regression, expansion_diagnostics
from .helpers import write_repository, subset

ROOT = Path(__file__).resolve().parents[1]


def raw_inputs():
    read = lambda p: json.loads(p.read_text(encoding='utf-8'))
    final = ROOT / 'data/poi_pipeline/semantic/final'
    return (read(ROOT / 'data/archive/pois_pre_phase2_5.json'), read(final / 'west_bund_route_nodes_final_staging.json'),
            read(final / 'west_bund_human_review_final.json'))


class WestBundIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.production, self.staging, self.review = raw_inputs()
        self.kb, self.mapping = build_candidate_kb(self.production, self.staging, self.review)
        self.repo = write_repository(self, self.kb)
        self.engine = RouteEngine(self.repo)

    def test_metadata_counts_actual_and_west_bund_13(self):
        self.assertEqual(len(self.repo.get_all_pois()), 35)
        self.assertEqual(len(self.repo.get_pois_by_zone('west_bund')), 13)
        self.assertEqual(self.kb['metadata']['poi_count'], len(self.kb['pois']))
        self.assertEqual(next(z['poi_count'] for z in self.kb['metadata']['walk_zones'] if z['id'] == 'west_bund'), 13)

    def test_existing_ids_and_other_zone_records_unchanged(self):
        old = {p['id']: p for p in self.production['pois']}
        new = {p['id']: p for p in self.kb['pois']}
        self.assertTrue(set(old).issubset(new))
        for pid, poi in old.items():
            if poi['walk_zone']['id'] != 'west_bund':
                self.assertEqual(poi, new[pid])
            else:
                stripped = {k:v for k,v in new[pid].items() if k not in ('route_role', 'counts_as_route_stop', 'route_selectable')}
                self.assertEqual(poi, stripped)

    def test_new_ids_stable_under_staging_reorder(self):
        reordered = copy.deepcopy(self.staging)
        reordered['route_nodes'].reverse()
        _, mapping = build_candidate_kb(self.production, reordered, self.review)
        self.assertEqual(mapping['staging_to_candidate_id'], self.mapping['staging_to_candidate_id'])
        self.assertEqual({mapping['staging_to_candidate_id'][nid] for nid in NEW_IDS}, set(NEW_IDS.values()))

    def test_roles_do_not_follow_modes(self):
        p = self.repo.get_poi_by_id('p5')
        for mode in ('walk_stop', 'full_visit'):
            visit = self.engine.visits.resolve(p, RouteRequest(180, visit_mode_overrides={'p5': mode}))
            self.assertEqual(visit.effective_primary_role, 'anchor')
        self.assertEqual(self.repo.get_poi_by_id('p36').effective_primary_role, 'supporting_stop')

    def test_composition_valid_combinations(self):
        for roles in [('anchor', 'supporting_stop', 'transition_stop'),
                      ('anchor', 'supporting_stop', 'supporting_stop'), ('anchor', 'anchor', 'supporting_stop')]:
            stops = [SimpleNamespace(effective_primary_role=r) for r in roles]
            self.assertTrue(composition_assessment(stops, True)['route_composition_passed'])

    def test_anchor_two_transitions_invalid(self):
        stops = [SimpleNamespace(effective_primary_role=r) for r in ('anchor', 'transition_stop', 'transition_stop')]
        result = composition_assessment(stops, True)
        self.assertTrue(result['minimum_stop_count_passed'])
        self.assertFalse(result['route_composition_passed'])

    def test_transition_only_not_complete_citywalk(self):
        raw = copy.deepcopy(self.kb)
        ids = ['p37', 'p42', 'p43']
        for p in raw['pois']:
            if p['id'] in ids:
                p['route_role'] = {'primary': 'transition_stop', 'eligible': ['transition_stop']}
        repo = write_repository(self, subset(raw, [p for p in raw['pois'] if p['id'] in ids]))
        plan = RouteEngine(repo).generate_route(RouteRequest(180, preferred_zone='west_bund'))
        self.assertEqual(plan.status, 'composition_failure')
        self.assertTrue(plan.composition_diagnostics['minimum_stop_count_passed'])

    def test_places_bypasses_composition_preserves_exact_selections(self):
        service = RouteEntryService(self.repo)
        result = service.generate(service.places_intent(['p42', 'p43'], available_minutes=180, preferred_zone='west_bund'))
        self.assertEqual(result.status, 'success')
        self.assertEqual({s.poi_id for s in result.route_plan.ordered_pois}, {'p42', 'p43'})
        self.assertFalse(result.route_plan.composition_diagnostics['enabled'])

    def test_other_zones_preserve_phase2_routes(self):
        baseline = RouteEngine(write_repository(self, self.production))
        for zone, tags in [('wukang_fuxing_xujiahui', ['architecture', 'local_life']),
                           ('old_city_central', ['history']), ('hongkou_literary', ['literature'])]:
            req = RouteRequest(180, preferred_zone=zone, interest_tags=tags)
            a, b = baseline.generate_route(req), self.engine.generate_route(req)
            self.assertEqual(a.status, b.status)
            self.assertEqual([(p.poi_id, p.selected_visit_mode) for p in a.ordered_pois],
                             [(p.poi_id, p.selected_visit_mode) for p in b.ordered_pois])
            self.assertEqual(a.total_estimated_minutes, b.total_estimated_minutes)
            self.assertFalse(b.composition_diagnostics['enabled'])

    def test_internal_registry_and_archived_cinema_never_active(self):
        self.assertEqual(self.mapping['active_conditional_candidates'], [])
        self.assertEqual(self.mapping['historical_rejected_candidates'][0]['decision'], 'reject_current_pilot')
        self.assertTrue(self.mapping['historical_rejected_candidates'][0]['evidence_catalog'])
        self.assertTrue(all(not e['counts_as_route_stop'] for e in self.mapping['internal_entities']))
        self.assertEqual(len(self.repo.get_pois_by_zone('west_bund')), len(self.mapping['staging_to_candidate_id']))
        self.assertFalse(any(p.name_zh == '无尽影院' for p in self.repo.get_all_pois()))

    def test_internal_poi_excluded_even_if_injected_into_kb(self):
        raw = copy.deepcopy(self.kb)
        child = copy.deepcopy(raw['pois'][-1])
        child.update(id='mock_child', route_selectable=False, counts_as_route_stop=False)
        raw = subset(raw, raw['pois'] + [child])
        repo = write_repository(self, raw)
        plan = RouteEngine(repo).generate_route(RouteRequest(180, preferred_zone='west_bund'))
        self.assertNotIn('mock_child', [p.poi_id for p in plan.ordered_pois])
        bad = RouteEngine(repo).generate_route(RouteRequest(180, must_go_poi_ids=['mock_child']))
        self.assertEqual(bad.status, 'validation_error')

    def test_avoid_museums_and_no_filler_art_anchor(self):
        plan = self.engine.generate_route(RouteRequest(180, interest_tags=['art'], avoid_tags=['museum_visit'], preferred_zone='west_bund'))
        self.assertEqual(plan.status, 'composition_failure')
        self.assertTrue(plan.composition_diagnostics['minimum_stop_count_passed'])
        self.assertNotIn('p30', [s.poi_id for s in plan.ordered_pois])
        for s in plan.ordered_pois:
            self.assertNotIn('museum_visit', self.repo.get_poi_by_id(s.poi_id).experience_tags)

    def test_schema_rejects_bad_role_and_missing_role_on_enabled_zone(self):
        for role in ({'primary': 'famous', 'eligible': ['anchor']}, None):
            raw = copy.deepcopy(self.kb)
            poi = next(p for p in raw['pois'] if p['id'] == 'p36')
            poi['route_role'] = role
            with self.assertRaises(DataValidationError):
                write_repository(self, raw)

    def test_gate_quality_keeps_or_interest_and_rejects_unrelated_and_far(self):
        req = RouteRequest(180, preferred_zone='west_bund', interest_tags=['parks', 'waterfront'], culture_tags=['public_life'])
        seed = self.engine.visits.resolve(self.repo.get_poi_by_id('p38'), req)
        candidate_visit = self.engine.visits.resolve(self.repo.get_poi_by_id('p42'), req)
        self.assertTrue(self.engine.is_candidate_worth_adding(candidate_visit, [seed], [seed, candidate_visit], req, 'west_bund', None))
        from dataclasses import replace
        far = replace(candidate_visit.poi, coordinates=(31.4, 121.6))
        visit = self.engine.visits.resolve(far, req)
        self.assertFalse(self.engine.is_candidate_worth_adding(visit, [seed], [seed, visit], req, 'west_bund', None))
        unrelated = self.engine.visits.resolve(self.repo.get_poi_by_id('p41'), req)
        self.assertFalse(self.engine.is_candidate_worth_adding(unrelated, [seed], [seed, unrelated], req, 'west_bund', None))

    def test_eight_regression_cases_and_three_modes(self):
        rows, modes = run_regression(self.repo)
        self.assertEqual(len(rows), 8)
        self.assertEqual(sum(r['route_status'] == 'success' for r in rows), 7)
        self.assertTrue(all(v['status'] == 'success' for v in modes.values()))
        diag = expansion_diagnostics(self.repo, rows)
        self.assertFalse(diag['zone_expansion_recommended'])
        self.assertEqual(diag['composition_failure_count'], 1)

    def test_mock_provider_end_to_end_contract(self):
        text = 'Mock outdoor West Bund walk'
        mock = MockLLMClient(fixtures={text: candidate(available_minutes=180, preferred_zone='west_bund',
            interest_tags=['waterfront', 'parks'], avoid_tags=['museum_visit'])})
        service = RouteEntryService(self.repo, mock)
        result = service.generate(service.parse_plan(text))
        self.assertEqual(result.status, 'success')
        self.assertTrue(result.route_plan.composition_diagnostics['route_composition_passed'])
        self.assertEqual(len(mock.calls), 1)

    def test_composition_repair_preserves_must_go_and_quality_gates(self):
        req = RouteRequest(180, preferred_zone='west_bund', interest_tags=['waterfront'])
        visits = [self.engine.visits.resolve(self.repo.get_poi_by_id(pid), req) for pid in ('p30','p42','p43','p38')]
        repaired = self.engine._repair_composition(visits[:3], visits, req, 'west_bund', None, 3)
        self.assertTrue(composition_assessment(repaired, True)['route_composition_passed'])
        self.assertEqual(len(repaired), 3)
        req.must_go_poi_ids = ['p42','p43']
        unchanged = self.engine._repair_composition(visits[:3], visits, req, 'west_bund', None, 3)
        self.assertEqual({p.id for p in unchanged}, {'p30','p42','p43'})
        self.assertFalse(composition_assessment(unchanged, True)['route_composition_passed'])
