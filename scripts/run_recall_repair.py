"""Phase 2.5F: cached shortlist audit, bounded evidence and candidate-only repair."""
import argparse,copy,hashlib,json,re
from collections import Counter
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
from scripts.run_poi_pipeline import ROOT,load,write
from scripts.recall_review_data import SHORTLIST,SOURCES,DEFER_NOTES
from src.poi_repository import POIRepository
from src.poi_pipeline.models import RawCandidate,CanonicalCandidate
from src.poi_pipeline.normalization import normalize_candidate,match_key
from src.poi_pipeline.deduplication import deduplicate_candidates
from src.poi_pipeline.zone_collection import consolidate_zone
from src.poi_pipeline.zone_config import ZonePipelineConfig
from src.poi_pipeline.prefilter import prefilter_node,physical_stability
from src.poi_pipeline.recall import recall_prefilter,RecallBudget,enrich_once,REASONS,identity
from src.poi_pipeline.evidence import build_evidence_bundle
from src.poi_pipeline.semantic.preparation import evidence_catalog,unique
from src.poi_pipeline.semantic.admission import source_confidence
from src.poi_pipeline.subject_validation import validate_subject_scope
from src.poi_pipeline.zone_candidate_kb import merge_zone
from src.poi_pipeline.coverage import ZoneCoverageAnalyzer
from src.poi_pipeline.zone_regression import run_zone_regression,regression_cases
from src.west_bund_regression import describe
from src.route_engine import RouteEngine
from src.models import RouteRequest
from src.geo_utils import haversine_km
from src.llm_client import DeepSeekLLMClient

OLD=ROOT/'data/poi_pipeline/all_zones';OUT=ROOT/'data/poi_pipeline/recall'
BASE=ROOT/'data/pois_phase2_5_all_zones_candidate.json';FINAL=ROOT/'data/pois_phase2_5_recall_candidate.json'
ZONES=('old_city_central','wukang_fuxing_xujiahui','hongkou_literary')

def catalog(c):
 fields={k:copy.deepcopy(c[k]) for k in CanonicalCandidate.__dataclass_fields__ if k in c}
 fields['merged_source_records']=[RawCandidate(**r) for r in fields['merged_source_records']]
 c['evidence_catalog']=evidence_catalog(asdict(build_evidence_bundle(CanonicalCandidate(**fields))))

def coarse_reason(reason,c=None):
 if reason in REASONS:return reason
 if reason=='outside_product_boundary':return 'outside_boundary'
 if reason=='child_or_internal_entity':return 'child_entity'
 if reason=='location_unresolved':return 'weak_location'
 if reason=='identity_not_resolved_new_node':
  return 'production_duplicate' if c and c['identity']['identity_status']=='existing_production' else 'possible_duplicate'
 if reason=='ancillary_or_temporary':return 'temporary_event' if c and re.search('快闪|花卉节|临时(?!政府.*旧址)',c.get('name_zh','')) else 'generic_service'
 if reason in ('generic_service_or_shop','generic_shop'):
  return 'generic_food_drink' if c and re.search('餐饮|cafe|restaurant|fast_food',str(c)) else 'generic_retail' if c and re.search('购物|shop',str(c)) else 'generic_service'
 if reason=='entity_no_longer_exists':return 'unstable_place'
 return 'other'

