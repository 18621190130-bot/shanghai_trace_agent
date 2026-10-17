# Phase 3A-2 — Deterministic Dynamic Replanning

**PHASE 3A-2 STATUS: PASS**。2026-10-05完成；437 tests，0 failures / 0 errors。原403项全部通过，新增34项重规划测试。Production59与64个冻结文件哈希完全一致；Phase3A整体仍进行中，停止等待人工验收。

## 1. Existing RouteEngine audit

RouteEngine.generate_route接收既有RouteRequest（也兼容dict），返回RoutePlan；ordered_pois为RouteStop，序列化保留原字段及兼容别名。共享转换入口是intent_to_route_request；RouteEntryService负责初次自然语言/澄清/quality流程，途中不需要再次进入该入口。

时间available_minutes、max_walking_km、必去ID/访问模式/不可full_visit约束进入引擎；avoid_tags匹配三组标签，avoid_poi_ids匹配身份。初次引擎允许must-go覆盖avoid，途中协调器预先拒绝此冲突。兴趣/体验/文化标签保留原匹配和评分；crowd/environment属于既有静态偏好。起点使用start_lat/start_lng/start_coordinate_system，统一GCJ-02代表坐标。

初次preferred_zone由引擎选区逻辑处理；途中从当前active_route.selected_zone固定区，并验证输出不跨区。初次至少三站主要由入口route_quality判断；引擎末端执行组成诊断及bounded repair。错误通过RoutePlan.status/errors/relaxation_suggestions；协调器保留引擎诊断并转换为具体ReplanResult类别。

**Existing RouteEngine文件没有修改**。新增ContinuationRouteEngine薄适配器，仅途中延后最终组成检查到journey层；没有visited时调用完全原行为。未访问anchor且提案存在组成缺口时，请原RouteEngine执行既有组成修复；可行且通过journey政策才采用。候选质量、评分、停留、模式、插入、排列和预算计算均继承原实现。该适配不会将角色升级、修改POI或手写路线。

## 2. Replanning architecture

TripState → staged TripStateDelta → RemainingRouteRequest → existing RouteRequest → existing RouteEngine → in-trip validation → detached version/record/event → CAS save。TripState负责进度事实，引擎负责生成路线，Coordinator只适配、验证及提交。store中不暴露中间REPLANNING状态；失败不会留下半条路线。

## 3. ReplanRequest / TripStateDelta

复用3A-1 TripStateDelta，不新增重复schema。remaining_minutes、pace、add/remove_interest_tags、add/remove_avoid_tags、add_must_go_poi_ids、request_replan都确定性处理；类型、有限数值、重复、冲突及taxonomy/production ID使用原Delta验证。primary_reason使用六项枚举。request_replan=False为no_change，staged delta不提交。

complete_stop、skip_stop、update_elapsed_time仍由TripService/Core独立执行保存。Delta中的skip_poi_ids返回invalid_delta并要求先保存Core skip，防止把明确进度与可失败的提案混为一笔事务。

## 4. RemainingRouteRequest

独立模型保存zone、remaining_minutes、current_intent、excluded_poi_ids、must_go_remaining、logical_origin、journey_context、replan_reason。to_route_request克隆RouteIntent，设置整数预算、固定区、起点、必去及排除ID，再使用现有intent_to_route_request。active请求中的既有plan-only访问/偏好约束保留，不启动实时信息层。

## 5. logical_origin

从新到旧查找包含visited的版本，选择该版本路线顺序最后一个visited POI；不依照按钮点击顺序推断位置。无visited用logical current stop。坐标来自当前production代表坐标，诊断明确approximate/not GPS。**DEFERRED TO PHASE 3B MAP ROUTING**。

## 6. Excluded POI logic

get_replan_excluded_poi_ids返回跨全部历史版本的visited∪skipped，并进入RouteRequest.avoid_poi_ids。协调器复查新序列无交集。新发现的点完成后也加入全局历史；过去已访问的角色不会因active_route被替换而丢失。本阶段没有恢复visited/skipped动作。

## 7. Time-budget logic

