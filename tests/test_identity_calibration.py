"""Phase 3B_2.1: dual dimensions, confirmed parents and exact authorized data diff."""
import copy
from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
from src import POIRepository,RouteEngine,RouteRequest,Location
from src.geo_utils import haversine_km
from src.intent_models import RouteIntent,RouteMode
from src.poi_mapping import PoiMappingRepository,match_poi,classify
from src.world_models import MappingStatus,LiveInfoApplicability,PoiCandidate,PoiLiveInfo,SHANGHAI
from src.services.location_service import LocationService
from src.services.proximity_service import ProximityService
from src.services.poi_live_info_service import PoiLiveInfoService
from src.services.walking_route_service import WalkingRouteService
from src.services.walking_route_planner import WalkingRoutePlanner
from src.trip_replanning import ReplanningCoordinator
from src.trip_state import TripState,TripStateDelta
from src.trip_store import InMemoryTripStore,TripService
from scripts.match_amap_poi_ids import audit,SPECIAL_ALIASES
from scripts.calibrate_core_data import remove_references
from tools.demos.trip_demo import load_fixture

AT=datetime(2026,10,5,12,tzinfo=SHANGHAI)

class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.repo=POIRepository();self.maps=json.loads(Path('data/amap_poi_mappings.json').read_text(encoding='utf-8'))
    def candidate(self,poi,name=None,pid='B0TEST12345',ptype=None,offset=0):
        lat,lng=poi.coordinates
        return PoiCandidate(pid,name or poi.name_zh,Location(lat+offset/111195.0802335,lng,'GCJ02'),{'west_bund':'徐汇区','hongkou_literary':'虹口区','old_city_central':'黄浦区','wukang_fuxing_xujiahui':'徐汇区'}[poi.zone_id],poi_type=ptype)
    def test_identity_enum_has_no_not_applicable(self):
        self.assertEqual(set(MappingStatus),{'MATCHED','AMBIGUOUS','NOT_FOUND'})
    def test_museum_park_street_dimensions(self):
        for pid,app in (('p28','FULL'),('p16','LIMITED'),('pz_b4acff8f32fc','NOT_APPLICABLE')):
            row=self.maps[pid];self.assertEqual(row['identity_mapping_status'],'MATCHED');self.assertEqual(row['live_info_applicability'],app)
    def test_all58_have_complete_separate_dimensions(self):
        PoiMappingRepository(records=self.maps)
        self.assertEqual(set(self.maps),{p.id for p in self.repo.get_all_pois()});self.assertEqual(len(self.maps),58)
        summary=json.loads(Path('examples/location_awareness/mapping_audit.json').read_text(encoding='utf-8'))
        self.assertEqual(sum(summary['identity_counts'].values()),58);self.assertEqual(sum(summary['live_info_applicability_counts'].values()),58)
    def test_manual_confirmations_are_exact_and_sticky(self):
        confirmed=json.loads(Path('data/amap_manual_confirmations.json').read_text(encoding='utf-8'))
        for pid,decision in confirmed.items():
            row=self.maps[pid];self.assertEqual(row['amap_poi_id'],decision['amap_poi_id']);self.assertTrue(row['reviewed']);self.assertEqual(row['match_method'],decision['match_method'])
        self.assertEqual({pid for pid,r in self.maps.items() if r['reviewed']},set(confirmed)|{'p24'})
    def test_child_confidence_does_not_veto_parent(self):
        for pid,suffix in (('p36','A馆'),('p37','北广场'),('p33','少年儿童馆')):
            poi=self.repo.get_poi_by_id(pid);name=poi.name_zh.split('（')[0]
            row=match_poi(poi,[self.candidate(poi,name,pid='PARENT123'),self.candidate(poi,name+suffix,pid='CHILD123')],aliases=[name,name+suffix])
            self.assertEqual(row['amap_poi_id'],'PARENT123');self.assertFalse(row['reviewed'])
    def test_two_unrelated_plausible_parents_remain_ambiguous(self):
        poi=self.repo.get_poi_by_id('p28')
        row=match_poi(poi,[self.candidate(poi,pid='FIRST123'),self.candidate(poi,pid='SECOND123')])
        self.assertEqual(row['identity_mapping_status'],'AMBIGUOUS');self.assertIsNone(row['amap_poi_id'])
    def test_thresholds_not_lowered_by_parent_rules(self):
        poi=self.repo.get_poi_by_id('p28')
        for candidate in (self.candidate(poi,offset=400),replace(self.candidate(poi),district='浦东新区'),self.candidate(poi,name='无关的文化中心')):
            self.assertEqual(match_poi(poi,[candidate],expected_district='徐汇区')['identity_mapping_status'],'NOT_FOUND')
    def test_park_access_notice_is_not_a_different_identity(self):
        poi=self.repo.get_poi_by_id('pz_8919938b21f2')
        row=match_poi(poi,[self.candidate(poi,name='淮海公园(暂停开放)',ptype='风景名胜;公园广场;公园')])
        self.assertEqual(row['identity_mapping_status'],'MATCHED');self.assertEqual(row['live_info_applicability'],'LIMITED')
    def test_street_merchant_rejected_area_parent_accepted(self):
        poi=self.repo.get_poi_by_id('p7')
        for ptype,status in (('餐饮服务;中餐厅','NOT_FOUND'),('购物服务;特色商业街;特色商业街','MATCHED')):
            row=match_poi(poi,[self.candidate(poi,name='新天地北里',ptype=ptype)])
            self.assertEqual(row['identity_mapping_status'],status);self.assertEqual(row['live_info_applicability'],'NOT_APPLICABLE')
    def test_road_hotspot_duplicate_resolves_to_road(self):
        poi=self.repo.get_poi_by_id('pz_b4acff8f32fc')
        row=match_poi(poi,[self.candidate(poi,pid='HOTSPOT12',ptype='风景名胜'),self.candidate(poi,pid='ROAD1234',ptype='地名地址信息;道路名',offset=49)])
        self.assertEqual(row['amap_poi_id'],'ROAD1234')
    def test_p24_searches_formal_aliases_and_excludes_children(self):
        poi=self.repo.get_poi_by_id('p24');provider=Mock()
        provider.search_mapping_candidates.return_value=[self.candidate(poi,name='中共一大纪念馆一大广场',ptype='风景名胜;公园广场')]
        provider.search_identity_near_coordinate.return_value=[]
        with patch.object(self.repo,'get_all_pois',return_value=[poi]):rows,_=audit(self.repo,provider,confirmations={})
        self.assertEqual(rows['p24']['identity_mapping_status'],'NOT_FOUND');self.assertIsNone(rows['p24']['amap_poi_id'])
        self.assertEqual([c.args[0] for c in provider.search_mapping_candidates.call_args_list],SPECIAL_ALIASES['p24'])
        self.assertEqual(provider.search_identity_near_coordinate.call_count,3)
        self.assertIn('现实地点',rows['p24']['notes'])
    def test_p24_real_parent_found_and_confirmed(self):
        poi=self.repo.get_poi_by_id('p24');provider=Mock();formal=SPECIAL_ALIASES['p24'][0]
        provider.search_mapping_candidates.return_value=[self.candidate(poi,name=formal,pid='PARENT123',ptype='风景名胜;纪念馆'),self.candidate(poi,name=formal+'-报告厅',pid='CHILD123',ptype='纪念馆')]
        provider.search_identity_near_coordinate.return_value=[]
        with patch.object(self.repo,'get_all_pois',return_value=[poi]):rows,_=audit(self.repo,provider,confirmations={})
        self.assertEqual(rows['p24']['amap_poi_id'],'PARENT123');self.assertTrue(rows['p24']['reviewed']);self.assertEqual(rows['p24']['match_method'],'MANUAL_ALIAS_CONFIRMATION')
        self.assertEqual(self.maps['p24']['amap_poi_id'],'B0MGOCVX94')
    def test_manual_mapping_survives_search_and_detail_failure(self):
        poi=self.repo.get_poi_by_id('p32');provider=Mock();provider.get_poi_detail.side_effect=TimeoutError()
        with patch.object(self.repo,'get_all_pois',return_value=[poi]):rows,_=audit(self.repo,provider)
        self.assertEqual(rows['p32']['amap_poi_id'],'B0H3TUK613');self.assertTrue(rows['p32']['reviewed']);provider.search_mapping_candidates.assert_not_called()
    def test_p24_confirmation_survives_rerun(self):
        poi=self.repo.get_poi_by_id('p24');provider=Mock();provider.get_poi_detail.side_effect=TimeoutError()
        with patch.object(self.repo,'get_all_pois',return_value=[poi]):rows,_=audit(self.repo,provider,existing=self.maps,confirmations={})
        self.assertEqual(rows['p24']['amap_poi_id'],self.maps['p24']['amap_poi_id']);self.assertTrue(rows['p24']['reviewed'])
    def test_not_applicable_open_status_independent_of_runtime_data(self):
        pid='pz_b4acff8f32fc';mapping=PoiMappingRepository(records=self.maps);provider=Mock()
        provider.get_poi_detail.return_value=PoiLiveInfo(provider_id=self.maps[pid]['amap_poi_id'],name='甜爱路',live_data_status='PARTIAL',opentime_today='00:00-24:00',fetched_at='2026-10-05T02:00:00+00:00')
        result=PoiLiveInfoService(provider,mapping,clock=lambda:AT).get_poi_live_info(pid)
        self.assertEqual((result.identity_mapping_status,result.live_data_status,result.open_status),('MATCHED','PARTIAL','NOT_APPLICABLE'))
        provider.get_poi_detail.side_effect=TimeoutError()
        result=PoiLiveInfoService(provider,mapping,clock=lambda:AT).get_poi_live_info(pid)
        self.assertEqual((result.identity_mapping_status,result.live_data_status,result.open_status),('MATCHED','UNAVAILABLE','NOT_APPLICABLE'))
    def test_full_and_limited_can_resolve_open_and_unknown(self):
        for pid in ('p28','p16'):
            provider=Mock();provider.get_poi_detail.return_value=PoiLiveInfo(provider_id=self.maps[pid]['amap_poi_id'],name=pid,live_data_status='PARTIAL',opentime_today='10:00-18:00',fetched_at='2026-10-05T02:00:00+00:00')
            service=PoiLiveInfoService(provider,PoiMappingRepository(records=self.maps),clock=lambda:AT)
            self.assertEqual(service.get_poi_live_info(pid).open_status,'OPEN')
            self.assertEqual(service.get_poi_live_info(pid,current_local_time=AT.replace(hour=19)).open_status,'CLOSED')
            provider.get_poi_detail.return_value=replace(provider.get_poi_detail.return_value,opentime_today=None)
            self.assertEqual(PoiLiveInfoService(provider,PoiMappingRepository(records=self.maps),clock=lambda:AT).get_poi_live_info(pid).open_status,'UNKNOWN')
    def test_p40_deleted_no_related_or_mapping_or_active_fixture(self):
        self.assertIsNone(self.repo.get_poi_by_id('p40'));self.assertNotIn('p40',self.maps)
        self.assertNotIn('"p40"',json.dumps(self.repo.get_raw_data()))
        plan,_=load_fixture();self.assertNotIn('p40',[s.poi_id for s in plan.ordered_pois])
        for zone in self.repo.zone_order:
            plan=RouteEngine(self.repo).generate_route(RouteRequest(180,preferred_zone=zone))
            self.assertNotIn('p40',[s.poi_id for s in plan.ordered_pois])
    def test_remove_active_references_keeps_remaining_order_no_replacement(self):
        removed=[];raw=dict(active_route=dict(ordered_pois=[dict(poi_id=p) for p in ('p36','p40','p28')]),related=['p40','p37'])
        cleaned=remove_references(raw,removed=removed)
        self.assertEqual([s['poi_id'] for s in cleaned['active_route']['ordered_pois']],['p36','p28']);self.assertEqual(cleaned['related'],['p37']);self.assertEqual(len(removed),2)
    def test_only_authorized_core_changes(self):
        before=json.loads(Path('examples/location_awareness/calibration/pois_before.json').read_text(encoding='utf-8'));after=self.repo.get_raw_data()
        expected=copy.deepcopy(before);expected['pois']=[p for p in expected['pois'] if p['id']!='p40']
        coords={r['core_id']:r for r in json.loads(Path('examples/location_awareness/coordinate_corrections.json').read_text(encoding='utf-8'))['corrections']}
        for i,p in enumerate(expected['pois'],1):
            p['display_order']=i
            if p['id'] in coords:
                point=coords[p['id']]['new_coordinate'];keys=('representative_lat','representative_lng') if p['poi_type'] in ('district','street') else ('lat','lng')
                p['location'][keys[0]]=point['lat'];p['location'][keys[1]]=point['lng']
                if p['id']=='p34':p['location']['coordinate_system']='GCJ-02 / Amap formal identity coordinate (Phase 3B_2.2)'
        expected['metadata']['poi_count']=58
        for z in expected['metadata']['walk_zones']:z['poi_count']=sum(p['walk_zone']['id']==z['id'] for p in expected['pois'])
        self.assertEqual(expected,after)
    def test_corrected_coordinates_match_formal_detail_and_proximity(self):
        details=json.loads(Path('examples/location_awareness/calibration/coordinate_provider_details.json').read_text(encoding='utf-8'))
        for pid in ('p4','p11'):
            poi=self.repo.get_poi_by_id(pid);point=Location(**details[pid]['location']);self.assertEqual(poi.coordinates,(point.lat,point.lng))
            self.assertEqual(ProximityService(LocationService(None,None)).check_arrival(point,poi).status,'ARRIVED')
    def test_engine_hydration_and_replan_use_corrected_core(self):
        for pid,zone in (('p4','hongkou_literary'),('p11','wukang_fuxing_xujiahui')):
            request=RouteRequest(180,preferred_zone=zone,must_go_poi_ids=[pid]);service=WalkingRouteService()
            plan=WalkingRoutePlanner(self.repo,walking_service=service).generate_route(request)
            stop=next(s for s in plan.ordered_pois if s.poi_id==pid);self.assertEqual(tuple(stop.estimated_coordinates),self.repo.get_poi_by_id(pid).coordinates)
            self.assertEqual(plan.walking_data_status,'FALLBACK_ESTIMATE');self.assertGreater(plan.walking_distance_m,0)
            intent=RouteIntent(RouteMode.PLAN_FOR_ME,available_minutes=180,preferred_zone=zone,must_go_poi_ids=[pid],interest_tags=['history','architecture'])
            store=InMemoryTripStore();core=TripService(store);trip=core.create_trip(plan,intent);core.start_trip(trip.trip_id)
            before=store.get(trip.trip_id)
            result=ReplanningCoordinator(store,self.repo,walking_service=service).replan(trip.trip_id,TripStateDelta(request_replan=True,remaining_minutes=160))
            self.assertTrue(result.committed,result.to_dict());after=store.get(trip.trip_id)
            self.assertEqual(before.route_versions[0],after.route_versions[0]);self.assertEqual(before.original_route,after.original_route)
            stop=next(s for s in after.active_route['ordered_pois'] if s['poi_id']==pid);self.assertEqual(tuple(stop['estimated_coordinates']),self.repo.get_poi_by_id(pid).coordinates)
            self.assertEqual(TripState.from_dict(after.to_dict()).to_dict(),after.to_dict())

if __name__=='__main__':unittest.main()
