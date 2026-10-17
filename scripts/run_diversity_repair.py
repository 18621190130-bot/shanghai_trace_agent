"""Phase 2.5G: bounded evidence repair and diagnostics; candidate only."""
import copy,hashlib,itertools,json,re
from collections import Counter
from dataclasses import asdict
from datetime import datetime,timezone
from scripts.run_poi_pipeline import ROOT,load,write
from scripts.run_recall_repair import catalog,ZONES
from scripts.diversity_review_data import SELECTED,SOURCES,PROFILES,TAGS
from src.poi_pipeline.models import RawCandidate
from src.poi_pipeline.sources.amap_source import AmapSource
from src.poi_pipeline.boundary import boundary_status
from src.poi_pipeline.zone_config import ZonePipelineConfig
from src.poi_pipeline.zone_collection import consolidate_zone
from src.poi_pipeline.conservative_repair import ConservativeSemanticRepair
from src.poi_pipeline.zone_candidate_kb import merge_zone
from src.poi_pipeline.semantic.admission import source_confidence
from src.poi_pipeline.diversity import distribution,route_diversity
from src.poi_repository import POIRepository
from src.poi_pipeline.zone_regression import regression_cases
from src.route_engine import RouteEngine
from src.west_bund_regression import describe,run_regression
from src.models import RouteRequest
from src.geo_utils import haversine_km
from scripts.finalize_all_zones import cross_modes,validation_fingerprint

BASE=ROOT/'data/pois_phase2_5_recall_candidate.json';FINAL=ROOT/'data/pois_phase2_5_diversity_candidate.json'
OUT=ROOT/'data/poi_pipeline/diversity';F=ROOT/'data/poi_pipeline/recall';OLD=ROOT/'data/poi_pipeline/all_zones'
REMOVED='pz_f2fffcd2526c'

def source_checks(c,name):
 prior=[s for r in load(F/f'{c["walk_zone"]}_evidence_checks.json') if r['name']==name for s in r['checks']]
 path=OUT/'evidence_checks.json';saved=load(path) if path.exists() else []
 rows=[]
 for url,text,typ in SOURCES.get(name,[]):
  old=next((s for s in prior if s['url']==url and s.get('excerpt')==text),None)
  timestamp=old['retrieved_at'] if old else next((s['retrieved_at'] for s in saved if s['name']==name and s['url']==url),datetime.now(timezone.utc).isoformat())
  rid='diversity_'+hashlib.sha256((name+url).encode()).hexdigest()[:12]
  address=next((a for a in ('五原路288弄3号','乌鲁木齐南路176号','淮海中路1670弄','海伦路505号','南京东路353号') if a in text),'')
  record=RawCandidate(rid,typ,'Phase 2.5G subject-specific inspected source',url,timestamp,name_zh=name,address=address,
   coordinate_system='GCJ-02',source_category='subject_specific_excerpt',snippets=[dict(text=text,supports=['history','public_space'],extraction='short inspected source passages, whitespace joined; not live access verification')])
  c['merged_source_records'].append(asdict(record));c['sources'].append(dict(source_type=typ,source_candidate_id=rid,url=url,retrieved_at=timestamp))
  rows.append(dict(name=name,url=url,excerpt=text,source_type=typ,retrieved_at=timestamp,reused_f_check=bool(old)))
 return rows

def map_identity(c,name):
 row=next((r for r in load(OUT/'map_checks.json') if r['candidate_name']==name),None)
 if not row or row['status']!='success':return dict(status='cached_geometry_retained',reason='new map query unavailable or intentionally skipped; authority/address and cached coordinate reviewed separately')
 wanted={'上海人民广场':'B00157917M','中国社会主义青年团中央机关旧址':'B0FFFV4AU5','大韩民国临时政府旧址':'B001556HRR','李白烈士故居':'B00155L3BC','沈尹默故居':'B00155L3B4','日本海军特别陆战队司令部旧址':'B00155MRU8'}
 p=next((p for p in row['results'] if p['id']==wanted.get(name)),None)
 if not p:return dict(status='identity_not_resolved',reason='No reviewed provider match; do not pick nearest name automatically')
 record=AmapSource.parse(p,row['retrieved_at']);old=c['coordinates']
 c['merged_source_records']=[r for r in c['merged_source_records'] if r['source_type']+':'+r['source_candidate_id']!='amap:'+p['id']]+[asdict(record)]
 c['sources'].append(dict(source_type='amap',source_candidate_id=p['id'],url=record.source_url,retrieved_at=record.retrieved_at))
 c['coordinates']=list(record.coordinates);c['field_sources']['coordinates']='amap:'+p['id'];c['address']=record.address;c['field_sources']['address']='amap:'+p['id']
 c['boundary_status']=boundary_status(c['coordinates'],ZonePipelineConfig.load(c['walk_zone']).polygon,150)
 return dict(status='identity_verified',provider_id=p['id'],provider_name=p['name'],address=p['address'],old_coordinate=old,new_coordinate=c['coordinates'],coordinate_system='GCJ-02',offset_m=round(haversine_km(old,c['coordinates'])*1000,1),
  basis='Explicitly reviewed named parent identity/address; subobjects/entrances and unrelated names excluded.',representative_coordinate_not_entire_entity_boundary=True)

