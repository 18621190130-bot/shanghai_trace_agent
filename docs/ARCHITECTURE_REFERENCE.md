> 历史架构与数据接口参考：迁自整理前 README。历史测试数字及旧 repair 状态不代表当前版本；当前状态以 README 和 docs/phases/PHASE2.md 为准。

# ShanghaiTrace / 沪迹 — Phase 2

City Walk 原型。当前运行知识库包含 **27 个 POI、四个 Walk Zone**，用访问模式和旅行节奏估算停留时间。Phase 2 在现有确定性路线引擎上新增三种输入入口；默认 CLI 与全部测试离线，真实自然语言解析通过显式启动 tools/demos/chat_demo.py 使用 DeepSeek。完整入口契约、源码展示、六个案例及限制见 [Phase 2 交付报告](history/phase2/PHASE2_DELIVERY_REPORT.md)；地点及访问时间见 [校准交付报告](history/phase1/PHASE15B_CALIBRATION_REPORT.md)。

## Phase 2 三种入口

```powershell
python tools/demos/route_entry_demo.py
python tools/demos/route_entry_demo.py --mode plan_for_me --text "I have three hours and want old Shanghai architecture and local neighborhoods."
python tools/demos/route_entry_demo.py --mode places_in_mind --places "Wukang Mansion;Jianyeli" --minutes 180
python tools/demos/route_entry_demo.py --mode surprise_me --start "West Bund" --minutes 180 --seed 42
```

Plan for me 使用 LLM candidate → 严格校验 → RouteIntent。默认离线模式仅支持 src/mock_examples.py 的精确句子，并明确标注 Mock；任意自然语言使用 `tools/demos/chat_demo.py`，真实 Key 从 `DEEPSEEK_API_KEY` 环境变量读取（不会自动加载 .env）。模型可用 `DEEPSEEK_MODEL` 配置，示例在 `.env.example`。

Places in mind 按四区列出图鉴，可跨区选择。先做必去点独立预检，再调用既有引擎补充节点。明显跨区（跨区地点估算最大间距超过3km）按本阶段保守步行政策拦截；不模拟交通。只有主动选择 HELP_ME_CHOOSE 且确认建议后才修改必去。

Surprise me 只需时间＋可解析起点，不问兴趣。七个固定主题通过共享 Adapter 和实际路线引擎检查；优先最近可达区、可行站数，再按稳定 seed 排平局。起点只支持目录名称、别名、四区名称及显式坐标；库外地址需要补充。

三入口共用 `RouteIntent → ClarificationLayer → intent_to_route_request → RouteEngine`。每轮至多两题，满足最低信息后立即生成。完整 JSON Schema 位于 examples/route_intent.schema.json 和 examples/clarification.schema.json；三入口案例见 examples/phase2_routes.json。

Phase 2 First Repair：`python tools/demos/chat_demo.py --mode plan_for_me` 或非JSON的缺字段 `--text` 调用可在同一进程直接回答澄清；支持 `3 hours` 和 `parks and local life`，回答合并到已有意图，不清空前轮字段。`--json` 保持批处理，不自动读stdin。完整 Parsed Intent 显示正负偏好、起点、区域、必去及约束。新增 `avoid_tags` / `avoid_poi_ids` 在共享引擎排除可选点，must-go优先；无可靠数据的拥挤/旅游化偏好只保留warning。低于65%利用率时尝试同区相关组合，长单段仅诊断，未接地图。全部143项测试通过；五个运行案例及真实Provider待验证说明见报告末章和 examples/phase2_first_repair.json。

Python 3.10+，只使用标准库；本次实际验证环境为 Python 3.14.6。运行不依赖网络服务。

## 运行

在本目录执行：

```powershell
python tools/demos/demo.py
python tools/demos/demo.py --request examples/request.json
python tools/demos/demo.py --output examples/route_plans.json
python tools/demos/demo.py --json
python -m unittest discover -s tests -t . -v
```

默认 CLI 用地点名称及 `display_order` 显示五条路线，不用内部 pXX 作为游客端编号。`--json` 是机器/调试输出，`--output` 保存完整机器 JSON；机器结果保留稳定的内部 `poi_id` 用于 must-go 和系统引用。成功返回退出码 0，其他请求结果或文件校验错误返回 2。

