# PHASE 2.5B REPAIR REPORT

本次为离线、定向、可复现的候选层修复；未开始 Phase 2.5C，未重新 collection，未整批 enrichment。

## 1. Before repair

Phase 2.5A canonical 61；用户分组后 58；校验结果 55、失败 3；Recommended Accept 0 / Needs Review 43 / Reject 15。

## 2. Production identity matches

| Production | Name | Source candidate records | Primary role |
| --- | --- | ---: | --- |
| p5 | 龙美术馆（西岸馆） | 3 | anchor |
| p28 | 西岸美术馆 | 3 | anchor |
| p29 | 上海油罐艺术中心 | 12 | anchor |
| p30 | Gate M 西岸梦中心 | 5 | anchor |
| p31 | 星美术馆 | 3 | anchor |

匹配综合精确中英文/别名、坐标距离、门牌、已知官方页面及 source identity。仅名字相似或同品牌不作为新节点：possible_duplicate。生产内容与访问时长作为已知结构化证据保留，不被旧 candidate 的信息空缺覆盖。

## 3. Duplicates merged

- **西岸艺术中心**：4 条当前 candidate 归入一个节点。用户指定整体优先为一个 stop；无独立入口、独立体验与有意义移动的联合证据。N馆距离较远也不能仅凭距离成为新 stop。
- **西岸穹顶艺术中心（含北广场）**：1 条当前 candidate 归入一个节点。Option 1：一个节点，不同 visit scope。广场在场馆北侧约84米；没有足够证据证明两次独立 City Walk 体验。
- **滨江滑板公园**：3 条当前 candidate 归入一个节点。官方描述同名徐汇滨江户外滑板场；Amap/OSM 公园名与邻近位置相符。合并身份，但不同代表坐标保留供入口核实。
- **徐汇跑道公园**：2 条当前 candidate 归入一个节点。官方机场跑道改造公园与 OSM 徐汇跑道公园的专名、区域及公园用途一致；官方记录无坐标，明确保留位置边界待核实。
- **上海摄影艺术中心**：2 条当前 candidate 归入一个节点。官方中文专名与 OSM 英文专名对应，均指向龙腾大道2555号；官方细分地址为2555号-1，合并为一个摄影场馆节点。

## 4. Parent/child entities removed from route selection

A/B1/N/D 馆、TANK 油罐几何、油罐公园既有 walk_stop 范围、南浦站场地和 Gate M 内部实体保留来源资料，child.route_selectable=false。没有按 provider ID 生成 stops。

源实体登记表单独保存，不进入主审核表。疑似内部建筑与疑似重叠公园没有强行确认身份，仍在主表中标为 possible_duplicate。

## 5. Final route-node candidate count

主审核表 **30** 行：已有 production 审核 **5**、新增路线节点候选 **19**、possible_duplicate **4**、unresolved **2**。
结构上可作为新增 stop 的提议 **12**；这只是 staging 标记，尚未进入 Route Engine。非可选记录与内部实体不增加 stop count。

## 6. Existing production POIs needing only route-role audit

p5 / p28 / p29 / p30 / p31 各保留一次，admission_scope=production_audit_only、counts_as_new_stop=false。角色提议基于既有内容、full_visit 产品估时与 walk_stop 范围，非地图类别或知名度。五处均提议 anchor，同时可用 supporting_stop 访问方式；不新增 transition 节点。

TANK 的 outdoor walk_stop 有 production 明确支持：外部油罐、工业遗产和滨江公共空间；这不等于证实独立户外艺术作品。原来失败的两条油罐对象归入内部实体，已无单独 enrichment 义务；龙美术馆失败行归回 p5 审核，已知 production 内容完整保留。

## 7. Recommended Accept / Needs Review / Reject

全表：**{'needs_review': 21, 'recommended_accept': 2, 'reject': 7}**；排除既有 production 审核后的候选决定：**{'recommended_accept': 2, 'needs_review': 16, 'reject': 7}**。
recommended_accept 仅是建议人工接受此候选层表达，仍非 promotion。route_selectable 表示独立节点资格，不表示已导入或已批准进入路线。

