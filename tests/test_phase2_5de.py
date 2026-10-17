"""Offline invariant and adversarial checks for the generalized data pipeline."""
import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from src.poi_repository import POIRepository
from src.poi_pipeline.zone_config import ZonePipelineConfig
from src.poi_pipeline.geometry import validate_polygon
from src.poi_pipeline.boundary import boundary_status,POLYGON
from src.poi_pipeline.role_audit import audit_existing,validate_role
from src.poi_pipeline.prefilter import physical_stability,prefilter_node
from src.poi_pipeline.sources.official_source import extract_page
from src.poi_pipeline.zone_collection import consolidate_zone
from src.poi_pipeline.zone_semantic import ZoneSemanticEnricher
from src.poi_pipeline.zone_candidate_kb import stable_poi_id
from src.poi_pipeline.subject_validation import validate_subject_scope
from src.kb_selection import resolve_poi_repository
from scripts.run_poi_pipeline import ROOT,OUT,BASE,FINAL,load

class Phase25DETests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.repo=POIRepository(FINAL);cls.base=load(BASE);cls.final=load(FINAL)

 def test_protected_production_hash(self):
  self.assertEqual(hashlib.sha256((ROOT/'data/archive/pois_pre_phase2_5.json').read_bytes()).hexdigest(),'6585b3baf653ae89cc6a1e3c5fc10140bdd801fb298d92c392381d0b5fc17513')

 def test_pilot_file_and_all_pilot_nodes_unchanged(self):
  self.assertEqual(hashlib.sha256(BASE.read_bytes()).hexdigest(),'dc30a2933786b2c339a1b1f10ddfbf5f0025b502894f1e376232287799c00d2c')
  self.assertEqual([p for p in self.base['pois'] if p['walk_zone']['id']=='west_bund'],[p for p in self.final['pois'] if p['walk_zone']['id']=='west_bund'])
  self.assertEqual(ZonePipelineConfig.load('west_bund').polygon,POLYGON)

 def test_all_seed_boundaries(self):
  prod=POIRepository(ROOT/'data/archive/pois_pre_phase2_5.json')
  for z in prod.zone_order:
   config=ZonePipelineConfig.load(z)
   result=validate_polygon(config.polygon,config.settings['seed_pois'])
   self.assertTrue(result['all_production_seeds_covered']);self.assertTrue(result['polygon_valid'])
   self.assertEqual(config.boundary_review_margin_m,150)

 def test_crossed_or_degenerate_polygon_refused(self):
  for p in [[(31.2,121.4),(31.22,121.42),(31.2,121.42),(31.22,121.4)],[(31.2,121.4)]*3]:
   with self.assertRaises(ValueError):validate_polygon(p,[])

 def test_margin_is_review_not_outside(self):
  polygon=((31.2,121.4),(31.2,121.42),(31.22,121.42),(31.22,121.4))
  self.assertEqual(boundary_status((31.1995,121.41),polygon,150),'needs_review')
  self.assertEqual(boundary_status((31.197,121.41),polygon,150),'outside_pilot')

 def test_twenty_two_explicit_existing_audits(self):
  rows=[a for z in self.repo.zone_order if z!='west_bund' for a in load(OUT/f'{z}_existing_role_audit.json')]
  self.assertEqual(len(rows),22);self.assertEqual(len({a['poi_id'] for a in rows}),22)
  self.assertTrue(any(a['primary_role']=='transition_stop' for a in rows))
  self.assertTrue(any(a['primary_role']=='supporting_stop' for a in rows))
  for a in rows:
   self.assertTrue(a['role_reason']);self.assertTrue(a['available_evidence']);self.assertIn(a['primary_role'],a['eligible_roles'])

 def test_missing_audit_cannot_default_to_anchor(self):
  with self.assertRaises(ValueError):audit_existing(POIRepository(BASE),ZonePipelineConfig.load('wukang_fuxing_xujiahui'),{})

 def test_supporting_cannot_be_eligible_anchor_without_high_independence(self):
  with self.assertRaises(ValueError):validate_role(dict(primary='supporting_stop',eligible=['supporting_stop','anchor'],confidence='medium',reason='test',independent_destination_value='medium'))

 def test_low_role_is_not_selectable(self):
  config=ZonePipelineConfig.load('wukang_fuxing_xujiahui');decisions=load(ROOT/'data/poi_pipeline/existing_role_decisions.json')
  decisions[config.seed_production_pois[0]]['role_confidence']='low'
  row=audit_existing(POIRepository(BASE),config,decisions)[0]
  self.assertEqual(row['decision'],'defer');self.assertFalse(row['route_selectable'])

 def test_substantive_official_excerpt_not_repeated_heading(self):
  html='<h1>测试公园</h1><h2>测试公园</h2><p>测试公园</p><p>测试公园'+('为市民提供公共休闲步道和公园绿地。'*7)+'</p>'
  result=extract_page(html,['测试公园'],substantive=True)
  self.assertIn('休闲步道',result['excerpts']['测试公园'][0])

 def test_current_hours_unknown_does_not_make_public_park_temporary(self):
  c=dict(name_zh='测试公园',entity_kind='public_space',merged_source_records=[dict(source_type='amap',source_category='公园',raw_provider_tags={}),dict(source_type='government',source_category='mention',raw_provider_tags={},snippets=[dict(text='社区公园')])])
  self.assertTrue(physical_stability(c,dict(category='park',stability='unknown'))['accepted'])
  self.assertFalse(physical_stability(c,dict(category='park',stability='temporary'))['accepted'])
  c['name_zh']='测试公园(暂停营业)'
  self.assertTrue(physical_stability(c,dict(category='park',stability='unknown'))['accepted'])
  c['name_zh']='测试公园(已拆除)'
  self.assertFalse(physical_stability(c,dict(category='park',stability='stable'))['accepted'])

 def test_child_filtered_before_missing_evidence(self):
  self.assertEqual(prefilter_node(dict(internal_parent='p5')),'child_or_internal_entity')

 def test_same_street_provider_objects_consolidated(self):
  registry=load(OUT/'hongkou_literary_internal_entities.json')
  self.assertTrue(any(r['relationship']=='same_named_route_experience' for r in registry if 'relationship' in r))
  for r in registry:self.assertFalse(r['route_selectable']);self.assertFalse(r['counts_as_route_stop'])

 def test_route_overview_cannot_support_subject_tag(self):
  c=dict(evidence_catalog={'e':dict(value='本条路线途经各个更新街区')})
  s=dict(interest_tags=[],experience_tags=[],culture_tags=['urban_renewal'],tag_evidence=[dict(group='culture_tags',tag='urban_renewal',evidence_refs=['e'])])
  self.assertEqual(validate_subject_scope(s,c)['culture_tags'],[])

 def test_street_does_not_inherit_adjacent_park_or_shopping_tags(self):
  c=dict(name_zh='一条街道',merged_source_records=[dict(source_type='amap',source_category='道路名')],evidence_catalog={'e':dict(value='街道南端接商业街，北端可见公园绿意')})
  s=dict(interest_tags=['parks','shopping_lifestyle'],experience_tags=[],culture_tags=[],tag_evidence=[dict(group='interest_tags',tag=t,evidence_refs=['e']) for t in ('parks','shopping_lifestyle')])
  self.assertEqual(validate_subject_scope(s,c)['interest_tags'],[])

 def test_attempt_budget_survives_changed_evidence_and_offline_resume(self):
  c=load(OUT/'wukang_fuxing_xujiahui_prepared_nodes.json')[0]
  with tempfile.TemporaryDirectory() as folder:
   identity=next((r['source_type']+':'+r['source_candidate_id'] for r in c['merged_source_records'] if r['source_type']=='amap'),c['candidate_id'])
   Path(folder,'prior.json').write_text(json.dumps(dict(candidate_id=c['candidate_id'],node_identity=identity,attempts=[{},{}],evidence_hash='old',output=None)),encoding='utf-8')
   client=Mock();r=ZoneSemanticEnricher(client,self.repo.taxonomy,folder,False).enrich(c)
   self.assertEqual(r['api_calls_this_run'],0);client.structured_parse.assert_not_called()

 def test_actual_attempts_never_exceed_two(self):
  from collections import Counter
  counts=Counter()
  for f in (OUT/'semantic_cache').glob('*.json'):
   r=load(f);counts[r.get('node_identity',r['candidate_id'])]+=len(r['attempts'])
  self.assertTrue(counts);self.assertLessEqual(max(counts.values()),2)

 def test_stable_ids_and_metadata(self):
  self.assertEqual(stable_poi_id('zone','amap:1'),stable_poi_id('zone','amap:1'))
  ids=[p['id'] for p in self.final['pois']];self.assertEqual(len(ids),len(set(ids)))
  self.assertTrue({p['id'] for p in self.base['pois']}<=set(ids))
  self.assertEqual(self.final['metadata']['poi_count'],len(ids))
  identities=[p['source_provenance']['stable_identity'] for p in self.final['pois'] if p['id'].startswith('pz_')]
  self.assertEqual(len(identities),len(set(identities)))

 def test_explicit_composition_and_cross_modes(self):
  self.assertEqual(set(self.final['route_engine_defaults']['route_composition_enabled_zones']),set(self.repo.zone_order))
  cases=load(OUT/'cross_zone_three_mode_regression.json')
  self.assertEqual(len(cases),12);self.assertTrue(all(c['passed'] for c in cases))

 def test_zone_regression_and_review_bound(self):
  for z in self.repo.zone_order:
   if z=='west_bund':continue
   r=load(OUT/f'{z}_regression_report.json');self.assertGreaterEqual(len(r['cases']),6);self.assertTrue(r['acceptable'])
   self.assertLessEqual(len(load(OUT/f'{z}_review.json')['human_review']),5)

 def test_candidate_requires_explicit_kb_selection(self):
  self.assertEqual(resolve_poi_repository('phase2_5_all_zones_candidate').path,FINAL)
  self.assertEqual(resolve_poi_repository().path,ROOT/'data/pois.json')
