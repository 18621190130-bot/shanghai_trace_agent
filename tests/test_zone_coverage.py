from .helpers import baseline_repository, PRE_PHASE2_5_PATH
import unittest
from src.poi_repository import POIRepository
from src.poi_pipeline.coverage import ZoneCoverageAnalyzer, WestBundCoverageAnalyzer


class ZoneCoverageTests(unittest.TestCase):
    def test_all_zones_remain_isolated(self):
        repo = baseline_repository()
        for zone in repo.zone_order:
            result = ZoneCoverageAnalyzer(zone, repo).analyze()
            ids = {p.id for p in repo.get_pois_by_zone(zone)}
            self.assertEqual(result['walk_zone'], zone)
            self.assertEqual({p['id'] for p in result['geography']['pois']}, ids)
            self.assertEqual(result['poi_count'], len(ids))
            self.assertEqual(sum(result['route_role_coverage'].values()), len(ids))

    def test_unknown_zone_fails(self):
        with self.assertRaises(ValueError):
            ZoneCoverageAnalyzer('not_a_zone')

    def test_pilot_compatibility(self):
        self.assertEqual(WestBundCoverageAnalyzer().analyze(), ZoneCoverageAnalyzer('west_bund').analyze())
