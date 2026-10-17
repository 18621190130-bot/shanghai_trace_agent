# ShanghaiTrace / Tracemate（沪迹）

当前主目录已撤回 Smart Start，保留后续表单补充修复、四个区块照片和原有功能。双击根目录 **Start_TraceMate.cmd** 启动本地网站；详见 [本地启动说明](../../LOCAL_START.md) 和 [恢复记录](../../maintenance/SMART_START_ROLLBACK.md)。

## 当前前端：Phase 4A，等待人工验收

运行 `python web_server.py`，打开 `http://127.0.0.1:8765`。全新前端使用现有 Core58 和冻结后端，支持三种路线模式、中英文、真实地图和实时信息。图片与文化内容保留给用户。见 [4A 前端报告](../frontend/4A_FRONTEND_REPORT.md) 和 [内容填写指南](../../../frontend/CONTENT_GUIDE.md)。

## 以下为历史阶段记录

当前状态：**Phase 3A IMPLEMENTATION_COMPLETE / AWAITING FINAL LIVE ACCEPTANCE**，3A-1/2/3/4/4.1/4.2均PASS，未标记HUMAN_ACCEPTED，不开始Phase3B。3A-4.2仅修正途中时间语义与冲突解释：现实剩余可用时间为hard，希望的大概时长为soft；冲突显示保护地点/理由、hard limit与最低可行估计。Hard compression、初始规划和Production59保持不变。新增26测试，完整645通过。见 [4.2报告](../phase3a/PHASE3A_4_2_REPORT.md) 与 [最终四例人工复测](../phase3a/PHASE3A_FINAL_LIVE_ACCEPTANCE.md)。Skip/remove不补点，add保持其他序列，明确授权才全局重规划，复访仍明确不支持。入口：`python tools/demos/trip_agent_demo.py --mock --trace-nlu`；初始接受后PLANNED，显式start才开始。`python tools/evaluation/nlu_live_eval.py --mock`的72条离线检查不代表live准确率；本轮live调用0。

**Phase 2.5 COMPLETE / FROZEN**。Production POI KB 为 `data/pois.json`：**59个 route-selectable 节点**，武康—复兴—徐家汇17、老城厢—新天地—外滩15、鲁迅公园—四川北路14、徐汇西岸滨江13。默认CLI使用正式生产基线；本次production内容保持不变。见 [Phase 2.5说明](../../phases/PHASE2_5.md)、[最终推广报告](../phase2_5/PHASE2_5_FINAL_PROMOTION_REPORT.md) 和 [推广Manifest](../../../data/PHASE2_5_PROMOTION_MANIFEST.json)。

历史阶段：Phase 2.5B 初次人工验收未通过，当时修复见 [Repair 报告](../phase2_5/PHASE2_5B_REPAIR_REPORT.md) 与 [Repair 使用说明](../../phases/PHASE2_5B_REPAIR.md)：生产身份、路线节点分组、内部实体和定向语义审核均与旧产物分开保存，；后续审核与最终推广已完成，历史产物继续保留。

## Architecture Overview

生产代码保留稳定的 `src/` 结构，按职责命名，不按 Phase 复制或拆分：

- 意图与契约：`intent_models.py`、`intent_schema.py`、`intent_parser.py`、`intent_adapter.py`、`semantic_expansion.py`。
- 入口与澄清：`route_entry.py`、`clarification.py`、`feasibility.py`、`route_quality.py`、`surprise_policy.py`、`location_resolver.py`。
- Provider：`llm_client.py`；离线 fixtures：`mock_examples.py`。
- 共享规划与数据：`route_engine.py`、`recommendation_engine.py`、`visit_planner.py`、`models.py`、`poi_repository.py`、`geo_utils.py`。
- 旅程与重规划：`trip_state.py`、`trip_store.py`、`trip_replanning.py`；确定性delta适配、途中minimum/composition、事务提交、CAS与版本审计。
- 途中对话：`trip_actions.py`、`trip_action_executor.py`、`route_mutation.py`、`trip_conversation.py`；复用provider的语义动作解析、本地地点解析、局部序列修改、独立pending澄清、只读查询和确定性理由。`trip_commands.py`保留历史兼容协议。
- 连续入口：`trip_agent.py`、`tools/demos/trip_agent_demo.py`；Session状态机连接原初次生成与途中服务，统一结构化响应和确定性展示，独立内存session/Trip事实。

