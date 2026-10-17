# Phase 3B_1 Walking Contracts

仅提供步行查询和选定路线的数据补全。没有新增 HTTP API 或前端。

```python
from src import (POIRepository, RouteRequest, WalkingRoutePlanner,
                 WalkingRouteService, Location)

# 配置通过进程环境 AMAP_WEB_SERVICE_KEY 注入。
service = WalkingRouteService.from_environment()
result = service.get_walking_route(
    Location(31.175, 121.463, 'GCJ02'),
    Location(31.176, 121.464, 'GCJ02'))

# 使用冻结 RouteEngine 规划，然后只补全最终路线。
route = WalkingRoutePlanner(POIRepository(), walking_service=service).generate_route(
    RouteRequest(180, preferred_zone='west_bund'))
output = route.to_dict()
```

`RouteEngine` 本身仍是原有纯规划器；直接调用它只获得 planning metrics。常规 `RouteEntryService.generate()` 和接受路线质量澄清的最终结果已自动补全。ReplanningCoordinator 及局部 RouteMutationService 在新版本保存前补全。可通过 `walking_service=` 注入 provider-neutral service；ConversationalTripService 可注入相应 coordinator。

Location 必須包含 `lat`、`lng`、`coordinate_system`，支持 `WGS84`、`GCJ02` 和兼容旧名称 `GCJ-02`。Walking API 的 WGS84 输入通过官方坐标转换接口变为 GCJ02；转换失败明确报内部错误，路线补全则回退估算。未知坐标系拒绝使用。当前 Core POI 由现有 repository 统一输出 GCJ-02；原始 WGS84 及历史近似转换来源仍保留。

单 leg 返回 WalkingRouteResult：origin、destination、distance_m、duration_s、steps、polyline、provider、fetched_at。steps 保留 instruction、road、distance_m、duration_s、polyline；缺失可选字段是 None。直接单 leg 查询失败抛 ExternalProviderError 子类，不伪造真实结果。

RoutePlan 输出新增：

| 字段 | 语义 |
| --- | --- |
| planning_distance_m | 原 total_estimated_distance_km × 1000 |
| planning_duration_min | 原 total_estimated_walking_minutes，不含停留或 buffer |
| walking_distance_m / walking_duration_s | 分段汇总；可能包含回退估算，必须一起读取状态 |
| walking_data_status | AVAILABLE / FALLBACK_ESTIMATE / UNAVAILABLE |
| walking_legs | 有向分段，每段含 POI 身份、起终点、指标、steps、polyline、来源、时间和缓存标记 |
| route_geometry | 完整真实路线的 GCJ02 [lng, lat] 数组；存在缺失分段时为空 |
| walking | status、total_distance_m、total_duration_s、legs、geometry、geometry_complete、geometry_segments、coordinate_system |

原 total_estimated_*、warnings、停留时间、remaining_minutes 和预算决策全部保留。walking_data_status 描述整条路线；单 leg status 可指出哪一段使用 fallback。AVAILABLE 仅代表所有所需路段真实数据可用；无移动的单 POI / 空路线是零 legs、零指标，不作真实道路验收依据。

没有 start 时，N 个 POI 请求 N−1 个 legs；有明确 start / Replan logical origin 时，多一个到首站的 approach leg，其 from_poi_id 为 None、from_name 为 Route origin。logical origin 是原有业务代表点，不是实测 GPS。规划总距离包含 approach，因此真实总量也包含它。

geometry 内部是 tuple of (lng, lat)，JSON 序列化后是二维数组。完整路线轻量删除连续重复点；部分失败时 geometry_segments 保留每段几何，失败段为空。消费者不得把缺失路段两侧直接连成真实街道线。

缓存按 provider 实例、walking mode、起终点坐标系、6 位经纬度组成有向 key；默认 TTL 3600s，最多 512 条 LRU，使用 monotonic clock。命中保留原 fetched_at；返回防御性副本；失败不缓存。fetched_at 是 UTC ISO8601。缓存局限于进程和该 service 实例。

缺 key 时常规路线自动 FALLBACK_ESTIMATE，无 HTTP 请求。默认网络 timeout 5s、响应上限 4MiB、相邻请求最短间隔 0.5s；不自动重试配额错误。异常返回固定内部 code，不保留原始 URL、key 或 provider error body。客户端只读取 AMAP_WEB_SERVICE_KEY，不读取旧 pipeline 的 AMAP_API_KEY。

默认自动验证：`python -m scripts.run_offline_tests`，会在测试及子进程中清除 live 配置。真实验证须显式设置 RUN_LIVE_AMAP_TESTS=1 和 AMAP_WEB_SERVICE_KEY，然后运行 `python -m scripts.live_walking_acceptance` 或 `python -m unittest tests.test_walking_live -v`。标准库不自动加载 .env 文件；由 shell / 调用宿主注入环境变量。
