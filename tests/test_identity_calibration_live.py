import os
import unittest
from scripts.live_calibration_acceptance import run_acceptance

@unittest.skipUnless(os.environ.get('RUN_LIVE_AMAP_TESTS')=='1','Live Amap calibration tests are opt-in')
class LiveCalibrationTests(unittest.TestCase):
    def test_corrected_routes_and_replan(self):
        result=run_acceptance()
        self.assertEqual(result['core_count'],58)
        self.assertEqual(len(result['coordinate_routes']),2)
        self.assertTrue(all(r['original_version_unchanged'] for r in result['coordinate_routes']))
