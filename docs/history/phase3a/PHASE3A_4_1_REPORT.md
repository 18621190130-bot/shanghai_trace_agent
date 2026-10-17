# Phase 3A-4.1 — Interaction Semantics & NLU Robustness

PHASE 3A-4.1 STATUS: **PASS**

Phase 3A: **IMPLEMENTATION_COMPLETE**, **NOT HUMAN_ACCEPTED**。本轮真实 API 调用为 0；需要重新执行人工 Live Acceptance。此前人工 live 尝试反馈是本轮修复依据，不等于本轮已通过 live 验收。未开始 Phase 3B。

## 1. 原 Live 问题根因

原途中协议把 skip/preference/time 更新送入全局 ReplanCoordinator。原 RouteEngine 按预算、组成与候选重新选点，因而可能补点、删掉无关点或改变顺序。这是执行策略与交互语义不匹配。原协议缺少独立 REMOVE、REVISIT、REPLACE、REORDER 与 mutation scope，也把默认剩余时间当成硬预算。

## 2. DeepSeek 理解错误还是协议错误

没有此前失败轮次的原始 provider proposal，不能断言 DeepSeek 当时输出了什么。源码能确认旧命令 grounding 对措辞作规则检查，可能接受 “don't want to visit” 却拒绝同义 “don't want to go”；即使模型理解正确也可能在协议层变成 invalid_command。已访问地点的 must-go 在旧执行层被视为 fulfilled，导致再次访问需求落成 no_change。新 trace 将 provider、解析、语义、解析地点、domain 和执行失败分开；真实语义准确率留给人工 live harness 测量。

## 3. 新 Action Ontology

`TripUtteranceProposal.actions` 支持最多 8 个动作。动作包含 COMPLETE_STOP、SKIP_PLACE、REMOVE_PLACE、ADD_PLACE、ADD_MUST_GO、REPLACE_PLACE、REVISIT_PLACE、MOVE_PLACE_NEXT/BEFORE/AFTER、ADD/REMOVE_INTEREST、ADD/REMOVE_AVOID、SET_TIME_TARGET、SET_HARD_TIME_LIMIT、SET_PACE、FULL_REPLAN、生命周期、五类只读查询、CANCEL，以及 DWELL_LONGER/UNSUPPORTED。

每个动作携带原始 target/reference、secondary target、taxonomy tags、time/pace/position、explicit_replan 等受限字段。`request_matching_insert` 区分“多看一些”与单纯偏好陈述。模型不能输出 POI ID、RouteVersion、visited/skipped 或路线；地点由本地 resolver 绑定。严格完整字段 schema 见 [action_schema.json](../../../examples/trip_interaction/action_schema.json)。

## 4. RouteMutationScope

REMOVE_ONLY、INSERT_ONLY、REPLACE_TARGETED、REORDER_ONLY、PREFERENCE_ADJUST、FULL_REPLAN、READ_ONLY；另外 CORE_PROGRESS 表示完成/开始/终止事实，不代表规划。`RouteMutationService` 是既有 RouteEngine 的局部序列适配器：使用原候选资格、visit profiles、推荐分、几何、步行限制；不修改原 RouteEngine 或评分。

局部动作不调用全局 coordinator、不执行组成补点。只有 FULL_REPLAN 且 explicit_replan=true 才授权全局选点。显式删点可以留下少于三站或空的未来序列；初始生成仍遵循既有最低路线规则。

## 5. Soft / hard time

默认 soft，包括 “I only have one hour left”。保存新的目标截止值，重算估计与超时提醒，保留原未来点；增加时间可以超过初始 180 分钟，不受旧默认预算封顶。硬约束仅由明确 mandatory leave/finish/fit 或授权压缩表达产生。

Hard 压缩先最小化删点数，再最小化既有 VisitPlanner 的 budget fallback 次数，然后比较近似距离与稳定顺序；不引入新 profile。不删本轮明确 ADD/REPLACE 或 must-go，不全局补点。无法满足时返回 state_conflict。已有 hard deadline 不会被随后 soft 更新悄悄取消；payload 同时显示 soft target 与 hard limit。

## 6. Skip semantics

只移除目标并记录 skipped 事实；其他未来点及顺序不变，不补点。追加 RouteVersion、ReplanRecord 和可重放事件。已跳过 ID 不会在后续普通插入/全局重规划中悄悄恢复。

## 7. Add / must-go semantics

普通 ADD 只插入明确地点，保持原序列子序列，不自动变成 must-go。强必去保存 must_go_remaining，可覆盖类别 avoid 的显式例外；不能越过同区、生产可选身份或历史访问排除。Soft 超时给出数字提醒，不删其他点。采用原近似几何选择插入位置；本轮明确加入点受 hard 压缩保护。

## 8. Preference semantics

