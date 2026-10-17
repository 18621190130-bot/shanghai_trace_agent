# Spatial Profile Review — Phase 3B_2.2

58 Core：26 POINT、27 AREA、5 LINEAR。下表覆盖全部 32 个 AREA/LINEAR。所有坐标为纬度、经度，GCJ02。

范围是首版 City Walk 体验范围，非行政边界、精确地籍或开放许可；没有伪装为 PROVIDER 的边界。CORE_EXISTING anchor 保留现有访问点并记录同主体地图匹配的偏移，不由 extent 求几何中心。

Reviewed=false 仅表示负责人尚未完成本次空间产品验收；不表示缺少必需字段。所有 32 项已通过模型校验。Identity 的授权确认状态独立。

| Core | Spatial Type | Anchor lat, lng | Anchor Source / Confidence | Extent Type | Extent Source / Confidence | Reviewed |
| --- | --- | --- | --- | --- | --- | --- |
| p2 永康路与嘉善路口 | AREA | 31.212800, 121.459200 | CORE_EXISTING / 0.75 | CENTER_RADIUS (90m) | TRACEMATE_CURATED / 0.55 | false |
| p7 新天地北里（石库门街区） | AREA | 31.220692, 121.474751 | CORE_EXISTING / 0.75 | CENTER_RADIUS (130m) | TRACEMATE_CURATED / 0.55 | false |
| p9 张园 | AREA | 31.227971, 121.460064 | CORE_EXISTING / 0.75 | CENTER_RADIUS (150m) | TRACEMATE_CURATED / 0.55 | false |
| p10 今潮8弄 | AREA | 31.251626, 121.484182 | CORE_EXISTING / 0.75 | CENTER_RADIUS (150m) | TRACEMATE_CURATED / 0.55 | false |
| p11 建业里 | AREA | 31.203688, 121.451802 | CORE_EXISTING / 0.75 | CENTER_RADIUS (160m) | TRACEMATE_CURATED / 0.55 | false |
| p12 陕南邨 | AREA | 31.214589, 121.460986 | CORE_EXISTING / 0.75 | CENTER_RADIUS (160m) | TRACEMATE_CURATED / 0.55 | false |
| p14 外滩·陈毅广场 | AREA | 31.238992, 121.490390 | AMAP_POI / 0.9 | CENTER_RADIUS (100m) | TRACEMATE_CURATED / 0.55 | false |
| p15 豫园 | AREA | 31.227000, 121.492500 | CORE_EXISTING / 0.75 | CENTER_RADIUS (240m) | TRACEMATE_CURATED / 0.55 | false |
| p16 鲁迅公园 | AREA | 31.271200, 121.484400 | CORE_EXISTING / 0.75 | CENTER_RADIUS (420m) | TRACEMATE_CURATED / 0.55 | false |
| p23 思南公馆 | AREA | 31.214509, 121.468956 | CORE_EXISTING / 0.75 | CENTER_RADIUS (180m) | TRACEMATE_CURATED / 0.55 | false |
| p30 Gate M 西岸梦中心 | AREA | 31.161190, 121.465465 | CORE_EXISTING / 0.75 | CENTER_RADIUS (350m) | TRACEMATE_CURATED / 0.55 | false |
| p34 南京路步行街 | LINEAR | 31.234789, 121.475710 | AMAP_POI / 0.88 | POLYLINE | DERIVED / 0.7 | false |
| p35 徐家汇商圈 | AREA | 31.193781, 121.438463 | TRACEMATE_CURATED / 0.82 | POLYGON | TRACEMATE_CURATED / 0.65 | false |
| p37 西岸穹顶艺术中心（含北广场） | AREA | 31.163167, 121.464561 | CORE_EXISTING / 0.75 | CENTER_RADIUS (160m) | TRACEMATE_CURATED / 0.55 | false |
| p38 滨江滑板公园 | AREA | 31.185976, 121.467781 | CORE_EXISTING / 0.75 | CENTER_RADIUS (200m) | TRACEMATE_CURATED / 0.55 | false |
| p39 徐汇跑道公园 | AREA | 31.168592, 121.457730 | CORE_EXISTING / 0.75 | CENTER_RADIUS (350m) | TRACEMATE_CURATED / 0.55 | false |
| p42 徐汇滨江海事塔广场 | AREA | 31.177546, 121.462400 | CORE_EXISTING / 0.75 | CENTER_RADIUS (100m) | TRACEMATE_CURATED / 0.55 | false |
| pz_a74f9e58195a 古城公园 | AREA | 31.228427, 121.493836 | CORE_EXISTING / 0.75 | CENTER_RADIUS (160m) | TRACEMATE_CURATED / 0.55 | false |
| pz_0b545bb1cf2a 四川北路公园 | AREA | 31.254871, 121.484802 | CORE_EXISTING / 0.75 | CENTER_RADIUS (220m) | TRACEMATE_CURATED / 0.55 | false |
| pz_b72e3b8998b3 多伦路文化名人街 | LINEAR | 31.262091, 121.483703 | AMAP_POI / 0.88 | POLYLINE | TRACEMATE_CURATED / 0.6 | false |
| pz_b4acff8f32fc 甜爱路 | LINEAR | 31.264694, 121.483313 | AMAP_POI / 0.88 | START_END | DERIVED / 0.7 | false |
| pz_68957332b418 太平桥公园 | AREA | 31.219646, 121.477882 | CORE_EXISTING / 0.75 | CENTER_RADIUS (250m) | TRACEMATE_CURATED / 0.55 | false |
| pz_8919938b21f2 淮海公园 | AREA | 31.223115, 121.477591 | CORE_EXISTING / 0.75 | CENTER_RADIUS (150m) | TRACEMATE_CURATED / 0.55 | false |
| pz_bd40d04c7f5d 复兴公园 | AREA | 31.216980, 121.469115 | CORE_EXISTING / 0.75 | CENTER_RADIUS (300m) | TRACEMATE_CURATED / 0.55 | false |
| pz_a87eb2b5b5da 武康路历史文化名街 | LINEAR | 31.203998, 121.437919 | AMAP_POI / 0.88 | START_END | DERIVED / 0.7 | false |
| pz_553cfd36707c 衡山公园 | AREA | 31.200607, 121.442139 | CORE_EXISTING / 0.75 | CENTER_RADIUS (120m) | TRACEMATE_CURATED / 0.55 | false |
| pz_a27dbbc6cab8 襄阳公园 | AREA | 31.216991, 121.456737 | CORE_EXISTING / 0.75 | CENTER_RADIUS (160m) | TRACEMATE_CURATED / 0.55 | false |
| pz_a446052910a0 山阴路274弄 | AREA | 31.268259, 121.484567 | CORE_EXISTING / 0.75 | CENTER_RADIUS (100m) | TRACEMATE_CURATED / 0.55 | false |
| pz_0db17d82e9ec 上海人民广场 | AREA | 31.228827, 121.475213 | CORE_EXISTING / 0.75 | CENTER_RADIUS (300m) | TRACEMATE_CURATED / 0.55 | false |
| pz_cc5300aee299 福州路 | LINEAR | 31.231509, 121.476291 | AMAP_POI / 0.88 | START_END | DERIVED / 0.7 | false |
| pz_de47b0cf3e98 中南新邨 | AREA | 31.207084, 121.442661 | CORE_EXISTING / 0.75 | CENTER_RADIUS (150m) | TRACEMATE_CURATED / 0.55 | false |
| pz_09b5938601ee 徐家汇公园 | AREA | 31.197401, 121.442461 | CORE_EXISTING / 0.75 | CENTER_RADIUS (300m) | TRACEMATE_CURATED / 0.55 | false |

