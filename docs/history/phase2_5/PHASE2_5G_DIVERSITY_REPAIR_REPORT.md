# Phase 2.5G Urban Texture & Diversity Repair

## 1. 为什么 F 出现 park-heavy recall

F 新增8个节点中6个为公园。公园的固定实体、公共空间和标签证据较易通过，而故居/建筑的模型输出出现过标签过度推断、事实字段或证据引用失败。因此这是召回准入偏差，并不代表城市本身只有公园。本轮从已缓存候选定向修复，使用最小证据骨架，不增加模型重试。

## 2. 四区类别和角色 before → after

| Zone | 节点 | Category before | Category after | Role before | Role after |
| --- | --- | --- | --- | --- | --- |
| wukang_fuxing_xujiahui | 12 → 17 | {"Plane-tree Neighborhood": 2, "Shikumen": 1, "Historic Residential Architecture": 1, "Historic Residence": 1, "Historic Religious Architecture": 1, "Contemporary Public Cultural Space": 1, "Commercial District": 1, "museum": 1, "heritage": 1, "park": 2} | {"Plane-tree Neighborhood": 2, "Shikumen": 1, "Historic Residential Architecture": 1, "Historic Residence": 1, "Historic Religious Architecture": 1, "Contemporary Public Cultural Space": 1, "Commercial District": 1, "museum": 1, "heritage": 2, "park": 3, "architecture": 2, "cultural_venue": 1} | {'transition_stop': 2, 'supporting_stop': 6, 'anchor': 4} | {'transition_stop': 3, 'supporting_stop': 10, 'anchor': 4} |
| old_city_central | 12 → 17 | {"Shikumen": 2, "Waterfront": 1, "Old City": 1, "Taoist Cultural Site": 1, "Historic Residential Block": 1, "Modern Chinese History": 1, "Commercial Pedestrian Street": 1, "park": 4} | {"Shikumen": 2, "Waterfront": 1, "Old City": 1, "Taoist Cultural Site": 1, "Historic Residential Block": 1, "Modern Chinese History": 1, "Commercial Pedestrian Street": 1, "park": 4, "public_space": 2, "heritage": 2, "architecture": 1} | {'anchor': 8, 'supporting_stop': 4} | {'anchor': 9, 'supporting_stop': 8} |
| hongkou_literary | 11 → 15 | {"Literary District": 2, "Historic Residential Architecture": 1, "Literary Heritage / Bookstore": 1, "Literary & Modern History": 1, "Industrial Heritage": 1, "park": 2, "public_space": 3} | {"Literary District": 2, "Historic Residential Architecture": 1, "Literary Heritage / Bookstore": 1, "Literary & Modern History": 1, "Industrial Heritage": 1, "park": 1, "public_space": 3, "heritage": 3, "cultural_venue": 2} | {'anchor': 4, 'supporting_stop': 6, 'transition_stop': 1} | {'anchor': 4, 'supporting_stop': 9, 'transition_stop': 2} |
| west_bund | 13 → 13 | {"Industrial Heritage": 1, "Contemporary Art": 1, "Industrial Heritage / Contemporary Art": 2, "Industrial Renewal / Waterfront Lifestyle": 1, "cultural_venue": 2, "performance_venue": 2, "park": 2, "public_space": 1, "heritage": 1} | {"Industrial Heritage": 1, "Contemporary Art": 1, "Industrial Heritage / Contemporary Art": 2, "Industrial Renewal / Waterfront Lifestyle": 1, "cultural_venue": 2, "performance_venue": 2, "park": 2, "public_space": 1, "heritage": 1} | {'anchor': 5, 'supporting_stop': 6, 'transition_stop': 2} | {'anchor': 5, 'supporting_stop': 6, 'transition_stop': 2} |

保留旧KB原分类词汇；不把旧类型重写成新taxonomy。角色沿用已审核基线，新角色依独立目的地/体验/连接价值判断。

## 3. 城市肌理与占比

| Zone | 肌理节点 | 公园 | 街道/里弄 | 历史建筑 | 广场/城市公共空间 | 地标 | 文化空间 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| wukang_fuxing_xujiahui | 7 → 11 | 16.7% → 17.6% | 33.3% → 29.4% | 33.3% → 41.2% | 0.0% → 0.0% | 16.7% → 17.6% | 33.3% → 35.3% |
| old_city_central | 7 → 12 | 33.3% → 23.5% | 25.0% → 23.5% | 8.3% → 23.5% | 8.3% → 11.8% | 8.3% → 17.6% | 16.7% → 17.6% |
| hongkou_literary | 7 → 11 | 27.3% → 13.3% | 36.4% → 26.7% | 27.3% → 40.0% | 0.0% → 0.0% | 0.0% → 0.0% | 27.3% → 46.7% |
| west_bund | 9 → 9 | 15.4% → 15.4% | 0.0% → 0.0% | 0.0% → 0.0% | 15.4% → 15.4% | 15.4% → 15.4% | 69.2% → 69.2% |

多标签诊断可重叠；每列分母为该区全部节点。park按poi_type或category判定，包括类别名称不同的鲁迅公园；普通公园绝不计入urban texture，徐家汇公园也保守排除。旧节点用原category/type/name/tags映射，新节点有显式scope/facets审计；不是新推荐标签。文化场馆只有明确建筑/社区等肌理身份才计入texture。

## 4. 定向 shortlist

