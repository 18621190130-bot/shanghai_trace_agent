# TraceMate 4A Frontend

在 `shanghai_trace_agent` 目录运行：

```powershell
python web_server.py
```

浏览器打开 `http://127.0.0.1:8765`。另一个端口可用 `--port 8766`。离线检查使用 `python web_server.py --offline`：规划仍使用真实 Core58 和既有引擎，实时数据明确显示不可用，路线连接明确标为预估。

生产前端是原生 ES modules、CSS 和 HTML，无需 npm install 或打包。Python HTTP 适配层调用既有路线、行程状态与 WorldContext 服务，不替换冻结的后端。

实时高德使用服务端环境变量 `AMAP_WEB_SERVICE_KEY`，也兼容当前本机已有的 `AMAP_API_KEY`；自然语言输入使用 `DEEPSEEK_API_KEY`。不要把密钥写入前端或 content.json。三种结构化路线模式无需语言模型。

图片和文化内容填写见 [CONTENT_GUIDE.md](CONTENT_GUIDE.md)。界面默认英文，顶部切换中英文，语言选择保存在浏览器本地。行程状态通过同源 HttpOnly Cookie 对应服务器内存会话；刷新可恢复，服务重启会清空，尚未实现账户或长期保存。

## 文件结构

- `app.js`：页面、导航、异步状态、表单及行程操作。
- `components.js`：共享图标、图片位、状态与文化内容组件。
- `i18n.js`：完整 EN/ZH 界面文案。
- `map-controller.js`：高德底图与路线/地点叠加、拖动、缩放、定位、列表联动。
- `lib.js`：数据展示、安全文本、地图投影等纯函数。
- `api.js`：同源请求；`content.json`：用户编辑内容。
- `styles.css`：统一设计变量、页面及响应式布局。

## 验证

```powershell
python -m unittest tests.test_web_frontend_api tests.test_route_engine tests.test_trip_store tests.test_trip_replanning tests.test_route_reality_check -q
node --test frontend/tests/contracts.test.js
```

浏览器测试需要本地 Edge 与 Playwright。`scripts/test_frontend_e2e.cjs` 针对运行在 8765 的离线服务器；`scripts/inspect_frontend.cjs` 保存截图。`scripts/accept_frontend_live.cjs` 是显式运行的最终实网检查，默认连接 8766，不加入常规回归。可通过 `TRACEMATE_URL` 指定地址；在本次环境中 Playwright 由 Codex 的依赖运行时提供，普通环境可自行安装开发测试依赖。测试遵循根目录 AGENTS.md 的范围约束。

本服务器仅绑定本机，适用于开发及人工验收；不是生产部署服务器。

## 本轮反馈修订

见 [修订报告](../docs/history/frontend/4A_FEEDBACK_REPORT.md)。英文地图使用 AMap JavaScript API 1.4.15，需要 `AMAP_JS_API_KEY` 和 `AMAP_JS_SECURITY_CODE`。前者为浏览器公开 JS key；后者通过服务端安全代理使用，不下发前端。Windows 新进程环境变量以及用户/系统级持久变量均支持。`.env.example` 只说明变量名称，不会自动加载 `.env`。

途中自然语言输入复用现有 LLM 动作解释和执行器；无模型配置时仍可使用结构化编辑按钮。累计探索保存在当前浏览器 localStorage，清除浏览器数据会重置。结算时长按行程开始/结束事件计算。

本轮针对性检查：`python -m unittest tests.test_web_frontend_api tests.test_web_sdk tests.test_trip_interaction tests.test_trip_conversation -q`。Windows 执行前可设 `$env:PYTHONIOENCODING='utf-8'`。`scripts/test_frontend_feedback.cjs` 默认连接 8767 离线服务；实网脚本只在验收时明确运行。


## Phase 4B_2 Arrival / Demo

Normal: `python web_server.py --port 8777`. Developer demonstration: `python web_server.py --demo --port 8777` (equivalent server environment: `TRACEMATE_ENABLE_DEMO_MODE=true`). The controller is hidden by default; demo mode only changes the location provider, and the SIMULATION label remains visible while enabled.

Generate a route, Start Walk, then use I'm Here or Developer Demo → Enable simulation → Far / Near / Arrived. Arrival does not complete a visit. Use Mark as Visited to update the real trip. Arrived Places keeps reached cards across page refresh and replans in the same browser/trip. Next Target only synchronizes the simulation target. Reset clears location, not trip progress. Reload starts in real GPS mode.

Arrival content: edit `data/poi_arrival_content.json`, `records[core_id]` with bilingual `arrival_hook: {en, zh}` and `what_to_notice: {en: [], zh: []}`, plus `content_status`. Omitted/null fields stay hidden. Full Cultural Bridge continues using the existing `frontend/content.json` schema. No runtime content generation or RAG is implemented.

Entrance cache: `data/poi_arrival_locations.json`, generated from existing identities by `python scripts/enrich_arrival_locations.py`. Only run deliberately when refreshing provider metadata; do not repeat for UI patches. It never updates route targets. Read PHASE4B_2_REPORT.md for acceptance and limitations.


### Arrival feedback revision

Start from the cover at `/` (do not append `#plan` when presenting the whole demo). Reached cards are under **Arrived Places** in the map's upper-left corner. On mobile the itinerary shortcut opens this map archive. Entrance **Show on map** uses a square teal arrow marker and never opens an external page.

Arrival content may additionally contain `arrival_point: {reviewed: true, location: {lat, lng, coordinate_system: "GCJ02"}}` and `entrance_image: {src: "/assets/entrances/pXX.webp", reviewed: true, alt: {en: "...", zh: "..."}}`. Explicit `source: "CURATED"` also qualifies an entrance image. Generic POI photos are never used as entrance images. Anchor Cultural Bridge and all POIs' What to Notice now have visible compact pending sections.

Location source types: `AMAP_PROVIDER_ENTRANCE`, `TRACE_REVIEWED_ARRIVAL_POINT`, `UNAVAILABLE`. Unreviewed frozen route points remain a separately labeled `suggested_location`, never a reviewed entrance. Marker positions do not change route geometry.
