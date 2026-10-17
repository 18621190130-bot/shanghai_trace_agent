# ShanghaiTrace Phase 2.5F — Recall Repair Report

2026-10-04T16:43:10.297015+00:00

## 1. 为什么需要 Recall Repair

D/E 的 1147 条 raw 记录最终新增 5 个节点；仅 3 / 2 / 3 个 prefilter survivors 无法证明现实缺少步行节点。F 阶段复用缓存，区内灰区再审，最终准入标准保持不变。

## 2. Funnel Before → After

| Zone | Raw | Canonical | Old survivors | Shortlist | Understood cached/new | New accept | Final nodes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 老城厢—新天地—外滩 | 524 | 417 | 2 | 11 | 6 | 3 | 12 |
| 武康—复兴—徐家汇 | 303 | 224 | 3 | 10 | 8 | 3 | 12 |
| 鲁迅公园—四川北路 | 320 | 220 | 3 | 8 | 4 | 2 | 11 |

全阶段计数、18 类 rejection/defer histogram 及原始原因位于 `data/poi_pipeline/recall/*_funnel_before.json`。Raw、source-ID unique 和 route canonical 不可相加；enriched 为候选数，API 次数另列。重复、内部对象、边界外和普通服务继续排除。历史原始 disposition 保留，不以当前规则改写过去结果。

| Zone | Unique normalized | Boundary survivors | Production duplicates | Internal/child | Early reject | Old deferred | Old enriched | Old accepted |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 老城厢—新天地—外滩 | 524 | 337 | 6 | 59 | 70 | 192 | 1 | 1 |
| 武康—复兴—徐家汇 | 303 | 134 | 7 | 17 | 61 | 61 | 1 | 1 |
| 鲁迅公园—四川北路 | 320 | 228 | 3 | 17 | 79 | 114 | 3 | 3 |

## 3. Recall 规则与漏失原因

旧规则把缺少官方摘录直接视为不足，未先理解路线潜力；“临时政府旧址”被临时设施正则误伤。修复仅影响进入理解阶段：历史旧址例外、先审地图身份和独立体验、补少量直接证据。普通体育设施排除，但公园的 provider 体育休闲分类不会否定公园。Strict validator、taxonomy、角色价值标准均未改动。

明确拆分 entity_stability 与 current_access_status。Closed、暂停开放、非营业时间不能推导临时或不存在；只有永久关闭、拆除、撤除等直接证据影响长期存在。淮海公园地图标签不能证明停建或不存在，已按稳定公园接受，实时开放状态 unknown，并保留原标签。公共街面/展陈体验范围仍需证据，这与此刻营业无关。

## 4. 每区 shortlist

### 老城厢—新天地—外滩

| Rank | Candidate | Disposition | Reason |
| --- | --- | --- | --- |
| 1 | 太平桥公园 | accept | unchanged_validator_and_admission_passed |
| 2 | 淮海公园 | accept | unchanged_validator_and_admission_passed |
| 3 | 福州路 | defer | independent_value_or_confidence_unresolved |
| 4 | 复兴公园 | accept | unchanged_validator_and_admission_passed |
| 5 | 中国社会主义青年团中央机关旧址 | defer | strict_semantic_validation_or_provider_failure |
| 6 | 大韩民国临时政府旧址 | defer | independent_value_or_confidence_unresolved |
| 7 | 延中公园 | defer | weak_location |
| 8 | 徐光启故居(九间楼) | defer | insufficient_evidence |
| 9 | fudeli | defer | weak_identity |
| 10 | 上海人民广场 | defer | weak_location |
| 11 | 东海大楼 | defer | insufficient_evidence |

### 武康—复兴—徐家汇

| Rank | Candidate | Disposition | Reason |
| --- | --- | --- | --- |
| 1 | 武康路历史文化名街 | accept | unchanged_validator_and_admission_passed |
| 2 | 普希金雕像 | defer | independent_value_or_confidence_unresolved |
| 3 | 衡山公园 | accept | unchanged_validator_and_admission_passed |
| 4 | 天钥桥路口袋公园 | defer | independent_value_or_confidence_unresolved |
| 5 | 优秀历史建筑乌鲁木齐南路176号 | defer | independent_value_or_confidence_unresolved |
| 6 | 襄阳公园 | accept | unchanged_validator_and_admission_passed |
| 7 | 徐家汇公园 | defer | strict_semantic_validation_or_provider_failure |
| 8 | 聂耳铜像 | defer | independent_value_or_confidence_unresolved |
| 9 | 中南新邨 | defer | insufficient_evidence |
| 10 | 盛宣怀住宅 | defer | insufficient_evidence |

