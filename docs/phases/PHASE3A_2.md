# Phase 3A-2 — Deterministic Dynamic Replanning

本子阶段 PASS；Phase 3A 整体仍进行中。完整验收：[PHASE3A_2_REPORT](../history/phase3a/PHASE3A_2_REPORT.md)。不启动 Phase 3A-3。

`src/trip_replanning.py` 将 TripState 的已保存进度和 staged TripStateDelta 转为 RemainingRouteRequest，再通过原有 `intent_to_route_request` 调用既有 RouteEngine。路线通过旅程级 minimum/composition、身份、排除、负偏好、必去、时间与距离校验后，才 CAS 保存 active_route/current_intent/v2+/record/event。原路线、原意图和 v1 永久保留。

## 确定性 API

```python
from src.trip_replanning import ReplanningCoordinator, ReplanReason
from src.trip_state import TripStateDelta

# store / service 来自现有 TripStore、TripService；trip_id 对应 ACTIVE 旅程。
service.skip_stop(trip_id, poi_id)  # 显式进度先独立保存
result = ReplanningCoordinator(store).replan(
    trip_id,
    TripStateDelta(remaining_minutes=60,
                   add_avoid_tags=['museum_visit'], request_replan=True),
    primary_reason=ReplanReason.TIME_REDUCED,
)
print(result.to_dict())
```

`primary_reason` 六种值：manual_replan、time_reduced、preference_changed、avoidance_changed、must_go_added、stop_skipped。一个 delta 可表达多种变更。未传 delta 表示手动请求；明确传入 delta 时须设置 request_replan=True。Delta 内 skip 不做 staged 修改，必须先调用 Core API。

## 状态与约束

- visited ∪ skipped 跨所有历史版本全局排除；已经 visited 的新增必去记为 already_satisfied，skipped 必去返回 must_go_conflict。
- 固定当前 zone；跨区、无法访问模式、时间不够的必去返回 infeasible_must_go。不存在的 ID 或非法 taxonomy 返回 invalid_delta。
- effective = min(当前剩余时间, override)。现有 RouteRequest 只接收整数分钟，向下取整；提交后保存绝对预算截止值，继续扣除显式 elapsed 增量，不返还已用时间。
- logical_origin 使用最新包含已访问点的版本中，按路线顺序最后的已访问点；无 visited 使用 logical current stop。它不是 GPS。**DEFERRED TO PHASE 3B MAP ROUTING**。
- minimum 计算 visited+future；visited≥2 时一站可行续行有效。visited=1 且明确缩短或改变限制时，可返回 success_shortened 的一站续行；visited=0 仍须至少三站。
- composition 使用已访问角色+未来角色：anchor≥1、anchor+supporting_stop≥2。未来不必重复 anchor；过去的 museum 不受新 future avoidance 追溯约束。不能满足组成时返回 composition_gap，并提供未提交的 proposal。
- ContinuationRouteEngine 是薄适配器，途中将最终组成交给 InTripPolicy。若尚未访问 anchor 且提案缺少组成，额外调用原 RouteEngine 的既有组成修复，仍通过原预算和质量筛选。原评分、候选、几何、角色均未修改。没有 visited 时与原引擎输出相同。
- 成功更新 active_route 为最新未来规划版本；visited/skipped 独立历史不重新插入。随后完成或跳过仍通过 Core API；remaining_stops 是过滤进度后的视图。
- 失败与 no_change 不增加版本/事件，不提交 staged 变更；显式保存的 complete/skip/elapsed 保留。CAS 冲突返回 stale_state_conflict。

## 离线验收

项目目录中运行，使用已有成功路线 fixture 和 production59，不调用 provider：

```powershell
python tools/demos/replan_demo.py --scenario time_reduced
python tools/demos/replan_demo.py --scenario skip_and_replan
python tools/demos/replan_demo.py --scenario avoid_museums
python tools/demos/replan_demo.py --scenario add_must_go
python tools/demos/replan_demo.py --scenario time_reduced --json
python -m unittest discover -s tests -t . -q
```

四例的完整 before/result/after 快照在 `examples/trip_replanning/`，包含 v2、record、事件和 JSON 往返证据。全量437测试（原403+新增34）通过；production 与冻结核心哈希核对通过。

## 存储与边界

state_revision 随追加事件递增；InMemoryTripStore.save_if_revision 比较载入 revision，保存时检查原始快照、版本与事件前缀。from_dict 重放 Core/replan 事件并核对派生字段，支持 v2/v3，以及旧3A-1 v1快照的新增字段迁移。快照一致性校验不是密码学认证；仅单进程内存持久性。

所有距离与停留均沿用既有产品估计。没有 GPS、地图道路导航、LLM delta、自然语言、聊天 UI、天气、实时开放/拥挤/票务。原引擎继承的静态提示不代表查询了实时信息。
