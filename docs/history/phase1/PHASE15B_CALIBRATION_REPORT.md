# ShanghaiTrace Phase 1.5B — Final POI and Route Calibration V2

交付日期：2026-10-03。27 个运行 POI、四区命名、全部访问模式与节奏已校准；全部 68 项测试通过。没有进入 Phase 2。

时间为产品规划估计，不是游客平均停留统计。徐家汇书院采用用户实际体验确认的 15/30/40 分钟，也不推断为总体游客统计。新增第二模式的保守估计已得到用户授权，标记为待人工校准。

## 1. 最终目录与全部 visit_profile

编号为 display_order，内部 ID 单独列出用于开发核对，不作为游客端地点编号。W=walk_stop，F=full_visit。每组时间为 quick / standard / deep（分钟）；† 表示新增估计，待人工校准。

| 显示编号 | 内部 ID | 中文名 | English Name | Zone | poi_type | 默认模式 | W 时间 | F 时间 |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | p2 | 永康路与嘉善路口 | Yongkang Road × Jiashan Road | A | street | walk_stop | 10/20/35 | — |
| 2 | p4 | 鲁迅故居 | Lu Xun Former Residence | C | venue | full_visit | — | 15/30/45 |
| 3 | p5 | 龙美术馆（西岸馆） | Long Museum (West Bund) | D | venue | full_visit | 15/25/40 † | 30/75/120 |
| 4 | p7 | 新天地北里（石库门街区） | Xintiandi North Block (Shikumen) | B | district | walk_stop | 15/30/60 | 30/60/90 † |
| 5 | p9 | 张园 | Zhangyuan | B | district | walk_stop | 20/40/60 | — |
| 6 | p10 | 今潮8弄 | Jinchao 8 Lanes | C | district | walk_stop | 15/30/60 | 30/60/90 † |
| 7 | p11 | 建业里 | Jianyeli | A | district | walk_stop | 10/15/25 | — |
| 8 | p12 | 陕南邨 | Shannan Village | A | district | walk_stop | 5/10/20 | — |
| 9 | p13 | 武康大楼 | Wukang Mansion | A | landmark | walk_stop | 5/15/25 | — |
| 10 | p14 | 外滩·陈毅广场 | The Bund · Chen Yi Square | B | landmark | walk_stop | 10/25/45 | — |
| 11 | p15 | 豫园 | Yu Garden | B | district | walk_stop | 30/45/60 | 60/90/120 |
| 12 | p16 | 鲁迅公园 | Lu Xun Park | C | park | full_visit | — | 30/50/75 |
| 13 | p20 | 上海城隍庙 | Shanghai City God Temple | B | venue | full_visit | — | 20/40/60 |
| 14 | p21 | 上海宋庆龄故居纪念馆 | Former Residence of Soong Ching-ling in Shanghai | A | venue | full_visit | — | 25/45/70 |
| 15 | p23 | 思南公馆 | Sinan Mansions | B | district | walk_stop | 15/30/50 | 30/60/90 † |
| 16 | p24 | 中共一大纪念馆 | Memorial of the First National Congress of the CPC | B | venue | full_visit | 15/25/40 † | 30/60/90 |
| 17 | p25 | 1927·鲁迅与内山纪念书局 | 1927 Lu Xun & Uchiyama Memorial Bookstore | C | venue | walk_stop | 10/25/40 | 20/40/60 † |
| 18 | p26 | 中国左翼作家联盟会址纪念馆 | Memorial Site of the League of Left-Wing Writers | C | venue | full_visit | — | 15/30/45 |
| 19 | p27 | 1933老场坊 | 1933 Old Millfun | C | venue | walk_stop | 15/35/60 | 30/60/90 † |
| 20 | p28 | 西岸美术馆 | West Bund Museum | D | venue | full_visit | 10/20/30 † | 30/75/120 |
| 21 | p29 | 上海油罐艺术中心 | TANK Shanghai | D | venue | walk_stop | 15/25/35 | 45/75/120 |
| 22 | p30 | Gate M 西岸梦中心 | Gate M West Bund Dream Center | D | district | walk_stop | 15/30/60 | 30/60/90 † |
| 23 | p31 | 星美术馆 | START Museum | D | venue | full_visit | 10/20/30 † | 30/60/100 |
| 24 | p32 | 徐家汇天主堂 | St. Ignatius Cathedral / Xujiahui Cathedral | A | landmark | walk_stop | 10/20/30 | 20/35/50 |
| 25 | p33 | 徐家汇书院 | Zikawei Library / Xujiahui Academy | A | venue | full_visit | — | 15/30/40 |
| 26 | p34 | 南京路步行街 | Nanjing Road Pedestrian Street | B | street | full_visit | — | 30/60/90 |
| 27 | p35 | 徐家汇商圈 | Xujiahui Commercial District | A | district | walk_stop | 20/30/45 | 60/90/150 |

