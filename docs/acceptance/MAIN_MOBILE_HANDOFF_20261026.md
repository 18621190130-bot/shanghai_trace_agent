# TraceMate 当前网页验收与手机端交接报告

日期：2026-10-26（北京时间）  
用途：将已完成的桌面网页与 Smart Start 工作交接给另一个聊天窗口，作为手机端开发的事实基线。本文描述当前代码，不把旧阶段计划当作已实现功能。

## 1. 版本与验收结论

- 项目目录：`C:/Users/huawei/Desktop/数据科学探索之路/city walk大创项目/shanghai_trace_agent`。
- 合并前 main：`a562ab1`；本轮 Smart Start 功能末次提交：`87ab358`。
- 本轮分支提交包含 `41c4e31`、`8f01eae`、`c10653d`、`296723b`、`87ab358`。
- 当前结论：历史测试已按用户授权修订，完整回归无失败；smart-start 已合并到本地 main，合并提交为 `35e0c4e`。未经真实手机验收，不宣称手机端已完成。
- 接手时先运行 `git status --short`、`git branch --show-current`、`git log -5 --oneline`，以磁盘现状为准。不要回退到“Smart Start 撤回”历史版本。

## 2. 架构基础

| 层 | 当前实现 | 交接注意事项 |
| --- | --- | --- |
| 前端 | 原生 HTML / CSS / JavaScript ES Modules | 不是 React、Vite；不需要 npm install 或打包即可运行 |
| 页面入口 | `frontend/index.html`、`frontend/app.js` | hash 页面导航，统一 render/state，重绘时保留地图实例 |
| 后端 | Python 3.10+，`ThreadingHTTPServer` / `BaseHTTPRequestHandler` | 不是 FastAPI；运行依赖为标准库 |
| Web 业务 | `src/web_app.py` 与 Web 专用适配器 | 同源 JSON API，复用已有规划、行程和 Provider 层 |
| 规划 | `route_entry.py` → 澄清/意图转换 → Route Engine | 结构化规划不依赖 LLM；自然语言使用 DeepSeek |
| 行程 | `TripState` / `TripService` / `InMemoryTripStore` | 原路线不可变、版本和事件追加、revision 并发检查 |
| 地图 | AMap JS SDK 1.4.15 + `amap-sdk.js`；`map-controller.js` 降级 | 不通过外部高德网页完成 Smart Start / Nearby 导航 |
| 外部数据 | AmapClient、WalkingRouteService、WorldContextService | 使用已有身份映射；失败显示不可用/预估，不伪造实时数据 |
| 内容 | JSON、静态图片、统一图片 resolver | 图片及文案不参与路线评分 |
| 会话 | HttpOnly / SameSite Cookie 对应服务端内存 | 刷新通常可恢复当前会话；服务重启会清空行程，无数据库/账号同步 |
| 浏览器保存 | localStorage | 语言、距离单位、探索/到达记录等；不是完整行程数据库 |

主要调用关系：

```text
页面 / 表单 / 地图操作
  → frontend/api.js → 同源 web_server.py
  → WebApplication
     ├─ RouteEntryService / RouteEngine：生成路线
     ├─ TripState / ReplanningCoordinator：开始、修改、访问与结算
     ├─ MapGuidance：接驳、搜索、转换、反向
     └─ WorldContext / WebArrival：地点、天气、附近服务与到达
```

前端没有独立开发服务器；Python 同时提供页面、静态文件及 API。不要为手机端布局改造先重写技术栈。

## 3. 当前数据与素材

本轮直接读取生产数据统计：

| 项目 | 数量 |
| --- | ---: |
| Core POI | 58 |
| Anchor | 22 |
| Supporting stop | 29 |
| Transition stop | 7 |
| 街区 | 4 |
| 图片清单 CURATED / AVAILABLE | 22 |
| 图片清单 AMAP / AVAILABLE | 34 |
| 图片清单 MANUAL_WEB / AVAILABLE | 2 |
| Cultural Bridge places 记录 | 22 |

四区：`wukang_fuxing_xujiahui`、`old_city_central`、`hongkou_literary`、`west_bund`。图片 AVAILABLE 是清单状态，不代表本次逐张重新验证远程 URL；运行时仍有失败 fallback。

- `data/pois.json`：生产地点；`data/amap_poi_mappings.json`：高德身份映射。
- `data/poi_images.json`：来源、状态、审核与图片地址；`frontend/poi-images.js`：共享 resolver。
- `frontend/content.json`：封面、已导入照片、文化内容、街区内容。
- `frontend/catalogue-en.json`：地点英文展示。
- `data/poi_arrival_content.json`：Arrival hook / What to notice；`data/poi_arrival_locations.json`：入口/建议到达点。
- `frontend/assets/`：网页实际使用的资源；`materials/`：原始素材，通常不进 Git，不能把原始文件夹当作网页运行依赖。
- 图片区域保持固定比例、失败回退，不因缺图改变地点顺序。Anchor 精选图优先。

