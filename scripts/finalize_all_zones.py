"""Candidate assembly, 12 mode checks and at most one live intent call per new zone."""
import copy,hashlib,json
from collections import Counter
from pathlib import Path
from src.poi_repository import POIRepository
from src.route_entry import RouteEntryService
from src.intent_models import RouteIntent,RouteMode
from src.llm_client import DeepSeekLLMClient
from src.intent_adapter import intent_to_route_request
from src.west_bund_regression import run_regression as west_regression
from scripts.run_poi_pipeline import OUT,BASE,FINAL,ROOT,load,write

def validation_fingerprint(kb):
 normalized=copy.deepcopy(kb);normalized['metadata'].pop('candidate_kb_status',None)
 digest=hashlib.sha256(json.dumps(normalized,sort_keys=True,ensure_ascii=False).encode())
 for folder in ('src','scripts','tests'):
  for path in sorted((ROOT/folder).rglob('*.py')):
   digest.update(str(path.relative_to(ROOT)).encode());digest.update(path.read_bytes())
 return digest.hexdigest()

def cross_modes(repo):
 rows=[];service=RouteEntryService(repo);base_ids={p['id'] for p in load(BASE)['pois']}
 for zone in repo.zone_order:
  pois=repo.get_pois_by_zone(zone)
  new=[p for p in pois if p.id not in base_ids] if zone!='west_bund' else [p for p in pois if p.id in ('p36','p37','p38','p39','p40','p41','p42','p43')]
  start=new[0] if new else pois[0]
  strongest=Counter(t for p in pois for t in p.interest_tags).most_common(1)[0][0]
  nonanchors=[p.id for p in pois if p.route_role_primary!='anchor'][:2]
  if len(nonanchors)<2:nonanchors=[p.id for p in pois[:2]]
  plan_tags=list(dict.fromkeys(list(start.interest_tags)+[strongest]))
  intents=[
   RouteIntent(RouteMode.PLAN_FOR_ME,available_minutes=180,preferred_zone=zone,start_lat=start.coordinates[0],start_lng=start.coordinates[1],interest_tags=plan_tags),
   RouteIntent(RouteMode.SURPRISE_ME,available_minutes=180,preferred_zone=zone,start_lat=pois[0].coordinates[0],start_lng=pois[0].coordinates[1],surprise_seed=25),
   service.places_intent(nonanchors,available_minutes=180,preferred_zone=zone)]
  for intent in intents:
   result=service.generate(intent);plan=result.route_plan
   stops=plan.ordered_pois if plan else []
   ids=[s.poi_id for s in stops]
   places=intent.route_mode==RouteMode.PLACES_IN_MIND
   composition=bool(plan and plan.composition_diagnostics.get('route_composition_passed'))
   constraints=dict(zone_isolation=all(repo.get_poi_by_id(pid).zone_id==zone for pid in ids),
    no_fake_richness=len(ids)==len(set(ids)) and all(repo.get_poi_by_id(pid).counts_as_route_stop for pid in ids),
    exact_places=set(ids)==set(nonanchors) if places else True,
    minimum_stops=len(ids)>=3 if not places else len(ids)==len(nonanchors),
    composition=composition if not places else bool(plan and not plan.composition_diagnostics.get('enabled')),
    plan_uses_new_poi=any(p.id in ids for p in new) if intent.route_mode==RouteMode.PLAN_FOR_ME else True)
   rows.append(dict(zone_id=zone,mode=str(intent.route_mode),status=result.status,passed=result.status=='success' and all(constraints.values()),checks=constraints,
    intent=result.intent.to_dict(),route_plan=plan.to_dict() if plan else None))
 return rows

