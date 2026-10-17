# Smart Start 撤回记录

日期：2026-10-16。当前生效代码为项目根目录的 `src/`、`frontend/`、`data/`、`web_server.py`。

根据已独立保存、且包含后续修复的 `versions/before-smart-start` 恢复主目录：

- 撤回 Smart Start 起点比较、自动/手动翻转、接驳路线与相关 API。
- 撤回地图任意点击虚拟定位，保留原有 Developer Demo 预设位置模拟。
- 撤回附近地点动态地图绕行，恢复原版附近地点交互。
- 移除本次功能专属模块、测试、浏览器脚本和示例文件。
- 保留封面按钮上移、填写表单后自然语言补充需求不再重复询问、四个区块照片。
- 保留到达卡片、Cultural Bridge、what to notice、地点图片、路线编辑和历史、三种规划模式、结算、单位设置及原有地图功能。

恢复后 `src/`、`frontend/` 与基线对应文件逐字节一致；`data/` 全部文件的 SHA-256 在操作前后一致，原校验记录现位于 [rollback_data_hashes.json](../history/project/rollback_data_hashes.json)。保留主目录原有的历史测试和其它工具。

2026-10-17 目录整理补充：上述旧版本副本已核对后归档到项目外，当前使用主目录代码；详见 [目录整理记录](ORGANIZATION_20261017.md)。

撤回前受影响文件的压缩备份放在项目文件夹外、同级目录：`../TraceMate_before_SmartStart_rollback_20261016.zip`。备份不参与网站运行。

## 本地启动

新增 `Start_TraceMate.cmd`、`start_local.py` 和 `LOCAL_START.md`，运行主目录的实际代码。自动检测空闲端口，绕过系统代理检查本机服务，确认启动后打开浏览器；本地 HTTP 不继承公网 Secure Cookie 配置。默认启用原版 Developer Demo，可用 `--standard` 关闭。

## 验证

- 132 项相关后端测试通过：表单补充、Web API、到达、SDK、TripState、TripStore、重规划及反馈。
- 24 项前端测试通过：到达生命周期、翻译、图片、结算、单位等。
- 启动程序检查通过：真实服务就绪、占用端口回退、浏览器打开、主目录资源、本地 Cookie、四区块照片、子进程退出清理。
- Edge 浏览器检查通过：封面及 8 张照片、规划模式、4 张区块照片、区块内地点选择、58 个图鉴地点、点击 Logo 返回封面、手机宽度无横向溢出、无 JavaScript 错误。
- 未运行整个历史回归套件；没有调用线上 LLM 或高德数据 API。

未初始化 Git；可将当前主目录作为接下来版本控制的基线。
