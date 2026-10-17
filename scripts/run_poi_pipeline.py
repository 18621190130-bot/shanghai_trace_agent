"""Unified configured Zone POI pipeline. Candidate-only; West Bund stays frozen."""
import argparse,copy,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.poi_repository import POIRepository
from src.poi_pipeline.zone_config import ZonePipelineConfig
from src.poi_pipeline.prefilter import prefilter_node,physical_stability
from src.poi_pipeline.role_audit import audit_existing,validate_role
from src.poi_pipeline.zone_semantic import ZoneSemanticEnricher
from src.poi_pipeline.semantic.admission import source_confidence
from src.poi_pipeline.zone_candidate_kb import merge_zone
from src.poi_pipeline.coverage import ZoneCoverageAnalyzer
from src.poi_pipeline.zone_regression import run_zone_regression
from src.poi_pipeline.subject_validation import validate_subject_scope
from src.llm_client import DeepSeekLLMClient
from scripts.collect_configured_zone import run as collect

OUT=ROOT/'data/poi_pipeline/all_zones'
BASE=ROOT/'data/pois_phase2_5_candidate.json'
FINAL=ROOT/'data/pois_phase2_5_all_zones_candidate.json'

def write(path,obj):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temp.replace(path)

def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def run(zone,live=False,recollect=False,input_path=None):
 config=ZonePipelineConfig.load(zone)
 if zone=='west_bund':raise ValueError('West Bund frozen; use cross-zone regression only')
 protected={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'data/pois.json',BASE)}
 base=load(input_path or BASE);repo=POIRepository(input_path or BASE)
 def export(suffix,obj):write(OUT/f'{zone}_{suffix}.json',obj)
 baseline=ZoneCoverageAnalyzer(zone,repo).analyze();export('baseline_report',baseline)
 audits=audit_existing(repo,config,load(ROOT/'data/poi_pipeline/existing_role_decisions.json'));export('existing_role_audit',audits)
 prepared=OUT/f'{zone}_prepared_nodes.json'
 if recollect or not prepared.exists():collect(zone,live)
 nodes=load(prepared); collection=load(OUT/f'{zone}_collection_report.json')
 enricher=ZoneSemanticEnricher(DeepSeekLLMClient(timeout=60,max_tokens=3300),repo.taxonomy,OUT/'semantic_cache',live)
 accepted=[];review=[];runs=[];survivors=0
 for c in nodes:
  reason=prefilter_node(c)
  priority=10 if any(s['source_type'] in ('official','government') for s in c['sources']) else 0
  row=dict(node_id=c['candidate_id'],name=c['name_zh'] or c['name_en'],decision='defer',route_selectable=False,counts_as_route_stop=False,reason=reason,identity=c['identity'],review_priority=priority,boundary_status='needs_boundary_review' if c['boundary_status']=='needs_review' else c['boundary_status'])
  if reason:
   if reason in ('outside_product_boundary','child_or_internal_entity') or c['identity']['identity_status']=='existing_production':row['decision']='reject'
   review.append(row);continue
  survivors+=1
  print(json.dumps(dict(zone=zone,enriching=row['name']),ensure_ascii=True),flush=True)
  result=enricher.enrich(c);runs.append(result);s=result['semantic']
  if s:s=validate_subject_scope(s,c)
  conf=source_confidence(c)['overall']
  if not s:row['reason']='semantic_validation_or_provider_failure'
  elif s['semantic_confidence']=='low' or s['route_role']['confidence']=='low' or not physical_stability(c,s)['accepted'] or s['citywalk_value']['level']=='low':row['reason']='insufficient_confident_independent_value'
  elif s['category'] not in config.allowed_candidate_categories or not(s['interest_tags'] or s['experience_tags']):row['reason']='no_admissible_evidenced_semantics'
  elif conf=='low':row['reason']='low_source_confidence'
  else:
   validate_role(s['route_role']);row.update(decision='recommended_accept',route_selectable=True,counts_as_route_stop=True,reason='all_admission_gates_passed',primary_role=s['route_role']['primary'],eligible_roles=s['route_role']['eligible'],role_confidence=s['route_role']['confidence'])
   accepted.append(dict(candidate=c,semantic=s,source_confidence=conf,stability_audit=physical_stability(c,s)))
  review.append(row)
  export('semantic_run',runs)
 kb=merge_zone(base,config,audits,accepted)
 # Composition is first tested on a disposable candidate. Only accepted regression
 # explicitly enables it in the cumulative candidate.
 probe=copy.deepcopy(kb)
 probe['route_engine_defaults']['route_composition_enabled_zones']=list(dict.fromkeys(probe['route_engine_defaults'].get('route_composition_enabled_zones',[])+[zone]))
 probe_path=OUT/f'{zone}_regression_candidate.json';write(probe_path,probe)
 tested=POIRepository(probe_path)
 regression=run_zone_regression(tested,zone,[r['poi_id'] for r in accepted]);export('regression_report',regression)
 if regression['acceptable']:
  kb=probe;kb['metadata']['candidate_kb_status']='zone_regression_passed_pending_full_validation'
 output=OUT/f'{zone}_candidate.json';write(output,kb)
 export('route_nodes',dict(existing=audits,accepted=[dict(poi_id=r['poi_id'],name=r['candidate']['name_zh'],primary_role=r['semantic']['route_role']['primary'],eligible_roles=r['semantic']['route_role']['eligible'],role_confidence=r['semantic']['route_role']['confidence'],tags={g:r['semantic'][g] for g in repo.taxonomy},source_provenance=r['candidate']['sources']) for r in accepted]))
 worthy=sorted([r for r in review if r['decision']=='defer' and r['review_priority'] and r['reason'] in ('needs_boundary_review','insufficient_confident_independent_value')],key=lambda r:(-r['review_priority'],r['node_id']))
 export('review',dict(human_review=worthy[:5],all_dispositions=review,remaining_deferred=max(0,len(worthy)-5),low_confidence_existing=[a for a in audits if a['role_confidence']=='low']))
 after=ZoneCoverageAnalyzer(zone,POIRepository(output)).analyze();export('coverage_report',dict(before=baseline,after=after))
 history=[load(p) for p in (OUT/'semantic_cache').glob('*.json')]
 history=[r for r in history if r.get('candidate_id','').startswith(zone+'_')]
 from collections import Counter
 attempts_by_node=Counter()
 for r in history:attempts_by_node[r.get('node_identity',r['candidate_id'])]+=len(r['attempts'])
 if any(n>2 for n in attempts_by_node.values()):raise RuntimeError('Per-node semantic attempt budget exceeded')
 historical_calls=sum(attempts_by_node.values())
 cost=dict(raw_candidates=collection['raw_count'],prefilter_survivors=survivors,llm_enriched_count=sum(r['semantic'] is not None for r in runs),deepseek_calls_this_run=sum(r['api_calls_this_run'] for r in runs),deepseek_calls_total=historical_calls,
  retry_count=sum(max(0,n-1) for n in attempts_by_node.values()),cache_hits=sum(r['cache_hit'] for r in runs),semantic_validation_failures=sum(a['status']=='validation_failure' for r in history for a in r['attempts']),accepted=len(accepted),deferred=sum(r['decision']=='defer' for r in review),rejected=sum(r['decision']=='reject' for r in review)+len(collection['deterministic_rejected']),existing_role_audited=len(audits),existing_role_audit_deepseek_calls=0,attempts_by_node=dict(attempts_by_node),
  counting_note='Raw provider objects; disposition counts are normalized route candidates plus raw early rejects, not an additive raw partition.')
 export('cost_report',cost)
 if any(hashlib.sha256(p.read_bytes()).hexdigest()!=h for p,h in protected.items()):raise RuntimeError('Protected KB changed')
 export('stage_report',dict(zone=zone,regression_acceptable=regression['acceptable'],protected_unchanged=True,candidate=str(output.relative_to(ROOT)),cost=cost))
 print(json.dumps(dict(zone=zone,regression=regression['passed_count'],accepted=len(accepted),candidate=str(output)),ensure_ascii=True),flush=True)
 return output,regression

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--zone',required=True);p.add_argument('--live',action='store_true');p.add_argument('--recollect',action='store_true');p.add_argument('--input',type=Path)
 a=p.parse_args()
 if a.zone=='all':
  base=a.input or BASE
  for z in POIRepository(BASE).zone_order:
   if z=='west_bund':continue
   base,reg=run(z,a.live,a.recollect,base)
   if not reg['acceptable']:raise RuntimeError('Unacceptable zone regression: '+z)
  from scripts.finalize_all_zones import finalize
  finalize(False)
 else:run(a.zone,a.live,a.recollect,a.input)
if __name__=='__main__':main()
