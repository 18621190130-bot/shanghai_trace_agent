"""Seven warning codes, progress, visit semantics and strict no-mutation evidence."""
import copy
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from src import POIRepository, Location
from src.world_models import PoiLiveInfo
from src.weather_models import CurrentWeather, SHANGHAI
from src.reality_models import WarningCode
from src.services.opening_hours_evaluator import OpeningHoursEvaluator
from src.services.route_reality_check_service import RouteRealityCheckService
from src.services.world_context_service import WorldContextService
from src.trip_state import TripState, RouteVersion
from src.trip_store import InMemoryTripStore
from tools.demos.trip_demo import load_fixture

AT = datetime(2026,10,6,12,tzinfo=SHANGHAI)


def observation(pid, **kwargs):
    fields = dict(core_poi_id=pid,opentime_today='09:00-22:00',open_status='OPEN',
                  live_data_status='AVAILABLE',live_info_applicability='FULL',fetched_at=AT.isoformat())
    fields.update(kwargs)
    return PoiLiveInfo(**fields)


def fixtures():
    stops = [dict(poi_id=pid,estimated_stay_minutes=stay,selected_visit_mode=mode,
                  effective_primary_role=role,visit_scope='室内展厅参观',must_go=True)
             for pid,stay,mode,role in [('p28',15,'walk_stop','anchor'),('p25',60,'full_visit','supporting_stop')]]
    legs = [dict(from_poi_id='p28',to_poi_id='p25',duration_s=600,distance_m=800,status='AVAILABLE')]
    route = dict(ordered_pois=stops,walking_legs=legs,request={})
    version = dict(version_id='v1',route_snapshot=route)
    trip = dict(visited_poi_ids=[],skipped_poi_ids=[],remaining_minutes=180,current_poi_id='p28',
                route_versions=[copy.deepcopy(version)],active_route=copy.deepcopy(route))
    return trip,version


