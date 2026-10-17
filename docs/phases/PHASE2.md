# Phase 2 — COMPLETE / FROZEN

Phase 2 功能已由用户验收通过。本轮只完成目录整理与阶段归档；没有业务行为变更，也没有开始 Phase 3。

## 归档入口

[PHASE2_DELIVERY_REPORT 完整原报告](../history/phase2/PHASE2_DELIVERY_REPORT.md) 保留全部有效内容，包括 First Repair、Repair 1.1/1.2、Final Repair 1.3、Final Patch、Final Unified Patch 和真实 DeepSeek provider 修复。根目录继续保留完整报告，避免破坏历史导出脚本与外部引用。本文件是该报告的阶段入口，不替代或裁剪历史记录。

## 已验收能力

- 三入口：Plan for me、Places in mind、Surprise me，复用同一共享引擎。
- DeepSeek Intent Extraction：完整 JSON 严格校验；thinking 显式关闭；provider 与 validation 错误分类区分；安全 debug 默认关闭。
- multi-turn clarification：同进程合并已有意图，不丢失约束；JSON 模式保留批处理约定。
- negative preferences 与 must-go 语义保留。
- Semantic Tag Expansion：使用现有 taxonomy，受限扩展和来源信息。
- route quality gate：拒绝弱候选；Minimum Viable City Walk 在 Plan / Surprise 要求至少三站，不靠 filler 达标。
- 不足时一次 route-quality clarification；用户保留窄偏好且仍不足，最终 insufficient_route。零候选建议扩大偏好/区域，不错误建议加时间。
- richness、time utilization soft target 均为软目标，硬预算继续验证。
- approximate geometry limitation：距离与时间只是近似，不是道路导航；Map API deferred。

## 证据

真实 DeepSeek smoke test 已通过：[真实三个输入和输出](../../examples/phase2/deepseek_provider_smoke.json)、[原始截断 baseline](../../examples/phase2/deepseek_provider_baseline.json)。三例都通过 Parsed Intent 并进入路线/质量流程。南京路案例回答既有区域问题；strict 后 insufficient_route 是原路线政策的结果。

历史 Mock 模拟独立标识：[自然语言模拟与输出](../../examples/phase2/phase2_plan_for_me_simulations.md)、[Unified Patch JSON](../../examples/phase2/phase2_unified_patch.json)。Mock 成功不作为真实 API 验证。

本轮最终回归、三个验收入口及整理前后树见 [cleanup record](../history/phase2/PHASE2_CLEANUP.md)；模块历史与限制见 [manifest](../history/project/PHASE_MANIFEST.md)。