| Zone | 候选 | 结果 | 原因/缺失 |
| --- | --- | --- | --- |
| old_city_central | 上海人民广场 | accept | fresh_conservative_skeleton_strict_validator_passed |
| old_city_central | 福州路 | accept | fresh_conservative_skeleton_strict_validator_passed |
| old_city_central | 中国社会主义青年团中央机关旧址 | accept | fresh_conservative_skeleton_strict_validator_passed |
| old_city_central | 大韩民国临时政府旧址 | accept | fresh_conservative_skeleton_strict_validator_passed |
| old_city_central | 徐光启故居(九间楼) | defer | No direct subject authority citation for history |
| old_city_central | 东海大楼 | accept | fresh_conservative_skeleton_strict_validator_passed |
| wukang_fuxing_xujiahui | 优秀历史建筑乌鲁木齐南路176号 | accept | fresh_conservative_skeleton_strict_validator_passed |
| wukang_fuxing_xujiahui | 中南新邨 | accept | fresh_conservative_skeleton_strict_validator_passed |
| wukang_fuxing_xujiahui | 盛宣怀住宅 | defer | 权威名单证明住宅稳定存在，但街面可见范围及领事住宅围墙遮挡未核实；保留供人工选择，不凭住宅名气凑数。 |
| wukang_fuxing_xujiahui | 张乐平 | accept | fresh_conservative_skeleton_strict_validator_passed |
| wukang_fuxing_xujiahui | 上海交响乐团音乐厅 | accept | fresh_conservative_skeleton_strict_validator_passed |
| wukang_fuxing_xujiahui | 徐家汇公园 | accept | fresh_conservative_skeleton_strict_validator_passed |
| hongkou_literary | 李白烈士故居 | accept | fresh_conservative_skeleton_strict_validator_passed |
| hongkou_literary | 沈尹默故居 | accept | fresh_conservative_skeleton_strict_validator_passed |
| hongkou_literary | 日本海军特别陆战队司令部旧址 | accept | fresh_conservative_skeleton_strict_validator_passed |
| hongkou_literary | 四川北路文化中心图书馆 | accept | fresh_conservative_skeleton_strict_validator_passed |
| hongkou_literary | 上海多伦路地区海派文化馆(多伦生活广场店) | defer | 多伦路179号存在报纸/地图博物馆名称，不能与今潮海派文化中心混同；未验证该文化馆独立常设展陈。 |
| hongkou_literary | 上海多伦现代美术馆 | accept | fresh_conservative_skeleton_strict_validator_passed |

每区6个，总18个；每区普通公园≤2；未扩大边界、未重新collect整个区域。三个defer不进入62节点，也不阻止整条生产线。

## 5. 新接受的15个 POI

| ID | 名称 | Zone | 角色 | 体验范围 |
| --- | --- | --- | --- | --- |
| pz_0db17d82e9ec | 上海人民广场 | old_city_central | anchor | 城市中心公共广场的独立城市空间体验，可承载上海城市中心主题；不含博物馆、人民公园或地铁内部。 |
| pz_cc5300aee299 | 福州路 | old_city_central | supporting_stop | 有明确文化街身份与连接价值；只观察代表点附近公共街段，不包含沿线书店或场馆内部，不把全路反复计数。 |
| pz_42efca09357d | 中国社会主义青年团中央机关旧址 | old_city_central | supporting_stop | 可主动参访的独立旧址与纪念馆体验，补充老城历史路线；不因红色旧址类别自动认定核心目的地。 |
| pz_66452d5db8a1 | 大韩民国临时政府旧址 | old_city_central | supporting_stop | 官方确认原址保留及近期访问；限定街面旧址观察，内部开放安排未知，不默认为入馆。 |
| pz_463c9b82ac1e | 东海大楼 | old_city_central | supporting_stop | 独立历史建筑立面的观察节点；与南京路总体步行体验区分，不包含商场内部购物。 |
| pz_54f53d30c0dc | 安康公寓（乌鲁木齐南路176号） | wukang_fuxing_xujiahui | transition_stop | 具体门牌的优秀历史建筑外观短观察；不进入居民住宅，不以建筑名气认定anchor。 |
| pz_de47b0cf3e98 | 中南新邨 | wukang_fuxing_xujiahui | supporting_stop | 里弄入口、临街建筑与门上铁艺提供独立建筑阅读；住宅内部及院落均不纳入访问承诺。 |
| pz_437ddd34f2c1 | 张乐平故居 | wukang_fuxing_xujiahui | supporting_stop | 已有近期公众展厅参访证据的故居与漫画创作观察，补充街区文化主题。 |
| pz_7e40d824dbee | 上海交响乐团音乐厅 | wukang_fuxing_xujiahui | supporting_stop | 有直接官方建筑描述的音乐厅外观观察；不包含购票音乐会或未经证明的内部参观。 |
| pz_09b5938601ee | 徐家汇公园 | wukang_fuxing_xujiahui | supporting_stop | 工业及唱片厂址再利用的公共空间观察，补充徐家汇城市文化路线；内部设施不另拆stop。 |
| pz_8b1bb0928e7e | 李白烈士故居 | hongkou_literary | supporting_stop | 独立旧址展陈与电台体验证据充分，作为历史路线的参访补充；不以革命人物知名度直接判anchor。 |
| pz_c862ec0d6ddd | 沈尹默故居 | hongkou_literary | supporting_stop | 独立故居陈列与书法体验，补充文学历史街区；不因标签多少提高角色。 |
| pz_c4f63095cb01 | 日本海军特别陆战队司令部旧址 | hongkou_literary | transition_stop | 官方走读证据支持道路侧旧址观察；军事设施内部完全排除，不提供进入承诺或内部观察位置。 |
| pz_bc5155c245b0 | 四川北路街道图书馆（海伦路505号） | hongkou_literary | supporting_stop | 地址对齐的社区图书馆阅读空间提供主动休憩与文化体验；不把活动临时安排当作常设节目。 |
| pz_f8277d15786a | 上海多伦现代美术馆 | hongkou_literary | supporting_stop | 公立美术馆的独立看展体验；与多伦路公共街段不重复计算，不单拆馆内书房。 |

