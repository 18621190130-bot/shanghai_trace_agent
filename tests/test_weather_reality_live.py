import os
import unittest
from scripts.live_weather_reality_acceptance import run_acceptance


@unittest.skipUnless(os.environ.get('RUN_LIVE_AMAP_TESTS') == '1', 'Live Amap tests are opt-in')
class LiveWeatherRealityTests(unittest.TestCase):
    def test_final_cases_a_b_c(self):
        result = run_acceptance()
        self.assertEqual(len(result['cases']),3)
        self.assertTrue(result['trip_state_unchanged'])
        self.assertEqual(result['walking_requests_during_reality_check'],0)