def prepare(zone,repo):
 config=ZonePipelineConfig.load(zone);raw=load(OLD/f'{zone}_raw_candidates.json')
 original=load(OLD/f'{zone}_prepared_nodes.json');collection=load(OLD/f'{zone}_collection_report.json');review=load(OLD/f'{zone}_review.json')
 normalized=[normalize_candidate(RawCandidate(**r),config) for r in raw]
 unique_normalized={(r.raw.source_type,r.raw.source_candidate_id) for r in normalized}
 # Reuse canonical EvidenceBundles; only recover the one proven lexical false
 # negative from raw. No broad normalization/collection rebuild is needed.
 nodes=copy.deepcopy(original)
 korean=[RawCandidate(**r) for r in raw if r['name_zh']=='大韩民国临时政府旧址']
 if korean:
  recovered=[asdict(c) for c in deduplicate_candidates([normalize_candidate(r,config) for r in korean],zone)]
  keys={r.source_type+':'+r.source_candidate_id for r in korean}
  # Remove the equivalent cached English OSM rendering, preserving its aliases.
  matches=[c for c in nodes if any(r['source_type']+':'+r['source_candidate_id'] in keys for r in c['merged_source_records'])]
  for c in matches:
   recovered[0]['aliases']=unique(recovered[0]['aliases']+[c['name_zh'],c['name_en']])
   nodes.remove(c)
  nodes+=recovered
 nodes,registry=consolidate_zone(nodes,repo,config)
 # Named child experiences confirmed by cached park identity and inspected
 # authority descriptions. Geometry alone never asserts containment.
 for c in nodes:
  name=c['name_zh'] or c['name_en']
  if zone=='wukang_fuxing_xujiahui' and name in ('徐家汇公园-希望之泉','六角亭','百年香樟','汇金湖','汇学长廊'):c['recall_parent']='徐家汇公园'
  if zone=='hongkou_literary' and (name in ('世界文豪广场','尹奉吉纪念园(梅园)','梅园','鲁迅墓','鲁迅雕像') or re.search('雕像|钟亭|纪念之林|纪念墙',name)):
   # Named figures on Dolun street are already included public observation;
   # memorial wall/grove are inside Sichuan North Road Park.
   c['recall_parent']='existing park/street public observation scope'
  if zone=='old_city_central' and name in ('春广场','马恩雕像'):c['recall_parent']='复兴公园'
 raw_index={r['source_type']+':'+r['source_candidate_id']:r for r in raw}
 histogram=Counter(coarse_reason(r['reason'],raw_index.get(r.get('record_id'))) for r in collection['deterministic_rejected'])
 original_index={c['candidate_id']:c for c in original}
 for row in review['all_dispositions']:
  if row['reason']=='all_admission_gates_passed':continue
  histogram[coarse_reason(row['reason'],original_index.get(row.get('candidate_id',row.get('node_id',row.get('id')))))]+=1
 for reason in REASONS:histogram.setdefault(reason,0)
 cost=load(OLD/f'{zone}_cost_report.json')
 funnel=dict(raw_provider_records=len(raw),normalized_unique_records=len(unique_normalized),
  boundary_survivors_unique=len({(r.raw.source_type,r.raw.source_candidate_id) for r in normalized if r.boundary_status in ('inside_pilot','needs_review')}),
  deduplicated_canonical_candidates=len(original),production_duplicates=sum(c['identity']['identity_status']=='existing_production' for c in original),
  internal_child_candidates=sum(bool(c.get('internal_parent')) for c in original),early_reject_count=len(collection['deterministic_rejected']),
  deferred_count=cost['deferred'],prefilter_survivors=cost['prefilter_survivors'],enriched_count=cost['llm_enriched_count'],accepted=cost['accepted'],
  rejection_defer_reason_histogram=dict(histogram),original_disposition_histogram=dict(Counter(r['reason'] for r in review['all_dispositions'])),
  count_basis='Raw provider rows vs source_type:source_id unique normalized rows vs consolidated route candidates. Non-additive stages; missing geometry authority mentions excluded from boundary counts. Histogram includes raw early rejects and original canonical prefilter dispositions; semantic failure counts separate.',
  duplicate_provider_rows=len(raw)-len(unique_normalized),confirmed_duplicate_route_objects=len([r for r in registry if r.get('relationship')=='same_named_route_experience']))
 screened=[];short=[]
 for c in nodes:
  reason=recall_prefilter(c)
  name=c['name_zh'] or c['name_en']
  screened.append(dict(candidate_id=c['candidate_id'],name=name,reason=reason,original_prefilter_reason=prefilter_node(c),identity=c['identity'],boundary_status=c['boundary_status'],parent=c.get('recall_parent') or c.get('internal_parent')))
  if reason in ('internal_entity','production_duplicate','outside_boundary','generic_service','generic_retail','generic_food_drink'):continue
  if name not in SHORTLIST[zone]:continue
  rank=SHORTLIST[zone].index(name)
  note=DEFER_NOTES.get(name)
  c['recall_screen']=dict(rank=rank+1,reason=reason,review_note=note,
   evidence_score=(4 if SOURCES.get(name) else 0)+(3 if any(r['source_type'] in ('amap','osm') for r in c['merged_source_records']) else 0)+(2 if c.get('coordinates') and c['boundary_status']=='inside_pilot' else 0)+(2 if not note else 0),
   priority_basis='Explicit cached-pool comparison: independent public walk/connector scope, differentiated location, stable mapped identity, source confidence. Coverage prioritizes only; never supplies tags.')
  short.append(c)
 short.sort(key=lambda c:(-c['recall_screen']['evidence_score'],c['recall_screen']['rank']))
 assert len(short)<=12
 write(OUT/f'{zone}_funnel_before.json',funnel);write(OUT/f'{zone}_pool_screen.json',screened);write(OUT/f'{zone}_shortlist.json',short)
 return config,short,funnel

