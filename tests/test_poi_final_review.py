"""Mock-only checks of explicit human decisions and conditional admission."""
import copy
import unittest
from src.poi_pipeline.semantic.final_review import (build_final_review, validate_final_review,
    zone_expansion_diagnostic, CONDITIONS, CHILDREN, CRANE, CINEMA, MARITIME, THEATRE, FIXED_TAGS)


def fixtures():
    ids = ['production:p5', 'production:p28', 'production:p29', 'production:p30', 'production:p31',
           'route:art_center', 'route:dome', 'route:skate', 'route:runway', 'route:photography', CRANE,
           CINEMA, MARITIME, THEATRE, *CHILDREN, 'route:sports', 'route:reject']
    rows = []
    for i, nid in enumerate(ids):
        rows.append(dict(node_id=nid, name='西岸运动公园' if nid == 'route:sports' else nid,
            identity_status='existing_production' if nid.startswith('production:') else 'new_candidate',
            primary_role='supporting_stop', route_role=dict(primary='supporting_stop', eligible=['supporting_stop']),
            sources=[], evidence_catalog={}, member_candidate_ids=['source:' + str(i)], internal_entity_ids=[],
            coordinates=[31.17, 121.462], coordinate_system='GCJ-02', source_confidence={'existence': 'high'},
            interest_tags=['art'], experience_tags=[], culture_tags=[],
            decision='reject' if nid == 'route:reject' else 'needs_review', reason=['fixture reason'],
            visit_profile={'supported_modes': ['walk_stop', 'full_visit'], 'scope': 'fixture'},
            semantic={'summary_draft': {'text': 'fixture', 'evidence_refs': []}}))
    nodes = [dict(node_id=nid, boundary_status='inside_pilot') for nid in ids]
    entities = [dict(entity_id='hall:' + hall, name='西岸艺术中心' + hall + '馆', parent_node='route:art_center',
        relationship='internal', route_selectable=False) for hall in ('A', 'B1', 'N', 'D')]
    entities.append(dict(entity_id='north_plaza', name='穹顶北广场', parent_node='route:dome', relationship='internal', route_selectable=False))
    taxonomy = {g: set(t for spec in FIXED_TAGS.values() for t in spec[i]) for i, g in enumerate(('interest_tags', 'experience_tags', 'culture_tags'))}
    return rows, nodes, entities, {}, taxonomy


def confirmed(nid):
    return {nid: dict(checks={key: dict(status='confirmed', evidence_refs=['fixture']) for key in CONDITIONS[nid]},
        evidence_catalog={'fixture': {'value': 'mock source'}}, sources=[], conclusion='mock verified')}


