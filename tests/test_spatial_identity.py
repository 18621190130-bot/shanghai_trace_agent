"""Spatial contracts and identity-independent route/Trip regressions."""
import copy
from dataclasses import asdict
import json
from pathlib import Path
import unittest
from unittest.mock import Mock
from src import POIRepository,RouteEngine,RouteRequest,Location
from src.geo_utils import haversine_km,to_gcj02
from src.spatial_profiles import SpatialProfileRepository,validate_extent
from src.spatial_geometry import point_in_polygon,distance_to_linear_extent_m,within_extent
from src.poi_mapping import PoiMappingRepository,match_poi
from src.world_models import PoiCandidate
from src.intent_models import RouteIntent,RouteMode
from src.services.walking_route_service import WalkingRouteService
from src.services.walking_route_planner import WalkingRoutePlanner
from src.walking_models import WalkingStep,WalkingRouteResult
from src.services.proximity_service import ProximityService
from src.services.location_service import LocationService
from src.trip_state import TripState,TripStateDelta
from src.trip_store import InMemoryTripStore,TripService
from src.trip_replanning import ReplanningCoordinator


def p(lat,lng):return dict(lat=lat,lng=lng,coordinate_system='GCJ02')
def synthetic_walking():
    provider=Mock()
    def route(a,b):
        line=((a.lng,a.lat),(b.lng,b.lat));d=haversine_km((a.lat,a.lng),(b.lat,b.lng))*1000
        return WalkingRouteResult(a,b,d,d/1.25,(WalkingStep('Walk',d,d/1.25,line),),line,'synthetic','2026-10-05T00:00:00+00:00')
    provider.get_walking_route.side_effect=route
    return WalkingRouteService(provider),provider

