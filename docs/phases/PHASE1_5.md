# Phase 1.5 — POI 与访问模式校准

主要能力：以 visit_profile 替代单一 recommended_stay；walk_stop / full_visit 与 quick / standard / deep；27 POI、四区、显示编号、坐标与访问范围；受支持的模式降级、票务/可用性请求约束。时间属于产品估计，待人工校准模式继续标注。

完整报告保留于 [PHASE15B_CALIBRATION_REPORT](../history/phase1/PHASE15B_CALIBRATION_REPORT.md)。当前 POI/taxonomy/配置保存在 [data/pois.json](../../data/pois.json)；地点目录、五条校准路线与共享 request 示例保留在 examples 根目录，以保持原 demo 与正式测试命令兼容。历史来源知识库移至 data/archive/，校准脚本仅调整来源路径。

模块归属与跨阶段修改见 [PHASE_MANIFEST](../history/project/PHASE_MANIFEST.md)。
