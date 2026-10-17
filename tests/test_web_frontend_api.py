"""Adapter integration, isolation and transport checks; no live provider calls."""
import copy
from http.client import HTTPConnection
import io
import json
import os
import threading
import unittest
from unittest.mock import patch,Mock
from http.server import ThreadingHTTPServer
from src.web_app import WebApplication
from src.web_map import StaticMapService
from src.route_entry import RouteEntryService
from src.services.walking_route_service import WalkingRouteService
from src import POIRepository
from src.world_models import PoiLiveInfo
from src.providers.base import ProviderUnavailableError
from web_server import handler_for


def intent(mode='plan_for_me',**changes):
    result=dict(route_mode=mode,available_minutes=180,interest_tags=['architecture','local_life'],preferred_zone='wukang_fuxing_xujiahui')
    result.update(changes);return dict(intent=result)


class WebAdapterTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,AMAP_WEB_SERVICE_KEY='',DEEPSEEK_API_KEY='');self.env.start();self.addCleanup(self.env.stop)
        self.repo=POIRepository();entry=RouteEntryService(self.repo,walking_service=WalkingRouteService())
        self.app=WebApplication(repository=self.repo,entry=entry)
        self.token,self.session=self.app.session()

    def generate(self):return self.app.generate(self.session,intent())

    def test_bootstrap_real_core58_without_credentials_or_stories(self):
        value=self.app.bootstrap(self.session)
        self.assertEqual(len(value['pois']),58);self.assertIsNone(value['trip'])
        self.assertNotIn('culture_bridge',json.dumps(value))
        self.assertNotIn('API_KEY',json.dumps(value))
        p=next(p for p in value['pois'] if p['id']=='p35')
        self.assertEqual(p['coordinates'],self.repo.get_poi_by_id('p35').coordinates)

    def test_plan_for_me_real_engine_and_planned_trip(self):
        result=self.generate();self.assertEqual(result['entry']['status'],'success');self.assertEqual(result['trip']['status'],'PLANNED')
        self.assertGreaterEqual(len(result['trip']['active_route']['ordered_pois']),3)
        self.assertEqual(result['trip']['active_route']['walking_data_status'],'FALLBACK_ESTIMATE')

    def test_places_preserves_must_go(self):
        result=self.app.generate(self.session,intent('places_in_mind',available_minutes=240,interest_tags=[],must_go_poi_ids=['p28','p5'],preferred_zone='west_bund'))
        self.assertEqual(result['entry']['status'],'success')
        ids=[s['poi_id'] for s in result['trip']['active_route']['ordered_pois']]
        self.assertTrue({'p28','p5'}<=set(ids))

    def test_surprise_uses_existing_seed_and_start(self):
        result=self.app.generate(self.session,intent('surprise_me',interest_tags=[],preferred_zone='west_bund',start_lat=31.167682,start_lng=121.463841,start_coordinate_system='GCJ-02',surprise_seed=42))
        self.assertIn(result['entry']['status'],('success','needs_route_quality_clarification'))
        self.assertIsNotNone(result['entry']['surprise_theme'])

    def test_missing_fields_go_through_real_clarification(self):
        result=self.app.generate(self.session,{'intent':{'route_mode':'places_in_mind'}})
        self.assertEqual(result['entry']['status'],'needs_clarification')
        result=self.app.clarify(self.session,{'answers':{'available_minutes':240,'must_go_poi_ids':['p28','p5']}})
        self.assertEqual(result['entry']['status'],'success')

    def test_natural_language_unavailable_is_explicit(self):
        with self.assertRaisesRegex(ValueError,'natural_language_unavailable'):self.app.generate(self.session,{'text':'walk here'})

    def test_session_isolation(self):
        self.generate();_,other=self.app.session()
        self.assertIsNone(self.app.current_trip(other))
        self.assertEqual(self.app.session(self.token)[1],self.session)

    def test_progress_uses_existing_state_and_cas(self):
        generated=self.generate()['trip'];pid=generated['active_route']['ordered_pois'][0]['poi_id']
        started=self.app.action(self.session,{'action':'start','revision':generated['state_revision']})['trip']
        done=self.app.action(self.session,{'action':'complete','revision':started['state_revision'],'poi_id':pid})['trip']
        self.assertIn(pid,done['visited_poi_ids']);self.assertGreater(done['state_revision'],started['state_revision'])
        with self.assertRaisesRegex(ValueError,'stale_state_conflict'):self.app.action(self.session,{'action':'skip','revision':started['state_revision'],'poi_id':pid})

    def test_active_generation_cannot_silently_replace_trip(self):
        trip=self.generate()['trip'];self.app.action(self.session,{'action':'start','revision':trip['state_revision']})
        before=self.app.current_trip(self.session)
        with self.assertRaisesRegex(ValueError,'active_trip_requires_replan'):self.generate()
        self.assertEqual(before,self.app.current_trip(self.session))

    def test_confirmed_replacement_ends_old_walk(self):
        trip=self.generate()['trip']
        old=self.app.action(self.session,{'action':'start','revision':trip['state_revision']})['trip']
        body={**intent(), 'replace_active':True,'expected_trip_id':old['trip_id'],'expected_revision':old['state_revision']}
        with self.assertRaisesRegex(ValueError,'stale_state_conflict'):
            self.app.generate(self.session,{**body,'expected_revision':-1})
        self.assertEqual(self.app.current_trip(self.session),old)
        with patch.object(self.app.entry,'generate',side_effect=ValueError('generation_failed')):
            with self.assertRaisesRegex(ValueError,'generation_failed'):self.app.generate(self.session,body)
        self.assertEqual(self.app.current_trip(self.session),old)
        result=self.app.generate(self.session,body)
        self.assertEqual(result['ended_trip']['status'],'ABANDONED')
        self.assertEqual(result['ended_trip']['trip_id'],old['trip_id'])
        self.assertEqual(result['trip']['status'],'PLANNED')
        self.assertNotEqual(result['trip']['trip_id'],old['trip_id'])

    def test_replacement_clarification_keeps_old_walk_until_success(self):
        trip=self.generate()['trip']
        old=self.app.action(self.session,{'action':'start','revision':trip['state_revision']})['trip']
        result=self.app.generate(self.session,{'intent':{'route_mode':'places_in_mind'},'replace_active':True,'expected_trip_id':old['trip_id'],'expected_revision':old['state_revision']})
        self.assertEqual(result['entry']['status'],'needs_clarification')
        self.assertEqual(result['trip'],old)
        result=self.app.clarify(self.session,{'answers':{'available_minutes':240,'must_go_poi_ids':['p28','p5']}})
        self.assertEqual(result['ended_trip']['status'],'ABANDONED')
        self.assertEqual(result['trip']['status'],'PLANNED')

    def test_replan_failure_preserves_current_trip(self):
        trip=self.generate()['trip'];started=self.app.action(self.session,{'action':'start','revision':trip['state_revision']})['trip']
        result=self.app.action(self.session,{'action':'replan','revision':started['state_revision'],'delta':{'remaining_minutes':1}})
        self.assertFalse(result['replan']['committed']);self.assertEqual({k:v for k,v in result['trip'].items() if k!='change_history'},started)
        self.assertEqual(result['trip']['change_history'][-1]['execution_status'],'FAILED')

    def test_reality_read_only(self):
        self.generate();before=self.app.current_trip(self.session);core=self.repo.get_raw_data()
        result=self.app.reality(self.session,{})
        self.assertIn(result['status'],('PARTIAL','UNAVAILABLE'))
        self.assertEqual(before,self.app.current_trip(self.session));self.assertEqual(core,self.repo.get_raw_data())

    def test_nearby_no_core_append(self):
        self.generate();before=self.app.current_trip(self.session)
        result=self.app.nearby({'poi_id':'p35','categories':['CAFE']})
        self.assertEqual(result['status'],'UNAVAILABLE');self.assertEqual(before,self.app.current_trip(self.session))

    def test_unknown_fields_and_actions_rejected(self):
        with self.assertRaises(ValueError):self.app.generate(self.session,{'intent':{'route_mode':'places_in_mind','api_key':'private'}})
        trip=self.generate()['trip']
        with self.assertRaises(ValueError):self.app.action(self.session,{'action':'delete_all','revision':trip['state_revision']})