class SpatialTests(unittest.TestCase):
    def setUp(self):
        self.repo=POIRepository();self.rows=SpatialProfileRepository().all()
    def test_all58_valid_and_independent_of_identity_sidecar(self):
        SpatialProfileRepository(records=self.rows,core_ids=[p.id for p in self.repo.get_all_pois()])
        self.assertEqual(len(self.rows),58)
        self.assertIsNotNone(self.rows['p35']['spatial_extent']);self.assertEqual(PoiMappingRepository().get('p35')['identity_mapping_status'],'NOT_FOUND')
    def test_point_museum_keeps_official_core_coordinate(self):
        poi=self.repo.get_poi_by_id('p28');self.assertEqual(self.rows['p28']['spatial_type'],'POINT')
        self.assertEqual(poi.coordinates,(31.167682,121.463841));self.assertIsNone(self.rows['p28']['spatial_extent'])
    def test_area_routes_to_anchor_not_extent_center(self):
        profile=self.rows['p35'];a=profile['route_anchor'];poi=self.repo.get_poi_by_id('p35')
        self.assertEqual(poi.coordinates,(a['lat'],a['lng']))
        vertices=profile['spatial_extent']['vertices'][:-1];center=(sum(v['lat'] for v in vertices)/len(vertices),sum(v['lng'] for v in vertices)/len(vertices))
        self.assertNotEqual(poi.coordinates,center);self.assertTrue(point_in_polygon(p(a['lat'],a['lng']),profile['spatial_extent']['vertices']))
        square=self.repo.get_poi_by_id('p14')
        self.assertEqual(square.coordinates,(31.238992,121.49039));self.assertNotEqual(square.coordinates,square.original_coordinates)
        self.assertEqual(self.rows['p14']['route_anchor']['source'],'AMAP_POI')
    def test_linear_anchor_is_entry_not_identity_coordinate(self):
        profile=self.rows['p34'];poi=self.repo.get_poi_by_id('p34');a=profile['route_anchor']
        self.assertEqual(poi.coordinates,(a['lat'],a['lng']));self.assertNotEqual(poi.coordinates,poi.original_coordinates)
        self.assertEqual(profile['spatial_type'],'LINEAR');self.assertEqual(profile['spatial_extent']['type'],'POLYLINE')
        self.assertNotEqual(profile['route_anchor']['lng'],profile['secondary_anchor']['lng'])
    def test_raw_kb_and_original_coordinates_are_not_overwritten_by_anchor(self):
        raw={r['id']:r for r in self.repo.get_raw_data()['pois']};poi=self.repo.get_poi_by_id('p34')
        self.assertEqual(poi.original_coordinates,(raw['p34']['location']['representative_lat'],raw['p34']['location']['representative_lng']))
        self.assertNotEqual(poi.coordinates,poi.original_coordinates)
    def test_identity_match_uses_identity_coordinate_not_navigation_anchor(self):
        poi=self.repo.get_poi_by_id('p34');loc=Location(*poi.original_coordinates,'GCJ02')
        row=match_poi(poi,[PoiCandidate('B0TEST12345','南京路步行街',loc,'黄浦区',poi_type='地名地址信息;道路名')],expected_district='黄浦区')
        self.assertEqual(row['identity_mapping_status'],'MATCHED');self.assertAlmostEqual(row['distance_m'],0)
    def test_profile_defensive_copies(self):
        repository=SpatialProfileRepository();repository.get('p35')['route_anchor']['lat']=0
        self.assertNotEqual(repository.get('p35')['route_anchor']['lat'],0)
        self.repo.get_spatial_profile('p35')['route_anchor']['lat']=0;self.assertNotEqual(self.repo.get_spatial_profile('p35')['route_anchor']['lat'],0)
    def test_legacy_and_candidate_kbs_do_not_load_production_profiles(self):
        repo=POIRepository('data/pois_phase2_5_final_candidate.json')
        self.assertIsNone(repo.spatial_profiles);self.assertIsNone(repo.get_spatial_profile('p35'))
        self.assertEqual(len(repo.get_all_pois()),59)
    def test_invalid_anchor_datum_number_confidence_or_provenance_rejected(self):
        for key,value in (('coordinate_system','WGS84'),('lat',float('nan')),('lng',181),('confidence',True),('confidence',1.1),('source','GUESSED')):
            rows=copy.deepcopy(self.rows);rows['p35']['route_anchor'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):SpatialProfileRepository(records=rows)
    def test_missing_area_anchor_and_missing_core_profile_rejected(self):
        rows=copy.deepcopy(self.rows);rows['p35']['route_anchor']=None
        with self.assertRaises(ValueError):SpatialProfileRepository(records=rows)
        rows=self.rows.copy();rows.pop('p35')
        with self.assertRaises(ValueError):SpatialProfileRepository(records=rows,core_ids=[p.id for p in self.repo.get_all_pois()])
    def test_provider_polygon_requires_actual_boundary_reference(self):
        rows=copy.deepcopy(self.rows);row=rows['p35'];row['extent_source']=row['spatial_extent']['extent_source']='PROVIDER'
        with self.assertRaises(ValueError):SpatialProfileRepository(records=rows)
        self.assertFalse(any(r['extent_source']=='PROVIDER' for r in self.rows.values()))
    def test_invalid_extent_shapes_rejected(self):
        for vertices in ([p(31,121),p(31,122),p(32,122)], [p(31,121),p(32,122),p(31,122),p(32,121),p(31,121)], [p(31,121)]*4):
            rows=copy.deepcopy(self.rows);rows['p35']['spatial_extent']['vertices']=vertices
            with self.assertRaises(ValueError):SpatialProfileRepository(records=rows)
    def test_missing_extent_requires_explicit_review_status(self):
        rows=copy.deepcopy(self.rows);rows['p35']['spatial_extent']=None
        with self.assertRaises(ValueError):SpatialProfileRepository(records=rows)
        rows['p35']['extent_status']='REVIEW_REQUIRED';SpatialProfileRepository(records=rows)
    def test_all_area_linear_have_documented_extents_and_secondary_linear_anchor(self):
        for row in self.rows.values():
            if row['spatial_type']!='POINT':self.assertIsNotNone(row['spatial_extent']);self.assertTrue(row['route_anchor']['notes']);self.assertTrue(row['spatial_extent']['notes'])
            if row['spatial_type']=='LINEAR':self.assertIsNotNone(row['secondary_anchor'])
            self.assertFalse(row['reviewed'])
    def test_xujiahui_polygon_covers_named_core_facilities_not_wider_district(self):
        extent=self.rows['p35']['spatial_extent'];e=json.loads(Path('examples/spatial_identity/provider_evidence.json').read_text(encoding='utf-8'))
        for q in ('美罗城','港汇恒隆广场'):self.assertTrue(within_extent(e['queries'][q][0]['location'],extent))
        self.assertFalse(within_extent(p(31.205,121.45),extent))
    def test_geometry_inside_outside_edge_and_vertex(self):
        polygon=[p(31,121),p(31,121.01),p(31.01,121.01),p(31.01,121),p(31,121)]
        for location,result in ((p(31.005,121.005),True),(p(31,121.005),True),(p(31,121),True),(p(31.02,121.02),False)):
            self.assertEqual(point_in_polygon(location,polygon),result)
    def test_linear_distance_segment_clamping_and_multiple_bends(self):
        extent=dict(type='START_END',start=p(31,121),end=p(31.01,121))
        self.assertAlmostEqual(distance_to_linear_extent_m(p(31.005,121),extent),0)
        self.assertGreater(distance_to_linear_extent_m(p(31.02,121),extent),1000)
        extent=dict(type='POLYLINE',vertices=[p(31,121),p(31.01,121),p(31.01,121.01)])
        self.assertAlmostEqual(distance_to_linear_extent_m(p(31.01,121.005),extent),0)
    def test_geometry_rejects_mixed_datums(self):
        with self.assertRaises(ValueError):distance_to_linear_extent_m(dict(lat=31,lng=121,coordinate_system='WGS84'),dict(type='START_END',start=p(31,121),end=p(31.01,121)))
    def test_proximity_still_measures_anchor_not_geofence(self):
        poi=self.repo.get_poi_by_id('p35');service=ProximityService(LocationService(None,None));result=service.check_arrival(Location(*poi.coordinates,'GCJ02'),poi)
        self.assertEqual(result.status,'ARRIVED');self.assertEqual((result.target_location.lat,result.target_location.lng),poi.coordinates)
        other=p(31.1909,121.4359);self.assertTrue(within_extent(other,self.rows['p35']['spatial_extent']))
        self.assertEqual(service.check_arrival(Location(**other),poi).status,'FAR')
    def test_corrected_provider_coordinates_are_distinct_from_spatial_anchor(self):
        e=json.loads(Path('examples/spatial_identity/provider_evidence.json').read_text(encoding='utf-8'))
        for pid in ('p10','p12','p34'):
            poi=self.repo.get_poi_by_id(pid);location=e['details'][pid]['normalized']['location']
            self.assertEqual(to_gcj02(*poi.original_coordinates,poi.original_coordinate_system),(location['lat'],location['lng']))
        self.assertEqual(PoiMappingRepository().get('p25')['amap_poi_id'],'B0I2KZFZRY')
        self.assertEqual(PoiMappingRepository().get('pz_b72e3b8998b3')['amap_poi_id'],'B00155FLFD')