def add_sources(c):
 name=c['name_zh'] or c['name_en'];checks=[]
 prior_path=OUT/f'{c["walk_zone"]}_evidence_checks.json'
 prior_checks=[check for row in load(prior_path) if row['name']==name for check in row['checks']] if prior_path.exists() else []
 for url,text,typ in SOURCES.get(name,[]):
  rid='recall_'+hashlib.sha256((name+url).encode()).hexdigest()[:12]
  retrieved=next((s['retrieved_at'] for s in prior_checks if s['url']==url),datetime.now(timezone.utc).isoformat())
  r=RawCandidate(rid,typ,'Phase 2.5F targeted inspected source',url,retrieved,name_zh=c['name_zh'],name_en=c['name_en'],
   source_category='subject_specific_excerpt',snippets=[dict(text=text,supports=['history','public_space','access'])],coordinate_system='GCJ-02')
  # Actual quoted words, not inferred accessibility, enter EvidenceBundle.
  c['merged_source_records'].append(asdict(r));c['sources'].append(dict(source_type=typ,source_candidate_id=rid,url=url,retrieved_at=r.retrieved_at))
  checks.append(dict(url=url,excerpt=text,source_type=typ,method='inspected web result/page; source-specific small excerpt',retrieved_at=r.retrieved_at))
 extra_path=OUT/'targeted_map_identity_checks.json'
 extras=[r for r in load(extra_path) if r['zone']==c['walk_zone'] and r['name']==name] if extra_path.exists() else []
 for extra in extras:
  matches=[p for p in extra.get('results',[]) if (p['name']==name or p['name'].startswith(name+'(') or p['name']==name+'小区')]
  if len(matches)!=1:continue
  p=matches[0];lng,lat=map(float,p['location'].split(','))
  if haversine_km(c['coordinates'],[lat,lng])>.3:continue
  from src.poi_pipeline.sources.amap_source import AmapSource
  r=AmapSource.parse(p,extra['retrieved_at']);c['merged_source_records'].append(asdict(r))
  c['sources'].append(dict(source_type='amap',source_candidate_id=r.source_candidate_id,url=r.source_url,retrieved_at=r.retrieved_at))
  checks.append(dict(url=r.source_url,provider_identity=p,source_type='amap',method='one bounded targeted map identity query; extras ignored',retrieved_at=r.retrieved_at))
  c['entity_stability']='stable'
  c['current_access_status']='unknown'
  if re.search('暂停|当前未开放|非营业时间|关闭|停业',p['name']):
   c['current_access_status']='closed_now' if re.search('非营业时间|当前未开放',p['name']) else 'unknown'
   c['current_access_note']='Map closed label alone cannot distinguish normal hours from temporary closure; it does not negate entity existence.'
  if re.search('永久关闭|永久停业|已拆除|已撤除',p['name']):c['entity_no_longer_exists']=True
 if name=='武康路历史文化名街':c['entity_kind']='street';c['entity_kind_basis']='mapped historic street identity plus authority walk-street description'
 if name in ('襄阳公园','徐家汇公园','李白烈士故居','沈尹默故居','中国社会主义青年团中央机关旧址'):
  c['recall_material_repair']='Added subject-specific public access/visitor-space evidence beyond first attempt; no retry solely for unsupported tags.'
 assert len(checks)<=2
 catalog(c);return checks

