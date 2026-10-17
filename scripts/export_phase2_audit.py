"""Export reproducible mock-based Phase 2 acceptance cases and source contracts."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.demos.route_entry_demo import render_result
from src import POIRepository, RouteEntryService, RouteIntent, RouteMode
from src.intent_models import FeasibilityAction
from src.intent_parser import SYSTEM_PROMPT
from src.intent_schema import route_intent_schema, candidate_schema, CLARIFICATION_SCHEMA
from src.llm_client import MockLLMClient
from src.mock_examples import PLAN_EXAMPLES


def export():
    repo = POIRepository()
    service = RouteEntryService(repo, MockLLMClient(fixtures=PLAN_EXAMPLES))
    cases = {
        "P1 Architecture and local neighborhoods": service.generate(service.parse_plan(next(iter(PLAN_EXAMPLES)))),
        "P3 Relaxed literary walk": service.generate(service.parse_plan("I want a relaxed literary walk around Lu Xun's neighborhood for two hours.")),
        "M1 Wukang Mansion and Jianyeli": service.generate(service.places_intent(["Wukang Mansion", "Jianyeli"], 180)),
        "M2 Three distant areas in two hours": service.generate(service.places_intent(["Wukang Mansion", "Yu Garden", "Lu Xun Park"], 120)),
        "S1 West Bund": service.generate(RouteIntent(RouteMode.SURPRISE_ME, start_location_text="West Bund", available_minutes=180, surprise_seed=42)),
        "S2 Hongkou": service.generate(RouteIntent(RouteMode.SURPRISE_ME, start_location_text="Hongkou", available_minutes=120, surprise_seed=42)),
    }
    before = service.parse_plan("Plan a walk for me.")
    after = service.clarification.answer(before, {"available_minutes": 180, "interest_tags": ["architecture", "local_life"]})
    clarification_result = service.generate(after)
    m2 = cases["M2 Three distant areas in two hours"].intent
    proposals = service.feasibility.suggest_subsets(m2, FeasibilityAction.HELP_ME_CHOOSE, ["p13"])
    from dataclasses import asdict
    output = ROOT / "examples" / "phase2"
    payload = {"provider": "MockLLMClient: exact fixtures, no actual LLM inference or API calls",
               "cases": {name: result.to_dict() for name, result in cases.items()},
               "clarification": {"before": before.to_dict(), "answers": {"available_minutes": 180, "interest_tags": ["architecture", "local_life"]}, "after": clarification_result.to_dict()},
               "help_me_choose_after_explicit_selection": [asdict(p) for p in proposals],
               "original_selection_after_suggestions": m2.must_go_poi_ids}
    (output / "phase2_routes.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (output / "phase2_manual_routes.txt").write_text("Offline mock acceptance examples; not real API parser results.\n\n" +
        "\n\n".join(name + "\n" + render_result(result, repo) for name, result in cases.items()) + "\n", encoding="utf-8")
    for filename, schema in (("route_intent.schema.json", route_intent_schema(repo)),
                             ("clarification.schema.json", CLARIFICATION_SCHEMA),
                             ("llm_candidate.schema.json", candidate_schema(repo))):
        (output / filename).write_text(json.dumps(schema, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (output / "intent_system_prompt.txt").write_text(service.parser.system_prompt(), encoding="utf-8")
    lines = ["# ShanghaiTrace Phase 2 — Route Intent & Three Entry Modes", "",
        "交付日期：2026-10-03。Phase 2 输入层、三入口、澄清、可行性预检及受控惊喜策略已实现。现有 Route Engine 核心算法及 POI 数据未修改。没有进入 Phase 3。", "",
        "所有自然语言案例使用明确的 Mock fixtures，程序确实运行并生成了路线，但不能据此声称真实 LLM 解析准确率。DeepSeek 是唯一真实 Provider；HTTP 请求契约已用 Mock 测试，真实 API 尚未调用。", "",
        "## 1. 新增及修改文件", "",
        "新增：src/intent_models.py、intent_schema.py、location_resolver.py、clarification.py、intent_adapter.py、llm_client.py、intent_parser.py、mock_examples.py、feasibility.py、surprise_policy.py、route_entry.py；data/surprise_themes.json；tools/demos/route_entry_demo.py、tools/demos/chat_demo.py；.env.example；tests/test_phase2.py；scripts/export_phase2_audit.py；本报告及 examples 下的 Phase 2 验收输出。", "",
        "修改：src/__init__.py（导出新接口）、.gitignore（排除密钥文件）、README.md、CONTEXT.md。未修改 src/route_engine.py、recommendation_engine.py、models.py、data/pois.json 或旧测试。", "",
        "## 2. 三种入口共用一个流程", "",
        "```text\nPlan for me → IntentParser / LLMClient → 校验候选\nPlaces in mind → 分区目录勾选 → 稳定 POI ID\nSurprise me → 时间及可解析起点\n                 ↓\n             RouteIntent\n                 ↓\n        ClarificationLayer（每轮最多两题）\n                 ↓\n  必去点 FeasibilityChecker / SurpriseRoutePolicy\n                 ↓\n       intent_to_route_request\n                 ↓\n        Existing RouteEngine → RoutePlan\n```", "",
        "Plan for me 最低为时间＋任意一类偏好 Tag，未提供起点允许从首站开始；用户给出但无法解析的起点要补充。Places in mind 最低为时间＋已选地点，允许跨区勾选，不要求兴趣。Surprise me 最低为时间＋可用起点，不询问兴趣。", "",
        "## 3. 最终 RouteIntent 与 ClarificationRequest Schema", "",
        "完整机器契约：[RouteIntent JSON Schema](examples/phase2/route_intent.schema.json)、[ClarificationRequest JSON Schema](examples/phase2/clarification.schema.json)、[LLM candidate JSON Schema](examples/phase2/llm_candidate.schema.json)。使用严格 JSON Schema 子集本地校验，不依赖第三方运行库。拒绝额外字段、错误类型、未知 Tag/Zone/POI、不成对坐标及未知模式。派生的缺失项和问题每次重算，不信任客户端或模型提供的状态。", "",
        "visit_mode_overrides 沿用 Phase 1.5 能力；start_coordinate_system 防止混合坐标体系；surprise_seed 用于可复现。warnings 是诊断字段。未加入拥挤、票务、天气、交通或实时开放字段。", "",
        "```python", (ROOT/"src/intent_models.py").read_text(encoding="utf-8"), "```", "",
        "## 4. LLM System Prompt、Parser、Mock 与 Adapter", "",
        "提示词基础正文如下；调用时追加实际 pois.json 的 tag_taxonomy、四区定义及 candidate JSON Schema。[实际完整提示词](examples/phase2/intent_system_prompt.txt)。", "",
        "```text", SYSTEM_PROMPT, "```", "",
        "模型只提取显式偏好和必去地点名字，不输出坐标、路线或自选 POI。必去名字再通过本地目录解析。JSON/Schema 校验失败默认最多两次，配置上限三次；网络/认证失败立即明确返回，不循环请求。", ""]
    for title, file in (("IntentParser", "intent_parser.py"), ("MockLLMClient 与唯一真实 Provider", "llm_client.py"),
                        ("Intent → RouteRequest Adapter", "intent_adapter.py")):
        lines.extend([f"### {title}", "", "```python", (ROOT/"src"/file).read_text(encoding="utf-8"), "```", ""])
    lines.extend(["## 5. Places-in-mind FeasibilityChecker", "",
        "在补充推荐点之前，独立核算必去点：允许的最短停留＋估算最短开放路径＋原路线缓冲。同时输出涉及区域、区域跨度、跨区标记、距离上限、时间下限和三种操作按钮。默认模式若可用不主动缩短，minimum 只是允许降级后的下限，最终模式仍由既有 Route Engine 展示。", "",
        "最多12个必去点使用 Held–Karp 精确求解估算模型的最短开放路径。更多点使用 MST 下界及近邻候选；minimum_is_exact=false，并区分 search_inconclusive 与已证明超过预算。None 表示因缺坐标无法估算，不用0冒充已知。", "",
        "明显跨区的产品判据：跨区 POI 之间最大的估算距离超过3km，拦截为 transfer_required / walking_only_feasible=false。3km 是可配置的保守产品阈值，不是地铁数据，也不代表物理上绝对无法徒步；增加时间不会绕过该约束。相邻跨区且在阈值内的选择仍可按步行估算检查。", "",
        "只有显式 HELP_ME_CHOOSE 才生成 subset；原集合不变。建议按同区连续、保留数量、显式优先级和兴趣互补排序，最多三组。confirmed=True 代表调用方获得用户确认，CLI 会展示保留及删除项并要求 yes；还检查原集合和当前预算，拒绝过期或伪造 proposal。候选仅搜索同区子集，非全局最优删点算法。", "",
        "```python", (ROOT/"src/feasibility.py").read_text(encoding="utf-8"), "```", "",
        "## 6. SurpriseRoutePolicy", "",
        "有限七主题池见 [surprise_themes.json](data/surprise_themes.json)，启动时校验现有 taxonomy。根据起点筛可达区域和最短估算预算，再用共享 Adapter 和实际 Route Engine 检查每个主题，排除失败结果。优先最近可达区域、再选可行站数更丰富的主题，seed 的稳定 SHA256 仅用于平局；不同 seed 不保证改变路线。没有无约束 random 或 LLM 生成主题。", "",
        "```python", (ROOT/"src/surprise_policy.py").read_text(encoding="utf-8"), "```", "",
        "## 7. 六个实际程序案例", "",
        "完整每站模式、时间、距离、约束及警告见 [phase2_routes.json](examples/phase2/phase2_routes.json)，游客可读全文见 [phase2_manual_routes.txt](examples/phase2/phase2_manual_routes.txt)。以下为离线 Mock 输入→真实既有引擎执行结果，未将 Mock 冒充真实 LLM。", "",
        "| 案例 | 状态 / 主题 | 地点顺序 | 总计 / 预算 min |", "| --- | --- | --- | --- |"])
    for name, result in cases.items():
        plan = result.route_plan
        stops = " → ".join(n.name_zh for n in plan.ordered_pois) if plan else "原选择保留，未生成部分路线"
        timing = f"{plan.total_estimated_minutes:.2f} / {result.intent.available_minutes}" if plan else f"最低估算 {result.feasibility.estimated_minimum_minutes:.2f} / {result.intent.available_minutes}"
        lines.append(f"| {name} | {result.status}" + (f" / {result.surprise_theme}" if result.surprise_theme else "") + f" | {stops} | {timing} |")
    lines.extend(["", "M2 涉及三区，原 Wukang Mansion、Yu Garden、Lu Xun Park 均保留；没有偷偷替换或删点。只在显式请求 HELP_ME_CHOOSE 后建议子集。", "",
        "## 8. 一个澄清交互", "",
        "```text\nUser: Plan a walk for me.\nSystem: How long would you like to walk? [90 / 120 / 180 / 240]\nSystem: What are you most interested in? [实际 taxonomy，最多3项]\nUser: 180; architecture, local_life\nSystem: 最低信息满足 → 立即生成路线，无需继续收集画像。\n```", "",
        "实际 before、answers、after 全文保存在 phase2_routes.json 的 clarification 字段。此案例生成成功，总计 " + f"{clarification_result.route_plan.total_estimated_minutes:.2f} / 180 分钟。", "",
        "## 9. CLI 与真实 Key 配置", "",
        "```powershell\npython tools/demos/route_entry_demo.py\npython tools/demos/route_entry_demo.py --list-places\npython tools/demos/route_entry_demo.py --mode places_in_mind --places \"Wukang Mansion;Jianyeli\" --minutes 180\npython tools/demos/route_entry_demo.py --mode surprise_me --start \"West Bund\" --minutes 180 --seed 42\n```", "",
        "默认 tools/demos/route_entry_demo.py 无任何真实 API 调用，Plan 输入仅支持 src/mock_examples.py 中公开列出的精确句子；任意其他自然语言会明确提示没有 fixture。真实自然语言使用 tools/demos/chat_demo.py。", "",
        "```powershell\n$env:DEEPSEEK_API_KEY = '你的真实Key'\n$env:DEEPSEEK_MODEL = 'deepseek-flash'\npython tools/demos/chat_demo.py --mode plan_for_me --text \"I have three hours and want old architecture and local neighborhoods.\"\n```", "",
        ".env.example 是配置示例，程序不会自动读取 .env；环境变量必须由终端或部署环境注入。真实 Key 不写入代码、输出、报告或前端。.gitignore 排除 .env 与 .env.*，仅保留示例。tools/demos/chat_demo.py 的 Places/Surprise 不需要也不调用 LLM。", "",
        "真实接口采用 DeepSeek /chat/completions、JSON object 输出、30秒超时、1200 output tokens、temperature=0，本地仍严格校验结构。配置模型名称可通过环境变量覆盖。接口依据：[DeepSeek JSON Output 文档](https://api-docs.deepseek.com/guides/json_mode/)、[Chat Completions 文档](https://api-docs.deepseek.com/api/create-chat-completion/)。", "",
        "## 10. 全部测试", "",
        "测试使用 Mock fixtures 和模拟 HTTP response，所有 Phase 2 测试默认阻止真实 urlopen；子进程仅启动离线 tools/demos/route_entry_demo.py。保留并运行 Phase 1 / 1.5 原68项测试，新增49项 Phase 2 测试（包含 P1–P3、M1–M3、S1–S3、澄清、Schema、失败边界和 CLI）。以下为2026-10-03实际运行记录；导出脚本不代替运行测试。", "",
        "```text\npython -m unittest discover -s tests -t . -q\nRan 117 tests in 6.098s\nOK\n```", "",
        "## 11. 当前限制", "",
        "- 真实 LLM 的理解正确性和端到端网络服务尚未验证；Mock 只验证结构和控制流程，不能证明真实解析质量。", "- JSON Mode 保证 JSON 形式，不保证语义忠实；应用校验不能证明模型正确理解了用户意思。展示 Parsed Intent 便于审核。", "- 起点只做目录中英文名称/别名和区域名精确匹配，不做模糊匹配或外部地址解析。People's Square 当前不在目录，因此提示 unresolved external location，必须选择目录起点或显式坐标。", "- 区域名称使用一个代表 POI 的 medoid 近似锚点，不是游客真实位置；已有坐标精度和入口待核实的限制保留。", "- Plan/Places 可不提供起点，此时到达首站前的时间不计；Surprise 必须有可用起点。", "- 步行采用直线×绕行因子，不是地图导航，内部移动、真实道路、入口和围墙不识别。", "- 跨区3km阈值属于保守产品约束；无地铁、出租车、公交路径或换乘时间。", "- 预检 minimum 可以允许既有预算模式降级，最终 RoutePlan 必须保留 selected mode 与 downgrade_reason；大集合搜索、推荐插入和删点建议仍有启发式限制。", "- Surprise seed 仅平局时影响主题；候选区域与主题数量有限，不承诺每次新路线或全局最优。", "- 没有真实定位、天气、拥挤、票务、开放状态、实时交通、LLM路线生成、RAG、多Agent、数据库服务器、网页UI或用户账户。", "",
        "Phase 2 完成后停止，没有启动 Phase 3。"])
    report = ROOT/"docs/history/phase2/PHASE2_DELIVERY_REPORT.md"
    previous = report.read_text(encoding="utf-8") if report.exists() else ""
    repair_marker = "## Phase 2 First Repair"
    suffix = "\n\n" + repair_marker + previous.split(repair_marker, 1)[1] if repair_marker in previous else ""
    report.write_text("\n".join(lines)+"\n"+suffix, encoding="utf-8")
    print("Exported Phase 2 schemas, prompt, six cases, clarification and delivery report.")


if __name__ == "__main__":
    export()
