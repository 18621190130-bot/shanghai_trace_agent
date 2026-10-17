import os
import unittest
from scripts.live_spatial_acceptance import run_acceptance


@unittest.skipUnless(os.environ.get('RUN_LIVE_AMAP_TESTS') == '1', 'Live spatial tests are opt-in')
class SpatialLiveTests(unittest.TestCase):
    def test_anchor_routes_and_replans(self):
        result = run_acceptance()
        self.assertEqual(len(result['routes']), 5)
        self.assertTrue(all(r['original_version_unchanged'] for r in result['routes']))
        self.assertEqual(next(r for r in result['routes'] if r['core_id']=='p35')['identity_mapping_status'], 'NOT_FOUND')
