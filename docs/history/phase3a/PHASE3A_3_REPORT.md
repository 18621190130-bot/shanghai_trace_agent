# Phase 3A-3 — Conversational State Update

**PHASE 3A-3 STATUS: PASS**。2026-10-05。全量 **506 tests in 29.509s，0 failures / 0 errors**（原437＋新增69）。Production59未变。Phase3A整体未完成；停止等待人工验收，不进入3A-4。

## 1. Existing provider/parser audit

已有LLMClient.structured_parse接口接收system_prompt/user_text/schema/validation_feedback。DeepSeekLLMClient使用当前进程DEEPSEEK_API_KEY、可选DEEPSEEK_MODEL（代码默认deepseek-flash）、JSON response_format、temperature0、thinking disabled和既有1200 token上限；API错误、截断、空内容及配置错误由LLMClientError保留kind/stage。MockLLMClient支持exact fixtures与队列，永不回退联网。

TripCommandParser复用parse_provider_json（完整JSON、可接受既有fence/prose容错）、intent_schema.validate_json/array/nullable/object_schema。原IntentParser使用严格schema＋有界validation_feedback重试；新parser收敛为最多两次provider调用，即一次初次解析、最多一次格式修复。原client、parser、schema validator和API契约完全未改。

Phase2 ClarificationLayer服务RouteIntent必填字段与初次规划；Trip阶段不复制其初次规划逻辑。新澄清只处理途中受限命令与地点确认，独立pending上下文，不把未执行意图写进TripState。

## 2. Conversational architecture

User text → existing provider → TripCommandParser → TripCommandProposal → deterministic normalization/validation → TripPOIResolver → Core action / TripStateDelta / read query → existing TripService / 3A-2 ReplanningCoordinator → TripTurnResult → deterministic explanation。

TripState仍是状态authority，RouteEngine仍是唯一路线authority。对话层不选择/排列POI，不计算推荐分、不写角色或版本。组合表达只产生一次delta和一次Coordinator调用。没有第二个DeepSeek client或第二个RouteEngine。

## 3. TripCommandProposal schema

command_type为core_action/replan_change/read_query/ambiguous/unsupported。字段为core_action、remaining_minutes、可选elapsed_minutes、pace、add/remove_interest_tags、add/remove_avoid_tags、must_go_place_mentions、place_reference、read_query、request_replan、needs_clarification、clarification_reason、可选semantic_concepts。

core_action限complete_stop/skip_stop/update_elapsed_time；pace沿用quick/standard/deep；query限四项；taxonomy枚举直接引用production定义。additionalProperties=False。没有visited/skipped/current ID、active/original route、role、selected_zone、status写入、route_versions、history、revision或坐标输出字段。

## 4. Trusted/untrusted boundary

当前store快照是trusted data；用户表达及provider候选是untrusted。只在JSON/schema、显式表达语义、taxonomy、地点确定性解析和现有domain/CAS验证之后执行。模型不能输出POI ID，也不能自由写route/state。必须引用用户原文中的地点名字；相对地点只能使用有限明确引用。protected字段/改角色/忽略规则等要求返回unsupported；provider输出保护字段直接invalid_command，不进行修复后执行。

## 5. Minimal LLM context

只给trip status、current logical stop双语名、接下来最多三个remaining名称、visited/skipped名称、当前interests/avoids、未完成必去名称、remaining_minutes、current pace、最新reason和allowed taxonomy。不传完整59库、POI ID、坐标、ordered route快照、versions、record或revision。用户提到库中其他点仍只让模型抽取raw mention；本地resolver随后处理。

## 6. Core actions

complete/skip/elapsed和偏好delta严格分开。complete当前逻辑点直接用TripService原状态方法；单独complete不重规划，最终站点完成仍沿用自动COMPLETED。skip先保存Core事实再重规划，随后失败也不回滚skip。Core冲突（如skip已visited点、操作已退出active的未完成点）返回core_action_conflict，不改state。

新增TripService.apply_core_action是很薄的revision适配：载入状态、比对解析所依据的revision、调用原complete/skip/update_elapsed，再使用原save_if_revision。没有改变Core事实定义。一个turn不执行两个互相独立的Core动作；冲突表达整体拒绝，不执行一半。

## 7. TripStateDelta mapping

偏好字段确定性映射为原TripStateDelta；must-go名字经resolver后才成为stable IDs。pace的“relaxed/take it easy”使用现有deep较长停留估计，不创建新字段，也不假装调整了实际步行速度。明确分钟/小时才允许budget；疲惫本身只改变pace或澄清。

当前已存在的interest/avoid、已取消的限制、已visited必去及不增加剩余预算的重复时间声明会过滤为有效无变化；不调用Coordinator制造新版本。兴趣扩展只处理本turn明确正向表达，复用原expand_semantic_concepts，绝不重跑original intent。原意图与原路线永久保留。

