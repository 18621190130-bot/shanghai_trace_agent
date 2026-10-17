# TraceMate Phase 3B_1 验收报告

交付日期：2026-10-05（Asia/Shanghai）。范围仅限 Real Walking Route Integration；结束后等待人工查收。

## 1. Summary

已把选定 Core POI 路线补全为高德真实道路步行数据：距离、预计时间、导航 steps、每段 polyline、完整 route geometry；加入官方 WGS84 转换、进程内缓存、限流间隔和逐段 fallback。已集成路线入口、完整 Replan、局部路线修改和新 RouteVersion snapshot。

原 RouteEngine、geo_utils、生产 59 节点 KB、TripState、TripStore、TripCommand、原有测试文件均保持冻结内容。已有 skip/remove/must-go/soft budget/revisit/CAS 等行为通过原有测试，不根据真实时间自动调整地点。

## 2. Architecture

```text
RouteEntryService / WalkingRoutePlanner
    → 原 RouteEngine（纯规划；不调用高德）
    → 最终路线
    → WalkingRouteService
    → WalkingRouteProvider protocol
    → AmapWalkingProvider
    → AmapClient
    → Amap HTTPS Web Service

ReplanningCoordinator / RouteMutationService
    → 原 3A 选点、预算与版本验证
    → 最终新序列
    → 同一 WalkingRouteService
    → 新 RouteVersion snapshot
    → 原 CAS 保存
```

Route Entry 的 Surprise 多主题比较、路线质量澄清前的候选结果、Continuation 修复、Mutation 单点物化和插入排序均不请求高德。成功的最终候选才补全；Replan no-change 不补全。

直接调用原 RouteEngine 仍返回原 planning 结果。新 `WalkingRoutePlanner` 是简单组合服务，为需要一步完成规划与补全的内部调用者提供稳定入口，没有改写或继承重设计原规划算法。

## 3. Files Changed

新增代码：

- `src/walking_models.py`
- `src/providers/__init__.py`、`src/providers/base.py`
- `src/providers/amap/__init__.py`、`client.py`、`walking.py`
- `src/services/__init__.py`、`walking_route_service.py`、`walking_route_planner.py`
- `tests/test_walking_routing.py`、`tests/test_walking_live.py`
- `scripts/freeze_phase3a.py`、`scripts/run_offline_tests.py`、`scripts/live_walking_acceptance.py`、`scripts/audit_walking_delivery.py`

修改代码及配置：`src/models.py`、`src/__init__.py`、`src/route_entry.py`、`src/trip_replanning.py`、`src/route_mutation.py`、`src/trip_action_executor.py`、`.env.example`、`README.md`。

新增文档及证据：本报告、`PHASE3A_FREEZE.md`、`docs/PHASE3B_1_API_CONTRACTS.md`、冻结 archive / manifest、完整基线及最终测试输出、真实 live 测试输出、live_west_bund.json、delivery_audit.json。

`.gitignore` 已有 `.env` / `.env.*` 规则及 `.env.example` 例外，无需修改。发现旧 `.env.example` 中已有凭据，已改为空占位值；没有复制到新的文件、日志、测试或 TripState。

## 4. Amap Integration

