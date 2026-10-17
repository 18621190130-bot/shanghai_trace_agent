# TraceMate Phase 3B_2.2 验收报告

状态：**READY**。本轮开发结束，STOP，等待人工验收。未进入 Phase 3B_3。

生产 Core 维持 58 项，p40 不恢复。Phase 3A 与 Phase 3B_1 冻结实现保持；空间层通过 POIRepository 的坐标契约接入，无 RouteEngine / Trip / RouteVersion / CAS / Walking 实现改写。

## Remaining Identity Resolution

| Core | 最终身份 | Provider ID | 判断依据 |
| --- | --- | --- | --- |
| p10 今潮8弄 | MATCHED，NOT_APPLICABLE | B0HDACXK1W | 虹口区、特色商业街、四川北路989弄35–95号，同主体，旧位置近980m误差不再作为否决理由 |
| p12 陕南邨 | MATCHED，NOT_APPLICABLE | B00156COKX | 黄浦区、住宅小区、陕西南路187弄1–87号；151至187门牌段是同一历史住宅群的地址范围 |
| p34 南京路步行街 | MATCHED，NOT_APPLICABLE | B0IA369WVI | 黄浦区道路名正式主体，不绑定商店或更广的商业街区 |
| p35 徐家汇商圈 | NOT_FOUND，NOT_APPLICABLE | null | Core 指美罗城/港汇公共空间核心体验区；单商场、办公楼和徐家汇源均不能代表整个商圈。独立 AREA anchor/extent 完整 |
| p25 1927·鲁迅与内山纪念书局 | MATCHED，FULL | B0I2KZFZRY | 当前运营书局，虹口区四川北路2056号；内山书店只保留历史语义。MANUAL_SEMANTIC_SCOPE_CONFIRMATION，reviewed=true |
| 多伦路文化名人街 | MATCHED，NOT_APPLICABLE | B00155FLFD | 文化街主体，虹口区多伦路；不使用普通道路 BZAGR0033N。MANUAL_SEMANTIC_SCOPE_CONFIRMATION，reviewed=true |

formal detail、周边地图实体与端点证据保存在 `examples/spatial_identity/provider_evidence.json`。本轮 Identity reviewed=true 明确记为 CODEX_UNDER_OWNER_AUTHORIZATION，表示依据用户本轮授权完成，不假称负责人已亲自验收。