## 数据和接口

运行数据为 `data/pois.json`。删除旧核心点董家渡天主堂与黑石M+，新增徐家汇天主堂、徐家汇书院、南京路步行街与徐家汇商圈。旧内部 ID 保持不变；显示编号按当前数据顺序为 1–27。

四区为：

| 区域 ID | 中文 | English | 地点数 |
| --- | --- | --- | ---: |
| wukang_fuxing_xujiahui | 武康—复兴—徐家汇 | Wukang–Fuxing–Xujiahui | 8 |
| old_city_central | 老城厢—新天地—外滩 | Old City–Xintiandi–Bund | 8 |
| hongkou_literary | 鲁迅公园—四川北路 | Lu Xun Park–North Sichuan Road | 6 |
| west_bund | 徐汇西岸滨江 | West Bund Waterfront | 5 |

每个 POI 包含 `display_order`、`poi_type` 和 `visit_profile`。类型允许 landmark、venue、park、street、district；街道和商圈是体验区域，不要求对应单栋建筑。street/district 使用 `location.representative_lat/lng`，其他类型使用 `location.lat/lng`。代表点不是整片区域的唯一位置或准确入口。

```json
{
  "default_mode": "walk_stop",
  "supported_modes": ["walk_stop", "full_visit"],
  "modes": {
    "walk_stop": {"quick": 30, "standard": 45, "deep": 60},
    "full_visit": {"quick": 60, "standard": 90, "deep": 120}
  }
}
```

这是当前豫园的 profile。walk_stop 是商城及周边街区，不购园林票；full_visit 包含购票入园和周边游览。`flexible` 与旧 `recommended_stay` 已移除。时间是产品估计；新增的第二模式估计在 `visit_profile_calibration.pending_manual_calibration_modes` 中标记，选入路线时也提示。

Repository 校验默认模式必须受支持、modes 与 supported_modes 一致、每种模式的三档时间为正且不递减、显示编号连续并符合文件顺序、合法标签、区域、坐标和元数据计数。无效数据抛出 `DataValidationError`。保留全部六个原始查询接口。

## RouteRequest

`available_minutes` 为必填正整数。起点、标签、必去、区域、最大步行距离、人流及环境偏好字段继续保留。新增：

| 字段 | 默认 | 用途 |
| --- | --- | --- |
| travel_pace | standard | quick / standard / deep |
| visit_mode_overrides | {} | 按内部 POI ID 明确指定 walk_stop / full_visit |
| full_visit_unavailable_poi_ids | [] | 明确已知无法完整参访的地点；不是实时查询结果 |
| willing_to_buy_tickets | true | 是否接受已知需要门票的模式 |
| allow_mode_downgrade | true | 不可完整参访时是否允许降为受支持的 walk_stop |

```python
from src import POIRepository, RouteEngine, RouteRequest

engine = RouteEngine(POIRepository())
plan = engine.generate_route(RouteRequest(
    available_minutes=180,
    travel_pace="standard",
    must_go_poi_ids=["p35"],
    visit_mode_overrides={"p35": "full_visit"},
    interest_tags=["shopping_lifestyle", "modern_city"],
    preferred_zone="wukang_fuxing_xujiahui",
))
print(plan.to_dict())
```

请求也可以是同字段字典。非法节奏、模式、已删除地点引用、未知区域或跨 taxonomy 分组的非法标签返回 `validation_error`。

## 路线行为

先解析 mode 和 pace，再计算停留：`visit_profile.modes[selected_visit_mode][travel_pace]`。用户指定模式优先，否则取默认。已知 full_visit 不可用、用户拒绝该模式的已知门票，或整条路线时间不足时，可以降为支持的 walk_stop；节点记录原请求模式、最终模式和原因。不支持外观模式的必去点不会被静默删除。禁止降级时，不可行就明确失败。

full_visit 表示主要目的地，**不与 indoor 或购票绑定**；南京路和鲁迅公园均可用 full_visit。具体环境、票务与范围保存在 `visit_mode_details`。未知票务不视为免费。