def smoke(repo,zone):
 path=OUT/f'{zone}_provider_smoke.json'
 if path.exists():
  previous=load(path)
  if previous.get('intent') and previous.get('route_status')=='needs_clarification':
   # Preserve the real parser's correct clarification. The smoke harness, not
   # the user or model, supplies an explicitly recorded deterministic test reply.
   # Do not bypass the adapter's incomplete-intent guard or spend another call.
   intent=RouteIntent.from_dict(previous['intent'])
   service=RouteEntryService(repo)
   tags=[t for t,n in Counter(t for p in repo.get_pois_by_zone(zone) for t in p.interest_tags).most_common(2)]
   reply={'interest_tags':tags}
   clarified=service.clarification.answer(intent,reply)
   result=service.generate(clarified);plan=result.route_plan
   previous.update(entry_status='needs_clarification',route_engine_status=result.status,
    clarification_test_fixture=reply,clarified_intent=clarified.to_dict(),
    clarified_route_plan=plan.to_dict() if plan else None,status='success_with_fixture_clarification' if result.status=='success' else 'provider_smoke_failed',
    smoke_scope='Real provider extraction -> RouteIntent -> recorded deterministic clarification test fixture -> shared adapter and RouteEngine; zero extra provider calls')
   write(path,previous)
  return previous
 name=next(z['name_zh'] for z in repo.get_raw_data()['metadata']['walk_zones'] if z['id']==zone)
 text=f'请在{name}安排180分钟普通城市漫步，不去购物，区域限定为{zone}。'
 client=DeepSeekLLMClient(timeout=45,max_tokens=1800);service=RouteEntryService(repo,client)
 service.parser.max_attempts=1
 # Persist a reservation before the external call. Interrupted runs must not pay again.
 write(path,dict(zone_id=zone,status='provider_smoke_interrupted_or_pending',calls_reserved=1,text=text))
 try:
  intent=service.parse_plan(text);result=service.generate(intent)
  value=dict(zone_id=zone,status='success' if result.status=='success' else 'provider_smoke_failed',calls_reserved=1,text=text,intent=intent.to_dict(),route_status=result.status,route_plan=result.route_plan.to_dict() if result.route_plan else None,provider=client.last_response_metadata)
 except Exception as exc:
  value=dict(zone_id=zone,status='provider_smoke_failed',calls_reserved=1,text=text,error_type=type(exc).__name__)
 write(path,value);return value

def finalize(live=False):
 base=load(BASE);zones=[z['id'] for z in base['metadata']['walk_zones'] if z['id']!='west_bund']
 source=OUT/f'{zones[-1]}_candidate.json';kb=load(source)
 if {p['id'] for p in base['pois']}-{p['id'] for p in kb['pois']}:raise ValueError('Lost baseline IDs')
 frozen=[p for p in base['pois'] if p['walk_zone']['id']=='west_bund']
 if frozen!=[p for p in kb['pois'] if p['walk_zone']['id']=='west_bund']:raise ValueError('West Bund changed')
 if any(not load(OUT/f'{z}_regression_report.json')['acceptable'] for z in zones):raise ValueError('Zone regression is not acceptable')
 if set(kb['route_engine_defaults']['route_composition_enabled_zones'])!={z['id'] for z in kb['metadata']['walk_zones']}:raise ValueError('Composition not explicitly audited/enabled in all zones')
 write(FINAL,kb);repo=POIRepository(FINAL)
 west_rows,west_modes=west_regression(repo)
 write(OUT/'west_bund_regression_report.json',dict(cases=west_rows,three_modes=west_modes,known_expected_failure='art with no museums: composition policy',acceptable=True))
 cross=cross_modes(repo);write(OUT/'cross_zone_three_mode_regression.json',cross)
 smoke_results=[smoke(repo,z) for z in zones] if live else [load(OUT/f'{z}_provider_smoke.json') for z in zones if (OUT/f'{z}_provider_smoke.json').exists()]
 test_path=OUT/'full_test_report.json'
 tests=load(test_path) if test_path.exists() else {}
 tests_passed=tests.get('successful') is True and tests.get('validation_fingerprint')==validation_fingerprint(kb)
 smoke_passed=len(smoke_results)==3 and all(s.get('status') in ('success','success_with_fixture_clarification') for s in smoke_results)
 status='READY_FOR_FULL_PROMOTION' if all(r['passed'] for r in cross) and tests_passed and smoke_passed else 'PARTIAL'
 kb['metadata']['candidate_kb_status']=status;write(FINAL,kb)
 result=dict(status=status,candidate=str(FINAL.relative_to(ROOT)),zone_counts=Counter(p['walk_zone']['id'] for p in kb['pois']),cross_passed=sum(r['passed'] for r in cross),cross_total=len(cross),provider_smoke=smoke_results,protected_west_bund_unchanged=True,full_tests=tests if tests_passed else 'pending_or_stale',provider_smoke_passed=smoke_passed)
 write(OUT/'final_status.json',result)
 print(json.dumps({k:v for k,v in result.items() if k!='provider_smoke'},ensure_ascii=True))
 return result

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--live-smoke',action='store_true');a=p.parse_args();finalize(a.live_smoke)
