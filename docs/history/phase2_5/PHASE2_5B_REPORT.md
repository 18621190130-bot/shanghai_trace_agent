# PHASE 2.5B REPORT

状态：Evidence-Grounded Semantic Enrichment 完成，等待人工验收。accept 仅代表建议审核；没有正式入库。

Phase 2.5A 原始 canonical：**61**；用户指定合并后：**58**。
语义校验成功：**55**；失败：**3**；重试候选：**46**。
其中 **18** 条只保留有证据的标签子集；模型不受支持的标签提议被逐项拒绝，原提议与原因留存，解释理由需人工协调。它们不会成为 accept。
Recommended Accept：**0**；Needs Review：**43**；Reject：**15**。

## 用户指定合并

- **西岸艺术中心（含A馆）**：合并 3 条 canonical；保留每个成员与原始证据。代表坐标沿用主场馆，不求平均、不生成新坐标。
- **西岸穹顶艺术中心（含北广场）**：合并 2 条 canonical；保留每个成员与原始证据。代表坐标沿用主场馆，不求平均、不生成新坐标。

这是路线节点范围合并：北广场与穹顶不是同一建筑；场馆室内访问与广场短暂停留仍需分清。B1/N/D 馆没有自动并入。

## 方法与事实边界

- 复用 DeepSeekLLMClient、原 JSON Schema validator 与现有 taxonomy。Intent 默认 1200 token 不变；本任务单独使用 3600 token。
- 标签、类别引用细粒度 evidence IDs；标签校验先于 coverage gain。LLM 没有收到 coverage 数值，prompt 明确说明 coverage gaps are NOT evidence。
- 坐标不在 LLM 输出 schema 中；程序校验并继承已选来源坐标。summary/culture_bridge 及敏感事实槽均为证据原文摘录，解释性文字单独保留为草稿。
- 解释理由仍需要人工核实：确定性校验可验证结构、引用、保守证据门槛和事实摘录，不能证明所有自然语言推理都正确。
- visit_profile 为 product_planning_estimate；没有声称实际平均停留时长或已验证当前营业。
- 距离与空间空白用 Haversine 近似，不是真实步行连通性。source confidence 与 semantic confidence 分开。
- 重复 production 地点作为新增候选拒绝；同名且邻近的油罐 OSM 子对象作为重复路线节点提议拒绝，不等于断言各油罐是同一建筑。其他可能重复、嵌套或无坐标地点保留 review。

## Coverage：before → proposed after

仅叠加 Recommended Accept；Needs Review / Reject 不计入 proposed after。数字不代表写入生产。

### interest_tags

| Tag | Before | Proposed after |
| --- | ---: | ---: |
| history | 0 | 0 |
| architecture | 4 | 4 |
| local_life | 0 | 0 |
| literature | 0 | 0 |
| art | 4 | 4 |
| industrial_heritage | 4 | 4 |
| waterfront | 4 | 4 |
| religion | 0 | 0 |
| parks | 0 | 0 |
| modern_city | 1 | 1 |
| modern_china_history | 0 | 0 |
| music | 0 | 0 |
| gardens | 0 | 0 |
| shopping_lifestyle | 1 | 1 |

### experience_tags

| Tag | Before | Proposed after |
| --- | ---: | ---: |
| iconic_landmark | 0 | 0 |
| neighborhood_walk | 0 | 0 |
| street_scene | 0 | 0 |
| local_atmosphere | 0 | 0 |
| museum_visit | 4 | 4 |
| photogenic | 4 | 4 |
| quiet_walk | 0 | 0 |
| adaptive_reuse | 4 | 4 |
| riverside_walk | 4 | 4 |
| bookish | 0 | 0 |
| social_observation | 0 | 0 |
| architecture_detail | 1 | 1 |
| shopping_leisure | 1 | 1 |

### culture_tags

| Tag | Before | Proposed after |
| --- | ---: | ---: |
| old_city | 0 | 0 |
| shikumen | 0 | 0 |
| lane_life | 0 | 0 |
| modern_shanghai | 5 | 5 |
| literary_shanghai | 0 | 0 |
| religious_culture | 0 | 0 |
| sino_foreign_exchange | 0 | 0 |
| political_history | 0 | 0 |
| industrial_transformation | 5 | 5 |
| urban_renewal | 5 | 5 |
| garden_culture | 0 | 0 |
| public_life | 0 | 0 |
| music_culture | 0 | 0 |

## Proposed route-role distribution