| Name | Identity / production | Selectable | Category | Role / confidence | Decision |
| --- | --- | --- | --- | --- | --- |
| 龙美术馆（西岸馆） | existing_production / p5 | True | Industrial Heritage | anchor / medium | needs_review |
| 西岸美术馆 | existing_production / p28 | True | Contemporary Art | anchor / medium | needs_review |
| 上海油罐艺术中心 | existing_production / p29 | True | Industrial Heritage / Contemporary Art | anchor / medium | needs_review |
| Gate M 西岸梦中心 | existing_production / p30 | True | Industrial Renewal / Waterfront Lifestyle | anchor / medium | needs_review |
| 星美术馆 | existing_production / p31 | True | Industrial Heritage / Contemporary Art | anchor / medium | needs_review |
| 西岸艺术中心 | new_candidate / — | True | cultural_venue | supporting_stop / medium | recommended_accept |
| 西岸穹顶艺术中心（含北广场） | new_candidate / — | True | performance_venue | supporting_stop / medium | needs_review |
| 滨江滑板公园 | new_candidate / — | True | park | supporting_stop / medium | needs_review |
| 徐汇跑道公园 | new_candidate / — | True | park | supporting_stop / medium | needs_review |
| 上海摄影艺术中心 | new_candidate / — | True | cultural_venue | supporting_stop / medium | recommended_accept |
| 光启龙华港湾 | new_candidate / — | False | public_space | transition_stop / low | reject |
| 徐汇滨江海事塔广场 | new_candidate / — | True | public_space | transition_stop / medium | needs_review |
| 优秀历史建筑龙腾大道2555号 | possible_duplicate / — | False | heritage | transition_stop / medium | needs_review |
| 攀岩抱石区 | new_candidate / — | False | sports_space | transition_stop / low | reject |
| GATE M 西岸凤巢 | possible_duplicate / p30 | False | commercial_complex | supporting_stop / medium | needs_review |
| 北票码头塔吊 | new_candidate / — | True | heritage | transition_stop / medium | needs_review |
| 乐动力西岸活力谷 | new_candidate / — | False | sports_space | transition_stop / low | reject |
| 龙华码头 | new_candidate / — | True | public_space | transition_stop / low | needs_review |
| 玻璃宅 | new_candidate / — | False | public_art | supporting_stop / low | reject |
| 西岸大剧院 | new_candidate / — | True | performance_venue | supporting_stop / low | needs_review |
| 星扬公园 | new_candidate / — | True | park | transition_stop / medium | needs_review |
| FISEHOOD极限运动公园 | new_candidate / — | False | sports_space | transition_stop / low | reject |
| 西岸国际会展中心(上海) | new_candidate / — | False | cultural_venue | supporting_stop / low | reject |
| 西岸运动公园 | possible_duplicate / — | False | park | supporting_stop / medium | needs_review |
| 西岸中环梯田广场 | new_candidate / — | False | public_space | transition_stop / low | reject |
| 塔吊广场 | possible_duplicate / — | False | public_space | transition_stop / medium | needs_review |
| 谷地花溪 | unresolved / — | False | public_space | transition_stop / medium | needs_review |
| 西岸中央公园 | unresolved / — | False | park | supporting_stop / low | needs_review |
| 无尽影院 | new_candidate / — | True | public_art | transition_stop / medium | needs_review |
| 西岸漩心 | new_candidate / — | True | museum | supporting_stop / low | needs_review |

## 8. Tags changed after repair