effective=min(TripState.remaining_minutes, explicit override)，无override用当前remaining。现有整数RouteRequest采用floor，diagnostics记录budget_floor_minutes。成功提交remaining_budget_deadline=elapsed+effective，之后remaining=max(0,min(original_minutes,deadline)-elapsed)。因此override=120不能把当前80扩回120；后续elapsed增加仍扣除已缩减预算。

demo原180、elapsed60、当前120、override60，未来估计51.43分钟；返回一站success_shortened。零预算不生成假路线，失败override不改变已存预算。

## 8. Intent update logic

stage为current_intent防御性副本，add/remove保留既有标签顺序，新标签去重并确定排序；手动无变更不改标签顺序。只有通过全部校验和CAS才替换current_intent；original_intent永久不变。architecture测试验证新matched_tags中出现architecture，不固定某个地点名称。future避免museum不追溯过去已经visited的museum。

## 9. Must-go logic

保留当前未完成必去，新增ID须存在production且counts_as_route_stop/route_selectable。visited新增记already_satisfied；skipped新增返回must_go_conflict。跨区或未来avoid冲突返回infeasible_must_go；时间/模式/坐标不可行沿用引擎可行性结果并明确失败。未知ID返回invalid_delta。提案遗漏任一必去直接验证失败，不删掉必去重新偷偷规划。

## 10. In-trip Minimum policy

InTripPolicy计算visited_count+future_count，skipped不计入。至少一站未来且总数≥3有效；visited≥3时一或两站future有效；visited=2一站有效。visited=1、future=1且显式缩短/skip/改变限制，允许success_shortened。没有visited仍须至少三站。数量缺口不会通过加入无关、避让冲突或内部节点解决。

## 11. In-trip Composition policy

整段visited_roles+proposed_future_roles要求anchor≥1且anchor+supporting_stop≥2。已visited anchor可允许future无anchor；真实引擎生成的Places例验证visited p29后，future p38/p42两站通过。没有visited anchor时优先调用原引擎组成修复。所有可用anchor被avoid阻断时返回composition_gap；可保留proposal作为建议但committed=False。角色只能来自production审定primary role。

## 12. Transactional commit

所有staged修改、引擎调用和校验在脱离store的快照上完成。验证身份、坐标、角色、访问模式停留、匹配/avoid、must-go、固定zone、排除、原request、硬预算与引擎metrics一致性，然后构建version/record/event，最后一笔CAS保存。任何失败只返回ReplanResult，不写失败事件。原active/current/history完整保持；先保存的visited/skipped/elapsed事实不回滚。

## 13. Store revision / CAS

state_revision=1+事件数，每追加事件递增（一次Core完成可能生成完成站点及旅程完成两个事件）。TripStore新增save_if_revision；InMemory实现在锁内比较expected_revision，校验原始快照和历史前缀后替换快照。save同样使用载入revision，不能覆盖较新进度。测试在引擎生成期间另行保存skip，旧提案返回stale_state_conflict，新skip事实保留。

## 14. RouteVersion v2+

成功追加v2/v3，包含parent_version_id、route_snapshot、reason、created_at、effective_remaining_minutes。v1及已有版本前缀不可重写。active_route存最新规划版本，首次仍为初始计划快照；重规划后只包含未来序列。进度事实单独保存，remaining_stops始终过滤visited/skipped。

## 15. ReplanRecord

记录replan_id、timestamp、primary reason、old/new_route_version_id、完整delta、effective_remaining_minutes、visited_at_replan、skipped_at_replan及diagnostics。兼容3A-1的old/new_route_version别名和state_before/state_after；前后快照保存意图、版本、elapsed与remaining，不递归嵌套整段history。事件route_replanned保存reason/old_version/new_version及重放所需提案。失败/no_change不追加record/event。

## 16. Serialization upgrade

from_dict重放Core事件和route_replanned事件，核对v1/v2/v3、active/current、预算截止值、record、revision与派生字段。JSON往返完整；篡改版本parent或revision被拒绝。旧3A-1单v1无replan快照补充revision及v1的两个null字段，原route/intent值不变。该校验是内部一致性验证，非密码学认证。

## 17. Demo scenarios

`python tools/demos/replan_demo.py --scenario NAME`，可加`--json`。使用已缓存成功的production路线p29→p30→p42→p43→p5，不重新执行初次discovery/LLM。固定demo时间与trip_id支持确定性复现。

