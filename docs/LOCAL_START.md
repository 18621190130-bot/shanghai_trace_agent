# 本地网站启动

双击项目根目录的 **Start_TraceMate.cmd**。程序会启动当前主目录中的网站，检查服务正常后自动打开浏览器。

- 需要 Python 3.10 或以上；无需安装额外 Python 包。
- 默认地址为 http://127.0.0.1:8765/；端口被占用时自动选择后续空闲端口，以启动窗口打印的网址为准。
- 默认保留原版 Developer Demo 的预设位置模拟，适合演示到达卡片。
- 使用期间保持启动窗口打开；按 Ctrl+C 停止服务。
- 地图、实时信息和自然语言功能使用本机已有 API 环境变量；启动程序不包含密钥。
- 本地网址只供这台电脑访问，不是公网链接。

命令行启动（在项目根目录）：

```console
python start_local.py
python start_local.py --standard
python start_local.py --port 8770
```

`--standard` 隐藏开发者模拟；`--offline` 用于断网界面检查；`--no-browser` 只启动服务。
