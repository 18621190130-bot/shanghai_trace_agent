"""Offline bounded Phase 2.5B repair. No collection, LLM, promotion or route run."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.poi_repository import POIRepository
from src.poi_pipeline.semantic.consolidation import RouteNodeConsolidator
from src.poi_pipeline.semantic.repair_review import build_review,LOW_VALUE
from src.poi_pipeline.semantic.repair_policy import historical_failures,compact_evidence


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def report(rows,registry,stats):
    lines=['# PHASE 2.5B REPAIR REPORT','','本次为离线、定向、可复现的候选层修复；未开始 Phase 2.5C，未重新 collection，未整批 enrichment。','',
           '## 1. Before repair','', 'Phase 2.5A canonical 61；用户分组后 58；校验结果 55、失败 3；Recommended Accept 0 / Needs Review 43 / Reject 15。','',
           '## 2. Production identity matches','', '| Production | Name | Source candidate records | Primary role |', '| --- | --- | ---: | --- |']
    for r in rows:
        if r['identity_status']=='existing_production':
            lines.append(f"| {r['production_match']} | {r['name']} | {len(r['member_candidate_ids'])} | {r['primary_role']} |")
    lines+=['','匹配综合精确中英文/别名、坐标距离、门牌、已知官方页面及 source identity。仅名字相似或同品牌不作为新节点：possible_duplicate。生产内容与访问时长作为已知结构化证据保留，不被旧 candidate 的信息空缺覆盖。','',
            '## 3. Duplicates merged','']
    for r in rows:
        if r['node_id'] in ('route:art_center','route:dome','route:skate','route:runway','route:photography'):
            lines.append(f"- **{r['name']}**：{len(r['member_candidate_ids'])} 条当前 candidate 归入一个节点。{r['consolidation_reason']}")
    lines+=['','## 4. Parent/child entities removed from route selection','',
            'A/B1/N/D 馆、TANK 油罐几何、油罐公园既有 walk_stop 范围、南浦站场地和 Gate M 内部实体保留来源资料，child.route_selectable=false。没有按 provider ID 生成 stops。','',
            '源实体登记表单独保存，不进入主审核表。疑似内部建筑与疑似重叠公园没有强行确认身份，仍在主表中标为 possible_duplicate。','',
            '## 5. Final route-node candidate count','',
            f"主审核表 **{len(rows)}** 行：已有 production 审核 **{stats['production_audit_count']}**、新增路线节点候选 **{stats['new_candidate_count']}**、possible_duplicate **{stats['possible_duplicate_count']}**、unresolved **{stats['unresolved_count']}**。",
            f"结构上可作为新增 stop 的提议 **{stats['new_route_selectable_count']}**；这只是 staging 标记，尚未进入 Route Engine。非可选记录与内部实体不增加 stop count。",'',
            '## 6. Existing production POIs needing only route-role audit','',
            'p5 / p28 / p29 / p30 / p31 各保留一次，admission_scope=production_audit_only、counts_as_new_stop=false。角色提议基于既有内容、full_visit 产品估时与 walk_stop 范围，非地图类别或知名度。五处均提议 anchor，同时可用 supporting_stop 访问方式；不新增 transition 节点。','',
            'TANK 的 outdoor walk_stop 有 production 明确支持：外部油罐、工业遗产和滨江公共空间；这不等于证实独立户外艺术作品。原来失败的两条油罐对象归入内部实体，已无单独 enrichment 义务；龙美术馆失败行归回 p5 审核，已知 production 内容完整保留。','',
            '## 7. Recommended Accept / Needs Review / Reject','',
            f"全表：**{stats['decisions']}**；排除既有 production 审核后的候选决定：**{stats['new_admission_decisions']}**。",
            'recommended_accept 仅是建议人工接受此候选层表达，仍非 promotion。route_selectable 表示独立节点资格，不表示已导入或已批准进入路线。','',
            '| Name | Identity / production | Selectable | Category | Role / confidence | Decision |',
            '| --- | --- | --- | --- | --- | --- |']
    for r in rows:
        category=r['category'] if isinstance(r['category'],str) else r['category']['en']
        lines.append(f"| {r['name']} | {r['identity_status']} / {r['production_match'] or '—'} | {r['route_selectable']} | {category} | {r['primary_role']} / {r['role_confidence']} | {r['decision']} |")
    lines+=['','## 8. Tags changed after repair','',
            '| Node | Removed from previous effective tags | Added / restored from evidence | Supported tags now |',
            '| --- | --- | --- | --- |']
    for r in rows:
        removed=[t for g in r['tag_changes'].values() for t in g['removed']]
        added=[t for g in r['tag_changes'].values() for t in g['added']]
        tags='; '.join(','.join(r[g]) or '—' for g in ('interest_tags','experience_tags','culture_tags'))
        lines.append(f"| {r['name']} | {', '.join(removed) or '—'} | {', '.join(added) or '—'} | {tags} |")
    lines+=['','- 滑板公园：parks 来自公园分类；滨江身份支持 waterfront/riverside_walk；市文旅局明确描述“本地滑板社群的重要聚集地”，支持 social_observation/public_life。移除仅由泛景观词支撑的 photogenic。',
            '- 跑道公园：官方原文支持航空历史、原跑道转用、街道和公园系统，所以保留 history/adaptive_reuse/street_scene。内部水系不等于黄浦江步道，移除 waterfront/riverside_walk；“现代社会”不是 modern_city 的可靠依据。',
            '- 塔吊广场和北票码头塔吊：不以工业设备或同段文字中的美术馆推导 art。无尽影院由 OSM tourism=artwork、installation 支持公共艺术线索，但公共可达与稳定性未确认。',
            '- 未新增 taxonomy，未用覆盖率修正任何标签。生产既有标签仅恢复/保留为 production 事实快照，不声称本次重新外部验证了全部标签。','',
            '## 9. Route roles changed after repair','', '| Node | Before roles | Proposed role | Evidence-based reason |', '| --- | --- | --- | --- |']
    for r in rows:
        lines.append(f"| {r['name']} | {', '.join(r['role_changes']['before'])} | {r['primary_role']} | {r['route_role']['reason']} |")
    lines+=['','## 10. Key ambiguous POIs still needing human decision','']
    for r in rows:
        if r['decision']=='needs_review' and r['identity_status']!='existing_production':
            lines.append(f"- **{r['name']}**：{' '.join(r['reason'])}")
    lines+=['','专项低价值检查：','']
    for item in stats['low_value_review']:
        lines.append(f"- {item['name']}：{item['decision']}；{item['reason']}")
    lines+=['','## 11. semantic_validation_error root causes','',
            f"历史失败尝试总数 **{stats['failure_analysis']['total_failed_attempts']}**；每次按首要类别归类：`{stats['failure_analysis']['primary_categories']}`。",
            '- 模型用地点名/类别外推 architecture、photogenic、城市更新等；同一段列举多个地点，引用存在却不一定支持当前地点。',
            '- EvidenceBundle 对同一内容按多个组重复展现；原来只反馈首个不支持标签，导致连续试错。',
            '- 自然语言解释混入应为原文摘录的 factual slots；anchor 与 independent_destination_value 不一致。',
            '- 原先把 stability unknown、缺少精确坐标和既有 production 身份问题混为新候选语义问题。',
            '修复使用显式身份/父子关系和针对特定片段的证据选择；保留原严格 validator，不再从反复生成中碰运气。TargetedRepair prompt 要求 uncertain→omit/null；重复证据去重但保留 also_supported_by 引用。','',
            '## 12. Retry reduction','',
            f"本 Repair：**0 外部采集请求、0 DeepSeek 请求、0 retry**。历史调用 {stats['historical_api_attempts']}，不将离线审核宣称为模型错误率改善。",
            '三条失败通过 production 身份恢复/内部实体收敛解决，未重新请求成功的55条。选中的重点节点采用明确标注的确定性审核提议；其余已通过结果复用。',
            'TargetedRetryPolicy 只允许 failed / identity_changed / merged / role_ambiguous / tag_reconciliation_required；最多两次。第二次仅语法/schema、单个可省略字段或证据实质改善可重试。证据不足立即 needs_review/reject，不请求模型。',
            f"去重前证据 atoms：{stats['evidence_atoms_before']}；语义输入精简后：{stats['evidence_atoms_compact']}（原 provenance 未删除）。",'',
            '## 13. Tests','', stats['test_result'],
            '复现：`python -m unittest discover -s tests -t . -q`；离线导出：`python scripts/repair_west_bund.py`。','',
            '## 14. Files modified','',
            '- 新增 `semantic/identity.py`、`consolidation.py`、`repair_policy.py`、`repair_review.py`。',
            '- 新增 `scripts/repair_west_bund.py`、`tests/test_poi_repair.py`、`docs/phases/PHASE2_5B_REPAIR.md`。',
            '- 新增 repaired review / route nodes / source entity registry / identity matches / run metadata；新增本报告。',
            '- README 增加修复报告入口。既有 validator、production、路线/意图/澄清/组合代码和旧阶段产物未改动。',
            f"受保护文件 SHA256 全部保持一致：{stats['protected_unchanged']}。",'',
            '## 15. Exact next-step recommendation','',
            '人工先验收艺术中心整体、穹顶双访问范围、滑板公园、跑道公园与摄影艺术中心的节点边界；再确认塔吊广场/北票码头塔吊关系、2555号建筑是否内部实体、运动公园是否与滑板公园重叠。确认滑板公园入口与跑道公园试点范围后，才讨论后续阶段；本轮不进行 promotion。','',
            'PHASE 2.5B REPAIR STATUS: '+stats['status'],'','等待人工验收。']
    return '\n'.join(lines)+'\n'


def main():
    root=ROOT/'data/poi_pipeline/semantic'
    output=root/'repair'
    protected=[ROOT/'data/pois.json',ROOT/'src/poi_pipeline/semantic/validation.py',
               root/'west_bund_review.json',root/'west_bund_prepared_candidates.json',
               ROOT/'src/route_engine.py',ROOT/'src/intent_models.py',ROOT/'src/intent_schema.py',
               ROOT/'src/semantic_expansion.py',ROOT/'src/clarification.py',ROOT/'src/route_quality.py',ROOT/'src/route_entry.py']
    protected+=list((ROOT/'data/poi_pipeline/canonical').glob('*.json'))
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    before=json.loads((root/'west_bund_review.json').read_text(encoding='utf-8'))
    candidates=json.loads((root/'west_bund_prepared_candidates.json').read_text(encoding='utf-8'))
    repo=POIRepository()
    nodes,registry,identities=RouteNodeConsolidator(repo).consolidate(candidates,before)
    rows=build_review(nodes,registry,before,repo)
    assert {r['production_match'] for r in rows if r['identity_status']=='existing_production'}=={'p5','p28','p29','p30','p31'}
    memberships=[cid for r in rows for cid in r['member_candidate_ids']]
    assert len(memberships)==len(set(memberships))==len(candidates)
    assert all(not entity['route_selectable'] for entity in registry)
    assert all(not r['counts_as_new_stop'] for r in rows if r['identity_status']=='existing_production')
    for node in nodes:
        row=next(r for r in rows if r['node_id']==node['node_id'])
        node.update({key:row[key] for key in ('route_selectable','counts_as_new_stop','parent_node','identity_status','decision','route_role')})
    write(output/'west_bund_review_repaired.json',rows)
    write(output/'west_bund_route_nodes.json',nodes)
    write(output/'west_bund_source_entities.json',registry)
    write(output/'west_bund_production_identity_matches.json',identities)
    unchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest for p,digest in hashes.items())
    test_record=output/'test_result.json'
    test_result=json.loads(test_record.read_text(encoding='utf-8')) if test_record.exists() else dict(passed=False,summary='Tests pending')
    stats=dict(before=dict(canonical=58,needs_review=43,reject=15),final_review_count=len(rows),
        production_audit_count=sum(r['identity_status']=='existing_production' for r in rows),
        new_candidate_count=sum(r['identity_status']=='new_candidate' for r in rows),
        possible_duplicate_count=sum(r['identity_status']=='possible_duplicate' for r in rows),
        unresolved_count=sum(r['identity_status']=='unresolved' for r in rows),
        new_route_selectable_count=sum(r['route_selectable'] and r['admission_scope']=='new_route_node' for r in rows),
        decisions=dict(Counter(r['decision'] for r in rows)),new_admission_decisions=dict(Counter(r['decision'] for r in rows if r['admission_scope']=='new_route_node')),
        failure_analysis=historical_failures(before),historical_api_attempts=sum(len(r['run']['attempts']) for r in before),
        evidence_atoms_before=sum(len(n['evidence_catalog']) for n in nodes),evidence_atoms_compact=sum(len(compact_evidence(n['evidence_catalog'])) for n in nodes),
        protected_unchanged=unchanged,protected_hashes=hashes,test_result=test_result['summary'],
        low_value_review=[dict(name=r['name'],decision='reject',reason='empty validated tags and no independent City Walk evidence; internal entities stay nonselectable') for r in before if r['name'] in LOW_VALUE],
        status='PASS' if unchanged and test_result['passed'] else 'BLOCKED')
    write(output/'west_bund_repair_run.json',stats)
    (ROOT/'docs/history/phase2_5/PHASE2_5B_REPAIR_REPORT.md').write_text(report(rows,registry,stats),encoding='utf-8')
    print(json.dumps({k:stats[k] for k in ('final_review_count','production_audit_count','new_route_selectable_count','decisions','protected_unchanged','status')},ensure_ascii=True))


if __name__=='__main__':main()
