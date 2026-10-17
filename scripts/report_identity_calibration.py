"""Build the Phase 3B_2.1 review report from saved audit and acceptance evidence."""
from collections import Counter
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
def read(name):return json.loads((ROOT/name).read_text(encoding='utf-8'))
def main():
    records=read('data/amap_poi_mappings.json');summary=read('examples/location_awareness/mapping_audit.json')
    core=read('data/pois.json');old=read('examples/location_awareness/calibration/mappings_before.json')
    corrections=read('examples/location_awareness/coordinate_corrections.json')['corrections']
    deletion=read('data/deleted_core_pois.json')['deleted'][0]
    live=read('examples/location_awareness/calibration/live_acceptance.json')
    delivery=read('examples/location_awareness/delivery_audit.json')
    offline=(ROOT/'examples/location_awareness/calibration/full_tests.txt').read_text(encoding='utf-8-sig')
    live_tests=(ROOT/'examples/location_awareness/calibration/live_tests.txt').read_text(encoding='utf-8-sig')
    assert 'Ran 737 tests' in offline and 'OK (skipped=3)' in offline
    assert 'Ran 3 tests' in live_tests and re.search(r'\nOK\s*$',live_tests)
    assert not delivery['unexpected_protected_changes'] and not delivery['configured_secret_exposures'] and not summary['search_failures']
    lines=['# TraceMate Phase 3B_2.1 验收报告','',
           '日期：2026-10-05（Asia/Shanghai）。本轮为 Phase 3B_2 受控修订，交付状态 **READY，等待人工验收**。未执行 Phase 3B_2 正式 Freeze，未开始 3B_3、3B_4、Reality Check 或 UI。','',
           '## Summary','',
           '完成 Core 错误删除与两项正式坐标校正、10 项人工确认身份落地、58 项双维度身份审计、alias 与 parent/child 判断、NOT_APPLICABLE 营业状态、离线及真实 API 回归。身份、动态信息适用性和本次查询的数据完整度各自独立。',
           '生产路线规划继续使用修订后的 Core；Trip、RouteEngine、Replan、CAS、RouteVersion 和 Walking fallback 源码保持基线一致。全部未授权知识字段逐对象比较通过。','',
           '## Core Data Corrections','',
           '- p40 上海摄影艺术中心已从生产 KB、sidecar 和当前路线样例删除，Core 总数 59→58，西岸节点 13→12。related 与 runtime fixture 无 active dangling reference。默认 Trip fixture 原本不包含 p40，因此保持不变。',
           '- 旧西岸样例序列 p36→p40→p28→p29→p37 仅删除 p40，保留为 p36→p28→p29→p37；未加替代点。真实几何重新获取：1166m、50 个 geometry points。新生成路线另存 calibration/new_generated_west_bund.json，属于新请求规划结果，未替换既有路线的剩余序列。',
           '- p4 与 p11 仅更新 lat/lng 或 representative_lat/lng 数值；story、tags、stay、walk_zone、访问模式、推荐规则、其他坐标和稳定 ID 未修改。删除后的 display_order 连续调整及元数据数量同步属于结构性校正。',
           '- 删除日志：data/deleted_core_pois.json；生产差异记录：calibration/core_revision_manifest.json。原生产 KB、原 sidecar、旧人工审查包和旧步行证据已保存到 examples/location_awareness/calibration。Phase 2.5 候选库、历史报告和冻结包保留为历史证据。','',
           '## Coordinate Correction Audit','',
           '| Core ID / Name | Old GCJ02 lat,lng | New official GCJ02 lat,lng | Amap ID | Offset m | Reviewed |',
           '| --- | --- | --- | --- | ---: | --- |']
    for c in corrections:
        a,b=c['old_coordinate'],c['new_coordinate']
        lines.append(f"| {c['core_id']} {c['name']} | {a['lat']}, {a['lng']} | {b['lat']}, {b['lng']} | {c['amap_poi_id']} | {c['old_to_new_distance_m']:.2f} | true |")
    lines.extend(['','坐标直接来自已人工确认 ID 的正式高德 detail，未做坐标平均或为通过旧测试保留错误点。证据：examples/location_awareness/coordinate_corrections.json、calibration/coordinate_provider_details.json。Core 原有说明文本保留；新的精确来源及坐标系在本轮审计中明确记录。','',
                  '## Manual Identity Mappings','',
                  '| Core ID | Core Name | Amap ID | Confirmed Amap Name | match_method | reviewed |',
                  '| --- | --- | --- | --- | --- | --- |'])
    for pid,row in records.items():
        if row['reviewed']:lines.append(f"| {pid} | {row['core_name']} | {row['amap_poi_id']} | {row['matched_name']} | {row['match_method']} | true |")
    lines.extend(['','9 项固定人工决定持久化于 data/amap_manual_confirmations.json；p24 按负责人给定条件找到总主体后确认。重跑审计不会由 confidence 或 margin 降级人工确认；真实 provider 查询失败只影响实时可用性，不取消身份。自动匹配 reviewed=false，不冒充人工确认。','',
                  '## p24 Resolution','',
                  '**已找到总主体：中国共产党第一次全国代表大会纪念馆，Amap ID B0MGOCVX94。**',
                  '正式全称、中共一大纪念馆、一大纪念馆分别进行上海名称检索及 Core 坐标附近检索；结合黄浦区、纪念馆类型和约 73m 偏移确认。不是一大广场、公交站、保管部、实验室、报告厅、专题展厅或宣誓大厅。Live detail 也成功返回该 ID 的主体信息。',
                  '状态 MATCHED + FULL，reviewed=true，MANUAL_ALIAS_CONFIRMATION，entity_type=memorial_museum。完整查询参数和候选证据在 sidecar p24.search_queries / candidates。','',
                  '## Identity Audit','',
                  '| Identity | Count |','| --- | ---: |'])
    for status,n in summary['identity_counts'].items():lines.append(f'| {status} | {n} |')
    lines.extend(['| **Total** | **58** |','',
                  'Identity 中不存在 NOT_APPLICABLE；未匹配不会解释为现实地点不存在。','',
                  '## Live Info Applicability Audit','', '| Applicability | Count |','| --- | ---: |'])
    for status,n in summary['live_info_applicability_counts'].items():lines.append(f'| {status} | {n} |')
    old_na=[pid for pid,r in old.items() if r['status']=='NOT_APPLICABLE']
    na_counts=Counter(records[pid]['identity_mapping_status'] for pid in old_na)
    lines.extend(['| **Total** | **58** |','',
                  'FULL/LIMITED 有可靠当天区间才计算 OPEN/CLOSED，否则 UNKNOWN。NOT_APPLICABLE 恒定返回 open_status=NOT_APPLICABLE，包括本次数据 UNAVAILABLE 的情况；这不改变其 Identity。AVAILABLE/PARTIAL/UNAVAILABLE 仅描述本次查询，不能推导实体是否存在。',
                  f"原 26 项混合 N/A 全部重新做 Identity 检索，当前身份结果：{dict(na_counts)}；26 是历史重审集合大小，不是当前 identity status。",'',
                  '## Park Re-audit','',
                  '| Core ID | Park | Identity | Provider ID | Live Info |','| --- | --- | --- | --- | --- |'])
    for pid,row in records.items():
        if row['entity_type']=='park':lines.append(f"| {pid} | {row['core_name']} | {row['identity_mapping_status']} | {row['amap_poi_id'] or '-'} | {row['live_info_applicability']} |")
    lines.extend(['','11 个公园全部完成重审，均为 MATCHED + LIMITED。淮海公园 provider 名中的“暂停开放”作为身份名称附注处理，不据此自行计算营业状态；缺可靠当天时间仍 UNKNOWN。','',
                  '## Street / District / Open-space Re-audit','',
                  '| Core ID | Core | Identity | Provider ID | Entity Type | Live Info |',
                  '| --- | --- | --- | --- | --- | --- |'])
    types={p['id']:p['poi_type'] for p in core['pois']}
    for pid,row in records.items():
        if types[pid] in ('street','district','landmark'):
            lines.append(f"| {pid} | {row['core_name']} | {row['identity_mapping_status']} | {row['amap_poi_id'] or '-'} | {row['entity_type']} | {row['live_info_applicability']} |")
    lines.extend(['','新天地北里已找到街区主体 B00156YMMX 上海新天地北里，provider 类型为特色商业街；MATCHED + NOT_APPLICABLE，不绑定内部餐厅/书店。甜爱路采用道路名实体 BZAGR001Z2，MATCHED + NOT_APPLICABLE；同名同区、相距 49m 的景点表示不是另一个现实地点。上海人民广场采用城市广场主体 B00157917M，热点表示不被误当竞争主体。','',
                  '## Matcher / Runtime Changes','',
                  '名称 aliases、行政区、坐标和实体类型共同校验；confidence≥0.92、相似度≥0.9、距离≤300m 与竞争主体 margin≥0.08 均保持。明显子馆/分馆/广场附属区域/入口/停车/售票/报告厅等不参与主体竞争。街区的特色商业街主体与商户区分；纪念馆不绑定广场或交通节点。',
                  'Sidecar 提供 identity_mapping_status、amap_poi_id、matched_name、entity_type、live_info_applicability、aliases、reviewed、match_method、confidence、distance_m、notes。PoiLiveInfo 输出 identity_mapping_status 和 live_info_applicability；mapping_status 暂作兼容别名，语义只等于 identity。API 与缓存仍只读，无 TripStore 引用。校准附近查询仅作为一次性 Core 身份证据，不增加 Nearby 推荐服务或任何路线补点。','',
                  '## Remaining Ambiguous / Not Found','',
                  '| Core ID | Name | Status | Actual remaining issue |','| --- | --- | --- | --- |'])
    issues={
        'p25':'identity ambiguity：内山书店旧址 B00155GHK0 与现运营的 1927·纪念书局 B0I2KZFZRY 均约 10m；Core alias 覆盖旧址与书局，需决定历史地点/现运营主体的身份范围。',
        'pz_b72e3b8998b3':'identity scope ambiguity：文化名人街 B00155FLFD 与道路名多伦路 BZAGR0033N 相距约 39m；Core 同时包含道路 alias，尚未统一文化街区与道路实体的覆盖范围。',
        'p10':'同名候选 B0HDACXK1W 约 980m，超过原距离阈值；没有确认可信对应主体。本轮没有授权修改此 Core 坐标。',
        'p12':'同名候选 B00156COKX 约 447m，超过原距离阈值；没有确认可信对应主体。本轮没有授权修改此 Core 坐标。',
        'p34':'道路名候选 B0IA369WVI 约 381m，超过原距离阈值；连续街段的代表点/范围尚未确认，不通过放宽阈值强绑。',
        'p35':'未检索到稳定统一的“徐家汇商圈”主体；徐家汇源、商圈服务中心、办公室、连廊均不能代替整片 Core 区域。',
    }
    for pid,row in records.items():
        if row['identity_mapping_status']!='MATCHED':lines.append(f"| {pid} | {row['core_name']} | {row['identity_mapping_status']} | {issues[pid]} |")
    lines.extend(['','NOT_FOUND 表示本次合理检索未取得可信 provider identity，不表示地点不存在。尤其 p10/p12/p34 的同名候选已返回，因此不能声称高德完全未收录；问题是距离/范围证据不足。p35 是稳定统一 area identity 未找到。以上不擅自改坐标、不补商户、不伪造营业数据。',
                  'Remaining Manual Review 仅包含上述 2 项身份范围歧义；本轮已确认的 p4/p11/p20/p24/p32/p33/p36/p37/安康公寓/交响音乐厅均不重复列入，p40 已删除。详见 examples/location_awareness/MAPPING_MANUAL_REVIEW.md。','',
                  '## Tests','',
                  '| Group | Discovered | Offline result | Live result |','| --- | ---: | --- | --- |',
                  '| Phase 3A / inherited regressions | 645 | 645 PASS | 不需要新外部服务 |',
                  '| Phase 3B_1 | 34 | 33 PASS + 1 opt-in skip | 1 PASS |',
                  '| Phase 3B_2 | 36 | 35 PASS + 1 opt-in skip | 1 PASS |',
                  '| Phase 3B_2.1 | 22 | 21 PASS + 1 opt-in skip | 1 PASS |',
                  '| **All** | **737** | **734 PASS, 3 skipped; 64.893s** | **3 PASS; 11.532s** |','',
                  '命令：python -m scripts.run_offline_tests；显式 live 环境下 python -m unittest tests.test_walking_live tests.test_location_live tests.test_identity_calibration_live -v。日志：calibration/full_tests.txt、calibration/live_tests.txt。schema 校验断言完善后额外重跑 world/calibration 合同测试：56 PASS（world_contract_tests.txt）。',
                  '删除后生产自动选点改变了旧业务测试的起始序列；三组 Trip 语义测试改用 tests/fixtures/trip_semantics_initial.json 的原 p29→p43→p5 有效场景，均为仍保留的 Core，当前生产规划仍实际执行，后续动作使用当前 repository。仅固定测试前提，skip/remove/must-go/revisit、soft/hard budget、CAS、RouteVersion、Replan 的既有断言未放宽，产品生成路线未固定为旧序列。645 项继承回归全部通过。旧生产 hash/数量断言同步明确授权的 58 Core 新快照。',
                  '两项正式坐标的真实验收结果：','',
                  '| Corrected Core | Real route distance m | Real duration s | Polyline points | Replan | Proximity |',
                  '| --- | ---: | ---: | ---: | --- | --- |'])
    for r in live['coordinate_routes']:
        route=r['route'];lines.append(f"| {r['core_id']} | {route['walking_distance_m']:.0f} | {route['walking_duration_s']:.0f} | {len(route['route_geometry'])} | committed v2 / success | ARRIVED at official coordinate |")
    lines.extend(['','Route Engine、hydration、真实距离、polyline、Replan 与 Proximity 均读取新坐标。Replan 保持 original_route/v1 字节内容一致；JSON roundtrip 正常。完整 fallback/cache/timeout/CAS 测试仍通过。p24 detail 和 p7 NOT_APPLICABLE 亦通过 live 验证。',
                  '保护审计：unexpected protected changes=0；未授权 Core 字段变化=0；active p40 references=0；配置凭据泄露=0；58 Core 与 sidecar ID 集合一致；完整审计无 provider search failure。证据：examples/location_awareness/delivery_audit.json。','',
                  '## Ready to Freeze Phase 3B_2?','',
                  '**READY**。本轮 Definition of Done 已满足，技术 blocker 为 0。剩余身份歧义与保守 NOT_FOUND 已明确保留，不伪造确定性；它们属于本阶段允许的降级结果。正式 Freeze 仍等待项目负责人验收，当前未主动冻结。','',
                  '**STOP：不进入 Phase 3B_3。**'])
    (ROOT/'docs/history/phase3b/PHASE3B_2_1_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('PHASE3B_2_1_REPORT.md: READY; pending human acceptance')

if __name__=='__main__':main()