新增角色：{'anchor': 1, 'supporting_stop': 12, 'transition_stop': 2}。transition_stop没有因数量目标升级为anchor。军事旧址仅限公共道路侧；音乐厅不含内部/音乐会；住宅不承诺进入院落。

## 6. 上海人民广场

{
  "poi_id": "pz_0db17d82e9ec",
  "name": {
    "zh": "上海人民广场",
    "en": "People's Square",
    "aliases": [
      "People's Square",
      "人民广场"
    ]
  },
  "location": {
    "address_zh": "人民大道185号",
    "coordinate_system": "GCJ-02",
    "coordinate_note": "Provider representative anchor, not verified entrance or a routed access point.",
    "representative_lat": 31.228827,
    "representative_lng": 121.475213
  },
  "role": {
    "primary": "anchor",
    "eligible": [
      "anchor"
    ]
  },
  "tags": {
    "interest_tags": [
      "modern_city"
    ],
    "experience_tags": [
      "iconic_landmark"
    ],
    "culture_tags": []
  },
  "visit_profile": {
    "default_mode": "walk_stop",
    "supported_modes": [
      "walk_stop"
    ],
    "modes": {
      "walk_stop": {
        "quick": 9,
        "standard": 18,
        "deep": 26
      }
    }
  },
  "map_identity": {
    "status": "identity_verified",
    "provider_id": "B00157917M",
    "provider_name": "上海人民广场",
    "address": "人民大道185号",
    "old_coordinate": [
      31.228827,
      121.475213
    ],
    "new_coordinate": [
      31.228827,
      121.475213
    ],
    "coordinate_system": "GCJ-02",
    "offset_m": 0.0,
    "basis": "Explicitly reviewed named parent identity/address; subobjects/entrances and unrelated names excluded.",
    "representative_coordinate_not_entire_entity_boundary": true
  }
}

高德parent B00157917M，GCJ-02纬度31.228827、经度121.475213；非人民广场地铁站、人民公园、博物馆或出入口。坐标是代表点而非完整广场边界。human_approved指用户产品准入，不表示已验证实时开放。18分钟是公共广场walk_stop产品估计，不从场馆游览时间复制。公共空间范围官方来源见逐点来源记录。

## 7. ConservativeSemanticRepair

18个进入本轮审查，15个新骨架通过原strict validator，3个defer。不是删除旧失败输出字段来救活它：不读取失败模型文本，按直接主体证据重新构造。interest≤2、experience≤2、culture≤1，至少1个有证据interest；无支持标签立即失败；factual_fields全部null；opening/ticket/reservation不补造；full_visit为null，walk_stop为明确scope的产品估计。坐标继承provider证据，OSM原WGS84记录保留并由已有转换进入GCJ-02。实体稳定与此刻开放分离，current_access_status=unknown，不把夜间closed判成不存在。博物馆名录的主体行补充museum_visit避免偏好漏滤。

## 8. 旧 blocker 的处理

团中央机关旧址、徐家汇公园、李白烈士故居、沈尹默故居均已接受。有明确独立主体来源、固定身份、坐标证据和可解释的supporting_stop。未改变旧POI角色。F留下的其他defer仍留在原档案；本轮按上表限定18个，不用普通候选歧义停止工作。

## 9. 公园冗余 review

| 同区公园对 | 距离km | 标签Jaccard | 建议 |
| --- | --- | --- | --- |
| 太平桥公园/淮海公园 | 0.387 | 1.0 | 供人工决定；未自动删除 |
| 太平桥公园/复兴公园 | 0.885 | 0.167 | 供人工决定；未自动删除 |
| 衡山公园/徐家汇公园 | 0.358 | 0.333 | 供人工决定；未自动删除 |

爱思儿童公园按最新明确指令删除，仅从本轮candidate删除；F归档保留不覆盖。其余仅提出review，靠近或标签类似不能证明体验重复。公园总数11；新增仅1/15。

## 10. 三区 route regression

| Zone | Case | before | after | stop数 | 负偏好 | 区内 | composition |
| --- | --- | --- | --- | --- | --- | --- | --- |
| old_city_central | core_1 | success | success | 4 | True | True | True |
| old_city_central | core_2 | success | success | 4 | True | True | True |
| old_city_central | non_museum | insufficient_route | success | 4 | True | True | True |
| old_city_central | new_coverage | success | success | 4 | True | True | True |
| old_city_central | general_180 | success | success | 5 | True | True | True |
| old_city_central | negative | success | success | 5 | True | True | True |
| old_city_central | history_street | success | success | 4 | True | True | True |
| old_city_central | old_city_life | insufficient_route | insufficient_route | 1 | True | True | False |
| old_city_central | architecture_neighborhood | success | success | 3 | True | True | True |
| wukang_fuxing_xujiahui | core_1 | success | success | 5 | True | True | True |
| wukang_fuxing_xujiahui | core_2 | success | success | 5 | True | True | True |
| wukang_fuxing_xujiahui | non_museum | success | success | 4 | True | True | True |
| wukang_fuxing_xujiahui | new_coverage | success | success | 5 | True | True | True |
| wukang_fuxing_xujiahui | general_180 | success | success | 5 | True | True | True |
| wukang_fuxing_xujiahui | negative | success | success | 5 | True | True | True |
| wukang_fuxing_xujiahui | architecture_life | success | success | 5 | True | True | True |
| hongkou_literary | core_1 | success | success | 5 | True | True | True |
| hongkou_literary | core_2 | success | success | 4 | True | True | True |
| hongkou_literary | non_museum | success | success | 3 | True | True | True |
| hongkou_literary | new_coverage | success | success | 5 | True | True | True |
| hongkou_literary | general_180 | success | success | 5 | True | True | True |
| hongkou_literary | negative | success | success | 5 | True | True | True |
| hongkou_literary | literature_neighborhood | success | success | 5 | True | True | True |

