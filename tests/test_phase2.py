from .helpers import baseline_repository, PRE_PHASE2_5_PATH
import copy
import io
import itertools
import json
import os
import subprocess
import sys
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from src import POIRepository, RouteEntryService, RouteIntent, RouteMode, intent_to_route_request
from src.geo_utils import haversine_km
from src.intent_models import FeasibilityAction
from src.intent_schema import candidate_schema, route_intent_schema, CLARIFICATION_SCHEMA, validate_json
from src.llm_client import MockLLMClient, DeepSeekLLMClient, LLMClientError
from src.mock_examples import PLAN_EXAMPLES, candidate
from src.models import RequestValidationError
from .helpers import write_repository

ROOT = Path(__file__).resolve().parents[1]


class Phase2Tests(unittest.TestCase):
    def setUp(self):
        self.network_guard = patch("urllib.request.urlopen", side_effect=AssertionError("Tests must not use live API"))
        self.network_guard.start()
        self.addCleanup(self.network_guard.stop)
        self.repo = baseline_repository()
        self.client = MockLLMClient(fixtures=PLAN_EXAMPLES)
        self.service = RouteEntryService(self.repo, self.client)

    def assert_budget(self, result):
        self.assertIn(result.status, ("success", "needs_route_quality_clarification"), result.errors)
        if result.status == "needs_route_quality_clarification":
            self.assertLess(len(result.route_plan.ordered_pois), 3)
        plan = result.route_plan
        self.assertLessEqual(plan.total_estimated_minutes, result.intent.available_minutes)
        self.assertTrue(set(result.intent.must_go_poi_ids).issubset(n.poi_id for n in plan.ordered_pois))
        previous = None if result.intent.start_lat is None else (result.intent.start_lat, result.intent.start_lng)
        distance, stays = 0, 0
        for stop in plan.ordered_pois:
            coordinates = self.repo.get_poi_by_id(stop.poi_id).coordinates
            if previous is not None:
                distance += haversine_km(previous, coordinates) * self.repo.defaults["walking_distance_factor"]
            stays += self.repo.get_poi_by_id(stop.poi_id).visit_profile.stay_for(stop.selected_visit_mode, result.intent.travel_pace)
            previous = coordinates
        expected = stays + distance * 1000 / self.repo.defaults["walking_speed_m_per_min"] + self.repo.defaults["route_buffer_minutes"]
        self.assertAlmostEqual(plan.total_estimated_minutes, expected)

    def test_P1_architecture_natural_language_fixture(self):
        intent = self.service.parse_plan(next(iter(PLAN_EXAMPLES)))
        self.assertEqual(intent.available_minutes, 180)
        self.assertEqual(intent.interest_tags, ["architecture", "local_life"])
        self.assert_budget(self.service.generate(intent))

    def test_P2_vague_text_needs_two_questions_and_no_engine(self):
        intent = self.service.parse_plan("Plan a walk for me.")
        with patch.object(self.service.engine, "generate_route", side_effect=AssertionError("Not ready")):
            result = self.service.generate(intent)
        self.assertEqual(result.status, "needs_clarification")
        self.assertEqual(intent.missing_fields, ["available_minutes", "interest_tags"])
        self.assertEqual(len(intent.clarification_requests), 2)

    def test_P3_literary_neighborhood(self):
        intent = self.service.parse_plan("I want a relaxed literary walk around Lu Xun's neighborhood for two hours.")
        self.assertEqual(intent.available_minutes, 120)
        self.assertIn("literature", intent.interest_tags)
        self.assertEqual(intent.preferred_zone, "hongkou_literary")
        self.assert_budget(self.service.generate(intent))

    def test_missing_time_only(self):
        intent = self.service.parse_plan("I want to see old Shanghai.")
        self.assertEqual(intent.missing_fields, ["available_minutes"])

    def test_missing_interests_only(self):
        intent = self.service.parse_plan("I have three hours.")
        self.assertEqual(intent.missing_fields, ["interest_tags"])

    def test_plan_experience_or_culture_satisfies_interest_requirement(self):
        for fields in ({"experience_tags": ["quiet_walk"]}, {"culture_tags": ["literary_shanghai"]}):
            intent = RouteIntent(RouteMode.PLAN_FOR_ME, available_minutes=120, **fields)
            self.assertFalse(self.service.clarification.prepare(intent).needs_clarification)

    def test_omitted_plan_start_is_optional(self):
        result = self.service.generate(RouteIntent(RouteMode.PLAN_FOR_ME, available_minutes=120, interest_tags=["architecture"]))
        self.assert_budget(result)
        self.assertIsNone(result.intent.start_lat)

    def test_pace_extraction(self):
        cases = [("I just want the highlights for two hours, focused on architecture.", "quick"),
                 ("I have three hours and want to take my time and understand the history.", "deep")]
        for text, pace in cases:
            self.assertEqual(self.service.parse_plan(text).travel_pace, pace)

    def test_prompt_contains_dynamic_vocabulary_and_extraction_boundary(self):
        prompt = self.service.parser.system_prompt()
        self.assertIn("Never choose POIs", prompt)
        for group in self.repo.taxonomy.values():
            self.assertTrue(all(t in prompt for t in group))

    def test_invalid_tag_is_retried_then_rejected(self):
        bad = candidate(interest_tags=["historic_vibes"])
        client = MockLLMClient(responses=[bad, bad])
        service = RouteEntryService(self.repo, client)
        with self.assertRaises(RequestValidationError):
            service.parse_plan("anything")
        self.assertEqual(len(client.calls), 2)
        self.assertIsNotNone(client.calls[-1]["validation_feedback"])

    def test_invalid_json_retry_recovers(self):
        client = MockLLMClient(responses=["not JSON", json.dumps(candidate(available_minutes=120, interest_tags=["art"]))])
        result = RouteEntryService(self.repo, client).parse_plan("anything")
        self.assertEqual(result.interest_tags, ["art"])
        self.assertEqual(len(client.calls), 2)

    def test_llm_cannot_invent_coordinates_route_fields_or_unsupported_preferences(self):
        for field in ("start_lat", "route", "avoid_crowds", "ticket_preference", "must_go_poi_ids"):
            bad = candidate(**{field: 1})
            service = RouteEntryService(self.repo, MockLLMClient(responses=[bad, bad]))
            with self.subTest(field=field), self.assertRaises(RequestValidationError):
                service.parse_plan("anything")

    def test_llm_explicit_place_names_resolve_and_unknown_names_reject(self):
        valid = candidate(available_minutes=180, interest_tags=["architecture"], must_go_place_names=["Wukang Mansion"])
        service = RouteEntryService(self.repo, MockLLMClient(responses=[valid]))
        self.assertEqual(service.parse_plan("I want Wukang Mansion").must_go_poi_ids, ["p13"])
        bad = candidate(must_go_place_names=["Invented Museum"])
        service = RouteEntryService(self.repo, MockLLMClient(responses=[bad, bad]))
        with self.assertRaises(RequestValidationError):
            service.parse_plan("anything")

    def test_provider_failure_does_not_retry_indefinitely(self):
        with patch.object(self.client, "structured_parse", side_effect=LLMClientError("offline")) as call:
            with self.assertRaises(LLMClientError):
                self.service.parse_plan("anything")
        self.assertEqual(call.call_count, 1)

    def test_empty_natural_language_rejected_without_provider(self):
        with self.assertRaises(RequestValidationError):
            self.service.parse_plan(" ")
        self.assertEqual(self.client.calls, [])

    def test_schema_rejects_bad_types_missing_properties_and_nonfinite_numbers(self):
        cases = [candidate(available_minutes=True), candidate(travel_pace="relaxed"),
                 candidate(max_walking_km=float("nan")), candidate(interest_tags="art"),
                 candidate(preferred_zone="Shanghai"), {}]
        for value in cases:
            with self.subTest(value=value), self.assertRaises(RequestValidationError):
                validate_json(value, candidate_schema(self.repo))

    def test_intent_schema_roundtrip_and_unknown_field_rejection(self):
        intent = self.service.parse_plan("Plan a walk for me.")
        data = intent.to_dict()
        validate_json(data, route_intent_schema(self.repo))
        self.assertEqual(RouteIntent.from_dict(data).to_dict(), data)
        for q in intent.clarification_requests:
            validate_json(asdict(q), CLARIFICATION_SCHEMA)
        data["realtime_weather"] = "rain"
        with self.assertRaises(RequestValidationError):
            self.service.generate(data)

    def test_clarification_options_come_from_taxonomy(self):
        intent = self.service.parse_plan("I have three hours.")
        choices = intent.clarification_requests[0].options
        self.assertEqual([o.value for o in choices], list(self.repo.taxonomy["interest_tags"]))

    def test_clarification_answer_rebuilds_and_routes_immediately(self):
        initial = self.service.parse_plan("Plan a walk for me.")
        updated = self.service.clarification.answer(initial, {"available_minutes": 180, "interest_tags": ["architecture", "local_life"]})
        self.assertFalse(updated.needs_clarification)
        self.assert_budget(self.service.generate(updated))
        self.assertIsNone(initial.available_minutes)

    def test_clarification_rejects_unknown_answer_field_invalid_tags_and_too_many_choices(self):
        intent = self.service.parse_plan("Plan a walk for me.")
        for answers in ({"ticket_preference": False}, {"interest_tags": ["unknown"]},
                        {"interest_tags": list(self.repo.taxonomy["interest_tags"])[:4]}, {"available_minutes": 0}):
            with self.subTest(answers=answers), self.assertRaises(RequestValidationError):
                self.service.clarification.answer(intent, answers)

    def test_two_questions_maximum_with_all_surprise_fields_missing(self):
        result = self.service.generate(RouteIntent(RouteMode.SURPRISE_ME))
        self.assertEqual(result.intent.missing_fields, ["available_minutes", "start_location_text"])
        self.assertEqual(len(result.intent.clarification_requests), 2)

    def test_surprise_missing_time_never_asks_interests(self):
        result = self.service.generate(RouteIntent(RouteMode.SURPRISE_ME, start_location_text="West Bund"))
        self.assertEqual(result.intent.missing_fields, ["available_minutes"])

    def test_location_names_chinese_english_alias_and_zone(self):
        for value in ("武康大楼", "Wukang Mansion"):
            self.assertEqual(self.service.resolver.resolve(value).poi_id, "p13")
        for raw in self.repo.get_raw_data()["pois"]:
            for alias in raw["name"].get("aliases", []):
                self.assertIsNotNone(self.service.resolver.resolve(alias).coordinates)
        for zone in self.repo.get_raw_data()["metadata"]["walk_zones"]:
            self.assertEqual(self.service.resolver.resolve(zone["name_en"]).zone_id, zone["id"])

    def test_unresolved_location_never_geocodes_or_fakes_start(self):
        result = self.service.generate(RouteIntent(RouteMode.SURPRISE_ME, start_location_text="People's Square", available_minutes=180))
        self.assertEqual(result.status, "needs_clarification")
        self.assertIsNone(result.intent.start_lat)
        self.assertIn("unresolved_external_location", " ".join(result.warnings))

    def test_known_explicit_plan_start_resolves_and_unknown_requires_clarification(self):
        for text, expected in (("Wukang Mansion", "success"), ("123 Unknown Street", "needs_clarification")):
            result = self.service.generate(RouteIntent(RouteMode.PLAN_FOR_ME, start_location_text=text,
                available_minutes=180, interest_tags=["architecture"]))
            self.assertEqual(result.status, expected)

    def test_start_coordinates_validation(self):
        for fields in ({"start_lat": 31.2}, {"start_lat": 100, "start_lng": 121},
                       {"start_lat": 31, "start_lng": float("inf")}, {"start_coordinate_system": "BD09"}):
            with self.subTest(fields=fields), self.assertRaises(RequestValidationError):
                self.service.generate(RouteIntent(RouteMode.SURPRISE_ME, available_minutes=180, **fields))

    def test_M1_must_go_feasible_and_optional_stops_added_without_llm(self):
        intent = self.service.places_intent(["Wukang Mansion", "Jianyeli"], 180)
        result = self.service.generate(intent)
        self.assertTrue(result.feasibility.feasible)
        self.assert_budget(result)
        self.assertGreater(len(result.route_plan.ordered_pois), 2)
        self.assertEqual(self.client.calls, [])

    def test_M2_cross_zone_rejected_original_selection_preserved_no_engine(self):
        intent = self.service.places_intent(["Wukang Mansion", "Yu Garden", "Lu Xun Park"], 120)
        original = intent.to_dict()
        with patch.object(self.service.engine, "generate_route", side_effect=AssertionError("Preflight must block")):
            result = self.service.generate(intent)
        self.assertFalse(result.feasibility.feasible)
        self.assertTrue(result.feasibility.cross_zone_required)
        self.assertFalse(result.feasibility.walking_only_feasible)
        self.assertEqual(intent.to_dict(), original)
        self.assertEqual(result.intent.must_go_poi_ids, ["p13", "p15", "p16"])
        self.assertEqual({s.action for s in result.feasibility.suggestions}, set(FeasibilityAction))

    def test_M3_subsets_only_after_help_and_confirmation(self):
        intent = self.service.places_intent(["Wukang Mansion", "Yu Garden", "Lu Xun Park"], 120)
        for action in (None, FeasibilityAction.EDIT_PLACES, FeasibilityAction.EXTEND_TIME):
            with self.assertRaises(RequestValidationError):
                self.service.feasibility.suggest_subsets(intent, action)
        proposals = self.service.feasibility.suggest_subsets(intent, FeasibilityAction.HELP_ME_CHOOSE, ["p13"])
        self.assertTrue(proposals)
        proposal = proposals[0]
        with self.assertRaises(RequestValidationError):
            self.service.feasibility.confirm_subset(intent, proposal)
        self.assertEqual(len(intent.must_go_poi_ids), 3)
        confirmed = self.service.feasibility.confirm_subset(intent, proposal, confirmed=True)
        self.assert_budget(self.service.generate(confirmed))
        self.assertEqual(len(intent.must_go_poi_ids), 3)

    def test_stale_and_forged_subset_rejected(self):
        intent = self.service.places_intent(["Wukang Mansion", "Yu Garden", "Lu Xun Park"], 120)
        proposal = self.service.feasibility.suggest_subsets(intent, FeasibilityAction.HELP_ME_CHOOSE)[0]
        stale = copy.deepcopy(intent)
        stale.available_minutes = 1
        with self.assertRaises(RequestValidationError):
            self.service.feasibility.confirm_subset(stale, proposal, confirmed=True)
        proposal.keep_poi_ids = ["p35"]
        with self.assertRaises(RequestValidationError):
            self.service.feasibility.confirm_subset(intent, proposal, confirmed=True)

    def test_feasibility_shortest_order_matches_independent_permutations(self):
        intent = self.service.places_intent(["Wukang Mansion", "Jianyeli", "Xintiandi North Block (Shikumen)"], 600)
        check = self.service.feasibility.check(intent)
        pois = [self.repo.get_poi_by_id(pid) for pid in intent.must_go_poi_ids]
        exact = min(sum(haversine_km(a.coordinates, b.coordinates) for a,b in zip(order,order[1:]))
                    for order in itertools.permutations(pois)) * self.repo.defaults["walking_distance_factor"]
        self.assertAlmostEqual(check.estimated_distance_km, exact)
        self.assertTrue(check.minimum_is_exact)
        minimum_stay = sum(min(p.visit_profile.stay_for(m,"standard") for m in p.visit_profile.supported_modes) for p in pois)
        self.assertAlmostEqual(check.estimated_minimum_minutes, minimum_stay + exact*1000/self.repo.defaults["walking_speed_m_per_min"] + self.repo.defaults["route_buffer_minutes"])

    def test_feasibility_accounts_for_start_and_distance_cap(self):
        intent = self.service.places_intent(["Wukang Mansion"], 180, start_location_text="徐家汇天主堂", max_walking_km=.1)
        check = self.service.feasibility.check(intent)
        self.assertGreater(check.estimated_distance_km, .1)
        self.assertFalse(check.feasible)

    def test_missing_coordinate_preflight_has_unknown_estimates(self):
        raw = self.repo.get_raw_data()
        next(p for p in raw["pois"] if p["id"] == "p13")["location"]["lat"] = None
        service = RouteEntryService(write_repository(self, raw))
        result = service.generate(service.places_intent(["Wukang Mansion"], 180))
        self.assertEqual(result.status, "missing_coordinates")
        self.assertIsNone(result.feasibility.estimated_minimum_minutes)

    def test_large_required_set_is_not_claimed_exact(self):
        intent = self.service.places_intent([p.id for p in self.repo.get_all_pois()[:13]], 2000)
        check = self.service.feasibility.check(intent)
        self.assertFalse(check.minimum_is_exact)
        self.assertGreaterEqual(check.estimated_candidate_minutes, check.estimated_minimum_minutes)

    def test_places_without_preferences_do_not_require_time_or_interest(self):
        intent = self.service.places_intent(["Wukang Mansion"])
        # Current Places in mind no longer requires a duration selection.
        self.assertEqual(intent.missing_fields, [])

    def test_display_selection_cross_zone_and_invalid_selection(self):
        intent = self.service.places_intent([9, 11, 12], 120)
        self.assertEqual(set(intent.must_go_poi_ids), {"p13", "p15", "p16"})
        with self.assertRaises(RequestValidationError):
            self.service.places_intent([999], 120)

    def test_S1_west_bund_single_zone_with_budget_and_no_llm(self):
        result = self.service.generate(RouteIntent(RouteMode.SURPRISE_ME, start_location_text="West Bund", available_minutes=180))
        self.assert_budget(result)
        self.assertEqual({n.walk_zone for n in result.route_plan.ordered_pois}, {"west_bund"})
        self.assertIn(result.surprise_theme, ("Art & Industrial Heritage", "Riverside Walk"))
        self.assertEqual(self.client.calls, [])

    def test_S2_hongkou_literary(self):
        result = self.service.generate(RouteIntent(RouteMode.SURPRISE_ME, start_location_text="Hongkou", available_minutes=120))
        self.assert_budget(result)
        self.assertEqual(result.surprise_theme, "Literary Shanghai")
        self.assertEqual(result.route_plan.selected_zone, "hongkou_literary")

    def test_S3_seed_and_inputs_repeat_five_times(self):
        intent = RouteIntent(RouteMode.SURPRISE_ME, start_location_text="West Bund", available_minutes=180, surprise_seed=42)
        values = [self.service.generate(intent).to_dict() for _ in range(5)]
        self.assertTrue(all(v == values[0] for v in values))
        self.assertEqual(intent.interest_tags, [])

    def test_surprise_excludes_unreachable_and_tiny_budget(self):
        for intent in (RouteIntent(RouteMode.SURPRISE_ME, start_lat=0, start_lng=0, available_minutes=90),
                       RouteIntent(RouteMode.SURPRISE_ME, start_location_text="West Bund", available_minutes=1)):
            result = self.service.generate(intent)
            self.assertEqual(result.status, "needs_route_quality_clarification")
            self.assertEqual(result.route_plan.ordered_pois, [])

    def test_surprise_respects_distance_budget(self):
        result = self.service.generate(RouteIntent(RouteMode.SURPRISE_ME, start_location_text="West Bund", available_minutes=180, max_walking_km=.001))
        if result.status == "success":
            self.assertLessEqual(result.route_plan.total_estimated_distance_km, .001)
        else:
            self.assertEqual(result.status, "needs_route_quality_clarification")

    def test_theme_config_invalid_tag_rejected(self):
        import tempfile
        from src.surprise_policy import SurpriseRoutePolicy
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"themes.json"
            path.write_text(json.dumps({"themes":[{"name":"Bad","zones":["west_bund"],"interest_tags":["new_tag"],"experience_tags":[],"culture_tags":[]}]}))
            with self.assertRaises(RequestValidationError):
                SurpriseRoutePolicy(self.repo,self.service.engine,path)

    def test_shared_adapter_preserves_all_executable_fields_and_copies_lists(self):
        for mode in RouteMode:
            intent = RouteIntent(mode, available_minutes=180, interest_tags=["architecture"],
                must_go_poi_ids=["p13"], start_lat=31.2, start_lng=121.4, travel_pace="quick",
                preferred_zone="wukang_fuxing_xujiahui", max_walking_km=5, visit_mode_overrides={"p13":"walk_stop"})
            request = intent_to_route_request(intent)
            self.assertEqual(request.travel_pace, "quick")
            self.assertEqual(request.visit_mode_overrides, {"p13":"walk_stop"})
            request.must_go_poi_ids.clear()
            self.assertEqual(intent.must_go_poi_ids, ["p13"])

    def test_adapter_refuses_incomplete_intent(self):
        with self.assertRaises(RequestValidationError):
            intent_to_route_request(self.service.parse_plan("Plan a walk for me."))

    def test_adapter_cannot_bypass_mode_minimums_with_false_clarification_flag(self):
        for mode in RouteMode:
            with self.subTest(mode=mode), self.assertRaises(RequestValidationError):
                intent_to_route_request(RouteIntent(mode, available_minutes=180))

    def test_deepseek_missing_key_has_clear_error_and_no_network(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(LLMClientError):
            DeepSeekLLMClient().structured_parse(system_prompt="json",user_text="hello",schema={})

    def test_deepseek_request_contract_mocked_no_secret_output(self):
        response = io.BytesIO(json.dumps({"choices":[{"finish_reason":"stop","message":{"content":"{}"}}]}).encode())
        with patch.dict(os.environ,{"DEEPSEEK_API_KEY":"test-only-not-a-real-key"}), patch("urllib.request.urlopen",return_value=response) as call:
            self.assertEqual(DeepSeekLLMClient().structured_parse(system_prompt="json",user_text="hello",schema={}),"{}")
        request = call.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["response_format"], {"type":"json_object"})
        self.assertEqual(payload["messages"][1]["content"],"hello")
        self.assertEqual(call.call_args.kwargs["timeout"],30)
        self.assertNotIn("test-only",json.dumps(payload))

    def test_cli_noninteractive_all_three_modes_and_no_network(self):
        cases = [(["--mode","plan_for_me","--text",next(iter(PLAN_EXAMPLES))],0,"success"),
                 (["--mode","places_in_mind","--places","Wukang Mansion;Jianyeli","--minutes","180"],0,"success"),
                 (["--mode","places_in_mind","--places","Wukang Mansion;Yu Garden;Lu Xun Park","--minutes","120"],1,"transfer_required"),
                 (["--mode","surprise_me","--start","West Bund","--minutes","180"],0,"success"),
                 (["--mode","plan_for_me","--text","Plan a walk for me."],0,"needs_clarification")]
        for args, code, status in cases:
            process = subprocess.run([sys.executable,"tools/demos/route_entry_demo.py",*args,"--json"],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",env={**os.environ,"PYTHONIOENCODING":"utf-8"},timeout=20)
            self.assertEqual(process.returncode,code,process.stderr)
            self.assertEqual(json.loads(process.stdout)["status"],status)

    def test_cli_interactive_clarification_and_subset_confirmation(self):
        cases = [("1\nPlan a walk for me.\n3\n1\n", "Status: success", []),
                 # Supply an explicit optional budget to exercise subset confirmation;
                 # Places in mind no longer asks the old duration clarification.
                 ("2\nWukang Mansion;Yu Garden;Lu Xun Park\n2\n1\nyes\n", "Status: success", ["--minutes", "120"]),
                 ("3\nWest Bund\n3\n", "Surprise Theme:", [])]
        for text, expected, args in cases:
            process = subprocess.run([sys.executable,"tools/demos/route_entry_demo.py",*args],input=text,cwd=ROOT,capture_output=True,text=True,encoding="utf-8",env={**os.environ,"PYTHONIOENCODING":"utf-8"},timeout=20)
            self.assertEqual(process.returncode,0,process.stderr)
            self.assertIn(expected,process.stdout)


if __name__ == "__main__":
    unittest.main()
