"""Replay final human decisions and recorded targeted checks. Entirely offline."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.poi_pipeline.semantic.final_review import build_final_review, zone_expansion_diagnostic


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def report(review, verification, test_result):
    counts = review['counts']
    lines = ['# PHASE 2.5B FINAL HUMAN REVIEW REPORT', '',
        '本轮仅落实人工审核与六项定向事实核验。最终 staging 集合没有导入 production，未执行 Phase 2.5C、路线回归或地图步行路由。', '',
        '| 统计 | 数量 |', '| --- | ---: |']
    for key, label in [('existing_anchor', '已有 production anchors'), ('new_supporting_stop', '已批准新增 supporting stops'),
                       ('new_transition_stop', '已批准新增 transition stops'), ('conditional', '尚待核验的条件节点'),
                       ('conditional_verified', '本轮条件核验通过'), ('total_route_selectable', '总可选 route nodes')]:
        lines.append(f'| {label} | {counts[key]} |')
    lines += ['', 'conditional 数量指尚未通过的节点；本轮核验通过的海事塔、大剧院已归入 B/C，统计不重复。节点数量不是 quota。', '']
    titles = {'A': '已有 production anchors', 'B': '已批准的新 supporting stops',
              'C': '已批准的新 transition stops', 'D': '条件接受 / 等待事实核验的节点',
              'E': 'deferred nodes', 'F': 'rejected nodes'}
    for group, title in titles.items():
        lines += [f'## {group}. {title}', '',
                  '| 名称 | 决定 | 角色 | 可选/新增计数 | 坐标 (GCJ-02 lat,lng) | interest / experience / culture | 原因 |',
                  '| --- | --- | --- | --- | --- | --- | --- |']
        for r in review['rows']:
            if r['review_group'] != group:
                continue
            tags = ' / '.join(', '.join(r[g]) or '—' for g in ('interest_tags', 'experience_tags', 'culture_tags'))
            lines.append(f"| {r['name']} | {r['decision']} | {r['primary_role']} | {r['route_selectable']}/{r['counts_as_new_stop']} | {r['coordinates']} | {tags} | {' '.join(r['reason'])} |")
        if group == 'A':
            lines += ['', '五个 production ID 保持原身份、坐标与内容快照，primary=anchor；既有 walk_stop 支持 supporting_stop eligibility。均 counts_as_new_stop=false。']
        if group == 'B':
            lines += ['', '穹顶采用 one_node_dual_mode：walk_stop 为北广场/外部停留；full_visit 为条件性场馆内部/演出访问。开放时间、当前演出、当前入内状态仍 unknown/null。所有新节点停留时长均为 product_planning_estimate，不是假设真实平均停留。',
                '大剧院保留 art，experience/culture 不填 quota；有预约导览/观演目的访问场景，详细场次和入场条件须另行确认。摄影中心中英文记录仅计一个 stop。']
        if group == 'D':
            lines += ['', '未通过条件者已落实 defer、route_selectable=false；不会阻碍以其他已批准节点开展下一阶段。']
        lines.append('')
    lines += ['## G. child / internal / duplicate source entities', '',
              '| 名称 | parent | 决定 | 可选 | 新增计数 | 关系 / 原因 |',
              '| --- | --- | --- | --- | --- | --- |']
    for e in review['source_entities']:
        lines.append(f"| {e['name']} | {e['parent_node']} | {e['decision']} | false | false | {e['relationship']}；{e.get('reason', '')} |")
    lines += ['', '2555号建筑的历史/建筑证据已归入艺术中心 evidence_catalog，没有自动给父节点增加标签。塔吊广场仅为塔吊节点别名和周边空间证据；A/B1/N/D和穹顶北广场均不增加 stop count。岩时攀岩维持 reject、非可选（登记于G的内部实体）。', '',
              '## 六项定向核验及代表点选择', '',
              '网页检索/读取结果只保留定向事实摘要与时间、来源、获取方式。搜索索引摘要不冒充成功直接读取；历史报道不冒充今日存在。所有坐标来自真实 provider 记录，没有平均或 LLM 生成坐标。代表点是近似访问锚点，不声称测绘了精确入口。', '']
    names = {r['node_id']: r['name'] for r in review['rows']}
    for nid, v in verification.items():
        lines += [f"### {names[nid]}", '', v['conclusion'], '',
                  '| 核验 | 结果 | 证据 |', '| --- | --- | --- |']
        for name, c in v['checks'].items():
            refs = ', '.join(f"[{ref}]({v['evidence_catalog'][ref]['url']})" for ref in c['evidence_refs']) or '无可靠当前证据'
            lines.append(f"| {name} | {c['status']} | {refs} |")
        if v.get('representative_anchor'):
            a = v['representative_anchor']
            lines += ['', f"代表点：`{a['coordinates']}` GCJ-02；confidence={a['confidence']}；{a['reason']}"]
        for e in v['evidence_catalog'].values():
            lines.append(f"- [来源]({e['url']})：{e['value']} 获取方式：{e['retrieval_method']}；检索时间：{e['retrieved_at']}；发布时间：{e['published_at'] or 'unknown'}。")
        lines.append('')
    lines += ['## 边界与下一阶段诊断', '',
        '边界多边形及原150米审核缓冲未修改。跑道公园代表点（31.168592,121.457730）处于多边形西侧约26米的既有审核带，按本轮明确人工接受决定纳入staging；不将其标为inside_pilot。线性公园完整边界不是此代表点，不把跨区范围全部纳入试点。',
        'zone_expansion_diagnostic 仅定义未来统计输入：theme_failure_count、insufficient_route_count、composition_failure_count、各请求candidate pool sizes、non-museum/parks-public-space success、geographic gap indicators。当前status=not_run、zone_expansion_recommended=null。只有失败归因主要为高质量节点不足或地理缺口才为true；parser/tag mismatch/算法/scoring原因不会被当作扩zone理由。', '',
        '## 测试与保护检查', '', str(test_result), '',
        f"受保护文件 SHA256 全部保持一致：{review['protected_unchanged']}（{len(review['protected_hashes'])} 个）。production pois.json 仍为 `{review['protected_hashes']['data\\pois.json']}`。",
        '本轮0 DeepSeek调用，0全量采集，0路线回归。定向网页核验已完成并记录六项结果；离线重放不再消耗外部API。', '',
        '## 文件与复现', '',
        '- src/poi_pipeline/semantic/final_review.py：人工准入、父子归并、校验与未来诊断。',
        '- scripts/finalize_west_bund_review.py：离线生成三份最终产物。',
        '- tests/test_poi_final_review.py：mock source与条件核验测试；无真实DeepSeek/网络。',
        '- data/poi_pipeline/semantic/final/：final review、selectable staging、targeted verification、protected baseline和test_result。',
        '- PHASE2_5B_FINAL_HUMAN_REVIEW_REPORT.md：本报告。', '',
        '复现：`python scripts/finalize_west_bund_review.py`；测试：`python -m unittest discover -s tests -t . -q`。', '',
        'STOP：等待 Phase 2.5C 的独立授权，本轮不自动开始。', '']
    return '\n'.join(lines)


def main():
    root = ROOT / 'data/poi_pipeline/semantic'
    output = root / 'final'
    verification = read(output / 'targeted_verification.json')
    taxonomy = read(ROOT / 'data/pois.json')['metadata']['tag_taxonomy']
    review, selectable = build_final_review(read(root / 'repair/west_bund_review_repaired.json'),
        read(root / 'repair/west_bund_route_nodes.json'), read(root / 'repair/west_bund_source_entities.json'), verification, taxonomy)
    if len({cid for r in review['rows'] for cid in r['member_candidate_ids']}) != 58:
        raise ValueError('Not all 58 prepared source candidates accounted for')
    protected = read(output / 'protected_baseline.json')
    if any(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest for path, digest in protected.items()):
        raise ValueError('Protected file changed')
    review.update(schema_version='phase2.5b-final-staging-v1', production_imported=False,
                  phase_2_5c_started=False, protected_unchanged=True, protected_hashes=protected,
                  diagnostic=zone_expansion_diagnostic(), deepseek_calls=0, full_collection_calls=0)
    tests = read(output / 'test_result.json') if (output / 'test_result.json').exists() else {'status': 'pending'}
    review['tests'] = tests
    write(output / 'west_bund_human_review_final.json', review)
    write(output / 'west_bund_route_nodes_final_staging.json', dict(schema_version='phase2.5b-final-staging-v1',
        production_imported=False, route_nodes=selectable, counts=review['counts'], source_review='west_bund_human_review_final.json'))
    (ROOT / 'docs/history/phase2_5/PHASE2_5B_FINAL_HUMAN_REVIEW_REPORT.md').write_text(report(review, verification, tests), encoding='utf-8')
    print(json.dumps(review['counts'], ensure_ascii=True))


if __name__ == '__main__':
    main()
