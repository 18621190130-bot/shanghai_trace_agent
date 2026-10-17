# PHASE 2.5B FINAL HUMAN REVIEW REPORT

本轮仅落实人工审核与六项定向事实核验。最终 staging 集合没有导入 production，未执行 Phase 2.5C、路线回归或地图步行路由。

| 统计 | 数量 |
| --- | ---: |
| 已有 production anchors | 5 |
| 已批准新增 supporting stops | 6 |
| 已批准新增 transition stops | 2 |
| 尚待核验的条件节点 | 1 |
| 本轮条件核验通过 | 2 |
| 总可选 route nodes | 13 |

conditional 数量指尚未通过的节点；本轮核验通过的海事塔、大剧院已归入 B/C，统计不重复。节点数量不是 quota。

## A. 已有 production anchors

| 名称 | 决定 | 角色 | 可选/新增计数 | 坐标 (GCJ-02 lat,lng) | interest / experience / culture | 原因 |
| --- | --- | --- | --- | --- | --- | --- |
| 龙美术馆（西岸馆） | recommended_accept | anchor | True/False | [31.1848, 121.465] | art, industrial_heritage, waterfront, architecture / museum_visit, adaptive_reuse, riverside_walk, photogenic / industrial_transformation, urban_renewal, modern_shanghai | 人工接受既有 production anchor；不计新增。 |
| 西岸美术馆 | recommended_accept | anchor | True/False | [31.167682, 121.463841] | art, waterfront, architecture / museum_visit, riverside_walk, photogenic / urban_renewal, industrial_transformation, modern_shanghai | 人工接受既有 production anchor；不计新增。 |
| 上海油罐艺术中心 | recommended_accept | anchor | True/False | [31.164519, 121.464321] | art, industrial_heritage, architecture, waterfront / museum_visit, adaptive_reuse, photogenic, riverside_walk / industrial_transformation, urban_renewal, modern_shanghai | 人工接受既有 production anchor；不计新增。 |
| Gate M 西岸梦中心 | recommended_accept | anchor | True/False | [31.16119, 121.465465] | industrial_heritage, waterfront, shopping_lifestyle, modern_city / adaptive_reuse, riverside_walk, shopping_leisure, photogenic / industrial_transformation, urban_renewal, modern_shanghai | 人工接受既有 production anchor；不计新增。 |
| 星美术馆 | recommended_accept | anchor | True/False | [31.18786, 121.470412] | art, industrial_heritage, architecture / museum_visit, adaptive_reuse, architecture_detail / industrial_transformation, urban_renewal, modern_shanghai | 人工接受既有 production anchor；不计新增。 |

五个 production ID 保持原身份、坐标与内容快照，primary=anchor；既有 walk_stop 支持 supporting_stop eligibility。均 counts_as_new_stop=false。

## B. 已批准的新 supporting stops

| 名称 | 决定 | 角色 | 可选/新增计数 | 坐标 (GCJ-02 lat,lng) | interest / experience / culture | 原因 |
| --- | --- | --- | --- | --- | --- | --- |
| 西岸艺术中心 | recommended_accept | supporting_stop | True/True | [31.167719, 121.461939] | art, industrial_heritage, architecture / adaptive_reuse, architecture_detail / industrial_transformation | 人工接受一个独立 staging 节点。 |
| 西岸穹顶艺术中心（含北广场） | recommended_accept | supporting_stop | True/True | [31.163167, 121.464561] | art / — / — | 人工接受一个独立 staging 节点。 |
| 滨江滑板公园 | recommended_accept | supporting_stop | True/True | [31.185976, 121.467781] | parks, waterfront / riverside_walk, social_observation / public_life | 人工接受一个独立 staging 节点。 官方公众台阶观察区域已确认。采用高德瑞宁路同名公园访问代表点，保留OSM几何点差异约180米；无独立入口证明，不拆节点。精确台阶入口坐标未测绘，不声称该点就是门口。 |
| 徐汇跑道公园 | recommended_accept | supporting_stop | True/True | [31.168592, 121.45773] | parks, history / adaptive_reuse, street_scene / urban_renewal | 人工接受一个独立 staging 节点。 线性公园以高德丰谷路南段访问点作为代表，不用OSM线性几何中心冒充入口。代表点在原多边形西侧约26米、原150米审核缓冲内；落实人工接受边界审核点，原polygon和margin均不改。 |
| 上海摄影艺术中心 | recommended_accept | supporting_stop | True/True | [31.167943363813837, 121.46296269374524] | art, architecture / museum_visit / — | 人工接受一个独立 staging 节点。 |
| 西岸大剧院 | recommended_accept | supporting_stop | True/True | [31.163461, 121.465695] | art / — / — | 定向核验通过人工指定的全部条件，接受 staging 节点。 近期官方许可与官网文化服务支持稳定公共演艺目的地及有目的参观场景，接受supporting_stop；仅保留直接支持art，不新增建筑/拍照/地标标签。详细开放时间、当前可订场次及现场入场条件unknown。 |

