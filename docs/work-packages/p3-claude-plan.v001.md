# P3 仿真计划与派发提示词

2026-11-16，侧栏 Claude 原会话 54ab7bfe-2bca-4714-9759-e3ae3e5474e7，Sonnet 5.5 Medium。下列是可见回复正文。

P3 仿真阶段：计划、契约与提示词

以下为提议，我没有读过本机源码，也没有改动仓库。我已对照 spec 与 v2 原文核对：v2 3.3（230）、3.4（247）、3.6（269）、4.1–4.9（314–429），spec 4.2 的 Simulator（485–502），P3 行（555）。P3 在 P2 验收后才开工，不依赖求解器。

一、阶段划分与文件互斥

顺序 A → B → C：B 依赖 A 的真实类型，C 要接真实引擎并做一致性测试，所以不并行，每组之间文件互斥。

组	职责	允许写入
A 基础类型	状态机、事件与队列、日志、场景与抽样、YAML 默认配置	src/simulator/__init__.py（仅文档字符串）、states.py、events.py、queue.py、log.py、sampling.py、scenarios.py、config.py；tests/simulator/test_states.py、test_events.py、test_queue.py、test_log.py、test_sampling.py、test_scenarios.py、test_scenario_config.py；experiments/configs/scenarios/default.yaml；docs/work-packages/p3.md；docs/agents/handoffs/p3-a.md
B 引擎	运行时、Simulator、触发与合并冷却、重规划门禁、回放、指标	src/simulator/runtime.py、engine.py、trigger.py、gate.py、replay.py、metrics.py；tests/simulator/test_runtime.py、test_engine_order.py、test_engine_interrupt.py、test_engine_overrun.py、test_trigger.py、test_gate.py、test_replay.py、test_engine_scale.py、test_reference_stepper.py、stub_schedulers.py、reference_stepper.py（后两者为测试助手）；docs/agents/handoffs/p3-b.md
C 适配器	协议、Simulated、Manual，仅预留 Real	src/simulator/adapters/__init__.py、base.py、simulated.py、manual.py；tests/simulator/adapters/test_adapter_base.py、test_simulated_adapter.py、test_manual_adapter.py、test_runtime_conformance.py；docs/agents/handoffs/p3-c.md
独立 G3 只写		docs/agents/handoffs/p3-review.md
root 单写	进度、registry、RESUME、CHANGELOG、提示词归档、Git

条件限定：tools/check_import_boundaries.py 及新增的治理测试，仅当边界工具拒绝 simulator 依赖 scheduler_core.{models,validate,validation_context,io}，或拒绝 config.py 引入 yaml 时才做最小修改，且只放行 simulator/config.py 的 yaml，不加全局豁免。由 A 负责判断并说明。

