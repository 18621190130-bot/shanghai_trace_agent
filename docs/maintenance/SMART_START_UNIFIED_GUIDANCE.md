# Smart Start & Unified Map Guidance 交付报告

日期：2026-10-25。开发分支：`smart-start`。基线：`a562ab1`（main）。

## 实施范围与 Git 隔离

本次仅在已存在的 `smart-start` 分支开发，不切换、不合并、不推送 main。保持 Vanilla JS ESM、Python 标准库 HTTP 服务及既有 Route Engine；Core POI、图片、文化文案与身份映射数据均未修改。

## 文件与职责

| 文件 | 职责 |
| --- | --- |
| `src/map_guidance.py` | 统一四种接驳查询、地点搜索、坐标转换、结果归一化、短时缓存、方向约束检查 |
| `src/web_app.py` | 组装共享 Provider；在 session 锁与版本检查下执行整体方向切换 |
| `src/trip_state.py` | 新增 planned-only 方向变更事件、路线版本及序列化重放；原始快照保持不可变 |
| `web_server.py` | 同源 guidance API，沿用现有 Host/Origin 检查与密钥配置 |
| `frontend/map-layers.js` | 分层拥有覆盖物及独立清理、样式与更新签名 |
| `frontend/amap-sdk.js` | 复用地图实例，主线/接驳/支线/POI/位置分层绘制 |
| `frontend/map-controller.js` | 无 JS SDK 时的示意地图降级、选点和辅助路线展示 |
| `frontend/navigation-controller.js` | Smart Start UI 状态、比较、四模式选择、Nearby/返程、过期请求隔离 |
| `frontend/location-heading.js` | 设备朝向授权、绝对朝向/移动航向区分、平滑、过期与监听器清理 |
| `frontend/arrival-session.js`、`frontend/arrival-controller.js` | 复用现有位置跟踪，保留质量、时间与移动航向，不新增重复 watch |
| `frontend/app.js` | 页面集成、地图 DOM/实例保留、生命周期、附近服务按钮与定位入口 |
| `frontend/i18n.js`、`frontend/guidance.css`、`frontend/index.html` | 双语提示、紧凑交通方案、移动布局和新样式加载 |
| `tests/test_map_guidance.py` | Provider 归一化、缓存、失败、坐标、原路线保护与方向事件测试 |
| `frontend/tests/guidance.test.js` | 图层隔离、跨方式自动选向、异步失效与朝向降级测试 |
| `tests/browser_guidance_smoke.py` | 使用明确的假 SDK / 路线 fixtures 进行无配额浏览器验收，不进入生产逻辑 |

## 实际高德接口方案

后端复用 `AmapClient`，步行直接复用 `WalkingRouteService` / `AmapWalkingProvider`，没有第二套 HTTP 客户端或 JS 插件算路。

- 步行：`/v3/direction/walking`。
- 公交：`/v3/direction/transit/integrated`，固定上海 city/cityd。
- 打车参考：`/v3/direction/driving`，不含叫车、等候、费用或支付。
- 单车参考：`/v5/direction/bicycling`，请求 cost/polyline，不含库存、解锁与费用。
- 起点搜索：`/v3/place/text`，上海 citylimit，最多 8 条，使用返回坐标。
- 浏览器 WGS84：复用 `/v3/assistant/coordinate/convert`，绘制坐标统一 GCJ02。

公交每段步行和乘车的真实 polyline 独立绘制，不跨段补直线。没有可靠几何的铁路/出租车公交混合方案保守标为不可用。高德返回的零长度、1 米以内步行节点跳过，不能据此否定整条公交线路。骑行兼容实际响应中的顶层 duration 及 cost.duration。

缓存上限 128，成功 180 秒、失败 15 秒；失败返回 UNAVAILABLE，不生成假时间/几何。后端服务密钥不进入前端；JS Key 继续使用原有 SDK 安全代理。