### 鲁迅公园—四川北路

| Rank | Candidate | Disposition | Reason |
| --- | --- | --- | --- |
| 1 | 山阴路274弄 | accept | unchanged_validator_and_admission_passed |
| 2 | 李白烈士故居 | defer | strict_semantic_validation_or_provider_failure |
| 3 | 沈尹默故居 | defer | strict_semantic_validation_or_provider_failure |
| 4 | 爱思儿童公园 | accept | unchanged_validator_and_admission_passed |
| 5 | 四川北路文化中心图书馆 | defer | insufficient_evidence |
| 6 | 上海多伦路地区海派文化馆(多伦生活广场店) | defer | insufficient_evidence |
| 7 | 上海子兮艺术社非遗文化馆 | defer | insufficient_evidence |
| 8 | 日本海军特别陆战队司令部旧址 | defer | insufficient_evidence |

已确认的春广场、世界文豪广场、梅园为 parent 内部对象；保留在 pool screen，最终 shortlist 排除，不调用模型。人民公园维持原 defer，不扩边界。

## 5. 新增 accepted POIs

| ID | Zone | Name | Role |
| --- | --- | --- | --- |
| pz_68957332b418 | 老城厢—新天地—外滩 | 太平桥公园 | supporting_stop |
| pz_8919938b21f2 | 老城厢—新天地—外滩 | 淮海公园 | supporting_stop |
| pz_bd40d04c7f5d | 老城厢—新天地—外滩 | 复兴公园 | anchor |
| pz_a87eb2b5b5da | 武康—复兴—徐家汇 | 武康路历史文化名街 | anchor |
| pz_553cfd36707c | 武康—复兴—徐家汇 | 衡山公园 | supporting_stop |
| pz_a27dbbc6cab8 | 武康—复兴—徐家汇 | 襄阳公园 | supporting_stop |
| pz_a446052910a0 | 鲁迅公园—四川北路 | 山阴路274弄 | transition_stop |
| pz_f2fffcd2526c | 鲁迅公园—四川北路 | 爱思儿童公园 | supporting_stop |

## 6. Route Role 与 Composition

| Zone | Anchor before→after | Supporting before→after | Transition before→after |
| --- | --- | --- | --- |
| 武康—复兴—徐家汇 | 3 → 4 | 4 → 6 | 2 → 2 |
| 老城厢—新天地—外滩 | 7 → 8 | 2 → 4 | 0 → 0 |
| 鲁迅公园—四川北路 | 4 → 4 | 5 → 6 | 0 → 1 |
| West Bund | 5 → 5 | 6 → 6 | 2 → 2 |

22 个 existing role audit 冻结；未将 supporting 升为 anchor，也未为凑站数改变 composition policy。新增角色理由和 eligible/confidence 在 candidate 的 route_role 中。

## 7. Coverage Before → After

### 老城厢—新天地—外滩

| Group | Changed tag frequencies |
| --- | --- |
| interest_tags | parks: 1→4, gardens: 1→2 |
| experience_tags | neighborhood_walk: 5→6, photogenic: 6→7 |
| culture_tags | garden_culture: 1→2, public_life: 2→3 |

### 武康—复兴—徐家汇

| Group | Changed tag frequencies |
| --- | --- |
| interest_tags | history: 6→7, parks: 0→2, gardens: 0→1 |
| experience_tags | neighborhood_walk: 3→4, street_scene: 3→4, local_atmosphere: 2→3, photogenic: 2→3 |
| culture_tags | modern_shanghai: 8→9, public_life: 3→4 |

### 鲁迅公园—四川北路

| Group | Changed tag frequencies |
| --- | --- |
| interest_tags | parks: 2→3 |
| experience_tags | street_scene: 3→4 |
| culture_tags | lane_life: 3→4 |

## 8. Duration Sweep Before → After

| Zone | Before 120/150/180 | After 120/150/180 |
| --- | --- | --- |
| 老城厢—新天地—外滩 | 2/2/3 | 2/2/3 |
| 武康—复兴—徐家汇 | 3/4/5 | 3/4/5 |
| 鲁迅公园—四川北路 | 3/3/4 | 3/3/5 |