| Role | Accept + Review | Accept only |
| --- | ---: | ---: |
| anchor | 6 | 0 |
| supporting_stop | 22 | 0 |
| transition_stop | 14 | 0 |

另有 1 条非拒绝候选角色尚未解决，不计入上表；如显示 supporting_stop，明确只是低置信审核占位。各候选的三种角色解释、时长与邻近节点见 review JSON。

## Non-museum art

缺少 museum_visit 标签不足以证明是非博物馆艺术。此处进一步限于 public_art/public_space/park/architecture/heritage 类别提议，仍待人工核实。

- 上海油罐艺术中心（review）：art 有引用，未赋 museum_visit；仍需检查对应证据与体验范围。
- 油罐艺术中心（reject）：art 有引用，未赋 museum_visit；仍需检查对应证据与体验范围。
- 油罐艺术中心（reject）：art 有引用，未赋 museum_visit；仍需检查对应证据与体验范围。
- 油罐艺术中心（reject）：art 有引用，未赋 museum_visit；仍需检查对应证据与体验范围。
- 油罐艺术中心（review）：art 有引用，未赋 museum_visit；仍需检查对应证据与体验范围。
- 塔吊广场（review）：art 有引用，未赋 museum_visit；仍需检查对应证据与体验范围。
- 无尽影院（review）：art 有引用，未赋 museum_visit；仍需检查对应证据与体验范围。
- 油罐艺术中心（reject）：art 有引用，未赋 museum_visit；仍需检查对应证据与体验范围。
- 油罐艺术中心（reject）：art 有引用，未赋 museum_visit；仍需检查对应证据与体验范围。

## Recommended Accept

| Name | Category / Role | Tags (interest; experience; culture) | Confidence source / semantic | Gain | Reason |
| --- | --- | --- | --- | ---: | --- |

## Needs Review

