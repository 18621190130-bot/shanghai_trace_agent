import os
import unittest
from scripts.live_walking_acceptance import run_acceptance


@unittest.skipUnless(os.environ.get('RUN_LIVE_AMAP_TESTS') == '1', 'Live Amap tests are opt-in')
class LiveWalkingTests(unittest.TestCase):
    def test_real_west_bund(self):
        result = run_acceptance()
        self.assertGreater(result['real_walking_distance_m'], 0)
        self.assertGreater(result['real_walking_duration_s'], 0)
        self.assertEqual(result['leg_count'], len(result['stops']) - 1)
        self.assertGreater(result['geometry_point_count'], 0)