所有 Supported Modes 就是表中有时间的模式；完整逐项 JSON 见 [poi_catalog.json](../../../examples/poi_catalog.json)，运行数据见 [pois.json](../../../data/pois.json)。没有 flexible 或 recommended_stay。

默认时间保持 Phase 1.5A 建议或本次明确覆盖值。第二模式待校准项：龙美术馆外观、新天地深入、今潮8弄深入、思南公馆深入、一大纪念馆外观、纪念书局深入、1933老场坊深入、西岸美术馆外观、西岸梦中心深入、星美术馆外观。其可达范围也需要人工核验。

## 2. 每个 Walk Zone 的 POI

- **Zone A：武康—复兴—徐家汇 / Wukang–Fuxing–Xujiahui**（8 个）；内部区域 ID：`wukang_fuxing_xujiahui`。

  #1 永康路与嘉善路口、#7 建业里、#8 陕南邨、#9 武康大楼、#14 上海宋庆龄故居纪念馆、#24 徐家汇天主堂、#25 徐家汇书院、#27 徐家汇商圈

- **Zone B：老城厢—新天地—外滩 / Old City–Xintiandi–Bund**（8 个）；内部区域 ID：`old_city_central`。

  #4 新天地北里（石库门街区）、#5 张园、#10 外滩·陈毅广场、#11 豫园、#13 上海城隍庙、#15 思南公馆、#16 中共一大纪念馆、#26 南京路步行街

- **Zone C：鲁迅公园—四川北路 / Lu Xun Park–North Sichuan Road**（6 个）；内部区域 ID：`hongkou_literary`。

  #2 鲁迅故居、#6 今潮8弄、#12 鲁迅公园、#17 1927·鲁迅与内山纪念书局、#18 中国左翼作家联盟会址纪念馆、#19 1933老场坊

- **Zone D：徐汇西岸滨江 / West Bund Waterfront**（5 个）；内部区域 ID：`west_bund`。

  #3 龙美术馆（西岸馆）、#20 西岸美术馆、#21 上海油罐艺术中心、#22 Gate M 西岸梦中心、#23 星美术馆

## 3. 访问范围与模式选择

- walk_stop 表示沿途或重点短停；full_visit 表示主要游览目的地，允许 park、street、district，并不隐含建筑入内或购票。
- 明确的 visit_mode_overrides 优先，否则使用 POI 默认模式；travel_pace 默认为 standard。
- 因请求明确提供的不可完整参访状态、拒绝已知门票、或时间不足而不可用时，支持 walk_stop 且允许降级的地点可以保留并降级。每个节点保留 requested_visit_mode、selected_visit_mode、downgrade_reason 和具体 scope。
- 可通过 allow_mode_downgrade=false 坚持完整参访；此时不可行就返回失败，不偷换模式。
- 豫园 W：商城及周边街区，不购园林票；F：购票入园并包含周边游览。该范围覆盖旧 Phase 1 的园林本体定义。
- 油罐 W：外观、工业遗产与滨江；F：入场看展。
- 徐家汇商圈 W：公共空间、短暂商场停留与补给；F：购物、用餐和深入商圈探索。不是单栋商场。

## 4. 坐标与缺失清单

street/district 使用 representative_lat / representative_lng；venue/landmark/park 使用 lat / lng。内部统一近似转换为 GCJ-02。代表点只用于估算接近和站间距离，不代表区域唯一位置、入口、出口或内部完整轨迹。

| 显示编号 | 地点 | 缺项 |
| ---: | --- | --- |
| — | 无：27 个 POI 均有可用坐标 | 无 |

本次已补齐此前缺失的五个地点。缺坐标保护逻辑保留，并用人工构造缺失数据的测试验证。