| Node | Removed from previous effective tags | Added / restored from evidence | Supported tags now |
| --- | --- | --- | --- |
| 龙美术馆（西岸馆） | — | architecture, industrial_heritage, waterfront, adaptive_reuse, photogenic, riverside_walk, industrial_transformation, modern_shanghai, urban_renewal | art,industrial_heritage,waterfront,architecture; museum_visit,adaptive_reuse,riverside_walk,photogenic; industrial_transformation,urban_renewal,modern_shanghai |
| 西岸美术馆 | architecture_detail, sino_foreign_exchange | industrial_transformation, modern_shanghai, urban_renewal | art,waterfront,architecture; museum_visit,riverside_walk,photogenic; urban_renewal,industrial_transformation,modern_shanghai |
| 上海油罐艺术中心 | parks, architecture_detail | waterfront, riverside_walk, modern_shanghai | art,industrial_heritage,architecture,waterfront; museum_visit,adaptive_reuse,photogenic,riverside_walk; industrial_transformation,urban_renewal,modern_shanghai |
| Gate M 西岸梦中心 | art | industrial_heritage, waterfront, adaptive_reuse, photogenic, riverside_walk, industrial_transformation, modern_shanghai, urban_renewal | industrial_heritage,waterfront,shopping_lifestyle,modern_city; adaptive_reuse,riverside_walk,shopping_leisure,photogenic; industrial_transformation,urban_renewal,modern_shanghai |
| 星美术馆 | history, waterfront, riverside_walk | architecture, industrial_heritage, adaptive_reuse, architecture_detail, industrial_transformation, modern_shanghai, urban_renewal | art,industrial_heritage,architecture; museum_visit,adaptive_reuse,architecture_detail; industrial_transformation,urban_renewal,modern_shanghai |
| 西岸艺术中心 | museum_visit, photogenic, modern_shanghai | — | art,industrial_heritage,architecture; adaptive_reuse,architecture_detail; industrial_transformation |
| 西岸穹顶艺术中心（含北广场） | architecture, architecture_detail | — | art; —; — |
| 滨江滑板公园 | photogenic | — | parks,waterfront; riverside_walk,social_observation; public_life |
| 徐汇跑道公园 | modern_city, waterfront, riverside_walk, modern_shanghai | — | parks,history; adaptive_reuse,street_scene; urban_renewal |
| 上海摄影艺术中心 | architecture_detail, photogenic | — | art,architecture; museum_visit; — |
| 光启龙华港湾 | — | — | —; —; — |
| 徐汇滨江海事塔广场 | — | — | waterfront; riverside_walk; — |
| 优秀历史建筑龙腾大道2555号 | architecture_detail | — | history,architecture; —; — |
| 攀岩抱石区 | — | — | —; —; — |
| GATE M 西岸凤巢 | — | — | shopping_lifestyle; shopping_leisure; — |
| 北票码头塔吊 | — | — | industrial_heritage,waterfront; riverside_walk; — |
| 乐动力西岸活力谷 | — | — | —; —; — |
| 龙华码头 | — | — | waterfront; —; — |
| 玻璃宅 | — | — | —; —; — |
| 西岸大剧院 | architecture_detail | — | art; —; — |
| 星扬公园 | — | — | parks; —; — |
| FISEHOOD极限运动公园 | — | — | —; —; — |
| 西岸国际会展中心(上海) | — | — | —; —; — |
| 西岸运动公园 | — | — | parks; —; — |
| 西岸中环梯田广场 | — | — | —; —; — |
| 塔吊广场 | art, photogenic | — | waterfront; riverside_walk; — |
| 谷地花溪 | parks | — | waterfront; riverside_walk; — |
| 西岸中央公园 | — | — | parks; —; — |
| 无尽影院 | — | — | art; photogenic; — |
| 西岸漩心 | architecture | — | art; museum_visit; — |

- 滑板公园：parks 来自公园分类；滨江身份支持 waterfront/riverside_walk；市文旅局明确描述“本地滑板社群的重要聚集地”，支持 social_observation/public_life。移除仅由泛景观词支撑的 photogenic。
- 跑道公园：官方原文支持航空历史、原跑道转用、街道和公园系统，所以保留 history/adaptive_reuse/street_scene。内部水系不等于黄浦江步道，移除 waterfront/riverside_walk；“现代社会”不是 modern_city 的可靠依据。
- 塔吊广场和北票码头塔吊：不以工业设备或同段文字中的美术馆推导 art。无尽影院由 OSM tourism=artwork、installation 支持公共艺术线索，但公共可达与稳定性未确认。
- 未新增 taxonomy，未用覆盖率修正任何标签。生产既有标签仅恢复/保留为 production 事实快照，不声称本次重新外部验证了全部标签。

