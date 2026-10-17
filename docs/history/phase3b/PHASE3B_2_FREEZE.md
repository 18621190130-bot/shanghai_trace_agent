# Phase 3B_2 Freeze

状态：**FROZEN**。用户在2026-10-05提供的Phase3B_3任务书明确将Phase3B_2标记为FROZEN，并授权进入3B_3。Phase3B_2、3B_2.1、3B_2.2作为同一个Phase3B_2验收范围收口。

验收依据：`PHASE3B_2_2_REPORT.md`、`SPATIAL_PROFILE_REVIEW.md`、完整762项离线回归和4项live regression、真实walking/Replan样本、全部58项Identity及Spatial审计。

冻结候选包：`examples/phase3b_2_freeze_candidate/phase3b_2_candidate.zip`，配套`manifest.json`逐文件SHA-256及archive SHA-256。包含src、scripts、tests、data、docs、本阶段报告、空间与历史位置/步行验收证据；不含环境变量、.env、密钥配置、缓存或其他冻结zip。

Phase3A和3B_1既有冻结材料继续保留；RouteEngine、Trip、RouteVersion、CAS、Replan、Walking实现和baseline SHA-256一致。经用户授权的Core坐标修正、最小repository坐标overlay及独立Identity坐标匹配例外在交付审计逐项记录。

Core=58，Identity=57MATCHED/0AMBIGUOUS/1NOT_FOUND，Spatial=26POINT/27AREA/5LINEAR；32项区域/线性anchor与extent完整。Spatial reviewed=false用于表达待本次产品验收，禁止把它伪装成负责人已亲自审定的官方边界。

3B_2.2结束时状态为READY并STOP；上述任务书现在确认FROZEN。旧候选包及manifest保留当时状态与文件原貌；3B_3开始前的新基线见 `examples/nearby_rest_stops/phase3b_2_baseline_manifest.json`。当前工作目录无Git仓库，因此使用实际源码/数据哈希与archive，不伪造commit/tag。
