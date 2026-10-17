# TraceMate（沪迹）

上海 City Walk 路线规划与步行体验原型。当前网站覆盖四个街区、58 个 Core POI，支持三种路线规划方式、中英文、途中路线调整与历史、地图、天气与地点信息、附近服务、到达卡片和行程结算。

当前主目录是唯一运行版本。Smart Start 已撤回；保留原版 Developer Demo 预设位置模拟、后续表单补充修复、四个区块照片及已填写的照片和文化内容。阶段报告属于历史记录，不代表当前待办或验收状态。

## 启动网站

Windows 下双击根目录 **Start_TraceMate.cmd**，网站就绪后自动打开浏览器。需要 Python 3.10 或以上，无需额外 Python 依赖。使用期间保留启动窗口，按 Ctrl+C 停止。

```console
python start_local.py
python start_local.py --standard
```

默认网址为 http://127.0.0.1:8765/；端口占用时自动选择其它端口，以窗口显示的网址为准。`--standard` 关闭开发者位置模拟。更多参数见[本地启动说明](docs/LOCAL_START.md)。

## 配置

真实服务通过环境变量配置，密钥不保存在代码中：

| 变量 | 用途 |
| --- | --- |
| `DEEPSEEK_API_KEY` | 自然语言规划与路线调整 |
| `DEEPSEEK_MODEL` | 可选模型设置 |
| `AMAP_WEB_SERVICE_KEY` | 高德 Web Service；本地网站兼容已有 `AMAP_API_KEY` |
| `AMAP_JS_API_KEY` | 高德 JavaScript 地图 |
| `AMAP_JS_SECURITY_CODE` | 地图安全代理配置，保留在后端 |

当前本机使用 Windows 用户环境变量；更换电脑需要重新配置。`.env.example` 是空值模板，程序不会自动加载 `.env`。可用 `python start_local.py --offline` 检查离线页面，但这不验证真实接口可用性。

## 目录

| 位置 | 内容 |
| --- | --- |
| `src/` | 规划、旅程状态、重规划、Provider 与 Web 业务逻辑 |
| `frontend/` | HTML、CSS、JavaScript，以及网站实际使用的图片与文案 |
| `data/` | 生产 POI、身份映射、空间配置、图片清单及历史数据证据 |
| `tests/` | Python 测试 |
| `frontend/tests/` | 前端测试 |
| `tools/demos/` | CLI 演示入口，保留历史验证用途 |
| `tools/evaluation/` | 自然语言动作评估工具 |
| `scripts/` | 审核、图片导入、数据处理、浏览器检查和阶段导出脚本 |
| `examples/` | 演示输入、测试证据、审核文件与历史验收产物 |
| `materials/` | 本机原始照片、Word 文案与设计参考；仅提交目录说明 |
| `docs/` | 使用说明、接口约定、阶段历史和整理记录 |

运行代码、生产数据和已发布的页面资源保持原路径。原始素材与网页资源是两套文件；只改 `materials/` 不会自动更新网站。见[素材说明](materials/README.md)及[内容填写指南](frontend/CONTENT_GUIDE.md)。

## 开发与测试

前端使用原生 JavaScript ES Modules，后端为 Python 标准库 HTTP 服务。项目不依赖 React、Vite 或 FastAPI。

开发期间先运行改动相关的测试，例如：

```console
python -m unittest tests.test_form_supplement tests.test_web_frontend_api tests.test_web_arrival
node --test frontend/tests/*.test.js
```

前端测试需要 Node.js；普通网站运行不需要 Node.js。完整历史回归仅在阶段稳定、准备验收或冻结时运行。实时 API 测试需要单独决定，不作为每次整理或补图的默认步骤。测试政策见 [AGENTS.md](AGENTS.md)。

## 文档与工具

- [文档索引](docs/INDEX.md)
- [CLI 工具用法](tools/README.md)
- [维护脚本说明](scripts/README.md)
- [目录整理记录](docs/maintenance/ORGANIZATION_20261017.md)
- [Smart Start 撤回记录](docs/maintenance/SMART_START_ROLLBACK.md)
- [第三方素材与服务说明](THIRD_PARTY_NOTICES.md)

Cloudflare 临时部署文件已移除。旧版本副本已归档到项目外，位置记录在整理报告中。当前没有配置替代的公网部署，Git 已初始化；首次提交前按 `.gitignore` 排除本机素材与生成文件。

## Git 提交范围

原始素材 `materials/` 仅保留目录说明；照片、Word 文案和设计参考不上传。已导入的 `frontend/assets/`、`frontend/content.json` 和生产数据正常提交，克隆后无需原始素材即可运行网站。重新导入素材时需自行补齐本机原文件。

流水线缓存、检查点、历史 ZIP、生成截图和常见测试日志仅保留本机。历史报告提及的这些产物可能不包含在克隆中；依赖冻结 ZIP 的历史审计脚本需要另行提供原归档。人工审核、测试输入、Schema 和基线 JSON 保留，不整体忽略 `data/` 或 `examples/`。
