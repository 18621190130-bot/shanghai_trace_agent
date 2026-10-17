# 维护与验收脚本

这些脚本保留现有位置，方便维护现有数据流水线和复现阶段产物。普通网站运行不需要执行它们。

| 类型 | 例子 | 使用目的 |
| --- | --- | --- |
| 审核与检查 | `audit_*`、`verify_*`、`check_*` | 检查数据或页面；是否读取实时接口以脚本参数为准 |
| 页面检查 | `test_*.cjs`、`accept_*.cjs` | 需要 Node.js、Playwright 和脚本指定端口的网站；部分是历史界面验收 |
| 图片与文案 | `enrich_poi_images.py`、`import_editorial_content.py` | enrichment、审核候选或导入已提供的内容 |
| 历史导出 | `export_*`、`write_*`、`report_*` | 复现报告及审核文件；报告输出路径已适配归档目录 |
| 数据变更 | `calibrate_*`、`promote_*`、`repair_*`、`finalize_*`、`collect_*`、`build_*` | 历史采集、校准、推广和配置生成 |

数据变更脚本可能覆盖 `data/` 的内容，不应作为普通启动或默认回归步骤。历史浏览器脚本中的端口、预期图片状态和界面结构对应其当时的验收阶段，运行前应核对。

`import_editorial_content.py` 已改从 `materials/` 读取原始图片和 Word 文案；网站实际资源位置没有改变。CLI 演示已迁至 `tools/`，本目录中的相关导入也已更新。
