# Phase 4A — 人工反馈修订

本轮完成原 8 项反馈及后续 2 项新增改动，等待再次人工验收。

## 已完成

1. 放大应用页正文、按钮、地点名称、标签与详情字体；天气加粗并增加底色；路线列表序号增大。首页大标题保留原设计。
2. Your walk 顶部新增“编辑地点”，提供添加必去/普通地点、移除、替换、前后排序、调整偏好和时长、严格时间上限、显式全局重规划。自然语言输入接入已有 ConversationalTripService 和 TripActionExecutor，支持多轮澄清，展示执行结果及增删变化。按钮操作复用相同执行器，不把普通添加变成全局重排。
3. 补齐 58 个 Core POI 的英文概览和 10 个缺失英文名称；英文界面移除中文副标题、中文原文回退、“Why this place matters”。实时附近地点名称/地址使用展示层英文翻译并缓存；失败时显示英文不可用提示。英文模式使用 EN/ZH 切换标记。翻译不修改原始 KB、实体身份、坐标或实时事实。
4. 新增独立结算页：实际开始到结束时长、路线完成率、累计探索 Core POI。完成率为 visited / (visited + skipped + remaining)，明确移除的地点不计入，跳过不会计为完成。累计探索按 Core POI id 在当前浏览器 localStorage 去重；尚未实现账户跨设备累计。
5. Places in mind 先选四个街区之一，再展示该街区的可搜索地点列表。保留勾选处滚动位置，下方展示已选地点并支持移除。服务端也拒绝跨街区初始选择。
6. 三种模式改为清晰卡片，选中时深色背景、白色标题及高对比序号。
7. Surprise me 必须先选街区，起点选择才启用，且仅显示该区 POI；切换街区会清空旧起点。
8. 使用用户提供的城市天际线图标；按钮采用取样紫色 `#C9AAD6`，深色文字保证可读性。
9. 删除 Plan a walk 右侧图片/介绍栏，表单自动填满内容区域。
10. Explore the city 新增四个街区介绍预留位置，`content.json` 的 `zones.<id>.introduction.en` 可直接填写；四张街区图片也已预留。

## 英文高德地图

接入用户配置的 JavaScript API。实际检查发现 JS API 2.0 的本次参数未产生英文标注，因此采用高德[官方英文地图示例](https://lbs.amap.com/demo/javascript-api/example/map/map-english)对应的 1.4.15 版本，设置 `lang: en`；中文模式使用 `zh_cn`。最终截图确认道路和地点为英文，路线仍使用既有高德步行几何和 GCJ02 坐标。

按[官方安全代理文档](https://lbs.amap.com/api/javascript-api-v2/guide/abc/jscode)设置 `serviceHost`。浏览器使用公开的 JS API key，`AMAP_JS_SECURITY_CODE` 仅服务端注入；Web 服务 Key、DeepSeek Key 不进入页面。地图保留 AMap 归属链接、AutoNavi 版权和审图号标识，以英文形式展示。

## 验证

- Python：本轮受影响层共 **179 项通过**，含 Web 适配、原有途中交互/会话、代理与展示翻译。历史 CLI 子进程测试首次因 Windows 输出编码失败，设置 `PYTHONIOENCODING=utf-8` 后单独重跑通过；没有修改冻结测试来掩盖问题。
- Node：**13 项通过**，新增实际时长、完成率、累计去重、英文内容及街区预留契约检查。
- 浏览器：按区选择、勾选滚动保留、已选标签、真实执行器插入、英文详情、结算、Surprise 前置条件、四区介绍及手机无横向溢出均通过。
- 实网 LLM：英文请求添加 TANK Shanghai 成功，原有站点相对顺序保留。
- 实网地图：英文道路/地点标注已截图核对；页面文本除左上角品牌外无中文。附近咖啡店返回 5 条英文名称，最终页面/控制台无 JavaScript 错误。
- 证据：`examples/frontend_4a/feedback-*.png`、`feedback-live.json`、`feedback-final-verification.json`。
- 遵循 AGENTS.md，按实际改变的层扩展测试；未重复全套历史回归。地图版本、代理 MIME 的修正属于对应接口集成变更，进行了针对性实网复测。

## 主要文件

前端：`app.js`、`walk-controls.js`、`amap-sdk.js`、`map-controller.js`、`styles.css`、`lib.js`、`i18n.js`、`api.js`、`catalogue-en.json`、`content.json`、`index.html`、`assets/brand.jpg`。

适配层：`web_server.py`、`src/web_app.py`、`src/web_trip_actions.py`、`src/web_sdk.py`、`src/web_english.py`。新增/扩展针对性测试和验收脚本。原有规划、途中执行器和 Core58 数据文件保持不变。

图片、Cultural Bridge 和街区介绍正文继续由用户填写。行程仍为本机内存会话，服务重启会清空当前行程；累计探索保存在当前浏览器中。


## 2026-10-07 第二轮交互反馈

- 移除路线顶部 Edit stops / Adjust preferences；下方统一通过带箭头的功能菜单选择添加、删除、排序、时间或偏好调整，并保留自然语言输入。
- ACTIVE 行程中 Plan a walk 正常进入规划表单；Find my walk 弹出覆盖确认。取消不变；新路线成功生成后才结束旧行程。服务端校验行程 ID 和版本，失败、澄清未完成或状态冲突时保留原行程。
- POI Overview 移除 A good place to pause 快捷入口，保留 Nearby 标签。
- 可行性检查使用浅紫背景，标题 18px、正文 16px、地点名 17px。
- 封面不显示顶部页面导航或设置；产品标识不再可点击，各页面无返回封面的链接。浏览器后退仍可返回封面。
- 桌面列表与地图之间增加可拖动分隔条，支持方向键和 Home/End，宽度比例本机保存；手机保留切换视图。
- 设置中可切换 km / mi。路线总距离、分段和附近地点距离统一转换，本机保存；后端距离和规划逻辑不变。

验证：28 项 Web 适配层测试；14 项前端契约测试；两组 Edge 浏览器定向流程通过、无页面脚本错误。未运行全部历史回归，未重复实时 API 测试。截图：examples/frontend_4a/feedback-round2-desktop.png 与 feedback-round2-mobile.png。
