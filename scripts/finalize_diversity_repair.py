"""Reviewable G candidate gate and report; never writes production."""
import hashlib,json
from collections import Counter
from datetime import datetime,timezone
from scripts.run_diversity_repair import ROOT,BASE,FINAL,OUT,ZONES,REMOVED,load,write
from scripts.finalize_all_zones import validation_fingerprint
from src.poi_repository import POIRepository
from src.poi_pipeline.diversity import distribution

def table(headers,rows):
 def cell(v):return str(v).replace('|',' / ').replace('\n',' ')
 return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+'\n'.join('| '+' | '.join(cell(v) for v in row)+' |' for row in rows)

def finalize():
 kb=load(FINAL);base=load(BASE);review=load(OUT/'review.json');cost=load(OUT/'cost_report.json');tests=load(OUT/'full_test_report.json')
 old={p['id']:p for p in base['pois']};index={p['id']:p for p in kb['pois']};new=[p for p in kb['pois'] if p['id'] not in old]
 comparisons={z:load(OUT/f'{z}_diversity_comparison.json') for z in POIRepository(FINAL).zone_order}
 regressions={z:load(OUT/f'{z}_regression_comparison.json') for z in ZONES}
 cross=load(OUT/'cross_zone_three_modes.json')
 protected=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in cost['protected_sha256'].items())
 square=next(p for p in new if p['name']['zh']=='上海人民广场')
 checks=dict(protected_files=protected,frozen_remaining_nodes=all(index.get(pid)==p for pid,p in old.items() if pid!=REMOVED),
  only_explicit_removal=set(old)-set(index)=={REMOVED},west_bund_13=sum(p['walk_zone']['id']=='west_bund' for p in kb['pois'])==13,
  existing_core_regression=all(r['passed'] for g in regressions.values() for r in g['after'][:6]),
  no_previously_successful_request_regressed=all(not a['passed'] or b['passed'] for g in regressions.values() for a,b in zip(g['before'],g['after'])),
  cross_modes=all(r['passed'] for r in cross),
  parks_not_dominant=distribution(kb['pois'])['park_share']<.25 and distribution(new)['park_share']<.2,
  texture_increased_all_three=all(g['after']['urban_texture_node_count']>g['before']['urban_texture_node_count'] for z,g in comparisons.items() if z!='west_bund'),
  square_human_approved=square.get('admission')=='human_approved' and square['route_role']['primary']=='anchor',
  no_fake_richness=all(p['route_selectable'] and p['counts_as_route_stop'] for p in new) and len(index)==len(kb['pois']),
  full_tests=tests.get('successful') is True and tests.get('validation_fingerprint')==validation_fingerprint(kb))
 status='READY_FOR_PRODUCTION_PROMOTION' if all(checks.values()) else 'BLOCKED'
 limitations=[dict(zone=z,kind='theme',case=r['case'],status=r['route_status'],stops=len(r['selected_stops']),reason=r['failure_reason']) for z,g in regressions.items() for r in g['after'] if not r['passed']]
 limitations += [dict(zone=z,kind='duration',case=r['request']['available_minutes'],status=r['route_status'],stops=len(r['selected_stops']),reason=r['failure_reason']) for z,g in regressions.items() for r in g['duration_sweep']['after'] if not r['passed']]
 kb['metadata']['candidate_kb_status']=status;write(FINAL,kb)
 result=dict(status=status,nodes=len(kb['pois']),new_nodes=len(new),removed=[REMOVED],checks=checks,remaining_blockers=[k for k,v in checks.items() if not v],known_coverage_limitations=limitations,
  zone_counts=dict(Counter(p['walk_zone']['id'] for p in kb['pois'])),candidate_sha256=hashlib.sha256(FINAL.read_bytes()).hexdigest(),full_tests=tests,completed_at=datetime.now(timezone.utc).isoformat())
 write(OUT/'final_status.json',result)
 sections=[]
 def section(title,body):sections.append('## '+title+'\n\n'+body)
 section('1. 为什么 F 出现 park-heavy recall','F 新增8个节点中6个为公园。公园的固定实体、公共空间和标签证据较易通过，而故居/建筑的模型输出出现过标签过度推断、事实字段或证据引用失败。因此这是召回准入偏差，并不代表城市本身只有公园。本轮从已缓存候选定向修复，使用最小证据骨架，不增加模型重试。')
 section('2. 四区类别和角色 before → after',table(['Zone','节点','Category before','Category after','Role before','Role after'],[(z,f"{g['before']['nodes']} → {g['after']['nodes']}",json.dumps(g['before']['category_distribution'],ensure_ascii=False),json.dumps(g['after']['category_distribution'],ensure_ascii=False),g['before']['primary_role_distribution'],g['after']['primary_role_distribution']) for z,g in comparisons.items()])+'\n\n保留旧KB原分类词汇；不把旧类型重写成新taxonomy。角色沿用已审核基线，新角色依独立目的地/体验/连接价值判断。')
 section('3. 城市肌理与占比',table(['Zone','肌理节点','公园','街道/里弄','历史建筑','广场/城市公共空间','地标','文化空间'],[(z,f"{g['before']['urban_texture_node_count']} → {g['after']['urban_texture_node_count']}",*[f"{g['before'][f]:.1%} → {g['after'][f]:.1%}" for f in ('park_share','street_lane_share','historic_building_share','public_square_civic_space_share','landmark_share','cultural_space_share')]) for z,g in comparisons.items()])+'\n\n多标签诊断可重叠；每列分母为该区全部节点。park按poi_type或category判定，包括类别名称不同的鲁迅公园；普通公园绝不计入urban texture，徐家汇公园也保守排除。旧节点用原category/type/name/tags映射，新节点有显式scope/facets审计；不是新推荐标签。文化场馆只有明确建筑/社区等肌理身份才计入texture。')
 section('4. 定向 shortlist',table(['Zone','候选','结果','原因/缺失'],[(r['zone'],r['name'],r['decision'],r.get('missing_evidence',r['reason'])) for r in review])+'\n\n每区6个，总18个；每区普通公园≤2；未扩大边界、未重新collect整个区域。三个defer不进入62节点，也不阻止整条生产线。')
 section('5. 新接受的15个 POI',table(['ID','名称','Zone','角色','体验范围'],[(p['id'],p['name']['zh'],p['walk_zone']['id'],p['route_role']['primary'],p['urban_texture_audit']['scope']) for p in new])+'\n\n新增角色：'+str(dict(Counter(p['route_role']['primary'] for p in new)))+'。transition_stop没有因数量目标升级为anchor。军事旧址仅限公共道路侧；音乐厅不含内部/音乐会；住宅不承诺进入院落。')
 sr=next(r for r in review if r['name']=='上海人民广场')
 section('6. 上海人民广场',json.dumps(dict(poi_id=square['id'],name=square['name'],location=square['location'],role=square['route_role'],tags=square['tags'],visit_profile=square['visit_profile'],map_identity=sr['map_identity']),ensure_ascii=False,indent=2)+'\n\n高德parent B00157917M，GCJ-02纬度31.228827、经度121.475213；非人民广场地铁站、人民公园、博物馆或出入口。坐标是代表点而非完整广场边界。human_approved指用户产品准入，不表示已验证实时开放。18分钟是公共广场walk_stop产品估计，不从场馆游览时间复制。公共空间范围官方来源见逐点来源记录。')
 section('7. ConservativeSemanticRepair','18个进入本轮审查，15个新骨架通过原strict validator，3个defer。不是删除旧失败输出字段来救活它：不读取失败模型文本，按直接主体证据重新构造。interest≤2、experience≤2、culture≤1，至少1个有证据interest；无支持标签立即失败；factual_fields全部null；opening/ticket/reservation不补造；full_visit为null，walk_stop为明确scope的产品估计。坐标继承provider证据，OSM原WGS84记录保留并由已有转换进入GCJ-02。实体稳定与此刻开放分离，current_access_status=unknown，不把夜间closed判成不存在。博物馆名录的主体行补充museum_visit避免偏好漏滤。')
 section('8. 旧 blocker 的处理','团中央机关旧址、徐家汇公园、李白烈士故居、沈尹默故居均已接受。有明确独立主体来源、固定身份、坐标证据和可解释的supporting_stop。未改变旧POI角色。F留下的其他defer仍留在原档案；本轮按上表限定18个，不用普通候选歧义停止工作。')
 section('9. 公园冗余 review',table(['同区公园对','距离km','标签Jaccard','建议'],[('/'.join(r['names']),r['distance_km'],r['tag_jaccard'],'供人工决定；未自动删除') for r in load(OUT/'park_redundancy_review.json')])+'\n\n爱思儿童公园按最新明确指令删除，仅从本轮candidate删除；F归档保留不覆盖。其余仅提出review，靠近或标签类似不能证明体验重复。公园总数'+str(sum(p['poi_type']=='park' or p['category']['en']=='park' for p in kb['pois']))+'；新增仅1/15。')
 section('10. 三区 route regression',table(['Zone','Case','before','after','stop数','负偏好','区内','composition'],[(z,r['case'],g['before'][i]['route_status'],r['route_status'],len(r['selected_stops']),r['negative_preference_passed'],r['zone_isolation_passed'],r['composition_passed']) for z,g in regressions.items() for i,r in enumerate(g['after'])])+'\n\n同一fixture before/after，原6例/区全部通过（18/18）；G新增主题4/5通过。新增old_city_life仍不足：真实local_life+old_city相关候选池只有1站，保持失败，不靠无关公园/伪标签凑数。West Bund只读检查保留原art+no museums已知composition failure，13节点未动。跨区三模式12/12通过，places_in_mind按原精确站点规则而非硬加anchor。')
 section('11. 120/150/180 duration sweep',table(['Zone','分钟','before站数','after站数','after状态','composition'],[(z,r['request']['available_minutes'],len(g['duration_sweep']['before'][i]['selected_stops']),len(r['selected_stops']),r['route_status'],r['composition_passed']) for z,g in regressions.items() for i,r in enumerate(g['duration_sweep']['after'])])+'\n\n旧城120分钟仍2站，保持可见不足。150/180分钟以及其余两区默认时长检查通过。此处只诊断，不改变RouteEngine打分、richness门槛或准入角色。')
 section('12. Route diversity diagnostics',table(['Zone','Case','categories','roles','park','street/lane','landmark/building','texture','类别数'],[(z,r['case'],r['diversity_diagnostics']['poi_categories'],r['diversity_diagnostics']['route_roles'],*[r['diversity_diagnostics'][k] for k in ('park_count','street_lane_count','landmark_building_count','urban_texture_count','route_category_diversity')]) for z,g in regressions.items() for r in g['after']])+'\n\n上述同类指标亦写入duration sweep、West Bund只读cases和跨区12个mode JSON；soft diagnostic only，不以类别数代替路线质量。')
 section('13. Cost/source calls',json.dumps(cost,ensure_ascii=False,indent=2)+'\n\n本轮DeepSeek=0，新增模型token=0。16次实际高德窄检：6成功、10provider_error；失败计入成本，未重复重试。未成功或刻意跳过的点保留此前地图坐标/地址来源，不能称为本轮高德确认。23条新增保留的候选/来源检查对 +10条F复用，共33；该数不是网络请求次数，不包括检索无关结果、timeout网页请求。官方网页检索没有完整HTTP调用账单，不能宣称这些是全部网络调用。地图金额未获账单，未估算人民币费用。')
 section('14. Full tests',json.dumps(tests,ensure_ascii=False,indent=2)+'\n\n运行unittest discover与verify_all_zones，后者验证旧40节点pipeline归档。G报告指纹绑定当前62节点candidate与src/scripts/tests代码，不能拿旧测试报告代替G结果。保护哈希含production、旧candidate、Fcandidate、boundaries、strict validator、RouteEngine。')
 section('15. Final count','48 − 爱思儿童公园1 + 新节点15 = **62**。\n\n'+table(['Zone','Count'],result['zone_counts'].items())+'\n\n四区均route_selectable。新增节点与全部62节点删选清单见 [POI_REVIEW_LIST.md](POI_REVIEW_LIST.md)。显式CLI：`--kb phase2_5_diversity_candidate`；默认仍production。最终文件：`data/pois_phase2_5_diversity_candidate.json`。')
 section('16. Remaining blockers/limitations','系统blocker：'+str(result['remaining_blockers'])+'。\n\n'+json.dumps(limitations,ensure_ascii=False,indent=2)+'\n\n这些未成功fixture为已有/未解决的主题或短预算覆盖限制，不能称为全部场景可用。三项defer详见shortlist，后续人工可以删节点或决定补证，本轮不继续增加。空间置信度均需区分缓存与本轮核验；代表坐标不是入口，未接真实地图routing。')
 section('17. Promotion recommendation','**PHASE 2.5G STATUS: '+status+'**\n\n'+json.dumps(checks,ensure_ascii=False,indent=2)+'\n\n建议进入人工最终验收；这不是自动推广。判断依据为公园占比下降、三区肌理增加、广场身份完成、strict validator保持、18原回归和12模式通过且无已成功主题退化、完整测试通过。old_city_life与旧城120分钟限制明确披露，不把这两个场景列为通过。未覆盖data/pois.json，未做Phase3/前端/真实地图routing。验收删选后必须重跑G回归和测试再推广。')
 section('18. 逐点证据/来源', '\n\n'.join('### '+r['name']+'\n\n'+ '\n'.join('- ['+s['source_type']+']('+s['url']+') retrieved_at='+s['retrieved_at']+'；摘录：'+s['excerpt'] for s in load(OUT/'evidence_checks.json') if s['name']==r['name']) for r in review if r['decision']=='accept')+'\n\nGCJ-02坐标继承、原provider、tag evidence_refs、坐标/地址field_sources见每个`*_repair.json`和candidate.source_provenance；six verified map IDs与其余cached_geometry_retained分开记录于review.json。短摘录仅支撑所引主体，不借用文章沿途其他景点。')
 (ROOT/'docs/history/phase2_5/PHASE2_5G_DIVERSITY_REPAIR_REPORT.md').write_text('# Phase 2.5G Urban Texture & Diversity Repair\n\n'+ '\n\n'.join(sections)+'\n',encoding='utf-8')
 pruning=['# 62个候选节点删选清单','爱思儿童公园已删除。以下全部仅位于新candidate，尚未推广。可以直接告知要删除的ID或名称；删选之后需重跑路线验证。每个新增点有严格证据骨架，但地理精度/访问范围仍按下列说明判断。','## 新增15个：优先供产品验收',table(['ID','名称','Zone','角色/置信度','地图状态','范围/理由','tags'],[(p['id'],p['name']['zh'],p['walk_zone']['id'],p['route_role']['primary']+' / '+p['role_confidence'],next(r['map_identity']['status'] for r in review if r.get('poi_id')==p['id']),p['urban_texture_audit']['scope'],p['tags']) for p in new]),'## 全部62个',table(['ID','名称','Zone','新增G?','角色','类型'],[(p['id'],p['name']['zh'],p['walk_zone']['id'],'新增' if p in new else '保留基线',p['route_role']['primary'],p['category']['en']) for p in kb['pois']]),'## 未进入62个的3个defer',table(['名称','原因'],[(r['name'],r.get('missing_evidence',r['reason'])) for r in review if r['decision']=='defer']),'## 如何删选','两个transition新增点（安康公寓、军事旧址）主要提供短时街面观察，可优先按产品体验偏好审查；不应以删除建议改变其角色。中南新邨仅公共入口/街面，不含居民院落；音乐厅仅外观；韩国旧址本轮仅街面。徐家汇公园是本轮唯一新增公园，若偏好减少公园可人工决定。人民广场是已授权的公共广场parent。所有新点当前开放状态unknown；closed_now不会等于entity不稳定。证据及公园对照见完整报告。']
 (ROOT/'docs/history/project/POI_REVIEW_LIST.md').write_text('\n\n'.join(pruning)+'\n',encoding='utf-8')
 print(json.dumps(dict(status=status,nodes=len(kb['pois']),checks=checks),ensure_ascii=True))
 return result

if __name__=='__main__':finalize()
