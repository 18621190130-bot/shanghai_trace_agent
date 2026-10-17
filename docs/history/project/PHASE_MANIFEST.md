# Phase Manifest

状态：Phase 3A IMPLEMENTATION_COMPLETE / AWAITING FINAL LIVE ACCEPTANCE，3A-4.2 PASS，未HUMAN_ACCEPTED、不开始Phase3B。新增26测试、完整645通过。Phase 2.5 COMPLETE / FROZEN。Production POI KB = 59 nodes（武康17、老城15、虹口14、西岸13），本轮字节不变。生产文件按功能职责组织；每个共享模块只保留一份。

以下归属依据现存阶段报告和测试记录重建，并非 Git 提交追踪（项目没有 Git 历史）。Introduced/Modified 表示报告能确认的阶段归属，不声称逐行作者或时间戳。

| Shared file / group | Introduced | Modified | 主要能力 |
| --- | --- | --- | --- |
| src/models.py, poi_repository.py, route_engine.py, __init__.py | Phase 1 | Phase 1.5, Phase 2 | 核心模型、数据验证、硬预算/必去、模式时间、负向与候选质量政策 |
| src/recommendation_engine.py, geo_utils.py | Phase 1 | 后续阶段复用；无独立重建 | 标签推荐分、坐标/近似几何 |
| tools/demos/demo.py, tests/helpers.py, tests/test_repository.py, test_recommendation.py, test_route_engine.py, test_cli.py | Phase 1 | Phase 1.5；部分共享测试在 Phase 2 扩展 | 共享 demo 和基础回归 |
| data/pois.json | Phase 1 | Phase 1.5；Phase 2.5正式推广 | 59节点生产KB、已审核Route Role、四区配置与候选provenance |
| src/visit_planner.py, tests/test_visit_calibration.py | Phase 1.5 | Phase 2 复用 | visit_profile、模式选择/降级与停留估计 |
| scripts/calibrate_phase15b.py, export_phase15b_audit.py | Phase 1.5 | 本轮仅来源路径整理 | 历史重建/校准导出；会覆盖运行数据/报告 |
| src/intent_models.py, intent_schema.py, intent_parser.py, intent_adapter.py | Phase 2 | Phase 2 repairs / provider repair | RouteIntent、candidate 严格验证与共享请求转换 |
| src/llm_client.py, mock_examples.py | Phase 2 | Phase 2 provider repair | 真实 DeepSeek、明确 Mock fixtures、JSON 提取及错误诊断 |
| src/clarification.py, feasibility.py, location_resolver.py | Phase 2 | Phase 2 repairs | 多轮字段合并、失败处理、起点解析 |
| src/route_entry.py, surprise_policy.py, route_quality.py, semantic_expansion.py | Phase 2 | Phase 2 repairs / Unified Patch | 三入口、主题选择、质量 gate、语义扩展与最低三站 |
| tools/demos/chat_demo.py, tools/demos/route_entry_demo.py, data/surprise_themes.json | Phase 2 | Phase 2 repairs / provider error 分类 | 根目录验收入口、主题库存 |
| tests/test_phase2*.py, tests/test_deepseek_provider.py | Phase 2 | 各次 repair | 入口、负向、质量、语义、provider 回归；不按 Phase 复制 |
| scripts/export_phase2*.py, diagnose_deepseek.py | Phase 2 | 本轮仅输出/文档路径 | 归档输出复现、真实 smoke 诊断 |

## Phase 1

新增核心：数据 Repository、模型、推荐与 Route Engine、几何工具、共享 demo 及基础测试。能力：确定性原型，必去保留、硬时间/距离预算、失败原因与近似统计。见 [PHASE1](../../phases/PHASE1.md)。

## Phase 1.5

新增 visit_planner 与校准工具/测试；修改共享数据、模型、Repository、Route Engine、demo。能力：27 POI、四区、按模式与节奏估算时间、降级/访问范围、坐标补齐。见 [PHASE1_5](../../phases/PHASE1_5.md)。