穹顶采用 one_node_dual_mode：walk_stop 为北广场/外部停留；full_visit 为条件性场馆内部/演出访问。开放时间、当前演出、当前入内状态仍 unknown/null。所有新节点停留时长均为 product_planning_estimate，不是假设真实平均停留。
大剧院保留 art，experience/culture 不填 quota；有预约导览/观演目的访问场景，详细场次和入场条件须另行确认。摄影中心中英文记录仅计一个 stop。

## C. 已批准的新 transition stops

| 名称 | 决定 | 角色 | 可选/新增计数 | 坐标 (GCJ-02 lat,lng) | interest / experience / culture | 原因 |
| --- | --- | --- | --- | --- | --- | --- |
| 徐汇滨江海事塔广场 | recommended_accept | transition_stop | True/True | [31.177546, 121.4624] | waterfront / riverside_walk / — | 定向核验通过人工指定的全部条件，接受 staging 节点。 公众广场/塔旁滨江停留范围获官方支持；接受transition_stop。保留高德广场代表点，不声明允许进入或攀登塔体，不保证实时无临时管制。北外滩同名海事塔搜索结果排除。 |
| 北票码头塔吊 | recommended_accept | transition_stop | True/True | [31.1819, 121.464763] | industrial_heritage, waterfront / riverside_walk / — | 人工接受一个独立 staging 节点。 人工指定塔吊与其周边广场为同一停留体验，官方步行描述和检测研究佐证这一解释；不把塔吊广场当作独立stop。保留原高德塔吊代表点，塔吊体不上人，不新增art/photogenic。 |

## D. 条件接受 / 等待事实核验的节点

| 名称 | 决定 | 角色 | 可选/新增计数 | 坐标 (GCJ-02 lat,lng) | interest / experience / culture | 原因 |
| --- | --- | --- | --- | --- | --- | --- |
| 无尽影院 | defer | transition_stop | False/False | [31.1684143209162, 121.46436181031861] | art / photogenic / — | 条件核验未通过：current_existence, public_access, long_term_stability 定向查询未找到可靠当前存在及长期保留证据；旧报道与OSM记录不等于今日可达。defer，保留art/photogenic历史提议，绝不添加museum_visit。 |

未通过条件者已落实 defer、route_selectable=false；不会阻碍以其他已批准节点开展下一阶段。

## E. deferred nodes

| 名称 | 决定 | 角色 | 可选/新增计数 | 坐标 (GCJ-02 lat,lng) | interest / experience / culture | 原因 |
| --- | --- | --- | --- | --- | --- | --- |
| GATE M 西岸凤巢 | defer | supporting_stop | False/False | [31.163444, 121.460353] | shopping_lifestyle / shopping_leisure / — | 人工 defer；不计可选 stop，不表示永久 reject。 |
| 龙华码头 | defer | transition_stop | False/False | [31.157613, 121.465024] | waterfront / — / — | 人工 defer；不计可选 stop，不表示永久 reject。 |
| 星扬公园 | defer | transition_stop | False/False | [31.161384, 121.460549] | parks / — / — | 人工 defer；不计可选 stop，不表示永久 reject。 |
| 西岸运动公园 | defer | supporting_stop | False/False | [31.185046, 121.46665] | parks / — / — | 人工 defer；不计可选 stop，不表示永久 reject。 |
| 谷地花溪 | defer | transition_stop | False/False | None | waterfront / riverside_walk / — | 人工 defer；不计可选 stop，不表示永久 reject。 |
| 西岸中央公园 | defer | supporting_stop | False/False | None | parks / — / — | 人工 defer；不计可选 stop，不表示永久 reject。 |
| 西岸漩心 | defer | supporting_stop | False/False | [31.182954667202253, 121.46364698059003] | art / museum_visit / — | 人工 defer；不计可选 stop，不表示永久 reject。 |

## F. rejected nodes

