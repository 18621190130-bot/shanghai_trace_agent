import copy,os,time,unittest
from unittest.mock import patch,Mock
from tests.test_web_frontend_api import WebAdapterTests,intent
from src.web_arrival import quality,remaining_target
from src.providers.amap.arrival import entrance_coordinate
class ArrivalTests(unittest.TestCase):
 setUp=WebAdapterTests.setUp
 def start(self):
  t=self.app.generate(self.session,intent())['trip'];return self.app.action(self.session,{'action':'start','revision':t['state_revision']})['trip']
 def body(self,source='DEMO',offset=0):
  c=self.app.arrivals.context(self.session);p=c['target_location'];return dict(trip_id=c['trip_id'],revision=c['revision'],poi_id=c['target']['poi_id'],source=source,position=dict(latitude=p['lat']+offset/111195,longitude=p['lng'],coordinate_system='GCJ02',accuracy=1,timestamp=time.time()*1000,source=source))
 def test_not_active(self):
  self.app.generate(self.session,intent());self.assertEqual(self.app.arrivals.check(self.session,{} )['status'],'INACTIVE')
 def test_demo_real_proximity_and_no_domain_mutation(self):
  old=self.start()
  with patch.dict(os.environ,TRACEMATE_ENABLE_DEMO_MODE='true'):
   with patch.object(self.app.world.proximity,'check_arrival',wraps=self.app.world.proximity.check_arrival) as check:
    for offset,status in [(700,'FAR'),(130,'NEAR'),(0,'ARRIVED')]:self.assertEqual(self.app.arrivals.check(self.session,self.body(offset=offset))['status'],status)
    self.assertEqual(check.call_count,3)
  self.assertEqual(self.app.current_trip(self.session),old)
 def test_manual_and_completed_via_existing_action(self):
  before=self.start();r=self.app.arrivals.check(self.session,{**self.body('MANUAL'),'position':None});self.assertEqual(r['arrival_source'],'MANUAL');self.assertEqual(self.app.current_trip(self.session),before)
  t=self.app.action(self.session,{'action':'complete','revision':before['state_revision'],'poi_id':r['context']['target']['poi_id']})['trip'];self.assertIn(r['context']['target']['poi_id'],t['visited_poi_ids']);self.assertNotEqual(remaining_target(t)['poi_id'],r['context']['target']['poi_id'])
 def test_low_quality_stale_future_invalid_rejected_before_proximity(self):
  self.start()
  with patch.dict(os.environ,TRACEMATE_ENABLE_DEMO_MODE='true'),patch.object(self.app.world,'check_arrival') as check:
   for change in ({'accuracy':80},{'accuracy':-1},{'timestamp':time.time()*1000-31000},{'timestamp':time.time()*1000+20000},{'latitude':float('nan')}):
    b=self.body();b['position'].update(change);self.assertEqual(self.app.arrivals.check(self.session,b)['status'],'LOW_QUALITY')
   check.assert_not_called()
 def test_demo_disabled_and_wrong_target(self):
  self.start()
  with patch.dict(os.environ,TRACEMATE_ENABLE_DEMO_MODE='false'):
   with self.assertRaises(ValueError):self.app.arrivals.check(self.session,self.body())
  with self.assertRaisesRegex(ValueError,'stale_state_conflict'):self.app.arrivals.check(self.session,{**self.body('MANUAL'),'poi_id':'p4'})
 def test_gps_coordinate_normalization_contract(self):
  self.start();b=self.body('GPS')
  with self.assertRaises(ValueError):self.app.arrivals.check(self.session,b)
  from src.walking_models import Location
  target=self.app.arrivals.context(self.session)['target_location'];b['position']['coordinate_system']='WGS84'
  with patch.object(self.app.world.locations,'normalize_location_for_amap',return_value=Location(target['lat'],target['lng'],'GCJ02')) as normalize:
   self.assertEqual(self.app.arrivals.check(self.session,b)['status'],'ARRIVED');self.assertEqual(normalize.call_args.args[0]['coordinate_system'],'WGS84')
 def test_area_linear_use_frozen_anchor(self):
  for p in self.repo.get_all_pois():
   profile=self.repo.get_spatial_profile(p.id)
   if profile['spatial_type'] in ('AREA','LINEAR'):
    a=profile['route_anchor'];self.assertEqual(p.coordinates,(a['lat'],a['lng']))
    out=self.app.world.check_arrival({'lat':a['lat'],'lng':a['lng'],'coordinate_system':'GCJ02'},p.id);self.assertEqual(out.status,'ARRIVED')
 def test_entrance_field_does_not_parse_navi_id(self):
  target=(31.2,121.4);self.assertIsNone(entrance_coordinate({'navi_poiid':'121.4,31.2'},target));self.assertIsNone(entrance_coordinate({'entr_location':'0,0'},target));self.assertEqual(entrance_coordinate({'entr_location':'121.4,31.2'},target)['coordinate_system'],'GCJ02')
 def test_entrance_fallback_and_empty_content(self):
  before=self.repo.get_raw_data()
  with patch('src.web_arrival.Path.read_text',return_value='{"records":{}}'):
   r=self.app.arrivals.content('p35')
  self.assertEqual(r['location']['display_note'],'suggestedStart');self.assertFalse(any(r['arrival_hook'].values()));self.assertFalse(any(r['what_to_notice'].values()));self.assertEqual(self.repo.get_raw_data(),before)
 def test_provider_entrance_and_route_unchanged(self):
  before=self.start();pid='p13';poi=self.repo.get_poi_by_id(pid);identity=self.app.arrivals.mappings[pid]['amap_poi_id'];lat,lng=poi.coordinates
  self.app.arrivals.cache[pid]={'provider_id':identity,'navi':{'entr_location':f'{lng},{lat}'}}
  self.assertEqual(self.app.arrivals.content(pid)['location']['location_type'],'AMAP_PROVIDER_ENTRANCE');self.assertEqual(self.app.current_trip(self.session),before)
 def test_reviewed_point_and_entrance_image_gate(self):
  import json
  raw={'records':{'p35':{'entrance_image':{'src':'/assets/poi-images/p35.png'}}}}
  with patch('src.web_arrival.Path.read_text',return_value=json.dumps(raw)):
   result=self.app.arrivals.content('p35');self.assertIsNone(result['entrance_image']);self.assertEqual(result['location']['source_type'],'UNAVAILABLE');self.assertIsNone(result['location']['arrival_location']);self.assertIsNotNone(result['location']['suggested_location'])
  raw['records']['p35'].update(arrival_point={'reviewed':True,'location':{'lat':31.19,'lng':121.43,'coordinate_system':'GCJ02'}},entrance_image={'src':'/assets/poi-images/p35.png','reviewed':True})
  with patch('src.web_arrival.Path.read_text',return_value=json.dumps(raw)):
   result=self.app.arrivals.content('p35');self.assertEqual(result['location']['source_type'],'TRACE_REVIEWED_ARRIVAL_POINT');self.assertEqual(result['location']['display_note'],'suggestedStart');self.assertIsNotNone(result['entrance_image'])
if __name__=='__main__':unittest.main()