## 4. 已实现的页面和功能

### 封面与 Explore the city

封面图片展示、醒目的 Plan my walk 入口、Explore 入口；点击产品标识可回封面。非封面页面提供导航和设置。Explore 包含四区、58 POI 图鉴、图片与地点介绍。界面支持中英文；距离可在公里/英里间切换。

### 三种规划方式

- Plan for me：时长、兴趣、步行节奏、街区及自然语言补充；表单信息参与意图，不应重复追问已选时长/偏好。
- Places in mind：选择同区必去地点，连接地点；界面不要求额外选择漫游时长。
- Surprise me：区块与时间生成随机主题路线，不再要求选择起点。实际出发位置由生成后的 Smart Start 处理。
- 活跃行程期间仍可打开规划页；生成替代路线前需要确认覆盖原行程。

### Your Walk 与 Smart Start

- 路线指标、POI 顺序、地图、路线可行性/营业信息、刷新入口；桌面支持左右栏拖动调整宽度。
- 进入 Your Walk 自动请求真实定位，显示地图位置标记；地图定位按钮聚焦当前位置。
- Smart Start 默认展开，仅保留“使用当前位置”和“搜索地点”；搜索显示具体名称/分店、地址，界面不显示经纬度。
- 两端分别比较步行、公交、打车、单车的最快可用方案，自动选择更快方向；保留人工反向，提示特定交通方式可能更适合另一端。
- 不再展示两个端点最快时间的对照表。实际四种接驳选项仍保留。
- Surprise / Places 模式不因生成请求里的旧起点字段被锁定。明确固定顺序、预约、时间窗等约束仍会保护顺序。
- 仅在 PLANNED 状态整体反转；原始路线及历史保留。开始后的路线调整走既有重规划路径。
- Start walk 只保留一个入口：当前所选首站 80 米内、定位精度 ≤ 50 米、位置年龄 ≤ 30 秒（允许 5 秒时钟偏差）时可开始；初始位于另一端附近可选择该端直接开始。
- 搜索得到的位置不是用户当前位置，不能代替 GPS 证明已到达。未满足开始条件时只有一段提示，再点会短暂闪烁。
- 当前开始位置门槛在前端交互层实施；后端 `/api/trip/action` 仍保留通用 start 行为。若未来做公开生产安全约束，需要另行设计服务端可信位置验证，不能把此门槛当防作弊机制。

### 地图、接驳与 Nearby

- 紫色主线无深色描边，蓝色接驳线，绿色附近服务支线；独立图层管理，不用 clearMap 清空整张地图。
- 导航保留在 TraceMate；交通估时说明为 “Travel estimates only.”。
- 配套服务支持咖啡、餐饮、茶饮、甜品、便利店、洗手间、商场等；分类图标可区分用途。
- 点击 Directions to this place 后，隐藏其他配套服务标记；目标只保留一个绿色分类图标与绿色路线，避免白圈/绿点重复。
- 支线不加入左侧 Core POI 主线、不改变访问状态。可返回主线或查看返回下一未访问地点的路线。
- 不再有 Enable device heading 按钮；设备可无额外授权提供朝向时尝试启用，否则不显示虚构朝向。手机授权交互未定稿。

### 到达、文化内容、途中调整与结算

- 到达卡片包含照片、介绍、What to notice、Anchor Cultural Bridge、入口/建议起点及附近服务。
- Show on map 在现有地图展示入口；入口标记与普通 POI 区分，不把普通 POI 图片当入口图。
- “已到达”与“已访问”分开；用户 Mark as Visited 更新正式行程。
- 到过的卡片收纳于地图 Arrived Places，可回看历史；兼顾重新规划后的历史记录。
- 调整路线支持自然语言、快捷操作和 Advanced options；支持原路线与多次调整历史、结果反馈/澄清。
- 行程可结束并显示结算与探索信息。详细领域约束仍以 TripState 和测试为准。

### 开发者虚拟定位

- 默认启动器启用演示；`--standard` 不提供模拟按钮。
- 开发者按钮位于地图角落；开启后点击任意地图位置更新模拟 GPS，再点恢复真实定位。
- 退出模拟清理旧位置与异步请求；离开路线页停止监听/模拟计时器。
- 模拟只换位置来源，不直接伪造已访问状态；按钮及地图控件的层级低于 POI/Arrival 卡片，不遮挡内容。

## 5. 关键文件与 API