运行数据、taxonomy 与配置保存在 `data/pois.json`，Surprise 主题保存在 `data/surprise_themes.json`。历史知识库在 `data/archive/`，不供引擎默认加载。路径基于项目目录和 pathlib，不依赖本机用户名。

阶段入口：[阶段清单](PHASE_MANIFEST.md)、[Phase 1](../../phases/PHASE1.md)、[Phase 1.5](../../phases/PHASE1_5.md)、[Phase 2](../../phases/PHASE2.md)。完整原报告保留根目录，所有 repair/final patch 与真实 DeepSeek 记录均保留。

## Three Entry Modes

| 入口 | 输入与流程 |
| --- | --- |
| Plan for me | 自然语言经 DeepSeek 提取、严格验证为 RouteIntent，再进入既有澄清和路线流程。 |
| Places in mind | 用户选地点，保留必去约束，检查可行性，再由共享引擎补充节点。 |
| Surprise me | 起点与时间，经固定主题和 seed 选择可行方案。 |

Plan / Surprise 的 Minimum Viable City Walk 至少三站；不足时先进行一次 route-quality clarification。保留窄偏好后仍不足，返回 `insufficient_route`。Places 不套用该三站最低要求。Richness 与 time utilization 是软目标，不强塞弱候选。

## How to Run

Python 3.10+，生产与测试仅使用标准库，无需安装第三方依赖。在项目根目录运行：

```powershell
python tools/demos/chat_demo.py --mode plan_for_me --text "I have two and a half hours. I want local neighborhoods and I'd rather avoid museums."
python tools/demos/route_entry_demo.py --mode places_in_mind --places "Wukang Mansion;Jianyeli" --minutes 180
python tools/demos/route_entry_demo.py --mode surprise_me --start "West Bund" --minutes 180 --seed 42
```

真实 Plan 需要当前进程的 `DEEPSEEK_API_KEY`。已设置 Windows 用户级变量、但当前 PowerShell 尚未继承时，可执行：

```powershell
$env:DEEPSEEK_API_KEY = [Environment]::GetEnvironmentVariable('DEEPSEEK_API_KEY', 'User')
```

不要把 key 写入项目或日志。`DEEPSEEK_MODEL` 可选；`.env.example` 仅作示例，不自动加载。真实提取显式关闭 thinking，保留 1200 token 上限。`DEEPSEEK_DEBUG=1` 可临时输出脱敏诊断，默认关闭。

`tools/demos/route_entry_demo.py --mode plan_for_me` 使用精确 Mock fixtures；它不能证明真实 provider 的自然语言能力。`tools/demos/chat_demo.py` 才调用真实 DeepSeek。非 JSON 模式可以同进程回答澄清；`--json` 不自动读 stdin。

原共享 demo 与文件入口继续有效：

```powershell
python tools/demos/demo.py --request examples/request.json
python tools/demos/demo.py --json
```

## How to Test

```powershell
python -m unittest discover -s tests -t . -q
```

正式测试统一留在 `tests/`，不按 Phase 复制。真实 provider 诊断可用 `python scripts/diagnose_deepseek.py`；会调用收费 API，并覆盖 `examples/phase2/deepseek_provider_smoke.json`。阶段导出脚本仍保留 `scripts/` 位置，Phase 2 输出统一到 `examples/phase2/`。

历史校准脚本 `scripts/calibrate_phase15b.py` 会从归档 v3 重建并覆盖运行数据，不属于日常运行命令。阶段导出脚本可能覆盖历史报告或证据；它们是复现工具，不应当作完整回归命令。

## Current Limitations

- 距离是 Haversine 与固定绕行系数的近似；没有 Map API、道路导航或实测旅行时间。Map API deferred。
- 停留时间是 product planning estimate，未独立计量内部步行、排队；开放状态、票务、实时交通未查询。
- 库外起点与别名可能需要澄清。南京路真实输入可成功提取，但现有 resolver 仍可能要求选择起点区域。
- POI 库存有限；零候选或少于三站时进入质量澄清，不保证扩大主题必然得到完整路线。
- 单次 provider 调用可受网络或服务波动影响。保留真实 provider error 类别；不通过 retry 掩盖截断。

真实 DeepSeek 三例已通过 Parsed Intent 和 route-quality flow；证据见 [真实 smoke JSON](../../../examples/phase2/deepseek_provider_smoke.json)，原始失败见 [baseline](../../../examples/phase2/deepseek_provider_baseline.json)。历史模拟为 Mock，见 [模拟报告](../../../examples/phase2/phase2_plan_for_me_simulations.md)。