def coordinate_patches(kb):
 rows=[];by_id={p['id']:p for p in kb['pois']}
 authority={
  'p7':('https://www.shanghai.gov.cn/nw31406/20250707/93b77d0a95794a39a75b7e8ef69ccfed.html','太仓路、兴业路、马当路、黄陂南路街区，与高德太仓路181弄北里身份一致。'),
  'p9':('https://arabic.shanghai.gov.cn/cmsres/fb/fb4c67ebf9604322a8b3f6f74d7e1760/eec310a1555eb5a02a121cee2922800d.pdf','茂名北路188弄；高德258号为同一张园街区另一地址，非门牌一一相等；采用 provider 街区代表点。'),
  'p13':('https://japanese.shanghai.gov.cn/ja-CityWalk/20240325/ab41c95b41a54cef96d54c2ab843abd9.html','官方与高德均指淮海中路1850号武康大楼。')}
 for check in load(OUT/'coordinate_provider_checks.json'):
  pid=check['poi_id'];p=by_id[pid];old=POIRepository(BASE).get_poi_by_id(pid).coordinates
  if not check.get('results'):rows.append(dict(poi_id=pid,status='coordinate_patch_deferred',reason='provider detail failed'));continue
  provider=check['results'][0];lng,lat=map(float,provider['location'].split(','));new=[lat,lng]
  from src.poi_pipeline.boundary import boundary_status
  config=ZonePipelineConfig.load(p['walk_zone']['id']);status=boundary_status(new,config.polygon,150)
  assert status in ('inside_pilot','needs_review')
  row=dict(poi_id=pid,name=p['name']['zh'],status='coordinate_patch_proposed',candidate_approval='approved_for_recall_candidate_by_authorized_identity_verification',
   old_coordinate=list(old),new_coordinate=new,coordinate_system='GCJ-02',distance_m=round(haversine_km(old,new)*1000,1),provider=provider,
   sources=['https://www.amap.com/detail/'+provider['id'],authority[pid][0]],reason=authority[pid][1],confidence='high',retrieved_at=check['retrieved_at'],boundary_status=status)
  loc=p['location'];keys=('representative_lat','representative_lng') if 'representative_lat' in loc else ('lat','lng')
  loc.update(dict(zip(keys,new)));loc['coordinate_note']='Phase 2.5F provider-identity-verified representative coordinate; not routed entrance.'
  p['coordinate_patch_proposed']=row;rows.append(row)
 write(OUT/'coordinate_patches.json',rows);return rows

