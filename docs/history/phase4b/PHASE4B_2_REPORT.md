# 4B_2 人工反馈修订（2026-10-08）

- 已到达卡片移到地图左上角固定可见的 Arrived Places 折叠入口，显示数量。后续到达、已完成参观和重规划不删除旧卡。手机行程页另有入口可切到地图收纳栏。
- 封面始终存在；此前验收链接的 #plan 直接进入规划页。现在验收从网站根路径进入封面。
- 到达卡正文行高 1.85，内容块间距 24px，增加内边距。Anchor 明示 Cultural Bridge 待填区；所有 POI 明示 What to Notice 待填区，不编造内容。
- 入口 Open in AMap 已移除，改为 Show on map。点击后收起卡片、聚焦站内地图的独立青绿色方形箭头标记，不开新窗口，不改变 TripState 或路线几何；卡片仍可从地图历史中重开。
- 入口来源类型改为 AMAP_PROVIDER_ENTRANCE / TRACE_REVIEWED_ARRIVAL_POINT / UNAVAILABLE。现有 24 个 provider entrance 保留；34 个未核验入口的地点为 UNAVAILABLE，同时可用独立 suggested_location 显示冻结路线推荐点。没有擅自把现有未审核坐标标记为 TRACE_REVIEWED。
- AREA/LINEAR 继续称为 Suggested starting point。侧车支持 reviewed arrival_point；不会改变路线目标。
- 可选 entrance_image 仅接受人工审核或明确 CURATED 的本地素材；默认不显示，不使用普通高德 POI 照片冒充入口图。目前未提供任何已审核入口图片。
- A little context before you go 恢复 12px 小字体、透明背景。

验证：11 个到达/入口定向 Python 测试、5 个到达历史前端测试通过；浏览器定向验证封面、地图历史、跨站重开、文化占位、内部入口标记、无外部窗口、无未审核入口照片、手机布局和紧凑路线提示通过。没有重跑历史全套，没有重新查询高德入口 API。

以下为初版交付记录，冲突处以本次修订为准。

---

# TraceMate Phase 4B_2 — Arrival Experience & Demo Simulation

## 1. Summary

PASS（本地功能验收）。完成 Arrival Card、独立到达历史、Explore 居中详情、真实 ProximityService 驱动的定位模拟。停在 4B_2 等待人工验收，未开始 4B_3。

验收地址：http://127.0.0.1:8777/#plan 。正常启动 `python web_server.py --port 8777`；演示启动 `python web_server.py --demo --port 8777`，或显式设置 `TRACEMATE_ENABLE_DEMO_MODE=true`。默认关闭，开启服务能力后还需在 Active Walk 中点击 Enable simulation。

## 2. 修改前后 UI 行为差异

| 场景 | 本阶段行为 |
| --- | --- |
| Your Walk 点击站点/地图标记 | 只聚焦与高亮；不再打开原右侧完整详情 |
| Active Walk 当前目标经定位 ARRIVED | 记录到达，打开轻量 Arrival Card；不自动 visited |
| I'm Here | MANUAL 到达，明确说明由用户确认 |
| Arrived Places | 可收起的历史列表，重新打开到达卡 |
| Explore 点击地点 | 居中大弹窗；保留图片、Overview、Cultural Bridge、Nearby 和围绕此处规划 |

Arrival Card 为地图上的独立非模态浮层，支持内部滚动与关闭；地图仍可操作。其他 modal/路线操作/对话输入期间到达先进入待显示记录，避免堆叠。手机使用适配浮层，原地图/行程切换仍保留。

## 3. Arrival Card 架构

- `frontend/arrival-session.js`：独立 ArrivalHistory 与位置来源类。
- `frontend/arrival-controller.js`：到达观察、卡片/历史 UI、访问信息、Demo、显式完成参观。
- `src/web_arrival.py`：只读 Web 适配器，验证 Active Trip、当前目标和状态版本；不新增 TripState 变更语义。
- 复用 `frontend/poi-images.js`、现有 Core catalogue/Overview、OpeningStatus、Nearby 查询与结果渲染。
- 图片/名称/类型/站点序号、`selected_visit_mode`、停留时间取实际 RouteStop。历史 POI 已移出当前路线时保留原 stop 快照和到达版本。

## 4. Proximity 触发链路

Browser watchPosition → WGS84、timestamp、accuracy、source=GPS → `/api/arrival/check` → 既有 LocationService 标准化 → 既有 WorldContextService.check_arrival / ProximityService → FAR / NEAR / ARRIVED。

