# TraceMate Phase 3B_2 验收报告

交付日期：2026-10-05（Asia/Shanghai）。范围为 Location Awareness + POI Live Information；本轮止于 3B_2，等待人工验收。

## 1. Summary

已实现标准位置输入、复用官方 WGS84→GCJ02 转换、逆地理编码及 adcode、独立 Core↔高德映射、POI 动态信息、保守营业状态、可配置接近/到达判断、TTL/LRU cache、安全错误结果、默认离线测试和真实验收。

完整审计生产 59 Core POI。没有要求 59/59 MATCHED，没有把街区或开放空间强行绑定到商户。所有 world queries 保持只读，没有修改 TripCommand 或 TripState；ARRIVED 不等于 visited。

Phase 3A 与 3B_1 基线通过；全部原有 tests、Core KB 和业务/步行源码保持不变。唯一既有代码修改是共用 AmapClient 的路径校验增加 v5，保留 v3 行为。

## 2. Architecture

```text
WorldContextService（只读 facade，无 TripStore）
 ├─ LocationService
 │    ├─ 原 AmapWalkingProvider.normalize_location_for_amap
 │    └─ GeocodingProvider → AmapGeocodingProvider
 ├─ PoiLiveInfoService
 │    ├─ PoiMappingRepository → sidecar
 │    ├─ PoiProvider → AmapPoiProvider
 │    └─ resolve_open_status
 └─ ProximityService → 统一坐标后 Haversine

Amap providers → 同一个原 AmapClient
```

Provider 解析高德 JSON 为内部 DTO；上层没有高德字段依赖。一次性 mapping search 独立于默认路线搜索和 Trip mutation，不提供附近商户产品功能。

## 3. Files Changed

Created：

- `src/world_models.py`、`src/poi_mapping.py`
- `src/providers/world.py`、`src/providers/amap/world.py`
- `src/services/ttl_cache.py`、`location_service.py`、`opening_hours.py`、`poi_live_info_service.py`、`proximity_service.py`、`world_context_service.py`
- `scripts/match_amap_poi_ids.py`、`live_location_acceptance.py`、`audit_location_delivery.py`
- `tests/test_location_awareness.py`、`tests/test_location_live.py`
- `data/amap_poi_mappings.json`
- 本报告、`PHASE3B_1_FREEZE.md`、`docs/PHASE3B_2_API_CONTRACTS.md`
- `examples/location_baseline_tests.txt` 和 `examples/location_awareness/` 的 baseline manifest、mapping audit、review pack、live evidence、test results、delivery audit。

Modified：`src/providers/amap/client.py`（只接受 v5 路径）、`README.md`（本阶段调用与状态说明）。未修改 production KB、旧 tests 或 walking models/services。

## 4. Current Location / Coordinate Handling

直接复用 3B_1 的 Location，输入为 Location 或恰含 lat/lng/coordinate_system 的 dict。明确 WGS84 / GCJ02（兼容 GCJ-02）；非法范围、NaN/infinity、缺 datum 和不支持 datum 均拒绝。

LocationService 的 GPS 转换直接调用原 AmapWalkingProvider 的官方 normalize 方法，不调用 Walking API，没有新建第二套转换公式。转换失败的 reverse result 为 UNAVAILABLE，保留原输入坐标系；不会静默标记为 GCJ02。

## 5. Reverse Geocoding

