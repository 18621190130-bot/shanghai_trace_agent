"""Recall budgets, frozen baselines and access/existence separation."""
import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from src.poi_pipeline.recall import RecallBudget,recall_prefilter,enrich_once
from src.poi_pipeline.prefilter import physical_stability,prefilter_raw
from src.poi_pipeline.models import RawCandidate
from src.poi_pipeline.zone_config import ZonePipelineConfig
from src.kb_selection import resolve_poi_repository,RECALL_CANDIDATE_PATH
from scripts.run_recall_repair import ROOT,BASE,FINAL,OUT,ZONES,load

class RecallRepairTests(unittest.TestCase):
 def candidate(self,name='社区公园(暂停开放)'):
  return dict(candidate_id='test',name_zh=name,name_en='',walk_zone='old_city_central',entity_kind='public_space',
   identity={'identity_status':'new_candidate'},coordinates=[31.22,121.47],boundary_status='inside_pilot',
   merged_source_records=[dict(source_type='amap',source_candidate_id='A',source_category='公园;体育休闲服务',raw_provider_tags={}),
    dict(source_type='government',source_candidate_id='G',source_category='公园',raw_provider_tags={},snippets=[{'text':'社区公园'}])])
 def test_closed_label_is_not_disappearance(self):
  for suffix in ('暂停开放','Closed','非营业时间','暂时关闭','暂停营业'):
   c=self.candidate('社区公园('+suffix+')')
   self.assertIsNone(recall_prefilter(c))
   self.assertTrue(physical_stability(c,dict(category='park',stability='unknown'))['accepted'])
 def test_permanent_disappearance_overrides_even_model_stable(self):
  for suffix in ('永久关闭','已拆除','已撤除'):
   c=self.candidate('社区公园('+suffix+')')
   self.assertEqual(recall_prefilter(c),'unstable_place')
   self.assertFalse(physical_stability(c,dict(category='park',stability='stable'))['accepted'])
 def test_historical_provisional_government_is_not_temporary_event(self):
  cfg=ZonePipelineConfig.load('old_city_central')
  self.assertIsNone(prefilter_raw(RawCandidate('a','amap','test','https://example.com','2026-10-05',name_zh='大韩民国临时政府旧址'),cfg))
  self.assertEqual(prefilter_raw(RawCandidate('b','amap','test','https://example.com','2026-10-05',name_zh='临时快闪装置'),cfg),'ancillary_or_temporary')
 def test_budget_limits_and_retry_reasons_persist(self):
  with tempfile.TemporaryDirectory() as t:
   b=RecallBudget(Path(t)/'ledger.json')
   for i in range(8):b.reserve('z',str(i))
   with self.assertRaises(ValueError):b.reserve('z','ninth')
   with self.assertRaises(ValueError):b.reserve('z','0',True,'unsupported_tag_only')
   for i in range(6):b.reserve('z',str(i),True,'material_new_evidence')
   with self.assertRaises(ValueError):b.reserve('z','6',True,'material_new_evidence')
   with self.assertRaises(ValueError):b.reserve('z','0',True,'material_new_evidence')
   self.assertEqual(len(RecallBudget(b.path).rows),14)
  with tempfile.TemporaryDirectory() as t:
   b=RecallBudget(Path(t)/'ledger.json')
   for z in ('a','b','c'):
    for i in range(8):b.reserve(z,str(i))
   for i in range(6):b.reserve('a',str(i),True,'schema_syntax_repair')
   self.assertEqual(len(b.rows),30)
   with self.assertRaises(ValueError):b.reserve('other','over-total')
 def test_new_provider_identity_reuses_successful_cache(self):
  with tempfile.TemporaryDirectory() as t:
   c=self.candidate();c['evidence_catalog']={}
   directory=Path(t)/'cache';directory.mkdir()
   path=directory/'original.json';path.write_text(json.dumps(dict(candidate_id='test',node_identity='original',output={'cached':True},semantic={'route_role':{}})),encoding='utf8')
   client=Mock();b=RecallBudget(Path(t)/'ledger.json')
   with patch('src.poi_pipeline.recall.validate_semantic_enrichment',return_value={'route_role':{}}),patch('src.poi_pipeline.recall.validate_role'):
    result=enrich_once(c,{},client,b,directory,True)
   client.structured_parse.assert_not_called();self.assertTrue(result['cache_hit']);self.assertEqual(b.rows,[])
 def test_protected_old_kb_exact_hash_and_frozen_nodes(self):
  self.assertEqual(hashlib.sha256(BASE.read_bytes()).hexdigest(),'7d773867802236dcffdc0e307bd7fbda1e312f45d7cdf307c055957bc1e0e14c')
  old=load(BASE);new=load(FINAL);index={p['id']:p for p in new['pois']}
  for p in old['pois']:
   if p['id'] not in ('p7','p9','p13'):self.assertEqual(p,index[p['id']])
   else:
    self.assertEqual(p['route_role'],index[p['id']]['route_role'])
    self.assertEqual(p['route_role_audit'],index[p['id']]['route_role_audit'])
 def test_cached_pool_bounded_source_checks_and_shortlists(self):
  for z in ZONES:
   shortlist=load(OUT/f'{z}_prepared_shortlist.json');self.assertLessEqual(len(shortlist),12)
   for c in shortlist:self.assertNotIn(recall_prefilter(c),('internal_entity','production_duplicate','outside_boundary'))
   for row in load(OUT/f'{z}_evidence_checks.json'):self.assertLessEqual(len(row['checks']),2)
 def test_same_six_requests_before_after_and_hard_constraints(self):
  for z in ZONES:
   g=load(OUT/f'{z}_regression_comparison.json')
   self.assertEqual([r['request'] for r in g['before']],[r['request'] for r in g['after']])
   self.assertEqual(len(g['after']),6)
   for r in g['after']:
    ids=[s['poi_id'] for s in r['selected_stops']]
    self.assertEqual(len(ids),len(set(ids)));self.assertTrue(r['negative_preference_passed']);self.assertTrue(r['zone_isolation_passed'])
    self.assertLessEqual(r['total_estimated_time'],r['request']['available_minutes'])
 def test_production_stays_explicit_default(self):
  self.assertEqual(resolve_poi_repository('phase2_5_recall_candidate').path,RECALL_CANDIDATE_PATH)
  self.assertNotEqual(resolve_poi_repository().path,RECALL_CANDIDATE_PATH)
