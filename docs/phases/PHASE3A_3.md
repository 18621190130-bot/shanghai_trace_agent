# Phase 3A-3 — Conversational State Update

本子阶段 **PASS**；Phase3A整体仍未完成，等待3A-4。完整验收：[PHASE3A_3_REPORT](../history/phase3a/PHASE3A_3_REPORT.md)。全量506项测试通过（原437＋新增69）。Production59未变。

## 使用

默认是明确的离线 **mock exact fixtures**，只匹配固定示例，不进行自然语言推理，也不会自动调用真实API。初始路线来自 **cached production fixture**；已明确保存首站visited与elapsed60，当前逻辑地点为下一可执行站点。

```powershell
python tools/demos/trip_chat_demo.py --help
python tools/demos/trip_chat_demo.py --list-fixtures
python tools/demos/trip_chat_demo.py --mock --text "I only have one hour left."
python tools/demos/trip_chat_demo.py --mock --text "Skip this place." --json
python tools/demos/trip_chat_demo.py --mock
```

交互模式可依次输入固定样例，例如“I'd like to see more architecture.”、“Why did you change my route?”、“What changes have been made to my route?”。`quit`退出，`cancel`取消未确认澄清。地点澄清接受显示名称、编号或A/B等选项；不用手动输入POI ID。

显式live模式复用原DeepSeekLLMClient，需要进程环境变量DEEPSEEK_API_KEY；DEEPSEEK_MODEL可选。会调用收费API；本阶段自动化验收没有调用live。

```powershell
python tools/demos/trip_chat_demo.py --live --text "I'm a little tired and I only have one hour left."
python tools/demos/trip_chat_demo.py --live
```

`--json`只用于有`--text`的单次输入，结果包含mode、初始路线来源、TripTurnResult和state_revision。未知mock措辞会明确返回provider_error并显示mock模式，不回退到live。

## 控制链路

自然语言→已有provider→TripCommandParser→受限TripCommandProposal→deterministic normalization/POI resolver→Core action或TripStateDelta或read query→原TripService/ReplanningCoordinator→结构化结果→确定性解释。模型不能返回状态列表、POI ID/坐标、路线、角色、版本或revision。

Core complete/skip/elapsed直接调用原状态操作。skip先CAS保存，再重新加载状态进行一次重规划；失败保留skip、偏好delta不提交。单句Core＋时间/兴趣变更遵循同一顺序。一句多字段偏好只形成一个delta、一次Coordinator调用。

当前taxonomy节奏为quick/standard/deep；“take it easy/relaxed”映射deep的既有较长停留估计，不建立新的pace枚举，也不声称测量了实际步速。时间只能来自明确分钟/小时表达，疲惫或赶时间不能自动产生预算。

兴趣只对本次明确正向表达调用原semantic expansion；不重跑original/current意图。负向标签须有明确、同一主题子句的负面表达；“This museum was boring”不能变为全局avoid。明确解除约束才remove。

## 地点与澄清

TripPOIResolver仅使用production59的中英文名、aliases/alternate names；精确匹配、标点/大小写规范化匹配优先。模糊匹配要求高相似度与候选分差，多个合理结果返回ambiguous，未知返回not_found，不访问互联网补点。

“this stop / this place / here / next stop / the next one / 下一站”均指TripState.current_poi_id，即下一可执行站点，不是GPS位置。“that place”与复杂指代需要澄清。

Pending命令保存在独立InMemoryTripConversationStore；不写TripState或增加事件。确认名称/选项后继续原命令，保留其时间和兴趣字段，不让LLM重新猜地点。等待期间revision变更则返回stale_state_conflict。**persistent conversation storage DEFERRED**。

## 读取与解释

四类query：show_original_route、show_current_route、show_route_history、why_latest_replan。只读TripService新薄接口，不调用RouteEngine，不增加事件/版本。历史包含版本parent、时间、reason、route_snapshot及关联record。

ReplanExplanationBuilder从最新ReplanRecord的真实delta、预算与对应版本差异生成headline/reasons/added_stops/removed_stops/kept_stops。比较旧可执行未来序列与新未来序列，visited/skipped作为独立事实排除。解释不再调用LLM，不虚构实时拥挤、闭馆、天气或票务原因。

## 错误与验收

保留3A-2原始composition_gap/infeasible_must_go/must_go_conflict/invalid_delta/engine_failure/stale_state_conflict等错误码。失败解释采用固定模板，分别标明Core事实是否已保存、staged变更未保存。schema/JSON最多一次格式修复；非法taxonomy、保护字段和语义错误不修复或执行半个结果。

西岸cached例中“60分钟＋deep＋avoid museum”返回composition_gap，保持旧状态；“must Wukang Mansion”返回跨区infeasible_must_go。两者是正确保留产品约束的结果。时间单项、兴趣单项、回避、skip、complete、同区West Bund Art Center必去、中英文读取均有成功证据。

```powershell
python -m unittest discover -s tests -t . -q
```

证据在examples/trip_conversation/：11个场景JSON、CLI JSON、full_tests.txt、前后哈希checks.json。506 tests，0 failures / 0 errors。

没有自然语言初次规划→整段旅行的3A-4端到端demo，没有GPS、真实routing、前端、RAG、语音、实时信息或数据库。**DEFERRED TO PHASE 3B MAP ROUTING**。