同一fixture before/after，原6例/区全部通过（18/18）；G新增主题4/5通过。新增old_city_life仍不足：真实local_life+old_city相关候选池只有1站，保持失败，不靠无关公园/伪标签凑数。West Bund只读检查保留原art+no museums已知composition failure，13节点未动。跨区三模式12/12通过，places_in_mind按原精确站点规则而非硬加anchor。

## 11. 120/150/180 duration sweep

| Zone | 分钟 | before站数 | after站数 | after状态 | composition |
| --- | --- | --- | --- | --- | --- |
| old_city_central | 120 | 2 | 2 | insufficient_route | True |
| old_city_central | 150 | 2 | 4 | success | True |
| old_city_central | 180 | 3 | 5 | success | True |
| wukang_fuxing_xujiahui | 120 | 3 | 4 | success | True |
| wukang_fuxing_xujiahui | 150 | 4 | 4 | success | True |
| wukang_fuxing_xujiahui | 180 | 5 | 5 | success | True |
| hongkou_literary | 120 | 3 | 4 | success | True |
| hongkou_literary | 150 | 3 | 4 | success | True |
| hongkou_literary | 180 | 5 | 5 | success | True |

旧城120分钟仍2站，保持可见不足。150/180分钟以及其余两区默认时长检查通过。此处只诊断，不改变RouteEngine打分、richness门槛或准入角色。

## 12. Route diversity diagnostics