| 位置 | 手机端工作中应关注的职责 |
| --- | --- |
| `frontend/app.js` | 页面装配、统一 render、地图 DOM 保留、开始门槛与操作分发 |
| `frontend/styles.css` / `guidance.css` | 断点、左右栏、卡片、地图控件层级、触控布局 |
| `frontend/navigation-controller.js` | Smart Start、方向比较、接驳方案与 Nearby 导航 |
| `frontend/walk-location.js` | 当前统一 GPS / 模拟定位、开始条件、watch 生命周期 |
| `frontend/arrival-controller.js` / `arrival-session.js` | 到达卡片、历史、访问、位置适配；不要新增重复 watch |
| `frontend/amap-sdk.js` / `map-controller.js` | SDK 与降级地图，点击/缩放/聚焦与标记 |
| `frontend/map-layers.js` / `service-markers.js` | 图层和配套服务分类符号 |
| `frontend/location-heading.js` | 朝向计算和生命周期；手机权限策略待验证 |
| `src/map_guidance.py` | 四方式接驳、缓存、地点搜索、坐标转换、方向约束 |
| `src/trip_state.py` / `trip_store.py` | 不可变原路线、事件、版本与并发约束 |

主要接口（具体字段请以调用代码和 tests 为准）：

- GET `/api/bootstrap`、`/api/poi-images`；同源地图安全代理 `/_AMapService/`。
- POST `/api/generate`、`/api/clarify`、`/api/trip/action`、`/api/trip/turn`。
- POST `/api/guidance/search`、`describe`、`location`、`route`、`direction`。
- POST `/api/arrival/context`、`check`、`content`；`/api/nearby`、`/api/poi`、`/api/reality`。

## 6. 本地启动与密钥

双击根目录 `Start_TraceMate.cmd`；或运行：

```console
python start_local.py
python start_local.py --standard
python start_local.py --offline
```

默认从 8765 选择空闲端口；本轮辅助预览为 `http://127.0.0.1:8767/`。必须在运行服务器的电脑访问该 localhost；此链接不是手机或队友可访问的公网地址。当前常驻预览与启动器可能同时存在，要以启动日志为准，避免看错旧进程。

环境变量：`AMAP_WEB_SERVICE_KEY`（网站兼容 `AMAP_API_KEY`）、`AMAP_JS_API_KEY`、`AMAP_JS_SECURITY_CODE`、`DEEPSEEK_API_KEY`，可选 `DEEPSEEK_MODEL`。本机从 Windows 用户/进程环境读取。禁止把真实值写进报告、Git、截图或前端；`.env.example` 仅空值模板，不自动加载 `.env`。JS Key 为浏览器侧用途，Security Code 经后端代理使用。

`.gitignore` 排除 `.env*`（保留 example）、`.runtime/`、缓存、日志、原始 materials 等。Git 未配置可持续公网部署；已移除 Cloudflare 临时部署文件。

## 7. 手机端下一阶段工作建议

从合并后的 main 建独立手机端分支，不直接重写 main。先阅读本文、AGENTS.md、frontend/README.md 和运行中的实际页面。

1. 确认手机导航、地图/列表切换、底部操作区、Arrival/POI 卡片展示形式，再改 CSS 和控制器。
2. 使用真实 iOS Safari / Android Chrome 验证 GPS 权限、定位延迟/精度、后台恢复、拒绝授权、方向权限。桌面 390px 视口通过不等于手机真机通过。
3. 手机不能访问电脑 localhost。当前服务只绑定 127.0.0.1，并限制 Host/Origin；需要明确授权的 HTTPS 部署或安全开发访问方案。不要只改为 0.0.0.0 就声称真实 GPS 可用；普通局域网 HTTP 可能不满足浏览器安全上下文。
4. 检查刘海/底部安全区、软键盘、100svh/dvh、横竖屏、按钮触达尺寸、卡片滚动与地图手势冲突、图层遮挡。
5. 地图实例不能随每次页面更新重新创建；只保留一个位置监听来源，切换真实/模拟/离开页面必须清理。
6. 保留 EN/ZH、公里/英里、固定图片槽、原路线历史、主支线隔离、开始与到达状态区分。不要因手机设计改动 Core POI 顺序或路线评分。
7. 保留无定位/粗定位/无网络/无服务配额的明确降级。当前 50 米精度门槛可能使电脑或部分手机不能开始，需要真机证据再决定是否调整，不能自动假装到达。
8. 测试采用定向开发 → 稳定阶段回归 → 单独实网验收，不重复跑所有历史测试或补图 API。

尚未完成的生产能力：账号、多端同步、数据库持久化、持续云部署、生产容量及安全评估、手机全浏览器真机验收、完整实时逐步转向导航。路线折线和预计时间不等于系统级导航 SDK。

