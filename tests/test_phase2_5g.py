from pathlib import Path
"""Evidence repair failures, frozen baselines and actual candidate regressions."""
import copy,hashlib,unittest
from scripts.run_diversity_repair import ROOT,BASE,FINAL,OUT,ZONES,REMOVED,load
from scripts.diversity_review_data import PROFILES,TAGS
from src.poi_pipeline.conservative_repair import ConservativeSemanticRepair
from src.poi_pipeline.semantic.validation import validate_semantic_enrichment
from src.poi_pipeline.diversity import facets,distribution,route_diversity,TEXTURE
from src.poi_repository import POIRepository
from src.kb_selection import resolve_poi_repository,DIVERSITY_CANDIDATE_PATH

class DiversityRepairTests(unittest.TestCase):
 def setUp(self):
  self.kb=load(FINAL);self.repo=POIRepository(FINAL)
  self.repairs=[load(p) for p in OUT.glob('*_repair.json')]
  self.square=next(r for r in self.repairs if r['candidate']['original_cached_name']=='上海人民广场')
 def build(self,c=None,tags=None):
  c=c or self.square['candidate'];o=self.square['output']
  return ConservativeSemanticRepair().build(c,self.repo.taxonomy,profile=PROFILES['上海人民广场'],tags=tags or TAGS['上海人民广场'],summary_ref=o['summary_draft']['evidence_refs'][0])
 def test_source_and_coordinates_revalidated_without_validator_bypass(self):
  self.assertEqual(len(self.repairs),15)
  for r in self.repairs:
   c=r['candidate'];s=validate_semantic_enrichment(r['output'],c,c['evidence_catalog'],self.repo.taxonomy)
   self.assertEqual(s['coordinates'],c['coordinates'])
   self.assertFalse(r['semantic']['subject_scope_validation']['removed_tags'])
   self.assertTrue(all(v is None for v in r['output']['factual_fields'].values()))
   self.assertEqual(r['api_calls'],0)
 def test_overgenerated_and_unsupported_tags_fail_instead_of_trimming(self):
  with self.assertRaises(ValueError):self.build(tags=(['modern_city','history','architecture'],[],[]))
  with self.assertRaisesRegex(ValueError,'No direct subject authority'):self.build(tags=(['religion'],[],[]))
 def test_unknown_summary_reference_fails(self):
  c=copy.deepcopy(self.square['candidate']);c['evidence_catalog'].pop(self.square['output']['summary_draft']['evidence_refs'][0])
  with self.assertRaises(KeyError):self.build(c)
 def test_frozen_nodes_and_explicit_removal_only(self):
  old=load(BASE);index={p['id']:p for p in self.kb['pois']}
  self.assertEqual({p['id'] for p in old['pois']}-set(index),{REMOVED})
  for p in old['pois']:
   if p['id']!=REMOVED:self.assertEqual(p,index[p['id']])
  self.assertEqual(len(self.repo.get_pois_by_zone('west_bund')),13)
  for path,digest in load(OUT/'cost_report.json')['protected_sha256'].items():
   self.assertEqual(hashlib.sha256((ROOT/('data/archive/pois_pre_phase2_5.json' if Path(path).name=='pois.json' else path)).read_bytes()).hexdigest(),digest,path)
 def test_square_parent_identity_not_station_or_park(self):
  r=next(r for r in load(OUT/'review.json') if r['name']=='上海人民广场')
  self.assertEqual(r['map_identity']['provider_id'],'B00157917M')
  p=self.repo.get_poi_by_id(r['poi_id'])
  self.assertEqual(list(p.coordinates),[31.228827,121.475213])
  self.assertEqual(p.route_role_primary,'anchor')
  self.assertNotIn('parks',p.interest_tags)
 def test_bounded_pool_and_explicit_defer(self):
  rows=load(OUT/'review.json')
  for z in ZONES:
   selected=load(OUT/f'{z}_shortlist.json');self.assertEqual(len(selected),6)
   self.assertLessEqual(sum('公园' in c['name_zh'] for c in selected),2)
   self.assertLessEqual(sum(r['decision']=='defer' for r in rows if r['zone']==z),5)
  self.assertEqual(sum(r['decision']=='accept' for r in rows),15)
 def test_parks_never_hide_in_explicit_texture_facets(self):
  p=copy.deepcopy(next(p for p in self.kb['pois'] if p['name']['zh']=='徐家汇公园'))
  p['urban_texture_audit']['facets']=['historic_building','public_square']
  self.assertEqual(facets(p),{'park'})
  self.assertEqual(distribution([p])['urban_texture_node_count'],0)
  self.assertEqual(distribution([p])['park_share'],1)
 def test_museum_visit_scope_has_supported_avoidance_tag(self):
  for name in ('中国社会主义青年团中央机关旧址','张乐平','李白烈士故居','沈尹默故居'):
   r=next(r for r in self.repairs if r['candidate']['original_cached_name']==name)
   self.assertIn('museum_visit',r['semantic']['experience_tags'])
   evidence=next(e for e in r['semantic']['tag_evidence'] if e['tag']=='museum_visit')
   self.assertTrue(any('博物馆名单' in str(r['candidate']['evidence_catalog'][ref]['value']) for ref in evidence['evidence_refs']))
 def test_regression_requests_unchanged_and_no_success_lost(self):
  for z in ZONES:
   g=load(OUT/f'{z}_regression_comparison.json')
   self.assertEqual([r['request'] for r in g['before']],[r['request'] for r in g['after']])
   self.assertTrue(all(r['passed'] for r in g['after'][:6]))
   for a,b in zip(g['before'],g['after']):
    if a['passed']:self.assertTrue(b['passed'])
    self.assertTrue(b['negative_preference_passed']);self.assertTrue(b['zone_isolation_passed'])
    self.assertEqual(b['diversity_diagnostics']['park_count'],sum(self.repo.get_poi_by_id(s['poi_id']).poi_type=='park' for s in b['selected_stops']))
 def test_cross_modes_have_diversity_and_hard_constraints(self):
  rows=load(OUT/'cross_zone_three_modes.json');self.assertEqual(len(rows),12)
  self.assertTrue(all(r['passed'] and r['diversity_diagnostics']['soft_diagnostic_only'] for r in rows))
 def test_explicit_candidate_selection_keeps_production_default(self):
  self.assertEqual(resolve_poi_repository('phase2_5_diversity_candidate').path,DIVERSITY_CANDIDATE_PATH)
  self.assertNotEqual(resolve_poi_repository().path,DIVERSITY_CANDIDATE_PATH)