仅检查后端当前剩余目标，必须 Active。校验 trip_id / state_revision / poi_id，排除切换目标或重规划后的过期请求。质量门槛：accuracy ≤ 50m、定位时间不超过 30 秒、不能未来偏移超过 5 秒；前后端均过滤非有限值。自动观察限频 5 秒，定位拒绝/超时/不可用/低精度均保留手动入口。

距离阈值直接使用冻结 ProximityConfig：ARRIVED ≤ 60m；NEAR ≤ 200m。前端不重复实现距离判断。AREA/LINEAR 使用 Repository 已应用的冻结 route_anchor；卡片明确表示到达推荐探索起点，不等于走完整条街、进入私人建筑或完成区域探索。

## 5. 手动到达与 Visited

I'm Here 只针对当前目标，调用同一只读到达适配器，事件来源为 MANUAL，不称为 GPS 验证。到达与 Dismiss 均不改变 visited、skip、RouteVersion 或触发 replan。

Mark as Visited 调用既有 `/api/trip/action` complete、携带 revision，由后端 TripService 更新事实。成功后刷新目标；失败保留卡片、明确错误并允许重试；已 visited、skipped 或已移出路线的历史卡片不提供重复完成入口。

## 6. Arrival Content 数据结构

`data/poi_arrival_content.json`：schema_version=1、default_status=PENDING、records={}，没有为 58 个 POI 堆砌空对象。

未来按 Core ID 写入：

```json
{
  "arrival_hook": {"en": null, "zh": null},
  "what_to_notice": {"en": [], "zh": []},
  "content_status": "PENDING"
}
```

只显示当前语言已有内容，不伪造翻译。Full Cultural Bridge 复用既有 frontend/content.json 的 cultural_bridge.places[Core ID]，有内容才在卡内展开。现有图片、Core Overview、计划参观时间已有真实数据；Cultural Hook、What to Notice、Full Bridge 仍待队友内容，不生成文化事实、不开发 RAG、不在到达时调用 LLM 写文案。

## 7. 入口信息来源与缺失

仅使用冻结 Core → AMap identity。新增 provider 适配器 `src/providers/amap/arrival.py` 复用 AmapClient，通过 ID Detail 的 show_fields=navi 取数据；只解析 entr_location，navi_poiid 保留为不透明值，不假定其是经纬度。