接口文档：
- [高德路径规划](https://lbs.amap.com/api/webservice/guide/api/direction)
- [高德路径规划 2.0](https://lbs.amap.com/api/webservice/guide/api/newroute)
- [JS 1.4 Polyline 覆盖物](https://developer.amap.com/api/javascript-api/reference/overlay)

## 地图图层与状态

`MapLayers` 分别管理 main、start_access、nearby_detour、pois、user。返程占用 nearby_detour 图层。每层按内容签名更新；替换支线只清理支线。没有 `clearMap()`。AMap 路线插件不自动绘制，因此无重复路线对象。

主线使用 #8053DB、无外框、8px 线宽、白色 showDir 箭头及圆角。接驳为 #397DE0；附近服务为 #20A89A 较细虚线。保留 POI 编号和终点标识。原本只能估算的主线仍显示虚线与 Estimated，不冒充实际道路。

同一路线页面重绘保留地图 DOM/实例和视野。位置变化只更新位置图层；新辅助路线才主动适配视野。切换交通模式、起点或附近目标时替换对应辅助内容。关闭 Smart Start、返回主线、离开路线页、切换路线版本、结束漫游时清理辅助状态。所有异步读取使用 epoch，过期结果不重新画线。

## Smart Start 流程

1. 原三种模式先生成路线，Setup 不新增起点要求。
2. Route Review 打开 Smart Start；可直接开始漫游，也可 GPS / 搜索 / 地图点击设置接驳起点。
3. 两端各查询步行、公交、打车、单车；分别取最快可用方式，再比较方向。无需先选择交通基准。
4. 自动应用更快方向，不设节省阈值。相同耗时保留原方向；缺少任一端结果则不自动改变。说明单一交通方式下的相反最优方向及节省时间。
5. 用户手动选择原方向或反向。固定起点（含原请求坐标）、预约、固定顺序、时间窗口或叙事约束锁定方向。
6. 原有 POI 与游览模式不变，仅整体倒序；重新获取该方向步行道路几何。原始 RoutePlan 和已有历史不可变，新增 `SMART_START_DIRECTION` 路线版本及 `walk_direction_changed` 事件。
7. 当前首站展示四种方式，按真实耗时排序；失败方式不可选。点击后只切换蓝色线。
8. Start walk 使用当前已确认方向；接驳线关闭，接驳时间/距离不计入 City Walk 统计。

## Nearby Services

Directions 留在现有地图内。起点优先使用 30 秒内、精度不超过 50 米的位置，其次使用手选起点，再用对应 Core POI。终点使用服务数据中的可靠坐标；缺失时不给虚构坐标。当前 Nearby 数据模型正常返回可靠坐标，异常缺失时明确提示，不做名称猜测。

一次仅一条支线；切换目标替换支线，不改变 TripState / RoutePlan / POI 序列。关闭 Arrival Card 后仍有地图上的独立导航控件。Back to City Walk 只移除支线并恢复主视图。Return to route 前往下一未访问 POI；没有新 GPS 时明确注明从服务位置出发，不悄悄跳站。不提供外部高德跳转主入口。

## 定位与朝向

Smart Start GPS 是用户点击触发的单次定位；Active Walk 复用既有位置跟踪，退出路线页停止跟踪。位置为深紫色、白边，质量允许时绘制精度圆。

设备朝向只在用户点击启用后监听；支持 iOS requestPermission。采用可靠 webkitCompassHeading 或 absolute alpha，并考虑屏幕角度；平滑和限频，5 秒无可靠设备事件则降级。GPS heading 只在移动速度至少 0.8m/s 且精度不超过 50m 时使用，不能当成手机面朝方向。位置超过 30 秒后不显示方向箭头。无权限/不支持时保持圆点。离开页面、结束路线、pagehide 清理传感器监听及过期定时器。

## 验证结果

- 247 项不重复的相关 Python 测试通过：guidance、TripState、web API、arrival、表单补充、walking、trip replanning、trip interaction、replan feedback。
- 30 项前端 Node 测试通过（含 6 项新 guidance 测试）。
- 离线浏览器验收通过：真实 Route Engine 生成、地图实例复用、四模式切换、整体反转/恢复、到达卡片、Nearby/返程/关闭图层、主线保护、手机宽度、无 JS 异常。
- 真实高德小范围联调通过：四种方式均返回 AVAILABLE；搜索返回 8 条。
- 真实 SDK 浏览器验收通过：英文地图、紫色描边及白箭头、橙色真实接驳路径、四方式可用、桌面与 390px 移动布局、无页面 JS 异常。
- `git diff --check` 通过。没有修改 Core 数据、文化文案、图片或 Route Engine；没有为此次补丁运行全部历史阶段测试。

复核命令：
```text
python -m unittest tests.test_map_guidance tests.test_trip_state tests.test_web_frontend_api tests.test_web_arrival tests.test_form_supplement tests.test_walking_routing tests.test_trip_replanning tests.test_trip_interaction tests.test_replan_feedback -q
node --test frontend/tests/*.test.js
python tests/browser_guidance_smoke.py
```

浏览器脚本需要本机 Playwright/Edge，使用明确的 fixtures，截图写入忽略的 `.runtime/`。真实 API 检查仅在本次最终联调执行，修正公交/骑行解析后只复测受影响接口。

## 限制与人工验收

- iPhone/Android 真机的设备朝向授权、屏幕旋转及移动 GPS 尚未实测；须在可用 HTTPS 环境中验收，不能把桌面模拟视口当作真机验证。
- 地图 SDK 未配置/不可加载时降级为示意地图；精度圆和原生白箭头主要由实际 SDK 提供。
- 公交仅绘制有真实几何的返回方案，缺少铁路几何等情况明确不可用。所有方案受服务配额、时间与可用性影响。
- 高德搜索结果可能仅有中文名；英文界面用搜索词、序号和坐标区分，中文界面显示原名；未增加 LLM 翻译调用。
- 页面刷新后恢复服务端已确认的方向；临时起点、接驳/支线选择不持久化。进程重启后仍遵循现有内存 session 生命周期。
- 本次没有实现自动偏航重算、语音导航、叫车或单车交易，也没有修改此前保留的预设 Developer Demo 位置按钮。

本地验收地址为运行中的 `http://127.0.0.1:8767/`，仅此电脑可访问。服务停止后可在本分支运行 `python web_server.py --port 8767 --demo`，或使用项目原有启动程序。


## 2026-10-25 反馈修订验收

- Surprise me 仅需区块和时长，不绑定起点；保留旧 API 显式起点兼容。四区均通过无起点生成测试。
- GPS 使用最多 12 秒短时 watch 等待改进；50 米以内直接用于规划，50–5000 米必须确认，过期与超范围拒绝。到达判定仍采用原严格标准。浏览器权限或设备无法返回位置时不会伪造 GPS。
- 搜索保留分店名称、上海市/区/街道地址，复用已有英文展示翻译；地图选点逆地理编码，显示名称/地址，不展示坐标。英文翻译不可用时明确提示切换中文。
- 公交/骑行/驾车从所有含可靠几何的返回方案中选最短耗时，不再仅取第一条。
- 定向测试：52 项后端、35 项前端通过；浏览器 fixture 验收覆盖地址、自动反向、手动覆盖、蓝色无描边线、四方式、原主线保护、Nearby 返回和移动布局。测试位置与交通 fixture 不等于真实 GPS 实测。
- 不修改 main，不修改 Core POI、图片、文案、映射数据。旧验收段落记录上次版本外观，本节及更新后的流程为当前规则。