| 名称 | 决定 | 角色 | 可选/新增计数 | 坐标 (GCJ-02 lat,lng) | interest / experience / culture | 原因 |
| --- | --- | --- | --- | --- | --- | --- |
| 光启龙华港湾 | reject | transition_stop | False/False | [31.176654, 121.46237] | — / — / — | 维持人工 reject：无证据支持独立 City Walk 体验；不以 transition_stop 作为保留空标签对象的兜底。 |
| 攀岩抱石区 | reject | transition_stop | False/False | [31.18186, 121.464527] | — / — / — | 维持人工 reject：无证据支持独立 City Walk 体验；不以 transition_stop 作为保留空标签对象的兜底。 |
| 乐动力西岸活力谷 | reject | transition_stop | False/False | [31.164802, 121.458362] | — / — / — | 维持人工 reject：无证据支持独立 City Walk 体验；不以 transition_stop 作为保留空标签对象的兜底。 pilot boundary or differing representative coordinates need verification |
| 玻璃宅 | reject | supporting_stop | False/False | [31.168905, 121.463904] | — / — / — | 维持人工 reject：无证据支持独立 City Walk 体验；不以 transition_stop 作为保留空标签对象的兜底。 |
| FISEHOOD极限运动公园 | reject | transition_stop | False/False | [31.158033, 121.464199] | — / — / — | 维持人工 reject：无证据支持独立 City Walk 体验；不以 transition_stop 作为保留空标签对象的兜底。 pilot boundary or differing representative coordinates need verification |
| 西岸国际会展中心(上海) | reject | supporting_stop | False/False | [31.162193, 121.463315] | — / — / — | 维持人工 reject：无证据支持独立 City Walk 体验；不以 transition_stop 作为保留空标签对象的兜底。 |
| 西岸中环梯田广场 | reject | transition_stop | False/False | [31.186625, 121.467075] | — / — / — | 维持人工 reject：无证据支持独立 City Walk 体验；不以 transition_stop 作为保留空标签对象的兜底。 |

## G. child / internal / duplicate source entities

