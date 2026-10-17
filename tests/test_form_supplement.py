import os,unittest
from unittest.mock import Mock,patch
from src.web_app import WebApplication
from src.route_entry import RouteEntryService
from src.poi_repository import POIRepository
from src.services.walking_route_service import WalkingRouteService
from src.intent_models import RouteIntent,RouteMode
class FormTests(unittest.TestCase):
 def setUp(self):
  self.env=patch.dict(os.environ,AMAP_WEB_SERVICE_KEY='',DEEPSEEK_API_KEY='');self.env.start();self.addCleanup(self.env.stop)
  repo=POIRepository();self.app=WebApplication(repository=repo,entry=RouteEntryService(repo,walking_service=WalkingRouteService()))
  self.app.entry.parser=Mock();_,self.session=self.app.session()
  self.gate=next(p.id for p in repo.get_all_pois() if 'Dream Center' in p.name_en)
  self.form=dict(route_mode='plan_for_me',available_minutes=240,interest_tags=['art','industrial_heritage','waterfront'],travel_pace='standard',preferred_zone='wukang_fuxing_xujiahui')
 def test_supplement_keeps_selected_fields(self):
  self.app.entry.parse_plan=Mock(return_value=RouteIntent(RouteMode.PLAN_FOR_ME,must_go_poi_ids=[self.gate],needs_clarification=True,missing_fields=['available_minutes','interest_tags']))
  r=self.app.generate(self.session,dict(text='include gate m west bund dream center in my route',intent=self.form));i=r['entry']['intent']
  self.assertEqual(i['available_minutes'],240);self.assertEqual(i['interest_tags'],self.form['interest_tags']);self.assertEqual(i['preferred_zone'],'west_bund');self.assertIn(self.gate,i['must_go_poi_ids']);self.assertNotEqual(r['entry']['status'],'needs_clarification')
 def test_explicit_duration(self):
  self.app.entry.parse_plan=Mock(return_value=RouteIntent(RouteMode.PLAN_FOR_ME,available_minutes=120,interest_tags=['art'],preferred_zone='west_bund'))
  r=self.app.generate(self.session,dict(text='Actually only two hours',intent=self.form));self.assertEqual(r['entry']['intent']['available_minutes'],120)
 def test_text_only(self):
  self.app.entry.parse_plan=Mock(return_value=RouteIntent(RouteMode.PLAN_FOR_ME))
  r=self.app.generate(self.session,dict(text='a walk'));self.assertEqual(r['entry']['status'],'needs_clarification');self.app.entry.parse_plan.assert_called_once_with('a walk')
 def test_invalid_form(self):
  self.app.entry.parse_plan=Mock()
  with self.assertRaises(ValueError):self.app.generate(self.session,dict(text='walk',intent={**self.form,'available_minutes':-1}))
  self.app.entry.parse_plan.assert_not_called()
