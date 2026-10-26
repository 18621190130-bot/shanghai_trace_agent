"""Guidance boundaries and direction persistence, with deterministic provider fixtures."""
import copy
import unittest
from unittest.mock import Mock, patch
from src.map_guidance import MapGuidance, direction_lock
from src.providers.base import ProviderUnavailableError
from src.services.walking_route_service import WalkingRouteService
from src.providers.amap.walking import AmapWalkingProvider
from src.web_app import WebApplication
from src.route_entry import RouteEntryService
from src.poi_repository import POIRepository
from src.trip_state import TripState

ORIGIN=dict(lat=31.2,lng=121.4,coordinate_system='GCJ02')
DEST=dict(lat=31.21,lng=121.41,coordinate_system='GCJ02')
LINE='121.4,31.2;121.405,31.207;121.41,31.21'


class GuidanceTests(unittest.TestCase):
    def setUp(self):
        self.client=Mock();self.client.redact_text.side_effect=lambda s:s
        self.service=MapGuidance(self.client,WalkingRouteService(AmapWalkingProvider(self.client)))

    def query(self,mode):return self.service.route(dict(origin=ORIGIN,destination=DEST,mode=mode))

    def test_walking_reuses_provider_cache(self):
        self.client.get.return_value={'route':{'paths':[dict(distance='100',duration='80',steps=[dict(polyline=LINE)])]}}
        result=self.query('walking');self.assertEqual(result['availability'],'AVAILABLE');self.query('walking')
        self.assertEqual(self.client.get.call_count,1)
        result['segments'].clear();self.assertTrue(self.query('walking')['segments'])

    def test_transit_disjoint_actual_segments(self):
        self.client.get.return_value={'route':{'transits':[dict(distance='5000',duration='800',segments=[{'walking':{'steps':[dict(polyline=LINE)]},'bus':{'buslines':[dict(name='Metro',polyline='121.42,31.22;121.43,31.23')]},'railway':{'via_stops':[],'alters':[],'spaces':[]}}])]}}
        result=self.query('transit');self.assertEqual(len(result['segments']),2)
        self.assertNotEqual(result['segments'][0]['polyline'][-1],result['segments'][1]['polyline'][0])

    def test_transit_without_real_vehicle_geometry_unavailable(self):
        self.client.get.return_value={'route':{'transits':[dict(distance='5000',duration='800',segments=[{'bus':{'buslines':[{'name':'Metro'}]}}])]}}
        self.assertEqual(self.query('transit')['availability'],'UNAVAILABLE')

    def test_bicycle_and_taxi_cost_shapes(self):
        for mode,path in [('bicycle',dict(cost={'duration':'100'})),('bicycle',dict(duration='100')),('taxi',dict(duration='100'))]:
            self.client.get.return_value={'route':{'paths':[dict(**path,distance='400',steps=[dict(polyline=LINE)])]}}
            self.assertEqual(self.query(mode)['duration_s'],100)
        self.assertIn('show_fields',self.client.get.call_args_list[0].args[1])

    def test_failure_and_bad_coordinates(self):
        self.client.get.side_effect=ProviderUnavailableError()
        result=self.query('taxi');self.assertEqual(result['segments'],[]);self.assertIsNone(result['duration_s'])
        with self.assertRaises(ValueError):self.service.route(dict(origin={**ORIGIN,'lat':True},destination=DEST))
        with self.assertRaises(ValueError):self.service.location(dict(lat=0,lng=0))
        with self.assertRaises(ValueError):self.query('flying')

    def test_gps_conversion_before_route(self):
        self.client.get.side_effect=[dict(locations='121.401,31.201'),{'route':{'paths':[dict(distance='100',duration='80',steps=[dict(polyline=LINE)])]}}]
        r=self.service.route(dict(origin={**ORIGIN,'coordinate_system':'WGS84'},destination=DEST))
        self.assertEqual(r['origin']['coordinate_system'],'GCJ02');self.assertEqual(r['origin']['lng'],121.401)

    def test_search_preserves_provider_coordinates_and_no_name_inference(self):
        self.client.get.return_value=dict(pois=[dict(id='A',name='Mall (Zhongshan Park)',cityname='Shanghai',adname='Changning',address='1018 Changning Road',location='121.4,31.2'),dict(id='B',name='Invalid',location='')])
        rows=self.service.search(dict(query='mall'))['results']
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['name'],'Mall (Zhongshan Park)')
        self.assertIn('1018 Changning Road',rows[0]['address'])

    def test_fastest_valid_transit_not_first_ranked_or_broken_path(self):
        def path(duration,valid=True):return dict(distance='400',duration=str(duration),segments=[{'bus':{'buslines':[dict(name='Bus',polyline=LINE if valid else '')]}}])
        self.client.get.return_value={'route':{'transits':[path(2500),path(500,False),path(900)]}}
        result=self.query('transit')
        self.assertEqual(result['duration_s'],900)

    def test_reverse_geocoding_uses_actual_address(self):
        self.client.get.return_value={'regeocode':{'formatted_address':'Shanghai Changning Road 1018'}}
        result=self.service.describe({'location':ORIGIN})
        self.assertEqual(result['name'],'Shanghai Changning Road 1018')
        self.assertEqual(result['location'],ORIGIN)

class DirectionTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict('os.environ',AMAP_WEB_SERVICE_KEY='',DEEPSEEK_API_KEY='');self.env.start();self.addCleanup(self.env.stop)
        repo=POIRepository();self.app=WebApplication(repository=repo,entry=RouteEntryService(repo,walking_service=WalkingRouteService()))
        _,self.session=self.app.session()
        self.before=self.app.generate(self.session,dict(intent=dict(route_mode='plan_for_me',available_minutes=180,interest_tags=['architecture','local_life'],preferred_zone='wukang_fuxing_xujiahui')))['trip']

    def test_reverse_original_immutable_replay_and_revert(self):
        self.assertIsNone(self.before['direction_lock'])
        result=self.app.guidance_direction(self.session,dict(direction='reverse',revision=self.before['state_revision']))['trip']
        self.assertEqual(result['original_route'],self.before['original_route'])
        self.assertEqual([s['poi_id'] for s in result['active_route']['ordered_pois']],[s['poi_id'] for s in reversed(self.before['active_route']['ordered_pois'])])
        self.assertEqual(len(result['route_versions']),2)
        restored=self.app.guidance_direction(self.session,dict(direction='original',revision=result['state_revision']))['trip']
        self.assertEqual(restored['original_route'],self.before['original_route'])
        self.assertEqual(restored['remaining_poi_ids'],self.before['remaining_poi_ids'])
        self.assertEqual(len(restored['route_versions']),3)

    def test_stale_and_active_direction_changes_rejected(self):
        with self.assertRaisesRegex(ValueError,'stale'):self.app.guidance_direction(self.session,dict(direction='reverse',revision=-1))
        active=self.app.action(self.session,dict(action='start',revision=self.before['state_revision']))['trip']
        with self.assertRaisesRegex(ValueError,'direction_locked'):self.app.guidance_direction(self.session,dict(direction='reverse',revision=active['state_revision']))

    def test_tampered_stop_facts_rejected(self):
        trip=self.app.store.get(self.before['trip_id']);route=trip.active_route
        route['ordered_pois'].reverse();route['ordered_pois'][0]['estimated_stay_minutes']+=10
        with self.assertRaises(ValueError):trip.set_walk_direction(route)

    def test_lock_constraints(self):
        for field in ('fixed_order','time_windows','narrative_constraints','direction_locked'):
            self.assertEqual(direction_lock(dict(request={field:True})),'constrained_order')
        self.assertEqual(direction_lock(dict(request={'start_poi_id':'p1'})),'fixed_start')

    def test_flexible_modes_ignore_legacy_start_but_keep_real_constraints(self):
        for mode in ('surprise_me','places_in_mind'):
            request=dict(route_mode=mode,start_poi_id='p1',start_lat=31.2)
            self.assertIsNone(direction_lock(dict(request=request)))
            self.assertEqual(direction_lock(dict(request={**request,'fixed_order':True})),'constrained_order')

    def test_places_and_surprise_allow_full_reversal(self):
        for mode in ('surprise_me','places_in_mind'):
            body=dict(route_mode=mode,available_minutes=240,interest_tags=[],preferred_zone='west_bund',surprise_seed=42)
            if mode=='places_in_mind':body['must_go_poi_ids']=['p28','p5']
            before=self.app.generate(self.session,dict(intent=body))['trip']
            self.assertIsNone(before['direction_lock'])
            reversed_trip=self.app.guidance_direction(self.session,dict(direction='reverse',revision=before['state_revision']))['trip']
            self.assertEqual([p['poi_id'] for p in reversed_trip['active_route']['ordered_pois']],list(reversed([p['poi_id'] for p in before['active_route']['ordered_pois']])))
            self.assertEqual(reversed_trip['original_route'],before['original_route'])
            restored=self.app.guidance_direction(self.session,dict(direction='original',revision=reversed_trip['state_revision']))['trip']
            self.assertEqual(restored['remaining_poi_ids'],before['remaining_poi_ids'])

    def test_guidance_never_changes_trip(self):
        snapshot=self.app.current_trip(self.session)
        self.app.guidance.route(dict(origin=ORIGIN,destination=DEST))
        self.assertEqual(self.app.current_trip(self.session),snapshot)

    def test_start_visit_and_replan_after_reversal_keep_original(self):
        reversed_trip=self.app.guidance_direction(self.session,dict(direction='reverse',revision=self.before['state_revision']))['trip']
        active=self.app.action(self.session,dict(action='start',revision=reversed_trip['state_revision']))['trip']
        first=active['remaining_poi_ids'][0]
        visited=self.app.action(self.session,dict(action='complete',poi_id=first,revision=active['state_revision']))['trip']
        result=self.app.action(self.session,dict(action='replan',revision=visited['state_revision'],delta={'remaining_minutes':120}))['trip']
        self.assertIn(first,result['visited_poi_ids'])
        self.assertEqual(result['original_route'],self.before['original_route'])
        self.assertEqual(result['route_versions'][1]['reason'],'SMART_START_DIRECTION')

    def test_reversal_failure_is_atomic(self):
        with patch.object(self.app.entry.walking_service,'hydrate_dict',side_effect=ValueError('failure')):
            with self.assertRaises(ValueError):self.app.guidance_direction(self.session,dict(direction='reverse',revision=self.before['state_revision']))
        self.assertEqual(self.app.current_trip(self.session),self.before)