| Zone | Case | categories | roles | park | street/lane | landmark/building | texture | 类别数 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| old_city_central | core_1 | ['architecture', 'Commercial Pedestrian Street', 'Waterfront', 'park'] | ['supporting_stop', 'anchor', 'anchor', 'supporting_stop'] | 1 | 1 | 2 | 3 | 4 |
| old_city_central | core_2 | ['Waterfront', 'architecture', 'Commercial Pedestrian Street', 'public_space'] | ['anchor', 'supporting_stop', 'anchor', 'supporting_stop'] | 0 | 2 | 2 | 4 | 4 |
| old_city_central | non_museum | ['Waterfront', 'architecture', 'Commercial Pedestrian Street', 'public_space'] | ['anchor', 'supporting_stop', 'anchor', 'supporting_stop'] | 0 | 2 | 2 | 4 | 4 |
| old_city_central | new_coverage | ['architecture', 'Commercial Pedestrian Street', 'Waterfront', 'park'] | ['supporting_stop', 'anchor', 'anchor', 'supporting_stop'] | 1 | 1 | 2 | 3 | 4 |
| old_city_central | general_180 | ['Waterfront', 'architecture', 'Commercial Pedestrian Street', 'public_space', 'public_space'] | ['anchor', 'supporting_stop', 'anchor', 'supporting_stop', 'anchor'] | 0 | 2 | 3 | 5 | 4 |
| old_city_central | negative | ['Waterfront', 'architecture', 'public_space', 'public_space', 'park'] | ['anchor', 'supporting_stop', 'supporting_stop', 'anchor', 'supporting_stop'] | 1 | 1 | 3 | 4 | 4 |
| old_city_central | history_street | ['architecture', 'Commercial Pedestrian Street', 'Waterfront', 'park'] | ['supporting_stop', 'anchor', 'anchor', 'supporting_stop'] | 1 | 1 | 2 | 3 | 4 |
| old_city_central | old_city_life | ['Taoist Cultural Site'] | ['anchor'] | 0 | 0 | 0 | 1 | 1 |
| old_city_central | architecture_neighborhood | ['Old City', 'Taoist Cultural Site', 'Shikumen'] | ['anchor', 'anchor', 'anchor'] | 0 | 1 | 0 | 3 | 3 |
| wukang_fuxing_xujiahui | core_1 | ['Historic Residential Architecture', 'Plane-tree Neighborhood', 'Shikumen', 'architecture', 'Historic Residence'] | ['transition_stop', 'transition_stop', 'supporting_stop', 'transition_stop', 'anchor'] | 0 | 3 | 3 | 5 | 5 |
| wukang_fuxing_xujiahui | core_2 | ['Shikumen', 'architecture', 'park', 'Historic Residence', 'Plane-tree Neighborhood'] | ['supporting_stop', 'transition_stop', 'supporting_stop', 'anchor', 'supporting_stop'] | 1 | 1 | 3 | 4 | 5 |
| wukang_fuxing_xujiahui | non_museum | ['Shikumen', 'architecture', 'park', 'Historic Religious Architecture'] | ['supporting_stop', 'transition_stop', 'supporting_stop', 'anchor'] | 1 | 1 | 2 | 3 | 4 |
| wukang_fuxing_xujiahui | new_coverage | ['Shikumen', 'architecture', 'park', 'Historic Residence', 'Plane-tree Neighborhood'] | ['supporting_stop', 'transition_stop', 'supporting_stop', 'anchor', 'supporting_stop'] | 1 | 1 | 3 | 4 | 5 |
| wukang_fuxing_xujiahui | general_180 | ['Shikumen', 'museum', 'architecture', 'Historic Residential Architecture', 'park'] | ['supporting_stop', 'anchor', 'supporting_stop', 'transition_stop', 'supporting_stop'] | 1 | 2 | 2 | 3 | 5 |
| wukang_fuxing_xujiahui | negative | ['Shikumen', 'museum', 'architecture', 'Historic Residential Architecture', 'park'] | ['supporting_stop', 'anchor', 'supporting_stop', 'transition_stop', 'supporting_stop'] | 1 | 2 | 2 | 3 | 5 |
| wukang_fuxing_xujiahui | architecture_life | ['Historic Residential Architecture', 'Plane-tree Neighborhood', 'Shikumen', 'Historic Religious Architecture', 'Contemporary Public Cultural Space'] | ['transition_stop', 'transition_stop', 'supporting_stop', 'anchor', 'supporting_stop'] | 0 | 3 | 2 | 4 | 5 |
| hongkou_literary | core_1 | ['Historic Residential Architecture', 'Literary & Modern History', 'Literary Heritage / Bookstore', 'heritage', 'Literary District'] | ['supporting_stop', 'supporting_stop', 'supporting_stop', 'transition_stop', 'anchor'] | 0 | 1 | 4 | 4 | 5 |
| hongkou_literary | core_2 | ['Literary District', 'Literary District', 'Literary Heritage / Bookstore', 'Literary & Modern History'] | ['anchor', 'anchor', 'supporting_stop', 'supporting_stop'] | 1 | 0 | 2 | 2 | 3 |
| hongkou_literary | non_museum | ['Literary District', 'Literary District', 'heritage'] | ['anchor', 'anchor', 'transition_stop'] | 1 | 0 | 2 | 2 | 2 |
| hongkou_literary | new_coverage | ['Literary District', 'heritage', 'Literary Heritage / Bookstore', 'Literary & Modern History', 'park'] | ['anchor', 'transition_stop', 'supporting_stop', 'supporting_stop', 'supporting_stop'] | 1 | 0 | 3 | 3 | 5 |
| hongkou_literary | general_180 | ['Historic Residential Architecture', 'cultural_venue', 'Literary & Modern History', 'public_space', 'heritage'] | ['supporting_stop', 'supporting_stop', 'supporting_stop', 'anchor', 'transition_stop'] | 0 | 2 | 3 | 4 | 5 |
| hongkou_literary | negative | ['Literary District', 'public_space', 'public_space', 'heritage', 'Literary District'] | ['anchor', 'transition_stop', 'supporting_stop', 'supporting_stop', 'anchor'] | 1 | 2 | 2 | 4 | 3 |
| hongkou_literary | literature_neighborhood | ['Literary & Modern History', 'public_space', 'Literary Heritage / Bookstore', 'heritage', 'Literary District'] | ['supporting_stop', 'anchor', 'supporting_stop', 'transition_stop', 'anchor'] | 0 | 1 | 3 | 4 | 5 |

上述同类指标亦写入duration sweep、West Bund只读cases和跨区12个mode JSON；soft diagnostic only，不以类别数代替路线质量。

## 13. Cost/source calls

{
  "semantic_candidates_per_zone": {
    "old_city_central": 6,
    "wukang_fuxing_xujiahui": 6,
    "hongkou_literary": 6
  },
  "semantic_candidates_total": 18,
  "deepseek_calls": 0,
  "reused_f_source_checks": 10,
  "new_retained_subject_checks": 23,
  "targeted_map_calls": 16,
  "map_provider_statuses": {
    "success": 6,
    "provider_error": 10
  },
  "accepted": 15,
  "deferred": 3,
  "protected_sha256": {
    "data\\pois.json": "6585b3baf653ae89cc6a1e3c5fc10140bdd801fb298d92c392381d0b5fc17513",
    "data\\pois_phase2_5_candidate.json": "dc30a2933786b2c339a1b1f10ddfbf5f0025b502894f1e376232287799c00d2c",
    "data\\pois_phase2_5_all_zones_candidate.json": "7d773867802236dcffdc0e307bd7fbda1e312f45d7cdf307c055957bc1e0e14c",
    "data\\pois_phase2_5_recall_candidate.json": "ac33bc58127a57f8c06fdf734eb91d1a3e3d3427b4aa4cd167136ed1085d78ee",
    "data\\poi_pipeline\\zone_configs.json": "0c55ae63d737ec5fe6c8ec046567be5c2410c997897a15f08deb32e157555686",
    "src\\poi_pipeline\\semantic\\validation.py": "d3f287eaf46c1e2c14c8955c38e4d760635b4ba92f972c3b14ebbdcae6b47b4a",
    "src\\route_engine.py": "0e2fc008023a39f7282cd0e2344279dc5a3c4df7dfc195c38fed57269451383f"
  },
  "full_zone_collection_calls": 0,
  "source_checks_definition": "Retained inspected candidate/source pairs; broad search-result snippets excluded. Failed map reservations counted, never hidden. Existing coordinate/source caches reused; no model tokens or currency costs."
}