## 9. Route roles changed after repair

| Node | Before roles | Proposed role | Evidence-based reason |
| --- | --- | --- | --- |
| 龙美术馆（西岸馆） | anchor, supporting_stop | anchor | 既有 production 内容：从工业生产岸线到公共文化空间，城市功能变化被直接写进了江岸。 结合已校准 full_visit standard 75 分钟（产品估计）及双访问范围，具有主题承载和独立停留理由。不是从知名度或地图类别推断。 |
| 西岸美术馆 | anchor | anchor | 既有 production 内容：西岸核心文化设施之一，适合把当代艺术体验与滨江步行结合。 结合已校准 full_visit standard 75 分钟（产品估计）及双访问范围，具有主题承载和独立停留理由。不是从知名度或地图类别推断。 |
| 上海油罐艺术中心 | anchor, supporting_stop | anchor | 既有 production 内容：由原航空储油罐改造而来的当代艺术空间，是西岸工业遗产再利用最直观的案例之一。 结合已校准 full_visit standard 75 分钟（产品估计）及双访问范围，具有主题承载和独立停留理由。不是从知名度或地图类别推断。 |
| Gate M 西岸梦中心 | supporting_stop, transition_stop | anchor | 既有 production 内容：由百年水泥厂旧址更新而来的滨水商业文化目的地，保留工业建筑元素并引入餐饮、演艺和公共空间。 结合已校准 full_visit standard 60 分钟（产品估计）及双访问范围，具有主题承载和独立停留理由。不是从知名度或地图类别推断。 |
| 星美术馆 | anchor, supporting_stop, transition_stop | anchor | 既有 production 内容：由原铁路南浦站十八线仓库改造的当代艺术馆，保留铁路工业场地记忆。 结合已校准 full_visit standard 60 分钟（产品估计）及双访问范围，具有主题承载和独立停留理由。不是从知名度或地图类别推断。 |
| 西岸艺术中心 | anchor, supporting_stop | supporting_stop | 官方说明保留飞机制造厂冲压车间的建筑与工业空间，并承载文化活动。可独立观察再利用空间，作为滨江主题的补充站；展览内容和可进入范围未核实，暂不将其当作主目的地。 |
| 西岸穹顶艺术中心（含北广场） | supporting_stop | supporting_stop | 一个节点保留两种访问范围：广场外部短停与场馆访问。广场与场馆相邻但非同一体验；尚无证据支持将其拆成两个独立 stops，演出和进入条件待核实。 |
| 滨江滑板公园 | supporting_stop | supporting_stop | 官方描述专业户外场地及本地滑板社群聚集，可有目的地观察公共活动；不是仅因位于滨江赋予社会观察标签。多源坐标为不同代表点，入口和观察边界仍需核对。 |
| 徐汇跑道公园 | supporting_stop | supporting_stop | 官方说明机场跑道转为街道、公园及多种交通休闲空间；可作为独立的线性空间观察站。水系不等于黄浦江滨水路线，因此移除 waterfront/riverside_walk；试点边界仍待核实。 |
| 上海摄影艺术中心 | supporting_stop | supporting_stop | 官方说明摄影场馆的独立内容和空间，中文与英文记录均指向龙腾大道同一门牌。适合有目的的摄影艺术补充访问；当前展览、开门及入口需另核实，不因相邻艺术中心就计作其分馆。 |
| 光启龙华港湾 | transition_stop | transition_stop | 仅有地图名称、地址与“风景名胜;旅游景点”分类，缺少可核验的体验内容；位于龙腾大道辅路与龙恒东路交叉口附近，可作为滨江步行路径上的短时停顿点。 |
| 徐汇滨江海事塔广场 | transition_stop | transition_stop | 地图确认滨江城市广场身份，空间位置可补充两处较强节点之间的短停；没有独立展览或复杂历史内容证据，故不提议 anchor。可达范围待核实。 |
| 优秀历史建筑龙腾大道2555号 | transition_stop | transition_stop | 地图名称提供历史建筑线索，但没有独立历史认定文件或建筑细节；与艺术中心场地及地址接近，先作为可能内部建筑核实，不独立增加 stop。 |
| 攀岩抱石区 | transition_stop | transition_stop | 仅有名称与地址证据，显示为攀岩抱石活动点，位于龙腾大道与东安路交叉口附近，紧邻北票码头塔吊（约23米），可作为滨江步行途中的短暂停留点，但缺乏独立目的地价值的证据。 |
| GATE M 西岸凤巢 | supporting_stop | supporting_stop | 地图分类为普通商场，具备独立休闲商业体验，可作为滨江艺术区步行中的补充节点；但缺乏地标性或文化叙事证据，不足以成为锚点。 |
| 北票码头塔吊 | supporting_stop | transition_stop | 塔吊及公共滨江地址支持工业构筑物的短时观察；设备不是因为视觉上有艺术感就成为 art。与塔吊广场的身份/范围关系未确证，不同时计作两站。 |
| 乐动力西岸活力谷 | transition_stop | transition_stop | 仅有地图类别“体育休闲服务场所”与交叉口地址，缺乏可体验内容、开放状态与规模信息，独立目的地价值不明；作为西岸滨江动线上的短时停留点更合理。 |
| 龙华码头 | transition_stop | transition_stop | 地图港口码头身份支持滨水线索，但没有公共游览及可达证据。仅为条件性的短停提议，不能把港口设施直接视为独立目的地。 |
| 玻璃宅 | supporting_stop | supporting_stop | 名称与地址显示其为西岸美术馆旁的独立小型构筑物，具备短暂视觉观察价值，但证据极薄，难以支撑独立目的地价值。 |
| 西岸大剧院 | supporting_stop | supporting_stop | 演艺用途有地图与OSM支持，可提出独立演艺访问的补充节点；但节目、入口及实际访问内容未核实。没有建筑细节证据，删除 architecture_detail；不凭剧院类别提升为 anchor。 |
| 星扬公园 | transition_stop | transition_stop | 地图确认公园，可提议短时绿地停留；无安静、社会活动或历史证据，不补 quiet_walk/public_life。开放边界和独立步行价值待核实。 |
| FISEHOOD极限运动公园 | transition_stop | transition_stop | 仅有名称与地图分类（体育休闲服务场所）可证，属极限运动公园类场地；无开放时间、活动内容或体验描述，独立目的地价值不明，更适合作为西岸滨江步行链上的短时过渡节点。 |
| 西岸国际会展中心(上海) | supporting_stop | supporting_stop | 地图类别为会展中心，属科教文化服务类场馆，具备一定独立到访价值，但缺少展览内容、开放状态等细节，难以支撑锚点级别。 |
| 西岸运动公园 | supporting_stop | supporting_stop | 地图公园类别支持 parks，但与滑板公园相邻，暂无独立功能范围的证据。两者是否同一运动空间待确认，不用重复公园条目增加 stops。 |
| 西岸中环梯田广场 | transition_stop | transition_stop | 仅有名称与地址等身份信息，无描述性内容；作为西岸滨江带内一处具名的梯田式广场，可作短时停留的过渡节点，但缺乏独立体验价值的证据。 |
| 塔吊广场 | transition_stop | transition_stop | 官方只支持滨江步道沿线的标志性景观，未描述独立公共艺术；移除 art/photogenic。可能是北票码头塔吊周边空间，缺坐标且关系未确证，暂不独立选点。 |
| 谷地花溪 | supporting_stop | transition_stop | 官方描述滨江绿地、铁轨遗迹及与滑板公园相邻，适合短时景观/遗迹观察。绿地描述不能直接证明 parks；缺少坐标，因此不能参与路线选点。 |
| 西岸中央公园 | transition_stop | supporting_stop | 仅有官方名称提及，公园身份可作为核查线索，缺位置、规模和活动内容；角色仅为低置信提议，暂不能参加路线选点。 |
| 无尽影院 | supporting_stop | transition_stop | OSM 明确记录具名 installation artwork，可支持短时作品观察；不是仅凭工业设备名称判断为艺术。公共可达性和长期保留情况未核实，不能据此假设 museum_visit。 |
| 西岸漩心 | supporting_stop | supporting_stop | OSM提供具名文化场所线索，位置与既有强节点相邻；仅能提出文化访问补充站，缺少独立内容描述，不能确定 anchor。building=yes 不是建筑体验证据，删除 architecture。 |