## 重点验收项

徐家汇商圈的矩形 polygon 限定美罗城、港汇及相邻教堂前公共空间核心片区，不代表更广的徐家汇中央活动区。

南京路西侧 anchor 是观光车位置旁的公共步行起点，不要求乘车或买票；多伦路使用文化街牌坊入口；甜爱路采用四川北路至甜爱支路首版体验段；武康路、福州路使用道路端点。secondary anchor 当前不增加路线内部步行用时。

新天地北里、外滩陈毅广场及西岸主要开放空间使用现有访问点和明确的体验半径。半径只描述访问点附近的首版体验范围；例如跑道公园 350m 圆不声称覆盖整条跑道。产品若要求完整公园边界，需以后另取边界，当前没有自动 geofence。

真正仍需负责人选择的是上述体验范围及入口是否符合产品希望的游览段；没有遗留 AMBIGUOUS 身份，也不需为徐家汇选择一个替代商场身份。其余字段与坐标规范化已自动完成。

## p2 永康路与嘉善路口

Anchor：永康路与嘉善路口 City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 90m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.

## p7 新天地北里（石库门街区）

Anchor：新天地北里（石库门街区） City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 130m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.

## p9 张园

Anchor：张园 City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 150m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.

## p10 今潮8弄

Anchor：今潮8弄 City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 150m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.

## p11 建业里

Anchor：建业里 City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 160m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.

## p12 陕南邨

Anchor：陕南邨 City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 160m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.

## p14 外滩·陈毅广场

Anchor：外滩-陈毅广场；Verified formal square identity position takes priority over the older Core point 296.5m away. Public square visit anchor; no Core identity coordinate rewrite.

Extent：100m first-version public square experience vicinity around the verified formal Chen Yi Square position. Not the entire Bund or a provider boundary.

## p15 豫园

Anchor：豫园 City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 240m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.

## p16 鲁迅公园

Anchor：鲁迅公园 City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 420m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.

## p23 思南公馆

Anchor：思南公馆 City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 180m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.

## p30 Gate M 西岸梦中心

Anchor：Gate M 西岸梦中心 City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 350m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.