## 8. 交接给新聊天窗口的简短任务说明

> 请先阅读 `docs/acceptance/MAIN_MOBILE_HANDOFF_20261026.md` 和项目 `AGENTS.md`，检查当前分支与未提交改动。此项目为原生 JavaScript ES Modules + Python 标准库 HTTP 服务，Smart Start 已集成。下一阶段做手机端网页，先从 main 创建独立工作分支，保留现有规划、TripState、内容和地图图层逻辑；先确认移动布局及真实手机访问/HTTPS方案，再实现并验收。不要依据历史 Smart Start 撤回报告回退代码，也不要把桌面浏览器模拟视口当作手机 GPS 实测。

## 9. 本轮验证与合并证据

### 历史测试修订依据

用户已明确授权“先修订这些历史测试再合并”。此次只维护测试断言，没有为通过测试回退生产功能、清空精选图片、修改历史哈希清单或更新旧哈希为当前值。

- `test_phase2_5g.py`：把历史数据保护与历史源码证据拆开。归档数据仍校验哈希，只容许 Git 的 LF/CRLF 换行差异；不允许其他内容归一化。旧阶段源码哈希与独立的 `examples/phase3a_freeze/manifest.json` 核对，不再错误地要求持续演进的当前源码永远保持旧字节。当前引擎/验证器行为由功能测试覆盖。这是历史证据一致性检查，不宣称从现有源码重现当年源码归档。
- `test_poi_images.py`：未审核候选不发布，但现有精选图必须保留；无精选图的情形继续验证全部空槽。新增显式高德 accept 决策也不能覆盖精选 anchor 的检查。
- 两份历史测试的旧失败可在 main 基线复现；本轮没有改生产图片、POI 或路线引擎代码。

### 最终验证

| 验证项 | 结果 |
| --- | --- |
| 修订相关定向测试 | 68 项通过 |
| Python 全量离线回归 | 共 1003 项，997 项通过，6 项显式实网测试跳过，0 失败、0 错误 |
| 前端 Node tests | 43 / 43 通过 |
| 浏览器验收 | 通过：路线生成、位置门槛、真实/模拟切换、自动/手动反转、地点地址、主支线隔离、服务标记去重与恢复、提示闪烁、移动视口、无页面异常 |
| 实网抽查 | 四种接驳方式均 AVAILABLE；龙之梦搜索 8 条，均有名称与地址（同一次合并验收前轮已验证，未为测试断言修订重复调用） |
| 手机真机 | 未验收；作为下一阶段任务 |

全量回归耗时约 111 秒。日志中有测试构造 HTTPError 对象的 ResourceWarning，但最终结果为 OK，不存在失败/错误。

完整回归命令（Windows PowerShell）：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
python -m unittest discover -s tests -t . -q
node --test frontend/tests/*.test.js
python tests/browser_guidance_smoke.py
```

必须带 `-t .` 让历史测试作为 tests 包加载。沙箱临时目录权限不足可能产生 PermissionError；最终回归在可正常读写临时目录的权限环境执行。早期的编码、包导入及临时目录问题不计作最终统计，也没有通过删除测试解决。

6 个默认跳过项为需显式启用的高德实网测试；本轮另做一次接驳四方式与搜索实网抽查，不代表天气/营业/远程图片 URL 都逐项重新实网验收。设备 GPS 使用浏览器 fixture 检查生命周期和门槛，尚未做手机真机验收。

日志保留在 `.runtime/merge-acceptance-repaired.log`、`merge-acceptance-node-final.log`、`merge-acceptance-live.json`。之前的 `.runtime/merge-acceptance-complete.log` 是修订前失败记录，不是最终结果。临时 main 基线副本位于 `.runtime/main-acceptance-baseline/`，不属于另一套运行版本。以上均被 Git 排除；本文保存可交接的结果摘要。

### 合并记录

- 历史测试修订提交：`e6ec5e8`。
- 合并提交：`35e0c4e`（`feat: 合并 Smart Start 与统一地图导航`），采用保留分支历史的 merge commit，无冲突。
- main 原基线：`a562ab1`；smart-start 末端：`e6ec5e8`。已验证该末端是 main 的祖先。
- 当前工作分支为 main。保留 smart-start 分支，未删除，未执行 git push。
- 合并后的生产代码与已验收的 smart-start 一致；随后仅更新 README、文档索引和本报告。最终文档提交位于该合并提交之后，可通过 `git log -3 --oneline` 查询。
- 手机端开发从当前 main 新建分支；不要把旧 main 的 a562ab1 或历史撤回记录当作当前产品基线。
