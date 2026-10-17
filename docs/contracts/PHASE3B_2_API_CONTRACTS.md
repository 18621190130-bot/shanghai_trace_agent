# Phase 3B_2 Read-only World Queries（含 3B_2.1 受控修订）

```python
from src import Location
from src.services.world_context_service import WorldContextService

world = WorldContextService.from_environment()
location = {'lat': 31.167682, 'lng': 121.463841, 'coordinate_system': 'GCJ02'}
address = world.reverse_geocode(location).to_dict()
info = world.get_poi_live_info('p28').to_dict()
arrival = world.check_arrival(location, 'p28').to_dict()
```

没有 HTTP API / UI。三个入口均为独立只读查询，没有 TripStore 引用、没有命令解析、没有自动状态转换。调用者可把 `trip.current_poi_id` 作为目标 ID 传入，但服务不从 GPS 自动推断 current stop，也不将 ARRIVED 转换为 visited。

复用 3B_1 Location；输入必须明确 WGS84 / GCJ02（兼容 GCJ-02），非法数据抛 ValueError。WGS84 官方转换复用 `AmapWalkingProvider.normalize_location_for_amap`，只执行坐标转换，不执行 walking query。失败时 reverse_geocode 返回 UNAVAILABLE 和安全 error_code，保留输入 datum；绝不把未转换 GPS 标记为 GCJ02。check_arrival 转换失败抛既有 ExternalProviderError，由调用边界处理，禁止跨坐标系算出虚假的到达。

ResolvedLocation 返回 location、formatted_address、province、city、district、township、adcode、street、street_number、provider、fetched_at、live_data_status、cache_hit、error_code。可选字段缺失为 None。高德直辖市 city=[] 时依据明确的 province=上海市/北京市/天津市/重庆市补充 city，这不是猜测地点。

PoiLiveInfo 返回 core_poi_id、provider_id、provider、name、address、location、tel、opentime_today、opentime_week、rating、cost、tags、poi_type、fetched_at、live_data_status、open_status、identity_mapping_status、live_info_applicability、mapping_status（兼容别名，同 identity_mapping_status）、cache_hit、status_evaluated_at、error_code。AVAILABLE 要求完整字段；有效主体但缺字段为 PARTIAL；映射未解决、无映射或 provider failure 为 UNAVAILABLE。没有用 Core planning opening_hours 代替实时字段，没有从 KB 永久写入 provider 数据。

营业状态仅解析当天完整数字时间区间，支持 `10:00-18:00`、多个以逗号/分号分隔的区间、`18:00-02:00`、`00:00-24:00`，开始包含、结束不包含。使用显式 Asia/Shanghai UTC+08:00，传入时间必须 aware，UTC 自动转换。FULL / LIMITED 范围外 CLOSED；无法可靠完整解析 UNKNOWN。NOT_APPLICABLE 适用性的地点始终返回 open_status=NOT_APPLICABLE，包含未匹配或 API 失败情况，且不受营业时间字符串影响。周规则、节日说明、全天文字等不推断。今天数据缓存跨上海日期时，保留原字段供追溯，但 FULL / LIMITED 的 open_status=UNKNOWN；NOT_APPLICABLE 保持不适用。每次查询重新计算状态，不缓存 OPEN/CLOSED。

ProximityResult 返回 current_location、target_poi_id、target_location、distance_m、status、arrival_threshold_m、near_threshold_m。统一 GCJ02 后用 Haversine 直线距离；默认 ARRIVED≤60m、NEAR≤200m，其余 FAR；配置通过 `ProximityConfig` 注入 `WorldContextService.from_environment(proximity_config=...)`。阈值集中且校验，不调用 Walking API。目标点为现有 Core 代表点，接近不代表进入、完成或访问证明。

缓存：POI detail 1800s，key=(provider, provider_id)；regeo 1800s，key=(provider, method, round(lat,6), round(lng,6))；官方 conversion 3600s，含输入 datum 和 6 位经纬度。每个 cache 最多512项、LRU、monotonic clock、防御性副本，provider 失败不缓存。默认不返回 stale data 冒充最新查询成功。

Core↔高德映射位于 `data/amap_poi_mappings.json`。仅 MATCHED 调用 provider；身份仅允许 MATCHED / AMBIGUOUS / NOT_FOUND；实时信息适用性独立为 FULL / LIMITED / NOT_APPLICABLE。其他身份状态返回 UNAVAILABLE，营业状态由适用性独立决定。一次搜索审计不写 Core KB；本轮明确授权的 p40 删除和 p4/p11 坐标校正由独立脚本完成并保存审计。MATCHED 的 reviewed=false 表示规则自动匹配，未获得人工确认；全部候选、confidence、offset 和原因保留，待验收清单位于 `examples/location_awareness/MAPPING_MANUAL_REVIEW.md`。

默认测试 `python -m scripts.run_offline_tests`。真实映射/验收需要显式 RUN_LIVE_AMAP_TESTS=1 和进程 AMAP_WEB_SERVICE_KEY：`python -m scripts.match_amap_poi_ids`、`python -m scripts.live_location_acceptance`、`python -m unittest tests.test_location_live -v`。凭据只由原 client 读取，不出现在 DTO、sidecar、异常或日志。