## Phase 2

新增三入口、DeepSeek intent、严格 schema、multi-turn clarification、negative preferences、语义扩展与路由质量层；修改共享 Route Engine 的偏好约束及候选质量检查、入口 CLI 与回归。完整 repair 历史和真实 provider 修复见 [PHASE2](../../phases/PHASE2.md)。

当前限制：近似几何、无 Map API/实时开放与票务、有限 POI 库存、库外地址/别名需要澄清、模式时间为产品估计。time utilization 与 richness 不替代硬预算或最低可行要求。

## Phase 2.5

COMPLETE / FROZEN，正式推广59节点。Route Role、Zone Config、POI Pipeline、Candidate provenance均已进入正式生产基线；稳定ID冻结；三项人工删除及display_order连续重排已审计。历史candidate与27节点快照保留。见 [Phase 2.5](../../phases/PHASE2_5.md)、[最终推广报告](../phase2_5/PHASE2_5_FINAL_PROMOTION_REPORT.md)、[Promotion Manifest](../../../data/PHASE2_5_PROMOTION_MANIFEST.json)。

## 文件整理约定

- src/ 保持稳定功能命名，不机械新增职责子包，避免 import 风险。
- data/pois.json 和 surprise_themes.json 为运行数据；data/archive/ 为历史，不复制为多份运行版本。
- tests/ 保留原功能回归，不按 Phase 复制。
- examples/phase1/ 为历史 Phase 1 路线；examples/phase2/ 为所有 Phase 2 契约、模拟及真实 smoke 证据。
- examples/request.json、route_plans.json、poi_catalog.json、manual_routes.txt 为共享/Phase 1.5 兼容文件，保持根目录。
- 根目录阶段报告保留全文；docs/phases/ 为规范阶段入口，明确引用完整历史。
- scripts/ 保持工具入口，仅修正归档路径；历史导出工具可能覆盖证据，正常验收不运行校准/导出。

Phase 3A-1/2/3/4/4.1/4.2：PASS。当前Phase3A为 **IMPLEMENTATION_COMPLETE / AWAITING FINAL LIVE ACCEPTANCE**。4.2只修正remaining availability时间语义和hard诊断；下方历史子阶段保留当时状态。


## Phase 3A-1 — Trip State Core

PASS（仅本子阶段完成；Phase 3A整体未完成）。新增`src/trip_state.py`与`src/trip_store.py`：TripState/事件/版本/Delta验证、InMemoryTripStore/TripService；轻量离线`tools/demos/trip_demo.py`，24个新核心测试。全部403测试通过，Phase2.5 production59节点与冻结能力未变。见 [Phase 3A-1说明](../../phases/PHASE3A_1.md) 和 [报告](../phase3a/PHASE3A_1_REPORT.md)。不实现重规划、LLM delta解析、GPS、地图routing或前端。

## Phase 3A-2 — Deterministic Dynamic Replanning

PASS（仅本子阶段完成；Phase 3A整体未完成）。新增`src/trip_replanning.py`、`tools/demos/replan_demo.py`、34项功能测试；扩展TripState的预算截止值、v2+/record/event重放和全旅程排除，扩展TripStore的revision/CAS。使用原RouteEngine、原intent adapter与途中薄组成适配器；不改核心评分或POI角色。全部437测试通过，64个冻结文件哈希一致，production59保持不变。见 [Phase 3A-2说明](../../phases/PHASE3A_2.md)、[报告](../phase3a/PHASE3A_2_REPORT.md) 与 `examples/trip_replanning/` 四个确定性场景。没有LLM delta、GPS或地图routing；等待人工验收，不开始3A-3。

## Phase 3A-3 — Conversational State Update