## 10. Key ambiguous POIs still needing human decision

- **西岸穹顶艺术中心（含北广场）**：一个节点保留两种访问范围：广场外部短停与场馆访问。广场与场馆相邻但非同一体验；尚无证据支持将其拆成两个独立 stops，演出和进入条件待核实。
- **滨江滑板公园**：官方描述专业户外场地及本地滑板社群聚集，可有目的地观察公共活动；不是仅因位于滨江赋予社会观察标签。多源坐标为不同代表点，入口和观察边界仍需核对。 pilot boundary or differing representative coordinates need verification
- **徐汇跑道公园**：官方说明机场跑道转为街道、公园及多种交通休闲空间；可作为独立的线性空间观察站。水系不等于黄浦江滨水路线，因此移除 waterfront/riverside_walk；试点边界仍待核实。 pilot boundary or differing representative coordinates need verification
- **徐汇滨江海事塔广场**：地图确认滨江城市广场身份，空间位置可补充两处较强节点之间的短停；没有独立展览或复杂历史内容证据，故不提议 anchor。可达范围待核实。
- **优秀历史建筑龙腾大道2555号**：地图名称提供历史建筑线索，但没有独立历史认定文件或建筑细节；与艺术中心场地及地址接近，先作为可能内部建筑核实，不独立增加 stop。
- **GATE M 西岸凤巢**：既有校验结果复用；未新增模型调用。仍需确认独立访问范围。 identity or production relationship unresolved; cannot become a new stop
- **北票码头塔吊**：塔吊及公共滨江地址支持工业构筑物的短时观察；设备不是因为视觉上有艺术感就成为 art。与塔吊广场的身份/范围关系未确证，不同时计作两站。
- **龙华码头**：地图港口码头身份支持滨水线索，但没有公共游览及可达证据。仅为条件性的短停提议，不能把港口设施直接视为独立目的地。 pilot boundary or differing representative coordinates need verification
- **西岸大剧院**：演艺用途有地图与OSM支持，可提出独立演艺访问的补充节点；但节目、入口及实际访问内容未核实。没有建筑细节证据，删除 architecture_detail；不凭剧院类别提升为 anchor。 pilot boundary or differing representative coordinates need verification
- **星扬公园**：地图确认公园，可提议短时绿地停留；无安静、社会活动或历史证据，不补 quiet_walk/public_life。开放边界和独立步行价值待核实。
- **西岸运动公园**：地图公园类别支持 parks，但与滑板公园相邻，暂无独立功能范围的证据。两者是否同一运动空间待确认，不用重复公园条目增加 stops。
- **塔吊广场**：官方只支持滨江步道沿线的标志性景观，未描述独立公共艺术；移除 art/photogenic。可能是北票码头塔吊周边空间，缺坐标且关系未确证，暂不独立选点。 identity or production relationship unresolved; cannot become a new stop pilot boundary or differing representative coordinates need verification
- **谷地花溪**：官方描述滨江绿地、铁轨遗迹及与滑板公园相邻，适合短时景观/遗迹观察。绿地描述不能直接证明 parks；缺少坐标，因此不能参与路线选点。 identity or production relationship unresolved; cannot become a new stop pilot boundary or differing representative coordinates need verification
- **西岸中央公园**：仅有官方名称提及，公园身份可作为核查线索，缺位置、规模和活动内容；角色仅为低置信提议，暂不能参加路线选点。 identity or production relationship unresolved; cannot become a new stop pilot boundary or differing representative coordinates need verification
- **无尽影院**：OSM 明确记录具名 installation artwork，可支持短时作品观察；不是仅凭工业设备名称判断为艺术。公共可达性和长期保留情况未核实，不能据此假设 museum_visit。
- **西岸漩心**：OSM提供具名文化场所线索，位置与既有强节点相邻；仅能提出文化访问补充站，缺少独立内容描述，不能确定 anchor。building=yes 不是建筑体验证据，删除 architecture。

