# Phase 3A Freeze

冻结日期：2026-10-05（Asia/Shanghai）。Phase 3B 当前仅执行 3B_1。

冻结前完整验证：设置 `PYTHONUTF8=1` 后，`python -m unittest discover -s tests -t . -q`，645 tests，OK，74.437s。原始记录：`examples/phase3a_freeze_baseline_tests.txt`。UTF-8 是 Windows 子进程 JSON 输出的运行条件；未修改测试预期。

当前项目及其父工作目录不是 Git 仓库，因此没有伪造 commit/tag。用 `examples/phase3a_freeze/phase3a_baseline.zip` 保存源码、数据和文档冻结快照；`manifest.json` 记录每个文件的 SHA-256。快照排除 .env、.env.example、缓存及历史 examples。不得重新运行脚本覆盖基线。

必须保持：

- skip 只跳过指定地点，不自动补地点；remove_place 只删除用户指定地点。
- must-go 允许超过软预算，提示风险，不擅自删除其他地点；已有显式硬期限行为保持。
- revisit / again 的现有处理保持。
- TripState、RouteVersion、ReplanRecord、CAS / state_revision 行为保持。
- Replan 保存新版本，旧 route snapshot 不变。
- 外部 API 失败不阻止有效路线和新版本保存，不泄漏凭据。
- 原有 Phase 3A 测试文件和预期不修改；生产 Core KB 不修改。
- Route Engine、距离工具、候选搜索、打分、排序和组成逻辑保持冻结版本；真实步行数据在外围服务添加。