## 8. Compound command behavior

同句时间＋pace＋avoid＋interest形成一个delta，只调用一次重规划。“Skip this place, and I only have 45 minutes left”先确定全部proposal有效/地点唯一，再保存skip、reload新revision、一次Coordinator调用。若预算或组成不可行，skip保存、未提交时间和偏好保持旧值。0分钟版本测试明确覆盖该失败路径。

cached西岸中“one hour＋tired＋avoid museums”正确解析60/deep/museum_visit，并调用一次真实Coordinator；当前候选结构返回composition_gap而不提交。此结果是真实约束冲突，不能通过升级角色或塞入低质量节点伪装成功。

## 9. POI resolution

TripPOIResolver建立production59中英文name、aliases/alternate_names索引。精确→NFKC/大小写/标点规范化→高置信保守模糊匹配。fuzzy要求相似度≥0.90；与最佳差距小于0.08的多候选返回ambiguous，不自动挑一个。短名称不模糊猜测。明确“old residence/故居”等泛称列出库中相应居所候选。

结果区分resolved/ambiguous/not_found/invalid_for_trip；non-selectable/internal不会进入执行。跨区/时间可行性不由resolver或LLM决定，仍交给原3A-2。不存在的名字不会触发地图或互联网补点。

## 10. Relative reference behavior

this stop/this place/here/next stop/the next one/下一站都映射current_poi_id，即下一可执行logical stop。它不表示GPS位置，也不是remaining[1]。that place及复杂discourse不猜测，要求澄清。命名Core操作可指用户明确提到的可执行点，domain仍拒绝visited/skipped冲突或非active未完成点。

## 11. Clarification behavior

PendingTripClarification以独立InMemoryTripConversationStore对象保存proposal、原文本、目标字段/索引、显示名称选项及绑定revision。没有TripState pending字段，没有未确认事件。第一轮old residence返回多个候选；第二轮B.、编号或名称确定候选后继续原始command，不再让LLM猜ID，保留原句剩余时间等字段。

unknown name可用第二轮明确production名称纠正。目标缺失可选择当前remaining名称。确认时重新验证原命令；等待期间任何trip revision改变会stale_state_conflict并清除过期pending。cancel只清除conversation pending，trip不变。**persistent conversation storage DEFERRED**。

## 12. Read-only queries

四项自然语言query均返回结构化query_type/value：show_original_route、show_current_route、show_route_history、why_latest_replan。只读取，零RouteEngine调用、零event/version增加。没有replan时why返回“No route changes yet”。中文/英文读取均有回归；read_query中混入mutations被整体拒绝。

## 13. Route history API

新增TripService.get_current_route/get_route_history/get_latest_replan_summary，复用已有get_original_route。history按v1/v2/v3排列，包含parent、created_at、reason、route_snapshot和关联ReplanRecord。所有读取使用防御性快照，调用者修改返回值不改变store。验收轨迹通过architecture→time reduction生成v2/v3，再读取why与完整版本历史。

## 14. Deterministic replan explanation

ReplanExplanationBuilder只读取已保存ReplanRecord.delta、真实effective budget、前后intent/version，以及对应旧/新route snapshot。headline/reasons/added_stops/removed_stops/kept_stops均由固定模板和集合差生成，没有第二次LLM回答。

比较旧可执行future与新future：record当时visited/skipped先排除，所以过去已visited的p29不会被虚构成因replan删除的stop。time60例kept p30，removed p42/p43/p5，added为空；理由为预算真实降到60。输出replan_id/version可追溯，pace说明只指既有估计，不能声称实时crowd、closed、weather、ticket或traffic。

## 15. Provider / mock / live mode

trip_chat_demo默认mock exact fixtures；--list-fixtures列出45条固定英文/中文输入，--help明确mock/live差别。--live复用原DeepSeekLLMClient，--text可单次，省略则从cached Trip开始交互；--json仅单次结构化输出。元数据明确“cached production fixture”，已保存首站visited/elapsed60。

固定smoke覆盖tired、one hour、no museums、architecture、skip、finished、Wukang Mansion、why、original、history等要求。同区West Bund Art Center例成功；Wukang例在西岸cached旅程中返回明确infeasible_must_go。未知mock文字不会偷偷联网。

本次自动化/人工mock验收 **0 live API调用**；提供显式live入口，但没有声称已经完成真实DeepSeek smoke。无key的live配置错误也被测试为provider_error/configuration_error，不产生state变化。

## 16. Error propagation