class SpatialIntegrationTests(unittest.TestCase):
    def setUp(self):self.repo=POIRepository();self.walking,self.provider=synthetic_walking()
    def plan(self,pid='p35'):
        poi=self.repo.get_poi_by_id(pid)
        return WalkingRoutePlanner(self.repo,walking_service=self.walking).generate_route(RouteRequest(180,preferred_zone=poi.zone_id,must_go_poi_ids=[pid],interest_tags=['architecture','history']))
    def test_not_found_identity_generates_and_hydrates_anchor_route(self):
        plan=self.plan();self.assertEqual(plan.status,'success');self.assertEqual(plan.walking_data_status,'AVAILABLE')
        stop=next(s for s in plan.ordered_pois if s.poi_id=='p35');self.assertEqual(tuple(stop.estimated_coordinates),self.repo.get_poi_by_id('p35').coordinates)
        legs=[l for l in plan.walking_legs if l['to_poi_id']=='p35'];self.assertTrue(legs)
        for leg in legs:self.assertEqual((leg['destination']['lat'],leg['destination']['lng']),self.repo.get_poi_by_id('p35').coordinates)
        self.assertGreater(plan.walking_distance_m,0)
    def test_linear_endpoint_and_planning_use_recommended_entry(self):
        plan=self.plan('p34');self.assertEqual(plan.status,'success')
        stop=next(s for s in plan.ordered_pois if s.poi_id=='p34');anchor=self.repo.get_poi_by_id('p34').coordinates
        self.assertEqual(tuple(stop.estimated_coordinates),anchor)
        endpoints=[(l['destination']['lat'],l['destination']['lng']) for l in plan.walking_legs]
        endpoints += [(l['origin']['lat'],l['origin']['lng']) for l in plan.walking_legs]
        self.assertIn(anchor,endpoints)
    def test_not_found_identity_replan_skip_remove_keeps_frozen_trip_semantics(self):
        plan=self.plan();intent=RouteIntent(RouteMode.PLAN_FOR_ME,available_minutes=180,preferred_zone='wukang_fuxing_xujiahui',must_go_poi_ids=['p35'],interest_tags=['architecture','history'])
        store=InMemoryTripStore();core=TripService(store);trip=core.create_trip(plan,intent);core.start_trip(trip.trip_id)
        before=store.get(trip.trip_id);result=ReplanningCoordinator(store,self.repo,walking_service=self.walking).replan(trip.trip_id,TripStateDelta(request_replan=True,remaining_minutes=160))
        self.assertTrue(result.committed,result.to_dict());after=store.get(trip.trip_id)
        self.assertEqual(after.original_route,before.original_route);self.assertEqual(after.route_versions[0],before.route_versions[0]);self.assertEqual(after.active_route['walking_data_status'],'AVAILABLE')
        self.assertIn('p35',after.remaining_poi_ids);self.assertEqual(TripState.from_dict(after.to_dict()).to_dict(),after.to_dict())
        # Remove optional p35 in a second ordinary Trip; no new identity query/refill.
        plan=self.plan();plan.request['must_go_poi_ids']=[]
        for s in plan.ordered_pois:s.must_go=False
        intent.must_go_poi_ids=[];trip=core.create_trip(plan,intent);core.start_trip(trip.trip_id)
        state=store.get(trip.trip_id);before_ids=state.remaining_poi_ids
        core.skip_stop(trip.trip_id,'p35');state=store.get(trip.trip_id)
        self.assertEqual(state.remaining_poi_ids,[pid for pid in before_ids if pid!='p35']);self.assertEqual(state.original_route['ordered_pois'],json.loads(json.dumps(plan.to_dict()['ordered_pois'])))
        from src.route_mutation import RouteMutationService
        mutation=RouteMutationService(self.repo,walking_service=self.walking)
        trip=core.create_trip(plan,intent);core.start_trip(trip.trip_id)
        before=store.get(trip.trip_id);stops=copy.deepcopy(before.active_route['ordered_pois'])
        edited=mutation.remove_only(stops,'p35')
        policy=dict(time_constraint_mode='soft',target_deadline=180,hard_deadline=None)
        rebuilt=mutation.build_route(before,edited,intent.to_dict(),policy)
        self.assertEqual([s['poi_id'] for s in rebuilt['ordered_pois']],[s['poi_id'] for s in stops if s['poi_id']!='p35'])
        self.assertEqual(store.get(trip.trip_id).original_route,before.original_route)
        self.assertEqual(rebuilt['walking_data_status'],'AVAILABLE')
        staged=store.get(trip.trip_id);revision=staged.state_revision
        staged.commit_mutation(rebuilt,intent.to_dict(),policy,reason='REMOVE_ONLY',diagnostics=mutation.diff(stops,edited))
        store.save_if_revision(staged,revision);after=store.get(trip.trip_id)
        self.assertNotIn('p35',after.remaining_poi_ids);self.assertNotIn('p35',after.skipped_poi_ids)
        self.assertEqual(after.original_route,before.original_route);self.assertEqual(after.route_versions[0],before.route_versions[0])
        self.assertEqual(len(after.route_versions),2)
    def test_anchor_failure_keeps_original_walking_fallback(self):
        plan=RouteEngine(self.repo).generate_route(RouteRequest(180,preferred_zone='wukang_fuxing_xujiahui',must_go_poi_ids=['p35']))
        hydrated=WalkingRouteService().hydrate_walking_route(plan)
        self.assertEqual(hydrated.walking_data_status,'FALLBACK_ESTIMATE');self.assertEqual([s.poi_id for s in plan.ordered_pois],[s.poi_id for s in hydrated.ordered_pois])

if __name__=='__main__':unittest.main()
