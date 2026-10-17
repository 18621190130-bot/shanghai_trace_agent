# Phase 3A-4.2 — Final Live Acceptance Fixes

PHASE 3A-4.2 STATUS: **PASS**

Phase 3A: **IMPLEMENTATION_COMPLETE / AWAITING FINAL LIVE ACCEPTANCE**。没有自动标记HUMAN_ACCEPTED。本轮live API调用0。范围仅剩余时间语义和state_conflict诊断；完成后停止。

## 1. Remaining-time semantic correction

修正4.1的时间提示：途中用户陈述现实剩余可用时间，映射SET_HARD_TIME_LIMIT；包括“I only have one hour left”与“I have one hour left”。“about”是数量近似，不将现实可用时间变成软偏好。明确的剩余限制会进入原hard压缩。

## 2. Planning time versus remaining time

Initial planning由原RouteEntryService/initial parser处理，未修改。初始三小时仍用于既有规划大小与估计，不因为后续普通ADD而新增hard deadline。ACTIVE_TRIP中的剩余availability与初始planning target区分；底层仍用原soft/hard字段，不新增TripState core语义或时间枚举。

## 3. Soft preference examples

“I'd like to spend about another hour”、 “Let's aim for around one hour”、 “Maybe another hour, but there's no rush”、 “我想再逛大概一个小时”、 “最好控制在一小时左右，不过不用赶”均SET_TIME_TARGET/60/soft。保留其他点与顺序，超目标仅提醒；已有真实hard约束不会被soft悄悄撤销。

## 4. Hard remaining-time examples

“I only have one hour left”与“I can only stay another hour”为60/hard；“I've only got 45 minutes left”为45/hard；“I have another 30 minutes before I need to go”与“最多只能再逛半小时”为30/hard；“我还有四十分钟就要走了”为40/hard。

## 5. DeepSeek prompt / schema changes

`trip_actions.PROMPT`明确Remaining availability→HARD、Preferred duration→SOFT，增加四个简洁few-shot：only hour left、about hour before leaving、wish another hour、another hour no rush。复用现有SET_HARD_TIME_LIMIT/SET_TIME_TARGET和schema，未新增协议字段，provider未修改。

Offline action fixtures及corpus更新同样语义，包括旧复合剩余时间fixtures；历史legacy TripCommand fixtures保持不变。Corpus从58到72例，增加hard与soft对照。真实模型输出仍由原JSON/schema验证，未在live输出后用短语分类器改写action。

## 6. No keyword hack

没有新增 `if 'only' in text`、正则短语分类或大批phrase规则。自然语言仍由DeepSeek语义提取；代码只按结构化action归一time mode。Fixture文本是明确标注的offline数据，不是live分类器。内部压缩异常文本的搜索上限判断只用于诊断搜索耗尽，与自然语言分类无关。

## 7. Hard compression unchanged

`RouteMutationService.compress`完整AST与修复前一致：最小删点数、最少既有visit mode降级、原顺序、原推荐/几何/VisitPlanner；搜索上限10000不变。只在调用失败后计算解释，不改变选点决策或授权。原engine、scoring、visit profiles、initial intent、provider、TripState/Store/Coordinator及taxonomy/roles保持不变。

AST SHA256：`ba377a61afe6894cc5b4279edea223af6e5190f7ed7050c35b5df3cf8dc4adcb`。见[保护检查](../../../examples/trip_final_acceptance/protected_checks.json)。

## 8. Conflict diagnostic schema

Hard冲突结构保存在现有`user_facing_summary.conflict_diagnostics`和`nlu_trace.conflict_diagnostics`，Agent传递原结构，不新增state字段：

```text
constraint_type
hard_limit_minutes
minimum_feasible_minutes
minimum_is_estimate / minimum_basis
protected_stops [{poi_id, name, name_zh, protection_reason, protection_reasons}]
removable_stops [{poi_id, name, name_zh}]
blocking_constraints
reason_code
blocking_reason
```

Minimum复用同一logical origin、原visit profiles/allowed budget fallback、近似geometry与buffer。有保护点时是删除全部optional后的最短保护子序列；无保护点时是最低估计单站，遵守原非空continuation。没有虚构地理/营业/实时事实。新增测试将诊断minimum与原profile所有允许mode及子序列的穷举最小值比较。

## 9. Protected stop rules

只有现有must_go与本轮明确插入/替换保护生效。分别说明`must_go`与`explicitly_added_this_turn`；两者兼具时列出全部原因。不额外发明current_required_stop或explicitly_protected状态。现有contract的current logical stop不自动受保护，因为没有GPS或真实正在参观事实。

## 10. Ordinary removable stop rules

