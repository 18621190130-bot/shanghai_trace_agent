import os
import unittest
from scripts.live_location_acceptance import run_acceptance


@unittest.skipUnless(os.environ.get('RUN_LIVE_AMAP_TESTS')=='1','Live Amap location tests are opt-in')
class LiveLocationTests(unittest.TestCase):
    def test_real_location_and_poi_queries(self):
        result=run_acceptance()
        self.assertTrue(result['trip_unchanged'])
        self.assertEqual(result['location']['city'],'上海市')
        self.assertEqual(result['gps_location']['location']['coordinate_system'],'GCJ02')