| 名称 | parent | 决定 | 可选 | 新增计数 | 关系 / 原因 |
| --- | --- | --- | --- | --- | --- |
| 龙美术馆(西岸馆) | production:p5 | internal | false | false | source_representation_or_internal_entity；已存在的 production route node；同名油罐几何等仅保留为内部资料，不增加 stop 数。 |
| 龙美术馆(西岸馆) | production:p5 | internal | false | false | source_representation_or_internal_entity；已存在的 production route node；同名油罐几何等仅保留为内部资料，不增加 stop 数。 |
| 龙美术馆 | production:p5 | internal | false | false | source_representation_or_internal_entity；已存在的 production route node；同名油罐几何等仅保留为内部资料，不增加 stop 数。 |
| 西岸美术馆 | production:p28 | internal | false | false | source_representation_or_internal_entity；已存在的 production route node；同名油罐几何等仅保留为内部资料，不增加 stop 数。 |
| 西岸美术馆 | production:p28 | internal | false | false | source_representation_or_internal_entity；已存在的 production route node；同名油罐几何等仅保留为内部资料，不增加 stop 数。 |
| 西岸美术馆x蓬皮杜中心 | production:p28 | internal | false | false | source_representation_or_internal_entity；已存在的 production route node；同名油罐几何等仅保留为内部资料，不增加 stop 数。 |
| 上海油罐艺术中心 | production:p29 | internal | false | false | source_representation_or_internal_entity；已存在的 production route node；同名油罐几何等仅保留为内部资料，不增加 stop 数。 |
| 上海油罐艺术中心 | production:p29 | internal | false | false | source_representation_or_internal_entity；已存在的 production route node；同名油罐几何等仅保留为内部资料，不增加 stop 数。 |
| 油罐艺术中心 | production:p29 | internal | false | false | source_representation_or_internal_entity；已存在的 production route node；同名油罐几何等仅保留为内部资料，不增加 stop 数。 |
| 油罐艺术中心 | production:p29 | internal | false | false | source_representation_or_internal_entity；已存在的 production route node；同名油罐几何等仅保留为内部资料，不增加 stop 数。 |
| 油罐艺术中心 | production:p29 | internal | false | false | source_representation_or_internal_entity；已存在的 production route node；同名油罐几何等仅保留为内部资料，不增加 stop 数。 |
| 油罐艺术中心 | production:p29 | internal | false | false | source_representation_or_internal_entity；已存在的 production route node；同名油罐几何等仅保留为内部资料，不增加 stop 数。 |
| 油罐艺术中心 | production:p29 | internal | false | false | source_representation_or_internal_entity；已存在的 production route node；同名油罐几何等仅保留为内部资料，不增加 stop 数。 |
| 油罐艺术中心 | production:p29 | internal | false | false | source_representation_or_internal_entity；已存在的 production route node；同名油罐几何等仅保留为内部资料，不增加 stop 数。 |
| 油罐艺术中心 | production:p29 | internal | false | false | source_representation_or_internal_entity；已存在的 production route node；同名油罐几何等仅保留为内部资料，不增加 stop 数。 |
| 油罐艺术中心 | production:p29 | internal | false | false | source_representation_or_internal_entity；已存在的 production route node；同名油罐几何等仅保留为内部资料，不增加 stop 数。 |
| 油罐艺术中心 | production:p29 | internal | false | false | source_representation_or_internal_entity；已存在的 production route node；同名油罐几何等仅保留为内部资料，不增加 stop 数。 |
| Gate M西岸梦中心 | production:p30 | internal | false | false | source_representation_or_internal_entity；已存在的 production route node；同名油罐几何等仅保留为内部资料，不增加 stop 数。 |
| 星美术馆 | production:p31 | internal | false | false | source_representation_or_internal_entity；已存在的 production route node；同名油罐几何等仅保留为内部资料，不增加 stop 数。 |
| 星美术馆 | production:p31 | internal | false | false | source_representation_or_internal_entity；已存在的 production route node；同名油罐几何等仅保留为内部资料，不增加 stop 数。 |
| 西岸艺术中心B1馆 | route:art_center | internal | false | false | source_representation_or_internal_entity；用户指定整体优先为一个 stop；无独立入口、独立体验与有意义移动的联合证据。N馆距离较远也不能仅凭距离成为新 stop。 |
| 西岸艺术中心N馆 | route:art_center | internal | false | false | source_representation_or_internal_entity；用户指定整体优先为一个 stop；无独立入口、独立体验与有意义移动的联合证据。N馆距离较远也不能仅凭距离成为新 stop。 |
| 西岸艺术中心D馆 | route:art_center | internal | false | false | source_representation_or_internal_entity；用户指定整体优先为一个 stop；无独立入口、独立体验与有意义移动的联合证据。N馆距离较远也不能仅凭距离成为新 stop。 |
| 西岸艺术中心（含A馆） | route:art_center | internal | false | false | source_representation_or_internal_entity；用户指定整体优先为一个 stop；无独立入口、独立体验与有意义移动的联合证据。N馆距离较远也不能仅凭距离成为新 stop。 |
| 西岸艺术中心 | route:art_center | internal | false | false | previously_grouped_component；用户指定整体优先为一个 stop；无独立入口、独立体验与有意义移动的联合证据。N馆距离较远也不能仅凭距离成为新 stop。 |
| 西岸艺术中心A馆 | route:art_center | internal | false | false | previously_grouped_component；用户指定整体优先为一个 stop；无独立入口、独立体验与有意义移动的联合证据。N馆距离较远也不能仅凭距离成为新 stop。 |
| 西岸艺术中心A馆 | route:art_center | internal | false | false | previously_grouped_component；用户指定整体优先为一个 stop；无独立入口、独立体验与有意义移动的联合证据。N馆距离较远也不能仅凭距离成为新 stop。 |
| 西岸穹顶艺术中心（含北广场） | route:dome | internal | false | false | source_representation_or_internal_entity；Option 1：一个节点，不同 visit scope。广场在场馆北侧约84米；没有足够证据证明两次独立 City Walk 体验。 |
| 西岸穹顶艺术中心 | route:dome | internal | false | false | previously_grouped_component；Option 1：一个节点，不同 visit scope。广场在场馆北侧约84米；没有足够证据证明两次独立 City Walk 体验。 |
| 西岸穹顶北广场 | route:dome | internal | false | false | previously_grouped_component；Option 1：一个节点，不同 visit scope。广场在场馆北侧约84米；没有足够证据证明两次独立 City Walk 体验。 |
| 上海市滨江滑板公园 | route:skate | internal | false | false | source_representation_or_internal_entity；官方描述同名徐汇滨江户外滑板场；Amap/OSM 公园名与邻近位置相符。合并身份，但不同代表坐标保留供入口核实。 |
| 滨江滑板公园 | route:skate | internal | false | false | source_representation_or_internal_entity；官方描述同名徐汇滨江户外滑板场；Amap/OSM 公园名与邻近位置相符。合并身份，但不同代表坐标保留供入口核实。 |
| 上海市滨江滑板公园 | route:skate | internal | false | false | source_representation_or_internal_entity；官方描述同名徐汇滨江户外滑板场；Amap/OSM 公园名与邻近位置相符。合并身份，但不同代表坐标保留供入口核实。 |
| 跑道公园 | route:runway | internal | false | false | source_representation_or_internal_entity；官方机场跑道改造公园与 OSM 徐汇跑道公园的专名、区域及公园用途一致；官方记录无坐标，明确保留位置边界待核实。 |
| 徐汇跑道公园 | route:runway | internal | false | false | source_representation_or_internal_entity；官方机场跑道改造公园与 OSM 徐汇跑道公园的专名、区域及公园用途一致；官方记录无坐标，明确保留位置边界待核实。 |
| 上海摄影艺术中心 | route:photography | internal | false | false | source_representation_or_internal_entity；官方中文专名与 OSM 英文专名对应，均指向龙腾大道2555号；官方细分地址为2555号-1，合并为一个摄影场馆节点。 |
| Shanghai Center of Photography | route:photography | internal | false | false | source_representation_or_internal_entity；官方中文专名与 OSM 英文专名对应，均指向龙腾大道2555号；官方细分地址为2555号-1，合并为一个摄影场馆节点。 |
| 光启龙华港湾 | route:wb_fedf89c7dfde83a8 | internal | false | false | source_representation_or_internal_entity；保留为独立候选；是否可选由身份、证据、访问范围和边界决定。 |
| 徐汇滨江海事塔广场 | route:wb_72b583ec31ffce20 | internal | false | false | source_representation_or_internal_entity；保留为独立候选；是否可选由身份、证据、访问范围和边界决定。 |
| 优秀历史建筑龙腾大道2555号 | route:art_center | internal | false | false | human_confirmed_internal_entity；保留为独立候选；是否可选由身份、证据、访问范围和边界决定。 |
| 攀岩抱石区 | route:wb_8dc5274ef73e2eb1 | internal | false | false | source_representation_or_internal_entity；保留为独立候选；是否可选由身份、证据、访问范围和边界决定。 |
| GATE M 西岸凤巢 | route:wb_098e8fdb22e5f74b | internal | false | false | source_representation_or_internal_entity；保留为独立候选；是否可选由身份、证据、访问范围和边界决定。 |
| 北票码头塔吊 | route:wb_fd436a54b9d249a2 | internal | false | false | source_representation_or_internal_entity；保留为独立候选；是否可选由身份、证据、访问范围和边界决定。 |
| 乐动力西岸活力谷 | route:wb_d424a21f3c8820bd | internal | false | false | source_representation_or_internal_entity；保留为独立候选；是否可选由身份、证据、访问范围和边界决定。 |
| 龙华码头 | route:wb_11d08a44ff039d07 | internal | false | false | source_representation_or_internal_entity；保留为独立候选；是否可选由身份、证据、访问范围和边界决定。 |
| 岩时攀岩(Gate M西岸梦中心) | production:p30 | reject | false | false | internal_entity；人工维持 reject：内部普通运动商户，无独立 City Walk stop 价值。 |
| 开心麻花大三角剧场(Gate M西岸梦中心) | production:p30 | reject_as_independent_route_node | false | false | internal_entity；同地址园区内部演艺场所；缺少独立入口与作为新 City Walk stop 的证据。 |
| 西岸梦中心·梦工场 | production:p30 | reject_as_independent_route_node | false | false | internal_entity；2266号园区楼层实体，不独立增加 City Walk stops。 |
| 玻璃宅 | route:wb_e4c848a74b49e650 | internal | false | false | source_representation_or_internal_entity；保留为独立候选；是否可选由身份、证据、访问范围和边界决定。 |
| 西岸大剧院 | route:wb_7ca7f91efb488c29 | internal | false | false | source_representation_or_internal_entity；保留为独立候选；是否可选由身份、证据、访问范围和边界决定。 |
| 星扬公园 | route:wb_aa87d61112f0c493 | internal | false | false | source_representation_or_internal_entity；保留为独立候选；是否可选由身份、证据、访问范围和边界决定。 |
| FISEHOOD极限运动公园 | route:wb_0114b03136d07772 | internal | false | false | source_representation_or_internal_entity；保留为独立候选；是否可选由身份、证据、访问范围和边界决定。 |
| 西岸国际会展中心(上海) | route:wb_e46dff9d9d460e1c | internal | false | false | source_representation_or_internal_entity；保留为独立候选；是否可选由身份、证据、访问范围和边界决定。 |
| 西岸运动公园 | route:wb_c412dd6d5286929f | internal | false | false | source_representation_or_internal_entity；保留为独立候选；是否可选由身份、证据、访问范围和边界决定。 |
| 西岸中环梯田广场 | route:wb_17ae682bcceb4b2f | internal | false | false | source_representation_or_internal_entity；保留为独立候选；是否可选由身份、证据、访问范围和边界决定。 |
| 徐汇油罐艺术公园 | production:p29 | reject_as_independent_route_node | false | false | internal_entity；同园区户外体验已由 p29.walk_stop 明确覆盖；未证明独立站点。 |
| 塔吊广场 | route:wb_fd436a54b9d249a2 | internal | false | false | human_confirmed_internal_entity；保留为独立候选；是否可选由身份、证据、访问范围和边界决定。 |
| 谷地花溪 | route:wb_8a0a2e8f5c9d990d | internal | false | false | source_representation_or_internal_entity；保留为独立候选；是否可选由身份、证据、访问范围和边界决定。 |
| 西岸中央公园 | route:wb_cb6512c707e6874f | internal | false | false | source_representation_or_internal_entity；保留为独立候选；是否可选由身份、证据、访问范围和边界决定。 |
| 南浦站 | production:p31 | reject_as_independent_route_node | false | false | internal_entity；production 描述原铁路南浦站仓库；候选与星美术馆代表坐标相邻，缺少独立 stop 证据。 |
| 无尽影院 | route:wb_d7d1677306fa4d92 | internal | false | false | source_representation_or_internal_entity；保留为独立候选；是否可选由身份、证据、访问范围和边界决定。 |
| 瓦肆 VAS est | production:p30 | reject_as_independent_route_node | false | false | internal_entity；OSM 地址龙腾大道2266，当前仅演艺类别，未证明独立街行节点。 |
| 西岸漩心 | route:wb_3855808c00edb19b | internal | false | false | source_representation_or_internal_entity；保留为独立候选；是否可选由身份、证据、访问范围和边界决定。 |
| 优秀历史建筑龙腾大道2555号 | route:art_center | internal | false | false | human_confirmed_internal_entity；人工确认：仅保留在父节点，不增加独立 stop。 |
| 塔吊广场 | route:wb_fd436a54b9d249a2 | internal | false | false | human_confirmed_internal_entity；人工确认：仅保留在父节点，不增加独立 stop。 |