| 补齐地点 | 纬度 | 经度 | 存储坐标体系 | 来源 |
| --- | ---: | ---: | --- | --- |
| 上海城隍庙 | 31.225879 | 121.492466 | GCJ-02/Amap POI anchor | [公开地图](https://ditu.amap.com/place/B00155FHOA) |
| 思南公馆 | 31.214509 | 121.468956 | GCJ-02/Amap representative anchor | [公开地图](https://ditu.amap.com/place/B001574I9I) |
| 中共一大纪念馆 | 31.222060 | 121.470690 | WGS84/OpenStreetMap approximation | [公开地图](https://mapcarta.com/W372180467) |
| 中国左翼作家联盟会址纪念馆 | 31.265534 | 121.476534 | WGS84 planning approximation | [公开地图](https://hkda.shhk.gov.cn/hkda/lswm/hk_protalSite/) |
| 星美术馆 | 31.187860 | 121.470412 | GCJ-02/approximate conversion from official BD09 map anchor | [公开地图](https://www.westbund.com/en/index/KEY-PROJECTS/detail_6f9E8.html) |

城隍庙与思南公馆采用高德 POI 锚点；思南公馆是街区代表点，来源地址为复兴中路509号，目录保留523号。中共一大采用历史会址的完整 WGS84 点，原不完整经纬度另存于 coordinate_previous_record，没有拼接不同坐标系；这个锚点不代表新展馆入口。

左联会址取自虹口档案馆公开地图 WM00377，匹配多伦路201弄2号。精确点数据的坐标系尚未获得明确声明，暂按 WGS84 解释并标注 Needs manual coordinate review。星美术馆取自西岸官网 BMap 目的地（BD09：31.193849, 121.476902），近似转为 GCJ-02；原始值随数据保存。全部为地图锚点，未经游客入口实地核验。

新增坐标来源与状态：

- 徐家汇天主堂：采用 [OSM 节点 11224212192 的 Mapcarta 展示位置](https://mapcarta.com/N11224212192)，WGS84 近似锚点，尚未核实游客入口。
- 徐家汇书院：采用 [OSM 节点 10610507005 的 Mapcarta 展示位置](https://mapcarta.com/N10610507005)，与历史徐家汇藏书楼区分，尚未核实入口。
- 南京路：采用[公开位置参考](https://opentravelguide.com/china/shanghai/shanghai/attractions/nanjing-road-pedestrian-street/)作为暂定代表点。来源坐标系未核实，暂按 WGS84 解释并明确提示人工复核；不宣称为准确中点。
- 徐家汇商圈：参考[美罗城 OSM 展示位置](https://mapcarta.com/W225521733)，向港汇方向选取近似公共空间锚点，是产品选择点，未经入口或地理中心核验。

运行代码无联网或地图导航调用；以上只用于本次静态数据校准。旧坐标沿用既有资料及其近似性质。

## 5. 全部测试结果

```text
python -m unittest discover -s tests -t . -q
Ran 68 tests in 5.727s
OK
```

实际运行环境：Python 3.14.6。原 39 项测试按新区域和模式语义更新保留；新增 29 项校准与边界测试。

| 测试文件 | 测试数 | 结果 |
| --- | ---: | --- |
| test_cli.py | 4 | 全通过 |
| test_geo_utils.py | 2 | 全通过 |
| test_recommendation.py | 5 | 全通过 |
| test_repository.py | 6 | 全通过 |
| test_route_engine.py | 22 | 全通过 |
| test_visit_calibration.py | 29 | 全通过 |

A–H：书院 F=30；南京路 F=60；徐家汇商圈 W=30/F=90；豫园 W=45/F=90；油罐 W=25/F=75，均通过。还覆盖三档节奏、模式校验、闭馆/门票/预算降级、必去完整性、降级关闭、代表坐标、软站数目标、五次完整输出一致性，以及独立重算预算。

旧豫园 90 分钟不可行测试现明确指定 full_visit 并禁止降级，继续验证最低 105 分钟；默认 walk_stop 的 90 分钟请求则可以成功。这是本次确认后的预期变化。

## 6. 五条人工路线测试输出

以下为用户指定的五组请求的实际程序输出，供人工复核；不是已完成实地体验审核的声明。未提供起点，首站到达前移动不计入预算。全部 standard。完整 JSON 见 [route_plans.json](../../../examples/route_plans.json)，含每站模式、时间、距离、分数、匹配标签、解释与警告；游客可读全文见 [manual_routes.txt](../../../examples/manual_routes.txt)。

| 路线 | 顺序 | 估算 km | 步行 min | 停留 min | 缓冲 min | 总计 / 预算 min | 软站数目标 |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1 | #8 陕南邨（W，10） → #1 永康路与嘉善路口（W，20） → #7 建业里（W，15） → #24 徐家汇天主堂（W，20） → #25 徐家汇书院（F，30） | 4.641 | 61.89 | 95 | 15 | 171.89 / 180 | 4–5；达到 |
| 2 | #12 鲁迅公园（F，50） → #2 鲁迅故居（F，30） | 0.483 | 6.43 | 80 | 15 | 101.43 / 120 | 3–4；未达到 |
| 3 | #21 上海油罐艺术中心（W，25） → #20 西岸美术馆（W，20） → #3 龙美术馆（西岸馆）（F，75） | 2.827 | 37.69 | 120 | 15 | 172.69 / 180 | 4–5；未达到 |
| 4 | #10 外滩·陈毅广场（W，25） → #26 南京路步行街（F，60） → #4 新天地北里（石库门街区）（W，30） | 3.546 | 47.28 | 115 | 15 | 177.28 / 180 | 4–5；未达到 |
| 5 | #1 永康路与嘉善路口（W，20） → #27 徐家汇商圈（W，30） | 3.644 | 48.59 | 50 | 15 | 113.59 / 180 | 4–5；未达到 |

静态结果检查：

- Route 1：陕南邨 → 永康路 → 建业里 → 徐家汇天主堂 → 徐家汇书院。从原武康—复兴片区进入徐家汇后没有再返回，片区转换一次；在当前坐标估算模型下通过顺序检查。实际入口与道路连通仍待核验。
- Route 2：鲁迅公园与故居两站。50+30 分钟停留加移动和缓冲后为 101.43 分钟，剩余 18.57 分钟不足以加入现有相关候选。未达到 3–4 站软目标，保留警告。
- Route 3：油罐外观 → 西岸美术馆外观 → 龙美术馆完整参访。西岸美术馆因剩余时间不足从默认 full_visit 降为 walk_stop，已记录；该外观时间为待校准估计，不宣称实际看过两座美术馆展览。未达到 4–5 站软目标。
- Route 4：外滩 → 南京路 → 新天地。南京路合理纳入且为 full_visit 60 分钟；总计 177.28 分钟，预算余量较小。其他符合当前兴趣的候选无法在预算内插入，未硬凑四站。
- Route 5：永康路 → 徐家汇商圈。商圈以默认 walk_stop 30 分钟进入；其他可规划候选没有请求的购物/现代城市兴趣匹配，不用建筑文化点凑站数。完整购物目的地体验应显式指定商圈 full_visit=90。

## 7. Route Engine 当前行为和限制

- 时间来自 selected mode × travel_pace，不再取旧停留区间中值；默认模式与用户覆盖均有可追溯记录。
- 必去点先安排；小规模访问顺序可穷举优化，插入候选时重新核算总预算，最多五个节点的候选集合按最短估算开放路径排序，减少片区来回跳跃。
- 相关性先过滤：给定 interest_tags 时可选点至少匹配一个兴趣；没有兴趣标签时至少匹配一个已给体验或文化标签；全空请求才不做标签过滤。必去不受此软相关性限制。
- 站数目标为 ≤90 分钟 2–3 站、91–150 分钟 3–4 站、151–240 分钟 4–5 站。选择优先趋向目标上沿，不能突破预算或删除必去；必去数量可超过目标上沿。未达到就提示。
- 联合模式/点集/区域选择仍是启发式：不会为了提高站数主动降级已经可行的完整参访，也不全局替换已选点；软目标未达到不等于证明不存在更多站方案。
- 直线距离乘固定绕行因子不识别街道、围墙、过街、入口或交通。区域型 POI 内部移动包含在参访体验中，但未单独计入估算移动里程；无法保证真实累计步行上限。
- 闭馆依赖 full_visit_unavailable_poi_ids 的明确输入，不解析日期/开放时间文字，不检查实时状态；外部 walk_stop 可达性也未实时验证。
- 门票与预约未知仍提示；willing_to_buy_tickets=false 只处理已知需要门票的模式，不把 full_visit 一律当作收费。
- 跨区仅由必去触发，全程按步行估计；既有符号跨区惩罚未随意赋值。超过八个必去点的搜索失败不冒充不可行证明。
- 临时代表坐标与十项第二模式时间需要后续人工核验。自动测试不能证明现实游客体验已经合格。

## 8. 文件变更

修改：data/pois.json；src/models.py、poi_repository.py、route_engine.py、__init__.py；tools/demos/demo.py；examples/request.json、route_plans.json；tests/helpers.py、test_repository.py、test_recommendation.py、test_route_engine.py、test_cli.py；README.md、CONTEXT.md 与历史记录提示。

新增：src/visit_planner.py；tests/test_visit_calibration.py；scripts/calibrate_phase15b.py、export_phase15b_audit.py；本报告；examples/poi_catalog.json、manual_routes.txt；data/archive/pois_phase1.json、examples/phase1/route_plans_phase1.json。旧原始 v1/v2/v3 文件保留作为历史来源，不参与当前运行；当前核心集合完全移除两个旧 POI。

本阶段完成并停止，不接入 LLM、OpenAI API、Agent Framework、RAG、数据库服务器或前端重构。