## Phase 2.5C candidate acceptance（历史归档）

West Bund 候选库为 `data/pois_phase2_5_candidate.json`（35 POIs，西岸13个独立节点），默认运行库仍为 `data/pois.json`。使用 `POIRepository("data/pois_phase2_5_candidate.json")` 显式加载候选后交给现有 `RouteEntryService` 或 `RouteEngine`；不要用历史校准脚本覆盖生产库。

验收报告：[PHASE2_5C_REPORT.md](../phase2_5/PHASE2_5C_REPORT.md)。离线生成与完整测试：`python scripts/export_phase2_5c.py --run-tests`；可选收费 smoke：`python scripts/export_phase2_5c.py --live-smoke`（最多3次，需已有环境变量；不记录密钥）。

人工 CLI 验收：`tools/demos/chat_demo.py` 与 `tools/demos/route_entry_demo.py` 共用 `--kb production|phase2_5_candidate`。不传参数仍为production；候选文件缺失/无效时明确报错，不回退到production。每次输出显示所选KB、实际POI数量及西岸独立节点数量；`--json`将这三项放在结果对象最前面，保持单个可解析JSON。

在项目目录运行：

```powershell
# 查看 production 或 candidate 地点目录（无 provider 请求）
python tools/demos/route_entry_demo.py --kb production --list-places
python tools/demos/route_entry_demo.py --kb phase2_5_candidate --list-places

# Plan for me：chat_demo 使用已有真实 DeepSeek provider
python tools/demos/chat_demo.py --kb phase2_5_candidate --mode plan_for_me --text "Give me a three-hour West Bund walk with river views and public spaces. No museums."

# Surprise me：直接使用所选KB，无需调用provider
python tools/demos/route_entry_demo.py --kb phase2_5_candidate --mode surprise_me --start "West Bund" --minutes 180 --seed 42

# Places in mind：中文新节点解析为p42 / p43，只保留显式选择
python tools/demos/route_entry_demo.py --kb phase2_5_candidate --mode places_in_mind --places "徐汇滨江海事塔广场;北票码头塔吊" --minutes 120
```

`tools/demos/route_entry_demo.py` 的 Plan for me 仍只支持已有离线mock样本文本；任意自然语言使用 `tools/demos/chat_demo.py`。KB选择不改变provider contract、角色/标签、评分、组成规则或production数据。无需重建candidate即可使用上述人工入口；本次只运行CLI测试，不重新执行采集/enrichment/promotion。

2.5C阶段的Composition只在候选库显式启用的西岸自动规划模式执行，明确地点模式保留用户选择。纯 art + avoid museum_visit 当前没有审定 anchor，返回明确 composition_failure，不添加无关节点。无尽影院已从当前 pilot 拒绝，历史证据留在 `data/poi_pipeline/phase2_5c/identity_mapping_and_archive.json`。这是2.5C历史状态；正式推广以顶部Phase 2.5 Final Promotion为准。

## Phase 3 status

Trip State Core（3A-1）、确定性动态重规划（3A-2）与Conversational State Update（3A-3）已完成，506项测试通过。重规划复用既有RouteEngine，按整段旅程检查minimum/composition，保留原始路线与意图，失败不提交偏好变更，CAS防止覆盖较新进度。Production59与冻结核心保持不变。

```powershell
python tools/demos/replan_demo.py --scenario time_reduced
python tools/demos/replan_demo.py --scenario skip_and_replan
python tools/demos/replan_demo.py --scenario avoid_museums
python tools/demos/replan_demo.py --scenario add_must_go
```

上述确定性demo支持`--json`输出完整before/result/after。途中自然语言CLI默认是固定mock样例，初始路线为cached production fixture，不调用真实API：

```powershell
python tools/demos/trip_chat_demo.py --list-fixtures
python tools/demos/trip_chat_demo.py --mock --text "I only have one hour left."
python tools/demos/trip_chat_demo.py --mock --text "Skip this place." --json
python tools/demos/trip_chat_demo.py --mock
```

固定样例也包括“I'm a little tired.”、“I'd like to see more architecture.”、“I've finished this stop.”、“Why did you change my route?”、“Show me the original route.”与“What changes have been made to my route?”。交互中的地点澄清可选名称/编号；`cancel`取消澄清，`quit`退出。未知mock表达明确报错，不自动联网。

真实DeepSeek仅在显式live模式使用既有进程API key配置（可能产生费用）：

