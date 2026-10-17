# Phase 3A-4.1 人工 Live Acceptance

当前实现 PASS，Phase3A IMPLEMENTATION_COMPLETE / NOT HUMAN_ACCEPTED。本轮未调用真实 API；需要根据此前人工 live 反馈重新验收。Mock 结果只证明协议与确定性执行，不证明真实模型准确率。以下 live 命令复用原 DeepSeek provider，人工执行时可能产生 API 费用。

## 准备与入口

在 `shanghai_trace_agent` 根目录运行。先在当前进程配置 DEEPSEEK_API_KEY；不要把 key 写进命令文本、截图、仓库或验收日志。已有用户级变量可读取：

```powershell
$env:DEEPSEEK_API_KEY = [Environment]::GetEnvironmentVariable('DEEPSEEK_API_KEY', 'User')
python tools/evaluation/nlu_live_eval.py --live --limit 5
```

5例只是连接/格式预览，acceptance_complete=false。完整解释验收：

```powershell
python tools/evaluation/nlu_live_eval.py --live --json > examples/trip_interaction/nlu_live_eval.json
```

完整58例中 REMOVE/ADD/MUST_GO/READ/TIME 必须100%，compound/reversal/reorder至少95%；检查 expected 与 actual action、target、time mode、tags、position 与明确 full authorization。不得用 mock 58/58 填作 live 结果。Provider 故障后余下为 NOT_RUN，不能算通过；先解决环境问题再手工重跑。

执行验收入口：

```powershell
python tools/demos/trip_agent_demo.py --live --trace-nlu
python tools/demos/trip_chat_demo.py --live --trace-nlu
```

`trip_agent_demo` 是同 session 从初始生成到途中修改的完整入口。`trip_chat_demo` 是既有途中 fixture 入口，两者共享新语义。不要把 mock 精确 fixtures 当作自由语言模型测试。Trace 包含十个阶段及 failure_stage，不输出密钥、headers、环境或完整系统 prompt。

## 建立基线

向 agent 输入：

```text
I have three hours and want architecture, industrial heritage and river views around West Bund.
start
Show me my current route.
```

使用真实 RouteEntryService/RouteEngine 的结果，接受后仍为 PLANNED，显式 start 才开始。离线基线是 TANK Shanghai → Beipiao Wharf Crane → Long Museum；真实结果可能不同，应先检查实际未来列表，不能把缺席地点的 not_applicable 当语义失败。

每个用例前记下 future POI ID 集合/顺序、visited、skipped、version。需要同 session 时使用查询；互相影响的用例使用新进程建立新 session。用 `--json --trace-nlu` 可以取得结构化结果；CLI 显示同名地点与估计。所有操作只涉及已接受 zone 的 production59，不能要求跨区临时发现。

## A — Named REMOVE

如果 West Bund Museum 不在未来路线，先输入 `Add West Bund Museum to my route.` 并确认加入，再输入：

```text
I don't want to go to West Bund Museum anymore.
```

应为 REMOVE_PLACE / REMOVE_ONLY；仅删 West Bund Museum，其他未来点和顺序不变，added=[]，museum_visit 不应加入 avoid，不能 generic invalid_command。普通 REMOVE 不记 skipped。随后明确 ADD 可以恢复。

## B — Skip 不补点

```text
Skip this place.
```

应 SKIP_PLACE / REMOVE_ONLY，仅移除当前逻辑站；该 ID 进入 skipped，未来序列等于原序列去掉该点，不加入替代，append version。不可因为 route composition 不足而补点。查询原计划与 history 验证原始计划未改。

## C — Add 与 strong must-go

选未访问且未跳过的 Long Museum。如果已在未来路线，先普通 `Remove Long Museum from the route.`，不能使用 SKIP，否则测试的是 skipped restore。然后：

```text
I only have one hour left.
Add Long Museum to my route.
```

SET_TIME_TARGET 为60/soft；ADD_PLACE 只插入 Long，原未来子序列不变，不默认 strong must，不删其他点。估计超过60时必须显示估计、目标和正的 overrun；若实际不超时，则不应伪造提醒，可用更短 soft target 重测。

新 session 测 `I definitely want to visit West Bund Museum.`：ADD_MUST_GO，未来原序列保留，must_go_remaining 包含目标；soft 超时仍不删点。

## D — Revisit

逻辑完成 TANK 或实际当前站：`I've finished this stop.`。再使用实际已访问地点名：

```text
I want to visit TANK Shanghai again.
```

应明确 REVISIT_PLACE、revisit_not_supported，不能 no_change/默认fulfilled，也不能偷偷清除 visited。当前版本没有重复 visit occurrence。普通 ADD 已访问点同样明确提示复访限制。