| Name | Category / Role | Tags (interest; experience; culture) | Confidence source / semantic | Gain | Reason |
| --- | --- | --- | --- | ---: | --- |
| FISEHOOD极限运动公园 | sports_space / transition_stop | —; —; — | medium / low | 0 | low_semantic_confidence; stability_unknown; no_evidenced_interest_or_experience_tag; low_role_confidence; boundary_or_location_needs_review |
| GATE M 西岸凤巢 | commercial_complex / supporting_stop | shopping_lifestyle; shopping_leisure; — | medium / medium | 1.0 | stability_unknown |
| 龙美术馆(西岸馆) | unknown / supporting_stop | —; —; — | medium / low | 0 | enrichment_failed_not_a_negative_place_verdict; missing_coordinates; boundary_or_location_needs_review; possible_duplicate_or_nested_identity_requires_human_linking |
| 龙华码头 | public_space / transition_stop | waterfront; —; — | medium / low | 0.2 | low_semantic_confidence; stability_unknown; low_role_confidence; boundary_or_location_needs_review |
| 徐汇油罐艺术公园 | public_space / supporting_stop | parks; —; — | medium / low | 1.0 | low_semantic_confidence; stability_unknown; low_role_confidence |
| 星美术馆 | cultural_venue / anchor | art, waterfront; museum_visit, riverside_walk; — | medium / medium | 0.8 | stability_unknown; missing_coordinates; boundary_or_location_needs_review; possible_duplicate_or_nested_identity_requires_human_linking |
| 西岸中环梯田广场 | public_space / transition_stop | —; —; — | medium / low | 0 | unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance; low_semantic_confidence; stability_unknown; no_evidenced_interest_or_experience_tag; low_role_confidence |
| 上海市滨江滑板公园 | park / supporting_stop | parks, waterfront; riverside_walk; — | medium / low | 1.4 | low_semantic_confidence; stability_unknown; low_role_confidence; boundary_or_location_needs_review; possible_duplicate_or_nested_identity_requires_human_linking |
| 西岸艺术中心N馆 | cultural_venue / supporting_stop | art; museum_visit; — | medium / medium | 0.4 | stability_unknown |
| 上海摄影艺术中心 | cultural_venue / supporting_stop | art, architecture; museum_visit, photogenic, architecture_detail; — | medium / medium | 1.3 | stability_unknown; missing_coordinates; boundary_or_location_needs_review |
| 上海油罐艺术中心 | public_art / anchor | art, industrial_heritage, architecture; adaptive_reuse, photogenic, architecture_detail; industrial_transformation, urban_renewal | medium / medium | 1.8334 | stability_unknown; missing_coordinates; boundary_or_location_needs_review; possible_duplicate_or_nested_identity_requires_human_linking |
| 滨江滑板公园 | public_space / supporting_stop | waterfront, parks; riverside_walk, social_observation, photogenic; public_life | medium / medium | 3.6 | stability_unknown; missing_coordinates; boundary_or_location_needs_review; possible_duplicate_or_nested_identity_requires_human_linking |
| 优秀历史建筑龙腾大道2555号 | heritage / transition_stop | history, architecture; architecture_detail; — | medium / low | 1.7 | low_semantic_confidence; stability_unknown; low_role_confidence |
| 西岸漩心 | museum / supporting_stop | art, architecture; museum_visit; — | medium / low | 0.6 | unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance; low_semantic_confidence; stability_unknown; low_role_confidence |
| 西岸美术馆 | museum / anchor | art, architecture, waterfront; museum_visit, architecture_detail, riverside_walk, photogenic; sino_foreign_exchange | medium / medium | 2.7 | unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance; missing_coordinates; boundary_or_location_needs_review; possible_duplicate_or_nested_identity_requires_human_linking |
| 西岸梦中心·梦工场 | unknown / transition_stop | —; —; — | medium / low | 0 | unresolved_category; low_semantic_confidence; stability_unknown; no_evidenced_interest_or_experience_tag; low_role_confidence; boundary_or_location_needs_review |
| 南浦站 | heritage / transition_stop | history; —; — | medium / low | 1.0 | low_semantic_confidence; stability_unknown; low_role_confidence; boundary_or_location_needs_review |
| 西岸艺术中心B1馆 | cultural_venue / supporting_stop | art; —; — | medium / low | 0.2 | low_semantic_confidence; stability_unknown; low_role_confidence |
| 徐汇滨江海事塔广场 | public_space / transition_stop | waterfront; riverside_walk; — | medium / low | 0.4 | low_semantic_confidence; stability_unknown; low_role_confidence |
| 龙美术馆 | museum / anchor | art; museum_visit; — | medium / medium | 0.4 | stability_unknown; possible_duplicate_or_nested_identity_requires_human_linking |
| 西岸大剧院 | performance_venue / supporting_stop | art; architecture_detail; — | medium / medium | 0.7 | unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance; stability_unknown; boundary_or_location_needs_review |
| 谷地花溪 | public_space / supporting_stop | waterfront, parks; riverside_walk; — | medium / medium | 1.4 | unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance; stability_unknown; missing_coordinates; boundary_or_location_needs_review |
| Shanghai Center of Photography | museum / supporting_stop | art; museum_visit; — | medium / medium | 0.4 | stability_unknown |
| 攀岩抱石区 | sports_space / transition_stop | —; —; — | medium / low | 0 | low_semantic_confidence; stability_unknown; no_evidenced_interest_or_experience_tag; low_role_confidence |
| 星扬公园 | public_space / transition_stop | parks; —; — | medium / low | 1.0 | low_semantic_confidence; stability_unknown; low_role_confidence |
| 油罐艺术中心 | public_art / anchor | art, industrial_heritage, architecture; adaptive_reuse, photogenic, architecture_detail; industrial_transformation, urban_renewal | medium / medium | 1.8334 | stability_unknown; missing_coordinates; boundary_or_location_needs_review; possible_duplicate_or_nested_identity_requires_human_linking |
| 岩时攀岩(Gate M西岸梦中心) | sports_space / transition_stop | —; —; — | medium / low | 0 | low_semantic_confidence; stability_unknown; no_evidenced_interest_or_experience_tag; low_role_confidence; boundary_or_location_needs_review |
| 塔吊广场 | public_space / transition_stop | waterfront, art; riverside_walk, photogenic; — | medium / low | 0.8 | low_semantic_confidence; stability_unknown; low_role_confidence; missing_coordinates; boundary_or_location_needs_review |
| 西岸运动公园 | park / supporting_stop | parks; —; — | medium / low | 1.0 | low_semantic_confidence; stability_unknown; low_role_confidence |
| 西岸中央公园 | public_space / transition_stop | parks; —; — | medium / low | 1.0 | low_semantic_confidence; stability_unknown; low_role_confidence; missing_coordinates; boundary_or_location_needs_review |
| 西岸艺术中心D馆 | cultural_venue / supporting_stop | art; —; — | medium / low | 0.2 | low_semantic_confidence; stability_unknown; low_role_confidence |
| 乐动力西岸活力谷 | sports_space / transition_stop | —; —; — | medium / low | 0 | low_semantic_confidence; stability_unknown; no_evidenced_interest_or_experience_tag; low_role_confidence; boundary_or_location_needs_review |
| 无尽影院 | public_art / supporting_stop | art; photogenic; — | medium / medium | 0.4 | stability_unknown |
| 徐汇跑道公园 | park / supporting_stop | parks; —; — | medium / low | 1.0 | low_semantic_confidence; stability_unknown; low_role_confidence; boundary_or_location_needs_review |
| 上海市滨江滑板公园 | park / supporting_stop | waterfront, parks; riverside_walk; — | medium / low | 1.4 | low_semantic_confidence; stability_unknown; low_role_confidence; possible_duplicate_or_nested_identity_requires_human_linking |
| 西岸国际会展中心(上海) | cultural_venue / supporting_stop | —; —; — | medium / low | 0 | unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance; low_semantic_confidence; stability_unknown; no_evidenced_interest_or_experience_tag; low_role_confidence |
| 玻璃宅 | public_art / supporting_stop | —; —; — | medium / low | 0 | unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance; low_semantic_confidence; stability_unknown; no_evidenced_interest_or_experience_tag; low_role_confidence |
| 瓦肆 VAS est | performance_venue / supporting_stop | art; —; — | medium / low | 0.2 | unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance; low_semantic_confidence; stability_unknown; low_role_confidence |
| 跑道公园 | public_space / supporting_stop | history, waterfront, modern_city; riverside_walk, adaptive_reuse, street_scene; urban_renewal, modern_shanghai | medium / low | 3.4334 | low_semantic_confidence; stability_unknown; low_role_confidence; missing_coordinates; boundary_or_location_needs_review |
| 北票码头塔吊 | public_art / supporting_stop | industrial_heritage, waterfront; riverside_walk; — | medium / medium | 0.6 | unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance; stability_unknown |
| 光启龙华港湾 | public_space / transition_stop | —; —; — | medium / low | 0 | unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance; low_semantic_confidence; stability_unknown; no_evidenced_interest_or_experience_tag; low_role_confidence |
| 西岸艺术中心（含A馆） | cultural_venue / anchor | art, industrial_heritage, architecture; adaptive_reuse, photogenic, architecture_detail; industrial_transformation, modern_shanghai | high / medium | 1.8334 | stability_unknown; user_grouped_node_visit_scope_needs_review |
| 西岸穹顶艺术中心（含北广场） | performance_venue / supporting_stop | art, architecture; architecture_detail; — | medium / medium | 0.9 | unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance; stability_unknown; user_grouped_node_visit_scope_needs_review |

