from .helpers import baseline_repository, PRE_PHASE2_5_PATH
import unittest
from src import POIRepository, RouteRequest
from src.recommendation_engine import RecommendationEngine
from .helpers import write_repository


class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.repo = baseline_repository()
        self.engine = RecommendationEngine(self.repo)

    def test_known_score_and_matched_tags(self):
        req = RouteRequest(180, interest_tags=["architecture", "history"],
                           experience_tags=["photogenic"], culture_tags=["modern_shanghai"])
        poi = self.repo.get_poi_by_id("p13")
        self.assertEqual(self.engine.tag_score(poi, req), 13)
        self.assertEqual(self.engine.score(poi, req, "wukang_fuxing_xujiahui", 2), 14)
        self.assertEqual(self.engine.score(poi, req, "west_bund", 2), 10)
        self.assertEqual(self.engine.matched_tags(poi, req)["interest_tags"], ["architecture", "history"])

    def test_weights_read_from_config(self):
        raw = self.repo.get_raw_data()
        raw["route_engine_defaults"]["scoring_weights"]["interest_tag_match"] = 11
        other = RecommendationEngine(write_repository(self, raw))
        self.assertEqual(other.tag_score(self.repo.get_poi_by_id("p13"), RouteRequest(180, interest_tags=["architecture"])), 11)

    def test_duplicate_request_tags_do_not_inflate_score(self):
        poi = self.repo.get_poi_by_id("p13")
        self.assertEqual(self.engine.tag_score(poi, RouteRequest(180, interest_tags=["architecture"])),
                         self.engine.tag_score(poi, RouteRequest(180, interest_tags=["architecture", "architecture"])))

    def test_soft_preferences_do_not_change_base_score(self):
        poi = self.repo.get_poi_by_id("p13")
        a = RouteRequest(180, interest_tags=["architecture"])
        b = RouteRequest(180, interest_tags=["architecture"], avoid_crowds=True, environment_preference="indoor")
        self.assertEqual(self.engine.score(poi, a, "wukang_fuxing_xujiahui", 0), self.engine.score(poi, b, "wukang_fuxing_xujiahui", 0))
        self.assertGreater(self.engine.preference_key(poi, b)[0], 0)
        self.assertEqual(self.engine.preference_key(poi, RouteRequest(180, environment_preference="mixed"))[0], 0)

    def test_template_reason_and_must_go(self):
        req = RouteRequest(180, interest_tags=["architecture"], must_go_poi_ids=["p13"])
        explanation = self.engine.explanation(self.repo.get_poi_by_id("p13"), req, "wukang_fuxing_xujiahui")
        self.assertIn("must-go", explanation)
        self.assertIn("architecture", explanation)
        self.assertIn("Wukang", explanation)
