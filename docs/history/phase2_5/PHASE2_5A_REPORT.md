# PHASE 2.5A REPORT

日期：2026-10-04（Asia/Shanghai）。状态：架构、source adapters、真实采集和离线验证已完成；等待人工验收。停止在 EvidenceBundle，不进入 Phase 2.5B。

## 1. Existing West Bund baseline

实际读取生产 `data/pois.json`，通过 `POIRepository` 解析，West Bund 共 **5** 个 POI：龙美术馆（西岸馆）、西岸美术馆、上海油罐艺术中心、Gate M 西岸梦中心、星美术馆。全库仍为 27 个 POI、4 个 walk zone。

museum_visit 为 **4/5（80%）**；这四处都支持 walk_stop，因此此指标表示标签依赖，不等于必须购票或进入室内。GCJ-02 基线范围（南、西、北、东）：`[31.16119, 121.463841, 31.18786, 121.470412]`；无缺失坐标。

## 2. Current tag coverage

### interest_tags

| Tag | Count |
| --- | ---: |
| history | 0 |
| architecture | 4 |
| local_life | 0 |
| literature | 0 |
| art | 4 |
| industrial_heritage | 4 |
| waterfront | 4 |
| religion | 0 |
| parks | 0 |
| modern_city | 1 |
| modern_china_history | 0 |
| music | 0 |
| gardens | 0 |
| shopping_lifestyle | 1 |

零覆盖：history, local_life, literature, religion, parks, modern_china_history, music, gardens。
低覆盖（出现 1 次）：modern_city, shopping_lifestyle。

### experience_tags

| Tag | Count |
| --- | ---: |
| iconic_landmark | 0 |
| neighborhood_walk | 0 |
| street_scene | 0 |
| local_atmosphere | 0 |
| museum_visit | 4 |
| photogenic | 4 |
| quiet_walk | 0 |
| adaptive_reuse | 4 |
| riverside_walk | 4 |
| bookish | 0 |
| social_observation | 0 |
| architecture_detail | 1 |
| shopping_leisure | 1 |

零覆盖：iconic_landmark, neighborhood_walk, street_scene, local_atmosphere, quiet_walk, bookish, social_observation。
低覆盖（出现 1 次）：architecture_detail, shopping_leisure。

### culture_tags

| Tag | Count |
| --- | ---: |
| old_city | 0 |
| shikumen | 0 |
| lane_life | 0 |
| modern_shanghai | 5 |
| literary_shanghai | 0 |
| religious_culture | 0 |
| sino_foreign_exchange | 0 |
| political_history | 0 |
| industrial_transformation | 5 |
| urban_renewal | 5 |
| garden_culture | 0 |
| public_life | 0 |
| music_culture | 0 |

零覆盖：old_city, shikumen, lane_life, literary_shanghai, religious_culture, sino_foreign_exchange, political_history, garden_culture, public_life, music_culture。
低覆盖（出现 1 次）：无。

三个文化标签 `industrial_transformation`、`urban_renewal`、`modern_shanghai` 都出现 5 次，成员完全重合。architecture/art/museum_visit 的成员也完全重合。完整共现对见 baseline JSON；使用 Jaccard ≥0.8 且共同出现至少 2 次，不将小样本共现解释为统计因果。

## 3. New pipeline architecture

`External Sources → RawCandidate → Normalization → Boundary audit → Deduplication → CanonicalCandidate → EvidenceBundle`。采用独立 dataclass，与生产 POI schema 隔离。保留 merged_source_records、逐字段来源、证据类别及缺失项，不生成最终三类标签。

## 4. Data sources implemented

- Amap：8 组关键词 + nearby 查询，分页最多 3 页/查询；detail/geocode 方法可用，本轮未额外调用。仅从环境变量取 key。
- OSM：Overpass 区域查询，覆盖艺术、历史、公共空间与滨水相关 features；未使用 Nominatim。
- Official：West Bund 项目目录发现 + 官方详情页 + 上海市文旅局页面短摘录；政府页面一个请求失败，其他来源继续。
- 所有 pipeline 请求共用缓存、超时、重试、退避、限速、脱敏与错误隔离；只缓存官方页面的简短摘录和链接元数据。