专项低价值检查：

- FISEHOOD极限运动公园：reject；empty validated tags and no independent City Walk evidence; internal entities stay nonselectable
- 攀岩抱石区：reject；empty validated tags and no independent City Walk evidence; internal entities stay nonselectable
- 岩时攀岩(Gate M西岸梦中心)：reject；empty validated tags and no independent City Walk evidence; internal entities stay nonselectable
- 乐动力西岸活力谷：reject；empty validated tags and no independent City Walk evidence; internal entities stay nonselectable
- 西岸国际会展中心(上海)：reject；empty validated tags and no independent City Walk evidence; internal entities stay nonselectable

## 11. semantic_validation_error root causes

历史失败尝试总数 **99**；每次按首要类别归类：`{'unsupported_tag_evidence_or_over_generation': 96, 'syntax_or_schema': 1, 'invalid_role_consistency': 1, 'unsupported_factual_field_or_nonextractive_draft': 1}`。
- 模型用地点名/类别外推 architecture、photogenic、城市更新等；同一段列举多个地点，引用存在却不一定支持当前地点。
- EvidenceBundle 对同一内容按多个组重复展现；原来只反馈首个不支持标签，导致连续试错。
- 自然语言解释混入应为原文摘录的 factual slots；anchor 与 independent_destination_value 不一致。
- 原先把 stability unknown、缺少精确坐标和既有 production 身份问题混为新候选语义问题。
修复使用显式身份/父子关系和针对特定片段的证据选择；保留原严格 validator，不再从反复生成中碰运气。TargetedRepair prompt 要求 uncertain→omit/null；重复证据去重但保留 also_supported_by 引用。

