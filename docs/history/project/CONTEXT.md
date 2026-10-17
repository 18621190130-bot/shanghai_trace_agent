> 当前状态：Phase 2 COMPLETE / FROZEN。以下保留历史上下文；当前入口与限制见 README.md、docs/phases/PHASE2.md。

# ShanghaiTrace City Walk

Phase 2 First Repair：非JSON Plan入口同进程持有意图，澄清回答按字段合并，不丢弃时间或偏好；JSON调用保持批处理。新增avoid_tags/avoid_poi_ids贯穿唯一Adapter与共享RouteEngine，可选点执行排除、必去优先。未能可靠表达的touristy/crowds保留为unresolved_negative_preferences和warning。仅低于65%预算利用率时做同区受限精修；estimated_max_single_leg_km仅诊断，不用于路线筛选，真实单段问题DEFERRED TO MAP API PHASE。143项离线测试通过；真实DeepSeek验收因当前执行环境无Key待验证。以下原始Phase2术语记录不代表本次修理未改引擎；本次只做上述授权的小范围修改，不进入Phase3。

当前阶段为 Phase 2 已实现：Plan for me、Places in mind、Surprise me 三种入口统一为 RouteIntent，再适配既有 RouteRequest。核心路线算法与27个地点不变。真实 LLM 仅提取意图，测试/默认CLI使用明确 Mock；不能用 Mock 结果声明真实语义解析质量。Places 必去点先预检，删点建议必须主动请求并确认；Surprise 只问时间和可用起点。跨区3km是保守产品阈值，不是交通事实。完整验收见 PHASE2_DELIVERY_REPORT.md。本阶段结束，不进入 Phase 3。

ShanghaiTrace 为上海城市漫步组织兴趣匹配的参访地点与行程。这里记录设计审查中已经确认的领域术语。

## Language

**必去点（Must-go POI）**：游客要求行程必须包含的地点；无法满足时，该请求不可行。
_Avoid_: 可选推荐点

**区域偏好（Preferred Zone）**：游客希望行程围绕的步行区域，是可以因必去点而让步的偏好。
_Avoid_: 指定区域硬约束

**行程时间预算**：从游客提供的起点出发到最后一个参访地点停留结束的可用时间；未提供起点时，从首个参访地点开始计算，不含末站后的返程。

**预计行程**：基于已有地点数据估算的漫步安排，包含移动、停留和缓冲时间。
_Avoid_: 已核验导航路线

**开放状态未核验**：地点在预计到访时刻是否开放尚未得到确认的状态。
_Avoid_: 默认开放

**环境偏好**：游客对室内或室外参访环境的倾向，可以因必去要求或候选条件而让步；混合偏好表示接受两类环境。
_Avoid_: 室内保障、室外保障

**跨区行程**：因必去点分属多个步行区域而需要跨越区域边界的漫步行程，包含区域之间的步行。
_Avoid_: 已含交通接驳的行程

**访问方式（Visit Mode）**：地点作为沿途短停（walk_stop）或主要游览目的地（full_visit）的访问方式；完整参访不意味着必须入内或购票。
_Avoid_: flexible、把 full_visit 当作 indoor

**旅行节奏（Travel Pace）**：游客选择的 quick、standard 或 deep 参访深度，与访问方式共同决定该节点的预计停留时间。

**显示编号（Display Order）**：用于向游客标识地点的目录编号，与稳定的内部地点标识区分。
_Avoid_: 以内部 pXX 作为地点序号

**区域型参访点**：以街道、街区或商圈整体为体验范围的地点，代表坐标是该体验区域的估算锚点，不是唯一位置。

**豫园参访点（p15）**：walk_stop 为豫园商城及周边街区，full_visit 为购票进入园林并包含周边游览；这是 Phase 1.5B 确认后的范围。

**模式降级**：完整参访不可用时，保留地点并改用其支持的沿途短停方式，仍需满足游客的时间和距离预算。
