# Phase 3A-4 — Continuous Agent Demo & End-to-End Integration

**PHASE 3A-4 STATUS: PASS**

**PHASE 3A STATUS: IMPLEMENTATION_COMPLETE**

2026-10-05。35项新增集成测试＋原506项回归＝541项全部通过。Production59保持不变。没有live API调用；人工验收准备完成，**HUMAN_ACCEPTED尚未确认**。

## 1. Existing subsystem audit

原RouteEntryService负责IntentParser、字段澄清、RouteQuality、三个入口和RouteEngine；TripState/TripService负责不可变original、进度、事件、版本与CAS；ReplanningCoordinator负责薄适配和事务重规划；ConversationalTripService负责命令/地点澄清和确定性解释。本次复用这些权威，不增加路线算法。

## 2. Continuous Agent architecture

TripAgentService连接初始入口与途中服务。自然语言→原provider→原初次解析/生成→幂等bridge→原Trip生命周期→原命令/Core/Coordinator→AgentTurnResult→确定性Renderer。初次extract fixture只返回意图候选，初始RouteEngine真实运行。

## 3. Session state machine

NEW、PLANNING、AWAITING_INITIAL_CLARIFICATION、ROUTE_READY、ACTIVE_TRIP、AWAITING_TRIP_CLARIFICATION、COMPLETED、ABANDONED。Session持有初次planning/pending和trip_id，不复制visited/skipped或路线历史。每轮加载TripStore派生阶段；终态清除途中pending。SessionStore CRUD均防御复制。

## 4. Initial planning integration

真实调用entry.parse_plan / entry.generate，success且plan.success才创建Trip。错误、不足和未完成澄清不创建。required architecture/local-neighborhood初句测试成功。三入口共享bridge；Places/Surprise通过既有RouteIntent入口进入，无新增聊天协议。

## 5. Initial clarification integration

字段和质量澄清继续用原入口，质量保留typed EntryResult上下文。两个待答字段的自然语言复合回答一次提取，仅合并正在询问的字段，再交既有ClarificationLayer验证。`I want to explore Shanghai.`→`Three hours, mainly architecture and local life.`成功。取消初次澄清无Trip；strict不足仍拒绝，不跳过minimum。

## 6. RoutePlan → TripState bridge

InitialPlanToTripBridge保留original_route/original_intent，稳定session派生trip_id保证重复接受相同计划幂等；不同计划不能覆盖既有Trip。比较使用JSON规范化snapshot。初始只有v1、PLANNED，未伪造start。

## 7. Start-trip behavior

显式start调用原Core。重复start为no_change，保持进度/时间/历史。--auto-start只在显式开启后发起独立start。未开始偏好重规划拒绝，查看允许。新增cancel_planned_trip / planned_trip_cancelled支持取消未开始行程，原active-only abandon行为保持兼容。

## 8. Active conversation integration

同一session/trip每轮调用原ConversationalTripService一次，按原schema分流Core、Delta、read。新鲜TripStore状态和expected_revision保护继续生效；stale冲突返回最新进度并提示基于最新路线重试，不覆盖已有变化。

## 9. Trip clarification integration

原独立pending管理地点歧义；名称/编号/B确认，不要求POI ID，不再调用provider。cancel仅清pending、Trip不变；stale确认被拒绝。与初次澄清不共享上下文。

## 10. Replanning integration

复用原Coordinator及ContinuationRouteEngine薄组成适配，仍由原RouteEngine生成。复合预算/节奏/avoid一次delta一次重规划；同区must-go成功；不可行delta不提交。skip先保存Core事实，后续失败仍保留skip而不提交偏好。未改角色、scoring、taxonomy或composition要求。

## 11. Route-change explanation

仅已commit结果标route_updated。旧新版本、原因、预算、added/removed/kept、下一逻辑站点与remaining均来自原记录/解释；不调用模型改写、不编造理由。普通Renderer展示名称和版本，JSON保留完整审计字段。

## 12. Route history

只读Core历史展示v1/v2/v3路线快照、预算与原因，按原版本顺序。query不会增加Trip事件、版本或运行RouteEngine。why读取最近已提交记录。

## 13. Original/current route behavior

原始路线保持v1不可变；current显示active快照和remaining，已visited/skipped不再进入后续候选。最后active路线可以包含刚完成的站点，remaining另行计算，不重写历史来删除完成站。

## 14. Completion behavior

complete显示completed_stop、next_stop、remaining_count/minutes/status。最后一站自动COMPLETED，附总结。终态只读查询可用，变更/重开拒绝。complete不自动扣时间，这是原Core语义，预算仅随明确时间更新变化。

## 15. Abandon behavior

active end-trip调用原abandon；planned cancel调用独立取消。终态总结仍可读。剩余站点不伪造visited/skipped，原路线、版本与已完成事实保留。