2555号建筑的历史/建筑证据已归入艺术中心 evidence_catalog，没有自动给父节点增加标签。塔吊广场仅为塔吊节点别名和周边空间证据；A/B1/N/D和穹顶北广场均不增加 stop count。岩时攀岩维持 reject、非可选（登记于G的内部实体）。

## 六项定向核验及代表点选择

网页检索/读取结果只保留定向事实摘要与时间、来源、获取方式。搜索索引摘要不冒充成功直接读取；历史报道不冒充今日存在。所有坐标来自真实 provider 记录，没有平均或 LLM 生成坐标。代表点是近似访问锚点，不声称测绘了精确入口。

### 滨江滑板公园

官方公众台阶观察区域已确认。采用高德瑞宁路同名公园访问代表点，保留OSM几何点差异约180米；无独立入口证明，不拆节点。精确台阶入口坐标未测绘，不声称该点就是门口。

| 核验 | 结果 | 证据 |
| --- | --- | --- |
| public_access | confirmed | [fv_skate_public](https://whlyj.sh.gov.cn/gqfc/20260904/89b6a38c04274b0fbfe300752f21c3e6.html) |
| same_experience | confirmed | [fv_skate_public](https://whlyj.sh.gov.cn/gqfc/20260904/89b6a38c04274b0fbfe300752f21c3e6.html), [fv_skate_coordinate](https://ditu.amap.com/place/B0FFG8TX4N) |
| representative_coordinate | confirmed | [fv_skate_coordinate](https://ditu.amap.com/place/B0FFG8TX4N) |

代表点：`[31.185976, 121.467781]` GCJ-02；confidence=medium；高德访问POI有瑞宁路地址，且被官方同名公众休憩场景佐证；优先于OSM几何代表点，不求平均。
- [来源](https://whlyj.sh.gov.cn/gqfc/20260904/89b6a38c04274b0fbfe300752f21c3e6.html)：2026年9月市文旅局描述滨江滑板公园、相邻绿地和滨江步道，明确游客可在旁边台阶休憩；支持公众观察空间及同一滑板体验。 获取方式：web_open；检索时间：2026-10-04T09:56:22+00:00；发布时间：2026-09-04。
- [来源](https://ditu.amap.com/place/B0FFG8TX4N)：高德同名瑞宁路公园点：GCJ-02纬度31.185976，经度121.467781。 获取方式：web_search_index；检索时间：2026-10-04T09:56:22+00:00；发布时间：unknown。

### 徐汇跑道公园

线性公园以高德丰谷路南段访问点作为代表，不用OSM线性几何中心冒充入口。代表点在原多边形西侧约26米、原150米审核缓冲内；落实人工接受边界审核点，原polygon和margin均不改。

| 核验 | 结果 | 证据 |
| --- | --- | --- |
| representative_coordinate | confirmed | [fv_runway_coordinate](https://www.amap.com/place/B0FFI8D8QU) |
| pilot_relation | confirmed | [fv_runway_coordinate](https://www.amap.com/place/B0FFI8D8QU) |

代表点：`[31.168592, 121.45773]` GCJ-02；confidence=medium；官方云锦路/丰谷路到访说明与高德访问POI一致；替换几何代表点，未为落入polygon而移动点。
- [来源](https://www.westbund.com/cn/index/KEY-PROJECTS/detail_6deD0.html)：西岸官方将跑道公园定位云锦路，说明原跑道转为多样线性街道、公园系统，并提供云锦路站/丰谷路公交到访说明。 获取方式：web_open；检索时间：2026-10-04T09:56:22+00:00；发布时间：unknown。
- [来源](https://www.amap.com/place/B0FFI8D8QU)：高德徐汇跑道公园B0FFI8D8QU定位云锦路与丰谷路交口南约200米，GCJ-02纬度31.168592，经度121.457730。 获取方式：web_open；检索时间：2026-10-04T09:56:22+00:00；发布时间：unknown。

### 徐汇滨江海事塔广场

公众广场/塔旁滨江停留范围获官方支持；接受transition_stop。保留高德广场代表点，不声明允许进入或攀登塔体，不保证实时无临时管制。北外滩同名海事塔搜索结果排除。

| 核验 | 结果 | 证据 |
| --- | --- | --- |
| public_access | confirmed | [fv_maritime_public](https://www.shanghai.gov.cn/nw17239/20260414/8562052ebffb4b4ebdd83c5eeceac4bc.html), [fv_maritime_tour](https://whlyj.sh.gov.cn/gqfc/20230523/3ee401f0a53846a990944f6275227162.html) |
| representative_coordinate | confirmed | [fv_maritime_coordinate](https://www.amap.com/detail/B0FFGXZYD4) |

代表点：`[31.177546, 121.4624]` GCJ-02；confidence=medium；已有高德广场点关联徐汇官方塔旁公共观赏范围；未发明内部塔体入口。
- [来源](https://www.shanghai.gov.cn/nw17239/20260414/8562052ebffb4b4ebdd83c5eeceac4bc.html)：徐汇区政府2026花卉节官方说明把瑞宁路至龙耀路滨江段界定为公共开放空间，海事塔周边/基座明确为公众观赏区域；证实广场外部访问，非塔体内部开放。 获取方式：web_open；检索时间：2026-10-04T09:56:22+00:00；发布时间：2026-04-14。
- [来源](https://whlyj.sh.gov.cn/gqfc/20230523/3ee401f0a53846a990944f6275227162.html)：市文旅局发布的徐汇滨江建筑城市漫步明确途经徐汇滨江海事塔。 获取方式：web_search_index；检索时间：2026-10-04T09:56:22+00:00；发布时间：2023-05-23。
- [来源](https://www.amap.com/detail/B0FFGXZYD4)：复用Phase 2.5A实际高德记录B0FFGXZYD4：海事塔广场GCJ-02代表点31.177546,121.4624。 获取方式：phase_2_5a_cached_record；检索时间：2026-10-04T07:38:50.249841+00:00；发布时间：unknown。

### 北票码头塔吊

人工指定塔吊与其周边广场为同一停留体验，官方步行描述和检测研究佐证这一解释；不把塔吊广场当作独立stop。保留原高德塔吊代表点，塔吊体不上人，不新增art/photogenic。

| 核验 | 结果 | 证据 |
| --- | --- | --- |
| one_node_identity | confirmed | [fv_crane_identity](https://www.westbund.com/cn/index/NEWS-CENTER/West-Bund-12.html), [fv_crane_walk](https://whlyj.sh.gov.cn/gqfc/20260904/89b6a38c04274b0fbfe300752f21c3e6.html), [fv_crane_observation](https://jpm.front-sci.com/index.php/jpm/article/download/7746/7492) |
- [来源](https://www.westbund.com/cn/index/NEWS-CENTER/West-Bund-12.html)：西岸官方记述北票码头工业遗存及保留塔吊，支持主要identity与工业遗存性质。 获取方式：web_search_index；检索时间：2026-10-04T09:56:22+00:00；发布时间：unknown。
- [来源](https://whlyj.sh.gov.cn/gqfc/20260904/89b6a38c04274b0fbfe300752f21c3e6.html)：官方游客步行说明：从相邻绿地沿滨江到龙美术馆途经塔吊广场；为塔吊周边步行公共空间证据。 获取方式：web_open；检索时间：2026-10-04T09:56:22+00:00；发布时间：2026-09-04。
- [来源](https://jpm.front-sci.com/index.php/jpm/article/download/7746/7492)：2025塔吊检测研究指北票码头塔吊在东安路与龙腾大道交口东侧，现作工业遗存景观供观赏，不再起重、不上人。 获取方式：web_search_index；检索时间：2026-10-04T09:56:22+00:00；发布时间：2025。

### 无尽影院

定向查询未找到可靠当前存在及长期保留证据；旧报道与OSM记录不等于今日可达。defer，保留art/photogenic历史提议，绝不添加museum_visit。

| 核验 | 结果 | 证据 |
| --- | --- | --- |
| current_existence | unknown | 无可靠当前证据 |
| public_access | unknown | 无可靠当前证据 |
| long_term_stability | unknown | 无可靠当前证据 |
- [来源](https://www.jfdaily.com/sgh/detail?id=1175176)：徐汇官方账号2023年11月报道：郭熙公共艺术装置在西岸美术馆北广场东侧供公众驻足观看。只有历史存在与历史公共可见证据，没有当前保留/长期稳定承诺。 获取方式：web_search_index; web_open shell did not expose article body；检索时间：2026-10-04T09:56:22+00:00；发布时间：2023-11-11。

### 西岸大剧院

近期官方许可与官网文化服务支持稳定公共演艺目的地及有目的参观场景，接受supporting_stop；仅保留直接支持art，不新增建筑/拍照/地标标签。详细开放时间、当前可订场次及现场入场条件unknown。

| 核验 | 结果 | 证据 |
| --- | --- | --- |
| current_existence | confirmed | [fv_theatre_license](https://www.xuhui.gov.cn/xxgk/portal/article/detail?id=8a4c0c069a97abda019f938a19e230a9), [fv_theatre_services](https://www.shwbtheatre.com/wbtheatrepc/index.html) |
| stable_public_venue | confirmed | [fv_theatre_license](https://www.xuhui.gov.cn/xxgk/portal/article/detail?id=8a4c0c069a97abda019f938a19e230a9), [fv_theatre_services](https://www.shwbtheatre.com/wbtheatrepc/index.html) |
| purposeful_visit | confirmed | [fv_theatre_services](https://www.shwbtheatre.com/wbtheatrepc/index.html) |
| arrival_scenario | confirmed | [fv_theatre_services](https://www.shwbtheatre.com/wbtheatrepc/index.html) |
| independent_citywalk_value | confirmed | [fv_theatre_services](https://www.shwbtheatre.com/wbtheatrepc/index.html), [fv_theatre_license](https://www.xuhui.gov.cn/xxgk/portal/article/detail?id=8a4c0c069a97abda019f938a19e230a9) |
- [来源](https://www.shwbtheatre.com/wbtheatrepc/index.html)：官方官网索引包含近期2026年9月资讯、演出购票、参观导览预约、如何到达及龙腾大道2290号地址；明确文化到访场景。直接open返回浏览器兼容提示，内容取官方页面搜索索引，不声称完成现场验门。 获取方式：web_search_index; web_open compatibility fallback；检索时间：2026-10-04T09:56:22+00:00；发布时间：2026-09。
- [来源](https://www.xuhui.gov.cn/xxgk/portal/article/detail?id=8a4c0c069a97abda019f938a19e230a9)：徐汇文旅局2026许可申请人为上海西岸大剧院管理有限公司、演出地点西岸大剧院大剧场，许可近期音乐剧演出，佐证当前场馆运营与文化用途。 获取方式：web_open；检索时间：2026-10-04T09:56:22+00:00；发布时间：2026-07-24。

## 边界与下一阶段诊断

边界多边形及原150米审核缓冲未修改。跑道公园代表点（31.168592,121.457730）处于多边形西侧约26米的既有审核带，按本轮明确人工接受决定纳入staging；不将其标为inside_pilot。线性公园完整边界不是此代表点，不把跨区范围全部纳入试点。
zone_expansion_diagnostic 仅定义未来统计输入：theme_failure_count、insufficient_route_count、composition_failure_count、各请求candidate pool sizes、non-museum/parks-public-space success、geographic gap indicators。当前status=not_run、zone_expansion_recommended=null。只有失败归因主要为高质量节点不足或地理缺口才为true；parser/tag mismatch/算法/scoring原因不会被当作扩zone理由。

## 测试与保护检查

{'command': 'python -m unittest discover -s tests -t . -q', 'status': 'passed', 'tests_run': 300, 'new_mock_tests': 15, 'elapsed_seconds': 9.463, 'exit_code': 0, 'real_deepseek_calls': 0, 'real_network_calls_in_new_unit_tests': 0}

受保护文件 SHA256 全部保持一致：True（354 个）。production pois.json 仍为 `6585b3baf653ae89cc6a1e3c5fc10140bdd801fb298d92c392381d0b5fc17513`。
本轮0 DeepSeek调用，0全量采集，0路线回归。定向网页核验已完成并记录六项结果；离线重放不再消耗外部API。

## 文件与复现

- src/poi_pipeline/semantic/final_review.py：人工准入、父子归并、校验与未来诊断。
- scripts/finalize_west_bund_review.py：离线生成三份最终产物。
- tests/test_poi_final_review.py：mock source与条件核验测试；无真实DeepSeek/网络。
- data/poi_pipeline/semantic/final/：final review、selectable staging、targeted verification、protected baseline和test_result。
- PHASE2_5B_FINAL_HUMAN_REVIEW_REPORT.md：本报告。

复现：`python scripts/finalize_west_bund_review.py`；测试：`python -m unittest discover -s tests -t . -q`。

STOP：等待 Phase 2.5C 的独立授权，本轮不自动开始。
