from .helpers import baseline_repository, PRE_PHASE2_5_PATH
import copy
import math
import unittest
from dataclasses import asdict
from unittest.mock import patch
from src import POIRepository, RouteEngine, RouteRequest
from src.geo_utils import haversine_km, to_gcj02
from .helpers import write_repository, subset


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.repo = baseline_repository()
        self.engine = RouteEngine(self.repo)

    def assert_valid_route(self, result, request, repo=None):
        repo = repo or self.repo
        self.assertEqual(result.status, "success", result.errors)
        self.assertTrue(result.ordered_pois)
        ids = [n.id for n in result.ordered_pois]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(set(request.must_go_poi_ids).issubset(ids))
        previous = None if request.start_lat is None else to_gcj02(request.start_lat, request.start_lng, request.start_coordinate_system)
        distance, stay = 0.0, 0.0
        for node in result.ordered_pois:
            poi = repo.get_poi_by_id(node.id)
            self.assertIsNotNone(poi.coordinates)
            leg = 0 if previous is None else haversine_km(previous, poi.coordinates) * repo.defaults["walking_distance_factor"]
            self.assertAlmostEqual(node.estimated_distance_from_previous_stop_km, leg)
            self.assertAlmostEqual(node.estimated_walking_minutes, leg * 1000 / repo.defaults["walking_speed_m_per_min"])
            self.assertEqual(node.opening_status, "opening_status_unverified")
            distance += leg
            stay += poi.visit_profile.stay_for(node.selected_visit_mode, node.travel_pace)
            previous = poi.coordinates
        walking = distance * 1000 / repo.defaults["walking_speed_m_per_min"]
        total = stay + walking + repo.defaults["route_buffer_minutes"]
        self.assertAlmostEqual(result.total_estimated_distance_km, distance)
        self.assertAlmostEqual(result.total_estimated_walking_minutes, walking)
        self.assertAlmostEqual(result.total_stay_minutes, stay)
        self.assertAlmostEqual(result.total_estimated_minutes, total)
        self.assertAlmostEqual(result.remaining_minutes, request.available_minutes - total)
        self.assertLessEqual(total, request.available_minutes)
        if request.max_walking_km is not None:
            self.assertLessEqual(distance, request.max_walking_km)

    def test_architecture_walk_prefers_wukang_fuxing_xujiahui(self):
        req = RouteRequest(180, interest_tags=["architecture", "local_life"], experience_tags=["neighborhood_walk"])
        result = self.engine.generate_route(req)
        self.assert_valid_route(result, req)
        self.assertEqual(result.selected_zone, "wukang_fuxing_xujiahui")
        self.assertTrue(all(n.walk_zone == "wukang_fuxing_xujiahui" for n in result.ordered_pois))

    def test_wukang_must_go_and_preferred_zone_conflict(self):
        req = RouteRequest(180, interest_tags=["architecture"], must_go_poi_ids=["p13"], preferred_zone="west_bund")
        result = self.engine.generate_route(req)
        self.assert_valid_route(result, req)
        self.assertEqual(result.selected_zone, "wukang_fuxing_xujiahui")
        self.assertTrue(any("preferred_zone_unfulfilled" in w for w in result.warnings))

    def test_literary_walk_prefers_hongkou(self):
        req = RouteRequest(120, interest_tags=["literature"], experience_tags=["quiet_walk"])
        result = self.engine.generate_route(req)
        self.assert_valid_route(result, req)
        self.assertEqual(result.selected_zone, "hongkou_literary")

    def test_art_walk_prefers_west_bund(self):
        req = RouteRequest(180, interest_tags=["art", "industrial_heritage"], experience_tags=["riverside_walk"])
        result = self.engine.generate_route(req)
        self.assert_valid_route(result, req)
        self.assertEqual(result.selected_zone, "west_bund")

    def test_yu_garden_90_minutes_proven_infeasible(self):
        req = RouteRequest(90, must_go_poi_ids=["p15"], visit_mode_overrides={"p15": "full_visit"}, allow_mode_downgrade=False)
        result = self.engine.generate_route(req)
        self.assertEqual(result.status, "infeasible")
        self.assertIn("105.00", result.errors[0])
        self.assertEqual(result.ordered_pois, [])
        self.assertIsNone(result.total_estimated_minutes)
        self.assertEqual(result.request["must_go_poi_ids"], ["p15"])
        self.assertTrue(result.relaxation_suggestions)

    def test_exact_single_stop_budget_and_scope(self):
        req = RouteRequest(105, must_go_poi_ids=["p15"], visit_mode_overrides={"p15": "full_visit"}, allow_mode_downgrade=False)
        result = self.engine.generate_route(req)
        self.assert_valid_route(result, req)
        self.assertEqual([n.id for n in result.ordered_pois], ["p15"])
        self.assertEqual(result.total_estimated_minutes, 105)
        self.assertIn("garden visit", result.ordered_pois[0].visit_scope)

    def test_five_repeated_complete_results_identical(self):
        for req in (RouteRequest(180, interest_tags=["architecture", "local_life"]),
                    RouteRequest(600, must_go_poi_ids=["p13", "p14", "p25"]),
                    RouteRequest(90, must_go_poi_ids=["p15"])):
            results = [self.engine.generate_route(req).to_dict() for _ in range(5)]
            self.assertTrue(all(r == results[0] for r in results))

    def test_cross_zone_must_go_retained_and_distance_enforced(self):
        req = RouteRequest(600, must_go_poi_ids=["p13", "p14"])
        result = self.engine.generate_route(req)
        self.assert_valid_route(result, req)
        self.assertTrue(result.cross_zone_required)
        self.assertTrue(all(n.must_go or n.walk_zone == result.selected_zone for n in result.ordered_pois))
        impossible = self.engine.generate_route(RouteRequest(600, must_go_poi_ids=["p13", "p14"], max_walking_km=.1))
        self.assertEqual(impossible.status, "infeasible")
        self.assertTrue(impossible.cross_zone_required)
        self.assertEqual(impossible.ordered_pois, [])

    def test_missing_coordinate_must_go_is_not_dropped(self):
        raw = self.repo.get_raw_data()
        next(p for p in raw["pois"] if p["id"] == "p24")["location"]["lat"] = None
        engine = RouteEngine(write_repository(self, raw))
        result = engine.generate_route(RouteRequest(600, must_go_poi_ids=["p13", "p24"]))
        self.assertEqual(result.status, "infeasible")
        self.assertIn("p24", result.errors[0])
        self.assertEqual(result.request["must_go_poi_ids"], ["p13", "p24"])

    def test_start_approach_counts_and_no_return(self):
        poi = self.repo.get_poi_by_id("p13")
        req = RouteRequest(600, start_lat=31.22, start_lng=121.45, must_go_poi_ids=["p13"])
        result = self.engine.generate_route(req)
        self.assert_valid_route(result, req)
        self.assertGreater(result.ordered_pois[0].estimated_distance_from_previous_stop_km, 0)
        self.assertIn("no return", result.time_budget_scope)
        fail = self.engine.generate_route(RouteRequest(45, start_lat=32, start_lng=121, must_go_poi_ids=["p13"]))
        self.assertEqual(fail.status, "infeasible")

    def test_start_wgs84_and_p25_conversion(self):
        req = RouteRequest(180, start_lat=31.26, start_lng=121.48, start_coordinate_system="WGS84", must_go_poi_ids=["p25"])
        result = self.engine.generate_route(req)
        self.assert_valid_route(result, req)
        self.assertTrue(any("start_coordinate_conversion" in w for w in result.warnings))
        self.assertTrue(any("coordinate_conversion: p25" in w for w in result.warnings))

    def test_invalid_requests(self):
        invalid = [
            {"available_minutes": 0}, {"available_minutes": True}, {"available_minutes": 10.5},
            {"available_minutes": 180, "interest_tags": ["invented"]},
            {"available_minutes": 180, "experience_tags": ["architecture"]},
            {"available_minutes": 180, "must_go_poi_ids": ["p999"]},
            {"available_minutes": 180, "preferred_zone": "unknown"},
            {"available_minutes": 180, "start_lat": 31},
            {"available_minutes": 180, "start_lat": 91, "start_lng": 121},
            {"available_minutes": 180, "max_walking_km": float("nan")},
            {"available_minutes": 180, "max_walking_km": float("inf")},
            {"available_minutes": 180, "max_walking_km": 0},
            {"available_minutes": 180, "avoid_crowds": "yes"},
            {"available_minutes": 180, "start_coordinate_system": "BD-09"},
            {"available_minutes": 180, "environment_preference": "rainproof"},
            {"available_minutes": 180, "interest_tags": "architecture"},
            {"available_minutes": 180, "extra": "field"}, {}, "natural language request",
        ]
        for req in invalid:
            with self.subTest(request=req):
                result = self.engine.generate_route(req)
                self.assertEqual(result.status, "validation_error")
                self.assertTrue(result.errors)

    def test_duplicate_values_and_input_not_mutated(self):
        req = RouteRequest(180, interest_tags=["architecture", "architecture"], must_go_poi_ids=["p13", "p13"])
        original = asdict(req)
        result = self.engine.generate_route(req)
        self.assert_valid_route(result, req)
        self.assertEqual(asdict(req), original)
        self.assertEqual(sum(n.id == "p13" for n in result.ordered_pois), 1)
        for n in result.ordered_pois:
            self.assertLessEqual(n.matched_tags["interest_tags"].count("architecture"), 1)

    def test_no_preferences_default_and_nearest_zone(self):
        self.assertEqual(self.engine.generate_route(RouteRequest(180)).selected_zone, "wukang_fuxing_xujiahui")
        result = self.engine.generate_route(RouteRequest(180, start_lat=31.17, start_lng=121.46))
        self.assertEqual(result.selected_zone, "west_bund")

    def test_all_unknown_entry_data_warns_and_hours_do_not_filter(self):
        req = RouteRequest(120, must_go_poi_ids=["p13"], environment_preference="indoor", avoid_crowds=True)
        result = self.engine.generate_route(req)
        self.assert_valid_route(result, req)
        for code in ("entry_requirements_unverified: p13", "crowd_level_unknown: p13", "environment_preference_unfulfilled: p13"):
            self.assertTrue(any(code in w for w in result.warnings))
        req2 = RouteRequest(180, must_go_poi_ids=["p28"])
        self.assert_valid_route(self.engine.generate_route(req2), req2)

    def test_budget_grid_and_final_recomputation(self):
        for minutes in (15, 45, 60, 90, 120, 180, 300):
            for limit in (.01, .5, 2, 6):
                req = RouteRequest(minutes, interest_tags=["architecture"], max_walking_km=limit)
                result = self.engine.generate_route(req)
                if result.status == "success":
                    self.assert_valid_route(result, req)
                else:
                    self.assertEqual(result.ordered_pois, [])

    def test_config_controls_factor_speed_buffer_and_cap(self):
        raw = self.repo.get_raw_data()
        raw["route_engine_defaults"].update(walking_distance_factor=2, walking_speed_m_per_min=50,
                                            route_buffer_minutes=7, max_pois_default=1)
        other = write_repository(self, raw)
        req = RouteRequest(180, start_lat=31.22, start_lng=121.45, must_go_poi_ids=["p13"])
        result = RouteEngine(other).generate_route(req)
        self.assert_valid_route(result, req, other)
        self.assertEqual(len(result.ordered_pois), 1)
        self.assertEqual(result.buffer_minutes, 7)

    def test_must_go_can_exceed_five_stop_cap(self):
        raw = self.repo.get_raw_data()
        template = next(p for p in raw["pois"] if p["id"] == "p13")
        pois = []
        for i in range(6):
            p = copy.deepcopy(template)
            p["id"] = f"s{i}"
            p["visit_profile"]["modes"]["walk_stop"] = {"quick": 1, "standard": 1, "deep": 1}
            pois.append(p)
        other = write_repository(self, subset(raw, pois))
        req = RouteRequest(30, must_go_poi_ids=[p["id"] for p in pois])
        result = RouteEngine(other).generate_route(req)
        self.assert_valid_route(result, req, other)
        self.assertEqual(len(result.ordered_pois), 6)

    def test_reordered_dataset_produces_identical_results(self):
        raw = self.repo.get_raw_data()
        raw = subset(raw, list(reversed(raw["pois"])))
        other = write_repository(self, raw)
        req = RouteRequest(180, interest_tags=["architecture", "local_life"])
        a, b = self.engine.generate_route(req), RouteEngine(other).generate_route(req)
        self.assertEqual([n.poi_id for n in a.ordered_pois], [n.poi_id for n in b.ordered_pois])
        self.assertEqual(a.total_estimated_minutes, b.total_estimated_minutes)

    def test_heuristic_failure_does_not_claim_impossibility(self):
        raw = self.repo.get_raw_data()
        template = next(p for p in raw["pois"] if p["id"] == "p13")
        pois = []
        for i in range(9):
            p = copy.deepcopy(template)
            p["id"] = f"s{i}"
            p["location"]["lat"] = 31 + i * .01
            p["visit_profile"]["modes"]["walk_stop"] = {"quick": 1, "standard": 1, "deep": 1}
            pois.append(p)
        other = write_repository(self, subset(raw, pois))
        engine = RouteEngine(other)
        req = RouteRequest(200, start_lat=30.99, start_lng=template["location"]["lng"], must_go_poi_ids=[p["id"] for p in pois])
        with patch.object(engine, "_order_required", return_value=[engine.visits.resolve(p, req) for p in reversed(other.get_all_pois())]):
            result = engine.generate_route(req)
        self.assertEqual(result.status, "no_feasible_route_found")
        self.assertEqual(result.ordered_pois, [])
        self.assert_valid_route(engine.generate_route(req), req, other)

    def test_small_required_set_exact_fallback_recovers(self):
        raw = self.repo.get_raw_data()
        template = next(p for p in raw["pois"] if p["id"] == "p13")
        pois = []
        for i in range(3):
            p = copy.deepcopy(template)
            p["id"] = f"s{i}"
            p["location"]["lat"] = 31 + i * .01
            p["visit_profile"]["modes"]["walk_stop"] = {"quick": 1, "standard": 1, "deep": 1}
            pois.append(p)
        other = write_repository(self, subset(raw, pois))
        engine = RouteEngine(other)
        req = RouteRequest(80, start_lat=30.99, start_lng=template["location"]["lng"], must_go_poi_ids=[p["id"] for p in pois])
        with patch.object(engine, "_order_required", return_value=[engine.visits.resolve(p, req) for p in reversed(other.get_all_pois())]):
            result = engine.generate_route(req)
        self.assert_valid_route(result, req, other)

    def test_soft_preferences_break_equal_score_ties(self):
        raw = self.repo.get_raw_data()
        template = next(p for p in raw["pois"] if p["id"] == "p13")
        pois = []
        for pid, environment, crowd in (("s0", "outdoor", "low"), ("s1", "mixed", "medium"),
                                        ("s2", "indoor", "high"), ("s3", "indoor", None),
                                        ("s4", "indoor", "medium")):
            p = copy.deepcopy(template)
            p["id"] = pid
            p["planning"].update(environment=environment, crowd_level_default=crowd)
            p["visit_mode_details"]["walk_stop"]["environment"] = environment
            pois.append(p)
        data = subset(raw, pois)
        data["route_engine_defaults"]["max_pois_default"] = 1
        other = write_repository(self, data)
        engine = RouteEngine(other)
        result = engine.generate_route(RouteRequest(180, interest_tags=["architecture"], environment_preference="indoor", avoid_crowds=True))
        self.assertEqual(result.ordered_pois[0].id, "s4")
        mixed = engine.generate_route(RouteRequest(180, interest_tags=["architecture"], environment_preference="mixed", avoid_crowds=True))
        self.assertEqual(mixed.ordered_pois[0].id, "s0")
