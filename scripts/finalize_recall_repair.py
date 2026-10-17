"""Read-only baseline checks and an honest Phase 2.5F promotion decision."""
import hashlib,json
from collections import Counter
from datetime import datetime,timezone
from scripts.run_recall_repair import ROOT,BASE,FINAL,OUT,OLD,ZONES,load,write
from scripts.finalize_all_zones import cross_modes,validation_fingerprint
from src.poi_repository import POIRepository
from src.west_bund_regression import run_regression
from src.poi_pipeline.recall import RecallBudget
from src.poi_pipeline.semantic.validation import validate_semantic_enrichment
from src.poi_pipeline.subject_validation import validate_subject_scope
from src.poi_pipeline.role_audit import validate_role
from src.poi_pipeline.boundary import boundary_status
from src.poi_pipeline.zone_config import ZonePipelineConfig

NAMES={'old_city_central':'老城厢—新天地—外滩','wukang_fuxing_xujiahui':'武康—复兴—徐家汇','hongkou_literary':'鲁迅公园—四川北路','west_bund':'West Bund'}
STRONG_UNRESOLVED=('中国社会主义青年团中央机关旧址','徐家汇公园','李白烈士故居','沈尹默故居')
PRIORITY={
 'old_city_central':['中国社会主义青年团中央机关旧址','大韩民国临时政府旧址','福州路','徐光启故居(九间楼)','延中公园'],
 'wukang_fuxing_xujiahui':['徐家汇公园','普希金雕像','聂耳铜像','优秀历史建筑乌鲁木齐南路176号','天钥桥路口袋公园'],
 'hongkou_literary':['李白烈士故居','沈尹默故居','日本海军特别陆战队司令部旧址','四川北路文化中心图书馆','上海多伦路地区海派文化馆(多伦生活广场店)']}

def table(headers,rows):
 clean=lambda x:str(x).replace('|','/').replace('\n','；')
 return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(clean,r))+' |' for r in rows])