契约依据：[高德官方 POI 2.0 文档](https://lbs.amap.com/api/webservice/guide/api/newpoisearch)。

一次性查询 57 个 MATCHED identity，共 6 批（最多 10 ID/批），51 个有 entr_location。最终展示：24 个 POINT 为 PROVIDER_ENTRANCE；34 个为 CURATED_ARRIVAL_ANCHOR（这里表示冻结路线推荐点，不声称这些点经人工核验为入口）。坐标必须有效、在本地范围且距现有目标不超过 500m；AREA/LINEAR 保守使用路线推荐探索起点。

所有 58 个均有冻结推荐坐标，因此 UNAVAILABLE = 0；但 34 个没有在卡中采用可靠 provider 入口，必须以“推荐位置，而非官方入口”展示。入口只是辅助信息，未替换路线坐标/旧几何。高德入口也是 provider-reported，不保证现场开放与通行。

### 展示高德入口的 24 个 POI

- `p4` 鲁迅故居
- `p5` 龙美术馆（西岸馆）
- `p13` 武康大楼
- `p20` 上海城隍庙
- `p21` 上海宋庆龄故居纪念馆
- `p25` 1927·鲁迅与内山纪念书局
- `p26` 中国左翼作家联盟会址纪念馆
- `p27` 1933老场坊
- `p28` 西岸美术馆
- `p29` 上海油罐艺术中心
- `p31` 星美术馆
- `p32` 徐家汇天主堂
- `p33` 徐家汇书院
- `p36` 西岸艺术中心
- `p41` 西岸大剧院
- `pz_17d41390cac9` 上海工艺美术博物馆
- `pz_66452d5db8a1` 大韩民国临时政府旧址
- `pz_54f53d30c0dc` 安康公寓（乌鲁木齐南路176号）
- `pz_437ddd34f2c1` 张乐平故居
- `pz_7e40d824dbee` 上海交响乐团音乐厅
- `pz_8b1bb0928e7e` 李白烈士故居
- `pz_c862ec0d6ddd` 沈尹默故居
- `pz_c4f63095cb01` 日本海军特别陆战队司令部旧址
- `pz_f8277d15786a` 上海多伦现代美术馆

### 仅使用推荐抵达点的 34 个 POI

- `p2` 永康路与嘉善路口（AREA）
- `p7` 新天地北里（石库门街区）（AREA）
- `p9` 张园（AREA）
- `p10` 今潮8弄（AREA）
- `p11` 建业里（AREA）
- `p12` 陕南邨（AREA）
- `p14` 外滩·陈毅广场（AREA）
- `p15` 豫园（AREA）
- `p16` 鲁迅公园（AREA）
- `p23` 思南公馆（AREA）
- `p24` 中共一大纪念馆（POINT）
- `p30` Gate M 西岸梦中心（AREA）
- `p34` 南京路步行街（LINEAR）
- `p35` 徐家汇商圈（AREA）
- `p37` 西岸穹顶艺术中心（含北广场）（AREA）
- `p38` 滨江滑板公园（AREA）
- `p39` 徐汇跑道公园（AREA）
- `p42` 徐汇滨江海事塔广场（AREA）
- `p43` 北票码头塔吊（POINT）
- `pz_a74f9e58195a` 古城公园（AREA）
- `pz_0b545bb1cf2a` 四川北路公园（AREA）
- `pz_b72e3b8998b3` 多伦路文化名人街（LINEAR）
- `pz_b4acff8f32fc` 甜爱路（LINEAR）
- `pz_68957332b418` 太平桥公园（AREA）
- `pz_8919938b21f2` 淮海公园（AREA）
- `pz_bd40d04c7f5d` 复兴公园（AREA）
- `pz_a87eb2b5b5da` 武康路历史文化名街（LINEAR）
- `pz_553cfd36707c` 衡山公园（AREA）
- `pz_a27dbbc6cab8` 襄阳公园（AREA）
- `pz_a446052910a0` 山阴路274弄（AREA）
- `pz_0db17d82e9ec` 上海人民广场（AREA）
- `pz_cc5300aee299` 福州路（LINEAR）
- `pz_de47b0cf3e98` 中南新邨（AREA）
- `pz_09b5938601ee` 徐家汇公园（AREA）

持久快照：data/poi_arrival_locations.json。完整来源与结果：examples/arrival/entrance_audit.json、navi_batches.json。刷新脚本 scripts/enrich_arrival_locations.py 只写新的展示 sidecar，不改 identity/spatial 文件。运行中若快照无记录，按 ID 查询，失败安全降级到推荐点。

## 8. Arrived Places 历史与持久化

localStorage 键为 tracemate-arrivals:{trip_id}；记录 event_id、trip_id、core_poi_id、arrival_cycle、route_version_id_at_arrival、arrival_source、arrived_at、dismissed_at、visited_status，以及原 RouteStop/序号快照。

visited/skipped 每次与后端 TripState 重新同步，本地状态不能覆盖领域事实。Dismiss 保留记录；语言切换不创建事件或版本；同一访问周期去重，GPS 漂移不会再次弹卡。只有 POI 从路线成员移除再加入的明确周期才允许生成新事件。重规划和换目标不删历史；不同 trip 隔离；刷新恢复当前 trip 的历史，模拟坐标与 Demo 开启状态不持久化。

## 9. Explore 居中弹窗

复用原详情查询和内容。桌面居中、最大 820px、内部滚动；手机适配。Esc/关闭按钮/遮罩关闭，恢复图鉴筛选、滚动及焦点。Overview/Cultural Bridge/Nearby 三标签保留，文化缺失继续使用原安全占位。Your Walk 完全不调用这套右侧 Drawer 行为。

## 10. Demo LocationProvider / Controller

BrowserLocationProvider 与 DemoLocationProvider 返回 latitude、longitude、coordinate_system、timestamp、accuracy、source。Demo 基于后端当前有效目标和现有阈值生成 GCJ02 位置：约 700m、130m、0m，再调用真实 ProximityService。请求不接受前端直接给定 ARRIVED 状态。

控制器：Far / Near / Arrived / Next Target / Reset Simulated Location / 返回真实 GPS。Next Target 只同步当前 TripState 目标，不完成、不跳过、不改变版本。页面固定 SIMULATION 标识，历史也保留 DEMO 来源。退出/重置清除模拟观察、有效位置和待返回请求；退出后恢复 Browser GPS，重载默认真实模式。模拟不能绕过正常 complete/replan 接口。

Nearby 复用既有七类及展示。有效 GPS/DEMO 优先；失效、低精度、已过期或手动确认且无可靠坐标时使用当前卡片 Core route_anchor，并显示来源说明。仍保持 proximity distance 语义，服务 POI 不进入 Core 或路线。

## 11. TripState / RouteVersion 冻结证明

采集前后比较 747 个已有 src Python / data JSON。仅 src/web_app.py 为已声明的 WebArrival 组合接线改动，其余 746 个完全一致；未发现意外修改。

Core POI、identity mapping、route_role、visit_mode、spatial profile、Route Engine、TripState 与 RouteVersion 实现、must-go 和 walking geometry 均未改写。测试进一步逐快照断言 FAR/NEAR/ARRIVED、手动到达、Dismiss、Demo Next Target 不改变 TripState；只有真实 complete / replan 命令产生正常变化。证据：examples/arrival/frozen_before.json、frozen_audit.json。

## 12. Targeted tests

- 10 个 Arrival Python 测试：Active gate、真实 proximity 三阶段、手动/complete、低质量/过期/未来时间、Demo gate、目标冲突、坐标系标准化、所有 AREA/LINEAR route_anchor、入口契约和降级。
- 28 个既有 Web adapter 测试通过，共 38 个后端定向测试。
- 24 个前端测试通过（其中 5 个新 Arrival session/location 测试，覆盖 history、refresh、trip 隔离、去重、replan 周期及后端 visited 权威）。
- 未运行全部历史 Phase 3 回归。新入口 provider 做一次批量数据验收；最终真实外部服务流程运行一次，没有为 UI 微调反复调用 API。

## 13. Local E2E 验收

scripts/test_arrival_e2e.cjs 在离线外部服务降级环境中使用真实本地领域服务，四条流程通过：

A：生成真实引擎路线 → Start → I'm Here → Nearby → Dismiss → 历史重开 → complete → 下一目标。额外注入 complete HTTP 500，确认卡片与领域状态保留，然后重试成功。

B：Demo FAR → NEAR → ARRIVED → 卡片 → complete → Next Target → 第二/第三个到达 → 重看历史。重复 ARRIVED 不重新弹卡。

C：Explore 居中详情、三标签、七类 Nearby、Esc 关闭与筛选保留。额外 scripts/test_arrival_atlas.cjs 验证滚动位置恢复、anchor 缺图占位、Plan around this place 正确传递 POI/zone，以及手机居中详情边界。

D：完成参观 → 通过已有 SET_PACE 结构化操作真实重规划 → 新 RouteVersion → 原到达历史仍可重开。双语切换、刷新、手机无横向溢出通过。

scripts/test_arrival_quality.cjs 额外验证：低质量 GPS 不发到达请求；手动确认仍可用；Nearby 明确使用 anchor；默认无 Demo 控制器；已有 modal 时到达进入待显示，关闭 modal 后显式查看。

scripts/accept_arrival_live.cjs 在真实服务环境通过：Walking=AVAILABLE、English JS map=true、真实 Proximity 距离约 700m / 130m / 0m、Nearby 请求及其既有降级渲染、真实 visited 更新。没有虚构天气/营业时间/附近结果。证据 live_acceptance.json、live-arrival.png；本轮没有真人在上海实地步行验证 GPS。

## 14. Known limitations

- TripState 沿用既有服务端内存会话；刷新可恢复，重启服务不能恢复丢失的后台 Trip。localStorage 到达历史不替代后台持久化。
- 本地历史绑定当前浏览器，无跨设备同步。
- GPS 实地精度与浏览器权限仍受设备环境影响；本地验收覆盖拒绝/低质量/手动和模拟，未冒充实地验证。
- 入口快照有采集时间，现场开放状态需另行确认；缺少 provider 入口时明确标为推荐位置。
- 到达历史不是完整 GPS 轨迹；只记当前目标到达。新的访问周期采用“移除再加入”规则，不根据短暂 GPS 离开触发新周期。
- Provider 不可用继续显示 unavailable/partial；文化内容仍未填充。

## 15. Ready for Phase 4B_3?

接口、双语字段、内容容器、图片共享和缺失处理已预留，技术上可以承接 4B_3。当前仅交付 4B_2，等待人工验收，不自动开始 Cultural RAG。
