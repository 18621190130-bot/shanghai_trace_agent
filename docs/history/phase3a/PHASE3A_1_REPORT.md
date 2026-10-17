# Phase 3A-1 Trip State Core Report

## 0. Existing code audit

RouteIntent在src/intent_models.py，RouteRequest/RoutePlan/RouteStop在src/models.py；RoutePlan.status=success，ordered_pois保存RouteStop、poi_id稳定身份、effective_primary_role已审核角色。to_dict输出完整request及站点compatibility aliases。CLI使用RouteEntryService/EntryResult；本轮不复制新planning模型，以JSON防御快照包裹现有输出。

## 1. TripState schema

trip_id；original/current_intent；original/active_route；route_versions；visited/skipped_poi_ids；派生current/remaining/excluded/must_go_remaining/avoid_tags；original/elapsed/remaining_minutes；status；created_at/updated_at；event_history/replan_history。完整字段通过to_dict保存，from_dict回放校验。

## 2. State machine

PLANNED→ACTIVE→COMPLETED或ABANDONED。REPLANNING仅保留enum，无操作入口；非法转移明确TripStateError。ACTIVE重复start不重置。全部skip维持ACTIVE，显式abandon；visited至少1且remaining为空自动COMPLETED。

## 3. Original Route immutability

输入模型先JSON snapshot；original/active独立深拷贝；public属性是防御拷贝且禁止属性赋值。ordinary complete/skip/time不修改original，v1记录独立。测试修改输入、返回active快照及内部future fixture均不污染original。private内部不是安全沙箱，serialize/load/store会拒绝不一致状态。

## 4. Active Route semantics

保留完整现有RoutePlan sequence；progress由visited/skipped表达，get_remaining_stops筛除已处置站，不产生新路线。没有restore_original_route。

## 5. RouteVersion design

v1 / initial_plan / 完整初始route_snapshot / created_at。只读拷贝。Phase3A-1只有v1；后续协调层可追加v2，不覆盖初始，当前from_dict拒绝未实现版本变化。

## 6. TripEvent design

结构event_id/timestamp/event_type/payload；trip_started、stop_completed、stop_skipped、trip_completed、trip_abandoned、elapsed_time_updated。事件ID由trip_id+顺序确定，时钟可注入，timestamp带时区且不倒退；history只追加，无重写API。

## 7. visited / skipped rules

互斥、无重复；同一已处置操作False且无事件，冲突拒绝；unknown stop拒绝；excluded按active顺序表示visited∪skipped。可完成未来站但不跳过逻辑current。must_go_remaining剔除显式skip，skip event和journey context保留was_must_go证据。

## 8. Logical current stop

ACTIVE下第一个未visited/skipped的active站；PLANNED/COMPLETED/ABANDONED为None。全部跳过时ACTIVE但None。不声称物理GPS位置。

## 9. Time-state model

original_minutes为可用旅程预算，非plan预计游览剩余；elapsed非负有限且只递增，manual update；remaining=max(0,original−elapsed)。超预算不自动完成，无timer/override；未知输入含bool、NaN、inf和overflow拒绝且不改状态。

## 10. Original/current intent

复用RouteIntent序列化，初始化独立copies，原意图永久保留。current现在是防御视图，未开放偏好修改操作；future测试fixture证明current内部修改不污染original，但现阶段该变化不能未经event/version登记直接save。

## 11. Journey Context

visited/remaining角色与计数、站数、has_visited_anchor、has_visited_anchor_or_supporting_count及skipped_must_go_ids。专门测试anchor/support已走过且remaining无anchor仍保留旅程核心主题context。不调用composition judge。

## 12. Serialization

JSON roundtrip semantic equality；from_dict重新用现有RouteStop/RoutePlan/RouteIntent结构构建，再回放events并比较所有derived及stored字段，防止状态漂移。ACTIVE、COMPLETED、ABANDONED均往返；tampered event/status/time、未知replan和空invalid拒绝。不是签名认证或通用未来版本迁移器。

## 13. InMemoryTripStore

TripStore Protocol定义create/get/save/delete；实现只保存JSON snapshots、复制读取、save检查immutable originals和已有event完整前缀，过期/分叉保存拒绝。无DB/跨进程/线程锁；store.get后操作需save，TripService统一执行。

## 14. Core API

TripState.create/start_trip/complete_stop/skip_stop/update_elapsed_time/abandon_trip/get_original_route/get_active_route/get_remaining_stops/get_journey_context/to_dict/from_dict。TripService提供按trip_id的同名操作，以及create_trip/get_trip/serialize_trip。TripStateDelta.schema/from_dict/validate只验证结构及可选taxonomy/ID，不接LLM、无apply。ReplanRecord是未来记录契约。

## 15. CLI demo

`python tools/demos/trip_demo.py`使用既有production成功RoutePlan fixture，默认路径data/poi_pipeline/promotion/production_cli_4.txt；不新规划。输出PLANNED→ACTIVE，完成p29、跳过p30，original始终p29/p30/p42/p43/p5，remaining p42/p43/p5；三种事件及context、JSON往返True。可用--route-fixture指定现有EntryResult JSON。输出见examples/trip_core/check_2.txt。

## 16. Tests

24个新核心测试：原route/intent/versions隔离、start/idempotence、complete/skip/dual/excluded、out-of-order/invalid/terminal、时间、JSON/tamper、role context、v1、delta、unique/independent trips、store stale分叉、Service保存失败原子性与无engine调用。测试文件tests/test_trip_state.py、tests/test_trip_store.py。

## 17. Existing regression

`python -m unittest discover -s tests -t . -q`：**403 tests，0 failures / 0 errors**（379既有+24新增）。所有Phase1/1.5/2/2.5继续通过。Production59完全未变，SHA-256 `6fe891c894995df9aaf9c1c8488d085178399e8cf6d22fe84a87c68e28018782`。原src模块及zone configs通过逐文件哈希核对。未运行会重写旧pipeline报告的verify_all_zones；本prompt规定的full unittest已完整执行。

## 18. Files modified

新增src/trip_state.py、src/trip_store.py、tools/demos/trip_demo.py、tests/test_trip_state.py、tests/test_trip_store.py、docs/phases/PHASE3A_1.md、PHASE3A_1_REPORT.md、examples/trip_core验收输出。更新README.md与docs/PHASE_MANIFEST.md。未修改data/pois.json、POI Pipeline、Route Engine、RouteIntent parsing、provider、Clarification、Semantic Expansion、Minimum Viable/Composition或Zone Config。

## 19. Known limitations

单进程内存存储、无重启持久化；前缀校验不是线程事务；输入需既有成功且resolved的plan/intent，不重新审核规划质量；当前意图/route版本变更尚不支持保存。私有内部不作为公开mutation API；快照一致性非密码学认证。时钟/UUID默认环境相关、测试可注入；无GPS/LLM/replanning/live tools/UI。显式skip必去属于主动放弃访问要求而非完成。全部skip需用户明确abandon。

## 20. Exact recommendation for Phase 3A-2

先定义RemainingRouteRequest协调层及途中composition政策，输入当前意图、remaining_minutes、excluded、logical current与get_journey_context；旧initial minimum/composition不能机械只检查remaining。成功后事务登记RouteVersion+ReplanRecord与event，再替换active/current，保留original/v1；失败保持当前state不变。给TripStore增加版本/CAS契约与快照迁移后再接既有RouteEngine。不在此阶段开始实现。

## 21. Final status

**PHASE 3A-1 STATUS: PASS**。Trip State Core完成；Phase3A整体未完成。等待人工验收，不开始3A-2/3A-3、GPS、Amap routing、前端、voice或weather。