使用 [高德逆地理编码](https://lbs.amap.com/api/webservice/guide/api/georegeo) GET `/v3/geocode/regeo`，extensions=base，仅解析地址/行政区/街道字段。

ResolvedLocation 保留 location、formatted_address、province、city、district、township、adcode、street、street_number、provider、fetched_at、live_data_status、cache_hit、error_code。缺字段为 None；上海等直辖市明确 province 与空 city 情况按 documented identity 规范化为 city=上海市。

缓存 TTL 1800s、容量512、6 位经纬度 key、monotonic clock、LRU、防御性副本。GPS 官方转换另缓存3600s，key包含原 datum。失败不缓存，不从 Core KB 猜地址。

## 6. Core POI Mapping Audit

一次性脚本通过 [高德 POI 2.0 名称搜索](https://lbs.amap.com/api/webservice/guide/api/newpoisearch) `/v5/place/text`，限制上海，最多10候选，完整遍历59 Core。侧文件持久化身份/候选/评估，不改 Core KB。

| Status | Count |
| --- | ---: |
| Total Core POIs | 59 |
| MATCHED | 21 |
| AMBIGUOUS | 12 |
| NOT_FOUND | 0 |
| NOT_APPLICABLE | 26 |
| Provider search failure | 0 |

评分：0.75×最大 Core 名称/现有 alias 相似度 + 0.25×max(0,1−distance_m/1000)。行政区冲突或停车/入口/厕所/公交等子实体类型冲突降低可信度。自动 MATCHED 同时要求 confidence≥0.92、name similarity≥0.90、distance≤300m、首二候选 margin≥0.08、district/type 检查通过。不是取第一条。

街道、公园和开放空间默认 NOT_APPLICABLE；对具有明确单体主体的商业/景点 district（例如梦中心、豫园、张园、思南公馆）允许匹配。未解决条目 amap_poi_id=null。低置信度手工匹配须明确 reviewed=true；本轮所有自动匹配仍 reviewed=false，不声称获得人工确认。

审计及人工查收资料覆盖 West Bund、武康/衡复、新天地、外滩/老城厢等全部区域；人工决策尚未执行，详见 `MAPPING_MANUAL_REVIEW.md`。

## 7. POI Live Information

`get_poi_live_info(core_poi_id)`：Core ID → mapping sidecar → MATCHED provider ID → `/v5/place/detail` show_fields=business → PoiLiveInfo。共用原 key、timeout、pacing、safe errors。

保留 name/address/location/tel/opentime_today/opentime_week/rating/cost/tags/poi_type/fetched_at。provider 文本去除 configured key 回显；缺失为 None，非法 rating/cost 为 None；没有人工制造评分和价格。

完整字段为 AVAILABLE；主体有效但部分字段缺失为 PARTIAL；映射缺失/不适用/歧义、provider故障为 UNAVAILABLE，open_status=UNKNOWN。没有将 Core story、文化标签、stay、environment 或 opening_hours 覆盖成高德数据。

POI detail 1800s TTL/LRU，key=(provider,provider_id)。缓存只存动态 DTO，开放状态每次按当前时间计算；查询输出中的 cache_hit/fetched_at/status_evaluated_at 区分获取与判断时间。

持久化的 live_acceptance.json 仅为带日期验收证据，不被 runtime 读取为动态数据源。

## 8. Opening Hours

显式使用 Asia/Shanghai（UTC+08:00），不读取 server local timezone。调用传入 datetime 必须 timezone-aware，UTC 可转换。

支持完整可靠当天数字区间 `10:00-18:00`、多个以分号/逗号分隔的区间、跨午夜 `18:00-02:00`、明确 `00:00-24:00`。开始包含，结束不包含；区间内 OPEN、区间外 CLOSED。跨午夜按该重复时段解释，不接受包含日期或特殊节日的复杂 prose。

缺字段、空值、全天文字、现场公告、节日调整、周规则、无法完整解析、非法时钟范围为 UNKNOWN。不会以周规则推测 today；跨上海日期的缓存 today 字段也不会用于新一天的状态判断。raw today/week 都保留供 UI 查看。

## 9. Proximity / Arrival

LocationService 先统一到 GCJ02，目标使用原 repository 的 GCJ-02 Core 代表点。Haversine 空间直线距离，未加入步行绕行系数，不调用 Walking API 或逆地理编码。

集中可配置 ProximityConfig 默认 arrival_threshold_m=60、near_threshold_m=200；校验有限数值且0≤arrival<near。返回 ProximityResult 包含起终点、目标Core ID、距离、状态和实际阈值。

ARRIVED≤60m，NEAR≤200m，其余 FAR。没有连续 tracking、自动 check-in、current stop 推断或 Trip progress mutation。GPS 转换故障抛已有内部 provider error，禁止混坐标系算到达。

## 10. Error / Cache / Data Ownership

复用既有 ExternalProviderError 层级；HTTP/timeout/connection/invalid JSON/provider status 等由原 client 处理。新增 malformed regeo、missing POI、wrong/invalid provider ID、缺 mapping、ambiguous mapping 均返回安全 unavailable 或明确内部错误。

WorldContextService 没有 TripStore 依赖，查询失败不进入生成/重规划/保存流程。TripState、walking snapshots 和 route history 不受影响。返回码不包含原 URL、provider raw error 或 key；配置凭据扫描结果无暴露。

## 11. Tests

3B_2 开始前基线：679 tests，OK (skipped=1)，83.125s（原645项3A、33项3B_1 offline、1项live默认跳过）。

新增35项离线测试：字段规范化/缺失/畸形、官方转换调用顺序、datum拒绝、regeo缓存/失败/TTL、detail及rating/cost缺失、provider ID校验、key回显防护、search候选过滤、hours边界/跨午夜/多时段/UNKNOWN/时区、mapping confidence/margin/距离/区县/NOT_APPLICABLE/完整59审计、mapping防御性校验、POI cache TTL/状态重算/跨日UNKNOWN、provider故障、threshold配置、30/120/1000m、无 walking API、Trip/KB不变。

最终完整离线 suite：`python -m scripts.run_offline_tests`，715 tests，OK (skipped=2)，82.755s；713项通过，2项live按默认配置跳过。结果记录于 `examples/location_awareness/full_tests.txt`。运行器清除测试及子进程真实配置，默认不联网；原有测试文件/预期完全未修改。

真实测试：显式 live 环境运行 `python -m unittest tests.test_location_live tests.test_walking_live -v`，2 tests，OK，3.888s；既验证3B_2真实位置/POI，也验证3B_1真实西岸路线。记录于 `examples/location_awareness/live_tests.txt`。

baseline保护审计只发现允许的 client v5 path 扩展；全部既有 test 和 Core KB 哈希保持一致。审计证据位于 `delivery_audit.json`。

## 12. Live Acceptance Evidence

查询日期2026-10-05；证据 `examples/location_awareness/live_acceptance.json`，fetched_at 以UTC存储，营业判断时间包含 +08:00。

GCJ02输入 (lat=31.167682,lng=121.463841) → 上海市/徐汇区/adcode=310104，地址「上海市徐汇区龙华街道龙耀滨江广场西岸美术馆」，街道龙腾大道2600号。

WGS84输入 (31.16,121.46) → 官方GCJ02 (31.15805826823,121.464558919271) → 上海市/徐汇区/adcode=310104，地址「上海市徐汇区龙华街道徐汇滨江绿道Gate M西岸梦中心」。明确先转换后regeo。

| Core | Provider ID | Live fields | Status |
| --- | --- | --- | --- |
| p28 西岸美术馆 | B0FFJGOAFY | 龙腾大道2600号；021-31011015；rating4.9；周营业原文 | PARTIAL / UNKNOWN |
| p30 Gate M西岸梦中心 | B0H0OSXDUD | 龙腾大道2266号；021-60196688；rating4.9；today10:00-22:00 | PARTIAL / OPEN（19:37上海时间） |
| p34 南京路步行街 | 无 | NOT_APPLICABLE；没有虚构营业信息 | UNAVAILABLE / UNKNOWN |

西岸美术馆 opentime_today 缺失，opentime_week 含「周二至周日11:00-18:00(最后入场时间17:30),周一固定闭馆」及节日说明；保留原文而不推算 today。梦中心原 today 与 week 均返回10:00-22:00；cost没有返回，保持None。

位置构造距离西岸美术馆代表点30m /120m /1000m → ARRIVED / NEAR / FAR，实际距离约30.000/120.000/1000.000m；全部查询后 TripState unchanged=true。

## 13. Known Limitations

- Core 代表点可能不是入口；接近不能证明进入或访问，GPS漂移没有本阶段自动消除。
- provider opening信息可能不完整或过时；特别说明和周规则保守UNKNOWN。本阶段不做独立官方营业日历或 Reality Check。
- 地址/POI/conversion cache仅进程内，默认30/30/60min；没有跨进程分布式缓存/QPS协调。
- 26个街道/公园/开放空间为保守NOT_APPLICABLE，未来可人工评估唯一主体；12个歧义不会提供live detail。
- 没有 Nearby、天气、到达自动visited、连续GPS、前端地图或任何3B_3/3B_4/4A功能。
- 凭据审计针对当前环境已配置已知key，不是通用secret scanner。

## 14. Manual Review Required

完整候选与全区域映射清单见 `examples/location_awareness/MAPPING_MANUAL_REVIEW.md`。以下12项保留AMBIGUOUS、provider ID为null，等待人工查收：

| Core | 待核查问题 |
| --- | --- |
| p4 鲁迅故居 | 同名候选距Core约501m，复核代表点/入口 |
| p7 新天地北里（石库门街区） | 结果主要为街区内商户，不能绑定餐厅 |
| p11 建业里 | 同名候选距Core约580m，复核范围/坐标 |
| p20 上海城隍庙 | 多个同名/子殿候选，明确主体ID |
| p24 中共一大纪念馆 | 广场/站点/馆区主体区分 |
| p32 徐家汇天主堂 | 别名/教区主体及“不对外开放”标注 |
| p33 徐家汇书院 | 图书馆总主体与子馆/厕所区分 |
| p36 西岸艺术中心 | parent 与 A/D 子馆范围区分 |
| p37 西岸穹顶艺术中心（含北广场） | 穹顶与北广场复合Core范围 |
| p40 上海摄影艺术中心 | 当前名称结果为远处摄影商户，核查名称/收录状态 |
| pz_54f53d30c0dc 安康公寓 | 历史建筑地址记录与Core命名同主体确认 |
| pz_7e40d824dbee 上海交响乐团音乐厅 | 当前品牌名称/机构与音乐厅主体确认 |

自动21项MATCHED也在清单逐条展示名称/ID/距离，并标记reviewed=false，可供人工核查。未擅自修改旧Core坐标，未把候选审核标记为人类已批准。

## 15. Ready for 3B_3?

READY（技术能力与自动/真实验收完成，未解决映射安全保留为不可查询状态）。人工映射验收仍按上表待处理；本轮停在3B_2，不启动3B_3。
