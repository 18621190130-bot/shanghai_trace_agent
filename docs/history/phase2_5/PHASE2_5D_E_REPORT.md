# Phase 2.5D/E — 四区 candidate 验收报告

PHASE 2.5 ALL-ZONE STATUS: **READY_FOR_FULL_PROMOTION**

2026-10-04。三区升级完成，最终 candidate 共 **40 个 route-selectable nodes**。READY 表示可进入人工整库验收，不表示已 promotion，也不保证所有主题、时长都有三点路线。production 未覆盖。

## 1. Generic pipeline architecture

统一入口 `python -m scripts.run_poi_pipeline --zone all` 按 metadata 顺序处理武康、老城厢、虹口，跳过西岸。流程为 config → collection → normalize → boundary → deduplication → production identity → route-node consolidation → deterministic prefilter → compact-evidence enrichment → validation → role/admission → candidate merge → coverage → regression → next zone。

`zone_collection.py`、`zone_semantic.py`、`zone_candidate_kb.py`、`zone_regression.py` 共享实现，区域差异进入配置。`ZoneCoverageAnalyzer` 为通用审计器，旧 WestBundCoverageAnalyzer 保持兼容。旧 West Bund 流程默认行为保持不变。

归一化保留源记录；同名街道多个对象合并；入口、内部雕塑和打卡点不重复计数。跨区 production identity 识别已归属其他区的对象。新增 ID 按 zone 与稳定 provider identity 生成。

服务设施、临时/附属对象、边界外、既有 production、内部节点与证据不足对象先确定性筛除，再调用模型。每稳定节点累计至多两次 enrichment，缓存/证据变动不能重置预算；第二次限可说明的补证或验证修复，仍失败则 defer。主体校验删除整条游线以及邻近公园/商业街不能支持的本体标签。

## 2. Zone configs 与初始产品边界

完整顶点、逐点覆盖、道路依据、URL 和 retrieved_at 见 [ZONE_BOUNDARY_REPORT.md](../project/ZONE_BOUNDARY_REPORT.md)、`data/poi_pipeline/zone_configs.json` 与 `all_zones/boundary_validation.json`。三区均为 `approved_for_phase2_5_pipeline`；GCJ-02，数组顺序为纬度、经度，review margin 150m。

| Zone | 顶点 | 面积 km² | Production seeds | 150m 内覆盖 |
|---|---:|---:|---:|---|
| wukang_fuxing_xujiahui | 13 | 5.2657 | 8 | 全部 |
| old_city_central | 15 | 7.6729 | 8 | 全部 |
| hongkou_literary | 12 | 2.5803 | 6 | 全部 |

基于高德道路地物、官方空间上下文及 seeds 建立保守产品边界，不是行政边界或 seed bounding box。通过非退化、无自交、面积、坐标及 seed 覆盖检查；面积阈值仅为诊断，合理性另由来源与走廊说明支持。审核带候选输出 `needs_boundary_review`，不因在带内自动 reject；内部兼容枚举为 needs_review。

`boundaries_gcj02.json` 可直接查看，明确是 GCJ-02，不冒充 RFC7946 WGS84 GeoJSON。没有引入大型依赖。西岸边界不变。

## 3. Baseline 与最终规模

| Zone | 基线 | 新增 | 最终 | 主要 interest 主题 |
|---|---:|---:|---:|---|
| 武康—复兴—徐家汇 | 8 | 1 | 9 | architecture, history, local_life, shopping_lifestyle |
| 老城厢—新天地—外滩 | 8 | 1 | 9 | architecture, history, shopping_lifestyle, local_life, modern_city |
| 鲁迅公园—四川北路 | 6 | 3 | 9 | history, literature, architecture |
| 徐汇西岸滨江 | 13 | 0 | 13 | art, waterfront, architecture, industrial_heritage, parks |

没有为凑 10–15 个放宽证据、拆分父子对象或扩大边界。各区 `_baseline_report.json` 保存 frequency、zero/low coverage、标签共现、类别和地理分布；`_coverage_report.json` 保存升级前后完整比较。

## 4. 新增 route nodes