今潮地址及主体参考[虹口区官方介绍](https://www.shhk.gov.cn/xwzx/002003/20211201/f7e7613f-be5d-4c30-93c1-e2edbbf45b2d.html)。陕南邨名称和历史地址参考[市绿化市容局](https://lhsr.sh.gov.cn/ywdt/20240807/5c8cb815-ef70-4bd1-909d-b31c45574382.html)，151–187门牌范围由[上观现场报道](https://www.shobserver.cn/wx/detail.do?id=47533) corroborate；本轮据此判断151旧门牌与187弄 provider 地址属同一住宅群。

南京步行街东西范围依据[上海市南京路步行街管理办法](https://www.shanghai.gov.cn/xxzfgzwj/20220127/d2c2979752314dc69738454f24cd515c.html)，同名商业街区范围与道路体验分开。书局当前文化活动及甜爱路语境参考[虹口官方报道](https://www.shhk.gov.cn/xwzx/002005/20251222/2cbc6abf-6327-465e-859c-c1c29873c841.html)，多伦街文化语境参考[虹口官方介绍](https://www.shhk.gov.cn/xwzx/002003/20240226/c159f769-0d8b-48d5-a8a9-d7fc432cfdad.html)。徐家汇核心商业载体参考[市商务委报道](https://sww.sh.gov.cn/swdt/20240220/42959b17d7da40d6b1ee2da5b196d64a.html)；该来源不被冒充为 polygon 的官方边界。

## Coordinate Corrections

纬度、经度；新坐标均为正式高德 GCJ02 身份位置。

| Core | 原始坐标 | 原 datum | 新 GCJ02 | 规范化后偏移 |
| --- | --- | --- | --- | ---: |
| p10 | 31.258800, 121.478200 | GCJ02 approximate | 31.251626, 121.484182 | 979.64m |
| p12 | 31.215800, 121.456500 | GCJ02 approximate | 31.214589, 121.460986 | 447.35m |
| p34 | 31.235900, 121.480500 | WGS84 planning approximation | 31.236534, 121.482374 | 381.44m |

p34 旧坐标先复用现有转换规范化为 GCJ02 `(31.2339412584,121.4850009005)` 再计算偏移。新数据同步改正 datum 标签，避免对正式 GCJ02 二次做 WGS84 转换。仅上述三项 representative lat/lng 与必要 datum 标签发生 Core 变更；名称、语义、票务、停留模式、zone、排序等未改。

继续使用 `examples/location_awareness/coordinate_corrections.json`，保留3B_2.1的p4/p11记录；本轮各项含old/new、provider ID、偏移、reason、reviewed、授权来源及证据引用。

## Spatial Model

`data/core_spatial_profiles.json` 独立于 Identity sidecar，按全部58个Core ID建档。空间来源、confidence、notes、reviewed完整。

- POINT：单体场馆/建筑；路线使用原 Core 规范化正式点，无 extent。
- AREA：区域/园区/广场；路线使用 route_anchor，范围以 POLYGON 或 CENTER_RADIUS 描述。
- LINEAR：线性街道；使用推荐入口 anchor、secondary anchor、START_END 或 POLYLINE extent。

Identity、Anchor、Extent 独立。所有空间坐标显式GCJ02；AREA/LINEAR 的原始身份位置保留在 Core 和 POI.original_coordinates，路线 POI.coordinates 由空间 repository 覆盖为 anchor。历史/候选KB不加载生产空间sidecar。Identity matcher 与候选查询仍使用原始身份坐标，避免按导航入口误判实体身份。

Extent来源可为 PROVIDER / DERIVED / TRACEMATE_CURATED；PROVIDER 必须有实际boundary reference。当前 PROVIDER=0，未伪造官方边界。26个AREA采用明确半径的体验近似范围，徐家汇使用curated polygon；五条街提供derived/curated线性范围。所有空间reviewed=false，待负责人本轮产品验收，独立于身份授权reviewed。7项导航anchor相对规范Core身份位置的独立覆盖记录见 `examples/spatial_identity/anchor_overrides.json`。

纯geometry辅助支持polygon内外/边缘、线段距离及局部范围验证。未新增geofence自动到达、离开、Trip切换、天气或UI。secondary anchor仅元数据，未自动安排整条街内部穿行或增加其walking时间。

## Area / Linear Profiles

| Core | Type | 导航 anchor GCJ02 | Extent |
| --- | --- | --- | --- |
| 徐家汇商圈 | AREA | 31.193781,121.438463，公共路口；TRACEMATE_CURATED | 核心美罗城/港汇及相邻公共空间近似polygon；非整个中央活动区 |
| 南京路步行街 | LINEAR | 31.234789,121.475710，西侧公共步行起点 | DERIVED polyline，东侧secondary为31.238985,121.490045 |
| 新天地北里 p7 | AREA | 31.220692,121.474751，保留规范Core访问点 | 130m CENTER_RADIUS，TRACEMATE_CURATED体验近似 |
| 多伦路文化名人街 | LINEAR | 31.262091,121.483703，文化街牌坊 | TRACEMATE_CURATED polyline，北接四川北路 |
| 甜爱路 | LINEAR | 31.264694,121.483313，四川北路交叉口 | DERIVED START_END，首版至甜爱支路体验段 |
| 武康路历史文化名街 | LINEAR | 31.203998,121.437919，淮海中路交叉口 | DERIVED START_END，至华山路；非精确道路几何 |

完整32项含主要滨江开放空间及来源、confidence、secondary、reviewed见 `SPATIAL_PROFILE_REVIEW.md`。陈毅广场另经formal detail验证，空间anchor优先采用B00155G6WO位置 `(31.238992,121.490390)`，比旧Core访问点偏移296.51m，Core坐标未重写。其100m范围围绕真实广场主体；这是空间anchor调整，与本节前三项Core坐标修正分开记录。

新天地、公园、滨江空间的圆只表示访问点附近体验范围，不声称完整公园边界。现有Core anchor未从extent中心计算；同主体地图核验偏移作为佐证随记录保存。

## Identity Audit

MATCHED = **57**；AMBIGUOUS = **0**；NOT_FOUND = **1**；TOTAL = **58**。

NOT_FOUND只有p35徐家汇商圈，是合法无统一主体情形。FULL=20、LIMITED=22、NOT_APPLICABLE=16。无search failures、无遗留manual identity ambiguity。当前审计：`examples/spatial_identity/identity_audit.json`；旧3B_2.1报告与审计保留历史事实，不混作当前统计。

## Spatial Audit

POINT = **26**；AREA = **27**；LINEAR = **5**；TOTAL = **58**。

AREA/LINEAR有效anchor **32/32**；有效extent **32/32**；LINEAR secondary **5/5**；身份与空间集合完全相同。配置非法datum、NaN、非法confidence、缺anchor、缺Core记录、不闭合/自交/退化polygon、伪PROVIDER来源均拒绝。缺extent只允许显式REVIEW_REQUIRED，本次没有缺失项。

## Route Compatibility

p35的NOT_FOUND不阻塞generate、walking hydrate、replan。真实walking输出有geometry、distance、duration，stop与各leg端点使用anchor。Replan生成新version，original_route与v1不变。skip保留原有处置语义；remove通过既有restricted mutation重建walking、CAS提交v2，保留未删除站点顺序、不refill、不标作skipped，original/v1不变。测试见 `tests/test_spatial_identity.py`。

Proximity仍依据anchor的原有阈值；在徐家汇polygon内部但距离anchor较远的点仍可FAR，证明未改变为geofence。身份状态不参与路线许可。

## Tests

完整offline：`python -m scripts.run_offline_tests`，**762项，758通过，4项opt-in live跳过**。涵盖Phase3A、3B_1、3B_2、3B_2.1、3B_2.2；本轮新增24项offline和1项live。最终日志：`examples/spatial_identity/offline_regression.txt`。

完整live：`python -m unittest tests.test_walking_live tests.test_location_live tests.test_identity_calibration_live tests.test_spatial_identity_live -q`，**4/4 PASS**。额外保存的五组真实路线与Replan验收见 `examples/spatial_identity/live_acceptance.json`：

| Core | 首版walking距离 | Geometry点数 | Replan |
| --- | ---: | ---: | --- |
| p10 | 2777m | 139 | success |
| p12 | 4466m | 198 | success |
| p34 | 3564m | 113 | success |
| p35 | 2000m | 92 | success |
| 多伦路 | 2886m | 122 | success |

Provider实时结果可能变化；以上为保存的本次验收样本。Core严格变更范围与冻结源码SHA-256对照见 `examples/spatial_identity/delivery_audit.json`；配置密钥内容未写入交付文件。

## Manual Review Required

Identity：无待决歧义。徐家汇无统一provider主体已按规范收口，不再请求商场替代ID。

Anchor / Extent：负责人最终判断徐家汇公共路口与核心polygon范围、南京西侧步行起点、多伦牌坊与弯折线、甜爱体验段、武康/福州端点是否符合产品体验；检查新天地及滨江开放空间的近似体验半径是否合适。均已落地为可查看、可测试的首版方案，没有未执行的坐标修正或字段补全工作。当前不是精确GIS/完整地块范围交付。

## Ready to Freeze Phase 3B_2?

**READY**。`PHASE3B_2_FREEZE.md` 和带哈希的冻结候选包已准备。依据任务最终条款，等待人工验收后才标记正式FROZEN；本轮到此STOP，未开始Phase3B_3。