class WebFeedbackTests(unittest.TestCase):
    setUp=WebAdapterTests.setUp
    # Reuse only setup, avoiding inherited test duplication below.
    def west(self):
        result=self.app.generate(self.session,intent('places_in_mind',preferred_zone='west_bund',must_go_poi_ids=['p28','p5'],available_minutes=240))
        trip=result['trip'];return self.app.action(self.session,dict(action='start',revision=trip['state_revision']))['trip']

    def test_english_catalogue_is_complete(self):
        import re
        for p in self.app.catalogue:
            self.assertTrue(p['summary']['summary_en']);self.assertFalse(re.search('[\u3400-\u9fff]',p['name_en']+p['summary']['summary_en']))

    def test_cross_zone_initial_selection_rejected(self):
        with self.assertRaisesRegex(ValueError,'zone_mismatch'):
            self.app.generate(self.session,intent('places_in_mind',must_go_poi_ids=['p28','p13'],preferred_zone=None))

    def test_explicit_add_preserves_existing_order_and_cross_zone_is_rejected(self):
        trip=self.west();old=[p['poi_id'] for p in trip['active_route']['ordered_pois']]
        result=self.app.turn(self.session,dict(revision=trip['state_revision'],kind='ADD_MUST_GO',targets=['p29']))
        self.assertEqual(result['turn']['status'],'success_mutated',result['turn'])
        ids=[p['poi_id'] for p in result['trip']['active_route']['ordered_pois']]
        self.assertIn('p29',ids);self.assertEqual([p for p in ids if p in old],old)
        with self.assertRaisesRegex(ValueError,'zone_mismatch'):
            self.app.turn(self.session,dict(revision=result['trip']['state_revision'],kind='ADD_MUST_GO',targets=['p13']))

    def test_natural_language_reaches_existing_executor(self):
        from src.llm_client import MockLLMClient
        from src.trip_actions import TripActionProposal,TripUtteranceProposal
        trip=self.west();self.app.llm=MockLLMClient(responses=[TripUtteranceProposal([TripActionProposal('ADD_MUST_GO',target_mentions=['TANK Shanghai'])]).to_dict()])
        result=self.app.turn(self.session,dict(revision=trip['state_revision'],text='Make sure I visit TANK Shanghai.'))
        self.assertEqual(result['turn']['status'],'success_mutated');self.assertIn('p29',result['trip']['current_intent']['must_go_poi_ids'])
        self.assertNotIn('nlu_trace',result['turn'])

    def test_control_reorder_and_remove_are_local(self):
        trip=self.west();result=self.app.turn(self.session,dict(revision=trip['state_revision'],kind='MOVE_PLACE_NEXT',targets=['p5']))
        self.assertEqual(result['trip']['active_route']['ordered_pois'][0]['poi_id'],'p5')
        result=self.app.turn(self.session,dict(revision=result['trip']['state_revision'],kind='REMOVE_PLACE',targets=['p5']))
        self.assertEqual([p['poi_id'] for p in result['trip']['active_route']['ordered_pois']],['p28'])


