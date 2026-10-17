# TraceMate Phase 4A — Frontend Report

后续人工反馈已修订，当前行为见 [4A_FEEDBACK_REPORT.md](4A_FEEDBACK_REPORT.md)。以下为首轮实现记录，地图和英文内容等限制已在修订中更新。

状态：实现与开发验证完成，等待人工验收。未推进下一阶段，未部署公网。

## 设计与实现

按最新要求从空白设计前端，旧网页未作为布局、样式或实现参考，也未删除。采用 Lightspark 式浅色大留白封面：加粗大字、八张绕标题缓慢旋转的图片卡片、暂停按钮和减少动态效果支持。图片当前均为专门设计的预留位。正文统一无衬线字体、暖白底、炭黑文字和陶土色强调，应用页延续同一套视觉体系。

参考关系：

- [Lightspark / Godly](https://godly.design/website/lightspark/)：封面空间与环绕卡片；按用户要求优先于方案中的不同建议。
- [Mindtrip](https://mindtrip.ai/) 与 [Wanderlog](https://wanderlog.com/plan-a-trip)：地图与路线共处一个工作区。
- [Linear](https://linear.app/now/behind-the-latest-design-refresh)：克制的层级与界面密度。
- [MapCN](https://mapcn.dev/blocks)：地图标记和控制器交互参考，未引入其地图供应商。
- Roadtrippers 的附近发现方向按方案实现；本轮其站点页面未成功读取，未把未检查的内容声称为视觉依据。

## 架构与页面

新增 `frontend/` 原生 ES modules 应用，无运行时第三方前端依赖、无构建步骤。新增 Python 标准库 HTTP 入口 `web_server.py` 与薄适配层 `src/web_app.py`。既有 RouteEntryService、TripService、ReplanningCoordinator、WorldContextService 仍为业务权威，不修改业务模型或 Core58 数据。

完成首页、三模式设置、生成中、澄清/失败状态、地点图库、路线预览、途中行程、POI 详情、Cultural Bridge 预留、附近服务、确认及重规划弹窗。桌面路线列表/地图约 40/60，手机采用路线/地图切换与地点底部抽屉。所有主要交互具有加载、空、不可用或失败状态；刷新可恢复当前内存会话行程。

共用组件包含图片位、语义按钮、图标、标签、营业状态、路线段、地图标记、骨架加载和文化内容组件。EN/ZH 文案集中于 `i18n.js`；切换保留当前表单、行程与页面状态。后端只提供中文的地点原文明确标注来源语言，不虚构英文事实。

## 地图与接口

- 路线几何、距离与时间使用现有高德 WalkingRouteService；只有真实 AVAILABLE 路段标为真实步行路线。不可用时显示虚线预估连接。
- 底图使用高德官方 [静态地图接口](https://lbs.amap.com/api/webservice/guide/api/staticmaps)，由 `src/web_map.py` 返回经过检查的图片。现有 JSON AmapClient 无法读取二进制图片，因此单独增加该适配器，不替换已有 provider。
- 浏览器绘制可交互的 GCJ02 标记与折线，支持拖动、缩放、适配全路线、定位、列表/地图悬停高亮、点击详情与附近点。定位仅由用户点击后请求权限。
- 静态图的像素尺度通过高德原生标记实测校准，并增加绝对像素回归测试；普通 256px 世界瓦片公式会导致偏移，本实现使用该静态图接口的 512px 尺度。
- 天气、营业时间、路线现实提醒及七类附近服务直接使用 WorldContextService。附近距离按 provider 的邻近距离说明，不冒充步行距离。
- `/api/bootstrap`、`/api/generate`、`/api/clarify`、`/api/trip/action`、`/api/reality`、`/api/nearby`、`/api/poi`、`/api/map` 均为本机同源适配入口。
- 密钥仅在服务器，前端没有密钥或供应商签名 URL。静态文件仅限 frontend 目录；会话隔离、版本冲突检查、Host/Origin 检查、JSON 大小限制和 CSP 均已加入。

## 验证结果

- 受影响层的 Python 回归：**123 通过**，覆盖新增适配层/静态地图、既有规划引擎、行程存储、重规划及路线现实检查。
- 前端 Node 契约测试：**11 通过**，包含双语键完整性、文本转义、图片路径、真实/预估展示、坐标往返与底图像素尺度。
- Edge 浏览器：**9 组端到端检查通过**，覆盖三模式、语言与刷新、地图联动、文化预留、开始/完成/跳过/结束、失败重规划回滚、附近不可用、390px 手机与 768px 平板、动态暂停和 reduced-motion；无 JavaScript 页面错误。
- 最终实网链路：西岸美术馆 → 龙美术馆，**2,057m / 1,646s / 55 个几何点**；底图 AVAILABLE、天气 AVAILABLE、附近咖啡店 AVAILABLE（5 条）。营业时间不完整，保留 UNKNOWN 和现实提醒，不显示假营业状态。
- 实网验收期间修正了测试选择器，并因地图集成的像素比例问题追加了针对该接口的校准与复测；相同业务请求复用了现有服务缓存。未将 live 测试加入日常回归。
- 按 AGENTS.md 只回归本次涉及的层，没有为前端工作重复运行整个历史测试集。
- 证据见 `examples/frontend_4a/`：浏览器检查 JSON、实网返回摘要、桌面/手机截图、冻结源文件 SHA-256 基线及核对结果。

## 预留内容与边界

没有生产假数据。封面八张图、正文图、各 POI 图片及 Cultural Bridge 均留给用户，统一通过 `frontend/content.json` 填写，详见 [内容指南](../../../frontend/CONTENT_GUIDE.md)。

临时服务 POI 可查看、定位和打开高德，尚不提供“加入核心路线”；当前后端未授权该能力，未创建虚假按钮。已有 Core POI 在途中可通过既有重规划增加。地图是静态底图加交互叠加层，不是完整导航 SDK；高德底图标注仍为中文。缺失密钥或接口失败会明确降级，可重试，不伪造实时信息。自然语言输入仅在配置语言模型时提供，三种结构化模式独立可用。

本地服务器和内存会话适合开发验收，不含登录、数据库持久化、跨设备同步或生产部署；服务重启会清空行程。英文档案内容、真实图片及文化桥接内容待用户补齐。下一阶段应以人工视觉验收和内容补充为先，再按明确需求推进持久化与部署。

## 变更文件

- 新增 `web_server.py`、`src/web_app.py`、`src/web_map.py`。
- 新增 `frontend/index.html`、`app.js`、`api.js`、`lib.js`、`components.js`、`map-controller.js`、`i18n.js`、`styles.css`、`content.json`、`assets/mark.svg`、`package.json`、`tests/contracts.test.js`、`README.md`、`CONTENT_GUIDE.md`。
- 新增 `tests/test_web_frontend_api.py`。
- 新增 `scripts/inspect_frontend.cjs`、`scripts/test_frontend_e2e.cjs`、`scripts/accept_frontend_live.cjs`。
- 新增本报告与 `examples/frontend_4a/` 验收证据；README 顶部补充当前前端入口，保留历史记录。