## 12. Retry reduction

本 Repair：**0 外部采集请求、0 DeepSeek 请求、0 retry**。历史调用 158，不将离线审核宣称为模型错误率改善。
三条失败通过 production 身份恢复/内部实体收敛解决，未重新请求成功的55条。选中的重点节点采用明确标注的确定性审核提议；其余已通过结果复用。
TargetedRetryPolicy 只允许 failed / identity_changed / merged / role_ambiguous / tag_reconciliation_required；最多两次。第二次仅语法/schema、单个可省略字段或证据实质改善可重试。证据不足立即 needs_review/reject，不请求模型。
去重前证据 atoms：467；语义输入精简后：298（原 provenance 未删除）。

## 13. Tests

python -m unittest discover -s tests -t . -q: 285 tests passed (259 existing + 26 repair tests); all offline fixtures/mock providers. No live route regression.
复现：`python -m unittest discover -s tests -t . -q`；离线导出：`python scripts/repair_west_bund.py`。

## 14. Files modified

- 新增 `semantic/identity.py`、`consolidation.py`、`repair_policy.py`、`repair_review.py`。
- 新增 `scripts/repair_west_bund.py`、`tests/test_poi_repair.py`、`docs/phases/PHASE2_5B_REPAIR.md`。
- 新增 repaired review / route nodes / source entity registry / identity matches / run metadata；新增本报告。
- README 增加修复报告入口。既有 validator、production、路线/意图/澄清/组合代码和旧阶段产物未改动。
受保护文件 SHA256 全部保持一致：True。

## 15. Exact next-step recommendation

人工先验收艺术中心整体、穹顶双访问范围、滑板公园、跑道公园与摄影艺术中心的节点边界；再确认塔吊广场/北票码头塔吊关系、2555号建筑是否内部实体、运动公园是否与滑板公园重叠。确认滑板公园入口与跑道公园试点范围后，才讨论后续阶段；本轮不进行 promotion。

PHASE 2.5B REPAIR STATUS: PASS

等待人工验收。