## Reject

| Name | Category / Role | Tags (interest; experience; culture) | Confidence source / semantic | Gain | Reason |
| --- | --- | --- | --- | ---: | --- |
| 油罐艺术中心 | cultural_venue / supporting_stop | art, industrial_heritage; museum_visit; — | medium / low | 0.6 | duplicate_existing_production:p29; unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance; low_semantic_confidence; stability_unknown; possible_duplicate_or_nested_identity_requires_human_linking |
| 上海油罐艺术中心 | cultural_venue / anchor | art; museum_visit; — | medium / medium | 0.4 | duplicate_existing_production:p29; unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance; stability_unknown; possible_duplicate_or_nested_identity_requires_human_linking |
| 西岸美术馆x蓬皮杜中心 | museum / anchor | art; museum_visit; — | medium / medium | 0.4 | duplicate_existing_production:p28; stability_unknown |
| 龙美术馆(西岸馆) | museum / anchor | art; museum_visit; — | medium / medium | 0.4 | duplicate_existing_production:p5; stability_unknown; possible_duplicate_or_nested_identity_requires_human_linking |
| 油罐艺术中心 | public_art / supporting_stop | art, architecture; architecture_detail; — | medium / low | 0.9 | duplicate_existing_production:p29; unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance; low_semantic_confidence; stability_unknown; low_role_confidence; possible_duplicate_or_nested_identity_requires_human_linking |
| 油罐艺术中心 | public_art / supporting_stop | art, industrial_heritage; architecture_detail; — | medium / low | 0.9 | duplicate_existing_production:p29; unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance; low_semantic_confidence; stability_unknown; low_role_confidence; possible_duplicate_or_nested_identity_requires_human_linking |
| 油罐艺术中心 | public_art / supporting_stop | art, architecture; architecture_detail; — | medium / low | 0.9 | duplicate_existing_production:p29; unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance; low_semantic_confidence; stability_unknown; possible_duplicate_or_nested_identity_requires_human_linking |
| 油罐艺术中心 | unknown / supporting_stop | —; —; — | medium / low | 0 | duplicate_existing_production:p29; enrichment_failed_not_a_negative_place_verdict; possible_duplicate_or_nested_identity_requires_human_linking |
| 星美术馆 | public_art / supporting_stop | art; museum_visit; — | medium / low | 0.4 | duplicate_existing_production:p31; low_semantic_confidence; stability_unknown; low_role_confidence; boundary_or_location_needs_review; possible_duplicate_or_nested_identity_requires_human_linking |
| 油罐艺术中心 | unknown / supporting_stop | —; —; — | medium / low | 0 | duplicate_existing_production:p29; enrichment_failed_not_a_negative_place_verdict; possible_duplicate_or_nested_identity_requires_human_linking |
| 西岸美术馆 | museum / anchor | art; museum_visit; — | medium / medium | 0.4 | duplicate_existing_production:p28; stability_unknown; possible_duplicate_or_nested_identity_requires_human_linking |
| Gate M西岸梦中心 | commercial_complex / supporting_stop | shopping_lifestyle, modern_city; shopping_leisure; — | medium / medium | 1.5 | duplicate_existing_production:p30; stability_unknown; boundary_or_location_needs_review |
| 开心麻花大三角剧场(Gate M西岸梦中心) | performance_venue / supporting_stop | art; —; — | medium / low | 0.2 | no_evidenced_independent_or_connector_citywalk_value; low_semantic_confidence; stability_unknown; low_role_confidence; boundary_or_location_needs_review |
| 油罐艺术中心 | public_art / supporting_stop | art, industrial_heritage; architecture_detail; — | medium / low | 0.9 | duplicate_existing_production:p29; unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance; low_semantic_confidence; stability_unknown; low_role_confidence; possible_duplicate_or_nested_identity_requires_human_linking |
| 油罐艺术中心 | public_art / supporting_stop | art, industrial_heritage; architecture_detail; — | medium / low | 0.9 | duplicate_existing_production:p29; unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance; low_semantic_confidence; stability_unknown; low_role_confidence; possible_duplicate_or_nested_identity_requires_human_linking |