老城 short-route limitation remains：2 / 2 / 3。武康 3 / 4 / 5 不变，新增改善选择多样性；虹口 180 分钟增加一站。未插 filler，未修改 route scoring。

## 9. 原六用例与跨区 Three-mode

| Zone | Before passed | After passed |
| --- | --- | --- |
| 老城厢—新天地—外滩 | 5/6 | 5/6 |
| 武康—复兴—徐家汇 | 6/6 | 6/6 |
| 鲁迅公园—四川北路 | 5/6 | 6/6 |

跨四区三模式：12/12。West Bund 只读原回归通过预期，纯 art/no museum 的 composition_failure 是原明确预期。老城 non_museum 短路线仍不足三站，未隐藏。每例记录 stop count、matched tags/relevance、negative preferences、role mix、time utilization、最大单段估算距离与 zone isolation。地理距离为代表点估算，无真实地图 routing。

## 10. 定向坐标核验

| ID | Name | Old GCJ-02 [lat,lng] | New | Offset m | Confidence |
| --- | --- | --- | --- | --- | --- |
| p7 | 新天地北里（石库门街区） | [31.2212, 121.4679] | [31.220692, 121.474751] | 653.9 | high |
| p9 | 张园 | [31.2286, 121.4638] | [31.227971, 121.460064] | 362.1 | high |
| p13 | 武康大楼 | [31.2108, 121.4472] | [31.20443, 121.438278] | 1105.3 | high |

