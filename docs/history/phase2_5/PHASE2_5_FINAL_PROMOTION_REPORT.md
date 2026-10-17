# Phase 2.5 Final Promotion Report

## 1. Promotion source

`data\pois_phase2_5_diversity_candidate.json`，62节点，Phase2.5G READY_FOR_PRODUCTION_PROMOTION。源candidate保持不变。SHA-256：`8ff0bcac4bed8d023661f6a22dfdcb6e9dc86c4f008caa0412bf4d3453a000bb`。只应用最终明确人工删除，不重新产品筛选/enrichment。

## 2. 三项人工删除

| ID | Name | Reason |
| --- | --- | --- |
| pz_42efca09357d | 中国社会主义青年团中央机关旧址 | explicit_human_product_removal |
| pz_463c9b82ac1e | 东海大楼 | explicit_human_product_removal |
| pz_bc5155c245b0 | 四川北路街道图书馆（海伦路505号） | explicit_human_product_removal |

爱思儿童公园已在G阶段删除，没有重新加入。删除证据历史不物理清理。

## 3. Final 59 POIs

最终candidate和production逐字节一致：`data\pois_phase2_5_final_candidate.json` → `data/pois.json`。动态数组计数 **59**，全为route-selectable且counts_as_route_stop。Repository原schema通过。

稳定ID全部不变，仅10个保留对象的display_order因三项删除连续压缩。source/final逐对象diff在忽略display_order后完全相等，原相对顺序保持。授权例外仅展示编号；role、tags、坐标、visit_profile、content、alias、ID均未改。metadata总量/分区计数及新增ID列表按删除更新，promotion metadata记录授权与来源。

## 4. Zone counts

| Zone | Production count |
| --- | --- |
| wukang_fuxing_xujiahui | 17 |
| old_city_central | 15 |
| hongkou_literary | 14 |
| west_bund | 13 |

## 5. Role distributions

| Zone | Roles |
| --- | --- |
| wukang_fuxing_xujiahui | {'transition_stop': 3, 'supporting_stop': 10, 'anchor': 4} |
| old_city_central | {'anchor': 9, 'supporting_stop': 6} |
| hongkou_literary | {'anchor': 4, 'supporting_stop': 8, 'transition_stop': 2} |
| west_bund | {'anchor': 5, 'supporting_stop': 6, 'transition_stop': 2} |

角色冻结，未通过supporting→anchor或transition→supporting补composition。西岸13对象及p36–p43内容包括display_order均完全保留。

## 6. Production backup

`data\archive\pois_pre_phase2_5.json`完整保存原27节点内容。已有备份复用未覆盖，SHA-256：`6585b3baf653ae89cc6a1e3c5fc10140bdd801fb298d92c392381d0b5fc17513`。created_at/source file/phase记录于`data\archive\pois_pre_phase2_5.manifest.json`，与原production哈希一致。

## 7. Coordinate changes inherited from Phase 2.5

coordinate changes inherited from Phase 2.5 validated candidate；没有新geocode或恢复旧坐标。

```json
[
  {
    "poi_id": "p7",
    "name": "新天地北里（石库门街区）",
    "old_location": {
      "address_zh": "黄浦区太仓路181弄",
      "coordinate_system": "GCJ-02 approximate (from current project HTML)",
      "representative_lat": 31.2212,
      "representative_lng": 121.4679,
      "coordinate_note": "Legacy point reused as representative anchor; not the whole area's unique location or verified entry/exit."
    },
    "new_location": {
      "address_zh": "黄浦区太仓路181弄",
      "coordinate_system": "GCJ-02 approximate (from current project HTML)",
      "representative_lat": 31.220692,
      "representative_lng": 121.474751,
      "coordinate_note": "Phase 2.5F provider-identity-verified representative coordinate; not routed entrance."
    },
    "basis": "coordinate changes inherited from Phase 2.5 validated candidate; no new geocoding"
  },
  {
    "poi_id": "p9",
    "name": "张园",
    "old_location": {
      "address_zh": "静安区威海路588号",
      "coordinate_system": "GCJ-02 approximate (from current project HTML)",
      "representative_lat": 31.2286,
      "representative_lng": 121.4638,
      "coordinate_note": "Legacy point reused as representative anchor; not the whole area's unique location or verified entry/exit."
    },
    "new_location": {
      "address_zh": "静安区威海路588号",
      "coordinate_system": "GCJ-02 approximate (from current project HTML)",
      "representative_lat": 31.227971,
      "representative_lng": 121.460064,
      "coordinate_note": "Phase 2.5F provider-identity-verified representative coordinate; not routed entrance."
    },
    "basis": "coordinate changes inherited from Phase 2.5 validated candidate; no new geocoding"
  },
  {
    "poi_id": "p13",
    "name": "武康大楼",
    "old_location": {
      "address_zh": "徐汇区淮海中路1850号",
      "lat": 31.2108,
      "lng": 121.4472,
      "coordinate_system": "GCJ-02 approximate (from current project HTML)"
    },
    "new_location": {
      "address_zh": "徐汇区淮海中路1850号",
      "lat": 31.20443,
      "lng": 121.438278,
      "coordinate_system": "GCJ-02 approximate (from current project HTML)",
      "coordinate_note": "Phase 2.5F provider-identity-verified representative coordinate; not routed entrance."
    },
    "basis": "coordinate changes inherited from Phase 2.5 validated candidate; no new geocoding"
  }
]
```