## Taxonomy extension candidates

无。

## Unresolved enrichment failures

- 龙美术馆(西岸馆)：unsupported factual field former_functions；未输出成功语义结果。
- 油罐艺术中心：anchor requires high independent destination value；未输出成功语义结果。
- 油罐艺术中心：anchor requires high independent destination value；未输出成功语义结果。

## API / 缓存 / 测试

本次执行 API 调用：0；缓存命中：58；历史实际尝试次数：158。
API/校验失败类型：`{'semantic_validation_error': 99}`。供应商返回 token usage 汇总：`{'prompt_tokens': 814478, 'completion_tokens': 115231, 'total_tokens': 929709, 'prompt_cache_hit_tokens': 424448, 'prompt_cache_miss_tokens': 390030}`。

单元测试使用 Mock DeepSeek 与 fixture evidence；完整 unittest 命令及结果见 run metadata 的 test_result。
测试结果：259 tests passed; all automated tests offline; no live Route Engine run。没有运行 live Route Engine 回归或路线导出。
production pois.json SHA256：`6585b3baf653ae89cc6a1e3c5fc10140bdd801fb298d92c392381d0b5fc17513`；保持不变：True。

## Files created / modified

- `src/llm_client.py`：可选 max_tokens 参数与安全的 usage metadata；默认调用行为不变。
- `src/poi_pipeline/semantic/`：preparation、schema、validation、enricher、admission、reporting。
- `scripts/enrich_west_bund.py`；`tests/test_poi_semantic.py`；`docs/phases/PHASE2_5B.md`；README 阶段入口。
- `data/poi_pipeline/semantic/`：三个请求的数据集、prepared candidates/evidence、merge manifest、run metadata 与独立 enrichment cache。
- `PHASE2_5B_REPORT.md`：本报告。Phase 2.5A canonical/evidence 文件保持原样。

## 最值得人工审核的 15–25 个 POI

优先列出用户指定合并节点，再按已验证标签的 coverage gain 与空间空白排序；只排序，不反向改标签或角色。