## p34 南京路步行街

Anchor：南京东路观光车；Recommended western public walking-start vicinity beside the sightseeing-car position. No ticket/service use is required; not claimed as an official surveyed gate.

Extent：Approximate City Walk street experience extent from named map features; straight chords/curated bends are not surveyed roadway geometry or provider boundary. Secondary anchor is metadata only; no automatic traversal, exit selection or internal walking-time addition.

Secondary：31.238985, 121.490045；中山东一路与南京东路交叉口；Eastern walking-space exit towards the Bund.

## p35 徐家汇商圈

Anchor：肇嘉浜路与虹桥路交叉口；Public junction beside the central Metro City/Grand Gateway cluster; curated City Walk entry, not a mall identity or region centroid.

Extent：Product review polygon limited to the Core central Metro City/Grand Gateway shopping and public-space cluster, including the adjacent cathedral frontage. Excludes the wider Xujiahui central activity district. Approximate bounds, not Amap or governmental commercial-district boundary.

## p37 西岸穹顶艺术中心（含北广场）

Anchor：西岸穹顶艺术中心（含北广场） City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 160m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.

## p38 滨江滑板公园

Anchor：滨江滑板公园 City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 200m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.

## p39 徐汇跑道公园

Anchor：徐汇跑道公园 City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 350m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.

## p42 徐汇滨江海事塔广场

Anchor：徐汇滨江海事塔广场 City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 100m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.

## pz_a74f9e58195a 古城公园

Anchor：古城公园 City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 160m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.

## pz_0b545bb1cf2a 四川北路公园

Anchor：四川北路公园 City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 220m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.

## pz_b72e3b8998b3 多伦路文化名人街

Anchor：多伦路文化名人街牌坊；Enter the cultural street at the southern archway; not its ordinary road identity.

Extent：Approximate City Walk street experience extent from named map features; straight chords/curated bends are not surveyed roadway geometry or provider boundary. Secondary anchor is metadata only; no automatic traversal, exit selection or internal walking-time addition.

Secondary：31.265131, 121.481874；多伦路与四川北路交叉口；Northern connection back to Sichuan North Road.

## pz_b4acff8f32fc 甜爱路

Anchor：四川北路与甜爱路交叉口；Southern entry from Sichuan North Road; start a walk along the cultural street.

Extent：Approximate City Walk street experience extent from named map features; straight chords/curated bends are not surveyed roadway geometry or provider boundary. Secondary anchor is metadata only; no automatic traversal, exit selection or internal walking-time addition.

Secondary：31.268113, 121.484034；甜爱路与甜爱支路交叉口；Secondary anchor at Tianai Branch Road; first-version romantic-walk segment.

## pz_68957332b418 太平桥公园

Anchor：太平桥公园 City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 250m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.

## pz_8919938b21f2 淮海公园

Anchor：淮海公园 City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 150m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.

## pz_bd40d04c7f5d 复兴公园

Anchor：复兴公园 City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 300m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.

## pz_a87eb2b5b5da 武康路历史文化名街

Anchor：武康路与淮海中路交叉口；Recommended southern entry beside Wukang Mansion; walk north along the historical street.

Extent：Approximate City Walk street experience extent from named map features; straight chords/curated bends are not surveyed roadway geometry or provider boundary. Secondary anchor is metadata only; no automatic traversal, exit selection or internal walking-time addition.

Secondary：31.213351, 121.439162；华山路与武康路交叉口；Northern secondary anchor connecting Huashan Road.

## pz_553cfd36707c 衡山公园

Anchor：衡山公园 City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 120m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.

## pz_a27dbbc6cab8 襄阳公园

Anchor：襄阳公园 City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 160m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.

## pz_a446052910a0 山阴路274弄

Anchor：山阴路274弄 City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 100m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.

## pz_0db17d82e9ec 上海人民广场

Anchor：上海人民广场 City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 300m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.

## pz_cc5300aee299 福州路

Anchor：福州路与西藏中路交叉口；Western entry for the bookish/street-scene walk.

Extent：Approximate City Walk street experience extent from named map features; straight chords/curated bends are not surveyed roadway geometry or provider boundary. Secondary anchor is metadata only; no automatic traversal, exit selection or internal walking-time addition.

Secondary：31.23563, 121.490436；中山东一路与福州路交叉口；Eastern secondary anchor at the Bund approach.

## pz_de47b0cf3e98 中南新邨

Anchor：中南新邨 City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 150m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.

## pz_09b5938601ee 徐家汇公园

Anchor：徐家汇公园 City Walk anchor；Retained existing Core visit position, corroborated against the current same-entity map identity and its recorded offset; not generated from an extent centroid and not claimed as a verified gate.

Extent：First-version City Walk experience vicinity: 300m around an existing place anchor. Product approximation chosen for this park/complex/lane/plaza scale; not a provider boundary, building footprint, public-access guarantee or whole administrative area.
