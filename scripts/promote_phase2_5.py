"""Explicit final human deletions, offline gates and atomic Phase 2.5 promotion."""
import copy,hashlib,json,os,subprocess,sys,time
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from scripts.run_poi_pipeline import ROOT,load,write
from scripts.run_diversity_repair import regression
from scripts.finalize_all_zones import cross_modes,validation_fingerprint
from src.poi_repository import POIRepository
from src.models import RouteRequest,DataValidationError
from src.poi_pipeline.diversity import route_diversity
from src.west_bund_regression import run_regression

SOURCE=ROOT/'data/pois_phase2_5_diversity_candidate.json'
FINAL=ROOT/'data/pois_phase2_5_final_candidate.json'
PRODUCTION=ROOT/'data/pois.json'
BACKUP=ROOT/'data/archive/pois_pre_phase2_5.json'
OUT=ROOT/'data/poi_pipeline/promotion'
G=ROOT/'data/poi_pipeline/diversity'
MANIFEST=ROOT/'data/PHASE2_5_PROMOTION_MANIFEST.json'
REMOVALS={'pz_42efca09357d':'中国社会主义青年团中央机关旧址','pz_463c9b82ac1e':'东海大楼','pz_bc5155c245b0':'四川北路街道图书馆（海伦路505号）'}
EXPECTED={'wukang_fuxing_xujiahui':17,'old_city_central':15,'hongkou_literary':14,'west_bund':13}
OLD_SHA='6585b3baf653ae89cc6a1e3c5fc10140bdd801fb298d92c392381d0b5fc17513'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def diff_check(source,final):
 expected=copy.deepcopy(source);expected['pois']=[p for p in expected['pois'] if p['id'] not in REMOVALS]
 for i,p in enumerate(expected['pois'],1):p['display_order']=i
 assert expected['pois']==final['pois'],'Retained POI content changed beyond authorized display_order'
 for k,v in source.items():
  if k not in ('metadata','pois'):assert final[k]==v,k
 a=copy.deepcopy(source['metadata']);b=copy.deepcopy(final['metadata'])
 for group in ('recall_new_ids','diversity_new_ids'):
  for z,ids in a.get(group,{}).items():a[group][z]=[pid for pid in ids if pid not in REMOVALS]
 for m in (a,b):
  for k in ('poi_count','promotion'):m.pop(k,None)
  for z in m['walk_zones']:z.pop('poi_count',None)
 assert a==b,'Unauthorized metadata change'
 counts=dict(Counter(p['walk_zone']['id'] for p in final['pois']))
 assert counts==EXPECTED,(counts,EXPECTED)
 assert len(final['pois'])==59
 assert all(p['route_selectable'] and p['counts_as_route_stop'] for p in final['pois'])
 assert {p['id'] for p in source['pois']}-{p['id'] for p in final['pois']}==set(REMOVALS)
 return dict(passed=True,removed_ids=list(REMOVALS),retained_objects_unchanged_except_display_order=True,stable_ids_unchanged=True,retained_order_unchanged=True,display_order_changes=[dict(poi_id=p['id'],before=p['display_order'],after=i) for i,p in enumerate([p for p in source['pois'] if p['id'] not in REMOVALS],1) if p['display_order']!=i],zone_counts=counts,final_count=len(final['pois']))