## 16. AgentTurnResult contract

统一status、session_phase、message_type、session_id/trip_id、planning_result、trip_turn_result、route、clarification、trip_status、user_facing_summary、available_actions、progress、trip_summary、read_result、route_updated、replan_explanation、route_change、error_code。progress为当前逻辑进度；route_change包含旧/新版本和所有结构化修改事实。

## 17. Mock mode

默认明确MOCK，exact fixtures仅模拟LLM extraction。--list-fixtures列全部支持输入；未知措辞provider_error提示mock限制和显式live选项，绝不网络fallback。无cached RoutePlan。--json提供场景trace或逐轮JSON，--auto-start显式可选。

## 18. Live mode

--live复用DeepSeekLLMClient和已有受限schemas；环境缺key返回configuration_error且不访问网络。初次RouteIntentCandidate与途中TripCommandProposal按阶段选择，route/explanation不由LLM生成。提供[人工验收文件](DETAILS_PHASE3A_MANUAL_ACCEPTANCE.md)；本阶段live调用0次、API费用0；不能宣称live passed。

## 19. Full_journey demo

`python tools/demos/trip_agent_demo.py --scenario full_journey --json`，初始真实West Bund路线TANK Shanghai→Beipiao Wharf Crane→Long Museum。完成TANK、skip Crane生成v2、60分钟生成v3、why/history/original、完成剩余West Bund Museum及West Bund Art Center、COMPLETED。所有turn同一session/trip，original始终一致。证据：[JSON](../../../examples/trip_agent/full_journey.json)、[普通输出](../../../examples/trip_agent/full_journey.txt)。初句选择明确西岸是为了真实可行的连续链路；required建筑/街区输入另测成功，不放宽其60分钟composition_gap。

## 20. Integration tests

新增35项高价值测试覆盖真实initial engine、required初句、复合初次澄清、取消/quality strict、初次失败重试、幂等bridge、start重复、planned操作保护、三入口生命周期、complete结构、skip/失败、同区must-go、复合delta、trip确认/cancel/stale、v1v2v3同session、原路线/只读、完成/放弃终态、provider异常、CAS provider竞争、fresh-store、Session复制/CRUD、无keylive无网络、CLI scenario/auto-start、production hash。

## 21. Total regression

`python -m unittest discover -s tests -t . -q`：**541 tests，OK，0 failures / 0 errors**，原506项原样保留并通过。[全量输出](../../../examples/trip_agent/full_tests.txt)。不运行会重写历史数据的export/promotion脚本，也不调用收费smoke。

## 22. Production integrity

Production59不变，West Bund13不变；POI SHA256：`6fe891c894995df9aaf9c1c8488d085178399e8cf6d22fe84a87c68e28018782`。70个既有source/data基线文件中，仅trip_state、trip_store、trip_conversation三处必要扩展有变化，其余67文件哈希一致。[保护证据](../../../examples/trip_agent/protected_checks.json)。原引擎、parser、provider、POI、zone config未修改。

## 23. Files modified

新增src/trip_agent.py、src/trip_agent_fixtures.py、tools/demos/trip_agent_demo.py、tests/test_trip_agent.py、docs/phases/PHASE3A_4.md、docs/PHASE3A_MANUAL_ACCEPTANCE.md、本报告、examples/trip_agent证据。修改TripState/TripService仅加入planned取消及重放，ConversationalTripService仅加入默认关闭的read_only保护；README和PHASE_MANIFEST更新当前阶段入口。

## 24. Known limitations

内存session退出即丢失；非数据库持久化。当前站点是计划逻辑位置，非GPS。距离/时间沿用近似引擎；实际道路、地图、off-route、实时营业/天气/票务均未实现。库存/组成/预算冲突真实返回失败。Mock非自由语言模型，live提取结果及provider可靠性必须人工验证。SessionStore不提供多进程事务；Trip写入CAS仍保护既有行程数据。

## 25. Phase 3A final status

3A-1/2/3/4实现完成，3A-4 PASS，**IMPLEMENTATION_COMPLETE**。契约与职责边界 **FROZEN FOR PHASE 3B**：RouteIntent/RoutePlan/TripState/TripStateDelta/TripCommandProposal/TripTurnResult/AgentTurnResult/TripAgentSession/RouteVersion/ReplanRecord，以及原Core、Coordinator、Conversation、Entry服务边界。此标记是实现契约冻结；人工live验收通过前不得写HUMAN_ACCEPTED或FULLY ACCEPTED。

## 26. Recommendation for Phase 3B

先按人工验收文档使用`python tools/demos/trip_agent_demo.py --live`确认真实同session端到端行为，记录结果。通过并获得后续授权后，Phase3B再引入真实位置和Amap walking routing，用既有契约承载结果。本次到此停止，未实现3B、前端或任何实时能力。