PASS（仅本子阶段完成；Phase 3A整体未完成，等待3A-4）。新增`src/trip_commands.py`、`src/trip_conversation.py`、`src/trip_command_fixtures.py`、`tools/demos/trip_chat_demo.py`及69项功能/集成测试。复用现有DeepSeek/Mock provider与JSON validator；受限TripCommandProposal分流Core/Delta/read，独立pending地点澄清，ReplanRecord驱动确定性解释与只读v1/v2/v3历史。TripService仅增薄history/Core CAS接口，Coordinator仅增可选expected_revision；原引擎/评分与production59未变。全部506测试通过。见 [Phase 3A-3说明](../../phases/PHASE3A_3.md)、[报告](../phase3a/PHASE3A_3_REPORT.md) 与`examples/trip_conversation/`证据。默认mock、live显式选择；本次没有live API调用。不启动3A-4/3B/前端/实时信息。

## Phase 3A-4 — Continuous Agent Demo & End-to-End Integration

PASS，Phase3A **IMPLEMENTATION_COMPLETE**。新增TripAgentService、八阶段Session、幂等初始bridge、统一AgentTurnResult、确定性Renderer和连续CLI，35项新集成测试；全部541测试通过。初始路线真实调用原EntryService/RouteEngine，三个入口均可进入Trip；同一session/trip完成v1/v2/v3与最终COMPLETED。初次/途中澄清独立，终态只读，CAS保持。仅扩展planned取消及Conversation可选read_only，不改原引擎/模型provider/production59。见 [说明](../../phases/PHASE3A_4.md)、[报告](../phase3a/PHASE3A_4_REPORT.md)、[人工验收](../phase3a/DETAILS_PHASE3A_MANUAL_ACCEPTANCE.md)、`examples/trip_agent/`。

当时 RouteIntent、RoutePlan、TripState、TripStateDelta、TripCommandProposal、TripTurnResult、AgentTurnResult、TripAgentSession、RouteVersion、ReplanRecord及服务边界标为 **FROZEN FOR PHASE 3B**。后续3A-4.1按人工live反馈授权扩展途中协议；原初始规划与生产数据不变。3B、GPS、地图routing、前端及实时数据未开始。

## Phase 3A-4.1 — Interaction Semantics & NLU Robustness

PASS，Phase3A **IMPLEMENTATION_COMPLETE / NOT HUMAN_ACCEPTED**。新增trip_actions、route_mutation、trip_action_executor、trip_action_rendering、trip_action_fixtures，NLU-only live eval harness及58条验收语料；两个CLI共享局部动作、soft/hard时间与脱敏trace。既有TripState/Store/Coordinator/Conversation/Agent仅扩展集成，不改RouteEngine/评分/VisitPlanner/provider/初始intent/Production59。新增78测试，完整619通过；离线58/58不代表live准确率，本轮live调用0。72个冻结基线文件中6个授权Trip模块改变，其余66个一致。见 [说明](../../phases/PHASE3A_4_1.md)、[报告](../phase3a/PHASE3A_4_1_REPORT.md)、[人工重新验收](../phase3a/DETAILS_PHASE3A_4_1_LIVE_ACCEPTANCE.md)、`examples/trip_interaction/`。完成后停止，不开始Phase3B。

## Phase 3A-4.2 — Final Live Acceptance Fixes

PASS，仅修正remaining availability→hard、preferred duration→soft，以及hard冲突minimum/protected/removable/reason诊断。增加共享trace第11项，复用既有summary传递，无TripState core改动。Compression完整AST不变，RouteEngine/initial intent/provider/Production59及其他mutation政策不变。原619测试保留，新增26，完整645通过；NLU-only corpus72条mock通过不代表live准确率，本轮live调用0。见 [报告](../phase3a/PHASE3A_4_2_REPORT.md)、[最终四例复测](../phase3a/PHASE3A_FINAL_LIVE_ACCEPTANCE.md)、`examples/trip_final_acceptance/`。Phase3A IMPLEMENTATION_COMPLETE / AWAITING FINAL LIVE ACCEPTANCE，未HUMAN_ACCEPTED，完成后停止。