| POI ID | 名称 | Zone | Primary role | Confidence |
|---|---|---|---|---|
| pz_17d41390cac9 | 上海工艺美术博物馆 | wukang_fuxing_xujiahui | anchor | medium |
| pz_a74f9e58195a | 古城公园 | old_city_central | supporting_stop | medium |
| pz_0b545bb1cf2a | 四川北路公园 | hongkou_literary | supporting_stop | medium |
| pz_b72e3b8998b3 | 多伦路文化名人街 | hongkou_literary | anchor | medium |
| pz_b4acff8f32fc | 甜爱路 | hongkou_literary | supporting_stop | medium |

完整来源、摘录、语义证据和 eligible roles 在 `_route_nodes.json` 与 candidate provenance。多伦路仅计独立公共街区体验，明确排除 p26 博物馆内部参观。甜爱路不继承邻近鲁迅公园的 parks 或四川北路的 shopping 标签。动态营业信息未核实时保留 unknown；公共道路/公园的物理稳定性与实时开放状态分开记录。

## 5. Existing Route Role Audit 与四区分布

22 个 existing POIs 全部逐个审核，原 production 身份不构成 anchor 理由。新旧节点使用相同 taxonomy，依据独立目的地价值、步行体验、可用证据与组合职责判断。现有 KB 简介、visit scope、visit profile 作为产品证据保存，明确不是本次外部事实核验。所有审核 medium/high，没有 low confidence 默认提升。

| Zone | anchor | supporting_stop | transition_stop | anchor_coverage_gap |
|---|---:|---:|---:|---|
| 武康 | 3 | 4 | 2 | false |
| 老城厢 | 7 | 2 | 0 | false |
| 虹口 | 4 | 5 | 0 | false |
| 西岸 | 5 | 6 | 2 | false |

Existing-only 分布依次为 2/4/2、7/1/0、3/3/0。具体 22 行见附录与 `_existing_role_audit.json`。没有为满足 anchor 要求而改角色；先用临时候选测试组合规则，区域回归通过后才在累计 candidate 中显式启用。Places in mind 不强行添加 anchor。

## 6. Coverage before → after

武康 art 0→1、museum_visit 1→2；保留原街道生活与建筑主题，不把工艺展馆虚构成非博物馆补点。老城厢 parks 0→1、history 8→9、old_city 2→3。虹口 parks 1→2、gardens 0→1、modern_china_history 1→2、street_scene 1→3、neighborhood_walk 2→4，增加公共空间与街道体验。

museum_visit 占比分别为 1/8→2/9、1/8→1/9、2/6→2/9；西岸仍 5/13。零覆盖标签继续保留，不能视为全部主题已经齐全。类别统计保留既有分类与新增规范分类，未为美化多样性改写旧 KB。

## 7. 四区 regression 与时长限制

三区各六类：主要主题、第二主题、非博物馆公共空间、新增覆盖、普通三小时、排除购物。检查至少三点、角色组合、negative preferences、区域隔离、相关性、重复/内部节点、预算与估算单段距离。接受阈值预设为至少 4/6；不能将少数困难请求误判为系统 blocker。

| Zone | 达标案例 | 说明 |
|---|---:|---|
| 武康 | 6/6 | 六类全部满足 |
| 老城厢 | 5/6 | 150 分钟非博物馆请求不足三点 |
| 虹口 | 5/6 | 150 分钟非博物馆请求不足三点 |
| 西岸 | 7/8 可行路线 | 另 1 例 art-only/no-museums 如期暴露 anchor 缺口；8/8 回归预期符合 |

补充无偏好 120/150/180 分钟 sweep：武康 3/4/5 点，老城厢 2/2/3 点，虹口 3/3/4 点，西岸 2/3/5 点。三区 7/9、四区 9/12 达到至少三点。老城厢 120 分钟不存在符合默认 visit mode、预算与角色的三点组合；150 分钟有预算可行三点组合，但当前排序/质量策略未选中。诊断组合不是推荐路线。西岸 120 分钟也有既有排序限制。

READY 不保证每个 120–180 分钟请求都有三点；role composition 与 minimum stop count 分开报告。没有放宽 relevance、虚构时长、拆点或抬角色来掩盖短路线。RouteEngine 核心策略本轮未改。详细输入和输出在 `_regression_report.json`、`duration_sweep.json`。

## 8. Zone expansion