类别 avoid 只过滤真实 taxonomy tag 匹配的未来点，不补点；强必去例外保留。新增正向偏好或“多看一些”可插入一个匹配生产点并保留已有序列。“仍然想看建筑”且已保存该偏好可以是 no-op。“多看建筑”即使 architecture 已存在也尝试插入；无 eligible 候选返回 not_applicable。

## 9. Replace semantics

明确 “Skip this place and find me another one” 为 REPLACE_TARGETED，替换恰好一个槽位。候选限当前 zone，排除已访问/已跳过/avoid/已在未来序列的点，复用原 tags、role、推荐与几何排序。支持明确命名 replacement。替换本身不伪造 skipped 事实；其他点与顺序不变。

## 10. Reorder semantics

只修改未来序列顺序，支持 next/last/before/after。目标不在未来路线返回 not_applicable，不隐式加入。硬 deadline 下指定顺序不可行返回 conflict，不偷偷恢复旧顺序。reordered_stop_count 比较 retained 子序列位置，新增插入造成的整体偏移不算重排。

## 11. Revisit semantics

REVISIT 明确认出并解析目标；已访问点再次 ADD 也进入 revisit_not_supported，绝不 no_change。当前 TripState 以唯一 POI ID 和全局 visited/skipped 集合表达事实，缺少 occurrence identity。本轮选择明确不支持重复 visit，而不破坏既有事实/重放契约。未执行复访时无状态变动。

## 12. Named POI 与 category

“不要 West Bund Museum”移除该地点，不设置 museum_visit avoid。“不要 museums”才设置类别 avoid。provider prompt 明确区分；若偏好 concept 唯一对应生产实体，本地再收敛为 named action。Category reference 多义时澄清，不按知名度猜。中英文、标点、大小写、已有别名与 Long Museum 简称归一，保留原保守 fuzzy 阈值。

## 13. Negation handling

Provider 解释分句范围；“不要 museums，但仍要 Long Museum”产生 ADD_AVOID + ADD_MUST_GO；“不讨厌 museums”产生 REMOVE_AVOID。代码验证受限动作并保护明确例外，不用关键词扩张器重判整个自然语言句子。58 条语料含否定与例外；mock 能证明处理合规 proposal 的行为，不能证明真实模型必定正确解释。

## 14. Reversal handling

REMOVE_AVOID 移除限制，不自动恢复已删点。普通 REMOVE 可由 ADD 恢复。明确 SKIP 后申请恢复先要求确认，确认后当前契约仍明确返回 skipped_restore_not_supported 并保持历史事实；没有伪装成已恢复。模糊 changed-my-mind 要求澄清。

## 15. Compound utterances

先基于原可见路线解析 references，再依次完成、移除/替换、插入、偏好、重排、时间、明确 full replan。局部多动作在 detached state 上暂存，统一验证、一次 CAS 提交；失败不部分落盘。complete+skip 的全部事实在 core_action_results 中返回。

可选 FULL_REPLAN 是局部提交之后的独立 coordinator 事务；若全局失败，明确报告局部修改已保存并返回其 diff，不声称整个复合动作原子。只读与修改混在一轮返回 ambiguous_intent，多项只读查询则都返回。

## 16. Clarification strategy

缺地点、多义地点、缺时长、不明确意图、skip 恢复进入独立 pending，不修改 TripState。数字/选项字母/唯一地点名回复确定性消费槽位，不再调用 provider。pending 保存 revision，过时返回 stale_state_conflict。查询或 provider/parse 失败不丢弃 pending；cancel 明确取消。

绝对钟点缺可信剩余时长时询问分钟数，不推测当前时间。Stay longer 识别 DWELL_LONGER，询问时长后明确当前动态 dwell 不支持，不把它当预算增加。

## 17. no_change semantics

只用于实际语义 no-op，例如已有普通地点/偏好无需改变。缺目标、不在未来路线、无新增匹配点、不可复访、不支持能力、取消、过时状态及不可行预算均使用各自状态，不能 generic no_change。

## 18. Error taxonomy

| 状态 | 意义 |
| --- | --- |
| provider_error | 原 DeepSeek client 的网络/认证/服务/响应错误，保留 kind |
| parse_error | JSON/格式错误或非法数值；格式修复最多两次解析尝试 |
| invalid_command | 非法协议字段或跨字段 payload，不作为普通措辞兜底 |
| ambiguous_target / ambiguous_intent / needs_duration_clarification | 需要用户补信息 |
| not_applicable | 合法动作无适用目标或当前生命周期不允许 |
| unsupported_action / revisit_not_supported | 明确认识到能力边界 |
| state_conflict / stale_state_conflict | 约束冲突或 CAS/revision 冲突 |
| cancelled | 取消 pending 或明确保留 skipped |

Provider 仍为原 DeepSeekLLMClient，无替换、无 live 失败转 mock。

## 19. NLU trace