```powershell
python tools/demos/trip_chat_demo.py --live --text "I'm a little tired and I only have one hour left."
python tools/demos/trip_chat_demo.py --live
```

上述记录是 Phase 3A-3 的历史验收说明。Phase 3A 后续阶段已经完成并冻结；当前交付状态以以下 Phase 3B_1 说明及验收报告为准。

## Phase 3B_1：真实步行路线

Phase 3A 冻结记录见 `PHASE3A_FREEZE.md`。RouteEngine、生产 Core KB 及全部原有测试保持不变。真实步行补全由独立 client/provider/service 完成；常规 RouteEntryService、Replan 和局部路线修改已集成，保存到对应 RouteVersion snapshot。

直接 Python 调用可用 `WalkingRoutePlanner(repository)`，或先用原 RouteEngine 规划，再调用 `WalkingRouteService.hydrate_walking_route(plan)`。只在最终 Core POI 顺序确定后查询相邻路段；可获得真实距离、秒数、导航步骤和 GCJ02 `[lng, lat]` geometry。原规划指标独立保留，不以真实时长自动删除或重新规划地点。

高德密钥通过进程环境 `AMAP_WEB_SERVICE_KEY` 注入，不自动加载 `.env`，不读取旧 POI pipeline 的 `AMAP_API_KEY`。无密钥或 provider 故障时返回 `FALLBACK_ESTIMATE`，路线继续可用。读取 walking 数值时必须同时读取状态。已有 start / logical origin 的路线会包含到首站的 approach leg。

默认离线回归（脚本会清除真实高德配置，包含子进程）：

```powershell
python -m scripts.run_offline_tests
```

真实验收（先在进程环境配置 AMAP_WEB_SERVICE_KEY；不要把 key 写入脚本或命令历史）：

```powershell
$env:RUN_LIVE_AMAP_TESTS='1'
python -m scripts.live_walking_acceptance
python -m unittest tests.test_walking_live -v
```

真实验收记录位于 `examples/walking_routing/live_west_bund.json`。接口约定见 `docs/PHASE3B_1_API_CONTRACTS.md`，交付详情见 `PHASE3B_1_REPORT.md`。3B_1 已冻结，后续状态见以下 3B_2 说明。

## Phase 3B_2：位置、到达判断和 POI 动态信息

新增独立只读 `WorldContextService`，提供 `reverse_geocode(location)`、`get_poi_live_info(core_poi_id)`、`check_arrival(location, target_poi_id)`。WGS84 坐标复用 3B_1 官方转换；地址保留 adcode。到达判断使用统一坐标后的 Haversine，默认 ARRIVED≤60m / NEAR≤200m，不调用步行 API，不自动完成或访问 Trip stop。

Core↔高德映射单独保存在 `data/amap_poi_mappings.json`，59 个 Core POI 已完整审计：21 MATCHED、12 AMBIGUOUS、0 NOT_FOUND、26 NOT_APPLICABLE。无法确认的主体不绑定 ID。人工查收清单见 `examples/location_awareness/MAPPING_MANUAL_REVIEW.md`；自动 MATCHED 的 reviewed=false，未经人工确认。

POI live info 保留 address、tel、opentime_today/week、rating、cost、tags、provider type；缺失字段为 None。营业时间按显式上海时间解析可靠当天区间，不能可靠解析时 UNKNOWN。地址与 POI 查询均有 30min TTL/LRU cache，返回安全 unavailable 状态，不覆盖 Core 文化内容或 TripState。

```python
from src.services.world_context_service import WorldContextService
world = WorldContextService.from_environment()
location = {'lat': 31.167682, 'lng': 121.463841, 'coordinate_system': 'GCJ02'}
print(world.reverse_geocode(location).to_dict())
print(world.get_poi_live_info('p28').to_dict())
print(world.check_arrival(location, 'p28').to_dict())
```

默认离线测试仍用 `python -m scripts.run_offline_tests`。在显式 live 配置下可运行 `python -m scripts.match_amap_poi_ids`、`python -m scripts.live_location_acceptance` 或 `python -m unittest tests.test_location_live -v`；只读取进程 AMAP_WEB_SERVICE_KEY，不打印凭据。

冻结记录见 `PHASE3B_1_FREEZE.md`，接口约定见 `docs/PHASE3B_2_API_CONTRACTS.md`，验收报告见 `PHASE3B_2_REPORT.md`。本阶段结束后等待人工查收；没有实现 Nearby、天气、Reality Check、持续 GPS 或 Phase 4A UI。