def prepare():
 OUT.mkdir(parents=True,exist_ok=True)
 source=load(SOURCE);assert len(source['pois'])==62
 assert source['metadata']['candidate_kb_status']=='READY_FOR_PRODUCTION_PROMOTION'
 for pid,name in REMOVALS.items():assert next(p for p in source['pois'] if p['id']==pid)['name']['zh']==name
 if BACKUP.exists():assert sha(BACKUP)==OLD_SHA,'Existing backup hash mismatch'
 else:
  assert sha(PRODUCTION)==OLD_SHA,'Unexpected pre-promotion production'
  BACKUP.parent.mkdir(parents=True,exist_ok=True)
  with BACKUP.open('xb') as stream:stream.write(PRODUCTION.read_bytes());stream.flush();os.fsync(stream.fileno())
 assert len(load(BACKUP)['pois'])==27 and sha(BACKUP)==OLD_SHA
 backup_meta=BACKUP.with_suffix('.manifest.json')
 if not backup_meta.exists():write(backup_meta,dict(sha256=OLD_SHA,created_at=now(),source_file='data/pois.json',promotion_phase='2.5',poi_count=27))
 final=copy.deepcopy(source);final['pois']=[p for p in final['pois'] if p['id'] not in REMOVALS]
 for i,p in enumerate(final['pois'],1):p['display_order']=i
 for group in ('recall_new_ids','diversity_new_ids'):
  for z,ids in final['metadata'].get(group,{}).items():final['metadata'][group][z]=[pid for pid in ids if pid not in REMOVALS]
 final['metadata']['poi_count']=len(final['pois'])
 for zone in final['metadata']['walk_zones']:zone['poi_count']=sum(p['walk_zone']['id']==zone['id'] for p in final['pois'])
 final['metadata']['promotion']=dict(phase='2.5',source_candidate=str(SOURCE.relative_to(ROOT)),source_candidate_sha256=sha(SOURCE),manual_removals=[dict(poi_id=p,name=n,reason='explicit_human_product_removal') for p,n in REMOVALS.items()],display_order_authorization='explicit user authorization; continuous display numbering only; stable IDs and all other POI fields frozen',production_baseline='human-approved final Phase 2.5',phase_status='COMPLETE / FROZEN after manifest promotion gates',production_imported_after_atomic_promotion=True)
 result=diff_check(source,final);write(FINAL,final)
 old={p['id']:p for p in load(BACKUP)['pois']};index={p['id']:p for p in final['pois']}
 assert set(old)<=set(index),'Original production IDs lost'
 result['inherited_coordinate_changes']=[dict(poi_id=pid,name=index[pid]['name']['zh'],old_location=p['location'],new_location=index[pid]['location'],basis='coordinate changes inherited from Phase 2.5 validated candidate; no new geocoding') for pid,p in old.items() if p['location']!=index[pid]['location']]
 result['protected_files']={str(p.relative_to(ROOT)):sha(p) for p in [SOURCE,ROOT/'data/pois_phase2_5_candidate.json',ROOT/'data/pois_phase2_5_all_zones_candidate.json',ROOT/'data/pois_phase2_5_recall_candidate.json',ROOT/'data/poi_pipeline/zone_configs.json',*[p for p in sorted((ROOT/'src').rglob('*.py'))]]}
 write(OUT/'object_diff.json',result)
 try:POIRepository(FINAL)
 except DataValidationError as exc:
  blocker=dict(status='BLOCKED',stage='final_candidate_schema',reason=str(exc),policy_conflict='Deleting objects preserves display_order gaps; retained POI object mutation is prohibited by the promotion request.',production_unchanged=sha(PRODUCTION)==OLD_SHA,final_candidate_sha256=sha(FINAL))
  write(OUT/'gate_status.json',blocker)
  raise
 write(OUT/'gate_status.json',dict(status='SCHEMA_AND_OBJECT_DIFF_PASSED',stage='final_candidate_schema',schema_valid=True,production_unchanged=sha(PRODUCTION)==OLD_SHA,final_candidate_sha256=sha(FINAL)))
 return result

def regress(path=FINAL,label='pre'):
 repo=POIRepository(path);index={p['id']:p for p in load(path)['pois']};results={};checks={}
 for zone in EXPECTED:
  if zone=='west_bund':continue
  previous=load(G/f'{zone}_regression_comparison.json')
  rows=regression(repo,[(r['case'],r['label'],RouteRequest(**r['request'])) for r in previous['after']],index)
  sweep=regression(repo,[(r['case'],r['label'],RouteRequest(**r['request'])) for r in previous['duration_sweep']['after']],index)
  checks[zone]=all(not a['passed'] or b['passed'] for a,b in zip(previous['after'],rows)) and all(not a['passed'] or b['passed'] for a,b in zip(previous['duration_sweep']['after'],sweep))
  checks[zone+'_hard_constraints']=all(r['negative_preference_passed'] and r['zone_isolation_passed'] and r['relevance_passed'] and r['total_estimated_time']<=r['request']['available_minutes'] for r in rows+sweep)
  results[zone]=dict(before=previous['after'],after=rows,duration_sweep=sweep)
 west,modes=run_regression(repo);previous=load(G/'west_bund_read_only_regression.json')['cases']
 checks['west_bund']=all(r['route_status']==a['route_status'] for r,a in zip(west,previous)) and len(west)==len(previous)
 cross=cross_modes(repo)
 for r in cross:
  stops=(r['route_plan'] or {}).get('ordered_pois',[])
  r['diversity_diagnostics']=route_diversity(dict(selected_stops=[dict(poi_id=s['poi_id'],primary_role=s['effective_primary_role']) for s in stops]),index)
 checks['cross_modes']=len(cross)==12 and all(r['passed'] for r in cross)
 results.update(west_bund=dict(cases=west,three_modes=modes),cross_modes=cross,checks=checks,passed=all(checks.values()),kb_path=str(path.relative_to(ROOT)))
 write(OUT/f'{label}_regression.json',results)
 print(json.dumps(dict(stage=label,checks=checks),ensure_ascii=True))
 return results