class RealityTests(unittest.TestCase):
    def setUp(self):
        self.trip,self.version=fixtures()
        self.weather=Mock()
        self.weather.get_current_weather.return_value=CurrentWeather(weather_text='晴',temperature_c=23,data_status='AVAILABLE')
        self.info=Mock()
        self.info.get_poi_live_info.side_effect=lambda pid,**kwargs:observation(pid)
        self.repo=POIRepository()
        self.service=RouteRealityCheckService(self.weather,self.info,repository=self.repo)

    def check(self,now=AT):return self.service.check_route_reality(self.trip,self.version,now=now)

    @staticmethod
    def codes(result):return [w.code for w in result.warnings]

    def test_healthy_ok(self):
        result=self.check()
        self.assertEqual(result.status,'OK');self.assertEqual(result.warnings,())
        self.assertEqual(result.metrics['reality_adjusted_remaining_minutes'],85)
        self.assertEqual(result.metrics['stops'][1]['estimated_arrival'],'2026-10-06T12:25:00+08:00')

    def test_budget_warning_soft_and_must_go_preserved(self):
        self.trip['remaining_minutes']=60
        before=copy.deepcopy((self.trip,self.version))
        result=self.check(); warning=result.warnings[0]
        self.assertEqual(warning.code,'LIVE_ROUTE_EXCEEDS_BUDGET')
        self.assertEqual(warning.confidence,'HIGH')
        self.assertEqual(warning.details['excess_minutes'],25)
        self.assertTrue(warning.details['budget_is_soft'])
        self.assertEqual((self.trip,self.version),before)

    def test_budget_tolerance_boundary(self):
        self.trip['remaining_minutes']=80
        self.assertNotIn('LIVE_ROUTE_EXCEEDS_BUDGET',self.codes(self.check()))
        self.trip['remaining_minutes']=79.9
        self.assertIn('LIVE_ROUTE_EXCEEDS_BUDGET',self.codes(self.check()))

    def test_eta_closed_dedup_precedence_over_may_close(self):
        self.info.get_poi_live_info.side_effect=lambda pid,**kw:observation(pid,opentime_today='09:00-12:20') if pid=='p25' else observation(pid)
        result=self.check()
        warnings=[w for w in result.warnings if w.poi_id=='p25']
        self.assertEqual([w.code for w in warnings],['POI_CLOSED'])
        self.assertEqual(warnings[0].details['estimated_arrival'],'2026-10-06T12:25:00+08:00')
        self.assertEqual(warnings[0].details['provider_status'],'AVAILABLE')

    def test_visit_crosses_close(self):
        self.info.get_poi_live_info.side_effect=lambda pid,**kw:observation(pid,opentime_today='09:00-13:00') if pid=='p25' else observation(pid)
        warning=self.check().warnings[0]
        self.assertEqual(warning.code,'POI_MAY_CLOSE_BEFORE_ARRIVAL')
        self.assertEqual(warning.details['closes_at'],'2026-10-06T13:00:00+08:00')

    def test_departure_exact_close_allowed(self):
        self.info.get_poi_live_info.side_effect=lambda pid,**kw:observation(pid,opentime_today='09:00-13:25') if pid=='p25' else observation(pid)
        self.assertEqual(self.check().warnings,())

    def test_unknown_missing_and_unparseable_full_limited(self):
        for hours in (None,'每天开放','09:00-99:00'):
            for applicability in ('FULL','LIMITED'):
                with self.subTest(hours=hours,applicability=applicability):
                    self.info.get_poi_live_info.side_effect=lambda pid,**kw:observation(pid,opentime_today=hours,live_info_applicability=applicability)
                    result=self.check()
                    self.assertEqual(self.codes(result),['OPENING_HOURS_UNKNOWN','OPENING_HOURS_UNKNOWN'])
                    self.assertEqual(result.status,'PARTIAL')

    def test_not_applicable_no_opening_warnings(self):
        self.info.get_poi_live_info.side_effect=lambda pid,**kw:observation(pid,opentime_today=None,live_info_applicability='NOT_APPLICABLE',open_status='NOT_APPLICABLE')
        self.assertEqual(self.check().warnings,())

    def test_p35_mapping_not_found_no_unknown(self):
        self.version['route_snapshot']['ordered_pois']=[dict(poi_id='p35',estimated_stay_minutes=10,selected_visit_mode='walk_stop')]
        self.version['route_snapshot']['walking_legs']=[]
        world=WorldContextService.from_environment(repository=self.repo)
        service=RouteRealityCheckService(self.weather,world.poi_info,repository=self.repo)
        result=service.check_route_reality(self.trip,self.version,now=AT)
        self.assertNotIn('OPENING_HOURS_UNKNOWN',self.codes(result))
        self.assertEqual(result.metrics['stops'][0]['opening_evaluation'],'NOT_APPLICABLE')

    def test_exterior_scope_only_waives_interior_hours(self):
        self.version['route_snapshot']['ordered_pois'][0]['visit_scope']='建筑外观，外部公共空间'
        self.info.get_poi_live_info.side_effect=lambda pid,**kw:observation(pid,opentime_today=None)
        warnings=self.check().warnings
        self.assertEqual([w.poi_id for w in warnings],['p25'])

    def test_transition_role_still_checks_hours(self):
        self.version['route_snapshot']['ordered_pois'][0]['effective_primary_role']='transition_stop'
        self.info.get_poi_live_info.side_effect=lambda pid,**kw:observation(pid,opentime_today='09:00-10:00')
        self.assertIn('p28',[w.poi_id for w in self.check().warnings if w.code=='POI_CLOSED'])

    def test_roles_do_not_choose_duration(self):
        result=self.check()
        self.assertEqual([s['planned_visit_minutes'] for s in result.metrics['stops']],[15,60])
        self.assertEqual([s['selected_visit_mode'] for s in result.metrics['stops']],['walk_stop','full_visit'])
        self.version['route_snapshot']['ordered_pois'][0]['effective_primary_role']='supporting_stop'
        self.version['route_snapshot']['ordered_pois'][1]['effective_primary_role']='anchor'
        self.assertEqual(self.check().metrics,result.metrics)

    def test_rain_risk_route_level(self):
        self.weather.get_current_weather.return_value=CurrentWeather(weather_text='小雨',data_status='AVAILABLE')
        warning=self.check().warnings[0]
        self.assertEqual(warning.code,'WEATHER_RISK')
        self.assertEqual(warning.details['risk_type'],['RAIN'])

    def test_trivial_walk_no_weather_warning(self):
        self.version['route_snapshot']['walking_legs'][0].update(duration_s=60,distance_m=100)
        self.weather.get_current_weather.return_value=CurrentWeather(weather_text='暴雨',data_status='AVAILABLE')
        self.assertNotIn('WEATHER_RISK',self.codes(self.check()))

    def test_fallback_budget_reference_lower_confidence(self):
        self.version['route_snapshot']['walking_legs'][0]['status']='FALLBACK_ESTIMATE'
        self.trip['remaining_minutes']=60
        result=self.check()
        self.assertEqual(result.status,'PARTIAL')
        self.assertIn('LIVE_ROUTE_DATA_UNAVAILABLE',self.codes(result))
        self.assertEqual(result.metrics['remaining_live_walking_minutes'],0)
        self.assertEqual(result.metrics['remaining_reference_walking_minutes'],10)
        warning=next(w for w in result.warnings if w.code=='LIVE_ROUTE_EXCEEDS_BUDGET')
        self.assertEqual(warning.confidence,'MEDIUM')

    def test_unavailable_no_fabricated_eta_budget(self):
        self.version['route_snapshot']['walking_legs'][0].update(status='UNAVAILABLE',duration_s=None,distance_m=None)
        self.trip['remaining_minutes']=1
        result=self.check()
        self.assertIsNone(result.metrics['stops'][1]['estimated_arrival'])
        self.assertIsNone(result.metrics['reality_adjusted_remaining_minutes'])
        self.assertNotIn('LIVE_ROUTE_EXCEEDS_BUDGET',self.codes(result))
        self.assertIn('LIVE_ROUTE_DATA_UNAVAILABLE',self.codes(result))

    def test_missing_leg_is_not_zero_walk(self):
        self.version['route_snapshot']['walking_legs']=[]
        result=self.check()
        self.assertIsNone(result.metrics['stops'][1]['estimated_arrival'])
        self.assertIn('LIVE_ROUTE_DATA_UNAVAILABLE',self.codes(result))

    def test_invalid_live_duration_is_unavailable(self):
        for value in (None,-1,float('nan'),True):
            with self.subTest(value=value):
                self.version['route_snapshot']['walking_legs'][0]['duration_s']=value
                self.assertIn('LIVE_ROUTE_DATA_UNAVAILABLE',self.codes(self.check()))

    def test_weather_failure_other_checks_continue(self):
        self.weather.get_current_weather.side_effect=TimeoutError('Never export raw provider exception')
        self.trip['remaining_minutes']=60
        self.info.get_poi_live_info.side_effect=lambda pid,**kw:observation(pid,opentime_today='09:00-10:00')
        result=self.check()
        self.assertEqual(result.status,'PARTIAL')
        self.assertIn('WEATHER_DATA_UNAVAILABLE',self.codes(result))
        self.assertIn('POI_CLOSED',self.codes(result))
        self.assertIn('LIVE_ROUTE_EXCEEDS_BUDGET',self.codes(result))
        self.assertNotIn('Never export',json.dumps(result.to_dict()))

    def test_partial_weather_honest_status_and_risk(self):
        self.weather.get_current_weather.return_value=CurrentWeather(weather_text='雷阵雨',data_status='PARTIAL')
        result=self.check()
        self.assertEqual(result.status,'PARTIAL')
        self.assertIn('WEATHER_RISK',self.codes(result))
        self.assertNotIn('WEATHER_DATA_UNAVAILABLE',self.codes(result))

    def test_missing_eta_and_missing_hours_both_visible(self):
        self.version['route_snapshot']['walking_legs'][0]['duration_s']=None
        self.info.get_poi_live_info.side_effect=lambda pid,**kw:observation(pid,opentime_today=None)
        result=self.check()
        self.assertIn('LIVE_ROUTE_DATA_UNAVAILABLE',self.codes(result))
        self.assertEqual([w.poi_id for w in result.warnings if w.code=='OPENING_HOURS_UNKNOWN'],['p28','p25'])

    def test_first_start_location_leg_counted(self):
        route=self.version['route_snapshot'];route['request']['start_lat']=31.2
        route['walking_legs'].insert(0,dict(from_poi_id=None,to_poi_id='p28',duration_s=300,distance_m=400,status='AVAILABLE'))
        result=self.check()
        self.assertEqual(result.metrics['reality_adjusted_remaining_minutes'],90)
        self.assertEqual(result.metrics['stops'][0]['estimated_arrival'],'2026-10-06T12:05:00+08:00')

    def test_all_observations_unavailable(self):
        self.weather.get_current_weather.return_value=CurrentWeather()
        self.info.get_poi_live_info.side_effect=lambda pid,**kw:observation(pid,opentime_today=None,live_data_status='UNAVAILABLE')
        self.version['route_snapshot']['walking_legs'][0].update(duration_s=None,distance_m=None,status='UNAVAILABLE')
        self.assertEqual(self.check().status,'UNAVAILABLE')

    def test_missing_visit_duration_not_inferred_from_role(self):
        self.version['route_snapshot']['ordered_pois'][0]['estimated_stay_minutes']=None
        result=self.check()
        self.assertIsNone(result.metrics['reality_adjusted_remaining_minutes'])
        self.assertIsNone(result.metrics['stops'][1]['estimated_arrival'])
        self.assertEqual(result.status,'PARTIAL')

    def test_poi_failure_isolated_and_other_poi_checked(self):
        self.info.mappings=None
        self.info.get_poi_live_info.side_effect=lambda pid,**kw:(_ for _ in ()).throw(TimeoutError()) if pid=='p28' else observation(pid,opentime_today='09:00-10:00')
        result=self.check()
        self.assertEqual(result.status,'PARTIAL')
        self.assertIn('p25',[w.poi_id for w in result.warnings if w.code=='POI_CLOSED'])

    def test_current_progress_only_stops_three_four(self):
        route=self.version['route_snapshot']
        route['ordered_pois']=[dict(poi_id=pid,estimated_stay_minutes=stay,selected_visit_mode='full_visit',must_go=True)
                               for pid,stay in [('p28',100),('p25',100),('p34',20),('p35',30)]]
        route['walking_legs']=[dict(from_poi_id=a,to_poi_id=b,duration_s=duration,distance_m=500,status=status)
                               for a,b,duration,status in [('p28','p25',6000,'FALLBACK_ESTIMATE'),('p25','p34',600,'AVAILABLE'),('p34','p35',300,'AVAILABLE')]]
        self.trip['visited_poi_ids']=['p28','p25'];self.trip['remaining_minutes']=70
        result=self.check()
        self.assertEqual(result.metrics['remaining_poi_ids'],['p34','p35'])
        self.assertEqual(result.metrics['reality_adjusted_remaining_minutes'],65)
        self.assertEqual([r['estimated_arrival'] for r in result.metrics['stops']],['2026-10-06T12:10:00+08:00','2026-10-06T12:35:00+08:00'])
        self.assertEqual([c.args[0] for c in self.info.get_poi_live_info.call_args_list],['p34','p35'])
        self.assertEqual(result.warnings,())

    def test_skipped_stop_excluded(self):
        self.trip['skipped_poi_ids']=['p28']
        result=self.check()
        self.assertEqual(result.metrics['remaining_poi_ids'],['p25'])
        self.assertEqual(result.metrics['reality_adjusted_remaining_minutes'],70)

    def test_empty_remaining_no_external_requests(self):
        self.trip['visited_poi_ids']=['p28','p25']
        result=self.check()
        self.assertEqual(result.status,'OK');self.assertEqual(result.warnings,())
        self.weather.get_current_weather.assert_not_called();self.info.get_poi_live_info.assert_not_called()

    def test_gps_only_weather_no_walking_calls(self):
        gps=Location(31.1,121.4,'GCJ02')
        with patch('src.services.walking_route_service.WalkingRouteService.hydrate_dict',side_effect=AssertionError('must not hydrate')):
            result=self.service.check_route_reality(self.trip,self.version,gps,AT)
        self.assertEqual(result.metrics['remaining_reference_walking_minutes'],10)
        self.assertEqual(self.weather.get_current_weather.call_args.args[0],gps)

    def test_shanghai_date_and_naive_rejected(self):
        result=self.check(datetime(2026,10,6,4,tzinfo=timezone.utc))
        self.assertEqual(result.checked_at,AT.isoformat())
        with self.assertRaises(ValueError):self.check(datetime(2026,10,6,12))

    def test_future_date_today_hours_not_reused(self):
        result=self.check(AT+timedelta(days=1))
        self.assertEqual(self.codes(result),['OPENING_HOURS_UNKNOWN','OPENING_HOURS_UNKNOWN'])

    def test_snapshot_equality_core_and_store_no_mutation(self):
        plan,intent=load_fixture();trip=TripState.create(plan,intent);trip.start_trip()
        store=InMemoryTripStore();store.create(trip)
        before=trip.to_dict();version=trip.route_versions[-1]
        core=self.repo.get_raw_data();coords={p.id:p.coordinates for p in self.repo.get_all_pois()}
        digest=lambda value:hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        hashes=digest([before,version,core])
        with patch.object(InMemoryTripStore,'save_if_revision',side_effect=AssertionError('No CAS')), patch.object(TripState,'commit_replan',side_effect=AssertionError('No replan')), patch.object(TripState,'commit_mutation',side_effect=AssertionError('No mutation')):
            self.service.check_route_reality(trip,RouteVersion(**version),now=AT)
        self.assertEqual(trip.to_dict(),before)
        self.assertEqual(store.get(trip.trip_id).to_dict(),before)
        self.assertEqual(version,trip.route_versions[-1])
        self.assertEqual(core,self.repo.get_raw_data())
        self.assertEqual(coords,{p.id:p.coordinates for p in self.repo.get_all_pois()})
        self.assertEqual(digest([trip.to_dict(),version,self.repo.get_raw_data()]),hashes)

    def test_defensive_return(self):
        self.trip['remaining_minutes']=1
        result=self.check();result.warnings[0].details['budget']=999
        self.assertEqual(self.trip['remaining_minutes'],1)
        self.assertEqual(self.check().warnings[0].details['budget'],1)

    def test_current_version_only(self):
        self.version['version_id']='v0'
        with self.assertRaises(ValueError):self.check()

    def test_only_seven_codes(self):
        self.assertEqual(len(WarningCode),7)