class FinalHumanReviewTests(unittest.TestCase):
    def run_review(self, verification=None):
        args = list(fixtures())
        args[3] = verification or {}
        return build_final_review(*args)

    def test_historical_building_is_child_and_preserves_source(self):
        review, nodes = self.run_review()
        self.assertFalse(any(n['node_id'] in CHILDREN for n in nodes))
        child = next(e for e in review['source_entities'] if e['entity_id'] == next(iter(CHILDREN)))
        self.assertEqual(child['parent_node'], 'route:art_center')
        self.assertFalse(child['counts_as_new_stop'])

    def test_crane_square_no_double_count(self):
        review, nodes = self.run_review()
        crane = next(n for n in nodes if n['node_id'] == CRANE)
        self.assertEqual(len(crane['member_candidate_ids']), 2)
        self.assertFalse(any(n['node_id'] == 'route:wb_bfd5b11fdae241d1' for n in nodes))

    def test_dome_dual_mode_one_stop(self):
        review, nodes = self.run_review()
        dome = next(n for n in nodes if n['node_id'] == 'route:dome')
        self.assertEqual(dome['node_model'], 'one_node_dual_mode')
        self.assertIsNone(dome['planning']['opening_hours'])
        self.assertEqual(dome['mode_access']['full_visit'], 'unknown')
        self.assertFalse(next(e for e in review['source_entities'] if e['entity_id'] == 'north_plaza')['route_selectable'])

    def test_sports_deferred(self):
        review, nodes = self.run_review()
        row = next(r for r in review['rows'] if r['name'] == '西岸运动公园')
        self.assertEqual(row['decision'], 'defer')
        self.assertFalse(row['route_selectable'])

    def test_unverified_conditions_excluded(self):
        review, nodes = self.run_review()
        self.assertFalse(set(CONDITIONS) & {n['node_id'] for n in nodes})
        self.assertEqual(review['counts']['conditional'], 3)

    def test_partial_and_uncited_verification_excluded(self):
        v = confirmed(CINEMA)
        v[CINEMA]['checks']['long_term_stability']['status'] = 'unknown'
        self.assertFalse(any(n['node_id'] == CINEMA for n in self.run_review(v)[1]))
        v = confirmed(MARITIME)
        v[MARITIME]['checks']['public_access']['evidence_refs'] = []
        self.assertFalse(any(n['node_id'] == MARITIME for n in self.run_review(v)[1]))

    def test_confirmed_conditions_admitted_with_required_roles(self):
        # Supply real-shaped mock theatre evidence IDs used by the human summary.
        for nid in CONDITIONS:
            v = confirmed(nid)
            v[nid]['evidence_catalog'].update(fv_theatre_services={}, fv_theatre_license={})
            nodes = self.run_review(v)[1]
            row = next(n for n in nodes if n['node_id'] == nid)
            self.assertEqual(row['primary_role'], 'supporting_stop' if nid == THEATRE else 'transition_stop')
            if nid == CINEMA:
                self.assertNotIn('museum_visit', row['experience_tags'])

    def test_art_internal_halls_dont_count(self):
        review, nodes = self.run_review()
        halls = [e for e in review['source_entities'] if e['entity_id'].startswith('hall:')]
        self.assertEqual(len(halls), 4)
        self.assertTrue(all(not e['counts_as_new_stop'] and not e['route_selectable'] for e in halls))
        self.assertEqual(review['counts']['total_route_selectable'], 11)

    def test_production_anchor_not_new(self):
        review, nodes = self.run_review()
        anchors = [n for n in nodes if n['node_id'].startswith('production:')]
        self.assertEqual(len(anchors), 5)
        self.assertTrue(all(n['primary_role'] == 'anchor' and not n['counts_as_new_stop'] for n in anchors))

    def test_coverage_never_changes_human_tags(self):
        args = list(fixtures())
        for r in args[0]:
            r['coverage_gap'] = {'local_life': 100, 'parks': 100}
        review, nodes = build_final_review(*args)
        runway = next(n for n in nodes if n['node_id'] == 'route:runway')
        self.assertEqual(runway['interest_tags'], ['parks', 'history'])
        self.assertNotIn('waterfront', runway['interest_tags'])
        self.assertNotIn('photogenic', next(n for n in nodes if n['node_id'] == 'route:skate')['experience_tags'])

    def test_unknown_tag_and_duplicate_node_fail(self):
        args = list(fixtures())
        args[0][5]['interest_tags'].append('invented')
        with self.assertRaises(ValueError):
            build_final_review(*args)
        args = list(fixtures())
        args[0].append(copy.deepcopy(args[0][0]))
        with self.assertRaises(ValueError):
            build_final_review(*args)

    def test_diagnostic_does_not_run_regression(self):
        self.assertIsNone(zone_expansion_diagnostic()['zone_expansion_recommended'])
        for cause in ('parser', 'tag_mismatch', 'route_engine', 'scoring'):
            self.assertFalse(zone_expansion_diagnostic({'failure_causes': {cause: 10}})['zone_expansion_recommended'])
        self.assertTrue(zone_expansion_diagnostic({'failure_causes': {'quality_node_shortage': 3, 'geographic_gap': 2, 'parser': 1}})['zone_expansion_recommended'])
        self.assertFalse(zone_expansion_diagnostic({'failure_causes': {'quality_node_shortage': 2, 'unknown': 3}})['zone_expansion_recommended'])

    def test_inputs_not_mutated(self):
        args = fixtures()
        original = copy.deepcopy(args)
        build_final_review(*args)
        self.assertEqual(args, original)

    def test_representative_coordinate_must_equal_cited_provider(self):
        v = confirmed(MARITIME)
        v[MARITIME]['representative_anchor'] = dict(coordinates=[31.17, 121.462],
            evidence_refs=['fixture'], confidence='medium')
        v[MARITIME]['evidence_catalog']['fixture']['coordinates'] = [31.18, 121.463]
        with self.assertRaisesRegex(ValueError, 'provider coordinate'):
            self.run_review(v)
        v[MARITIME]['evidence_catalog']['fixture']['coordinates'] = [31.17, 121.462]
        nodes = self.run_review(v)[1]
        self.assertEqual(next(n for n in nodes if n['node_id'] == MARITIME)['coordinates'], [31.17, 121.462])

    def test_verification_missing_source_reference_fails_closed(self):
        v = confirmed(CINEMA)
        v[CINEMA]['evidence_catalog'] = {}
        with self.assertRaisesRegex(ValueError, 'reference missing'):
            self.run_review(v)


if __name__ == '__main__':
    unittest.main()