禁止改：scheduler_core/*、io/*、generation*、P4–P8 的任何职责（重规划算法、影响域、诊断、Agent、前后端、实验评估、扰动强度预设）、依赖、docs/source。

二、契约 CB-P3（三组提示词与 G3 都引用）
# 1 时间与事件
Slot 为整数；事件键 (time, priority, seq)；seq 是引擎全局递增整数，入队时分配。
优先级（数小者先）：0 TASK_END；1 SETUP_END；2 DEVICE_RECOVER、MAINT_END；3 DEVICE_FAULT、MAINT_START；
  4 URGENT_ARRIVAL；5 TASK_OVERRUN；6 REPLAN_FLUSH；7 SETUP_START；8 TASK_START。
同槽语义：资源释放先于占用；故障与维护先于开工；故障恰发生在某任务结束的同一槽时，该任务不被打断（半开区间）；
  在 t 触发的重规划在 t 的全部扰动之后、同槽开工之前生效。
计划派生事件（SETUP_START、TASK_START、TASK_OVERRUN）批量入队的顺序固定为 (time, device_id, task_id) 升序。
run(t_end)：处理 time < t_end 的事件，结束后 clock = t_end；可续跑：run(a) 后 run(b) 与直接 run(b) 日志逐字节相同。
inject(ev, at)：at ≥ clock，否则 ValueError；DeviceOutage 要求 ev.start == at；UrgentInsert 的任务 release 取 max(release, at)；
  TaskOverrun 要求该任务在 at 为 RUNNING 且 new_end 大于当前预计结束；非法一律 ValueError，不入队。
事件失效：计划派生事件带 plan_epoch；采纳新计划只对 (设备、开始、结束、人员) 有变化的任务使旧事件失效并入队新事件；
  弹出失效事件时跳过，计入 stale_skipped，不写日志。
构造 Simulator(inst, plan, scenario, scheduler, seed)：先对初始 (inst, plan) 调用 validate，不通过 ValueError；
  初始任务只允许 PENDING 或 SCHEDULED；仿真从 inst.now 开始。

# 2 状态
DeviceState：IDLE、SETUP、BUSY、MAINTENANCE、FAULT、OFFLINE。设备持有计数 (running_demand, setups, down_causes 多重集)。
派生状态：有 FAULT → FAULT；否则有 OFFLINE → OFFLINE；否则有 MAINT → MAINTENANCE；否则 running_demand>0 → BUSY；否则 setups>0 → SETUP；否则 IDLE。
转移表 = v2 3.3 原表 + 最小扩展（U1，待用户确认）：BUSY→SETUP、SETUP→IDLE，以及 FAULT、MAINTENANCE、OFFLINE 两两互转。其余转移抛 IllegalTransition。
容量>1 的设备可同时运行多个任务（Σ demand ≤ capacity）。CLOSED 窗口只是日历，不产生状态变化。
中断（设备故障，或维护开始时仍有任务运行，U2）：对设备上每个运行中的任务置 INTERRUPTED，并生成重启副本 "<原id>~r<k>"（k 为该任务第几次中断，从 1 起）。
  不可抢占：计划工期等于原工期，实际工期重新取样（attempt+1）；
  可抢占：计划工期 = max(1, p − 已执行)，实际剩余 = 实际总工期 − 已执行（≥1，不重新取样）。
  副本 release = 当前 clock，status = PENDING，沿用 experiment、type、compatible、demand、skills、weight、deadline、preemptible；
  原任务的全部入边与出边复制给副本，原任务保留为历史；设备与人员立即释放。
任务状态：计划内为 SCHEDULED；开工 RUNNING（冻结设备与开始）；结束 DONE（记录 actual_start、actual_end）。

# 3 重规划交互
触发：事件驱动（DEVICE_FAULT、有任务中断的 MAINT_START、URGENT_ARRIVAL）；冲突驱动：
  A 超时：任务在 planned_end 仍在运行时发 TASK_OVERRUN（new_end=真实结束，每任务至多一次，U3）。
    构造"仅把该任务 end 延长到 new_end"的候选计划，用 validate（含上下文）判定：出现 V2、V3、V5、V6、V7、V9 任一违规 → 触发；
    否则采纳该候选为派生计划（id "<base.id>.ov<n>"，parent_id=base.id），不重规划。
  B 迟开：SETUP_START 或 TASK_START 时设备不可用或容量不足 → 记 START_BLOCKED，不开工，任务保持 SCHEDULED，并触发（U4）。
合并与冷却：首个触发在 t0 打开窗口，REPLAN_FLUSH 排在 t0 + delta_slots（默认 1，即 5 分钟）；窗口内事件并入同一批，按键排序。
  距上次重规划不足 cooldown_slots 则 flush 顺延到期；回调返回 None、被拒绝或内部失败 → 事件保留，重试时间 now+cooldown，
  连续失败超过 max_consecutive_failures 则记 REPLAN_ABANDONED 并保持当前计划。可选周期重规划 periodic_slots（默认 None）。
回调 scheduler(inst_post, plan, batch_events)：inst_post 是已应用本批事件的实例（工程约定，供 P4 对接）：
  now=当前 clock，任务状态与重启副本已更新，故障窗口已追加到 blocked（kind="FAULT"，start 为故障时刻，end 为恢复时刻，恢复时刻为场景已采样值，U3），
  紧急任务已追加；batch_events 仅供参考，调度器不得再次应用。回调异常原样上抛。
采纳门禁（独立校验）：validate(inst_post, new_plan, base=plan, free=None, context=ctx)；
  通过且 new_plan.parent_id == plan.id 才采纳，否则拒绝并记 REPLAN_REJECTED（含 code、reason 摘要）。
  ctx.snapshot：plan_id=base.id，as_of=clock，base_as_of=基础计划的采纳时刻；覆盖全部 RUNNING 与 DONE 任务：
    RUNNING：planned_end=base 中该任务 end，remaining_estimate=max(0, 已知结束−clock)，已知结束=已上报超时则 new_end，否则 planned_end；
    DONE：actual_end；event_id 取对应执行事件 id。
  ctx.end_changes：对超时延长且新计划 end 不等于 base end 的 RUNNING 任务，
    FrozenEndChange(plan_id=新计划id, base_plan_id=base.id, old_end, new_end, event_id=超时事件id, acted_at=超时时刻)。
  紧急任务与重启副本必须进入新计划（V1）；已完成与冻结任务不得被改写（V8、V10、V11）。
start_task(device_id, task_id, at) 在仿真中只校验其与当前计划一致并确认，不改变开工时间（开工由计划驱动）。

# 4 日志与回放
SimEventRecord：pydantic strict、frozen，按 kind 判别的联合，规范 JSONL（键排序、无 NaN）。通用字段 index、time、priority、seq、kind。
  类别：HEADER（seed、场景哈希、实例哈希、初始计划哈希、版本）；外生（DEVICE_FAULT 含 end、DEVICE_RECOVER、MAINT_START、MAINT_END、
  URGENT_ARRIVAL 含任务内容、INJECTED）；抽样（DURATION_SAMPLED：task_id、attempt、planned、actual）；
  状态（DEVICE_STATE、TASK_STATE）；重规划（REPLAN_TRIGGERED、REPLAN_CALLED、REPLAN_RESULT：adopted、rejected 或 none，
  adopted 时含完整规范计划及其哈希）；START_BLOCKED；REPLAN_ABANDONED。
随机：numpy Generator(PCG64(SeedSequence(seed, spawn_key=(流索引, 实体键…))))，纯函数，按键派生，不保留跨调用状态，因此与调用顺序无关。
  流索引只追加：durations 0（实体键 = 任务 id 的 sha256 前 8 字节整数与 attempt）、faults 1（设备序号、第 k 次）、
  repairs 2（设备序号、第 k 次）、urgent_times 3（到达序号）、urgent_content 4（到达序号）、persons 5（预留，P3 不启用）。
  开启或新增任一扰动不改变其他流的序列。故障与到达都是外生时间线，不依赖计划。
  spawn_key 对大整数的接受情况须在已装 numpy 上实测。
回放 replay(log, *, scheduler=None)：不创建任何 Generator，不重新抽样。
  scheduler=None：精确回放，重规划结果取自日志（含计划）；逐记录比较引擎重算与日志，首个差异抛 ReplayMismatch(index, 期望, 实际)；
    通过则返回与原 SimResult 相等的结果（日志字节、指标、最终计划哈希）。
  scheduler 给定：配对回放，复用日志中的外生事件与已记录抽样；未记录者按同一实体键从日志头的 seed 派生；比较不同算法。
抽样公式：实际工期 = max(1, floor(p·f + 1/2))，f 为对数正态因子截断到 [factor_min, factor_max]（默认 0.8 与 1.6）；
  修复时长 = max(1, floor(x + 1/2))。numpy 数值跨平台的末位差异可能影响取整边界，仅承诺同环境可复现，回放不受影响。

# 5 场景与指标
Scenario（strict、extra=forbid）：delta_slots、cooldown_slots（工程默认 6）、max_consecutive_failures（默认 3）、periodic_slots、
  duration_sigma、duration_factor_min、duration_factor_max；fault_enabled、mtbf_slots、repair_median_slots、repair_sigma；
  urgent_enabled、urgent_rate_per_day、urgent_task_range、urgent_slack、urgent_weight、urgent_chain。全部带范围校验；
  紧急任务内容从现有任务原型（类型、兼容设备、demand、技能）采样，id "u<k>-t<j>"，release=到达时刻，deadline=release+ceil(urgent_slack×CP)。
  扰动强度预设与评估协议属 P8，不在本阶段。experiments/configs/scenarios/default.yaml 与类型化默认值互锁，有漂移守卫测试。
SimResult：log、metrics、final_plan、final_instance、stale_skipped、counters。
metrics：events、replans（触发、采纳、拒绝、无解）、plan_deviation_mean（已开工任务 |实际开始−计划开始| 的均值）、
  realized_tardiness（DONE 且有截止期的 Σ w·max(0, actual_end−deadline)）、unfinished、interrupted、各设备 busy_slots 与 available_slots。

# 6 适配器协议（adapters/base.py，由 C 实现；B 的运行时按名称结构化实现）
DeviceAdapter：list_devices() -> list[Device]；get_status(device_id: str) -> str（DeviceState 的 value）；subscribe(cb: Callable[[SimEvent], None]) -> None   # spec 4.2
ControllableAdapter(DeviceAdapter)：get_calendar(device_id, start: Slot, end: Slot) -> list[CalendarWindow]；start_task(device_id, task_id, at: Slot) -> None   # v2 4.2
CalendarWindow：frozen，start、end、kind（CLOSED、MAINT、FAULT、RUNNING）。
RuntimeView（Protocol）：list_devices、device_status、calendar、add_status_listener、inject、confirm_start；Simulator 实现之。
SimulatedAdapter(runtime: RuntimeView)、ManualAdapter(runtime: RuntimeView)；回调异常包装为 AdapterCallbackError，中止 run，状态与日志保持到该事件之前一致。
ManualAdapter 另有 inject_outage、inject_urgent、inject_overrun，非法输入 ValueError。RealAdapter 只在 base.py 文档字符串中说明预留，不提供任何类。

# 7 可伸缩性
事件队列 heapq，每事件 O(log n)；每设备按开始时间有序索引，下一个任务与冲突检测 O(log n)；采纳计划时只对比变化的任务；
禁止按 horizon 逐槽循环、全量重建队列、O(n²) 配对扫描；日志写入通过可替换的 sink（默认内存列表）。
重规划成本由 validate 的 O(n log n) 与回调决定。
三、组 A 提示词（基础类型）
[附公共前言、增量 v002、契约 CB-P3 第 1、2、4、5 节] gpt-6.1-terra，high，fork_turns=none。
目标：实现 P3 基础类型，纯函数与纯数据，不含引擎。简单完整，函数约 20–60 行、文件约 150–300 行。完整类型与 docstring。不提交、不推送。
允许写入：见本组文件表。其余只读；禁止改 scheduler_core、io、generation、依赖；新增 skip 或 xfail；业务源码 import random。
先做：verify_source；读 spec 4.2 与 v2 3.3–3.6、4.3–4.7；读 scheduler_core 的 models（Event、Task、BlockedWindow 等）与 validation_context；
  运行 check_import_boundaries，判断 simulator 与 config.py 的 yaml 是否被拒；
  在已装 numpy 上实测 SeedSequence(seed, spawn_key=...) 对大整数键的接受情况与 PCG64 构造，结果记入交接单。
任务：
1 states.py：DeviceState、转移表（原表加 U1 扩展，扩展边单独标注）、由计数派生状态的纯函数、IllegalTransition。
2 events.py：EventKind、PRIORITY 表、SimEvent、StatusChange。queue.py：EventQueue（heapq，键 (time, priority, seq)，plan_epoch 惰性失效、stale 计数、批量入队的顺序助手）。
3 log.py：SimEventRecord 判别联合、规范 JSONL 序列化与严格解析（拒绝重复键、NaN、额外键、非规范字节）、日志哈希、ReplayMismatch 类型。
4 sampling.py：按键派生的纯抽样函数：actual_duration、next_fault_gap、repair_duration、urgent_gap、urgent_content，公式见 CB-P3 第 4 节。
5 scenarios.py：Scenario 与范围校验；config.py：YAML 加载（仅此模块 import yaml；SafeLoader 子类，拒绝重复键、锚点别名、自定义标签、多文档、非映射、未知键、yes/no 数值、NaN、bool 当数字）；
  experiments/configs/scenarios/default.yaml 与类型化默认值互锁。
6 docs/work-packages/p3.md：本阶段卡片，记录 A→B→C 顺序与 U1–U5 的待确认状态。
测试（断言到值）：
  states：全部状态对（6×6）逐一断言合法或非法；派生状态在计数组合下的结果；cap>1 的 BUSY→SETUP 与 SETUP→IDLE；叠加不可用原因的优先级。
  events/queue：同时刻不同优先级的顺序；同优先级按 seq；乱序入队结果相同；批量入队顺序助手；失效事件跳过与计数；pop 的确定性。
  log：往返字节相等；每种 kind 的正反例；重复键、NaN、额外键、非规范空白与键序被拒；哈希稳定；ReplayMismatch 字段。
  sampling：按键派生与调用顺序无关（打乱调用顺序结果不变）；改变一个流的参数不改变其他流；截断边界、取整、最小为 1；
    故障与修复序列的独立性；紧急到达第 k 个的内容只依赖 k；不使用全局随机状态（调用前后 numpy 全局状态不变）。
  scenarios/config：每个字段的边界与越界；严格类型；YAML 各类负例；默认 YAML 与类型化默认值互锁；无 yaml 导入于其他模块（AST）。
验收命令：uv run --python 3.11 --group dev python tools/check.py；pytest tests/simulator；布局与来源；git diff --check。基线以 root 提供的最新为准，不降。
交接：公共 H 格式，另附：numpy 实测、边界检查结论、转移表与 U1 扩展清单、行数表。
四、组 B 提示词（引擎）
[附公共前言、增量 v002、契约 CB-P3 全文] gpt-6.1-terra，high，fork_turns=none。前置：组 A 已验收合入。
目标：实现 Simulator 与重规划门禁、回放、指标。简单完整，职责分文件，函数约 20–60 行、文件约 150–300 行。不提交、不推送。
允许写入：见本组文件表。其余只读；禁止改 scheduler_core、io、组 A 与组 C 文件；实现 P4–P8 职责（重规划算法、影响域、诊断、Agent、实验）；新增依赖、skip 或 xfail。
接口：Simulator(inst, plan, scenario, scheduler, seed)；run(t_end)；inject(ev, at)；replay(log, *, scheduler=None)；
  另按 CB-P3 第 6 节提供 list_devices、device_status、calendar、add_status_listener、inject、confirm_start（供适配器结构化使用）。
先做：读组 A 代码与交接；读 validate 与 validation_context、ExecutionRecord、FrozenEndChange 的字段与语义。
任务：
1 runtime.py：设备与任务运行态、计数、转移应用、故障与维护中断、重启副本生成（含边复制）、事件应用到实例（FAULT 窗口、紧急任务）。
2 trigger.py：事件驱动与冲突驱动判定（超时用 validate 判定，迟开 START_BLOCKED）、合并窗口、冷却、重试与放弃、周期重规划。
3 gate.py：构造 inst_post、ExecutionSnapshot、FrozenEndChange 上下文；调用独立 validate；采纳或拒绝；派生计划（超时无冲突）。
4 engine.py：主循环、事件分发、计划采纳后只对变化任务更新后续事件、日志写入、run 续跑。
5 replay.py：精确回放与配对回放；metrics.py。engine.py 保持职责单一，不堆叠 gate 与 trigger 的细节。
6 测试助手：stub_schedulers.py（测试内的简单贪心调度器：保留冻结任务，其余任务按最早可行位置放置，遵守设备、准备、容量、阻塞、先后、release 与 now；
  每个输出用 validate 自检）；脚本化调度器（按预设时刻返回预设计划）；reference_stepper.py（独立的逐槽参考实现，仅用于微型场景，不 import 引擎）。
测试（断言到值；独立参考不复用引擎代码）：
  同槽顺序：TASK_END 与同槽 TASK_START（可连续开工）；故障恰在任务结束槽（不打断）；故障恰在开工槽（START_BLOCKED）；恢复与开工同槽（可开工）；
    MAINT_START 与 MAINT_END 相接；SETUP_END 与 TASK_START 同槽；优先级表逐对验证。
  状态与中断：设备状态序列与 DEVICE_STATE 日志；不可抢占重启副本（工期、release、边复制、实际重新取样 attempt+1）；
    可抢占续做（剩余工期、实际剩余不重新取样）；capacity=2 设备上两个任务同时被中断；维护开始仍有任务运行时中断（U2）。
  超时：无冲突时派生计划（id、parent）并不触发；设备冲突、后继 lag 冲突、截止冲突、人员冲突各触发；提前完成不触发也不回填。
  合并冷却：窗口内两个故障合并为一次回调且批次含两个事件；冷却顺延；回调返回 None 的重试与放弃；周期重规划。
  门禁：回调返回的计划若重叠、改写冻结或 DONE 任务、parent 不符、遗漏紧急任务或重启副本、违反 V7，均被拒并记录 code；合法计划采纳；
    快照与 FrozenEndChange 的各字段（as_of、base_as_of、planned_end、remaining_estimate、event_id）逐项断言；回调看到的是已应用事件的实例且不被修改。
  后续事件更新：采纳后失效事件被跳过、只有变化任务入队新事件（用计数断言），同槽新旧事件的顺序。
  确定性与独立：同 seed 日志字节相同、不同 seed 不同；开启或关闭紧急过程不改变故障时间线与工期样本；run(a)+run(b) 等于 run(b)。
  回放：精确回放与原 SimResult 相等；改动任一日志记录的字段，回放抛 ReplayMismatch 并指出首个差异下标；
    回放期间 numpy Generator 的任何抽样调用即失败（monkeypatch）；配对回放换调度器后外生记录序列与抽样值不变。
  参考步进器：≥100 个脚本化微型场景（含 setup、capacity、提前或超时完成、故障、脚本化重规划），引擎的设备状态序列、任务实际起止、DONE 与 INTERRUPTED 集合与逐槽参考一致。
  规模：horizon=10**9 的少量事件瞬时完成；2000 任务 50 设备的无扰动与单故障场景完成，并断言计数器：堆入队次数 O(n)、validate 调用次数等于重规划次数、
    没有逐槽循环；不以墙钟时间作通过条件（仅记录）。
验收命令同组 A；另 pytest tests/simulator 全部通过。基线不降。
交接：公共 H 格式，另附：门禁各拒绝路径的测试对照、参考步进器与引擎的差异（如有）、规模计数器表、U1–U5 对实现的影响。
五、组 C 提示词（适配器）
[附公共前言、增量 v002、契约 CB-P3 第 6 节] gpt-6.1-terra，high，fork_turns=none。前置：组 A、B 已验收合入。
目标：实现 DeviceAdapter 协议、SimulatedAdapter、ManualAdapter，仅预留 Real。不提交、不推送。
允许写入：src/simulator/adapters/{__init__,base,simulated,manual}.py；tests/simulator/adapters/{test_adapter_base,test_simulated_adapter,test_manual_adapter,test_runtime_conformance}.py；docs/agents/handoffs/p3-c.md。
其余只读；禁止改引擎与组 A、B 文件；提供 RealAdapter 类；新增依赖、skip 或 xfail。
任务：
1 base.py：DeviceAdapter 与 ControllableAdapter（Protocol）、CalendarWindow、RuntimeView、AdapterCallbackError、RealAdapter 的预留说明（仅文档字符串）。
2 simulated.py：只读门面与状态通知转发；get_calendar 合并实例阻塞窗口并按区间截取；start_task 仅校验与当前计划一致，不改变开工；回调按事件顺序通知。
3 manual.py：同上，并提供 inject_outage、inject_urgent、inject_overrun，参数校验后转发到 Simulator.inject，非法输入 ValueError，状态在引擎处理该事件前不变。
测试：协议结构一致性（真实 Simulator 满足 RuntimeView 与两个适配器协议，mypy 与运行时断言）；状态与日历查询与引擎一致；通知顺序与内容；
  回调异常 → AdapterCallbackError，run 中止且此前日志完整；过去时刻、start 不等于 at、未知设备、非运行任务的超时注入被拒；
  start_task 与计划不符被拒；API 表面中不存在 RealAdapter 之类的可实例化类；adapters 不 import numpy、random、yaml。
验收：同组 A；基线不降。交接：公共 H 格式，附协议与引擎的实际对应表、限制（start_task 不改变开工、Real 仅预留）。
六、独立 G3 提示词（仿真阶段整体）
[附公共前言、增量 v002、契约 CB-P3] gpt-6.1-terra，high，fork_turns=none。只读，只写 docs/agents/handoffs/p3-review.md；探针在仓库之外。
1 范围：各组 diff 只含各自允许文件；scheduler_core、io、依赖、docs/source 未变；P4–P8 职责未实现；无新增 skip 或 xfail；基线不降；
  条件限定的边界修改（如有）仅为最小放行且有治理测试。
2 状态机：对 6×6 转移逐对核对（原表与 U1 扩展分开标注）；cap>1 派生状态；叠加不可用原因；非法转移抛错。
3 同槽顺序：自行构造不少于 20 个同槽组合（任务结束与开工、故障与结束、故障与开工、恢复与开工、维护相接、setup 与开工、重规划 flush 与开工），
  对照 CB-P3 的优先级表与半开区间语义。
4 独立参考步进器：自写与作者无关的逐槽参考实现，对不少于 200 个脚本化微型场景比较设备状态序列、任务实际起止、DONE 与 INTERRUPTED 集合、重规划时刻。
5 重规划门禁：各拒绝路径（重叠、改写冻结或 DONE、parent 不符、遗漏紧急任务或重启副本、人员冲突）；
  独立核对 ExecutionSnapshot 与 FrozenEndChange 的每个字段；确认回调拿到的实例与事件应用一致且未被修改；
  确认超时冲突判定使用 validate 而非自写规则，提前完成不触发、不回填。
6 随机与回放：确认纯函数按键派生；开启或关闭紧急过程不改变故障与工期序列；不使用全局随机状态；
  精确回放逐字节一致，篡改任一记录被检出并指出下标，回放期间零抽样；配对回放保持外生序列与抽样不变；run 续跑一致。
7 规模：自行运行 2000 任务与 horizon=10**9 的场景，核对计数器（堆入队、validate 调用、无逐槽循环），记录耗时，不以耗时作通过条件。
8 适配器：协议与引擎的一致性；回调异常；Manual 注入的校验；不存在 Real 的实现；adapters 的依赖限制。
9 可读性与规范：模块职责与行数；无万能 utils；YAML 加载仅在 config.py。
10 复跑全部验收命令并记录真实输出。
结论 ACCEPT / REWORK / ESCALATE；发现列表（严重度、文件:行、证据、建议）；探针输出；未能核实项；模型、推理档、fork 模式。
七、需要用户确认的歧义（均有推荐；root 在 G1 前取得回复，回复"按推荐"即按本计划实施）
U1 状态机最小扩展。容量大于 1 的设备要有一个状态，叠加的不可用原因也要有互转，v2 3.3 的表不够用。推荐：在原表上加 BUSY→SETUP、SETUP→IDLE，以及 FAULT、MAINTENANCE、OFFLINE 两两互转，其余不变。
U2 维护窗口开始时仍有任务在运行。因超时可能出现。推荐：与故障同等处理，中断任务并保持窗口不变，这与校验器的日历语义一致。备选是推迟维护，但会让窗口与实例不一致。
U3 上报的精确性。故障的恢复时刻和超时的新结束时刻，调度器在上报时拿到的是真实值，超时每任务至多一次。推荐在 P3 采用精确上报，带噪估计和多次修订留作后续扩展。这会让重规划面对的不确定性比现实小，论文里要如实说明。
U4 迟开任务。计划开始时资源不可用。推荐严格按计划驱动，不自动补开工，记 START_BLOCKED 并触发重规划，失败按冷却重试。备选是资源就绪即开工，会改变计划偏差指标的含义。
U5 人员缺席。推荐推迟：Event 联合没有该类型，调度器无从得知，要加就得改 P1 契约，本阶段只预留流索引。
八、已由工程方定下的接口约定

这些不需要你确认，但 P4 要对接：

回调收到的是已应用事件的实例，events 仅供参考。
派生计划的 id 与 parent 规则。
新增 SETUP_START 与 REPLAN_FLUSH 两个内部事件。
run(t_end) 为半开区间且可续跑。
start_task 仅确认不改变开工。
冷却默认 6 槽、合并窗口默认 1 槽，均为工程默认，P8 可覆盖。

流程：root 审 G1，按 A→B→C 逐组派发，最后一次独立 G3，G5 由 root 提交推送。

提醒：重规划算法本身仍是 P4。P3 的测试用调度器只是测试助手，不作为交付的调度实现；如果其代码量显著膨胀，应停下上报，不要变成事实上的 P4。