## 8. Regression after deletion

| Zone | Case | G62 before | Production59 after | Stops | Composition | Negative preferences |
| --- | --- | --- | --- | --- | --- | --- |
| wukang_fuxing_xujiahui | core_1 | success | success | 5 | True | True |
| wukang_fuxing_xujiahui | core_2 | success | success | 5 | True | True |
| wukang_fuxing_xujiahui | non_museum | success | success | 4 | True | True |
| wukang_fuxing_xujiahui | new_coverage | success | success | 5 | True | True |
| wukang_fuxing_xujiahui | general_180 | success | success | 5 | True | True |
| wukang_fuxing_xujiahui | negative | success | success | 5 | True | True |
| wukang_fuxing_xujiahui | architecture_life | success | success | 5 | True | True |
| old_city_central | core_1 | success | success | 3 | True | True |
| old_city_central | core_2 | success | success | 3 | True | True |
| old_city_central | non_museum | success | success | 3 | True | True |
| old_city_central | new_coverage | success | success | 4 | True | True |
| old_city_central | general_180 | success | success | 4 | True | True |
| old_city_central | negative | success | success | 4 | True | True |
| old_city_central | history_street | success | success | 3 | True | True |
| old_city_central | old_city_life | insufficient_route | insufficient_route | 1 | False | True |
| old_city_central | architecture_neighborhood | success | success | 3 | True | True |
| hongkou_literary | core_1 | success | success | 5 | True | True |
| hongkou_literary | core_2 | success | success | 4 | True | True |
| hongkou_literary | non_museum | success | success | 3 | True | True |
| hongkou_literary | new_coverage | success | success | 5 | True | True |
| hongkou_literary | general_180 | success | success | 5 | True | True |
| hongkou_literary | negative | success | success | 5 | True | True |
| hongkou_literary | literature_neighborhood | success | success | 5 | True | True |

原三区18个核心case全部通过；G新增主题4/5通过。old_city_life仍不足，为明确接受的已有限制，没有此前成功case退化。

| Zone | Duration | Stops | Status | Composition |
| --- | --- | --- | --- | --- |
| wukang_fuxing_xujiahui | 120 | 4 | success | True |
| wukang_fuxing_xujiahui | 150 | 4 | success | True |
| wukang_fuxing_xujiahui | 180 | 5 | success | True |
| old_city_central | 120 | 2 | insufficient_route | True |
| old_city_central | 150 | 3 | success | True |
| old_city_central | 180 | 4 | success | True |
| hongkou_literary | 120 | 4 | success | True |
| hongkou_literary | 150 | 4 | success | True |
| hongkou_literary | 180 | 5 | success | True |

老城120分钟仍2站；150/180及其他两区检查正常。所有已成功的G时长fixture未退化。West Bund原8例保持状态，7成功+原art/no museums已知composition failure；其他三mode检查保持，13节点未变。每条路线校验预算、区内、偏好和相关候选，仍为approximate geometry。

## 9. Cross-zone three-mode result

