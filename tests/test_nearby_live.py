import os
import unittest
from scripts.live_nearby_acceptance import run_acceptance


@unittest.skipUnless(os.environ.get('RUN_LIVE_AMAP_TESTS')=='1','Live nearby acceptance is opt-in')
class NearbyLiveTests(unittest.TestCase):
    def test_three_cases_and_no_mutation(self):
        result=run_acceptance()
        self.assertEqual(len(result['cases']),3)
        self.assertTrue(result['trip_unchanged'] and result['route_versions_unchanged'] and result['core_repository_unchanged'])
        self.assertEqual(result['detail_request_count'],0)