一轮校准可用名称、aliases 和坐标附近查询验证 Core 主体；这不是用户可调用的 Nearby 推荐服务，不产生辅助 POI 或补点。本阶段没有 Nearby service search、天气、Reality Check、GPS tracking、UI 或 Trip mutation。POI 名称搜索仅为离线/一次性 Core 身份审计脚本服务，没有增加附近商户产品查询。

## 3B_2.1 Sidecar 与受控数据修订

校准使用的 text、around 与 detail 参数依据 [高德官方 POI 搜索 2.0 文档](https://developer.amap.com/api/webservice/guide/api-advanced/newpoisearch)。around 仅为主体身份校准使用。

Sidecar 必需字段：identity_mapping_status、amap_poi_id、matched_name、entity_type、live_info_applicability、aliases、reviewed、match_method、confidence、distance_m、notes。身份未解决时 amap_poi_id=null；禁止身份 NOT_APPLICABLE。自动绑定仍要求 confidence≥0.92、名称相似度≥0.9、距离≤300m、行政区与实体类型一致。主体的明显子馆、入口、停车场、附属大厅等不算竞争主体；地理实体的道路/热点表示仅在同名、同区、相距≤60m且类型明确时消除重复表示。其他多主体仍按原 margin≥0.08 校验。

reviewed=true 仅使用本次负责人确认的 9 项固定身份及条件确认后找到的 p24 总主体。决定持久化于 data/amap_manual_confirmations.json；脚本重跑保留人工决定，API 失败不会撤销身份，也不会写入空检索覆盖完整审计。p24 成功确认后也在 sidecar 保留其 reviewed 决定。审计 summary 分别提供 identity_counts 与 live_info_applicability_counts，两组均合计 58。

生产 Core 已为 58 项。data/deleted_core_pois.json 记录 p40 删除及受影响路线。p4/p11 old→new 见 examples/location_awareness/coordinate_corrections.json，正式 detail 证据见 calibration/coordinate_provider_details.json。默认 Trip fixture 无 p40；当前 walking example 仅从旧序列删除 p40，未加替代点。历史候选库、冻结快照与原验收证据不作为当前 Core 数据使用。

维护命令：python -m scripts.calibrate_core_data（显式授权校正，可重复运行）、python -m scripts.match_amap_poi_ids（全量身份审计）、python -m scripts.prune_deleted_route_example（删除样例 stop 并重新获取真实几何）、python -m scripts.audit_location_delivery（只读完整性审计）。校正和实时审计使用前述 live opt-in。3B_2.1 live 验收：python -m scripts.live_calibration_acceptance。
# Phase 3B_2.2 Spatial contracts

`data/core_spatial_profiles.json` 是独立空间 sidecar，以 Core ID 为键；当前 58 个 ID 必须和生产 Core 完全一致。每条含 `spatial_type`、`route_anchor`、`anchor_source`、`spatial_extent`、`extent_source`、`extent_confidence`、`extent_status`、`reviewed`、`notes`。LINEAR 另有 `secondary_anchor`。

所有 anchor 与 extent 坐标必须显式为 `GCJ02`。Anchor 含 `lat/lng/source/confidence/notes`，source 可为 `AMAP_POI/AMAP_ENTRANCE/CORE_EXISTING/TRACEMATE_CURATED`。AREA extent 接受闭合简单 `POLYGON` 或正半径 `CENTER_RADIUS`；LINEAR 接受不同端点 `START_END` 或至少两个不同顶点的 `POLYLINE`。Extent 必须带来源、置信度、说明及 evidence；来源为 `PROVIDER` 时必须另有真实 boundary reference。当前没有 provider 边界。

POINT 保持 Core 规范化位置，extent 为 null。生产 `POIRepository()` 对 AREA/LINEAR 只覆盖供路线使用的 `POI.coordinates` 为 anchor；`original_coordinates/original_coordinate_system` 与原始 Core 保留身份坐标。历史/候选 KB 不自动使用生产 sidecar。`get_spatial_profile(id)` 返回防御性副本。

Identity matcher 和审计查询由 original 坐标规范化后执行，避免 anchor 改动影响身份匹配。Identity `NOT_FOUND` 不影响空间加载与 Route Stop。RouteEngine、Walking、Replan、Proximity 通过已有 repository 坐标契约使用同一 anchor，均没有第二套坐标转换或 Trip 自动触发。LINEAR secondary anchor 仅是空间元数据，当前不会自动安排入口到出口的整条内部穿行。

`spatial_geometry.py` 的包含判断、线段距离使用上海小范围的近似投影，仅供数据验证和未来调用；不接入到达/离开自动化。Proximity 仍是 anchor 的原有 60m/200m 距离阈值。Spatial `reviewed=false` 表示尚未获得项目负责人的最终空间产品验收，与已在用户授权下完成的 Identity `reviewed=true` 分开。
