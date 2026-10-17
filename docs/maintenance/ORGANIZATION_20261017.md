# 项目目录整理记录

日期：2026-10-17。目的：在初始化 Git 前建立清晰目录，保留现有网站功能和历史证据。

## 整理结果

- 当前运行代码仍在根目录的 `src/`、`frontend/`、`data/`、`web_server.py`，启动入口仍为 `Start_TraceMate.cmd` 和 `start_local.py`。
- 根目录阶段报告按阶段迁入 `docs/history/`；使用说明迁入 `docs/LOCAL_START.md`，接口约定迁入 `docs/contracts/`。历史同名但内容不同的验收文档用 `DETAILS_` 前缀保留，没有合并覆盖。
- 原 README 保留为 `docs/history/project/README_before_cleanup.md`，新 README 描述当前功能、目录和启动方式。历史数字、状态和限制以其当时的阶段为背景阅读。
- 7 个演示入口迁入 `tools/demos/`，自然语言评估入口迁入 `tools/evaluation/`；相互导入、测试 Mock 目标、子进程命令和历史导出脚本已适配。
- 原始照片、Word 文案和设计参考迁入 `materials/`；网站图片和文化内容仍使用原生产路径。导入脚本已适配新的素材来源目录。
- 移除整个 Cloudflare 临时部署目录，包括可执行文件、隧道脚本、临时地址、PID、日志及部署检查截图；关闭了占用这些文件的遗留隧道和临时网站进程。
- 清理运行日志、PID 和可再生成的 Python 缓存；历史 CLI 输出、审核数据、冻结证据和验收截图继续保留。`data/poi_pipeline/semantic/latest_run.log` 是本次移除的流水线运行日志，业务 JSON 未改。
- `.gitignore` 补充运行输出、缓存、虚拟环境、本机编辑器配置和旧临时部署目录；继续忽略 `.env`，保留 `.env.example`。原始素材和实际网站资源不被忽略。
- 将外层已有的 Testing Policy 原样保存为项目根目录 `AGENTS.md`，供后续 Git 管理保留。

## 旧副本

`versions/before-smart-start` 中的运行代码、数据和页面资源已先与当前主目录逐字节核对一致。清除其隧道日志等临时文件后压缩归档，ZIP 校验通过，原重复目录已移除。

归档位置位于本项目文件夹外：`../TraceMate_before_smart_start_snapshot_20261017.zip`，约 66 MiB。此路径以项目根目录为参照。归档不参与网站运行，也不进入本项目 Git 提交范围。

之前撤回 Smart Start 的独立备份 `../TraceMate_before_SmartStart_rollback_20261016.zip` 未改动。

## 功能与文件校验

- 824 个运行源码、业务数据和页面资源文件与整理前基线 SHA-256 一致。校验不包含移走的文档、被清理的缓存和运行日志。
- 286 项主要相关后端测试通过；补充 CLI/导入检查中的 104 项通过，另外两项旧测试按现有 Places in mind 不强制时长的要求修订后通过，共 392 项。
- 24 项前端测试通过。
- 浏览器检查通过：封面及 8 张照片、规划入口、4 张区块照片、区块内地点选择、58 个图鉴地点、Logo 返回封面、手机宽度无横向溢出、无 JavaScript 错误。
- Windows 双击入口参数检查通过；本地启动服务就绪检查通过。
- 素材导入流程以禁用写入和复制的方式验证：8 张封面图、22 张 Anchor 图、22 份 Cultural Bridge、58 份观察提示均能读取，没有重新导入或改写生产内容。
- Python 语法检查通过；没有在项目文件中发现当前环境配置的真实 API 密钥值。
- 未运行整个历史回归，也没有进行线上 LLM 或高德数据 API 验收。

完整迁移对照和文件校验清单见 [organization_inventory.json](organization_inventory.json)。

## 后续入口

- 网站：[根目录 README](../../README.md)
- 文档：[docs/INDEX.md](../INDEX.md)
- 工具：[tools/README.md](../../tools/README.md)
- 素材：[materials/README.md](../../materials/README.md)

本次未初始化 Git、未创建提交、未配置新的公网部署。