本轮DeepSeek=0，新增模型token=0。16次实际高德窄检：6成功、10provider_error；失败计入成本，未重复重试。未成功或刻意跳过的点保留此前地图坐标/地址来源，不能称为本轮高德确认。23条新增保留的候选/来源检查对 +10条F复用，共33；该数不是网络请求次数，不包括检索无关结果、timeout网页请求。官方网页检索没有完整HTTP调用账单，不能宣称这些是全部网络调用。地图金额未获账单，未估算人民币费用。

## 14. Full tests

{
  "successful": true,
  "runs": [
    {
      "command": "python -m unittest discover -s tests -t . -q",
      "exit_code": 0,
      "tests_run": 372,
      "elapsed_seconds": 12.594
    },
    {
      "command": "python -m scripts.verify_all_zones",
      "exit_code": 0,
      "tests_run": 372,
      "elapsed_seconds": 13.411,
      "failures": 0,
      "errors": 0,
      "successful": true
    }
  ],
  "completed_at": "2026-10-05T02:59:13.497162+00:00",
  "validation_fingerprint": "aa706a5405385d390e108ab1c2f46b92d972de6eb4618a5d2d06266caf4b057b"
}

运行unittest discover与verify_all_zones，后者验证旧40节点pipeline归档。G报告指纹绑定当前62节点candidate与src/scripts/tests代码，不能拿旧测试报告代替G结果。保护哈希含production、旧candidate、Fcandidate、boundaries、strict validator、RouteEngine。

## 15. Final count

48 − 爱思儿童公园1 + 新节点15 = **62**。

| Zone | Count |
| --- | --- |
| wukang_fuxing_xujiahui | 17 |
| hongkou_literary | 15 |
| west_bund | 13 |
| old_city_central | 17 |

四区均route_selectable。新增节点与全部62节点删选清单见 [POI_REVIEW_LIST.md](../project/POI_REVIEW_LIST.md)。显式CLI：`--kb phase2_5_diversity_candidate`；默认仍production。最终文件：`data/pois_phase2_5_diversity_candidate.json`。

## 16. Remaining blockers/limitations

系统blocker：[]。

[
  {
    "zone": "old_city_central",
    "kind": "theme",
    "case": "old_city_life",
    "status": "insufficient_route",
    "stops": 1,
    "reason": [
      "fewer than three suitable stops"
    ]
  },
  {
    "zone": "old_city_central",
    "kind": "duration",
    "case": 120,
    "status": "insufficient_route",
    "stops": 2,
    "reason": [
      "fewer than three suitable stops"
    ]
  }
]

这些未成功fixture为已有/未解决的主题或短预算覆盖限制，不能称为全部场景可用。三项defer详见shortlist，后续人工可以删节点或决定补证，本轮不继续增加。空间置信度均需区分缓存与本轮核验；代表坐标不是入口，未接真实地图routing。

## 17. Promotion recommendation

**PHASE 2.5G STATUS: READY_FOR_PRODUCTION_PROMOTION**

{
  "protected_files": true,
  "frozen_remaining_nodes": true,
  "only_explicit_removal": true,
  "west_bund_13": true,
  "existing_core_regression": true,
  "no_previously_successful_request_regressed": true,
  "cross_modes": true,
  "parks_not_dominant": true,
  "texture_increased_all_three": true,
  "square_human_approved": true,
  "no_fake_richness": true,
  "full_tests": true
}

建议进入人工最终验收；这不是自动推广。判断依据为公园占比下降、三区肌理增加、广场身份完成、strict validator保持、18原回归和12模式通过且无已成功主题退化、完整测试通过。old_city_life与旧城120分钟限制明确披露，不把这两个场景列为通过。未覆盖data/pois.json，未做Phase3/前端/真实地图routing。验收删选后必须重跑G回归和测试再推广。

## 18. 逐点证据/来源

### 上海人民广场