原未来路线成员资格不提供保护。所有普通future stops列入removable_stops；在hard=60下实际初始TANK→Crane→Long三站可删除普通点，缩为合法单站，无refill。Hard=30时同一基线最短仍40分钟，会正确冲突，而不是误报所有原点must-go。

## 11. Conflict reason codes

`must_go_exceeds_limit`：真正must-go子路线本身超限；`protected_stops_exceed_limit`：全部真实保护约束联合超限；`minimum_route_exceeds_limit`：无保护，但最短非空单站也超限；`no_feasible_compression`：搜索上限或明确重排不能删点的冲突，blocking_constraints区分原因。非hard领域冲突保留`other_domain_constraint`，时间minimum未知为null，不伪造预算解释。

搜索耗尽仍沿用原保守失败行为，解释明确“尚未完整检查”，不宣称数学不可行。指定reorder冲突说明估计minimum来自允许removal后的路线，但该reorder操作自身不授权删除；没有修改reorder语义。

## 12. User-facing explanations

普通CLI显示“I can't fit the remaining route into 20 minutes”、最短估计，以及“Long Museum is being kept because you marked it as a must-go”。普通点冲突说明最短单站也超限与非空continuation要求。显示地点名称、分钟与原因，内部POI ID/结构仅在JSON或trace中可见。

同一现有user_facing_summary供两个CLI渲染，无单独模型生成解释。事务失败保持原计划、intent、version和revision不变；诊断解释的是staged proposal的不可行性，而不是声称失败约束已经保存。

## 13. Trace changes

原十阶段保留；冲突时添加`[11] Conflict diagnostics`，包含hard/minimum、protected/removable与blocking_reason。成功轮次不加第11项。继续共用safe_trace脱敏API key/token，禁止headers/system prompt/environment等敏感内容；默认文本不输出结构化diagnostics。

## 14. Regression tests

新增**26项**正式测试：8个英中hard语料、5个soft语料、13个执行/事务/诊断/渲染/保护测试。覆盖remaining hard真实删点，preferred soft不删点，initial180下ADD超过180仍保留原序列并warning，skip/remove无refill，must-go与本轮explicit-add保护，普通30分钟冲突的native minimum=40，current可删，minimum穷举对照，普通renderer与trace11，compression AST及production hash。

原619项测试方法全部保留。更新少量因新授权语义失效的断言：soft测试改用真正preferred-duration句；默认CLI的remaining-time测试断言hard≤60。原full_journey在skip后只剩Long，60/hard不可行，因此保留v1/v2并返回有解释的conflict，再正常完成；不再伪造必有v3。Deep pace+remaining60的旧复合用例minimum超60，改验证冲突与原状态未改。没有删除回归或更改压缩来迎合旧断言。

见[新增测试](../../../tests/test_trip_final_acceptance.py)、[新增测试输出](../../../examples/trip_final_acceptance/new_tests.txt)、[四例before/after证据](../../../examples/trip_final_acceptance/final_cases.json)。新增语料mock通过只能证明预设proposal协议，不能证明自由自然语言理解。

## 15. Full regression

`python -m unittest discover -s tests -t . -q`：**645 tests / OK，72.767秒，0 failures / 0 errors**。见[完整输出](../../../examples/trip_final_acceptance/full_tests.txt)。

NLU-only harness离线72/72，acceptance_complete=true且mock阈值通过，但不是live准确率；本轮live_api_calls=0。见[mock结果](../../../examples/trip_final_acceptance/nlu_mock_eval.json)。原4.1证据目录未覆盖；当前证据单独保存。离线复现：`python examples/trip_final_acceptance/export_evidence.py`。

## 16. Production hash

Production59字节不变：

```text
6fe891c894995df9aaf9c1c8488d085178399e8cf6d22fe84a87c68e28018782
```

44个本轮src/data既存检查文件，仅5个授权语义/fixture/diagnostic/renderer模块改变，39个一致，unexpected_changes=[]。未改POI、roles、taxonomy、RouteEngine或初始规划。Skip/remove/add/must-go/replace/reorder/revisit/full-replan政策不变。

## 17. Final Live acceptance commands

```powershell
python tools/demos/trip_agent_demo.py --live --trace-nlu
python tools/demos/trip_chat_demo.py --live --trace-nlu
python tools/evaluation/nlu_live_eval.py --live --json > examples/trip_final_acceptance/nlu_live_eval.json
```

只需人工最终执行remaining60/hard、preferred60/soft、普通30/hard、must-go20/conflict四例；详见[最终复测](PHASE3A_FINAL_LIVE_ACCEPTANCE.md)。完整NLU72例为可选辅助。当前状态IMPLEMENTATION_COMPLETE / AWAITING FINAL LIVE ACCEPTANCE，未自动HUMAN_ACCEPTED；未进入Phase3B/GPS/Amap/frontend/实时数据/RAG/voice。