def finalize():
 kb=load(FINAL);old=load(BASE);repo=POIRepository(FINAL);cost=load(OUT/'cost_report.json')
 protections={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in cost['protected_sha256'].items()}
 assert all(protections.values()),'Protected file changed'
 idx={p['id']:p for p in kb['pois']};old_ids={p['id'] for p in old['pois']}
 assert len(idx)==len(kb['pois']) and old_ids<=set(idx)
 for p in old['pois']:
  q=idx[p['id']]
  if p['id'] not in ('p7','p9','p13'):assert q==p
  else:assert q['route_role']==p['route_role'] and q['route_role_audit']==p['route_role_audit']
 new=[p for p in kb['pois'] if p['id'] not in old_ids]
 validated=[]
 for zone in ZONES:
  candidates=load(OUT/f'{zone}_prepared_shortlist.json')
  rows=load(OUT/f'{zone}_review.json')
  for row in rows['dispositions']:
   if row['decision']!='accept':continue
   c=next(c for c in candidates if c['candidate_id']==row['candidate_id'])
   s=load(OUT/f'{zone}_{c["candidate_id"]}_semantic.json')
   value=validate_subject_scope(validate_semantic_enrichment(s['output'],c,c['evidence_catalog'],repo.taxonomy),c)
   validate_role(value['route_role']);assert value['route_role']['confidence']!='low'
   assert boundary_status(c['coordinates'],ZonePipelineConfig.load(zone).polygon,150)=='inside_pilot'
   assert row['poi_id'] in idx;validated.append(row['poi_id'])
  rows['high_potential_unrescued']=[next(r for r in rows['dispositions'] if r['name']==n) for n in PRIORITY[zone] if any(r['name']==n and r['decision']!='accept' for r in rows['dispositions'])][:5]
  for row in rows['high_potential_unrescued']:
   if row['reason']=='strict_semantic_validation_or_provider_failure':row['missing_evidence']='Evidence already improved; missing a consistent, strictly evidence-cited semantic proposal. '+str(row['missing_evidence'])
  write(OUT/f'{zone}_review.json',rows)
 assert set(validated)=={p['id'] for p in new}
 cross=cross_modes(repo);write(OUT/'cross_zone_three_mode_regression.json',cross)
 west,modes=run_regression(repo);write(OUT/'west_bund_read_only_regression.json',dict(cases=west,three_modes=modes,frozen_node_count=13))
 tests=load(OLD/'full_test_report.json')
 tests_current=tests.get('successful') and tests.get('validation_fingerprint')==validation_fingerprint(load(BASE))
 direct=load(OUT/'unittest_command_result.json') if (OUT/'unittest_command_result.json').exists() else {'successful':False}
 failures=[dict(zone=z,name=r['name'],reason=r['reason'],validation_error=r['missing_evidence']) for z in ZONES for r in load(OUT/f'{z}_review.json')['dispositions'] if r['name'] in STRONG_UNRESOLVED and r['decision']!='accept']
 blockers=[]
 if failures:blockers.append(dict(code='semantic_proposal_reliability',explanation='Four evidence-backed high-potential nodes remain blocked by repeated unsupported citations or anchor/value inconsistency after two attempts. Cannot certify that obvious route supply is no longer systematically lost.',candidates=failures))
 if not all(r['passed'] for r in cross):blockers.append(dict(code='cross_zone_mode_regression',failed=[r for r in cross if not r['passed']]))
 if not tests_current or not direct.get('successful'):blockers.append(dict(code='full_tests_missing_failed_or_stale'))
 status='BLOCKED' if blockers else 'READY_FOR_PRODUCTION_PROMOTION'
 kb['metadata']['candidate_kb_status']=status;write(FINAL,kb)
 attempts=[]
 def attempt(s):
  if s.get('provider'):attempts.append(s['provider'])
  if s.get('prior_attempt'):attempt(s['prior_attempt'])
 for path in (OUT/'semantic_cache').glob('*.json'):attempt(load(path))
 ledger=RecallBudget(OUT/'semantic_call_ledger.json').rows
 cost.update(cache_hits_last_offline_pass=sum(load(OUT/f'{z}_{c["candidate_id"]}_semantic.json').get('cache_hit',False) for z in ZONES for c in load(OUT/f'{z}_prepared_shortlist.json') if (OUT/f'{z}_{c["candidate_id"]}_semantic.json').exists()),
  provider_usage_records=len(attempts),total_tokens=sum((a.get('usage') or {}).get('total_tokens',0) for a in attempts),
  first_calls_per_zone=dict(Counter(r['zone'] for r in ledger if not r['retry'])),retry_calls_per_zone=dict(Counter(r['zone'] for r in ledger if r['retry'])),
  distinct_first_enriched_nodes=18,duplicate_successful_call_deviation=1,
  deviation='One already successful Taipingqiao Park candidate was accidentally called again when Amap identity changed its cache key. Both calls retained/accounted; original successful output reused. Cache now resolves candidate_id before provider identity. No other successful node re-enriched.',
  targeted_historical_child_triage_checks=3,targeted_source_checks_lifetime=cost['targeted_retained_source_checks']+3,
  rejected_before_shortlist=sum(r['reason'] in ('internal_entity','production_duplicate','outside_boundary','generic_service','generic_retail','generic_food_drink') for z in ZONES for r in load(OUT/f'{z}_pool_screen.json')),
  cost_currency_amount='not computed; no verified unit price applied',semantic_hard_cap=30)
 assert cost['total_semantic_calls']<=30 and cost['retry_calls']<=6 and max(cost['first_calls_per_zone'].values())<=8
 write(OUT/'cost_report.json',cost)
 result=dict(status=status,blockers=blockers,candidate=str(FINAL.relative_to(ROOT)),final_poi_count=len(kb['pois']),accepted_new=len(new),
  zones=dict(Counter(p['walk_zone']['id'] for p in kb['pois'])),cross_mode_passed=sum(r['passed'] for r in cross),cross_mode_total=len(cross),
  tests=tests,direct_unittest=direct,tests_current=bool(tests_current),protected_sha256_checks=protections,
  west_bund_frozen=True,existing_22_roles_frozen=True,zone_expansion_passes=0,full_candidate_validation_ids=validated,
  semantic_validator_sha256=hashlib.sha256((ROOT/'src/poi_pipeline/semantic/validation.py').read_bytes()).hexdigest(),
  completed_at=datetime.now(timezone.utc).isoformat(),validation_fingerprint=validation_fingerprint(kb))
 write(OUT/'final_status.json',result)
 sections=[]
 def section(title,body):sections.append('## '+title+'\n\n'+body)
 section('1. 为什么需要 Recall Repair','D/E 的 1147 条 raw 记录最终新增 5 个节点；仅 3 / 2 / 3 个 prefilter survivors 无法证明现实缺少步行节点。F 阶段复用缓存，区内灰区再审，最终准入标准保持不变。')
 funnel=[(NAMES[z],)+tuple(load(OUT/f'{z}_funnel_after.json')[k] for k in ('raw_provider_records','deduplicated_canonical_candidates','prefilter_survivors','recall_shortlist','recall_enriched','new_accept','final_nodes')) for z in ZONES]
 section('2. Funnel Before → After',table(['Zone','Raw','Canonical','Old survivors','Shortlist','Understood cached/new','New accept','Final nodes'],funnel)+'\n\n全阶段计数、18 类 rejection/defer histogram 及原始原因位于 `data/poi_pipeline/recall/*_funnel_before.json`。Raw、source-ID unique 和 route canonical 不可相加；enriched 为候选数，API 次数另列。重复、内部对象、边界外和普通服务继续排除。历史原始 disposition 保留，不以当前规则改写过去结果。\n\n'+table(['Zone','Unique normalized','Boundary survivors','Production duplicates','Internal/child','Early reject','Old deferred','Old enriched','Old accepted'],[(NAMES[z],)+tuple(load(OUT/f'{z}_funnel_before.json')[k] for k in ('normalized_unique_records','boundary_survivors_unique','production_duplicates','internal_child_candidates','early_reject_count','deferred_count','enriched_count','accepted')) for z in ZONES]))
 section('3. Recall 规则与漏失原因','旧规则把缺少官方摘录直接视为不足，未先理解路线潜力；“临时政府旧址”被临时设施正则误伤。修复仅影响进入理解阶段：历史旧址例外、先审地图身份和独立体验、补少量直接证据。普通体育设施排除，但公园的 provider 体育休闲分类不会否定公园。Strict validator、taxonomy、角色价值标准均未改动。\n\n明确拆分 entity_stability 与 current_access_status。Closed、暂停开放、非营业时间不能推导临时或不存在；只有永久关闭、拆除、撤除等直接证据影响长期存在。淮海公园地图标签不能证明停建或不存在，已按稳定公园接受，实时开放状态 unknown，并保留原标签。公共街面/展陈体验范围仍需证据，这与此刻营业无关。')
 section('4. 每区 shortlist','\n\n'.join('### '+NAMES[z]+'\n\n'+table(['Rank','Candidate','Disposition','Reason'],[(i+1,r['name'],r['decision'],r['reason']) for i,r in enumerate(load(OUT/f'{z}_review.json')['dispositions'])]) for z in ZONES)+'\n\n已确认的春广场、世界文豪广场、梅园为 parent 内部对象；保留在 pool screen，最终 shortlist 排除，不调用模型。人民公园维持原 defer，不扩边界。')
 section('5. 新增 accepted POIs',table(['ID','Zone','Name','Role'],[(p['id'],NAMES[p['walk_zone']['id']],p['name']['zh'],p['route_role']['primary']) for p in new]))
 section('6. Route Role 与 Composition',table(['Zone','Anchor before→after','Supporting before→after','Transition before→after'],[(NAMES[z],)+tuple(str(Counter(p['route_role']['primary'] for p in old['pois'] if p['walk_zone']['id']==z)[role])+' → '+str(Counter(p['route_role']['primary'] for p in kb['pois'] if p['walk_zone']['id']==z)[role]) for role in ('anchor','supporting_stop','transition_stop')) for z in repo.zone_order])+'\n\n22 个 existing role audit 冻结；未将 supporting 升为 anchor，也未为凑站数改变 composition policy。新增角色理由和 eligible/confidence 在 candidate 的 route_role 中。')
 section('7. Coverage Before → After','\n\n'.join('### '+NAMES[z]+'\n\n'+table(['Group','Changed tag frequencies'],[(g,', '.join(t+': '+str(d['before']['coverage'][g]['frequency'].get(t,0))+'→'+str(n) for t,n in d['after']['coverage'][g]['frequency'].items() if n!=d['before']['coverage'][g]['frequency'].get(t,0)) or 'unchanged') for g in ('interest_tags','experience_tags','culture_tags')]) for z in ZONES for d in [load(OUT/f'{z}_coverage_comparison.json')]))
 section('8. Duration Sweep Before → After',table(['Zone','Before 120/150/180','After 120/150/180'],[(NAMES[z],'/'.join(str(len(r['selected_stops'])) for r in d['duration_sweep']['before']),'/'.join(str(len(r['selected_stops'])) for r in d['duration_sweep']['after'])) for z in ZONES for d in [load(OUT/f'{z}_regression_comparison.json')]])+'\n\n老城 short-route limitation remains：2 / 2 / 3。武康 3 / 4 / 5 不变，新增改善选择多样性；虹口 180 分钟增加一站。未插 filler，未修改 route scoring。')
 section('9. 原六用例与跨区 Three-mode',table(['Zone','Before passed','After passed'],[(NAMES[z],str(sum(r['passed'] for r in d['before']))+'/6',str(sum(r['passed'] for r in d['after']))+'/6') for z in ZONES for d in [load(OUT/f'{z}_regression_comparison.json')]])+f'\n\n跨四区三模式：{sum(r["passed"] for r in cross)}/12。West Bund 只读原回归通过预期，纯 art/no museum 的 composition_failure 是原明确预期。老城 non_museum 短路线仍不足三站，未隐藏。每例记录 stop count、matched tags/relevance、negative preferences、role mix、time utilization、最大单段估算距离与 zone isolation。地理距离为代表点估算，无真实地图 routing。')
 patches=load(OUT/'coordinate_patches.json')
 section('10. 定向坐标核验',table(['ID','Name','Old GCJ-02 [lat,lng]','New','Offset m','Confidence'],[(r['poi_id'],r['name'],r['old_coordinate'],r['new_coordinate'],r['distance_m'],r['confidence']) for r in patches])+'\n\n'+ '\n\n'.join(r['poi_id']+'：'+r['reason']+' '+ ' '.join('['+('高德' if 'amap' in u else '权威来源')+']('+u+')' for u in r['sources']) for r in patches)+'\n\n均仅写入 recall candidate；张园门牌差异显式保留，代表点不是实际入口。三点都在原 boundary/review margin 内。')
 section('11. Remaining Human Review','本轮没有把证据不足或模型技术失败推给人工产品判断；最终 human_review 为空，各区 ≤5。确定的身份/独立体验不足继续 defer；旧人民公园 defer 保持。技术阻断另列，未伪装为普通 ambiguity。')
 section('12. 未救回的高潜力候选','\n\n'.join('### '+NAMES[z]+'\n\n'+table(['Name','Reason','Missing evidence / contract'],[(r['name'],r['reason'],r.get('missing_evidence') or 'independent evidenced visit scope') for r in load(OUT/f'{z}_review.json')['high_potential_unrescued']]) for z in ZONES))
 section('13. 调用成本',table(['Metric','Phase 2.5F'],[(k,cost[k]) for k in ('reused_cached_records','targeted_retained_source_checks','targeted_source_checks_lifetime','targeted_coordinate_provider_checks','first_calls','retry_calls','total_semantic_calls','cache_hits_last_offline_pass','total_tokens','accepted','deferred','rejected','rejected_before_shortlist')])+ '\n\n19 首次调用记录对应18个不同候选，另5次有实质补证的重试，共24/30；各区首次记录为 '+str(cost['first_calls_per_zone'])+'。明确偏差：'+cost['deviation']+'\n\n现有 shortlist 保留31项来源检查，早期3项内部对象归属核验计入 lifetime34；另3次坐标详情。Targeted search 无可靠结果的检查保留在 defer note，不宣称所有网页查找均有成功来源。来源数指被核验的候选来源，不是搜索引擎返回结果条数。D/E三区语义调用13，另intent smoke3；West Bund旧pilot158调用/929709 tokens，本轮未重跑。货币成本未凭未核验单价估算。Offline最后重放仅cache hit，无新增API。')
 section('14. 完整测试',f'`python -m unittest discover -s tests -t . -q`：{direct}\n\n`python -m scripts.verify_all_zones`：{tests["tests_run"]} tests，{tests["failures"]} failures，{tests["errors"]} errors。当前源码指纹有效：{bool(tests_current)}。新增覆盖预算、身份变化复用缓存、闭园与消失区别、历史临时政府、冻结ID/角色/边界、six-case请求一致与硬约束。')
 section('15. 最终 POI 数量',str(len(kb['pois']))+' nodes；'+str(result['zones'])+'。West Bund13及p36–p43字节内容对应对象不变。没有新增 parent 内拆分节点。')
 section('16. Exact Candidate File','`data/pois_phase2_5_recall_candidate.json`\n\n显式 CLI KB 名：`phase2_5_recall_candidate`；默认仍是production。旧all-zone candidate、pilot candidate、production、zone config全部通过原SHA校验。Evidence checks、call ledger、cache原始输出、funnel、coverage和regression JSON位于`data/poi_pipeline/recall/`。所有短摘录、URL和retrieved_at已逐候选保存于`*_evidence_checks.json`。')
 section('17. Promotion Recommendation',f'**PHASE 2.5F STATUS: {status}**\n\n'+ ('未证明高潜力节点不再被系统性漏掉：团中央机关旧址、徐家汇公园、李白烈士故居、沈尹默故居已有直接来源，第二次提案仍因unsupported tags/citation或anchor/value矛盾被严格校验拒绝。它们不是当前闭馆问题，也不是待人工决定的普通 ambiguity。模型提案与证据引用可靠性是本阶段明确技术 blocker；各节点两次尝试已用尽，禁止第三次或标签校验绕过。现48-node候选可人工查看，但不推荐直接promotion。' if failures else '通过V1准入；短路线限制明确保留。')+'\n\n停在candidate与报告；不覆盖production，不开始Phase3。')
 report='# ShanghaiTrace Phase 2.5F — Recall Repair Report\n\n'+result['completed_at']+'\n\n'+'\n\n'.join(sections)+'\n'
 (ROOT/'docs/history/phase2_5/PHASE2_5F_RECALL_REPAIR_REPORT.md').write_text(report,encoding='utf-8')
 print(json.dumps({k:result[k] for k in ('status','final_poi_count','accepted_new','cross_mode_passed','tests_current')},ensure_ascii=True))
 return result

if __name__=='__main__':finalize()