两个 CLI 共用 `--trace-nlu`，默认不显示 raw proposal。十阶段：user text、raw proposal、parsed actions、normalized actions、POI resolution、semantic validation、domain validation、mutation scope、execution、route diff/warnings，并显示 failure_stage。脱敏真实密钥和 sk token，禁止 credentials/headers/environment/full system prompt。Why 查询标题为 **Latest route change**，查询不产生新版本；明确修改才显示 Route updated。

## 20. Live eval harness

`tools/evaluation/nlu_live_eval.py` 只执行 proposal 解析、归一与身份比较，不创建 TripState、不调用 RouteEngine。58 例覆盖 REMOVE/ADD/MUST_GO/READ/TIME、复合、反转、重排、否定、复访、替换、偏好、明确全局重规划。每例保存 expected/actual/targets/status/脱敏 trace。

核心五类须 100%，compound/reversal/reorder 须至少 95%。只有完整 58 例、无 NOT_RUN 才计算 acceptance_complete；--limit 仅预览。Provider 故障停止余下调用并标记 NOT_RUN。本轮 [mock 结果](../../../examples/trip_interaction/nlu_mock_eval.json) 58/58；这是 fixtures/schema 检查，**不是 live accuracy**。

## 21. New tests

新增 **78 个测试方法**：59 个端到端局部动作/事务/状态/时间/trace 测试，6 个协议/resolver/安全/harness 测试，以及 13 类语料测试（含 58 个 subcases）。涵盖题述 live 三例，保留子序列、hard 最少 visit-mode 降级、原始计划不可变、事件重放、复合失败回滚、CAS、pending 与查询隔离。见 [测试](../../../tests/test_trip_interaction.py)、[新测试输出](../../../examples/trip_interaction/new_tests.txt)。

## 22. Full regression

**619 tests / OK，49.830 秒**。原 541 个测试方法保留，无删除。旧 Phase3A-3 协议测试显式 legacy_protocol=True，继续检验历史协议；默认 service 和两个 CLI 都用新动作协议。旧 Agent/CLI 中“soft time 必须删点 / skip 应全局重排 / 取消等于 no_change”等过时产品断言已按本轮授权语义更新，不把它们包装成未经改动的旧行为。

证据：[完整测试输出](../../../examples/trip_interaction/full_tests.txt)、[四个局部回归场景](../../../examples/trip_interaction/regression_cases.json)、[连续全旅程 JSON](../../../examples/trip_interaction/full_journey.json)、[CLI trace 文本](../../../examples/trip_interaction/full_journey.txt)。原 examples/trip_agent 历史证据保留。导出复现：`python scripts/export_trip_interaction.py`，纯 offline。

## 23. Production hash

Production59 字节哈希未变：

```text
6fe891c894995df9aaf9c1c8488d085178399e8cf6d22fe84a87c68e28018782
```

72 个既存冻结检查文件中，仅授权修改的 6 个 Trip/Agent 集成模块改变；其余 66 个一致，unexpected_changes=[]。原 RouteEngine、recommendation、VisitPlanner、初始 intent、provider、trip_commands、taxonomy/zone/POI 数据未变。见 [完整性检查](../../../examples/trip_interaction/protected_checks.json)。新增动作模块、CLI 和测试按功能命名，无复制引擎。

## 24. Known limitations

真实 NLU 尚待本轮人工复验；58 条 mock 不能保证任意措辞。复访 occurrence、skip 恢复、动态逐点 dwell 不支持并明确报错。绝对时刻需人工提供剩余分钟。局部 hard 压缩搜索上限 10,000 次 metrics 评估，耗尽时保守返回 conflict。一次“更多”最多加入一个匹配点；有限库存可能无候选。

原唯一 POI/visited/skipped 契约、同区、步行上限继续有效。全局重规划沿用原 composition/minimum；局部显式编辑不会为满足组成而补点。所有距离/时间为既有近似与产品估计，无 GPS、Amap routing、实时开放/天气/人流/票务。未实现 Phase3B、前端或 RAG。

## 25. Manual Live acceptance commands

在项目根目录，已有进程 DEEPSEEK_API_KEY 时：

```powershell
python tools/evaluation/nlu_live_eval.py --live --limit 5
python tools/evaluation/nlu_live_eval.py --live --json > examples/trip_interaction/nlu_live_eval.json
python tools/demos/trip_agent_demo.py --live --trace-nlu
python tools/demos/trip_chat_demo.py --live --trace-nlu
```

`--limit 5` 不代表验收通过；完整 58 例 harness 与真实执行 A–J 都需人工检查。[人工步骤、断言与停止条件](DETAILS_PHASE3A_4_1_LIVE_ACCEPTANCE.md)。最终保持 IMPLEMENTATION_COMPLETE / NOT HUMAN_ACCEPTED，停止等待人工复验。