| Zone | Mode | Status | Passed | Checks |
| --- | --- | --- | --- | --- |
| wukang_fuxing_xujiahui | plan_for_me | success | True | {'zone_isolation': True, 'no_fake_richness': True, 'exact_places': True, 'minimum_stops': True, 'composition': True, 'plan_uses_new_poi': True} |
| wukang_fuxing_xujiahui | surprise_me | success | True | {'zone_isolation': True, 'no_fake_richness': True, 'exact_places': True, 'minimum_stops': True, 'composition': True, 'plan_uses_new_poi': True} |
| wukang_fuxing_xujiahui | places_in_mind | success | True | {'zone_isolation': True, 'no_fake_richness': True, 'exact_places': True, 'minimum_stops': True, 'composition': True, 'plan_uses_new_poi': True} |
| old_city_central | plan_for_me | success | True | {'zone_isolation': True, 'no_fake_richness': True, 'exact_places': True, 'minimum_stops': True, 'composition': True, 'plan_uses_new_poi': True} |
| old_city_central | surprise_me | success | True | {'zone_isolation': True, 'no_fake_richness': True, 'exact_places': True, 'minimum_stops': True, 'composition': True, 'plan_uses_new_poi': True} |
| old_city_central | places_in_mind | success | True | {'zone_isolation': True, 'no_fake_richness': True, 'exact_places': True, 'minimum_stops': True, 'composition': True, 'plan_uses_new_poi': True} |
| hongkou_literary | plan_for_me | success | True | {'zone_isolation': True, 'no_fake_richness': True, 'exact_places': True, 'minimum_stops': True, 'composition': True, 'plan_uses_new_poi': True} |
| hongkou_literary | surprise_me | success | True | {'zone_isolation': True, 'no_fake_richness': True, 'exact_places': True, 'minimum_stops': True, 'composition': True, 'plan_uses_new_poi': True} |
| hongkou_literary | places_in_mind | success | True | {'zone_isolation': True, 'no_fake_richness': True, 'exact_places': True, 'minimum_stops': True, 'composition': True, 'plan_uses_new_poi': True} |
| west_bund | plan_for_me | success | True | {'zone_isolation': True, 'no_fake_richness': True, 'exact_places': True, 'minimum_stops': True, 'composition': True, 'plan_uses_new_poi': True} |
| west_bund | surprise_me | success | True | {'zone_isolation': True, 'no_fake_richness': True, 'exact_places': True, 'minimum_stops': True, 'composition': True, 'plan_uses_new_poi': True} |
| west_bund | places_in_mind | success | True | {'zone_isolation': True, 'no_fake_richness': True, 'exact_places': True, 'minimum_stops': True, 'composition': True, 'plan_uses_new_poi': True} |

12/12通过，post直接从data/pois.json加载；Plan使用正式POI；Surprise组成正常；Places不硬加anchor；无重复/不可选子节点，区隔正确。负偏好由三区negative/non_museum回归同时覆盖。

## 10. Full test result

推广前两套各379项通过；推广后最新两套各379项通过，0 failures / 0 errors。

```json
{
  "pre": {
    "successful": true,
    "runs": [
      {
        "command": "python -m unittest discover -s tests -t . -q",
        "exit_code": 0,
        "tests_run": 379,
        "output": "pre_tests_1.txt",
        "elapsed_seconds": 13.016
      },
      {
        "command": "python -m scripts.verify_all_zones",
        "exit_code": 0,
        "tests_run": 379,
        "output": "pre_tests_2.txt",
        "elapsed_seconds": 14.705
      }
    ],
    "completed_at": "2026-10-05T03:31:39.370355+00:00",
    "validation_fingerprint": "f0d4c67b138ea584bb29560d11e54abb8b43edf47159664cd5725201f132b04f"
  },
  "post": {
    "successful": true,
    "runs": [
      {
        "command": "python -m unittest discover -s tests -t . -q",
        "exit_code": 0,
        "tests_run": 379,
        "output": "post_tests_1.txt",
        "elapsed_seconds": 16.991
      },
      {
        "command": "python -m scripts.verify_all_zones",
        "exit_code": 0,
        "tests_run": 379,
        "output": "post_tests_2.txt",
        "elapsed_seconds": 18.041
      }
    ],
    "completed_at": "2026-10-05T03:34:37.257956+00:00",
    "validation_fingerprint": "4c4563f21fdb07b89371925aeec74a71d78fa22d8112f150c2c2cbf5b3d002e2"
  }
}
```

新增tests/test_phase2_5_promotion.py：final/count/四区/删除/保留对象/稳定ID/p36–p43/default selection与隐藏role/ID变更拒绝。历史Phase1/2与pipeline baseline断言绑定已保存27节点快照，生产默认行为有独立实际CLI/default测试。

推广后初次测试有3个历史fixture失败（旧库CLI窄偏好和西岸5节点计数），原日志保留于initial_post_tests_1/2.txt与initial_post_full_tests.json；修正为显式历史快照后全部通过。没有改算法或弱化原断言。窄偏好在G62与final59均返回composition_failure，核对见historical_narrow_preference_diagnostic.json，不是三项删除引发的回归。

## 11. Old → new production hash

Old：`6585b3baf653ae89cc6a1e3c5fc10140bdd801fb298d92c392381d0b5fc17513`

New：`6fe891c894995df9aaf9c1c8488d085178399e8cf6d22fe84a87c68e28018782`

Final candidate：`6fe891c894995df9aaf9c1c8488d085178399e8cf6d22fe84a87c68e28018782`。替换前临时文件同目录写入、flush/fsync并验hash，然后os.replace；没有先删除production。

## 12. Promotion manifest