def review_pool(zone,repo):
 pools=load(OLD/f'{zone}_prepared_nodes.json')+load(F/f'{zone}_prepared_shortlist.json')
 chosen=[]
 for name in SELECTED[zone]:
  matches=[c for c in pools if (c['name_zh'] or c['name_en'])==name]
  if not matches:raise ValueError('Missing cached candidate '+name)
  # Use F-prepared identity when available, but preserve cached successful outputs.
  c=copy.deepcopy(matches[-1]);c['original_cached_name']=name
  c['recall_parent']=None
  chosen.append(c)
 chosen,registry=consolidate_zone(chosen,repo,ZonePipelineConfig.load(zone))
 assert len(chosen)<=10
 return chosen,registry

def regression(repository,fixtures,index):
 rows=[]
 for name,label,req in fixtures:
  r=describe(RouteEngine(repository),req,name,label)
  r['zone_isolation_passed']=all(repository.get_poi_by_id(s['poi_id']).zone_id==req.preferred_zone for s in r['selected_stops'])
  r['relevance_passed']=all(s['poi_id'] in r['relevant_candidate_pool'] for s in r['selected_stops'])
  r['passed']=r['route_status']=='success' and r['minimum_viable_passed'] and r['composition_passed'] and r['negative_preference_passed'] and r['zone_isolation_passed'] and r['relevance_passed'] and (r['estimated_max_single_leg_km'] or 0)<=3.5
  r['diversity_diagnostics']=route_diversity(r,index);rows.append(r)
 return rows

