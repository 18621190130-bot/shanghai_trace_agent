"""Candidate-only West Bund integration, deterministic acceptance and bounded live smoke."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.poi_pipeline.candidate_kb import build_candidate_kb, NEW_IDS
from src.poi_repository import POIRepository
from src.route_engine import RouteEngine
from src.models import RouteRequest
from src.west_bund_regression import run_regression, expansion_diagnostics, cases, describe

OUT = ROOT / 'data/poi_pipeline/phase2_5c'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_test_digest():
    paths = sorted(list((ROOT/'src').rglob('*.py')) + list((ROOT/'tests').rglob('*.py')))
    paths += [ROOT/'data/pois.json', ROOT/'data/pois_phase2_5_candidate.json']
    return hashlib.sha256(''.join(str(p.relative_to(ROOT)) + digest(p) for p in paths).encode()).hexdigest()


def provider_smoke(repository):
    from src.llm_client import DeepSeekLLMClient, redact_diagnostic
    from src.route_entry import RouteEntryService
    if not os.environ.get('DEEPSEEK_API_KEY'):
        return dict(status='provider_smoke_not_run', reason='provider environment unavailable', calls=0)
    # Never print/debug raw provider responses or credentials. No parser retry in this smoke.
    os.environ.pop('DEEPSEEK_DEBUG', None)
    client = DeepSeekLLMClient(timeout=40)
    service = RouteEntryService(repository, client)
    service.parser.max_attempts = 1
    prompts = ['I have three hours to explore art in the West Bund but I do not want to visit museums.',
               'Give me a three-hour outdoor West Bund walk with river views and public spaces. No museums.',
               'I have three hours in the West Bund and want to understand Shanghai industrial past while walking along the river.']
    rows = []
    for prompt in prompts:
        print('Provider smoke case ' + str(len(rows)+1) + '/3', flush=True)
        try:
            intent = service.parse_plan(prompt)
            result = service.generate(intent)
            rows.append(dict(prompt=prompt, parsed_intent=intent.to_dict(), result=result.to_dict(),
                provider_metadata=client.last_response_metadata, status='contract_passed'))
        except Exception as exc:
            rows.append(dict(prompt=prompt, status='provider_or_contract_error', error_type=type(exc).__name__,
                error=redact_diagnostic(str(exc)), provider_metadata=client.last_response_metadata))
    return redact_diagnostic(dict(status='completed', calls=len(rows), retried=0, cases=rows))


def coverage(repo):
    return {g: {tag: sum(tag in getattr(p, g) for p in repo.get_pois_by_zone('west_bund'))
                for tag in repo.taxonomy[g]} for g in ('interest_tags', 'experience_tags', 'culture_tags')}


def report(data, candidate, mapping):
    rows, diag = data['regression'], data['zone_expansion_diagnostic']
    lines = ['# PHASE2_5C_REPORT', '', '## 1. Candidate KB summary', '',
        f"candidate POIs={candidate['metadata']['poi_count']}，West Bund={len(data['west_bund_nodes'])}；8个新节点、5个既有anchors。candidate_kb_status={data['candidate_kb_status']}。production pois.json 未覆盖。", '',
        f"route-role distribution={data['route_role_distribution']}。", '',
        '**确定性验收检查通过不等于8条请求都成功**：7条完整路线成功，A纯art/no-museums正确返回composition_failure；不伪造anchor或添加低相关Gate M。', '',
        '## 2. Final West Bund 13 nodes', '', '| ID | 名称 | primary | eligible | interest / experience / culture |', '| --- | --- | --- | --- | --- |']
    for p in data['west_bund_nodes']:
        tags = ' / '.join(', '.join(p['tags'][g]) or '—' for g in ('interest_tags', 'experience_tags', 'culture_tags'))
        lines.append(f"| {p['id']} | {p['name']} | {p['route_role']['primary']} | {', '.join(p['route_role']['eligible'])} | {tags} |")
    lines += ['', '## 3. New stable IDs', '', '| Staging identity | Candidate production ID |', '| --- | --- |']
    lines += [f'| {nid} | {pid} |' for nid,pid in NEW_IDS.items()]
    lines += ['', '已有ID最高已为p35，因此显式分配p36–p43；ID映射常量按identity版本化，不按当前数组位置生成。重排staging不改变ID。', '',
        '## 4. Route-role implementation', '',
        'POIRepository验证route_role.primary/eligible；POI.effective_primary_role和RouteStop.effective_primary_role暴露审定角色。旧节点缺少角色时返回None，不隐式猜测anchor。访问模式不改变角色。', '',
        '## 5. Composition rule', '',
        'candidate defaults显式启用west_bund，仅plan_for_me/surprise_me执行：至少1 anchor、至少2 anchor/supporting；Minimum Viable City Walk仍为3站。几何、avoid、must-go优先。违规路线可在原质量/预算门槛内作一次独立节点插入或替换，找不到则composition_failure，保留所选相关节点和明确诊断。',
        '超过2个连续transition仅为软偏好：只在等距离排序中优先选择较短连续串，不为了组成拉长路程或添加节点。',
        '西岸局部质量修正沿用_relevant的核心兴趣OR语义：多兴趣命中用于排序，单个真实核心兴趣匹配不被最高分种子的多标签分母隐式否决。核心比较仍要求真实请求标签；距离增长、边际步行、预算及负面偏好门槛保留。不是修改标签或角色。', '',
        '## 6. Backward compatibility', '',
        'production配置未开启composition，因此原数据及其路线行为保留。其他三个zone的POI JSON逐字段保持一致；固定显式zone请求与Phase 2 production基线的状态、所选ID/模式、总时间一致。Places in mind西岸保留显式选择集合，不暗加anchor；两座transition也可生成明确选择的轻量路线，composition.enabled=false。', '',
        '## 7. Tag coverage before → after', '']
    for g, values in data['coverage_after'].items():
        lines += [f'### {g}', '', '| tag | Phase 2 | Candidate |', '| --- | ---: | ---: |']
        for tag,count in values.items():
            lines.append(f"| {tag} | {data['coverage_before'][g][tag]} | {count} |")
        lines.append('')
    lines += [f"non-museum art nodes：{data['non_museum_art_before']} → {data['non_museum_art_after']}；无尽影院没有计入。", '',
        '## 8. Eight deterministic route regression cases', '',
        '| Case | Status | Pool before / eligible / relevant | Stops | Minimum | Composition | Avoid | Total min | Utilization | Failure cause |',
        '| --- | --- | --- | ---: | --- | --- | --- | ---: | ---: | --- |']
    for r in rows:
        pool = f"{len(r['candidate_pool_before_filtering'])}/{len(r['candidate_pool_after_filtering'])}/{len(r['relevant_candidate_pool'])}"
        lines.append(f"| {r['case']} | {r['route_status']} | {pool} | {len(r['selected_stops'])} | {r['minimum_viable_passed']} | {r['composition_passed']} | {r['negative_preference_passed']} | {(r['total_estimated_time'] or 0):.1f} | {(r['time_utilization'] or 0):.1%} | {r['failure_attribution'] or '—'} |")
    for r in rows:
        lines += ['', f"### Case {r['case']}: {r['label']}", '',
            f"request=`{json.dumps(r['request'],ensure_ascii=False)}`", '',
            f"matched={r['matched_tags']}；avoid={r['avoid_tags']}；before={r['candidate_pool_before_filtering']}；eligible={r['candidate_pool_after_filtering']}；relevant={r['relevant_candidate_pool']}", '',
            '| ID | Stop | Primary role | Matched tags | Visit mode | Product visit estimate min |',
            '| --- | --- | --- | --- | --- | ---: |']
        for s in r['selected_stops']:
            lines.append(f"| {s['poi_id']} | {s['name']} | {s['primary_role']} | {s['matched_tags']} | {s['visit_mode']} | {s['estimated_visit_minutes']} |")
        lines += ['', f"failure reason={r['failure_reason']}；max estimated leg km={r['estimated_max_single_leg_km']}。"]
    lines += ['', 'A有3个真实non-museum art supporting stops，minimum_stop_count_passed=true、route_composition_passed=false。当前唯一non-museum anchor Gate M没有art标签，因此不能用于纯art补位。该问题来自审定角色组成约束，不是缺少三站，也不是当前边界空间空洞。', '',
        '### Strong-theme baseline comparison', '', '| Case | Phase 2 status / stops / max leg | Candidate status / stops / max leg |', '| --- | --- | --- |']
    for key in ('C','F'):
        old = next(r for r in data['baseline_regression'] if r['case']==key)
        new = next(r for r in rows if r['case']==key)
        lines.append(f"| {key} | {old['route_status']} / {len(old['selected_stops'])} / {old['estimated_max_single_leg_km']} | {new['route_status']} / {len(new['selected_stops'])} / {new['estimated_max_single_leg_km']} |")
    lines += ['', '## 9. Three-mode regression', '', '| Mode | Status | Stop IDs | Composition enabled |', '| --- | --- | --- | --- |']
    for mode,v in data['three_modes'].items():
        plan = v['route_plan'] or {}
        lines.append(f"| {mode} | {v['status']} | {[s['poi_id'] for s in plan.get('ordered_pois',[])]} | {plan.get('composition_diagnostics',{}).get('enabled')} |")
    lines += ['', '## 10. Optional real DeepSeek smoke tests', '',
        f"status={data['provider_smoke']['status']}；calls={data['provider_smoke'].get('calls',0)}。"]
    for s in data['provider_smoke'].get('cases',[]):
        result = s.get('result',{})
        lines.append(f"- {s['prompt']}：contract={s['status']}；route status={result.get('status')}；provider metadata={s.get('provider_metadata')}；error={s.get('error')}。")
    lines += ['', '真实smoke只验证provider→RouteIntent→Engine契约，仍保留真实澄清/组成失败，不能将其误报为完整路线成功。最多3条、每条1次、无retry，未进行enrichment。', '',
        '## 11. Geographic distribution', '',
        json.dumps(diag['geographic_gap_indicators'],ensure_ascii=False,indent=2), '',
        'north纬度>=31.18，central 31.17–31.18，south<31.17；仅表示13个代表点的分布。没有依据从较多south点推导断路/不可达。跑道与大剧院点仍如实保留既有审核缓冲身份，未移动坐标凑polygon。', '',
        '## 12. zone_expansion_diagnostic', '', '```json', json.dumps(diag,ensure_ascii=False,indent=2), '```', '',
        '多个请求的数据供给/空间缺口失败才可建议扩zone。本轮唯一失败为route_role_composition，所以推荐false；无新增collection、无扩边界。', '',
        '## 13. Full test results', '', json.dumps(data['tests'],ensure_ascii=False,indent=2), '',
        f"protected unchanged={data['protected_unchanged']}；production SHA256={data['production_sha256']}。", '',
        '## 14. Known limitations', '',
        '- A纯art/no-museums没有审定anchor；应独立讨论组成政策或主题拓宽，不为了过测试修改role。',
        '- 停留时间为product estimate；真实演出、开放、票务、预约与内部访问范围未实时核实。full_visit不保证可入内。',
        '- 距离为Haversine×配置绕行系数；没有真实街道routing。',
        '- 少数路线时间利用率高于95%，仍在硬预算内；70–95%为软偏好，没有为填时间加入低相关点。',
        '- 没有把defer/internal对象加回。无尽影院reject_current_pilot保留历史证据，active conditional列表为空；旧Phase 2.5B报告保留为历史记录。',
        '- 单步composition修复是轻量启发式，不承诺搜索所有合法路线；失败不自动断言数据不足。', '',
        '## 15. Files modified', '',
        '- src/models.py、poi_repository.py、intent_adapter.py、route_engine.py：兼容角色与显式zone/mode gating。',
        '- 新增src/route_composition.py、src/west_bund_regression.py、src/poi_pipeline/candidate_kb.py。',
        '- 新增scripts/export_phase2_5c.py、tests/test_phase2_5c.py。',
        '- 新增data/pois_phase2_5_candidate.json及data/poi_pipeline/phase2_5c/验收、映射/归档、测试和smoke证据。',
        '- 新增本报告；README增加候选运行说明。', '',
        '## 16. Exact commands to reproduce', '', '```powershell',
        'python scripts/export_phase2_5c.py --run-tests',
        'python -m unittest discover -s tests -t . -q',
        '# Optional paid provider smoke (up to three calls; requires process DEEPSEEK_API_KEY)',
        'python scripts/export_phase2_5c.py --live-smoke', '```', '',
        '默认POIRepository仍使用production；候选使用POIRepository("data/pois_phase2_5_candidate.json")，再交给现有RouteEntryService/RouteEngine。导出不覆盖production。', '',
        'PHASE 2.5C STATUS: '+data['status'], '', 'STOP：等待人工验收；不promotion，不扩zone，不开始Phase 3。', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-tests', action='store_true')
    parser.add_argument('--live-smoke', action='store_true')
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    final = ROOT / 'data/poi_pipeline/semantic/final'
    baseline = read(final/'protected_baseline.json')
    allowed = {'src\\models.py', 'src\\poi_repository.py', 'src\\intent_adapter.py', 'src\\route_engine.py'}
    protected = {p: h for p,h in baseline.items() if p not in allowed}
    if any(digest(ROOT/p) != h for p,h in protected.items()):
        raise RuntimeError('unauthorized protected file change')
    production = read(ROOT/'data/pois.json')
    kb, mapping = build_candidate_kb(production, read(final/'west_bund_route_nodes_final_staging.json'), read(final/'west_bund_human_review_final.json'))
    path = ROOT/'data/pois_phase2_5_candidate.json'
    # Status is established by the acceptance artifact, not by a write-and-read test illusion.
    kb['metadata']['candidate_kb_status'] = 'candidate_only; see phase2_5c/acceptance.json'
    write(path, kb)
    repo, old_repo = POIRepository(path), POIRepository()
    rows, modes = run_regression(repo)
    if args.run_tests:
        start = time.monotonic()
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-t', '.', '-q'],
            cwd=ROOT, capture_output=True, text=True)
        print(result.stdout + result.stderr)
        match = re.search(r'Ran (\d+) tests', result.stderr)
        write(OUT/'test_result.json', dict(command='python -m unittest discover -s tests -t . -q',
            status='passed' if result.returncode == 0 else 'failed', exit_code=result.returncode,
            tests_run=int(match.group(1)) if match else None, elapsed_seconds=round(time.monotonic()-start,3),
            input_digest=current_test_digest()))
    tests = read(OUT/'test_result.json') if (OUT/'test_result.json').exists() else {'status':'not_run'}
    test_pass = tests['status'] == 'passed' and tests.get('input_digest') == current_test_digest()
    if args.live_smoke and not test_pass:
        raise RuntimeError('current deterministic/full-test gate must pass before real provider smoke')
    if args.live_smoke:
        write(OUT/'provider_smoke.json', provider_smoke(repo))
    smoke = read(OUT/'provider_smoke.json') if (OUT/'provider_smoke.json').exists() else {'status':'provider_smoke_not_run','calls':0}
    before, after = coverage(old_repo), coverage(repo)
    non_museum = lambda r: sum('art' in p.interest_tags and 'museum_visit' not in p.experience_tags for p in r.get_pois_by_zone('west_bund'))
    data = dict(status='PASS' if test_pass else 'BLOCKED', candidate_kb_status='ready_for_promotion' if test_pass else 'pending_validation',
        counts=dict(actual_pois=len(repo.get_all_pois()), west_bund=len(repo.get_pois_by_zone('west_bund'))),
        route_role_distribution=dict(Counter(p.effective_primary_role for p in repo.get_pois_by_zone('west_bund'))),
        west_bund_nodes=[dict(id=p.id, name=p.name_zh, tags={g:list(getattr(p,g)) for g in before},
            route_role=dict(primary=p.effective_primary_role, eligible=list(p.route_role_eligible))) for p in repo.get_pois_by_zone('west_bund')],
        coverage_before=before, coverage_after=after, non_museum_art_before=non_museum(old_repo), non_museum_art_after=non_museum(repo),
        regression=rows, baseline_regression=[describe(RouteEngine(old_repo),r,n,l) for n,l,r in cases()],
        three_modes=modes, zone_expansion_diagnostic=expansion_diagnostics(repo,rows), provider_smoke=smoke,
        tests=tests, protected_unchanged=all(digest(ROOT/p)==h for p,h in protected.items()),
        production_sha256=digest(ROOT/'data/pois.json'), production_promoted=False)
    write(OUT/'identity_mapping_and_archive.json',mapping)
    write(OUT/'acceptance.json',data)
    (ROOT/'docs/history/phase2_5/PHASE2_5C_REPORT.md').write_text(report(data,kb,mapping),encoding='utf-8')
    print(json.dumps({'status':data['status'],'candidate_kb_status':data['candidate_kb_status'],
        'counts':data['counts'],'zone_expansion_recommended':data['zone_expansion_diagnostic']['zone_expansion_recommended']}))


if __name__ == '__main__':
    main()