## 5. Actual raw candidate count

本次来源输出 **271** 条 provider records；排除 **145** 条非徐汇、普通服务/店铺、停车充电、临时打卡等发现噪声后，raw JSON 保存 **126** 条。

其中 **60** 条明确在试点边界外，仍保留于 raw 与边界排除审计。进入去重的区域内/待核实 raw 为 **66** 条。超过 40–60 预期范围，没有按配额截断或补齐；所有计数口径均分开报告。

## 6. Deduplicated candidate count

**61** 条 canonical，边界内 **37** 条，**needs_review 24** 条。它们是未验收的候选记录，不代表 61 个已确认唯一、稳定、开放或适合路线的节点。

官方无坐标提及不依靠名字自动合并；OSM 油罐园区多个独立对象不强行合并。它们造成保守去重后的重复/嵌套残留，后续需人工核对。边界内也不等于适合正式入库。

## 7. Source coverage

| Source | Raw | Canonical with this source |
| --- | ---: | ---: |
| amap | 67 | 31 |
| osm | 47 | 23 |
| official | 9 | 9 |
| government | 3 | 3 |

Canonical 列按来源覆盖计数，多来源记录会重叠；不是可相加的独立候选数。

## 8. Errors / partial failures

- `partial_source_failure=true`：`https://www.shanghai.gov.cn/xuhui/index.html` 请求失败，未把页面搜索摘要伪装成已抓取证据。失败缓存保留安全 HTTP 状态/异常类型。
- 两个 Amap 查询达到分页上限：西岸公园关键词与 nearby；报告记录 `discovery_truncated`。本轮不是全量盘点。
- 官方记录无地图坐标时保留缺失和 needs_review；开放时间、通行、历史证据空缺均留在 EvidenceBundle.gaps。

## 9. Key assumptions

- 试点仅覆盖现有星美术馆—西岸梦中心簇的保守八顶点滨江走廊，不扩大为全徐汇滨江。多边形为试点近似边界；边缘两侧 150 米均需复核。
- WGS84 → GCJ-02 使用已有离线近似转换；OSM way/relation 的 center 不是入口点。
- 原始地图类别与 OSM tags 只作来源证据；没有修改 taxonomy。
- 普通店铺/服务/临时打卡点只做发现范围排除；没有做最终候选价值筛选。攀岩空间、场馆分馆、园区与内部对象是否有独立路线价值仍待验收。
- 官方证据尚未全部与地图身份链接，历史页面也不证明当前营业状态。
- 来源优先级与坐标字段优先级分开；同名、近距离不单独构成合并条件。

## 10. Tests run and results

- 修改前：`python -m unittest discover -s tests -t . -q` → **214 tests, OK**。
- 修改后相同命令 → **235 tests, OK**（原有 214 + 新增 21）。新测试使用本地 fixture/mock，不访问互联网或 DeepSeek。
- 覆盖坐标/名称标准化、别名与地址去重、非传递合并、嵌套实体保护、边界、原始 provenance、部分失败、官方抽取、OSM center、缓存重放/完整性/脱敏、覆盖率与现有 POI 边界保护。
- `python scripts/collect_west_bund.py --live` 已实际请求来源；修复后的输出由真实响应缓存离线重放生成。
- 缓存与输出 39 个 JSON 扫描未发现当前 API Key（只输出布尔检查结果）。
- 生产 KB SHA256 前后一致：`6585b3baf653ae89cc6a1e3c5fc10140bdd801fb298d92c392381d0b5fc17513`。

## 11. Files created / modified

新增：