| Name | Decision | Role | Priority | 核查重点 |
| --- | --- | --- | ---: | --- |
| 西岸穹顶艺术中心（含北广场） | review | supporting_stop | 1.9 | unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance; stability_unknown; user_grouped_node_visit_scope_needs_review |
| 西岸艺术中心（含A馆） | review | anchor | 1.8334 | stability_unknown; user_grouped_node_visit_scope_needs_review |
| 滨江滑板公园 | review | supporting_stop | 3.6 | stability_unknown; missing_coordinates; boundary_or_location_needs_review; possible_duplicate_or_nested_identity_requires_human_linking |
| 跑道公园 | review | supporting_stop | 3.4334 | low_semantic_confidence; stability_unknown; low_role_confidence; missing_coordinates; boundary_or_location_needs_review |
| 西岸美术馆 | review | anchor | 2.7 | unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance; missing_coordinates; boundary_or_location_needs_review; possible_duplicate_or_nested_identity_requires_human_linking |
| 上海市滨江滑板公园 | review | supporting_stop | 2.4 | low_semantic_confidence; stability_unknown; low_role_confidence; boundary_or_location_needs_review; possible_duplicate_or_nested_identity_requires_human_linking |
| 上海市滨江滑板公园 | review | supporting_stop | 2.4 | low_semantic_confidence; stability_unknown; low_role_confidence; possible_duplicate_or_nested_identity_requires_human_linking |
| 西岸运动公园 | review | supporting_stop | 2.0 | low_semantic_confidence; stability_unknown; low_role_confidence |
| 上海油罐艺术中心 | review | anchor | 1.8334 | stability_unknown; missing_coordinates; boundary_or_location_needs_review; possible_duplicate_or_nested_identity_requires_human_linking |
| 油罐艺术中心 | review | anchor | 1.8334 | stability_unknown; missing_coordinates; boundary_or_location_needs_review; possible_duplicate_or_nested_identity_requires_human_linking |
| 优秀历史建筑龙腾大道2555号 | review | transition_stop | 1.7 | low_semantic_confidence; stability_unknown; low_role_confidence |
| 西岸大剧院 | review | supporting_stop | 1.7 | unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance; stability_unknown; boundary_or_location_needs_review |
| 徐汇滨江海事塔广场 | review | transition_stop | 1.4 | low_semantic_confidence; stability_unknown; low_role_confidence |
| 谷地花溪 | review | supporting_stop | 1.4 | unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance; stability_unknown; missing_coordinates; boundary_or_location_needs_review |
| 上海摄影艺术中心 | review | supporting_stop | 1.3 | stability_unknown; missing_coordinates; boundary_or_location_needs_review |
| GATE M 西岸凤巢 | review | supporting_stop | 1.0 | stability_unknown |
| 徐汇油罐艺术公园 | review | supporting_stop | 1.0 | low_semantic_confidence; stability_unknown; low_role_confidence |
| 西岸中环梯田广场 | review | transition_stop | 1 | unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance; low_semantic_confidence; stability_unknown; no_evidenced_interest_or_experience_tag; low_role_confidence |
| 南浦站 | review | transition_stop | 1.0 | low_semantic_confidence; stability_unknown; low_role_confidence; boundary_or_location_needs_review |
| 星扬公园 | review | transition_stop | 1.0 | low_semantic_confidence; stability_unknown; low_role_confidence |
| 西岸中央公园 | review | transition_stop | 1.0 | low_semantic_confidence; stability_unknown; low_role_confidence; missing_coordinates; boundary_or_location_needs_review |
| 徐汇跑道公园 | review | supporting_stop | 1.0 | low_semantic_confidence; stability_unknown; low_role_confidence; boundary_or_location_needs_review |
| 光启龙华港湾 | review | transition_stop | 1 | unsupported_tag_proposals_rejected; reconcile_interpretive_reasons_before_acceptance; low_semantic_confidence; stability_unknown; no_evidenced_interest_or_experience_tag; low_role_confidence |
| 星美术馆 | review | anchor | 0.8 | stability_unknown; missing_coordinates; boundary_or_location_needs_review; possible_duplicate_or_nested_identity_requires_human_linking |
| 塔吊广场 | review | transition_stop | 0.8 | low_semantic_confidence; stability_unknown; low_role_confidence; missing_coordinates; boundary_or_location_needs_review |

STOP：等待人工验收。未覆盖 pois.json，未修改 route composition，未调用真实 Route Engine 验收流程。
