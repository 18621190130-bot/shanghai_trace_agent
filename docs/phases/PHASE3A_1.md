# Phase 3A-1 — Trip State Core

状态：PASS。仅Trip State Core完成，Phase 3A整体仍在进行中。Phase 2.5 production保持59节点、已冻结。

## Existing model integration

审计`src/models.py`和`src/intent_models.py`：RoutePlan.status成功值为`success`，站点为`ordered_pois: list[RouteStop]`，身份字段`poi_id`，已审核角色为`effective_primary_role`。RoutePlan.to_dict额外提供两个距离/步行兼容alias。RouteIntent.to_dict/from_dict保留既有意图契约。TripState接收这些真实模型，通过JSON快照保存完整字段，不重写RoutePlan或重新评判最低三站、anchor/composition。空/失败/重复ID路线、未解析或时间不匹配意图会拒绝。

## Architecture and API

`src/trip_state.py`定义TripState、TripStatus、TripEvent、RouteVersion、ReplanRecord、TripStateDelta。`src/trip_store.py`定义TripStore Protocol、InMemoryTripStore和TripService。Core不import RouteEngine、LLM、地图或CLI。

```python
from src.trip_store import InMemoryTripStore, TripService
service = TripService(InMemoryTripStore())
trip = service.create_trip(route_plan, route_intent)
service.start_trip(trip.trip_id)
service.complete_stop(trip.trip_id, poi_id)
service.skip_stop(trip.trip_id, another_poi_id)
service.update_elapsed_time(trip.trip_id, 30)
service.get_trip(trip.trip_id)
service.get_original_route(trip.trip_id)
service.get_active_route(trip.trip_id)
service.get_remaining_stops(trip.trip_id)
service.get_journey_context(trip.trip_id)
service.serialize_trip(trip.trip_id)
service.abandon_trip(trip.trip_id)
```

TripState本身提供同一操作（无需trip_id）。Service按get→operation→save返回新状态；非法操作不保存。可直接调用状态对象操作，然后显式store.save。

## State machine

PLANNED→start→ACTIVE。ACTIVE→剩余为空且至少visited一站→COMPLETED。ACTIVE→abandon→ABANDONED。重复ACTIVE start不重置（False）；重复complete/skip同一处置为False且无事件，终态完成重试也幂等；与已处置相冲突会拒绝。COMPLETED/ABANDONED不得start，新进度操作要求ACTIVE。REPLANNING是保留enum，无进入/恢复接口。

所有stop都skip时保持ACTIVE、current为空，可显式abandon；不会将完全没走的路线称为完成。mixed visited+skipped且remaining为空则完成。

## Original versus active

original_route/original_intent是初始完整JSON snapshot；active_route/current_intent以独立深拷贝初始化。所有公开字段、route_versions及events是只读防御拷贝。修改输入模型、返回快照、active/current内部未来测试fixture均不会污染original或v1。本阶段只更新进度，active_route仍保留完整原sequence；get_remaining_stops是实际未处置视图。没有restore_original_route或新route生成。

current_poi_id是ACTIVE时active route第一未visited/skipped的logical_current_stop，并非GPS位置；PLANNED/终态为None。允许显式完成后面的站点，但current仍为首个未处置站。remaining由active_route+visited+skipped实时推导，不保存第二份可漂移的状态源。

## Events, versions and time

v1包含version_id/route_snapshot/created_at/reason=initial_plan，保留未来中间版本机制；现在只有v1。TripEvent为event_id/timestamp/event_type/payload；ID为trip UUID+递增事件序号，事件历史只追加。支持trip_started/stop_completed/stop_skipped/trip_completed/trip_abandoned以及elapsed_time_updated。相同ID、时钟及操作得到相同数据；默认UUID4/UTC时钟可注入测试值。时间戳必须带时区且不倒退。

original_minutes从初始意图的available_minutes继承，并与plan.request budget核对；不是RoutePlan预计游览后的remaining_minutes。elapsed由用户显式更新、非负有限且不倒退；remaining=max(0,original−elapsed)，超过预算仍保留真实elapsed并截断remaining为0，不自动结束。更新相同elapsed无事件。无计时器/剩余时间override。

visited/skipped不重复且不交叉，excluded为两者并集并按active顺序输出。must_go_remaining为尚未处置的必去站；显式skip视为主动放弃该站访问义务，事件记录was_must_go，context保留skipped_must_go_ids，不能误称已经完成。avoid_tags从current_intent派生。

## Journey Context and reserved delta

get_journey_context提供visited/remaining角色数组和计数、visited/remaining站数、has_visited_anchor及has_visited_anchor_or_supporting_count。未来不能只因remaining没anchor就忽略已完成anchor。这里只返回context，不改composition。

ReplanRecord预留reason/old_route_version/new_route_version/state_before/state_after/timestamp。TripState的replan_history目前必须空；未实现跨版本更新。

TripStateDelta定义remaining_minutes/pace、增删interest/avoid标签、增加必去ID、skip IDs、request_replan。schema+from_dict/validate校验非负有限时间、pace、boolean、未知字段、重复字符串、增删冲突；可传taxonomy/allowed_poi_ids做词汇与身份检查。独立delta未传词表时只验证结构，不推断实际tag有效性。本阶段没有apply_delta、LLM、自然语言解析或自动重规划。

## Serialization and store

TripState.to_dict→JSON→TripState.from_dict完整往返。from_dict重播事件，要求结果与序列化状态、派生字段、原始/v1/active/current完整一致；无依据的history改写、手改visited/status/time、未知事件和replanned状态会失败。仅一致性校验，不是密码学认证。当前序列化格式仅支持3A-1，未来实际replan及新schema需要显式迁移。

InMemoryTripStore.create/get/save/delete使用可验证快照；get返回独立TripState，需save才持久于进程内。重复ID拒绝。save要求original、created_at、v1不变，并要求已保存事件历史为新历史的完整前缀，拒绝过期/分叉保存。单进程内存实现，无数据库、跨进程事务或线程安全保证；后续存储可实现Protocol并加CAS，不改domain。

## Demo and acceptance

```powershell
python tools/demos/trip_demo.py
python tools/demos/trip_demo.py --route-fixture data/poi_pipeline/promotion/production_cli_4.txt
python -m unittest tests.test_trip_state tests.test_trip_store -q
python -m unittest discover -s tests -t . -q
```

Demo读取推广验收中已有成功EntryResult JSON，无新RouteEngine规划或provider调用。演示PLANNED→ACTIVE→完成首站→跳过下一站→original/remaining/events/context/JSON往返。其他fixture须为同一现有EntryResult schema并包含route_plan与intent。

24个新Trip测试、全部403测试通过。证据在`examples/trip_core/`；生产SHA-256保持`6fe891c894995df9aaf9c1c8488d085178399e8cf6d22fe84a87c68e28018782`。

## Next integration boundary

Phase 3A-2建议新增独立协调层：get_journey_context+excluded+current_intent+remaining_minutes→RemainingRouteRequest→既有RouteEngine；验证成功后原子登记新RouteVersion和ReplanRecord，仅替换active/current，永久保留original/v1与事件。首次规划规则不能直接套到剩余路线，应利用已完成journey context设计单独的途中规则。先定义失败不提交、must-go显式放弃语义和新version事务，再接生成器。本阶段没有实现这些。