def run(live=False):
 OUT.mkdir(exist_ok=True);protected={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'data/pois.json',ROOT/'data/pois_phase2_5_candidate.json',BASE,ROOT/'data/poi_pipeline/zone_configs.json')}
 kb=load(BASE);repo=POIRepository(BASE);budget=RecallBudget(OUT/'semantic_call_ledger.json');client=DeepSeekLLMClient(timeout=60,max_tokens=3000)
 allrows={};funnels={};accepted_ids={}
 for zone in ZONES:
  config,short,funnel=prepare(zone,repo);accepted=[];reviews=[];checks=[];enriched=0
  for c in short:
   name=c['name_zh'] or c['name_en'];note=DEFER_NOTES.get(name)
   sources=add_sources(c);checks.append(dict(candidate_id=c['candidate_id'],name=name,checks=sources))
   row=dict(candidate_id=c['candidate_id'],name=name,decision='defer',reason=recall_prefilter(c),missing_evidence=None,route_selectable=False)
   if note:row.update(reason=note[0],explanation=note[1],missing_evidence=note[2]);reviews.append(row);continue
   if row['reason']:reviews.append(row);continue
   if not any(s['source_type'] in ('official','government') for s in sources):row.update(reason='targeted_evidence_still_insufficient',missing_evidence='independent subject/access evidence');reviews.append(row);continue
   if enriched>=8:row.update(reason='zone_enrichment_budget_defer');reviews.append(row);continue
   print(json.dumps(dict(zone=zone,enriching=name),ensure_ascii=True),flush=True)
   result=enrich_once(c,repo.taxonomy,client,budget,OUT/'semantic_cache',live);enriched+=1
   write(OUT/f'{zone}_{c["candidate_id"]}_semantic.json',result)
   s=result.get('semantic')
   if s:s=validate_subject_scope(s,c)
   conf=source_confidence(c)['overall']
   if not s:row.update(reason='strict_semantic_validation_or_provider_failure',missing_evidence=result.get('reason'))
   elif s['semantic_confidence']=='low' or s['route_role']['confidence']=='low' or s['citywalk_value']['level']=='low' or not physical_stability(c,s)['accepted']:row.update(reason='independent_value_or_confidence_unresolved',missing_evidence='confident stable independent visit scope')
   elif s['category'] not in config.allowed_candidate_categories or not(s['interest_tags'] or s['experience_tags']):row.update(reason='category_or_evidenced_tags_not_admissible',missing_evidence='permitted category and minimal direct tags')
   elif conf=='low':row.update(reason='low_source_confidence')
   else:
    row.update(decision='accept',reason='unchanged_validator_and_admission_passed',route_selectable=True,role=s['route_role'])
    accepted.append(dict(candidate=c,semantic=s,source_confidence=conf,stability_audit=physical_stability(c,s)))
   reviews.append(row)
  kb=merge_zone(kb,config,[],accepted)
  for a in accepted:
   p=next(p for p in kb['pois'] if p['id']==a['poi_id']);p['verification']['source']='Phase 2.5F bounded cached-pool recall; candidate only'
   p['entity_access_audit']=dict(entity_stability='stable',current_access_status=a['candidate'].get('current_access_status','unknown'),
    basis=a['stability_audit'],access_note=a['candidate'].get('current_access_note','Live opening hours are not a long-term admission criterion.'))
  accepted_ids[zone]=[a['poi_id'] for a in accepted]
  for r in reviews:
   a=next((a for a in accepted if a['candidate']['candidate_id']==r['candidate_id']),None)
   if a:r['poi_id']=a['poi_id']
  allrows[zone]=reviews;funnels[zone]=dict(funnel,recall_shortlist=len(short),recall_enriched=enriched,new_accept=len(accepted))
  write(OUT/f'{zone}_evidence_checks.json',checks);write(OUT/f'{zone}_prepared_shortlist.json',short);write(OUT/f'{zone}_review.json',dict(dispositions=reviews,human_review=[r for r in reviews if r['reason']=='weak_location'][:5],high_potential_unrescued=[r for r in reviews if r['decision']!='accept'][:5]))
 patches=coordinate_patches(kb)
 kb['metadata'].update(version='phase2.5f-recall-candidate',candidate_kb_status='pending_promotion_gate',recall_new_ids=accepted_ids,zone_expansion_passes=0)
 write(FINAL,kb);after=POIRepository(FINAL)
 for zone in ZONES:
  # EXACT same six requests on both KBs, so improved coverage cannot change fixtures.
  old_added=[p.id for p in repo.get_pois_by_zone(zone) if p.id.startswith('pz_')]
  fixtures=regression_cases(repo,zone,old_added)
  before=[describe(RouteEngine(repo),req,name,label) for name,label,req in fixtures]
  after_rows=[describe(RouteEngine(after),req,name,label) for name,label,req in fixtures]
  for group in (before,after_rows):
   for r in group:
    r['zone_isolation_passed']=all(after.get_poi_by_id(s['poi_id']).zone_id==zone for s in r['selected_stops'])
    r['relevance_passed']=all(s['poi_id'] in r['relevant_candidate_pool'] for s in r['selected_stops'])
    r['passed']=r['route_status']=='success' and r['minimum_viable_passed'] and r['composition_passed'] and r['negative_preference_passed'] and r['zone_isolation_passed'] and r['relevance_passed'] and (r['estimated_max_single_leg_km'] or 0)<=3.5
  sweep={}
  for label,repository in [('before',repo),('after',after)]:sweep[label]=[describe(RouteEngine(repository),RouteRequest(t,preferred_zone=zone),str(t),'no preference duration sweep') for t in (120,150,180)]
  write(OUT/f'{zone}_regression_comparison.json',dict(before=before,after=after_rows,duration_sweep=sweep))
  write(OUT/f'{zone}_coverage_comparison.json',dict(before=ZoneCoverageAnalyzer(zone,repo).analyze(),after=ZoneCoverageAnalyzer(zone,after).analyze()))
  funnels[zone]['final_nodes']=len(after.get_pois_by_zone(zone));write(OUT/f'{zone}_funnel_after.json',funnels[zone])
 for p,h in protected.items():assert hashlib.sha256(p.read_bytes()).hexdigest()==h,'Protected file changed: '+str(p)
 for old in load(BASE)['pois']:
  new=next(p for p in kb['pois'] if p['id']==old['id'])
  if old['id'] not in ('p7','p9','p13'):assert new==old,'Frozen existing changed: '+old['id']
  else:assert new['route_role']==old['route_role'] and new['route_role_audit']==old['route_role_audit']
 cost=dict(reused_cached_records=sum(f['raw_provider_records'] for f in funnels.values()),targeted_coordinate_provider_checks=3,
  targeted_retained_source_checks=sum(len(x['checks']) for z in ZONES for x in load(OUT/f'{z}_evidence_checks.json')),
  first_calls=sum(not r['retry'] for r in budget.rows),retry_calls=sum(r['retry'] for r in budget.rows),total_semantic_calls=len(budget.rows),
  accepted=sum(len(v) for v in accepted_ids.values()),deferred=sum(r['decision']=='defer' for rs in allrows.values() for r in rs),rejected=sum(r['decision']=='reject' for rs in allrows.values() for r in rs),
  no_mass_collection=True,west_bund_frozen=True,protected_sha256={str(p.relative_to(ROOT)):h for p,h in protected.items()})
 write(OUT/'cost_report.json',cost);print(json.dumps(dict(candidate=str(FINAL),nodes=len(kb['pois']),cost=cost),ensure_ascii=True))
 return kb

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--live',action='store_true');args=parser.parse_args();run(args.live)