def run():
 OUT.mkdir(exist_ok=True)
 protected={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'data/pois.json',ROOT/'data/pois_phase2_5_candidate.json',ROOT/'data/pois_phase2_5_all_zones_candidate.json',BASE,ROOT/'data/poi_pipeline/zone_configs.json',ROOT/'src/poi_pipeline/semantic/validation.py',ROOT/'src/route_engine.py')}
 original=load(BASE);kb=copy.deepcopy(original);repo=POIRepository(BASE)
 assert next(p for p in kb['pois'] if p['id']==REMOVED)['name']['zh']=='爱思儿童公园'
 kb['pois']=[p for p in kb['pois'] if p['id']!=REMOVED]
 for z,ids in kb['metadata']['recall_new_ids'].items():kb['metadata']['recall_new_ids'][z]=[pid for pid in ids if pid!=REMOVED]
 all_checks=[];accepted_all=[];dispositions=[];repairs=ConservativeSemanticRepair();newids={}
 for zone in ZONES:
  candidates,registry=review_pool(zone,repo);accepted=[]
  for c in candidates:
   name=c['original_cached_name'];row=dict(zone=zone,name=name,candidate_id=c['candidate_id'],decision='defer',route_selectable=False)
   if c.get('internal_parent') or c['identity']['identity_status']!='new_candidate':row['reason']='duplicate_or_parent_child';dispositions.append(row);continue
   checks=source_checks(c,name);all_checks+=checks;row['map_identity']=map_identity(c,name)
   if name=='张乐平':c['aliases'].append('张乐平');c['name_zh']='张乐平故居';c['address']='五原路288弄3号'
   if name=='优秀历史建筑乌鲁木齐南路176号':c['aliases']+=['巨福公寓','乌鲁木齐公寓'];c['name_zh']='安康公寓（乌鲁木齐南路176号）';c['address']='乌鲁木齐南路176号'
   if name=='中南新邨':c['entity_kind']='street';c['address']='淮海中路1670弄'
   if name=='四川北路文化中心图书馆':c['aliases'].append(c['name_zh']);c['name_zh']='四川北路街道图书馆（海伦路505号）';c['address']='海伦路505号'
   if name=='东海大楼':c['aliases']+=['慈淑大楼','东海商都'];c['address']='南京东路353号'
   if name=='福州路':c['entity_kind']='street'
   # A normalized address must point to the actual inspected authority atom.
   for record in c['merged_source_records']:
    if record['source_type'] in ('government','official') and record.get('address')==c.get('address') and record.get('address'):
     c['field_sources']['address']=record['source_type']+':'+record['source_candidate_id']
   catalog(c)
   if name=='上海多伦路地区海派文化馆(多伦生活广场店)':row.update(reason='unresolved_venue_identity',missing_evidence='多伦路179号存在报纸/地图博物馆名称，不能与今潮海派文化中心混同；未验证该文化馆独立常设展陈。');dispositions.append(row);continue
   if name=='盛宣怀住宅':row.update(reason='independent_public_observation_unresolved',missing_evidence='权威名单证明住宅稳定存在，但街面可见范围及领事住宅围墙遮挡未核实；保留供人工选择，不凭住宅名气凑数。');dispositions.append(row);continue
   if c['boundary_status']!='inside_pilot':row.update(reason='needs_boundary_review' if c['boundary_status']=='needs_review' else 'outside_boundary');dispositions.append(row);continue
   if not checks:row.update(reason='missing_direct_authority_evidence');dispositions.append(row);continue
   refs=[r for r,a in c['evidence_catalog'].items() if a['source_type'] in ('government','official') and a['field']=='description']
   if not refs:refs=[r for r,a in c['evidence_catalog'].items() if a['source_type'] in ('government','official') and isinstance(a['value'],str) and len(a['value'])>20 and a['field'] not in ('name_zh','name_en','address','category')]
   try:
    result=repairs.build(c,repo.taxonomy,profile=PROFILES[name],tags=TAGS[name],summary_ref=refs[-1])
    row.update(decision='accept',reason='fresh_conservative_skeleton_strict_validator_passed',route_selectable=True,route_role=result['semantic']['route_role'])
    write(OUT/f'{c["candidate_id"]}_repair.json',dict(candidate=c,**result))
    accepted.append(dict(candidate=c,semantic=result['semantic'],source_confidence=source_confidence(c)['overall'],stability_audit=dict(accepted=True,confidence='medium',basis='mapped fixed entity plus direct subject authority; current open/closed status not a permanence criterion'),profile_name=name,facets=result['facets']))
   except (ValueError,KeyError) as exc:row.update(reason='conservative_skeleton_validation_failed',missing_evidence=str(exc))
   dispositions.append(row)
  kb=merge_zone(kb,ZonePipelineConfig.load(zone),[],accepted)
  newids[zone]=[a['poi_id'] for a in accepted]
  for a in accepted:
   p=next(p for p in kb['pois'] if p['id']==a['poi_id'])
   p['verification']['source']='Phase 2.5G deterministic evidence skeleton; candidate only'
   p['urban_texture_audit']=dict(facets=a['facets'],scope=a['semantic']['visit_profile_proposal']['scope'],basis='Explicit product typology of supported visit scope; no ordinary park counted as urban texture')
   p['entity_access_audit']=dict(entity_stability='stable',current_access_status='unknown',access_scope=a['semantic']['visit_profile_proposal']['scope'])
   if a['profile_name']=='上海人民广场':p['admission']='human_approved';p['verification']['status']='human_product_approved_facts_strictly_validated_candidate'
   for row in dispositions:
    if row['candidate_id']==a['candidate']['candidate_id']:row['poi_id']=a['poi_id']
  accepted_all+=accepted
  write(OUT/f'{zone}_shortlist.json',candidates);write(OUT/f'{zone}_consolidation.json',registry)
 write(OUT/'evidence_checks.json',all_checks);write(OUT/'review.json',dispositions)
 kb['metadata'].update(version='phase2.5g-diversity-candidate',poi_count=len(kb['pois']),candidate_kb_status='pending_diversity_promotion_gate',diversity_new_ids=newids,
  zone_expansion_passes=0,removal_decisions=[dict(poi_id=REMOVED,name='爱思儿童公园',reason='explicit user removal overrides pasted G preservation rule',scope='new diversity candidate only')])
 write(FINAL,kb);after=POIRepository(FINAL);oldindex={p['id']:p for p in original['pois']};newindex={p['id']:p for p in kb['pois']}
 assert set(oldindex)-set(newindex)=={REMOVED}
 for pid,p in oldindex.items():
  if pid!=REMOVED:assert p==newindex[pid],'Frozen existing node changed '+pid
 for path,h in protected.items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h,path
 for zone in after.zone_order:
  write(OUT/f'{zone}_diversity_comparison.json',dict(before=distribution([p for p in original['pois'] if p['walk_zone']['id']==zone]),after=distribution([p for p in kb['pois'] if p['walk_zone']['id']==zone])))
 for zone in ZONES:
  fixtures=regression_cases(repo,zone,[p.id for p in repo.get_pois_by_zone(zone) if p.id.startswith('pz_')])
  if zone=='old_city_central':extras=[('history_street',['history'],['street_scene'],[]),('old_city_life',['local_life'],[],['old_city']),('architecture_neighborhood',['architecture'],['neighborhood_walk'],[])]
  elif zone=='wukang_fuxing_xujiahui':extras=[('architecture_life',['architecture','local_life'],['street_scene'],[])]
  else:extras=[('literature_neighborhood',['literature','history'],['neighborhood_walk','street_scene'],[])]
  fixtures+= [(name,'G urban texture theme',RouteRequest(180,preferred_zone=zone,interest_tags=i,experience_tags=e,culture_tags=c)) for name,i,e,c in extras]
  comparisons={label:regression(repository,fixtures,index) for label,repository,index in [('before',repo,oldindex),('after',after,newindex)]}
  comparisons['duration_sweep']={label:regression(repository,[(str(t),'no preferences',RouteRequest(t,preferred_zone=zone)) for t in (120,150,180)],index) for label,repository,index in [('before',repo,oldindex),('after',after,newindex)]}
  write(OUT/f'{zone}_regression_comparison.json',comparisons)
 west,modes=run_regression(after)
 for row in west:row['diversity_diagnostics']=route_diversity(row,newindex)
 write(OUT/'west_bund_read_only_regression.json',dict(cases=west,three_modes=modes))
 cross=cross_modes(after)
 for row in cross:
  stops=(row.get('route_plan') or {}).get('ordered_pois',[])
  row['diversity_diagnostics']=route_diversity(dict(selected_stops=[dict(poi_id=s['poi_id'],primary_role=s['effective_primary_role']) for s in stops]),newindex)
 write(OUT/'cross_zone_three_modes.json',cross)
 parks=[p for p in kb['pois'] if p['poi_type']=='park'];pairs=[]
 for a,b in itertools.combinations(parks,2):
  if a['walk_zone']['id']!=b['walk_zone']['id']:continue
  distance=haversine_km(after.get_poi_by_id(a['id']).coordinates,after.get_poi_by_id(b['id']).coordinates)
  ta={t for ts in a['tags'].values() for t in ts};tb={t for ts in b['tags'].values() for t in ts};similar=len(ta&tb)/len(ta|tb)
  if distance<1 or similar>.8:pairs.append(dict(poi_ids=[a['id'],b['id']],names=[a['name']['zh'],b['name']['zh']],distance_km=round(distance,3),tag_jaccard=round(similar,3),same_primary_role=a['route_role']['primary']==b['route_role']['primary'],recommendation='review_keep_or_remove; proximity/tag similarity alone does not prove spatial or experiential duplication',automatic_removal=False))
 write(OUT/'park_redundancy_review.json',pairs)
 write(OUT/'cost_report.json',dict(semantic_candidates_per_zone={z:len(SELECTED[z]) for z in ZONES},semantic_candidates_total=18,deepseek_calls=0,reused_f_source_checks=sum(r['reused_f_check'] for r in all_checks),new_retained_subject_checks=sum(not r['reused_f_check'] for r in all_checks),
  targeted_map_calls=len(load(OUT/'map_checks.json')),map_provider_statuses=dict(Counter(r['status'] for r in load(OUT/'map_checks.json'))),accepted=len(accepted_all),deferred=sum(r['decision']=='defer' for r in dispositions),protected_sha256=protected,full_zone_collection_calls=0,
  source_checks_definition='Retained inspected candidate/source pairs; broad search-result snippets excluded. Failed map reservations counted, never hidden. Existing coordinate/source caches reused; no model tokens or currency costs.'))
 write(OUT/'assembly_status.json',dict(nodes=len(kb['pois']),accepted=len(accepted_all),deferred=sum(r['decision']=='defer' for r in dispositions),new_ids=newids,semantic_fingerprint=validation_fingerprint(kb)))
 print(json.dumps(dict(nodes=len(kb['pois']),accepted=len(accepted_all),dispositions=dispositions),ensure_ascii=True))
 return kb

if __name__=='__main__':run()
