# Phase 2.5 — COMPLETE / FROZEN

正式production：`data/pois.json`，59个route-selectable节点。默认`tools/demos/chat_demo.py`及`tools/demos/route_entry_demo.py`均加载production。

| Zone | Nodes |
| --- | --- |
| 武康—复兴—徐家汇 | 17 |
| 老城厢—新天地—外滩 | 15 |
| 鲁迅公园—四川北路 | 14 |
| 徐汇西岸滨江 | 13 |

Route Role（anchor/supporting_stop/transition_stop）、四区Zone Config、POI Pipeline、Candidate provenance均进入正式生产基线。West Bund 13节点及p36–p43对象不变。保留既有稳定ID；只在本次人工删除三个新ID后，按明确授权重新连续编号display_order，未修改其余保留POI字段。

原27节点production备份：`data/archive/pois_pre_phase2_5.json`，SHA-256及创建时间见同目录snapshot manifest。全部历史candidate、evidence、缓存和报告保留。历史Phase 1/2测试明确使用该备份，当前production用独立promotion/default CLI测试验证。

最终candidate：`data/pois_phase2_5_final_candidate.json`；来源为G62候选，删除团中央机关旧址、东海大楼、四川北路街道图书馆。稳定ID、已审核角色、tags、坐标修正及visit profile冻结。源candidate未改写。

完整验收见[最终推广报告](../history/phase2_5/PHASE2_5_FINAL_PROMOTION_REPORT.md)与[Promotion Manifest](../../data/PHASE2_5_PROMOTION_MANIFEST.json)。两套完整测试各379项通过；删除前后三区核心/G主题、时长、西岸和跨区12模式均未出现成功场景退化。默认CLI已验证59节点。

```powershell
python tools/demos/route_entry_demo.py --list-places
python tools/demos/chat_demo.py --list-places
python tools/demos/route_entry_demo.py --mode surprise_me --start "West Bund" --minutes 180 --seed 42
python -m unittest discover -s tests -t . -q
python -m scripts.verify_all_zones
```

Known limitations：old_city_life仍可能不足；老城120分钟默认路线可能2站；历史窄local_life偏好在G62和final59均可能缺少相关anchor而composition_failure；真实开放、crowd/weather/tickets未接；代表坐标非入口；仍使用approximate walking geometry，未接真实Map Routing。当前closed状态不会被当成稳定实体不存在。不开新POI来补这些限制，也不提高角色或补造标签。

Phase 2.5冻结。本任务未实现Phase 3、前端或真实地图routing。历史重建/采集/校准工具不是日常运行入口，避免用它们重写已冻结production。