| Scenario | Delta / saved progress | Proposed future | Estimated min | Result |
| --- | --- | --- | --- | --- |
| time_reduced | visited p29, elapsed60, override60 | p30 | 51.43 | success_shortened / v2 |
| skip_and_replan | visited p29, elapsed60, saved skip p30 | p28→p42→p43→p5 | 118.62 | success / v2 |
| avoid_museums | visited p29, elapsed60, avoid museum_visit | p30→p42→p43 | 111.03 | success / v2 |
| add_must_go | visited p29, elapsed60, must p36 | p30→p36→p43 | 116.42 | success / v2 |

全部minimum/composition通过、committed=True、serialization_roundtrip=True。证据为examples/trip_replanning/同名JSON，内含before/result/after。

## 18. Tests

新增tests/test_trip_replanning.py共34项：用户要求的22类场景全部覆盖，另含already_satisfied、larger override/持久预算、visited2/3最小规则、legacy迁移、origin路线顺序、新发现站点完成、unknown tags/IDs、must/avoid冲突、非法引擎输出、角色/身份篡改、Delta skip契约及revision篡改。

用户场景与测试对应：1排除；2原始保留；3v2/active；4v3；5失败完整回滚；6visited anchor+future无anchor；7两站future；8initial语义；9time reduction；10future avoid；11过去museum；12interest/matched_tags；13feasible must；14time/cross-zone infeasible；15skip conflict；16CAS；17engine exception；18JSON v2/v3；19record；20事件前缀；21no_change；22全部disposed无fake route。组合场景包含真实production RouteEngine集成，故障注入只用于异常/竞争/恶意输出验证。

## 19. Existing regression

`python -m unittest discover -s tests -t . -q`：**437 tests in 22.491s，OK，0 failures / 0 errors**（403原有+34新增）。包含Phase1/1.5/2/2.5/3A-1的原始测试，未删改旧测试。

64个冻结文件与examples/trip_core/protected_before.json逐个核对，0变化，见examples/trip_replanning/protected_checks.json。覆盖原src核心、pipeline、zone config与production。Production59 SHA-256：`6fe891c894995df9aaf9c1c8488d085178399e8cf6d22fe84a87c68e28018782`。原RouteEngine SHA-256：`0e2fc008023a39f7282cd0e2344279dc5a3c4df7dfc195c38fed57269451383f`。未运行会覆盖旧报告的pipeline导出脚本。

## 20. Files modified

新增src/trip_replanning.py、tools/demos/replan_demo.py、tests/test_trip_replanning.py、docs/phases/PHASE3A_2.md、PHASE3A_2_REPORT.md和examples/trip_replanning/验收证据。更新src/trip_state.py（全局历史/预算/v2+/重放）、src/trip_store.py（revision/CAS）、README.md、docs/PHASE_MANIFEST.md。没有修改production、taxonomy、pipeline、初次引擎、parser、provider、clarification、semantic expansion、Phase2.5候选数据或评分权重。

## 21. Known limitations

InMemoryTripStore不跨进程/重启持久化；CAS保证本实现保存时的一致性，未来数据库store须实现同一契约。引擎仍是既有确定性启发式，不宣称穷尽所有可能续行；组成修复复用现有有界初次策略，未实现新的journey专用搜索。距离/时间是代表坐标、Haversine+绕行系数和产品停留估计，非道路routing或实测。当前active_route不会自动扣除用户的真实停留时间，elapsed须显式更新。相同序列/模式/pace且同意图同有效预算视no_change，不因分数或估计腿信息变化制造版本。

**DEFERRED TO PHASE 3B MAP ROUTING**。没有GPS、高德walking routing、天气、实时营业/拥挤/票务、新前端、语音、聊天或LLM自然语言delta。已有引擎静态access/warnings沿用，不代表查询实时服务。

## 22. Recommendation for Phase 3A-3

下一阶段只增加自然语言→既有TripStateDelta的受控adapter，复用本Coordinator和结构化失败结果。显式Core progress与staged偏好仍应分开；composition_gap/infeasible_must_go/stale_state_conflict需由对话层解释，不能让LLM自行改POI角色或绕过CAS。当前立即停止，等待人工验收；不提前实现3A-3或3B。
