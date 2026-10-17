from .helpers import baseline_repository, PRE_PHASE2_5_PATH
import copy
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from src import POIRepository, RouteEngine, RouteRequest, RouteEntryService, RouteIntent, RouteMode, intent_to_route_request
from src.intent_schema import candidate_schema, route_intent_schema, validate_json
from src.llm_client import MockLLMClient
from src.mock_examples import PLAN_EXAMPLES, candidate
from src.models import RequestValidationError
from tools.demos.route_entry_demo import main, render_intent, render_result
from .helpers import write_repository, subset

ROOT = Path(__file__).resolve().parents[1]
AUTHENTIC = "I want to see the more authentic side of Shanghai."
NO_MUSEUMS = "I have two and a half hours. I want local neighborhoods and I'd rather avoid museums."


class RepairTests(unittest.TestCase):
    def setUp(self):
        guard = patch("urllib.request.urlopen", side_effect=AssertionError("No live network in tests"))
        guard.start()
        self.addCleanup(guard.stop)
        self.repo = baseline_repository()
        self.client = MockLLMClient(fixtures=PLAN_EXAMPLES)
        self.service = RouteEntryService(self.repo, self.client)
        self.engine = RouteEngine(self.repo)

    def test_case_A_time_answer_preserves_existing_preferences_and_routes(self):
        initial = self.service.parse_plan(AUTHENTIC)
        merged = self.service.answer_clarification(initial, "available_minutes", "3 hours")
        self.assertEqual(merged.available_minutes, 180)
        self.assertIn("local_life", merged.interest_tags)
        self.assertFalse(merged.needs_clarification)
        self.assertEqual(self.service.generate(merged).status, "success")
        self.assertEqual(len(self.client.calls), 1)
        self.assertIsNone(initial.available_minutes)

    def test_case_B_two_answers_merge_without_deleting_time(self):
        initial = self.service.parse_plan("Plan a walk for me.")
        self.assertLessEqual(len(initial.clarification_requests), 2)
        timed = self.service.answer_clarification(initial, "available_minutes", "3 hours")
        self.assertEqual(timed.missing_fields, ["interest_tags"])
        merged = self.service.answer_clarification(timed, "interest_tags", "parks and local life")
        self.assertEqual(merged.available_minutes, 180)
        self.assertEqual(set(merged.interest_tags), {"parks", "local_life"})
        self.assertFalse(merged.needs_clarification)
        self.assertEqual(self.service.generate(merged).status, "success")

    def test_natural_language_answer_patch_does_not_erase_other_fields(self):
        initial = self.service.clarification.prepare(RouteIntent(RouteMode.PLAN_FOR_ME,
            interest_tags=["local_life"], experience_tags=["neighborhood_walk"], culture_tags=["lane_life"],
            preferred_zone="wukang_fuxing_xujiahui", travel_pace="quick", max_walking_km=4,
            avoid_tags=["museum_visit"], avoid_poi_ids=["p5"]))
        client = MockLLMClient(responses=[candidate(available_minutes=180)])
        service = RouteEntryService(self.repo, client)
        merged = service.answer_clarification(initial, "available_minutes", "three hours should be fine")
        for field in ("interest_tags", "experience_tags", "culture_tags", "preferred_zone", "travel_pace", "max_walking_km", "avoid_tags", "avoid_poi_ids"):
            self.assertEqual(getattr(merged, field), getattr(initial, field))
        self.assertEqual(merged.available_minutes, 180)
        self.assertEqual(len(client.calls), 1)

    def test_new_explicit_avoidance_in_clarification_is_merged(self):
        initial = self.service.clarification.prepare(RouteIntent(RouteMode.PLAN_FOR_ME, available_minutes=150))
        client = MockLLMClient(responses=[candidate(interest_tags=["local_life"], avoid_tags=["museum_visit"])])
        merged = RouteEntryService(self.repo, client).answer_clarification(initial, "interest_tags", "Local neighborhoods but no museums please")
        self.assertEqual(merged.available_minutes, 150)
        self.assertEqual(merged.avoid_tags, ["museum_visit"])

    def test_invalid_answer_preserves_intent_and_required_question(self):
        initial = self.service.parse_plan(AUTHENTIC)
        before = initial.to_dict()
        with self.assertRaises(RequestValidationError):
            self.service.answer_clarification(initial, "available_minutes", "0")
        self.assertEqual(initial.to_dict(), before)
        self.assertTrue(initial.needs_clarification)

    def test_time_answer_units_and_menu_compatibility(self):
        initial = self.service.parse_plan(AUTHENTIC)
        for text, minutes in (("3",180),("180",180),("3 hours",180),("2.5 hours",150),("90 minutes",90)):
            self.assertEqual(self.service.answer_clarification(initial, "available_minutes", text).available_minutes, minutes)

    def test_negative_preferences_extracted_from_validated_candidates(self):
        result = self.service.parse_plan(NO_MUSEUMS)
        self.assertEqual(result.available_minutes, 150)
        self.assertEqual(result.avoid_tags, ["museum_visit"])
        self.assertIn("local_life", result.interest_tags)
        client = MockLLMClient(responses=[candidate(available_minutes=150, interest_tags=["local_life"], avoid_tags=["history"], avoid_place_names=["Wukang Mansion"])])
        intent = RouteEntryService(self.repo,client).parse_plan("Local life, nothing historical, and skip Wukang Mansion.")
        self.assertEqual(intent.avoid_poi_ids,["p13"])
        self.assertEqual(intent.avoid_tags,["history"])

    def test_avoidance_schema_rejects_unknown_ids_tags_and_wrong_types(self):
        intent = self.service.parse_plan(NO_MUSEUMS).to_dict()
        validate_json(intent, route_intent_schema(self.repo))
        for field, value in (("avoid_tags",["touristy"]),("avoid_poi_ids",["p999"]),("avoid_tags","history"),("avoid_poi_ids",[1])):
            bad = {**intent,field:value}
            with self.subTest(field=field,value=value), self.assertRaises(RequestValidationError):
                self.service.generate(bad)
        with self.assertRaises(RequestValidationError):
            validate_json(candidate(avoid_tags=["crowded"]),candidate_schema(self.repo))

    def test_avoidance_passes_through_the_one_adapter(self):
        for mode in RouteMode:
            intent = RouteIntent(mode, available_minutes=150, start_lat=31.2, start_lng=121.4,
                interest_tags=["local_life"], must_go_poi_ids=["p13"], avoid_tags=["history"], avoid_poi_ids=["p5"])
            request = intent_to_route_request(intent)
            self.assertEqual(request.avoid_tags,["history"])
            self.assertEqual(request.avoid_poi_ids,["p5"])
            request.avoid_tags.clear()
            self.assertEqual(intent.avoid_tags,["history"])

    def test_engine_rejects_invalid_negative_request(self):
        for fields in ({"avoid_tags":["touristy"]},{"avoid_poi_ids":["p999"]},{"avoid_tags":"history"}):
            self.assertEqual(self.engine.generate_route(RouteRequest(180,**fields)).status,"validation_error")

    def test_optional_avoided_pois_never_enter_route(self):
        request = RouteRequest(180,interest_tags=["local_life"],avoid_tags=["museum_visit"],avoid_poi_ids=["p33"])
        plan = self.engine.generate_route(request)
        self.assertEqual(plan.status,"success")
        for node in plan.ordered_pois:
            p=self.repo.get_poi_by_id(node.poi_id)
            self.assertNotEqual(p.id,"p33")
            self.assertNotIn("museum_visit",[*p.interest_tags,*p.experience_tags,*p.culture_tags])

    def test_must_go_wins_against_avoid_tag_and_id(self):
        req=RouteRequest(180,must_go_poi_ids=["p14"],avoid_poi_ids=["p14"],avoid_tags=["iconic_landmark"])
        plan=self.engine.generate_route(req)
        self.assertEqual(plan.status,"success")
        self.assertIn("p14",[n.poi_id for n in plan.ordered_pois])
        self.assertTrue(any("negative_preference_overridden_by_must_go: p14" in w for w in plan.warnings))

    def test_unresolved_negative_preferences_warn_without_fake_data(self):
        phrase="avoid crowded and touristy places"
        client=MockLLMClient(responses=[candidate(available_minutes=150,interest_tags=["local_life"],unresolved_negative_preferences=[phrase])])
        service=RouteEntryService(self.repo,client)
        intent=service.parse_plan("I want local life but avoid crowded and touristy places for 150 minutes.")
        self.assertEqual(intent.avoid_tags,[])
        self.assertEqual(intent.avoid_poi_ids,[])
        result=service.generate(intent)
        self.assertTrue(any("cannot be enforced" in w for w in result.warnings))
        for field in ("crowd_level","touristy_score","popularity_score","avoid_crowds"):
            self.assertNotIn(field,intent.to_dict())
        self.assertEqual(self.repo.get_raw_data(),baseline_repository().get_raw_data())

    def test_positive_local_life_does_not_infer_avoidances(self):
        intent=self.service.parse_plan(AUTHENTIC)
        self.assertEqual(intent.avoid_tags,[])
        self.assertEqual(intent.avoid_poi_ids,[])
        self.assertIn("ONLY when explicitly expressed",self.service.parser.system_prompt())

    def test_150_local_life_preserves_quality_without_exceeding_constraints(self):
        req=RouteRequest(150,interest_tags=["local_life"],max_walking_km=10)
        plan=self.engine.generate_route(req)
        self.assertEqual(plan.status,"success")
        self.assertNotIn("p33", [n.poi_id for n in plan.ordered_pois])
        self.assertTrue(any("Limited matching POIs" in w for w in plan.warnings))
        self.assertLessEqual(plan.time_utilization_ratio,.95)
        self.assertAlmostEqual(plan.time_utilization_ratio,plan.total_estimated_minutes/150)
        self.assertLessEqual(len(plan.ordered_pois),4)
        self.assertLessEqual(plan.total_estimated_distance_km,10)
        self.assertEqual({n.walk_zone for n in plan.ordered_pois},{plan.selected_zone})
        self.assertTrue(all("local_life" in self.repo.get_poi_by_id(n.poi_id).interest_tags for n in plan.ordered_pois))

    def test_90_and_180_good_routes_do_not_regress(self):
        cases=[(90,78.26347977250235,["p11","p2","p12"]),(180,78.26347977250235,["p11","p2","p12"])]
        for minutes,total,ids in cases:
            plan=self.engine.generate_route(RouteRequest(minutes,interest_tags=["local_life"]))
            self.assertEqual(plan.status,"success")
            self.assertAlmostEqual(plan.total_estimated_minutes,total)
            self.assertEqual([n.poi_id for n in plan.ordered_pois],ids)

    def test_insufficient_matching_pois_warn_without_unrelated_filler(self):
        raw=self.repo.get_raw_data()
        points=[p for p in raw['pois'] if p['id'] in ('p2','p4')]
        engine=RouteEngine(write_repository(self,subset(raw,points)))
        plan=engine.generate_route(RouteRequest(150,interest_tags=["local_life"],preferred_zone="wukang_fuxing_xujiahui"))
        self.assertEqual(plan.status,"success")
        self.assertEqual([n.poi_id for n in plan.ordered_pois],["p2"])
        self.assertLess(plan.time_utilization_ratio,.65)
        self.assertTrue(any("Limited matching POIs" in w for w in plan.warnings))

    def test_optimization_obeys_explicit_modes_and_walking_budget(self):
        plan=self.engine.generate_route(RouteRequest(150,interest_tags=["local_life"],max_walking_km=.8,visit_mode_overrides={"p33":"full_visit"}))
        self.assertEqual(plan.status,"success")
        self.assertLessEqual(plan.total_estimated_distance_km,.8)
        self.assertLessEqual(plan.total_estimated_minutes,150)

    def test_refinement_can_expand_mode_without_violating_user_override(self):
        raw=self.repo.get_raw_data()
        points=[p for p in raw['pois'] if p['id']=='p7']
        engine=RouteEngine(write_repository(self,subset(raw,points)))
        plan=engine.generate_route(RouteRequest(90,interest_tags=["architecture"]))
        self.assertEqual(plan.ordered_pois[0].selected_visit_mode,"full_visit")
        self.assertEqual(plan.ordered_pois[0].requested_visit_mode,"walk_stop")
        self.assertAlmostEqual(plan.time_utilization_ratio,75/90)
        explicit=engine.generate_route(RouteRequest(90,interest_tags=["architecture"],visit_mode_overrides={"p7":"walk_stop"}))
        self.assertEqual(explicit.ordered_pois[0].selected_visit_mode,"walk_stop")

    def test_explicit_long_leg_must_go_preserves_diagnostic(self):
        req=RouteRequest(180,interest_tags=["architecture","local_life"],experience_tags=["neighborhood_walk"],
                         must_go_poi_ids=["p12","p2","p11","p32","p33"])
        plan=self.engine.generate_route(req)
        self.assertEqual(plan.status,"success")
        self.assertEqual({n.poi_id for n in plan.ordered_pois},{"p12","p2","p11","p32","p33"})
        self.assertAlmostEqual(plan.estimated_max_single_leg_km,max(n.estimated_distance_from_previous_stop_km for n in plan.ordered_pois))
        self.assertGreater(plan.estimated_max_single_leg_km,2)
        self.assertTrue(plan.long_estimated_leg_warning)
        self.assertTrue(any("DEFERRED TO MAP API PHASE" in w for w in plan.warnings))

    def test_single_leg_metric_includes_supplied_start_and_is_zero_without_leg(self):
        raw=self.repo.get_raw_data()
        engine=RouteEngine(write_repository(self,subset(raw,[p for p in raw['pois'] if p['id']=='p13'])))
        no_start=engine.generate_route(RouteRequest(180,must_go_poi_ids=["p13"]))
        self.assertEqual(no_start.estimated_max_single_leg_km,0)
        self.assertFalse(no_start.long_estimated_leg_warning)
        started=engine.generate_route(RouteRequest(180,must_go_poi_ids=["p13"],start_lat=31.2,start_lng=121.4))
        self.assertGreater(started.estimated_max_single_leg_km,0)

    def test_failed_route_diagnostics_remain_unknown(self):
        plan=self.engine.generate_route(RouteRequest(1))
        self.assertIsNone(plan.time_utilization_ratio)
        self.assertIsNone(plan.estimated_max_single_leg_km)

    def test_parsed_intent_prints_all_fields_and_empty_values(self):
        text=render_intent(RouteIntent(RouteMode.PLAN_FOR_ME),self.repo)
        for label in ("Mode:","Time: -","Start: -","Interest: -","Experience: -","Culture: -","Avoid: -","Must-go: -","Pace:","Preferred Zone: -","Max Walking Distance: -","Needs Clarification:"):
            self.assertIn(label,text)
        intent=self.service.parse_plan(NO_MUSEUMS)
        self.assertIn("Avoid: museum_visit",render_result(self.service.generate(intent),self.repo))

    def test_live_entry_uses_same_process_for_first_llm_parse_and_stdin_answers(self):
        for text,answers,expected_tags in ((AUTHENTIC,"3 hours\n",["local_life"]),("Plan a walk for me.","3 hours\nparks and local life\n",["parks","local_life"])):
            mock=MockLLMClient(fixtures=PLAN_EXAMPLES)
            with patch("tools.demos.route_entry_demo.POIRepository",return_value=self.repo),patch("tools.demos.route_entry_demo.DeepSeekLLMClient",return_value=mock),patch("sys.stdin",io.StringIO(answers)),patch("sys.stdout",new_callable=io.StringIO) as out:
                code=main(["--mode","plan_for_me","--text",text],live=True)
            self.assertEqual(code,0)
            self.assertIn("Time: 180 min",out.getvalue())
            self.assertIn("Merged Intent",out.getvalue())
            self.assertIn("Status: success",out.getvalue())
            self.assertEqual(len(mock.calls),1)
            for tag in expected_tags:
                self.assertIn(tag,out.getvalue())
            if text==AUTHENTIC:
                self.assertNotIn("What are you most interested",out.getvalue())

    def test_cli_mode_plan_without_text_reads_first_turn_and_clarification(self):
        # This Phase 2 clarification contract uses its original data fixture.
        harness="from tools.demos import route_entry_demo as app; from tests.helpers import baseline_repository; app.POIRepository=lambda *args:baseline_repository(); raise SystemExit(app.main())"
        process=subprocess.run([sys.executable,"-c",harness,"--mode","plan_for_me"],input=AUTHENTIC+"\n3 hours\n",cwd=ROOT,capture_output=True,text=True,encoding="utf-8",env={**os.environ,"PYTHONIOENCODING":"utf-8"},timeout=20)
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertIn("Status: success",process.stdout)
        self.assertNotIn("What are you most interested",process.stdout)

    def test_complete_single_turn_text_keeps_success_without_stdin(self):
        process=subprocess.run([sys.executable,"tools/demos/route_entry_demo.py","--mode","plan_for_me","--text","I have three hours and want to see old architecture and local neighborhoods."],input="",cwd=ROOT,capture_output=True,text=True,encoding="utf-8",env={**os.environ,"PYTHONIOENCODING":"utf-8"},timeout=20)
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertIn("Status: success",process.stdout)


if __name__ == "__main__":
    unittest.main()