class WebTransportTests(unittest.TestCase):
    def setUp(self):
        WebAdapterTests.setUp(self);self.server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(self.app))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)

    def get(self,path,headers=None):
        connection=HTTPConnection('127.0.0.1',self.server.server_port);connection.request('GET',path,headers=headers or {})
        response=connection.getresponse();body=response.read();connection.close();return response,body

    def test_http_bootstrap_cookie_http_only(self):
        response,body=self.get('/api/bootstrap')
        self.assertEqual(response.status,200);self.assertIn('HttpOnly',response.getheader('Set-Cookie'));self.assertEqual(len(json.loads(body)['pois']),58)

    def test_static_only_frontend_and_path_traversal_blocked(self):
        response,body=self.get('/');self.assertEqual(response.status,200);self.assertIn(b'TraceMate',body)
        for path in ('/../src/llm_client.py','/%2e%2e/data/pois.json','/src/poi_repository.py'):
            with self.subTest(path=path):self.assertEqual(self.get(path)[0].status,404)

    def test_untrusted_host_blocked(self):self.assertEqual(self.get('/',{'Host':'attacker.example'})[0].status,403)

    def test_cross_origin_and_non_json_post_blocked(self):
        for headers,status in (({'Origin':'https://attacker.example','Content-Type':'application/json'},403),({'Content-Type':'text/plain'},415)):
            connection=HTTPConnection('127.0.0.1',self.server.server_port);connection.request('POST','/api/generate','{}',headers)
            response=connection.getresponse();response.read();self.assertEqual(response.status,status);connection.close()


class StaticMapTests(unittest.TestCase):
    def query(self):return dict(lng='121.46',lat='31.16',zoom='14',width='800',height='600')

    def test_missing_key_safe(self):
        with patch.dict(os.environ,AMAP_WEB_SERVICE_KEY=''),self.assertRaises(ProviderUnavailableError):StaticMapService().get(self.query())

    def test_map_cache_and_validated_binary(self):
        response=io.BytesIO(b'\x89PNG\r\n\x1a\nfixture');response.headers={'Content-Type':'image/png'}
        opener=Mock(return_value=response);service=StaticMapService(opener)
        with patch.dict(os.environ,AMAP_WEB_SERVICE_KEY='secret-placeholder'):
            first=service.get(self.query());second=service.get(self.query())
        self.assertEqual(first,second);opener.assert_called_once();self.assertEqual(first[1],'image/png')

    def test_provider_error_does_not_echo_url_or_secret(self):
        service=StaticMapService(Mock(side_effect=RuntimeError('secret-placeholder')))
        with patch.dict(os.environ,AMAP_WEB_SERVICE_KEY='secret-placeholder'),self.assertRaises(ProviderUnavailableError) as cm:service.get(self.query())
        self.assertNotIn('secret-placeholder',str(cm.exception))

    def test_invalid_view_rejected_before_network(self):
        service=StaticMapService(Mock())
        for changes in ({'lng':'nan'},{'zoom':'19'},{'width':'99999'},{'lat':'90'}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):service.get(dict(self.query(),**changes))
        service.opener.assert_not_called()
