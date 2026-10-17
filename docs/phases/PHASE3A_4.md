# Phase 3A-4 — Continuous Agent Demo & End-to-End Integration

**PHASE 3A-4 STATUS: PASS**。**PHASE 3A STATUS: IMPLEMENTATION_COMPLETE**。人工 live acceptance 尚未执行，不标记 HUMAN_ACCEPTED。完整结果见 [报告](../history/phase3a/PHASE3A_4_REPORT.md)，人工步骤见 [Manual Acceptance](../history/phase3a/DETAILS_PHASE3A_MANUAL_ACCEPTANCE.md)。

## 运行

在项目根目录使用 Python 3.10+；仅标准库，无新依赖。

```powershell
python tools/demos/trip_agent_demo.py --help
python tools/demos/trip_agent_demo.py --list-fixtures
python tools/demos/trip_agent_demo.py --mock
python tools/demos/trip_agent_demo.py --scenario full_journey
python tools/demos/trip_agent_demo.py --scenario full_journey --json
python tools/demos/trip_agent_demo.py --mock --auto-start
python -m unittest tests.test_trip_agent -q
python -m unittest discover -s tests -t . -q
```

默认 MOCK，只有 exact fixture extraction，没有网络回退。交互第一句是初次规划；初始路线由真实 RouteEntryService / RouteEngine 生成，没有缓存路线输入。普通模式直接显示地点名称、澄清选项、版本、进度和修改理由；`--json`输出每轮完整结构化契约，scenario 则输出完整 trace。

初次可输入 `I want to explore Shanghai.`，再回答 `Three hours, mainly architecture and local life.`。初次字段/质量澄清属于 RouteEntryService；途中地点澄清属于 ConversationalTripService，两者独立。默认接受路线后停在 PLANNED，输入 `start` 才开始；`--auto-start`仅是显式选择。未开始时允许查看或取消，偏好重规划明确拒绝。

## 连续生命周期

Session 使用 NEW → PLANNING → ROUTE_READY → ACTIVE_TRIP → COMPLETED / ABANDONED；初始和途中澄清分别为 AWAITING_INITIAL_CLARIFICATION / AWAITING_TRIP_CLARIFICATION。Session只保存编排上下文，TripStore保存所有行程事实，每轮重新读取。Store使用 defensive copies；退出进程后数据丢失，不实现数据库。

成功且通过入口质量检查的 RoutePlan 才通过幂等 bridge 创建 TripState。Complete/skip/delta/read 均委托原服务；原引擎仍是唯一路线生成权威。版本、事件、ReplanRecord 和 CAS 仍由已有 Trip 层控制。完成/放弃后只读、不重开；放弃不伪造 visited/skipped。取消 PLANNED 使用新增独立取消事件，不伪造 trip_started。

`full_journey`使用 West Bund 的明确偏好输入。真实初始路线为 TANK Shanghai → Beipiao Wharf Crane → Long Museum；完成首站、skip并生成v2、缩短60分钟生成v3、why/history/original查询、完成剩余站点。全过程同一session/trip。required architecture/local-neighborhood 示例也通过初始生成测试；该区域的60分钟结果可能因真实composition约束失败，不伪造成功。

## 冻结与限制

**FROZEN FOR PHASE 3B**：RouteIntent、RoutePlan、TripState、TripStateDelta、TripCommandProposal、TripTurnResult、AgentTurnResult、TripAgentSession、RouteVersion、ReplanRecord及现有服务边界。本次冻结是实现交付契约；HUMAN_ACCEPTED / FROZEN仍等待人工live验收。

35项新集成测试，合计541项全部通过。Production59及原RouteEngine/parser/provider/zone配置不变。当前站点为逻辑计划站点，不是GPS；距离/耗时仍是原引擎估算。remaining_minutes仅随明确时间更新变化，complete不会自动计时；completed后仍可剩余预算。没有实时营业/票务、地图routing、前端、RAG、voice或Phase3B实现。
