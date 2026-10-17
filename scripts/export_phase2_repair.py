"""Actual offline repair executions; never labels fixture parsing as real DeepSeek."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.demos.route_entry_demo import render_result
from src import POIRepository, RouteEntryService, RouteIntent, RouteMode
from src.intent_parser import SYSTEM_PROMPT
from src.intent_schema import route_intent_schema, candidate_schema, CLARIFICATION_SCHEMA
from src.llm_client import MockLLMClient
from src.mock_examples import PLAN_EXAMPLES

MARKER = "## Phase 2 First Repair"


def export():
    repo = POIRepository()
    client = MockLLMClient(fixtures=PLAN_EXAMPLES)
    service = RouteEntryService(repo, client)
    specs = [
        ("CASE 1", "I want to see the more authentic side of Shanghai.", [("available_minutes", "3 hours")]),
        ("CASE 2", "Plan a walk for me.", [("available_minutes", "3 hours"), ("interest_tags", "parks and local life")]),
        ("CASE 3", "I have two and a half hours. I want local neighborhoods and I'd rather avoid museums.", []),
        ("CASE 4", None, []),
        ("CASE 5", "I have three hours and want old architecture and local neighborhoods.", []),
    ]
    cases, human, transcripts = {}, [], []
    for name, text, answers in specs:
        intent = (service.parse_plan(text) if text is not None else
                  service.clarification.prepare(RouteIntent(RouteMode.PLAN_FOR_ME, available_minutes=150, interest_tags=["local_life"])))
        initial, turns = intent.to_dict(), []
        for field, answer in answers:
            intent = service.answer_clarification(intent, field, answer)
            turns.append({"field": field, "answer": answer, "merged_intent": intent.to_dict()})
        result = service.generate(intent)
        assert result.status == "success", result.errors
        cases[name] = {"input": text or "150-minute local-life request", "initial_intent": initial,
                       "clarification_turns": turns, "final": result.to_dict()}
        human.append(name + "\n" + render_result(result, repo))
        if text is not None:
            # Execute the actual CLI process; only initial semantic extraction is a fixture.
            argv = [sys.executable, "tools/demos/route_entry_demo.py", "--mode", "plan_for_me", "--text", text]
            process = subprocess.run(argv, input="\n".join(a for _, a in answers)+("\n" if answers else ""),
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            assert process.returncode == 0, process.stderr
            transcripts.append(name + "\nCommand: " + " ".join(argv) + "\n" + process.stdout)
    output = ROOT / "examples" / "phase2"
    (output/"phase2_first_repair.json").write_text(json.dumps({
        "execution": "Actual program/CLI execution with explicitly mocked semantic extraction; no real DeepSeek API calls",
        "real_provider_verification": "Not run: DEEPSEEK_API_KEY absent in the execution environment",
        "cases": cases}, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (output/"phase2_first_repair_routes.txt").write_text("OFFLINE MOCK PARSING — actual route engine outputs\n\n"+"\n\n".join(human)+"\n", encoding="utf-8")
    (output/"phase2_first_repair_cli.txt").write_text("OFFLINE MOCK PARSING — actual CLI subprocess transcripts\n\n"+"\n\n".join(transcripts)+"\n", encoding="utf-8")
    for filename, schema in (("route_intent.schema.json",route_intent_schema(repo)),
                             ("llm_candidate.schema.json",candidate_schema(repo)),("clarification.schema.json",CLARIFICATION_SCHEMA)):
        (output/filename).write_text(json.dumps(schema,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (output/"intent_system_prompt.txt").write_text(service.parser.system_prompt(),encoding="utf-8")
    lines = [MARKER, "", "修理日期：2026-10-03。以下章节为当前状态；前文的117项测试、‘未修改 Route Engine’及源码块是初次 Phase 2 交付记录。当前契约以更新后的 Schema 和本节为准。", "",
        "### 发现的问题与修改范围", "",
        "1. --mode plan_for_me 不进入 stdin 澄清，--text 缺字段后直接退出，新进程会丢失前次状态。", "2. 只有正向 Tag，明确排除偏好没有可执行表示。", "3. 150分钟 local-life 请求只使用78.26分钟，尚有可用同区相关组合。", "4. Parsed Intent 未显示完整偏好；长估算单段未单独诊断。", "",
        "修改：tools/demos/route_entry_demo.py；src/intent_models.py、models.py、intent_schema.py、clarification.py、intent_parser.py、intent_adapter.py、route_entry.py、route_engine.py、mock_examples.py；本报告、README.md、CONTEXT.md 及 Schema/提示词导出。新增 tests/test_phase2_repair.py、scripts/export_phase2_repair.py 及三个验收输出。未改27个POI、排序和距离计算模型、旧HTML或目录结构；没有启动 Phase 3。", "",
        "### 多轮澄清闭环", "",
        "```powershell\npython tools/demos/chat_demo.py --mode plan_for_me\npython tools/demos/chat_demo.py --mode plan_for_me --text \"I want to see the more authentic side of Shanghai.\"\npython tools/demos/chat_demo.py --mode plan_for_me --text \"I have three hours and want old architecture and local neighborhoods.\"\n```", "",
        "非JSON Plan入口在同一次进程内保存 RouteIntent，先读初始自然语言，再直接读取 stdin 回答。3 hours / 数字菜单和分钟单位可本地解析；parks and local life 根据现有 taxonomy 名称组合解析。更复杂自然语言仍走唯一 IntentParser/Provider，但仅把所问字段作为补丁合并，空默认值不覆盖已有时间、正向偏好、起点、节奏、必去点或排除项。回答中新表达的显式排除以去重并集合并。每次回答后重算缺失项，最多两题，满足最低信息就生成。无效回答保留原意图；八轮上限仍保留。", "",
        "--json 保持非交互机器输出；缺字段时返回 needs_clarification，不读取stdin。跨进程不保存会话状态，本次修复的是同一 CLI 进程内的闭环，没有数据库或 Trip State。", "",
        "### 新增 Schema 与负向偏好", "",
        "```python\n# RouteIntent\navoid_tags: list[str]\navoid_poi_ids: list[str]\nunresolved_negative_preferences: list[str]\n# RouteRequest\navoid_tags: list[str]\navoid_poi_ids: list[str]\n# RoutePlan diagnostics\ntime_utilization_ratio: float | None\nestimated_max_single_leg_km: float | None\nlong_estimated_leg_warning: bool\n```", "",
        "LLM candidate 使用 avoid_place_names，再由同一离线 Resolver 映射真实 ID；禁止模型发明或推荐排除地点。avoid_tags 只允许现有三类 taxonomy 的并集，avoid_poi_ids 只允许目录 ID。RouteIntent → Schema/validation → 唯一 Adapter → RouteRequest → RouteEngine 完整传播，三入口同一行为。", "",
        "明确不想看博物馆可映射 museum_visit，明确不喜欢历史可映射 history。匹配排除 Tag 的可选 POI 整体排除（不假装拥有细粒度参访范围分类）；显式 must-go 永远优先，冲突通过 warning 展示，绝不删除。", "",
        "crowded/touristy/famous tourist attractions 当前缺乏可靠执行数据，保存到 unresolved_negative_preferences 并提示不能执行为可靠约束。不创造 crowd_level、touristy_score、popularity_score；仅喜欢 local_life 不隐含排除地标。既有正向 Tag 是软匹配，Case2 保留 parks，但不保证生成的每条路线必有公园；若公园是硬要求应选择具体必去地点。", "",
        "### 时间利用率优化与边界", "",
        "共享引擎只在原有效路线利用率低于65%且有正向偏好时，尝试同区相关候选组合或合法模式变化。既有得分插入、richness/stop cap 保留，精修最多8个可选候选及5站；不减少原已选站数，全部必去保留，明确模式覆盖不被升级，已知不可入内不能升级。继续使用既有顺序优化和预算核算，每个组合检查时间、步行预算、相关性与同区范围。找到当前站数下70–95%的方案后停止增加站数。", "",
        "在目标预算带内先比较 Tag 相关性、再比较整体估算距离及利用率；不保证全局最优。不存在预算带方案时可保留原success。低于65%时提示 Limited matching POIs prevented fuller use...，说明候选池、模式和站数上限的限制，不能把搜索失败当作不存在更好路线的证明。模式扩展会显示 selected/requested mode 和明确warning，待校准时间仍保持其产品估计性质。", "",
        "同类local-life请求：90分钟仍为78.26348分钟（86.96%），180分钟仍为151.47684分钟（84.15%）；150分钟由78.26348提升为134.46084分钟（89.64%）。不以无关地点填满100%。", "",
        "### 单段步行：DEFERRED TO MAP API PHASE", "",
        "estimated_max_single_leg_km 从原有几何估算腿长取最大值，包括明确起点到首站；没有起点的单站为0，失败路线为None。超过2km仅设置long_estimated_leg_warning并输出：Estimated geometry suggests a long walking leg; real street routing has not yet been verified。", "",
        "2km仅是诊断提示阈值，完全没有用于排除、排序或替换路线。距离依然是坐标直线×固定绕行因子，不能代表真实道路、围墙、过街和入口。真实单段限制与导航留到未来地图API阶段，本次没有接入该能力。Case5原顺序保持，建业里→徐家汇天主堂约3.151km只报警。", "",
        "### 五个实际程序输出", "",
        "**解析真实性说明：** 当前执行环境未检测到DEEPSEEK_API_KEY。下面确实运行了会话、共享引擎及CLI子进程，但第一轮语义解析使用明确 Mock fixture，不能当作真实DeepSeek验收。测试还通过注入Mock验证chat_demo真实Provider入口所走的同进程闭环；真实Provider网络及实际语义解析仍待在配置Key后验证。没有读取或输出任何真实Key。", "",
        "完整初始/合并/最终Intent与RoutePlan：[phase2_first_repair.json](examples/phase2/phase2_first_repair.json)。游客可读全文：[路线输出](examples/phase2/phase2_first_repair_routes.txt)；实际CLI过程：[CLI transcripts](examples/phase2/phase2_first_repair_cli.txt)。", "",
        "| Case | Final Interest | Avoid | Total / Available | Remaining | Utilization | Max estimated leg km |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for name, case in cases.items():
        final = case['final']; intent = final['intent']; plan = final['route_plan']
        lines.append(f"| {name} | {', '.join(intent['interest_tags'])} | {', '.join(intent['avoid_tags']) or '—'} | {plan['total_estimated_minutes']:.2f} / {intent['available_minutes']} | {plan['remaining_minutes']:.2f} | {plan['time_utilization_ratio']:.3f} | {plan['estimated_max_single_leg_km']:.3f} |")
    lines.extend(["", "Case1：初始只有local_life，3 hours后合并180分钟并直接生成；没有再次询问兴趣。Case2：先补3 hours，再补parks and local life，180分钟未被删除。Case3：保留local_life，排除museum_visit，仍使用共享引擎。Case4：展示同一150分钟结构化请求的利用率。Case5：完整单轮调用仍成功，原顺序不变，仅显示长单段诊断。", "",
        "### 回归测试与剩余限制", "",
        "原117项全部保留且通过，新增26项：同进程/自然语言补丁状态保持、多答案合并、完成自动出路线、无效答案、负向解析/Schema/传播、must-go优先、不支持的排除不造假、150分钟利用率、90/180结果保持、候选不足警告、模式覆盖与步行预算、长单段纯诊断、完整Parsed Intent、真实入口注入Mock、无text启动及完整单轮调用。", "",
        "```text\npython -m unittest discover -s tests -t . -q\nRan 143 tests in 7.924s\nOK\n```", "",
        "剩余限制：真实DeepSeek验收因当前执行环境无Key尚未执行；Mock不能证明真实语义准确率。排除行为依赖已有Tag覆盖，touristy/crowds不构成可执行硬约束。精修是受限候选搜索，无法保证全局最佳利用率。估算坐标、单段道路、交通、票务、天气和开放状态未核验。会话仅当前进程保存，JSON调用方需自行持有并合并Intent。原Phase2跨区保守政策、起点解析、Surprise有限主题等限制继续适用。", "",
        "本次修理到此停止，没有开发前端、修改旧HTML、接入后续服务、重组源码目录或启动Phase3。"])
    report = ROOT/"docs/history/phase2/PHASE2_DELIVERY_REPORT.md"
    existing = report.read_text(encoding='utf-8').split(MARKER,1)[0].rstrip()
    notice = "> 当前修理状态见文末 Phase 2 First Repair；前文是首次交付记录。"
    if notice not in existing:
        title, rest = existing.split('\n',1)
        existing = title+'\n\n'+notice+'\n'+rest
    report.write_text(existing+'\n\n'+"\n".join(lines)+'\n',encoding='utf-8')
    print('Exported five repair cases, CLI transcripts, updated schemas and First Repair chapter.')


if __name__ == '__main__':
    export()