- `src/poi_pipeline/__init__.py`
- `src/poi_pipeline/boundary.py`
- `src/poi_pipeline/collection.py`
- `src/poi_pipeline/coverage.py`
- `src/poi_pipeline/deduplication.py`
- `src/poi_pipeline/discovery_scope.py`
- `src/poi_pipeline/evidence.py`
- `src/poi_pipeline/models.py`
- `src/poi_pipeline/normalization.py`
- `src/poi_pipeline/sources/__init__.py`
- `src/poi_pipeline/sources/amap_source.py`
- `src/poi_pipeline/sources/base.py`
- `src/poi_pipeline/sources/official_source.py`
- `src/poi_pipeline/sources/osm_source.py`
- `scripts/collect_west_bund.py`
- `tests/test_poi_pipeline.py`
- `docs/phases/PHASE2_5A.md`
- `PHASE2_5A_REPORT.md`
- `data/poi_pipeline/raw/west_bund_raw_candidates.json`
- `data/poi_pipeline/canonical/west_bund_canonical_candidates.json`
- `data/poi_pipeline/canonical/west_bund_evidence_bundles.json`
- `data/poi_pipeline/west_bund_baseline_report.json`
- `data/poi_pipeline/west_bund_collection_report.json`
- `data/poi_pipeline/cache/*.json`（34 个缓存文件，含历史发现请求和失败元数据）。

修改：`README.md`（增加本阶段入口）。现有 Route Engine、Intent、Clarification、Minimum Viable City Walk、taxonomy 和 production pois.json 未改动。

## 12. Commands to reproduce the collection

项目目录中执行：

```powershell
python scripts/collect_west_bund.py --live
python scripts/collect_west_bund.py
python scripts/collect_west_bund.py --live --retry-failed
python -m unittest discover -s tests -t . -q
```

第二条仅从缓存重放，无网络、无密钥要求。新快照可使用 `--live --output data/poi_pipeline/new_snapshot`；所有输出都是 staging 文件。环境变量已在当前进程可见，不记录具体值。

## Representative canonical candidates（25 条）

表中“边界内”仅为空间状态；“需核实”包括边缘或缺坐标。全部尚未验收入库。

| Name | Sources | Boundary | Candidate ID |
| --- | --- | --- | --- |
| 龙美术馆(西岸馆) | amap,osm | 边界内 | `wb_4d10e8e089d4b29b` |
| 西岸美术馆 | amap | 边界内 | `wb_c75021545eb8ab4b` |
| 上海油罐艺术中心 | amap,osm | 边界内 | `wb_391963dbf79f7d2a` |
| 西岸艺术中心 | amap,osm | 边界内 | `wb_fffb4fce772125fc` |
| 西岸艺术中心A馆 | amap | 边界内 | `wb_464c18668419c201` |
| 西岸穹顶艺术中心 | amap,osm | 边界内 | `wb_6711fedf4e2dbb17` |
| 西岸大剧院 | amap,osm | 需核实 | `wb_7ca7f91efb488c29` |
| Gate M西岸梦中心 | amap | 需核实 | `wb_cec508b088058505` |
| 上海市滨江滑板公园 | amap | 边界内 | `wb_e3c7d189b1207ada` |
| 徐汇滨江海事塔广场 | amap | 边界内 | `wb_72b583ec31ffce20` |
| 北票码头塔吊 | amap | 边界内 | `wb_fd436a54b9d249a2` |
| 光启龙华港湾 | amap | 边界内 | `wb_fedf89c7dfde83a8` |
| 优秀历史建筑龙腾大道2555号 | amap | 边界内 | `wb_325c03999db02641` |
| 玻璃宅 | amap | 边界内 | `wb_e4c848a74b49e650` |
| 星扬公园 | amap | 边界内 | `wb_aa87d61112f0c493` |
| 西岸穹顶北广场 | amap | 边界内 | `wb_cc94250299ef60fc` |
| 西岸中环梯田广场 | amap | 边界内 | `wb_17ae682bcceb4b2f` |
| 徐汇油罐艺术公园 | amap | 边界内 | `wb_131d04df1342ff37` |
| 西岸运动公园 | amap | 边界内 | `wb_c412dd6d5286929f` |
| 龙华码头 | amap | 需核实 | `wb_11d08a44ff039d07` |
| 无尽影院 | osm | 边界内 | `wb_d7d1677306fa4d92` |
| 星美术馆 | osm | 需核实 | `wb_b760ec28e10728b8` |
| 塔吊广场 | government | 需核实 | `wb_bfd5b11fdae241d1` |
| 谷地花溪 | government | 需核实 | `wb_8a0a2e8f5c9d990d` |
| 上海摄影艺术中心 | official | 需核实 | `wb_2433e40493d7a35f` |

STOP POINT：等待人工验收。未调用 DeepSeek enrichment，未进行正式入库，未开始 Phase 2.5B。