初始边界建立后扩区次数均为 0。未出现至少两个明确高质量 POI 供给不足案例；失败归因于组合或评分/预算，不能据此向无关街区扩张。各区保存 `zone_expansion_recommended=false`、`expansion_passes=0`。张园、1933 属于名称走廊边缘的原节点，沿连续街区保留并在边界报告说明。

## 9. Cross-zone three-mode 与真实 provider smoke

四区 × Plan for me / Places in mind / Surprise me：**12/12 通过**。Plan 实际使用新增节点（西岸使用既有 p36–p43）；Surprise 满足组合；Places 保留两个明确非 anchor 选择，不自动补点。保持区域隔离且无重复计数。

三区各一次真实 DeepSeek intent 调用，共 **3 次**。解析均成功，但测试句未给正向兴趣，入口正确返回 `needs_clarification`。测试框架随后提供有记录的确定性兴趣答案，经原 clarification → adapter → RouteEngine 完成路线，均为 `success_with_fixture_clarification`。这不是三例无需澄清的端到端成功；没有追加模型调用。原始 intent、provider usage、澄清答案和路线全部保存在 `_provider_smoke.json`。

## 10. Cost comparison

| 指标 | 武康 | 老城厢 | 虹口 |
|---|---:|---:|---:|
| Raw provider records | 303 | 524 | 320 |
| Prefilter survivors | 3 | 2 | 3 |
| 当前有效 enriched nodes | 1 | 1 | 3 |
| 历史 enrichment API calls | 5 | 4 | 4 |
| Retry calls | 2 | 2 | 1 |
| Semantic validation failure attempts | 3 | 3 | 0 |
| 最近离线回放 cache hits | 3 | 1 | 3 |
| Accepted | 1 | 1 | 3 |
| Deferred | 61 | 192 | 114 |
| Rejected | 223 | 294 | 182 |
| Existing audits / 额外调用 | 8 / 0 | 8 / 0 | 6 / 0 |

合计 13 次 enrichment + 3 次 NLP smoke = **16 次实际 DeepSeek 调用**；最近离线重放零新增调用。每稳定节点累计最多两次，包含换证据和恢复执行。Raw、归一化节点与 early reject 口径不同，disposition 不应与 raw 直接加总。

West Bund 历史 `semantic/west_bund_enrichment_run.json` 记录 158 attempts、929709 tokens；本轮三区仅 13 semantic attempts。采集规模、补证和产出不同，这是调用量对照，不是等量实验或金额节省承诺。Amap/OSM/网页不是 DeepSeek calls，不虚构其货币成本。早期少数失败 attempt 缺完整 usage，未声称精确 token 总账。

## 11. Full tests 与保护检查

`python -m scripts.verify_all_zones`：**352 tests，0 failures，0 errors，0 skipped，11.342s，OK**。包括旧数据/路线/入口测试、合法边界、22 个显式审核、父子合并、主体证据限制、两次调用上限、稳定 ID、四区模式及默认 production 选择。

`full_test_report.json` 保存代码、tests 与 candidate 指纹；finalizer 只有当前指纹测试通过、三个 smoke 以及跨区回归通过才输出 READY。完整日志为 `full_test_output.txt`。

保护 SHA-256：

- production：`6585b3baf653ae89cc6a1e3c5fc10140bdd801fb298d92c392381d0b5fc17513`
- 原 candidate：`dc30a2933786b2c339a1b1f10ddfbf5f0025b502894f1e376232287799c00d2c`

两文件与开始时一致，全部原 ID 保留。西岸 13 个 POI 对象逐项完全一致，含 p36–p43；没有重做 discovery/enrichment 或边界。新 KB 必须显式选择，默认 production 仍为 27 点。

## 12. Remaining human-review items

武康 0、老城厢 1、虹口 0，均 ≤5。唯一候选是 **人民公园**：位于边界审核带并有官方证据，需要产品判断是否纳入；当前 defer、不计 route node。其他证据不足、预算用尽或普通 ambiguity 已 defer，未阻塞流程。

另有遗留坐标核验事项：p7 新天地旧代表点与高德对象约差 650m，p9 张园约 360m，p13 武康大楼旧点疑偏北。本轮未静默修改旧坐标；均在边界/审核带内，未单独拉长边界补救。验收时需留意这些偏差对估算步行距离的影响。

## 13. Known limitations