## E — Targeted replacement

新 soft session：

```text
Skip this place and find me another one.
```

应 REPLACE_PLACE / REPLACE_TARGETED，一处删除、一处添加，其他槽位顺序完全一致，无全局补点。候选必须同区、生产可选、未访问/跳过且符合 avoid；无合格候选或约束不可满足可明确 not_applicable/conflict，不能伪造替代。该动作本身不等于独立 SKIP 事实。

## F — Reorder

确认 Long 在未来列表：

```text
Can we go to Long Museum next?
Put Long Museum after Beipiao Wharf Crane.
```

分别 REORDER_ONLY；POI 集合不变，只改变指定位置。目标缺席时 not_applicable，不自动加入。可以再测 move last。Hard 下若顺序超时返回 conflict，不偷偷还原顺序。

## G — Category 与 named POI

在至少一个未来点真实带 museum_visit 的新 session 输入：

```text
I don't want museums anymore.
```

应 ADD_AVOID/museum_visit，只移除未来 tag 匹配点，visited 不变，无补点。与 A 的 named REMOVE 比较，不能因为地点名含 Museum 就扩张为全类别避开。`the museum` 多义时应给地点选项，唯一时可绑定。`this museum` 绑定当前逻辑站，不跳去后面的 museum。

## H — Negation 与 exception

```text
I don't want museums, but I still want Long Museum.
```

应 ADD_AVOID museum_visit + ADD_MUST_GO Long Museum，保留明确 exception，不把否定扩散到正向分句。必须保证 Long 未访问/未跳过，否则域层历史排除先提示。`I don't dislike museums.` 应 REMOVE_AVOID，而非新增 avoid。

## I — Reversal 与 positive preference

```text
Actually museums are fine again.
I still want architecture.
I'd like more architecture.
```

第一句移除 avoid，不恢复已删路线；第二句已保存 architecture 时是真实 no-op；第三句即使已有 tag，也尝试增加一个合格匹配点并保留其他点，没有候选应 not_applicable。普通 removed 点可以通过明确 ADD 恢复。明确 skipped 点申请 ADD 会先确认；当前确认后仍提示 skipped_restore_not_supported，不冒充恢复成功。

## J — Soft / hard 时间

新 session 比较：

```text
I only have one hour left.
I must leave in one hour. Please cut the route to fit.
```

第一句 soft，仅提醒；第二句 hard，允许压缩。先最少改变原 visit modes，再必要时最少删除，保留顺序/强必去/本轮明确加入点；不是全局重新发现。不能满足时 state_conflict 是有效结果。`I have another hour now.` 可以增加 soft 目标而不被初始预算封顶；已有 hard 不会被 soft 悄悄取消。

`I need to leave at five.` 缺可信分钟数时 needs_duration_clarification，不用机器当前时刻猜测。

## Compound / full replan / read / pending

根据实际路线准备适用目标后测试：

```text
Skip this museum, add Long Museum, and I'd like more architecture.
Replan the rest of my route.
Why did you change my route?
What changes have been made to my route?
Show me my original route.
Show all visited places.
```

复合动作应输出多个 actions，先基于原可见路线绑定目标；局部处理一次提交，非法子动作不得半执行。唯有明确全局一句可 FULL_REPLAN。其后的 Why 标题是 Latest route change，读取不能增加 version/revision。历史 diff 包含 retained/removed/added/reordered 数量和 route_preservation_ratio，不把插入引起的位置偏移计作重排。

故意说含糊目标/缺分钟数，确认不修改 TripState。选项数字、字母或唯一地点名直接消费 pending；中途读查询或 provider/parse error 不丢 pending；cancel 为 cancelled。`I want to stay longer here.` 应识别 dwell 意图、询问分钟数，并明确目前不支持逐点动态 dwell，不能改成整体预算或无变化。

## 验收记录与停止条件

保留完整58例 live harness JSON，并逐项记录 A–J 输入、proposal、解析目标、scope、执行状态、before/after ID/顺序、时间提醒及异常阶段。验证原计划、visited/skipped、事件重放不被覆盖；复合 FULL_REPLAN 若后半失败，应明确局部已保存，不能声称整体回滚。

普通合法同义表达不得被措辞正则拦成 invalid_command。No_change 仅是实际 no-op。Trace 不泄露 credential。所有自动回归本轮619通过、Production59哈希一致；人工仍须验收真实提取和真实执行。只有人工完成后才另行决定 HUMAN_ACCEPTED。完成本轮代码后已停止，不进入 Phase3B/GPS/Amap/frontend/RAG/实时数据。
