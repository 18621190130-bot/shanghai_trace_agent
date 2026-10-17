# Phase 3B_1 Freeze

2026-10-05（Asia/Shanghai）开始 Phase 3B_2 前复核：`python -m scripts.run_offline_tests`，679 tests，OK (skipped=1)，83.125s。记录见 `examples/location_baseline_tests.txt`。

`examples/location_awareness/phase3b_1_baseline_manifest.json` 保存当时 src、tests 全部 Python 文件和生产 `data/pois.json` 的 SHA-256。Phase 3A 的 archive / manifest 仍保留。当前工作目录没有 Git 仓库，没有伪造 tag/commit。

冻结边界：Walking DTO / Location、WalkingProvider、WalkingRouteService、route hydration、cache、fallback、Replan 和 RouteVersion 行为不重新设计。全部原有测试及 Core KB 保持原内容。

3B_2 仅将共用 AmapClient 的合法路径从 v3 扩展为 v3/v5，以调用 POI 2.0 的 business 字段；key、HTTP transport、timeout、pacing、错误层级及 v3 行为保持。新位置服务复用原 provider 的官方坐标转换方法，没有第二份转换公式。
