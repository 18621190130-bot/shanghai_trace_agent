from .helpers import baseline_repository, PRE_PHASE2_5_PATH
import copy
import json
import re
import unittest
from pathlib import Path

from tools.demos.demo import EXAMPLES, render_plan
from src import POIRepository, RouteEngine, RouteRequest
from src.models import DataValidationError
from .helpers import subset, write_repository


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.repo = baseline_repository()
        self.engine = RouteEngine(self.repo)

    def selected_stop(self, pid, mode, pace="standard", **kwargs):
        request = RouteRequest(300, must_go_poi_ids=[pid], travel_pace=pace,
                               visit_mode_overrides={pid: mode}, **kwargs)
        result = self.engine.generate_route(request)
        self.assertEqual(result.status, "success", result.errors)
        return next(n for n in result.ordered_pois if n.poi_id == pid)

    def test_A_xujiahui_academy_standard_full_visit_30(self):
        self.assertEqual(self.selected_stop("p33", "full_visit").estimated_stay_minutes, 30)

    def test_B_nanjing_road_standard_full_visit_60(self):
        stop = self.selected_stop("p34", "full_visit")
        self.assertEqual(stop.estimated_stay_minutes, 60)
        self.assertEqual(stop.poi_type, "street")
        self.assertIs(stop.ticket_required, False)

    def test_C_xujiahui_district_standard_walk_stop_30(self):
        self.assertEqual(self.selected_stop("p35", "walk_stop").estimated_stay_minutes, 30)

    def test_D_xujiahui_district_standard_full_visit_90(self):
        self.assertEqual(self.selected_stop("p35", "full_visit").estimated_stay_minutes, 90)

    def test_E_yu_garden_standard_walk_stop_45(self):
        stop = self.selected_stop("p15", "walk_stop")
        self.assertEqual(stop.estimated_stay_minutes, 45)
        self.assertIs(stop.ticket_required, False)
        self.assertIn("excludes ticketed", stop.visit_scope)

    def test_F_yu_garden_standard_full_visit_90(self):
        stop = self.selected_stop("p15", "full_visit")
        self.assertEqual(stop.estimated_stay_minutes, 90)
        self.assertIs(stop.ticket_required, True)
        self.assertIn("plus surrounding", stop.visit_scope)

    def test_G_tank_standard_walk_stop_25(self):
        self.assertEqual(self.selected_stop("p29", "walk_stop").estimated_stay_minutes, 25)

    def test_H_tank_standard_full_visit_75(self):
        self.assertEqual(self.selected_stop("p29", "full_visit").estimated_stay_minutes, 75)

    def test_quick_and_deep_use_mode_specific_values(self):
        for pid, mode, quick, deep in (("p33", "full_visit", 15, 40),
                                      ("p35", "walk_stop", 20, 45),
                                      ("p35", "full_visit", 60, 150),
                                      ("p15", "walk_stop", 30, 60),
                                      ("p29", "full_visit", 45, 120)):
            with self.subTest(poi=pid, mode=mode):
                self.assertEqual(self.selected_stop(pid, mode, "quick").estimated_stay_minutes, quick)
                self.assertEqual(self.selected_stop(pid, mode, "deep").estimated_stay_minutes, deep)

    def test_default_mode_and_default_pace_are_used(self):
        for pid, expected_mode, expected_stay in (("p15", "walk_stop", 45), ("p29", "walk_stop", 25),
                                                ("p33", "full_visit", 30), ("p35", "walk_stop", 30)):
            result = self.engine.generate_route(RouteRequest(300, must_go_poi_ids=[pid]))
            stop = next(n for n in result.ordered_pois if n.poi_id == pid)
            self.assertEqual(stop.selected_visit_mode, expected_mode)
            self.assertEqual(stop.travel_pace, "standard")
            self.assertEqual(stop.estimated_stay_minutes, expected_stay)

    def test_closed_cathedral_falls_back_to_exterior(self):
        stop = self.selected_stop("p32", "full_visit", full_visit_unavailable_poi_ids=["p32"])
        self.assertEqual(stop.selected_visit_mode, "walk_stop")
        self.assertEqual(stop.estimated_stay_minutes, 20)
        self.assertEqual(stop.downgrade_reason, "full_visit_unavailable")

    def test_closure_without_fallback_does_not_drop_must_go(self):
        result = self.engine.generate_route(RouteRequest(180, must_go_poi_ids=["p33"], full_visit_unavailable_poi_ids=["p33"]))
        self.assertEqual(result.status, "infeasible")
        self.assertEqual(result.ordered_pois, [])
        self.assertEqual(result.request["must_go_poi_ids"], ["p33"])

    def test_closed_optional_only_full_visit_is_not_selected(self):
        req = copy.deepcopy(EXAMPLES["Route 1 — Architecture & Neighborhood Walk"])
        req.full_visit_unavailable_poi_ids = ["p33"]
        result = self.engine.generate_route(req)
        self.assertEqual(result.status, "success")
        self.assertNotIn("p33", [n.poi_id for n in result.ordered_pois])

    def test_declining_tickets_downgrades_known_ticketed_visit(self):
        stop = self.selected_stop("p15", "full_visit", willing_to_buy_tickets=False)
        self.assertEqual(stop.selected_visit_mode, "walk_stop")
        self.assertEqual(stop.downgrade_reason, "user_declines_ticket")
        self.assertEqual(stop.estimated_stay_minutes, 45)

    def test_free_full_visit_does_not_downgrade_when_tickets_declined(self):
        stop = self.selected_stop("p34", "full_visit", willing_to_buy_tickets=False)
        self.assertEqual(stop.selected_visit_mode, "full_visit")
        self.assertIsNone(stop.downgrade_reason)

    def test_short_budget_downgrades_full_visit_without_removing_must_go(self):
        request = RouteRequest(60, must_go_poi_ids=["p15"], visit_mode_overrides={"p15": "full_visit"})
        result = self.engine.generate_route(request)
        self.assertEqual(result.status, "success", result.errors)
        stop = next(n for n in result.ordered_pois if n.poi_id == "p15")
        self.assertEqual(stop.selected_visit_mode, "walk_stop")
        self.assertEqual(stop.downgrade_reason, "insufficient_time")
        self.assertEqual(result.total_estimated_minutes, 60)
        self.assertTrue(any("visit_mode_downgraded" in w for w in result.warnings))

    def test_downgrade_can_be_disabled_to_preserve_explicit_full_visit(self):
        result = self.engine.generate_route(RouteRequest(90, must_go_poi_ids=["p15"], visit_mode_overrides={"p15": "full_visit"}, allow_mode_downgrade=False))
        self.assertEqual(result.status, "infeasible")
        self.assertEqual(result.request["visit_mode_overrides"], {"p15": "full_visit"})

    def test_too_short_for_any_mode_is_proven_infeasible(self):
        result = self.engine.generate_route(RouteRequest(59, must_go_poi_ids=["p15"], visit_mode_overrides={"p15": "full_visit"}))
        self.assertEqual(result.status, "infeasible")

    def test_joint_required_mode_fallback_is_recomputed(self):
        request = RouteRequest(110, must_go_poi_ids=["p28", "p29"], visit_mode_overrides={"p28": "full_visit", "p29": "full_visit"})
        result = self.engine.generate_route(request)
        self.assertEqual(result.status, "success", result.errors)
        self.assertTrue({"p28", "p29"}.issubset({n.poi_id for n in result.ordered_pois}))
        self.assertLessEqual(result.total_estimated_minutes, 110)
        self.assertTrue(any(n.downgrade_reason for n in result.ordered_pois))
        self.assertEqual(result.total_stay_minutes, sum(n.estimated_stay_minutes for n in result.ordered_pois))

    def test_mode_and_pace_validation(self):
        invalid = [
            {"travel_pace": "slow"}, {"visit_mode_overrides": {"p15": "flexible"}},
            {"visit_mode_overrides": {"p33": "walk_stop"}}, {"visit_mode_overrides": {"p999": "walk_stop"}},
            {"visit_mode_overrides": ["walk_stop"]}, {"full_visit_unavailable_poi_ids": ["p999"]},
            {"full_visit_unavailable_poi_ids": "p32"}, {"willing_to_buy_tickets": "no"},
            {"allow_mode_downgrade": "yes"}, {"preferred_zone": "hengfu"},
            {"must_go_poi_ids": ["p1"]}, {"must_go_poi_ids": ["p22"]},
        ]
        for values in invalid:
            with self.subTest(values=values):
                result = self.engine.generate_route({"available_minutes": 180, **values})
                self.assertEqual(result.status, "validation_error")

    def test_final_data_ids_orders_types_and_zone_counts(self):
        pois = self.repo.get_all_pois()
        self.assertEqual(len(pois), 27)
        self.assertEqual([p.display_order for p in pois], list(range(1, 28)))
        self.assertEqual(set(p.id for p in pois), {"p2", "p4", "p5", "p7", "p9", "p10", "p11", "p12", "p13", "p14", "p15", "p16", "p20", "p21", "p23", "p24", "p25", "p26", "p27", "p28", "p29", "p30", "p31", "p32", "p33", "p34", "p35"})
        self.assertEqual({z: len(self.repo.get_pois_by_zone(z)) for z in self.repo.zone_order},
                         {"wukang_fuxing_xujiahui": 8, "old_city_central": 8, "hongkou_literary": 6, "west_bund": 5})
        self.assertEqual(self.repo.get_poi_by_id("p34").poi_type, "street")
        self.assertEqual(self.repo.get_poi_by_id("p35").poi_type, "district")
        self.assertEqual(self.repo.get_poi_by_id("p13").poi_type, "landmark")
        self.assertEqual(self.repo.get_poi_by_id("p28").poi_type, "venue")
        self.assertEqual(self.repo.get_poi_by_id("p16").poi_type, "park")

    def test_removed_legacy_fields_and_modes(self):
        for item in self.repo.get_raw_data()["pois"]:
            self.assertNotIn("recommended_stay", item["planning"])
            profile = item["visit_profile"]
            self.assertNotIn("flexible", profile["supported_modes"])
            self.assertIn(profile["default_mode"], profile["supported_modes"])
            self.assertEqual(set(profile["supported_modes"]), set(profile["modes"]))

    def test_area_anchor_is_used_for_distance_and_warned(self):
        for pid in ("p34", "p35"):
            raw = next(p for p in self.repo.get_raw_data()["pois"] if p["id"] == pid)
            self.assertIn("representative_lat", raw["location"])
            self.assertIn("representative_lng", raw["location"])
            self.assertNotIn("lat", raw["location"])
            result = self.engine.generate_route(RouteRequest(180, must_go_poi_ids=[pid]))
            self.assertEqual(result.status, "success")
            self.assertTrue(any(f"representative_coordinate: {pid}" in w for w in result.warnings))

    def test_profile_schema_corruption_is_rejected(self):
        mutations = [
            lambda r: r["pois"][0]["visit_profile"].update(default_mode="flexible"),
            lambda r: r["pois"][0]["visit_profile"].update(supported_modes=["walk_stop", "flexible"]),
            lambda r: r["pois"][0]["visit_profile"]["modes"]["walk_stop"].update(quick=0),
            lambda r: r["pois"][0]["visit_profile"]["modes"]["walk_stop"].update(standard=4),
            lambda r: r["pois"][0]["visit_profile"]["modes"].update(full_visit={"quick": 1, "standard": 2, "deep": 3}),
            lambda r: r["pois"][0].update(display_order=2),
            lambda r: r["pois"][0].update(poi_type="building"),
            lambda r: r["pois"][0]["planning"].update(recommended_stay={"min_minutes": 1, "max_minutes": 2}),
            lambda r: r["pois"][0]["location"].pop("representative_lat"),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                raw = self.repo.get_raw_data()
                mutate(raw)
                with self.assertRaises(DataValidationError):
                    write_repository(self, raw)

    def test_human_cli_render_does_not_show_internal_id_numbers(self):
        plan = self.engine.generate_route(EXAMPLES["Route 1 — Architecture & Neighborhood Walk"])
        rendered = render_plan("Route 1", plan, self.repo)
        self.assertIsNone(re.search(r"\bp\d+\b", rendered))
        self.assertIn("#", rendered)
        self.assertIn(plan.ordered_pois[0].name_zh, rendered)

    def test_five_manual_route_requests_and_no_cluster_backtracking(self):
        for name, request in EXAMPLES.items():
            with self.subTest(route=name):
                result = self.engine.generate_route(request)
                self.assertEqual(result.status, "success", result.errors)
                self.assertEqual(result.selected_zone, request.preferred_zone)
                self.assertLessEqual(result.total_estimated_minutes, request.available_minutes)
                for node in result.ordered_pois:
                    self.assertEqual(node.travel_pace, "standard")
                    self.assertEqual(node.estimated_stay_minutes, self.repo.get_poi_by_id(node.poi_id).visit_profile.stay_for(node.selected_visit_mode, "standard"))
                    self.assertTrue(set(node.matched_tags["interest_tags"]) & set(request.interest_tags))
                for node in result.to_dict()["ordered_pois"]:
                    self.assertIn("poi_id", node)
                    self.assertIn("display_order", node)
                    self.assertIn("selected_visit_mode", node)
                    self.assertIn("travel_pace", node)
                    self.assertEqual(node["estimated_distance_from_previous"], node["estimated_distance_from_previous_stop_km"])
                    self.assertEqual(node["estimated_walking_minutes_from_previous"], node["estimated_walking_minutes"])
                if name.startswith("Route 1"):
                    clusters = [n.poi_id in {"p32", "p33", "p35"} for n in result.ordered_pois]
                    self.assertLessEqual(sum(a != b for a, b in zip(clusters, clusters[1:])), 1)
                if name.startswith("Route 4"):
                    self.assertIn("p34", [n.poi_id for n in result.ordered_pois])
                if name.startswith("Route 5"):
                    self.assertIn("p35", [n.poi_id for n in result.ordered_pois])

    def test_richness_targets_are_soft_and_never_fill_with_unrelated_stops(self):
        for minutes, expected in ((90, (2, 3)), (91, (3, 4)), (150, (3, 4)), (151, (4, 5)), (240, (4, 5))):
            result = self.engine.generate_route(RouteRequest(minutes, interest_tags=["religion"], preferred_zone="wukang_fuxing_xujiahui"))
            self.assertEqual(result.status, "success")
            self.assertEqual((result.richness_target["min_stops"], result.richness_target["max_stops"]), expected)
            self.assertEqual([n.poi_id for n in result.ordered_pois], ["p32"])
            self.assertIs(result.richness_target_met, False)
            self.assertTrue(any("richness_target_unmet" in w for w in result.warnings))

    def test_same_data_and_requests_are_deterministic_five_times(self):
        for request in EXAMPLES.values():
            results = [self.engine.generate_route(request).to_dict() for _ in range(5)]
            self.assertTrue(all(p == results[0] for p in results))

    def test_pending_alternative_times_are_marked_in_output(self):
        result = self.engine.generate_route(RouteRequest(300, must_go_poi_ids=["p7"], visit_mode_overrides={"p7": "full_visit"}))
        self.assertEqual(result.status, "success")
        self.assertTrue(any("visit_time_pending_manual_calibration: p7 full_visit" in w for w in result.warnings))