采用 [高德 v3 步行路径规划](https://lbs.amap.com/api/webservice/guide/api/direction)：GET `/v3/direction/walking`，origin / destination 为六位小数的 lng,lat。官方 path 的 distance 为米、duration 为秒，steps 带道路指示及 polyline。

客户端统一读取 `AMAP_WEB_SERVICE_KEY`，HTTPS、默认 timeout 5 秒、JSON body 上限 4 MiB。HTTP、connection、timeout、invalid JSON、status failure、missing route/path/distance/duration/steps/polyline 均转换为内部异常。可选 road/instruction/step distance/step duration 缺失保留 None，不补造。

错误采用固定内部 code，不传播高德 raw info/body、请求 URL 或 key；transport exception context 不保留原始 URL。返回文本额外去除 configured key 的回显。直接单 leg 查询报明确内部错误；路线 hydration 捕获故障并回退。

真实验收复用当前机器已有高德配置，在验收子进程中映射到新规范变量；新 client 只读取 AMAP_WEB_SERVICE_KEY，没有增加 legacy alias。凭据没有写入磁盘。

## 5. Coordinate Handling

内部 Location 明确 lat、lng、coordinate_system；接受 GCJ02、WGS84，兼容已有 GCJ-02 名称，校验范围和有限数值，未知坐标系不会被当作高德坐标使用。

现有 repository 的 Core POI planning 坐标已经统一为 GCJ-02；一些点来自历史 WGS84 / BD09 的近似转换，原始来源、坐标备注和代表点限制保留，未重新标定 KB 或游客入口。

新工具收到 WGS84 时，通过 [高德坐标转换 API](https://lbs.amap.com/api/webservice/guide/api/convert) GET `/v3/assistant/coordinate/convert`、coordsys=gps 转换后再 routing。GCJ02 直接使用。已有规划器的离线近似转换继续保持原有行为，不把它冒充新的官方 GPS 转换。

## 6. Route Hydration

无 start 的 N 个 POI，仅查询 N−1 个相邻有向 legs。有 start 或 Replan logical origin 时，多一个到首站的 approach leg，使真实汇总与原 planning 总量具有相同范围。

新增 planning_distance_m、planning_duration_min、walking_distance_m、walking_duration_s、walking_legs、route_geometry、walking_data_status 及 walking 输出对象；保留全部原 estimated_* 指标。planning_duration_min 是步行估算，不含 stay / buffer。

AVAILABLE 表示所有需要的 legs 有真实数据；FALLBACK_ESTIMATE 表示至少一段使用原规划估算，汇总可能包含真实和估算；UNAVAILABLE 表示某段连合法估算也无法提供。消费者必须一起读取状态。

## 7. Polyline

高德 `lng,lat;lng,lat;...` 字符串在 provider 内解析为 tuple of (lng,lat)，JSON 输出为 `[lng, lat]` 二维数组。保留每个 step、每个 leg 和完整路线 geometry，删除连续重复点。

部分 fallback 时，完整 route_geometry 为空，geometry_complete=false；geometry_segments 保留已成功分段，不跨缺失路段画虚假的道路线。fallback 不生成直线作为真实 geometry。

## 8. Cache

provider/service 实例内有向 leg cache；key 包含 walking mode、origin/destination datum 与经纬度（round 6 位）。TTL 3600 秒、最多 512 entries、LRU 淘汰、monotonic clock，返回防御性副本；cache hit 保留原 fetched_at。

默认 service 跨 Route Entry / Replan / Mutation 复用，因此 A→B→C→D 改为 A→B→E→D 可自然复用 A→B。不同方向不共用；失败不缓存为成功。没有分布式缓存或复杂 route diff。

## 9. Fallback

逐段失败时，使用原 stop 的 estimated distance ×1000、estimated walking minutes ×60；保留可用分段的真实指标。无 key 不发请求，正常路线返回 FALLBACK_ESTIMATE。

真实验收第一次连续请求的最后一段触发 provider 配额/限流错误，路线正确保留成功段并回退失败段。随后加入默认 0.5 秒、可配置的请求间隔；重跑全路线成功。[高德错误码文档](https://lbs.amap.com/api/webservice/guide/tools/info) 区分请求频率、配额等失败，本实现统一转换为安全内部异常，不自动无限重试。

## 10. Replan Integration

Continuation 和组成修复先保持原纯规划结果，通过原身份、模式、预算、journey policy 和 no-change 检查后，再补全新路线；JSON 化的 proposed_route 保存到新 RouteVersion。原 RouteVersion / original_route 不改。

Mutation 的 skip/remove/insert 等先完成原有局部修改，再补全最终序列。TripState mutation logic 没有新增 world command。hydrate 完成后仍使用原 state_revision CAS，网络等待期间并发进度变更导致 stale_state_conflict，不覆盖更新状态。

真实 duration 不参与 soft/hard 预算决策，不自动删站或 replan；LIVE_ROUTE_EXCEEDS_BUDGET 和 Reality Check 留给 3B_4。

## 11. Tests

- Phase 3A 冻结前：645 tests，全部通过，74.437s。
- 新增离线 tests：33 项，覆盖正常/异常 provider、可选字段、polyline、坐标转换、transport redaction、请求 pacing、分段汇总、TTL/LRU/方向/副本、未变 legs 缓存、部分 fallback、无合法估算、单站与 approach、最终路线请求数、Surprise 候选隔离、真实超预算不改站、故障有效 Trip、Replan snapshot/record、CAS、局部 remove、no-change。
- 默认完整 suite：`python -m scripts.run_offline_tests`，679 tests，OK (skipped=1)，81.114s：全部原 645 tests 加 33 项新增离线 tests 通过，1 项 live test 按默认配置跳过。最终结果见 `examples/walking_routing_full_tests.txt`。
- 实际真实测试：`RUN_LIVE_AMAP_TESTS=1` 时 `python -m unittest tests.test_walking_live -v`，1 test，OK，1.749s。记录见 `examples/walking_live_tests.txt`。
- delivery_audit 校验原有测试文件、受保护核心文件和已配置凭据暴露；结果见 `examples/walking_routing/delivery_audit.json`。

原测试预期未修改，原 RouteEngine 哈希校验保持通过。Windows 完整 suite 需 PYTHONUTF8=1，默认 offline runner 已负责注入到子进程。

## 12. Live West Bund Result

真实验收查询日期：2026-10-05，首次数据 fetched_at 11:10:48 UTC（19:10:48 Asia/Shanghai）。证据：`examples/walking_routing/live_west_bund.json`，包含每段 steps、完整 polyline 和时间戳。

Core POI 顺序：西岸艺术中心 p36 → 上海摄影艺术中心 p40 → 西岸美术馆 p28 → 上海油罐艺术中心 p29 → 西岸穹顶艺术中心（含北广场）p37。

| 指标 | 结果 |
| --- | --- |
| Planning walking distance | 869.677 m |
| Planning walking duration | 11.596 min |
| Real walking distance | 1340 m |
| Real walking duration | 1072 s = 17 min 52 s |
| Leg count | 4 |
| Route geometry points | 60 |
| Status | AVAILABLE |

| Leg | Distance m | Duration s | Steps | Leg geometry points |
| --- | ---: | ---: | ---: | ---: |
| 西岸艺术中心 → 上海摄影艺术中心 | 211 | 169 | 3 | 9 |
| 上海摄影艺术中心 → 西岸美术馆 | 230 | 184 | 3 | 13 |
| 西岸美术馆 → 上海油罐艺术中心 | 505 | 404 | 2 | 21 |
| 上海油罐艺术中心 → 西岸穹顶艺术中心 | 394 | 315 | 4 | 18 |

Case A 两点查询返回 211m、169s、3 steps、9 geometry points。Case B 完整西岸路线全部来自真实高德道路 routing。Case C mock timeout 返回 FALLBACK_ESTIMATE，正常生成路线、Trip 和新版本。

## 13. Known Limitations

- 当前 client 同步逐段调用；timeout 和请求间隔可能增加最终路线延迟，缓存仅进程内，不提供跨进程 QPS 协调。
- 已有 Core POI 是代表点，不保证实测游客入口；官方 routing 不证明场馆开放、室内可通行或营业信息。
- 没有天气、营业信息、Nearby、Reverse Geocode 产品能力、Arrival、Reality Check、连续 GPS、公交或前端地图。
- 高德时长是地图服务预计值，不根据个人 pace 重新计算。
- 没有 Git 仓库，冻结交付为不可覆盖的 archive / SHA-256 manifest，没有 tag/commit。
- 凭据审计只检查当前环境已配置的已知凭据，不能声称是完整通用 secret scanner。

## 14. Manual Review Required

None。代码、回归及真实验收没有剩余技术 blocker。请人工查收本报告与 live route 证据；收到验收后再决定开始下一阶段。

## 15. Ready for 3B_2?

READY。仅表示 3B_1 技术交付达到要求；本轮工作停在 3B_1，未开始 3B_2。