`data\PHASE2_5_PROMOTION_MANIFEST.json`，status=PROMOTED_AND_FROZEN，phase=2.5。记录来源/最终候选/旧新production哈希、三项删除、动态count、zone counts、timestamp、backup、pre/post tests/regression、默认CLI、授权展示序号差异。promotion_timestamp：2026-10-05T03:32:29.691101+00:00。

## 13. Default CLI verification

| Command | Exit | KB | Count |
| --- | --- | --- | --- |
| python tools/demos/route_entry_demo.py --kb production --list-places | 0 | production | 59 |
| python tools/demos/route_entry_demo.py --list-places | 0 | production | 59 |
| python tools/demos/chat_demo.py --list-places | 0 | production | 59 |
| python tools/demos/route_entry_demo.py --mode surprise_me --start West Bund --minutes 180 --seed 42 --json | 0 | production | 59 |
| python tools/demos/route_entry_demo.py --mode plan_for_me --text I have three hours and want to see old architecture and local neighborhoods. --json | 0 | production | 59 |

5/5通过。显式production与不传--kb的两入口均显示production/59；默认Plan（离线fixture）和Surprise成功。chat_demo目录不调用provider。无新的DeepSeek调用或semantic token成本。

## 14. Known limitations

- old_city_life insufficient_route
- old_city default 120min may have two stops
- real-time opening/crowd/weather/tickets unknown
- representative coordinates are not actual entrances
- approximate walking geometry; no real Map Routing
- historical narrow local_life preference composition_failure present in both G62 and final59

当前closed与entity稳定分离。营业、预约、票务等未知不补造；后续Phase3可以接实时层，本次不扩POI、不更改roles或算法解决这些限制。

## 15. Files modified / created

- `data/pois.json`
- `data/pois_phase2_5_final_candidate.json`
- `data/archive/pois_pre_phase2_5.json`
- `data/archive/pois_pre_phase2_5.manifest.json`
- `data/PHASE2_5_PROMOTION_MANIFEST.json`
- `scripts/promote_phase2_5.py`
- `tests/helpers.py`
- `tests/test_phase2_5_promotion.py`
- `README.md`
- `docs/PHASE_MANIFEST.md`
- `docs/phases/PHASE2_5.md`
- `PHASE2_5_FINAL_PROMOTION_REPORT.md`
- `tests/test_repository.py`
- `tests/test_recommendation.py`
- `tests/test_route_engine.py`
- `tests/test_visit_calibration.py`
- `tests/test_phase2.py`
- `tests/test_phase2_quality.py`
- `tests/test_phase2_final_repair.py`
- `tests/test_phase2_unified_patch.py`
- `tests/test_phase2_repair.py`
- `tests/test_phase2_richness.py`
- `tests/test_poi_repair.py`
- `tests/test_zone_coverage.py`
- `tests/test_phase2_5c.py`
- `tests/test_phase2_5de.py`
- `tests/test_phase2_5g.py`
- `tests/test_cli.py`
- `tests/test_kb_selection_cli.py`
- `tests/test_poi_pipeline.py`

完整pre/post回归、duration/diversity诊断、test/CLI日志/object diff/gates在data/poi_pipeline/promotion。verify_all_zones更新旧pipeline测试报告，但所有历史candidate字节哈希保持不变。src全部冻结、未修改Route Engine scoring、RouteIntent、Clarification、Semantic Expansion、Minimum Viable City Walk或Route Composition。

## 16. Exact commands

```powershell
python -m scripts.promote_phase2_5 prepare
python -m scripts.promote_phase2_5 regress
python -m scripts.promote_phase2_5 test
python -m scripts.promote_phase2_5 promote
python -m scripts.promote_phase2_5 post-regress
python -m scripts.promote_phase2_5 post-test
# test/post-test各自执行：
python -m unittest discover -s tests -t . -q
python -m scripts.verify_all_zones
# production目录与默认入口：
python tools/demos/route_entry_demo.py --kb production --list-places
python tools/demos/route_entry_demo.py --list-places
python tools/demos/chat_demo.py --list-places
python tools/demos/route_entry_demo.py --mode surprise_me --start "West Bund" --minutes 180 --seed 42 --json
python tools/demos/route_entry_demo.py --mode plan_for_me --text "I have three hours and want to see old architecture and local neighborhoods." --json
```

仅初始display_order schema blocker按后续明确授权解决；pre测试新fixture mock曾需修正绑定factory，post历史fixture迁移见上节；最终两套post命令均0退出。

## 17. Phase freeze status

**PHASE 2.5 FINAL STATUS: PROMOTED_AND_FROZEN**

Production KB：data/pois.json；Production POI Count：59；Phase 2.5：COMPLETE / FROZEN。

历史candidate/证据不删除，正式停止。未开始Phase3，未增加POI、未discovery/enrichment、未接真实地图routing、未做前端。