class OpeningEvaluatorTests(unittest.TestCase):
    def setUp(self):self.evaluator=OpeningHoursEvaluator()

    def evaluate(self,hours,at=AT):return self.evaluator.evaluate_open_status(hours,at,fetched_at=AT.isoformat())

    def test_arbitrary_arrival_closed(self):
        self.assertEqual(self.evaluate('09:00-18:00',AT.replace(hour=18)),'CLOSED')

    def test_midday_break(self):
        self.assertEqual(self.evaluate('09:00-12:00;13:00-18:00'),'CLOSED')

    def test_overlapping_intervals_close(self):
        close=self.evaluator.closes_at('09:00-13:00;12:00-18:00',AT,fetched_at=AT.isoformat())
        self.assertEqual(close.hour,18)

    def test_overnight_close(self):
        at=AT.replace(hour=23)
        close=self.evaluator.closes_at('22:00-02:00',at,fetched_at=AT.isoformat())
        self.assertEqual(close,datetime(2026,10,7,2,tzinfo=SHANGHAI))

    def test_early_overnight_window(self):
        at=AT.replace(hour=1)
        close=self.evaluator.closes_at('22:00-02:00',at,fetched_at=AT.isoformat())
        self.assertEqual(close,AT.replace(hour=2))

    def test_stale_missing_naive_fetch_unknown(self):
        for fetched in (None,'bad','2026-10-06T12:00:00','2026-10-05T12:00:00+08:00'):
            with self.subTest(fetched=fetched):self.assertEqual(self.evaluator.evaluate_open_status('09:00-18:00',AT,fetched_at=fetched),'UNKNOWN')

    def test_strict_parser_unmodified_behavior(self):
        for text in ('周一闭馆','9am-6pm','09:00-18:00 或 节假日','00:00-00:00'):
            with self.subTest(text=text):self.assertEqual(self.evaluate(text),'UNKNOWN')