- Amap 每词有页数上限，部分查询明确记录 truncated；不是上海 POI 全量抓取。
- 个别 Xuhui 页过大，两个权威摘录使用标明来源的网页索引 fallback，不声称本次完整抓取；失败均留档。
- 部分英文名没有可靠来源，保留中文 fallback；实时开放未知，道路为代表坐标，不是真实步行图。
- 边界是产品近似 polygon；GCJ-02 检查验证数值及来源约定，不能靠经纬度数学证明坐标基准。
- Existing 角色审核基于保留的 KB 产品证据，不表示 22 个地点都完成本轮独立网页核验。
- 短路线、纯艺术非博物馆 anchor 限制如第 7 节所列。可人工验收不等于全部请求质量保证。

## 14. Files modified / artifacts

- 通用模块：`src/poi_pipeline/{zone_config,geometry,zone_collection,prefilter,role_audit,zone_semantic,subject_validation,zone_candidate_kb,zone_regression}.py`。
- 兼容泛化：boundary、normalization、deduplication、source adapters、HTTP、identity、coverage；显式选择 `src/kb_selection.py`。
- CLI：`scripts/run_poi_pipeline.py`、`collect_configured_zone.py`、`finalize_all_zones.py`、`verify_all_zones.py`；边界/证据及角色构建脚本。
- 配置审核：`zone_configs.json`、`existing_role_decisions.json`、`authority_excerpt_fallbacks.json`。
- 测试：`tests/test_zone_coverage.py`、`tests/test_phase2_5de.py`。
- 最终 `data/pois_phase2_5_all_zones_candidate.json`；阶段证据、成本、审核和回归在 `data/poi_pipeline/all_zones/`。

## 15. Exact CLI

在 `shanghai_trace_agent` 下执行，以下离线复用证据，不新增模型调用：

```powershell
python -m scripts.run_poi_pipeline --zone all
python -m scripts.verify_all_zones
python tools/demos/route_entry_demo.py --kb phase2_5_all_zones_candidate --list-places
python tools/demos/route_entry_demo.py --kb phase2_5_all_zones_candidate
```

单区同一入口：`python -m scripts.run_poi_pipeline --zone wukang_fuxing_xujiahui`。默认从原 candidate 开始；累计升级用 `--zone all` 或明确 `--input`，避免丢前一区成果。

维护时需新采集才用 `--live --recollect`（需 provider key，历史两次预算仍有效）；`python -m scripts.finalize_all_zones --live-smoke` 复用已存 smoke，不重复付费。不要直接用边界构建脚本覆盖已补证配置；调整应审查差异并重验覆盖。

任务在 candidate 与报告处停止；未覆盖 production，未开始 Phase 3、前端或真实地图 routing。

## 附录：22 个 existing POIs 逐点审核

表格从保存的审核 JSON 生成；eligible roles 均为审核 primary role，无隐含 anchor fallback。

### wukang_fuxing_xujiahui

| poi_id | name | primary_role | eligible_roles | confidence | role_reason |
|---|---|---|---|---|---|
| p2 | 永康路与嘉善路口 | transition_stop | transition_stop | medium | 街口的核心体验是街景与日常活动观察；现有访问范围仅短时公共空间观察，主要连接衡复街道节点，不足以独立承担目的地主题。 |
| p11 | 建业里 | supporting_stop | supporting_stop | medium | 门、弄堂和天井构成明确的住宅空间观察体验，值得主动绕入；现有短时外观范围不支持作为整条路线核心，避免把酒店内部当作可自由参观空间。 |
| p12 | 陕南邨 | transition_stop | transition_stop | medium | 既有体验限定于入口与立面细节，短暂停留提供街道连续性；没有更大独立访问范围的证据，不承担核心目的地。 |
| p13 | 武康大楼 | supporting_stop | supporting_stop | medium | 船形转角立面与路口形态提供独立建筑观察价值；既有范围是短时外观观察，没有把知名度转换为主题承担能力，故不列anchor。 |
| p21 | 上海宋庆龄故居纪念馆 | anchor | anchor | high | 既有来源支持人物长期生活及国务活动住所，完整参访可持续展开人物、近现代史与居住空间体验；适合作为明确目的地组织周边路线。 |
| p32 | 徐家汇天主堂 | anchor | anchor | medium | 用户确认的教堂建筑外观及可选深入参访，提供完整宗教建筑与徐家汇文化主题观察；即使入内未知仍有明确目的地体验，但不保证当前开放。 |
| p33 | 徐家汇书院 | supporting_stop | supporting_stop | medium | 用户确认的短时入内与公共阅读空间观察有独立文化体验，可补充徐家汇建筑主题；当前证据不支持将其当作路线的主要目的地。 |
| p35 | 徐家汇商圈 | supporting_stop | supporting_stop | medium | 既有范围明确是多栋商业空间及其间公共空间的区域观察，有整体城市生活体验；并非普通商铺，但默认短时商圈观察不承担文化路线核心。 |

