# Phase 3A 最终人工 Live Acceptance — 3A-4.2

当前 Phase3A IMPLEMENTATION_COMPLETE / AWAITING FINAL LIVE ACCEPTANCE，尚未 HUMAN_ACCEPTED。本轮自动回归645项全部通过，真实API调用0。这里只复测两个修复方向的四个 case；4.1其余交互语义保持不变。

在项目根目录，先确保当前进程已有 DEEPSEEK_API_KEY。不要把密钥写入仓库、命令文本或日志。Live 会调用原 DeepSeek provider，可能收费：

```powershell
python tools/demos/trip_agent_demo.py --live --trace-nlu
```

每个 case 用独立进程/session，输入初始规划：

```text
I have three hours and want architecture, industrial heritage and river views around West Bund.
start
Show me my current route.
```

初始生成保持原行为。先记录实际未来地点/顺序/估计，真实生成可能与mock不同。未开始时不允许途中修改。当前逻辑站只是可执行未来点，不因为在路线里就受保护；这里没有GPS或真实“正在参观”的状态。

## Case 1 — 现实剩余时间为 hard

```text
I only have one hour left.
```

查看 raw/normalized action：SET_HARD_TIME_LIMIT / 60 / hard。若剩余估计大于60，应进入既有局部压缩，必要时删除普通未来点，保留剩余顺序，不补点，不悄悄删除must-go。压缩后估计≤60；本来就≤60则不应为了测试制造删除。

如果保护地点或最短合法非空路线本身超限，可以 state_conflict，但必须明确给出原因和数字。离线实际初始169.3分钟可缩到60以内；真实测试以当前路线为准。

## Case 2 — 希望时长为 soft

```text
I'd like to spend about another hour, but there's no rush.
```

应 SET_TIME_TARGET / 60 / soft，其他未来ID集合和顺序不变，不能自动删点。估计超60时显示目标、预计时长和超时提醒；不超时不伪造warning。请从新session测试，避免Case1已保存的hard limit影响结果。

## Case 3 — 普通点允许删除

确认没有must-go，再输入：

```text
I must leave in 30 minutes.
```

应 hard=30，尝试删除普通future stops，而不是把原路线所有点当protected。若能保留合法非空路线≤30则提交。如果最短路线仍>30，允许state_conflict，但diagnostics必须protected_stops=[]，普通点列在removable_stops，明确minimum_feasible_minutes与hard_limit_minutes。

现有离线基线最短单站估计为40分钟，因此这个具体基线30分钟会冲突，这是正确结果。可在同一未变状态再用 `I have one hour left.` 验证普通点确实可删并成功压缩。不要为了让30分钟强行成功修改原visit profiles、buffer或把路线清空。

## Case 4 — 真实 must-go 冲突

新session，确认Long Museum位于当前zone且未访问/跳过：

```text
Long Museum is a must-go.
I only have 20 minutes left.
```

第一句须ADD_MUST_GO且保存真实必去；不能仅凭地点原在路线里声称它受保护。第二句hard=20；如果Long最短可行估计>20，应state_conflict，未来计划/intent/版本/revision不提交半修改。

普通CLI必须说出Long Museum受保护因为must-go、hard为20，以及最短估计多少分钟。`[11] Conflict diagnostics`至少包含constraint_type、hard_limit_minutes、minimum_feasible_minutes、protected_stops含protection_reason、removable_stops、blocking_constraints、reason_code/blocking_reason。不能只显示“required destinations”。若真实生成已经有别的must-go，也应准确列出其保护理由。

## 验收记录

记录四例的输入、raw/normalized actions、before/after ID与顺序、状态、时间数字和冲突trace。不得泄露API key/headers/system prompt/environment。只读Why仍为Latest route change，不产生新版本；只有成功编辑显示Route updated。

可选完整NLU-only corpus复验（72例；mock不是live准确率）：

```powershell
python tools/evaluation/nlu_live_eval.py --live --limit 5
python tools/evaluation/nlu_live_eval.py --live --json > examples/trip_final_acceptance/nlu_live_eval.json
```

`--limit`只是预览，不算完整验收；provider故障后NOT_RUN不算通过。核心REMOVE/ADD/MUST_GO/READ/TIME需100%，compound/reversal/reorder≥95%。也可使用共享途中入口 `python tools/demos/trip_chat_demo.py --live --trace-nlu` 复验time/diagnostics。

人工完成这四例后再明确决定是否HUMAN_ACCEPTED；当前停在AWAITING FINAL LIVE ACCEPTANCE，不进入Phase3B、GPS、Amap、前端或实时功能。