def full_tests(label):
 rows=[]
 for command in ([sys.executable,'-m','unittest','discover','-s','tests','-t','.','-q'],[sys.executable,'-m','scripts.verify_all_zones']):
  started=time.monotonic();r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
  output=r.stdout+r.stderr;filename=f'{label}_tests_{len(rows)+1}.txt';(OUT/filename).write_text(output,encoding='utf-8')
  import re
  match=re.search(r'Ran (\d+) tests',output)
  count=int(match.group(1)) if match else load(ROOT/'data/poi_pipeline/all_zones/full_test_report.json')['tests_run']
  row=dict(command='python '+' '.join(command[1:]),exit_code=r.returncode,tests_run=count,output=filename,elapsed_seconds=round(time.monotonic()-started,3));rows.append(row);print(row,flush=True)
  if r.returncode:print(output[-12000:],flush=True)
 report=dict(successful=all(r['exit_code']==0 for r in rows),runs=rows,completed_at=now(),validation_fingerprint=validation_fingerprint(load(FINAL)))
 write(OUT/f'{label}_full_tests.json',report);return report

def promote():
 d=load(OUT/'object_diff.json');reg=load(OUT/'pre_regression.json');tests=load(OUT/'pre_full_tests.json')
 diff_check(load(SOURCE),load(FINAL));POIRepository(FINAL)
 assert all(sha(ROOT/p)==h for p,h in d['protected_files'].items()),'Frozen source files changed'
 assert reg['passed'] and tests['successful'] and tests['validation_fingerprint']==validation_fingerprint(load(FINAL)),'Regression/test gate failed'
 assert sha(PRODUCTION)==OLD_SHA and sha(BACKUP)==OLD_SHA,'Backup/current production mismatch'
 manifest=dict(source_candidate=str(SOURCE.relative_to(ROOT)),source_candidate_sha256=sha(SOURCE),final_candidate=str(FINAL.relative_to(ROOT)),final_candidate_sha256=sha(FINAL),manual_removed_ids=list(REMOVALS),manual_removed_names=list(REMOVALS.values()),final_poi_count=len(load(FINAL)['pois']),zone_counts=d['zone_counts'],old_production_sha256=OLD_SHA,new_production_sha256=sha(FINAL),promotion_timestamp=now(),phase='2.5',status='PREPARED',tests=tests,regression_status=reg['checks'],backup=str(BACKUP.relative_to(ROOT)),backup_sha256=sha(BACKUP))
 write(MANIFEST,manifest)
 temp=PRODUCTION.with_name('pois.phase2_5_promotion.tmp')
 with temp.open('xb') as stream:stream.write(FINAL.read_bytes());stream.flush();os.fsync(stream.fileno())
 assert sha(temp)==sha(FINAL);os.replace(temp,PRODUCTION)
 assert sha(PRODUCTION)==sha(FINAL)
 manifest['status']='PROMOTED_PENDING_POST_VERIFICATION';write(MANIFEST,manifest)
 print(json.dumps(dict(status=manifest['status'],sha256=sha(PRODUCTION))))

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('step',choices=['prepare','regress','test','promote','post-regress','post-test']);a=p.parse_args()
 if a.step=='prepare':print(prepare())
 elif a.step=='regress':raise SystemExit(0 if regress()['passed'] else 1)
 elif a.step=='test':raise SystemExit(0 if full_tests('pre')['successful'] else 1)
 elif a.step=='promote':promote()
 elif a.step=='post-regress':raise SystemExit(0 if regress(PRODUCTION,'post')['passed'] else 1)
 elif a.step=='post-test':raise SystemExit(0 if full_tests('post')['successful'] else 1)