必去优先于区域偏好。无必去时先采用区域偏好，再比较区域中最多五个可规划地点的标签分与起点距离。全空请求默认武康—复兴—徐家汇。

推荐分继续读取 JSON 配置，当前为：

```text
5 × interest matches + 2 × experience matches + 1 × culture matches
+ 4 × same zone − 1.5 × estimated distance km
```

环境、人流只在基础分相同时决定顺序。候选插入时用新增整条路线距离作惩罚；最终节点展示分用前一段距离，`scoring_distance_basis` 解释这一区别。

给定兴趣标签时，可选点至少匹配一个兴趣；否则至少匹配给定体验或文化标签。全空偏好不做相关性过滤；必去保留。按可行插入选择点，每次重新核算完整预算。小规模路径进行地理排序以减少绕回；必去超过八个时保留启发式失败与不可行证明的区别。

软站数目标为 ≤90 分钟 2–3 站、91–150 分钟 3–4 站、151–240 分钟 4–5 站。可选点选择趋向上沿，必去可超过上沿；不能为达标突破预算或加入无关点。未达标返回 `richness_target_unmet`，不伪造成功达标。算法没有全局联合优化模式、点集和区域，不能保证找到站数最多或兴趣总分最高的路线。

## 统计和结果

```text
estimated leg km = Haversine × configured walking_distance_factor
estimated walking minutes = estimated km × 1000 / configured walking_speed_m_per_min
total estimated minutes = sum(selected-mode/pace stays) + walking + configured buffer
```

当前绕行因子 1.25、步速 75 米/分钟、缓冲一次 15 分钟，均读配置。预算检查不四舍五入；无起点则从首站到达开始，有起点则计入到首站步行；末站参访结束后停止，不含返程。

节点包含 `poi_id`、`display_order`、双语名称、poi_type、selected_visit_mode、travel_pace、停留、匹配标签、前段距离/时间、推荐理由、模式降级原因和 scope。机器输出同时保留既有距离字段和 `estimated_distance_from_previous`（km）、`estimated_walking_minutes_from_previous`（min）别名。

状态继续为 success、validation_error、infeasible、no_feasible_route_found。失败保留原请求和原因，统计为 null，不输出缺失必去的部分成功路线。

## 交付与限制

- [完整校准报告](history/phase1/PHASE15B_CALIBRATION_REPORT.md)：27 个地点、全部 profile、四区清单、坐标缺口、测试和五条路线。
- [机器地点目录](../examples/poi_catalog.json)、[完整路线 JSON](../examples/route_plans.json)、[游客可读五条路线](../examples/manual_routes.txt)。
- 27 个 POI 坐标齐全。城隍庙、思南公馆、一大纪念馆、左联会址纪念馆、星美术馆已补齐公开地图锚点，并保存来源、坐标体系及原始记录。左联点的精确坐标体系暂按 WGS84 解释、需要人工复核；街区代表点和游客入口仍需核验。详见校准报告。缺坐标时拒绝生成遗漏必去点的路线这一保护逻辑保留。
- 南京路与徐家汇商圈代表点待人工核验；其他新增地点也未核实准确入口。代码不伪装为真实地图导航。
- 未单独计量 POI 内部步行、排队或实时交通；日期与开放时间不解析，已知闭馆状态由请求输入。
- 原 39 项测试按新模型更新，新增 29 项，包括 A–H、模式降级和全部五条人工测试请求；全部通过。实际游客体验仍需复核。

`scripts/calibrate_phase15b.py` 用于复现本次迁移，会从历史 v3 重建并覆盖运行数据；`scripts/export_phase15b_audit.py` 导出本次报告和示例，报告内测试记录是本次已运行结果，导出不代替执行测试。

原始 v1/v2/v3 文件保留作历史来源，不供当前引擎默认加载。旧运行数据与示例归档在 `data/archive`、`examples/archive`。以上为 Phase 1.5B 的数据与引擎校准记录；当前 Phase 2 First Repair 已完成代码修理及143项离线测试，到此停止，不进入 Phase 3。
