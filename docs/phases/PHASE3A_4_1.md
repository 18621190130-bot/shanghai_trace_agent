# Phase 3A-4.1 — Interaction Semantics & NLU Robustness

实现 PASS；Phase3A IMPLEMENTATION_COMPLETE / NOT HUMAN_ACCEPTED。Production59 与原 RouteEngine/provider/初始 intent 不变。默认途中对话现使用 action ontology；历史 TripCommandProposal 仅供显式 legacy_protocol=True 兼容测试。

途中修改遵循 Minimal Change First：SKIP/REMOVE 不补点；ADD/MUST_GO 保持其他点和顺序；REPLACE 恰好一处；REORDER 仅重排。MORE interest 可以插入一个符合偏好的点；REMOVE_AVOID 不自动恢复旧路线。完整重规划必须明确 FULL_REPLAN/explicit_replan=true。

时间默认 soft，显示估计/目标/超时数字而不删点。明确 hard 才允许最少删点、最少既有 visit-mode 降级；不能容纳明确要求加入的点或 must-go 时返回冲突。Revisit 和 skipped restore 当前明确不支持，不返回 no_change。

```powershell
python tools/demos/trip_agent_demo.py --mock --trace-nlu
python tools/demos/trip_agent_demo.py --scenario full_journey --trace-nlu
python tools/demos/trip_chat_demo.py --mock --trace-nlu
python tools/evaluation/nlu_live_eval.py --mock
python -m unittest discover -s tests -t . -q
```

两个 CLI 共用解析、执行和脱敏 trace。普通运行不显示原始 proposal。直接使用名称查询未来/原始/历史路线；Why 标题为 Latest route change，查询不修改状态。

新增共享功能文件：trip_actions、route_mutation、trip_action_executor、trip_action_rendering、trip_action_fixtures。既有 TripState 新增派生 route mutation 提交及时间政策；TripStore 使用 revision/CAS。局部复合一次提交；可选 full replan 另一个事务。

新增78测试，完整619通过。58条离线语料全部通过，但不代表模型真实理解准确率。见 [完整报告](../history/phase3a/PHASE3A_4_1_REPORT.md)、[人工 live 验收](../history/phase3a/DETAILS_PHASE3A_4_1_LIVE_ACCEPTANCE.md) 与 [独立证据目录](../../examples/trip_interaction)。不开始 Phase3B。