TripTurnResult包含status、command_type、parsed_command、core_action_result、replan_result、read_result、clarification、user_facing_summary、state_revision及error_code。原3A-2错误码完整保留；replan_failed只是turn类别，内部composition_gap/infeasible_must_go/must_go_conflict/invalid_delta/engine_failure仍可读取。stale_state_conflict不吞掉。

provider_error保留LLMClientError.kind/stage，错误文本沿用现有redaction。JSON/schema不合法最多一次format repair后parse_error；非法taxonomy/protected/矛盾类别/未明确时间/语义错误invalid_command且不修复。失败固定模板说明Core是否已保存、staged变更未保存，不以“something went wrong”压平诊断。

## 17. Prompt injection protections

受限schema无状态/路线写入字段；提供名称上下文而不提供生成ID列表；用户protected/角色改写/ignore rules请求拒绝执行；provider多余字段立即拒绝；minute budget、Core动作/目标、pace、tag主题和显式负向/撤销表达另行验证。

负向表达按同一主题子句验证，不能因句子别处说“no museums”就把正向architecture变成avoid。正向architecture不能暗推museum avoidance；museum was boring不能变成全局avoid；tired不能变成30分钟预算。格式修复保持同一原文，不能借修复猜地点或时间。后续domain和CAS仍是最后防线。

## 18. Integration tests

新增tests/test_trip_conversation.py **69 tests**。用户40类要求逐项编号覆盖，额外验证多轮B.、unknown→known保留compound、相对next语义、pending过期/取消、provider阶段stale、正负子句隔离、no第三次repair、read快照隔离、non-selectable、自动完成以及mock CLI JSON。

测试链路实际为MockLLMClient→TripCommandParser→TripStateDelta→真实3A-2 Coordinator→真实production RouteEngine→v2/v3。不是全部mock路线。CAS race故障注入仍调用真实引擎，仅在生成后另行保存进度。

## 19. Total regression

`python -m unittest discover -s tests -t . -q`：**506 tests in 29.509s，OK，0 failures / 0 errors**。原437项（Phase1/1.5/2/2.5/3A-1/3A-2）原样保留通过，新69项通过。全量输出见examples/trip_conversation/full_tests.txt；检查与hash证据见checks.json。

67个开始前基线文件核对：只有授权的两个薄适配src/trip_store.py、src/trip_replanning.py变化，其余65个一致。原RouteEngine、评分、semantic expansion、parser/provider、taxonomy、pipeline、production和zone config未变。11个场景JSON与CLI JSON已生成；history_and_reason包含v1→v2→v3及四类read。

## 20. Files modified

新增src/trip_commands.py（proposal/schema/parser/normalize/resolver）、src/trip_conversation.py（turn orchestration/pending/解释）、src/trip_command_fixtures.py、tools/demos/trip_chat_demo.py、tests/test_trip_conversation.py、docs/phases/PHASE3A_3.md、PHASE3A_3_REPORT.md及examples/trip_conversation/证据。更新README.md、docs/PHASE_MANIFEST.md。

必要薄适配：TripService增只读history接口及Core expected-revision执行；ReplanningCoordinator.replan增可选expected_revision，在load后立即拒绝LLM解析期间的过期上下文。未传参数的3A-2行为不变，原437测试证明兼容。没有修改TripState、原引擎或provider API contract。

## 21. Production hash

data/pois.json仍为 **59 POIs**，SHA-256完全一致：`6fe891c894995df9aaf9c1c8488d085178399e8cf6d22fe84a87c68e28018782`。没有discovery、enrichment、promotion或Phase2.5数据重写，West Bund仍13节点。

## 22. Known limitations

mock是固定样例，不具备自由NLP；live入口可用于人工DeepSeek smoke，真实抽取质量未在本次调用验证。语义grounding刻意保守，未覆盖的措辞/时间表达/复杂撤销指代可能拒绝或要求澄清，不猜测新预算/地点。仅支持一个Core动作；pending主要支持地点选择/名称纠正，泛化多轮discourse和复杂命令插队未实现，可cancel再提出新命令。

Conversation/TripStore均为进程内存；**persistent conversation storage DEFERRED**。没有初次自然语言规划到完整旅行的3A-4端到端demo。代表坐标、Haversine绕行和停留估计沿用，logical stop不是GPS；**DEFERRED TO PHASE 3B MAP ROUTING**。没有地图routing、实时天气/营业/crowd/票务、数据库、RAG、前端、语音。phase3A整体未完成。

## 23. Recommendation for Phase 3A-4

人工验收本阶段后，下一阶段再把既有初次RouteEntryService、start_trip、本对话服务、Core complete/skip、动态重规划、why/history与完成串成端到端Agent Demo。沿用本阶段结构化错误和pending隔离；不要让对话层代替规划authority、猜可行性或绕过CAS。本阶段立即停止，不提前实现3A-4/3B。
