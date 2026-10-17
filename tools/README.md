# 命令行工具

网站启动使用根目录 `Start_TraceMate.cmd` 或 `python start_local.py`。这里保留独立 CLI 演示和评估入口，从项目根目录运行以下命令。

| 入口 | 用途 |
| --- | --- |
| `demos/demo.py` | 结构化路线请求与基础示例 |
| `demos/route_entry_demo.py` | 三种规划入口，默认使用离线 Mock |
| `demos/chat_demo.py` | 显式启用真实 DeepSeek 的规划入口 |
| `demos/trip_demo.py` | TripState 和历史路线 fixture |
| `demos/replan_demo.py` | 确定性重规划示例 |
| `demos/trip_chat_demo.py` | 途中对话，默认 Mock |
| `demos/trip_agent_demo.py` | 连续旅程演示，默认 Mock |
| `evaluation/nlu_live_eval.py` | 动作解析评估；`--mock` 为离线评估 |

```console
python tools/demos/demo.py --json
python tools/demos/route_entry_demo.py --mode surprise_me --start "West Bund" --minutes 180 --seed 42 --json
python tools/demos/trip_agent_demo.py --mock --scenario full_journey --json
python tools/evaluation/nlu_live_eval.py --mock
```

各入口可用 `--help` 查看参数，也支持通过绝对路径从其它目录启动；自己提供的相对输入/输出路径仍以命令执行目录为准。

Python 导入使用包路径，例如 `from tools.demos.trip_demo import load_fixture`。测试和阶段导出脚本已同步更新，根目录不再保留重复的 demo 入口。

真实模型模式和实时 API 工具会使用当前环境变量，可能产生接口费用；离线演示不代表真实接口验收。