- [government](https://cgzf.sh.gov.cn/cmsres/93/93019f9cb5d44c08933f17508a226ea6/6db9509e42251bc6063c5b003b6e8ff2.pdf) retrieved_at=2026-10-05T02:33:01.163569+00:00；摘录：东起西藏中路西侧人行道，西至黄陂北路东侧人行道，南起延安东路北侧人行道，北至上海大剧院和人民大道200号外墙沿线范围内的公共区域。
- [government](https://www.shanghai.gov.cn/nw18454/20260602/40dbded48d5747bdb76023efebc0cc60.html) retrieved_at=2026-10-05T02:33:01.163639+00:00；摘录：人民广场是上海的城市核心地标，更是见证百年城市变迁、镌刻红色发展记忆的重要载体。人民广场从旧时风貌蝶变为现代化城市客厅的百年历程。

### 福州路

- [government](https://www.shanghai.gov.cn/gwk/search/content/cf46474f-4259-4087-ada5-105e2ec94971) retrieved_at=2026-10-05T02:33:01.169643+00:00；摘录：上海市主要道路（河道）和景观区域范围界定。福州路 | 中山东一路-西藏中路
- [government](https://www.shanghai.gov.cn/nw12344/20260228/2bd94b73f5d74b28bf38d392cebd8ab6.html) retrieved_at=2026-10-05T02:33:01.169698+00:00；摘录：建设福州路文化街等“阅读+”街区，构建“城市书房”体系，形成建筑可阅读、街区可漫步、书店可品味的书香氛围。

### 中国社会主义青年团中央机关旧址

- [government](https://www.shanghai.gov.cn/nw17239/20260924/6d8d89744aef4043b941cbf78fede58b.html) retrieved_at=2026-10-04T16:17:44.582021+00:00；摘录：中国社会主义青年团中央机关旧址纪念馆
地址：淮海中路567弄1-6号
该7处场馆均向公众（含未成年人）免费开放，无需预约。
- [government](https://whlyj.sh.gov.cn/bwg/20250227/c238000e1dc5486e8027e2c4e1774ac4.html) retrieved_at=2026-10-05T02:53:51.348199+00:00；摘录：上海市博物馆名单（2024年度）。中国社会主义青年团中央机关旧址纪念馆 | 淮海中路567弄1-6号

### 大韩民国临时政府旧址

- [government](https://www.shanghai.gov.cn/gwk/search/content/f6c94ab732754740a06562bd7aeae40c) retrieved_at=2026-10-04T16:17:47.371768+00:00；摘录：区级文物保护单位大韩民国临时政府旧址（马当路306弄4号）本体原址保留，不纳入征收实施范围。
- [government](https://www.shanghai.gov.cn/nw4411/20260108/8358d0e5029b45a981750e8696ba90c7.html) retrieved_at=2026-10-04T16:17:47.371818+00:00；摘录：下午，总统夫妇一同访问大韩民国临时政府旧址。
- [government](https://whlyj.sh.gov.cn/bwg/20250227/c238000e1dc5486e8027e2c4e1774ac4.html) retrieved_at=2026-10-05T02:53:51.353083+00:00；摘录：上海市博物馆名单（2024年度）。大韩民国临时政府旧址管理处 | 马当路306弄4号

### 东海大楼

- [government](https://fgj.sh.gov.cn/yxlsjz/20210922/8f72fa07617c4828a25ef948cd1c5da7.html) retrieved_at=2026-10-05T02:33:01.183336+00:00；摘录：优秀历史建筑。2A027 | 慈淑大楼 | 东海商都 | 南京东路353号

### 优秀历史建筑乌鲁木齐南路176号

- [government](https://fgj.sh.gov.cn/yxlsjzjk/20240223/921ff8d978724856b21e8c38fc1d23ba.html) retrieved_at=2026-10-04T16:18:04.034549+00:00；摘录：原则同意乌鲁木齐南路176号等优秀历史建筑保护性修缮项目设计方案
- [government](https://fgj.sh.gov.cn/yxlsjz1/20200331/e3b99cf457ae48cab87ad5c02aa0fee3.html) retrieved_at=2026-10-05T02:33:01.301093+00:00；摘录：优秀历史建筑。4D033 | 巨福公寓/安康公寓 | 安康公寓/乌鲁木齐公寓 | 乌鲁木齐南路176号

### 中南新邨

- [government](https://www.xuhui.gov.cn/zfjg_qzfbm_fgj_bmdt/20241104/546672.html) retrieved_at=2026-10-05T02:33:01.305296+00:00；摘录：中南新邨 建筑类型 | 花园式里弄 建筑地址 | 淮海中路1670弄 建筑风格 | 现代主义风格。中南新邨建筑均为平缓的红瓦坡屋顶，形式简洁，横向窗间墙灰绿色面砖贴面，深绿色钢窗，整体强调水平线条。

### 张乐平

- [government](https://www.xuhui.gov.cn/xwzx_zwxx/20260715/575182.html) retrieved_at=2026-10-05T02:33:01.309594+00:00；摘录：离开武康大楼，一行人抵达五原路288弄张乐平故居，走近“三毛之父”，探寻经典漫画背后的温情与初心。在专业讲解员的带领下，大家参观故居展厅，了解张乐平先生的创作生涯。
- [government](https://www.xuhui.gov.cn/xwzx_zwxx/20260702/574867.html) retrieved_at=2026-10-05T02:33:01.309629+00:00；摘录：完成武康大楼、周璇旧居门头、张乐平故居三毛艺术弄等12个点位电影主题微更新
- [government](https://whlyj.sh.gov.cn/bwg/20250227/c238000e1dc5486e8027e2c4e1774ac4.html) retrieved_at=2026-10-05T02:53:51.491254+00:00；摘录：上海市博物馆名单（2024年度）。衡复风貌博物馆群 | 张乐平故居（五原路288弄3号）

### 上海交响乐团音乐厅

- [government](https://www.shanghai.gov.cn/xuhui/index.html) retrieved_at=2026-10-05T02:33:01.312738+00:00；摘录：上海交响乐团音乐厅位于上海复兴中路1380号。建筑外立面采用褐红色陶土砖，曲面屋顶形似摊开的乐谱，因外观被昵称为“馄饨皮”。

### 徐家汇公园

- [government](https://www.shanghai.gov.cn/nw17239/20250324/147efed623f141bb95a509e62aefdd0f.html) retrieved_at=2026-10-04T16:18:10.952160+00:00；摘录：徐家汇公园的樱花主要集中在悬铃木大道的南端和汇金湖河畔，粉白色的染井吉野樱和东京樱与湖光林色交相辉映
- [government](https://www.shanghai.gov.cn/nw15343/20250625/89c5c3f7be2a4dfbaae717e8bb74de36.html) retrieved_at=2026-10-04T16:29:33.815752+00:00；摘录：在徐家汇公园，曹立强沿着人行步道察看景观绿化养护、儿童空间打造以及公厕布局等情况。

### 李白烈士故居

- [government](https://www.shhk.gov.cn/xwzx/002008/002008045/002008045002/20260907/a797bda7-753b-4a6f-b8a3-bdeda4d9c9ba.html) retrieved_at=2026-10-04T16:18:22.358788+00:00；摘录：坐南朝北的三层砖木结构的老式洋房，曾是抗日战争和解放战争时期李白同志的住所，也是他最后居住、工作和被捕的地方。一、二楼李白烈士事迹陈列室，讲述了李白的成长经历以及与敌人斗争的光辉事迹。三楼为场景复原，再现了李白烈士生前战斗、生活的情景。
- [government](https://www.shhk.gov.cn/xwzx/002008/002008047/002008047002/20251222/17639b35-93cb-4d17-87de-e06467604e62.html) retrieved_at=2026-10-04T16:29:38.932348+00:00；摘录：故居还保留了发报互动体验区，并在发报设备上进行了提升优化，同时设置了一定难度，让观众可以学习摩斯电码小知识，体验更真实的发送电码过程，寓教于乐。
- [government](https://www.shhk.gov.cn/qyfwy/030002/030002002/030002002002/20190111/b53c6837-8bb2-4cc0-85b6-773559cc68ec.html) retrieved_at=2026-10-05T02:33:01.433500+00:00；摘录：李白烈士故居位于黄渡路107弄亚西亚里15号。故居建筑为欧式联排花园里弄住宅，建于1935年。坐北朝南，砖木结构三层。1987年，故居对外开放。一、二楼为展厅，展出李白生平事迹；三楼为场景复原，再现李白生前战斗、生活的情景。
- [government](https://whlyj.sh.gov.cn/bwg/20250227/c238000e1dc5486e8027e2c4e1774ac4.html) retrieved_at=2026-10-05T02:53:51.622153+00:00；摘录：上海市博物馆名单（2024年度）。李白烈士故居 | 黄渡路107弄15号

### 沈尹默故居

- [government](https://www.shhk.gov.cn/qyfwy/030002/030002002/030002002005/20181215/b300eab7-5cb1-43de-835b-b20d2b40308c.html) retrieved_at=2026-10-04T16:18:25.315161+00:00；摘录：沈尹默故居是沿街三层两开间西式住宅，居门首挂有赵朴初题写的“沈尹默先生故居”匾额。底楼是陈列室、有沈尹默的半身塑像，橱里陈列着沈尹默先生生前眼镜、笔筒等遗物和书法集、诗词集、书法理论等。二楼是书房兼画室，陈列着沈尹默的书法精品。
- [government](https://www.shhk.gov.cn/slh/038001/20251114/803f173f-6bd9-4bbc-aa6d-5aeff18bb1f7.html) retrieved_at=2026-10-04T16:18:25.315215+00:00；摘录：统筹84处红色旧址遗址，推出“重走解放路”等研学线路，活化沈尹默故居、景云里名人故居群等历史建筑，让居民在城市更新中触摸文化根脉。
- [government](https://whlyj.sh.gov.cn/bwg/20250227/c238000e1dc5486e8027e2c4e1774ac4.html) retrieved_at=2026-10-05T02:53:51.628319+00:00；摘录：上海市博物馆名单（2024年度）。沈尹默故居 | 海伦路504号

### 日本海军特别陆战队司令部旧址

- [government](https://www.shhk.gov.cn/xwzx/002004/20190826/eb1c2f45-f642-4218-af30-3327b4777473.html) retrieved_at=2026-10-05T02:33:01.444713+00:00；摘录：走读李白烈士故居、日本海军特别陆战队司令部旧址和周恩来在沪早期革命活动旧址。日本海军特别陆战司令部旧址位于黄渡路口，斑驳的围墙记录了这幢看似普通的建筑背后的历史。这里曾经是日军重要军事基地，如今已是解放军部队的重要军事基地。

### 四川北路文化中心图书馆

- [government](https://www.shhk.gov.cn/shhk/8a8aec5f-a003-4c93-911d-88d2dcc2eaef/c5ab84a9-8af4-4579-8550-353a1ec06475/%E8%99%B9%E5%8F%A3%E5%B9%B4%E9%89%B42021.pdf) retrieved_at=2026-10-05T02:33:01.449841+00:00；摘录：四川北路街道图书馆 | 海伦路505号
- [government](https://www.shhk.gov.cn/hkjy_nas/07b6abda-39b8-4046-a72c-cd4dd334fb96/f127a8f8-8eb5-4d3e-a2a1-28e7043c3d80/2025%E5%B9%B4%E6%9A%91%E6%9C%9F%E6%B4%BB%E5%8A%A8%E9%A1%B9%E7%9B%AE%EF%BC%88%E6%AD%A3%E7%A8%BF%29.pdf) retrieved_at=2026-10-05T02:33:01.449973+00:00；摘录：四川北路街道 海伦路505号。前往社区图书馆少儿阅览室，在书海遨游；体验图书馆“小小志愿者”活动，了解图书馆管理、收归整理等流程。

### 上海多伦现代美术馆

- [government](https://www.shhk.gov.cn/bmff/004001/004001006/004001006002/20260428/fb47bcab-fc58-4d6d-9faf-5fe6b0892b92.html) retrieved_at=2026-10-05T02:33:01.455131+00:00；摘录：上海多伦现代美术馆 地址：多伦路27号 开放时间：周二至周日 10:00-18:00（17:30停止入场）

GCJ-02坐标继承、原provider、tag evidence_refs、坐标/地址field_sources见每个`*_repair.json`和candidate.source_provenance；six verified map IDs与其余cached_geometry_retained分开记录于review.json。短摘录仅支撑所引主体，不借用文章沿途其他景点。
