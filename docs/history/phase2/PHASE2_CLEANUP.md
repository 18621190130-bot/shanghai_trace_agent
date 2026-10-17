# Phase 2 Cleanup Record — 2026-10-04

Phase 2 COMPLETE / FROZEN。功能已验收；本轮仅归档、目录整理及最小工具路径修复。

## 整理前审计

生产：src/*.py，根目录三个 demo；测试：tests/；运行数据：data/pois.json 与 surprise_themes.json。历史来源：三份根目录知识库、data/archive/pois_phase1.json。历史阶段报告全部保留完整内容，只调整迁移产物的文档引用。Phase 2 simulation 与 diagnostics 属于证据，不是废弃文件，全部保留。

没有确认可删除的业务代码。根目录和 examples 下的 simulation Markdown SHA-256 完全一致，删除根目录副本，保留归档版本。缓存 __pycache__/ 与 *.pyc 已被 .gitignore 忽略，测试会再生成，本轮未删除。外层项目的 zip、notebook、问卷等文件未触碰。

完整整理前文件树（忽略可再生缓存）：

```text
.env.example
.gitignore
tools/demos/chat_demo.py
CONTEXT.md
data/
data/archive/
data/archive/pois_phase1.json
data/pois.json
data/surprise_themes.json
tools/demos/demo.py
EXAMPLE_REVIEW.md
examples/
examples/archive/
examples/archive/route_plans_phase1.json
examples/clarification.schema.json
examples/deepseek_provider_baseline.json
examples/deepseek_provider_smoke.json
examples/intent_system_prompt.txt
examples/llm_candidate.schema.json
examples/manual_routes.txt
examples/phase2_first_repair.json
examples/phase2_first_repair_cli.txt
examples/phase2_first_repair_routes.txt
examples/phase2_manual_routes.txt
examples/phase2_plan_for_me_simulations.md
examples/phase2_repair11.json
examples/phase2_repair11_cli.txt
examples/phase2_repair12.json
examples/phase2_repair12_cli.txt
examples/phase2_repair13.json
examples/phase2_repair13_cli.txt
examples/phase2_routes.json
examples/phase2_unified_patch.json
examples/phase2_unified_patch_cli.txt
examples/poi_catalog.json
examples/request.json
examples/route_intent.schema.json
examples/route_plans.json
PHASE15B_CALIBRATION_REPORT.md
PHASE1_DESIGN_REVIEW.md
PHASE2_DELIVERY_REPORT.md
phase2_plan_for_me_simulations.md
README.md
tools/demos/route_entry_demo.py
scripts/
scripts/calibrate_phase15b.py
scripts/diagnose_deepseek.py
scripts/export_phase15b_audit.py
scripts/export_phase2_audit.py
scripts/export_phase2_repair.py
scripts/export_phase2_repair11.py
scripts/export_phase2_repair12.py
scripts/export_phase2_repair13.py
scripts/export_phase2_unified_patch.py
shanghaitrace_poi_kb_v1.json
shanghaitrace_poi_kb_v2_25pois.json
shanghaitrace_poi_kb_v3_minimal_tags.json
src/
src/__init__.py
src/clarification.py
src/feasibility.py
src/geo_utils.py
src/intent_adapter.py
src/intent_models.py
src/intent_parser.py
src/intent_schema.py
src/llm_client.py
src/location_resolver.py
src/mock_examples.py
src/models.py
src/poi_repository.py
src/recommendation_engine.py
src/route_engine.py
src/route_entry.py
src/route_quality.py
src/semantic_expansion.py
src/surprise_policy.py
src/visit_planner.py
tests/
tests/__init__.py
tests/helpers.py
tests/test_cli.py
tests/test_deepseek_provider.py
tests/test_geo_utils.py
tests/test_phase2.py
tests/test_phase2_final_repair.py
tests/test_phase2_quality.py
tests/test_phase2_repair.py
tests/test_phase2_richness.py
tests/test_phase2_unified_patch.py
tests/test_recommendation.py
tests/test_repository.py
tests/test_route_engine.py
tests/test_visit_calibration.py
THIRD_PARTY_NOTICES.md
```

## Files moved

| Original | Final |
| --- | --- |
| `examples/clarification.schema.json` | `examples/phase2/clarification.schema.json` |
| `examples/deepseek_provider_baseline.json` | `examples/phase2/deepseek_provider_baseline.json` |
| `examples/deepseek_provider_smoke.json` | `examples/phase2/deepseek_provider_smoke.json` |
| `examples/intent_system_prompt.txt` | `examples/phase2/intent_system_prompt.txt` |
| `examples/llm_candidate.schema.json` | `examples/phase2/llm_candidate.schema.json` |
| `examples/phase2_first_repair.json` | `examples/phase2/phase2_first_repair.json` |
| `examples/phase2_first_repair_cli.txt` | `examples/phase2/phase2_first_repair_cli.txt` |
| `examples/phase2_first_repair_routes.txt` | `examples/phase2/phase2_first_repair_routes.txt` |
| `examples/phase2_manual_routes.txt` | `examples/phase2/phase2_manual_routes.txt` |
| `examples/phase2_plan_for_me_simulations.md` | `examples/phase2/phase2_plan_for_me_simulations.md` |
| `examples/phase2_repair11.json` | `examples/phase2/phase2_repair11.json` |
| `examples/phase2_repair11_cli.txt` | `examples/phase2/phase2_repair11_cli.txt` |
| `examples/phase2_repair12.json` | `examples/phase2/phase2_repair12.json` |
| `examples/phase2_repair12_cli.txt` | `examples/phase2/phase2_repair12_cli.txt` |
| `examples/phase2_repair13.json` | `examples/phase2/phase2_repair13.json` |
| `examples/phase2_repair13_cli.txt` | `examples/phase2/phase2_repair13_cli.txt` |
| `examples/phase2_routes.json` | `examples/phase2/phase2_routes.json` |
| `examples/phase2_unified_patch.json` | `examples/phase2/phase2_unified_patch.json` |
| `examples/phase2_unified_patch_cli.txt` | `examples/phase2/phase2_unified_patch_cli.txt` |
| `examples/route_intent.schema.json` | `examples/phase2/route_intent.schema.json` |
| `examples/archive/route_plans_phase1.json` | `examples/phase1/route_plans_phase1.json` |
| `shanghaitrace_poi_kb_v1.json` | `data/archive/shanghaitrace_poi_kb_v1.json` |
| `shanghaitrace_poi_kb_v2_25pois.json` | `data/archive/shanghaitrace_poi_kb_v2_25pois.json` |
| `shanghaitrace_poi_kb_v3_minimal_tags.json` | `data/archive/shanghaitrace_poi_kb_v3_minimal_tags.json` |

Files renamed: NONE。移动时文件名未改变。

Files deleted: 根目录 phase2_plan_for_me_simulations.md（已核对 SHA-256 相同）；已搬空 examples/archive/ 目录。没有删除真实数据、fixture、报告或重要 smoke 证据。

Files created: docs/phases/PHASE1.md、PHASE1_5.md、PHASE2.md；docs/PHASE_MANIFEST.md、PHASE2_CLEANUP.md、ARCHITECTURE_REFERENCE.md、cleanup_inventory.json；requirements.txt；examples/phase2/cleanup_smoke.json。更新 README、历史报告/CONTEXT 的链接或当前状态指引。ARCHITECTURE_REFERENCE 保留整理前 README 的详细接口与历史说明。

## Import/path fixes

没有生产 import 修改。scripts/export_phase2*.py 与 diagnose_deepseek.py 仅将输出目标改为 examples/phase2/。calibrate_phase15b.py 的 v3 来源改为 data/archive/；export_phase15b_audit.py 更新历史示例引用。生产 src、tests、三个根目录 demo、两份运行数据 SHA-256 与整理前一致，记录见 cleanup_inventory.json。

报告选择保留根目录完整原文，docs/phases/ 建立清晰入口；不裁剪 repair/final patch 记录。正式 tests 仍在 tests/；共享 request/Phase 1.5 示例留在 examples 根目录以兼容旧命令。

## Regression tests

`python -m unittest discover -s tests -t . -q`

Ran 214 tests in 9.648s — OK。

## Three-entry smoke tests

| Command | Actual result |
| --- | --- |
| python tools/demos/chat_demo.py --mode plan_for_me --text "I have two and a half hours. I want local neighborhoods and I'd rather avoid museums." | 真实 DeepSeek；Parsed Intent，local_life / avoid museum_visit，route quality passed，3 stops，success，exit 0。 |
| python tools/demos/route_entry_demo.py --mode places_in_mind --places "Wukang Mansion;Jianyeli" --minutes 180 | 必去保留，5 stops，success，exit 0。Places 按既有契约不套用 Plan/Surprise 的 MVC quality line。 |
| python tools/demos/route_entry_demo.py --mode surprise_me --start "West Bund" --minutes 180 --seed 42 | waterfront + industrial_heritage，route quality passed，3 stops，success，exit 0。 |

完整输出：[cleanup_smoke.json](../../../examples/phase2/cleanup_smoke.json)。没有把 Mock provider response 用于本轮真实 Plan 验证。安全 key 只注入真实测试子进程，不写入项目文件。

## FINAL PROJECT TREE

```text
shanghai_trace_agent/
├─ src/                         # stable functional modules
├─ data/
│  ├─ pois.json
│  ├─ surprise_themes.json
│  └─ archive/                  # Phase 1 and v1/v2/v3 source knowledge bases
├─ tests/                       # 214 regression tests, unchanged
├─ scripts/                     # existing tool entry points; path fixes only
├─ examples/
│  ├─ phase1/route_plans_phase1.json
│  ├─ phase2/                   # schemas, simulations, real smoke evidence
│  ├─ request.json
│  ├─ route_plans.json
│  ├─ poi_catalog.json
│  └─ manual_routes.txt
├─ docs/
│  ├─ phases/PHASE1.md
│  ├─ phases/PHASE1_5.md
│  ├─ phases/PHASE2.md
│  ├─ PHASE_MANIFEST.md
│  ├─ PHASE2_CLEANUP.md
│  ├─ ARCHITECTURE_REFERENCE.md
│  └─ cleanup_inventory.json
├─ tools/demos/chat_demo.py
├─ tools/demos/route_entry_demo.py
├─ tools/demos/demo.py
├─ requirements.txt
├─ README.md
├─ PHASE1_DESIGN_REVIEW.md        # full historical report retained
├─ EXAMPLE_REVIEW.md
├─ PHASE15B_CALIBRATION_REPORT.md
├─ PHASE2_DELIVERY_REPORT.md      # all repairs/provider history retained
├─ CONTEXT.md
├─ THIRD_PARTY_NOTICES.md
├─ .env.example
└─ .gitignore
```

Behavior changes: NONE。

Phase 2 Status: FROZEN / COMPLETE。未开始 Phase 3。
