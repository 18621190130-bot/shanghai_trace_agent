"""Generate a human-review report directly from the staging dataset."""
from collections import Counter


def render_report(rows, preview, run, lineage):
    counts = Counter(r['decision'] for r in rows)
    lines = ['# PHASE 2.5B REPORT', '',
        '状态：Evidence-Grounded Semantic Enrichment 完成，等待人工验收。accept 仅代表建议审核；没有正式入库。', '',
        f"Phase 2.5A 原始 canonical：**{run['raw_canonical_count']}**；用户指定合并后：**{len(rows)}**。",
        f"语义校验成功：**{run['successfully_enriched']}**；失败：**{run['number_failed']}**；重试候选：**{run['number_retried']}**。",
        f"其中 **{run.get('supported_subset_recovered',0)}** 条只保留有证据的标签子集；模型不受支持的标签提议被逐项拒绝，原提议与原因留存，解释理由需人工协调。它们不会成为 accept。",
        f"Recommended Accept：**{counts['accept']}**；Needs Review：**{counts['review']}**；Reject：**{counts['reject']}**。", '',
        '## 用户指定合并', '']
    for item in lineage:
        lines.append(f"- **{item['name']}**：合并 {len(item['member_ids'])} 条 canonical；保留每个成员与原始证据。代表坐标沿用主场馆，不求平均、不生成新坐标。")
    lines += ['', '这是路线节点范围合并：北广场与穹顶不是同一建筑；场馆室内访问与广场短暂停留仍需分清。B1/N/D 馆没有自动并入。', '',
        '## 方法与事实边界', '',
        '- 复用 DeepSeekLLMClient、原 JSON Schema validator 与现有 taxonomy。Intent 默认 1200 token 不变；本任务单独使用 3600 token。',
        '- 标签、类别引用细粒度 evidence IDs；标签校验先于 coverage gain。LLM 没有收到 coverage 数值，prompt 明确说明 coverage gaps are NOT evidence。',
        '- 坐标不在 LLM 输出 schema 中；程序校验并继承已选来源坐标。summary/culture_bridge 及敏感事实槽均为证据原文摘录，解释性文字单独保留为草稿。',
        '- 解释理由仍需要人工核实：确定性校验可验证结构、引用、保守证据门槛和事实摘录，不能证明所有自然语言推理都正确。',
        '- visit_profile 为 product_planning_estimate；没有声称实际平均停留时长或已验证当前营业。',
        '- 距离与空间空白用 Haversine 近似，不是真实步行连通性。source confidence 与 semantic confidence 分开。',
        '- 重复 production 地点作为新增候选拒绝；同名且邻近的油罐 OSM 子对象作为重复路线节点提议拒绝，不等于断言各油罐是同一建筑。其他可能重复、嵌套或无坐标地点保留 review。', '',
        '## Coverage：before → proposed after', '',
        '仅叠加 Recommended Accept；Needs Review / Reject 不计入 proposed after。数字不代表写入生产。', '']
    for group, tags in preview['coverage'].items():
        lines += ['### '+group, '', '| Tag | Before | Proposed after |', '| --- | ---: | ---: |']
        lines += [f"| {tag} | {v['before']} | {v['proposed_after']} |" for tag,v in tags.items()]
        lines.append('')
    lines += ['## Proposed route-role distribution', '', '| Role | Accept + Review | Accept only |', '| --- | ---: | ---: |']
    for role in ('anchor','supporting_stop','transition_stop'):
        lines.append(f"| {role} | {preview['role_distribution'].get(role,0)} | {preview['accepted_role_distribution'].get(role,0)} |")
    lines += ['', f"另有 {preview.get('unresolved_role_count',0)} 条非拒绝候选角色尚未解决，不计入上表；如显示 supporting_stop，明确只是低置信审核占位。各候选的三种角色解释、时长与邻近节点见 review JSON。", '',
              '## Non-museum art', '']
    art_rows=[r for r in rows if r['candidate_id'] in preview['non_museum_art_proposals']]
    lines += ['缺少 museum_visit 标签不足以证明是非博物馆艺术。此处进一步限于 public_art/public_space/park/architecture/heritage 类别提议，仍待人工核实。','']
    lines += [f"- {r['name']}（{r['decision']}）：art 有引用，未赋 museum_visit；仍需检查对应证据与体验范围。" for r in art_rows] or ['没有足够证据形成独立案例。']
    lines.append('')
    for decision, title in [('accept','Recommended Accept'),('review','Needs Review'),('reject','Reject')]:
        lines += ['## '+title, '', '| Name | Category / Role | Tags (interest; experience; culture) | Confidence source / semantic | Gain | Reason |', '| --- | --- | --- | --- | ---: | --- |']
        for row in rows:
            if row['decision']!=decision:
                continue
            tags='; '.join(', '.join(row[g]) or '—' for g in ('interest_tags','experience_tags','culture_tags'))
            role=row['route_role']['primary'] if row['route_role'] else 'unknown'
            lines.append(f"| {escape(row['name'])} | {row['category']} / {role} | {escape(tags)} | {row['source_confidence']['overall']} / {row['semantic_confidence']} | {row['coverage_gain']['score']} | {escape('; '.join(row['reason']))} |")
        lines.append('')
    extensions = [dict(candidate=r['name'], **e) for r in rows if r['semantic'] for e in r['semantic']['taxonomy_extension_candidate']]
    lines += ['## Taxonomy extension candidates', '']
    lines += [f"- {e['candidate']}：{e['label']} — {e['reason']}（仅供讨论）" for e in extensions] or ['无。']
    lines += ['', '## Unresolved enrichment failures', '']
    lines += [f"- {item['name']}：{item.get('reason') or 'validation failed'}；未输出成功语义结果。" for item in run.get('failed_candidates',[])] or ['无。']
    lines += ['', '## API / 缓存 / 测试', '',
        f"本次执行 API 调用：{run['api_calls_this_run']}；缓存命中：{run['cache_hits']}；历史实际尝试次数：{run['total_recorded_attempts']}。",
        f"API/校验失败类型：`{run['error_counts']}`。供应商返回 token usage 汇总：`{run['token_usage']}`。", '',
        '单元测试使用 Mock DeepSeek 与 fixture evidence；完整 unittest 命令及结果见 run metadata 的 test_result。',
        f"测试结果：{run.get('test_result','not recorded')}。没有运行 live Route Engine 回归或路线导出。",
        f"production pois.json SHA256：`{run['production_sha256']}`；保持不变：{run['production_unchanged']}。", '',
        '## Files created / modified', '',
        '- `src/llm_client.py`：可选 max_tokens 参数与安全的 usage metadata；默认调用行为不变。',
        '- `src/poi_pipeline/semantic/`：preparation、schema、validation、enricher、admission、reporting。',
        '- `scripts/enrich_west_bund.py`；`tests/test_poi_semantic.py`；`docs/phases/PHASE2_5B.md`；README 阶段入口。',
        '- `data/poi_pipeline/semantic/`：三个请求的数据集、prepared candidates/evidence、merge manifest、run metadata 与独立 enrichment cache。',
        '- `PHASE2_5B_REPORT.md`：本报告。Phase 2.5A canonical/evidence 文件保持原样。', '',
        '## 最值得人工审核的 15–25 个 POI', '',
        '优先列出用户指定合并节点，再按已验证标签的 coverage gain 与空间空白排序；只排序，不反向改标签或角色。', '',
        '| Name | Decision | Role | Priority | 核查重点 |', '| --- | --- | --- | ---: | --- |']
    shortlist = sorted([r for r in rows if r['decision']!='reject'], key=lambda r:(not r.get('component_candidates'), -r['selection_priority']))[:25]
    for row in shortlist:
        lines.append(f"| {escape(row['name'])} | {row['decision']} | {row['route_role']['primary']} | {row['selection_priority']} | {escape('; '.join(row['reason']))} |")
    lines += ['', 'STOP：等待人工验收。未覆盖 pois.json，未修改 route composition，未调用真实 Route Engine 验收流程。', '']
    return '\n'.join(lines)


def escape(value):
    return str(value).replace('|','/').replace('\n',' ')