### old_city_central

| poi_id | name | primary_role | eligible_roles | confidence | role_reason |
|---|---|---|---|---|---|
| p7 | 新天地北里（石库门街区） | anchor | anchor | medium | 石库门街巷肌理与商业再利用形成可独立持续探索的整体街区，可用完整访问范围承担城市更新主题；不是因购物或production身份判定。 |
| p9 | 张园 | anchor | anchor | medium | 既有完整历史建筑群保存与重新使用的观察体验具有独立目的地范围，能围绕保护和再利用组织主题；依赖街区公共范围，非入店购物。 |
| p14 | 外滩·陈毅广场 | anchor | anchor | medium | 既有外滩节点同时涵盖临江历史建筑界面、河流与对岸天际线的对照观察，可独立展开上海历史与现代城市主题；不再拆广场和雕像为新站。 |
| p15 | 豫园 | anchor | anchor | medium | 用户确认的街区游览以及可选完整园林参访，分别具有持续探索范围；能承担老城商业与园林主题，明确walk_stop不含购票园林。 |
| p20 | 上海城隍庙 | anchor | anchor | high | 官方支持的道教宫观及完整参访范围可以独立阐释城隍信仰与传统城市，具有专门宗教文化目的地价值；与周边商城观察区分。 |
| p23 | 思南公馆 | supporting_stop | supporting_stop | high | 历史住宅建筑群与保护再利用提供独立街区体验，值得主动加入；在此产品的默认短时外观范围内主要补充周边历史和更新主题。 |
| p24 | 中共一大纪念馆 | anchor | anchor | high | 既有官方支持的纪念馆完整参访可以持续展开政治史与石库门城市空间关系，具备独立主目的地价值；外观模式不改变审定角色。 |
| p34 | 南京路步行街 | anchor | anchor | medium | 用户明确确认核心步行路段作为完整目的地，持续的商业建筑和街道观察能够承担城市商业史主题；不以普通商店数量增加路线站点。 |

### hongkou_literary

| poi_id | name | primary_role | eligible_roles | confidence | role_reason |
|---|---|---|---|---|---|
| p4 | 鲁迅故居 | anchor | anchor | medium | 故居作为文学人物具体生活空间，结合既有完整参访范围可承担鲁迅文学主题；周边街巷作为理解背景，不将每个内部居所再拆站。 |
| p10 | 今潮8弄 | supporting_stop | supporting_stop | medium | 旧弄堂与新文化功能并置，提供独立再利用观察体验，可连接四川北路其他目的地；现有证据不足以将其设为全路线核心。 |
| p16 | 鲁迅公园 | anchor | anchor | medium | 既有完整公园参访范围支持持续公共生活观察、步行与文学背景体验，能独立承担社区公园主题；内部纪念设施不重复计站。 |
| p25 | 1927·鲁迅与内山纪念书局 | supporting_stop | supporting_stop | high | 旧址阅读和文化交流网络有具体独立体验，可有目的地补充鲁迅主题；与故居和街区相辅，不凭书店类别或历史名气升级anchor。 |
| p26 | 中国左翼作家联盟会址纪念馆 | supporting_stop | supporting_stop | high | 官方支持的文学组织旧址和完整短时参访能解释作家网络，适合文学路线重点补充；现有资料支持专题站而非一般路线核心。 |
| p27 | 1933老场坊 | anchor | anchor | high | 原工业建筑的坡道、廊桥与空间流线构成可持续独立探索的完整建筑体验，能承担工业空间再利用主题；内部商户和展厅不独立增站。 |