p7：太仓路、兴业路、马当路、黄陂南路街区，与高德太仓路181弄北里身份一致。 [高德](https://www.amap.com/detail/B00156YMMX) [权威来源](https://www.shanghai.gov.cn/nw31406/20250707/93b77d0a95794a39a75b7e8ef69ccfed.html)

p9：茂名北路188弄；高德258号为同一张园街区另一地址，非门牌一一相等；采用 provider 街区代表点。 [高德](https://www.amap.com/detail/B00155QIPB) [权威来源](https://arabic.shanghai.gov.cn/cmsres/fb/fb4c67ebf9604322a8b3f6f74d7e1760/eec310a1555eb5a02a121cee2922800d.pdf)

p13：官方与高德均指淮海中路1850号武康大楼。 [高德](https://www.amap.com/detail/B00155ITJ1) [权威来源](https://japanese.shanghai.gov.cn/ja-CityWalk/20240325/ab41c95b41a54cef96d54c2ab843abd9.html)

均仅写入 recall candidate；张园门牌差异显式保留，代表点不是实际入口。三点都在原 boundary/review margin 内。

## 11. Remaining Human Review

本轮没有把证据不足或模型技术失败推给人工产品判断；最终 human_review 为空，各区 ≤5。确定的身份/独立体验不足继续 defer；旧人民公园 defer 保持。技术阻断另列，未伪装为普通 ambiguity。

## 12. 未救回的高潜力候选

### 老城厢—新天地—外滩

| Name | Reason | Missing evidence / contract |
| --- | --- | --- |
| 中国社会主义青年团中央机关旧址 | strict_semantic_validation_or_provider_failure | Evidence already improved; missing a consistent, strictly evidence-cited semantic proposal. anchor requires high independent destination value |
| 大韩民国临时政府旧址 | independent_value_or_confidence_unresolved | confident stable independent visit scope |
| 福州路 | independent_value_or_confidence_unresolved | confident stable independent visit scope |
| 徐光启故居(九间楼) | insufficient_evidence | independent public observation or exhibition scope |
| 延中公园 | weak_location | sub-park identity and representative anchor |

### 武康—复兴—徐家汇

| Name | Reason | Missing evidence / contract |
| --- | --- | --- |
| 徐家汇公园 | strict_semantic_validation_or_provider_failure | Evidence already improved; missing a consistent, strictly evidence-cited semantic proposal. photogenic unsupported by cited evidence; remove or cite explicit matching description |
| 普希金雕像 | independent_value_or_confidence_unresolved | confident stable independent visit scope |
| 聂耳铜像 | independent_value_or_confidence_unresolved | confident stable independent visit scope |
| 优秀历史建筑乌鲁木齐南路176号 | independent_value_or_confidence_unresolved | confident stable independent visit scope |
| 天钥桥路口袋公园 | independent_value_or_confidence_unresolved | confident stable independent visit scope |

### 鲁迅公园—四川北路

| Name | Reason | Missing evidence / contract |
| --- | --- | --- |
| 李白烈士故居 | strict_semantic_validation_or_provider_failure | Evidence already improved; missing a consistent, strictly evidence-cited semantic proposal. art unsupported by cited evidence; remove or cite explicit matching description |
| 沈尹默故居 | strict_semantic_validation_or_provider_failure | Evidence already improved; missing a consistent, strictly evidence-cited semantic proposal. architecture unsupported by cited evidence; remove or cite explicit matching description; architecture_detail unsupported by cited evidence; remove or cite explicit matching description; modern_shanghai unsupported by cited evidence; remove or cite explicit matching description |
| 日本海军特别陆战队司令部旧址 | insufficient_evidence | public exterior scope/access |
| 四川北路文化中心图书馆 | insufficient_evidence | current identity/public access |
| 上海多伦路地区海派文化馆(多伦生活广场店) | insufficient_evidence | venue identity and independent visitor scope |

## 13. 调用成本

| Metric | Phase 2.5F |
| --- | --- |
| reused_cached_records | 1147 |
| targeted_retained_source_checks | 31 |
| targeted_source_checks_lifetime | 34 |
| targeted_coordinate_provider_checks | 3 |
| first_calls | 19 |
| retry_calls | 5 |
| total_semantic_calls | 24 |
| cache_hits_last_offline_pass | 18 |
| total_tokens | 108696 |
| accepted | 8 |
| deferred | 21 |
| rejected | 0 |
| rejected_before_shortlist | 554 |

19 首次调用记录对应18个不同候选，另5次有实质补证的重试，共24/30；各区首次记录为 {'old_city_central': 7, 'wukang_fuxing_xujiahui': 8, 'hongkou_literary': 4}。明确偏差：One already successful Taipingqiao Park candidate was accidentally called again when Amap identity changed its cache key. Both calls retained/accounted; original successful output reused. Cache now resolves candidate_id before provider identity. No other successful node re-enriched.

现有 shortlist 保留31项来源检查，早期3项内部对象归属核验计入 lifetime34；另3次坐标详情。Targeted search 无可靠结果的检查保留在 defer note，不宣称所有网页查找均有成功来源。来源数指被核验的候选来源，不是搜索引擎返回结果条数。D/E三区语义调用13，另intent smoke3；West Bund旧pilot158调用/929709 tokens，本轮未重跑。货币成本未凭未核验单价估算。Offline最后重放仅cache hit，无新增API。

## 14. 完整测试

`python -m unittest discover -s tests -t . -q`：{'command': 'python -m unittest discover -s tests -t . -q', 'tests_run': 361, 'failures': 0, 'errors': 0, 'successful': True, 'exit_code': 0, 'elapsed_seconds': 11.44}

`python -m scripts.verify_all_zones`：361 tests，0 failures，0 errors。当前源码指纹有效：True。新增覆盖预算、身份变化复用缓存、闭园与消失区别、历史临时政府、冻结ID/角色/边界、six-case请求一致与硬约束。

## 15. 最终 POI 数量

48 nodes；{'wukang_fuxing_xujiahui': 12, 'hongkou_literary': 11, 'west_bund': 13, 'old_city_central': 12}。West Bund13及p36–p43字节内容对应对象不变。没有新增 parent 内拆分节点。

## 16. Exact Candidate File

`data/pois_phase2_5_recall_candidate.json`

显式 CLI KB 名：`phase2_5_recall_candidate`；默认仍是production。旧all-zone candidate、pilot candidate、production、zone config全部通过原SHA校验。Evidence checks、call ledger、cache原始输出、funnel、coverage和regression JSON位于`data/poi_pipeline/recall/`。所有短摘录、URL和retrieved_at已逐候选保存于`*_evidence_checks.json`。

## 17. Promotion Recommendation

**PHASE 2.5F STATUS: BLOCKED**

未证明高潜力节点不再被系统性漏掉：团中央机关旧址、徐家汇公园、李白烈士故居、沈尹默故居已有直接来源，第二次提案仍因unsupported tags/citation或anchor/value矛盾被严格校验拒绝。它们不是当前闭馆问题，也不是待人工决定的普通 ambiguity。模型提案与证据引用可靠性是本阶段明确技术 blocker；各节点两次尝试已用尽，禁止第三次或标签校验绕过。现48-node候选可人工查看，但不推荐直接promotion。

停在candidate与报告；不覆盖production，不开始Phase3。
