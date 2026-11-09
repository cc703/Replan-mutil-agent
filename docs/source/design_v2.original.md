# 面向多约束场景的任务动态调度与重规划Agent研究与实现
# —— 完整设计框架（v2）

> 应用场景：实验室设备共享与实验任务调度（作为多约束场景的验证场景）
> 技术路线：约束求解保证可行 + 稳定性感知重规划 + 人机协同智能体 + 仿真验证
> 本文件取代《毕业设计_项目设计文档.md》（v1）。相对 v1 的主要变化见 0.2。

---

## 0. 文档说明

### 0.1 阅读指引

| 章节 | 内容 | 对应论文章节 |
|---|---|---|
| 1 | 课题定位、研究问题、范围边界 | 绪论 |
| 2 | 总体架构与数据流 | 总体设计 |
| 3 | 领域模型、状态模型、数据库设计 | 需求分析与模型 |
| 4 | **仿真与设备适配层**（没有真实设备时如何描述状态） | 系统实现 / 实验环境 |
| 5 | 约束体系 | 调度模型 |
| 6 | **调度内核算法（重点）** | 算法设计 |
| 7 | Agent 设计 | 智能体设计 |
| 8–10 | 后端、前端、技术栈与工程规范 | 系统实现 |
| 11 | 评估方案 | 实验与分析 |
| 12–16 | 里程碑、风险、文献定位、论文大纲、范围控制 | — |

### 0.2 相对 v1 的变化

1. **新增仿真与设备适配层**（第 4 章）：用设备状态机 + 离散事件仿真 + 适配器接口解决"没有真实设备"的问题。
2. **新增状态模型**（第 3 章）：设备状态机、任务状态机、计划版本状态，区分"计划值"与"实际值"。
3. **算法细化**（第 6 章）：给出完整的 CP-SAT 数学模型、重规划细节（含运行中任务被打断的处理）、事件合并与触发策略、基线的公平性设计。
4. **评估增强**（第 11 章）：除单事件微基准外，增加**滚动仿真评估**（连续多事件），并给出指标公式。
5. **Agent 权限分级**（第 7 章）：L0/L1/L2 自主级别，把"人机协同"落到制度上。
6. **文献依据**（第 14 章）：纳入 2024–2026 年相关工作，并明确差异定位。

---

## 1. 课题定位与边界

### 1.1 一句话定位

> 设计并实现一个面向多约束场景的任务动态调度与重规划智能体：**约束求解器**保证计划可行、**稳定性感知重规划**应对动态事件、**大模型**负责需求解析与方案解释、**用户**参与约束确认与方案选择，并以实验室设备调度为场景，在仿真环境中通过对比实验验证。

### 1.2 本文对"Agent"的界定

本文的 Agent 不是"让大模型自己做规划"，而是一个**带权限分级的受控智能体**：

```
感知：用户自然语言输入、系统事件（设备状态变化、紧急任务）
推理：识别意图、抽取约束、判断是否需要澄清、选择工具
行动：调用求解/诊断/比较工具，向用户提出方案与解释
反馈：用户确认、选择、拒绝；仿真/设备状态更新
约束：所有改变正式计划的行动必须经过校验器与用户确认
```

### 1.3 研究问题（RQ）

| 编号 | 研究问题 | 对应实验 |
|---|---|---|
| RQ1 | 与大模型直接生成计划相比，"大模型 + 约束求解"能否保证硬约束可行并保持计划质量？ | E1、E2 |
| RQ2 | 在扰动重规划中，稳定性感知目标能否显著减少计划改动而不明显增加延期代价？ | E2、E3、E5 |
| RQ3 | 邻域扩张策略相对全量重排，在改动量与求解耗时上有何收益，是否损失可行性？ | E2、E4 |
| RQ4 | 自然语言约束抽取的可靠性如何，回译确认与校验能否降低误解风险？ | E6 |
| RQ5 | 解释一致性校验能否降低解释与求解结果不符的比例？ | E7 |
| RQ6 | 无解时的冲突诊断与最小松弛建议，能否让用户更快完成协商？ | E8 |

### 1.4 范围

**范围内**

- 任务/设备/时间/人员的多约束建模与 CP-SAT 求解
- 设备停用、紧急任务插入两类**主事件**；任务工期超时、人员缺席为**扩展事件**
- 稳定性感知重规划、冲突诊断、最小松弛、候选方案生成
- 自然语言需求解析、回译确认、方案解释、一致性校验
- 设备状态仿真、事件注入、滚动仿真评估
- Web 管理系统（资源/任务管理、甘特图、diff、版本、确认）

**范围外（论文中明确说明）**

- 真实设备接入与在线部署（仅预留适配器接口）
- 大模型微调与训练（仅调用 API）
- 不确定性下的随机/鲁棒优化理论（仅在展望中讨论）
- 多实验室、多租户、复杂权限体系

### 1.5 防简单化原则

| 维度 | 问答式做法（避免） | 本课题做法 |
|---|---|---|
| 计划由谁生成 | 大模型直接输出排程 | **约束求解器是唯一的计划生成者** |
| 大模型角色 | 回答问题 | 翻译为可校验的约束/事件，并解释结果 |
| 可行性保证 | 靠提示词 | 求解器 + 独立校验器，硬约束违反率目标为 0 |
| 动态事件 | 重新生成 | 影响域分析 + 邻域重规划，显式权衡延期与改动 |
| 无解 | 模型编造 | 最小冲突集诊断 + 最小松弛建议 |
| 人的参与 | 聊天 | 约束回译确认、候选方案选择、版本可回滚 |
| 状态来源 | 对话里"口述" | 数据库 + 仿真器维护的设备/任务状态 |
| 评估 | 主观演示 | 基线、指标、消融、统计检验、滚动仿真 |

**自检清单**

- [ ] 删掉大模型后，系统仍能基于结构化输入完成调度与重规划
- [ ] 展示给用户的计划均已通过独立校验器
- [ ] 重规划结果能给出"改了什么、为什么"的 diff
- [ ] 无解时给出冲突核，而不是任意给方案
- [ ] 有一键运行的实验脚本，可复现全部结果表

### 1.6 预期贡献（避免写"首创"）

1. 一种"大模型翻译与解释、求解器保证可行、用户确认与取舍"的协同框架，含 NL→IR→校验→回译确认的约束获取流程。
2. 一种面向动态事件的稳定性感知邻域扩张重规划方法。
3. 无解场景下的冲突核诊断与最小松弛协商机制。
4. 解释与求解证据的一致性校验机制。
5. 一套无真实设备条件下的仿真与评估框架（设备状态机、事件驱动仿真、适配器接口、滚动仿真评估），含大模型直接生成、全量重排、规则修复三类基线与消融实验。

> 上述各点所用的算法技术（LNS 思想、MUS、ε-约束等）均为已有方法，本文贡献在于**面向该场景的整合、改造与系统评估**。

---

## 2. 总体架构

### 2.1 分层架构

```
┌──────────────────────────────────────────────────────────────────┐
│ 前端 Web（Vue3 + TS）                                             │
│  资源/任务管理 · 甘特图 · 计划Diff · 约束确认卡片 · 候选对比 ·       │
│  对话面板 · 事件注入面板 · 仿真控制台 · 版本时间线                  │
└───────────────▲──────────────────────────────────────────────────┘
                │ REST / SSE
┌───────────────┴──────────────────────────────────────────────────┐
│ 业务后端（Spring Boot）                                           │
│  资源/任务/约束 CRUD · 计划版本(乐观锁) · 事件管理 · 审计 ·        │
│  任务队列(重规划作业) · Agent 网关 · 仿真控制代理                   │
└──────┬───────────────────────┬───────────────────────────────────┘
       │ JDBC                  │ HTTP
┌──────▼─────────┐   ┌─────────▼──────────────────────────────────┐
│ PostgreSQL     │   │ 智能体服务（FastAPI + LangGraph）            │
│ (+ Redis 可选) │   │  角色节点 · 工具层 · LLM 适配层 · Trace       │
└──────▲─────────┘   └─────────┬──────────────────────────────────┘
       │                       │ 进程内调用
       │             ┌─────────▼──────────────────────────────────┐
       │             │ 调度内核 scheduler_core（Python 包）          │
       │             │  建模 · 求解 · 影响域 · 邻域重规划 · 诊断 ·    │
       │             │  松弛 · Pareto · Validator · 基线             │
       │             └─────────▲──────────────────────────────────┘
       │                       │ 事件 / 状态
┌──────┴───────────────────────┴───────────────────────────────────┐
│ 仿真与设备适配层 simulator（Python 包）                            │
│  虚拟时钟 · 事件队列 · 设备/任务状态机 · 扰动生成 ·                 │
│  DeviceAdapter 接口（Simulated / Manual / Real 预留）              │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 模块职责与边界

| 模块 | 负责 | 不负责 |
|---|---|---|
| 前端 | 展示、交互、确认动作入口 | 任何调度计算 |
| Spring Boot | 持久化、版本管理、权限、审计、作业排队、网关 | 求解、语言理解 |
| 智能体服务 | 意图识别、约束抽取、协商、解释、工具编排 | 直接改计划、绕过校验 |
| scheduler_core | 求解与诊断的全部算法、独立校验 | 语言处理、界面 |
| simulator | 虚拟时间推进、状态变化、扰动产生 | 调度决策 |
| 数据库 | 状态与历史的唯一来源 | 业务计算 |

### 2.3 运行模式

| 模式 | 用途 | 特点 |
|---|---|---|
| **演示模式（Demo）** | 答辩与交互展示 | 全链路：前端 → 后端 → Agent → 内核；仿真器与数据库联动；可手动注入事件 |
| **实验模式（Headless）** | 批量实验 | 不经过前端/后端/大模型：仿真器 + 内核在内存中运行，固定随机种子，结果写 CSV |
| **Agent 评测模式** | 约束抽取、解释一致性评测 | 只跑 Agent 服务与评测集，求解器可用桩（stub）替代以降低成本 |

> **关键设计决策**：调度内核与仿真器都是**纯 Python 包，不依赖数据库和 Web**，这样实验模式能快速批量运行，演示模式只是在外面套了一层服务。

### 2.4 三条典型数据流

**流程 A：初始调度**

```
用户导入/录入任务与设备 → 后端校验并落库 → 触发 solve_initial
→ 内核建模求解 → Validator 校验 → 生成 plan_version(draft)
→ 前端展示甘特图 → 用户确认 → plan_version(confirmed) → active
```

**流程 B：设备事件触发重规划（含仿真）**

```
仿真器/用户注入 DEVICE_FAULT → 后端写 event 表 → 事件合并窗口
→ ImpactAnalysis 得到 (F, A, U) → 邻域重规划 → 候选集(Pareto)
→ Validator 逐个校验 → Agent 生成解释 + 一致性校验
→ 前端展示候选与 diff → 用户选择 → commit 新 plan_version
→ 仿真器按新计划继续推进
```

**流程 C：自然语言变更**

```
用户输入 → 意图识别 → 抽取为 IR → 语法/语义校验 → 歧义则澄清
→ 回译确认卡片 → 用户确认 → 写 ir_item / constraint 或 event
→ 若是事件则进入流程 B；若是约束变更则触发重规划
```

---

## 3. 领域模型与状态模型

### 3.1 核心实体

| 实体 | 关键属性 | 说明 |
|---|---|---|
| Experiment（实验） | id, name, owner, priority, deadline, 任务 DAG | 一个实验由多个任务组成 |
| Task（任务） | id, experiment_id, type, planned_duration, release_time, deadline, deadline_level(HARD/NEGOTIABLE), required_device_type/capabilities, required_skill, preemptible, status | 调度的基本单位 |
| TaskPrecedence | pred_id, succ_id, lag_min, lag_max | 先后关系与时滞 |
| Device（设备） | id, type, capabilities, capacity, status, calendar, setup 矩阵 | 资源 |
| Person（人员） | id, skills, calendar | 可选资源 |
| Constraint（约束） | id, type, scope, params, level(HARD/SOFT/NEGOTIABLE), weight, source, confirmed_by, confirmed_at, lifecycle | 来自系统/用户/Agent |
| PlanVersion（计划版本） | id, parent_id, status, metrics, created_by, trigger_event_id | 版本树 |
| PlanAssignment | plan_id, task_id, device_id, person_id, planned_start, planned_end | 计划内容 |
| Event（事件） | id, type, payload, occurred_at, source(manual/script/sim/agent), handled_plan_id | 扰动 |
| DecisionLog | 谁、何时、确认了什么、选了哪个候选、被拒绝的候选 | 审计 |
| SimRun | id, scenario, seed, params, start, end | 仿真运行记录 |

### 3.2 时间模型

- **时间槽**：默认 5 分钟（可配 5/10/15），内部以整数槽表示；对外以 ISO 时间展示。粒度越粗求解越快，需在实验中给出灵敏度说明。
- **规划视野 H**：默认 14 天（5 分钟槽下约 4032 槽）。
- **工作日历**：非开放时间通过**阻塞区间**建模，而不是裁剪时间轴，以保持统一。
- **当前时刻 `now`**：重规划的核心参数。`planned_start < now` 的任务进入冻结集合 F。
- **时区**：数据库存 UTC，业务时区固定 Asia/Shanghai；自然语言时间解析一律以 `now` 与业务时区为锚。

### 3.3 设备状态机

| 状态 | 含义 | 进入条件 | 可迁移到 |
|---|---|---|---|
| IDLE | 空闲，可用 | 任务结束且无准备；故障恢复；维护结束 | BUSY、SETUP、MAINTENANCE、FAULT、OFFLINE |
| SETUP | 准备/清洗/校准中 | 切换任务类型 | BUSY、FAULT |
| BUSY | 正在执行任务 | 任务开始 | IDLE、FAULT |
| MAINTENANCE | 计划内维护 | 维护窗口开始 | IDLE |
| FAULT | 故障停用 | 故障事件 | IDLE（恢复后） |
| OFFLINE | 人工下线 | 管理员操作 | IDLE |

**关键规则**

- BUSY 期间发生 FAULT：对**不可抢占**任务，任务置为 `INTERRUPTED`，需要重启（见 6.2 节处理）；对**可抢占**任务，剩余工期可续做。
- MAINTENANCE 是**已知的未来窗口**（计划内），FAULT 是**突发事件**。前者进入日历阻塞，后者触发重规划。
- 每次状态变化写入 `device_status_log`，支持回放和统计利用率。

### 3.4 任务状态机

```
PENDING ──(被排入计划)──→ SCHEDULED ──(到达开始时刻且资源就绪)──→ RUNNING ──→ DONE
   │                          │                                      │
   │                          └──(重规划后被改动)──→ SCHEDULED        ├──→ INTERRUPTED ──(重启)──→ PENDING
   └──→ CANCELLED                                                   └──→ FAILED
```

| 状态 | 是否冻结 | 说明 |
|---|---|---|
| PENDING | 否 | 尚未排入计划 |
| SCHEDULED | 否 | 已排入计划但未开始，可被重规划调整 |
| RUNNING | **是**（设备与开始时间固定） | 已开始，结束时刻可因超时顺延 |
| DONE | 是 | 已完成 |
| INTERRUPTED | — | 因设备故障被打断，转为待重启 |
| FAILED / CANCELLED | — | 终态 |

### 3.5 计划版本状态

`draft → confirmed → active → superseded`；被拒绝的候选记为 `rejected`（保留用于审计和消融）。同一时刻只有一个 `active` 版本。版本通过 `parent_id` 形成树，支持回滚与 diff。

### 3.6 计划值与实际值

| 字段 | 来源 | 用途 |
|---|---|---|
| planned_start / planned_end | 计划版本 | 调度输入输出 |
| actual_start / actual_end | 仿真器 / 设备适配器 | 冻结判定、偏差统计 |
| actual_duration | 仿真器按分布采样 | 工期超时事件、计划偏差指标 |

**计划偏差**（滚动仿真评估指标）：`|actual_start − planned_start|` 的均值，用于衡量计划的可执行性。

### 3.7 数据库设计（PostgreSQL）

**表清单**

| 表 | 主要字段 | 备注 |
|---|---|---|
| `device_type` | id, name, capabilities(jsonb) | |
| `device` | id, type_id, name, capacity, status, version | status 由适配器更新 |
| `device_calendar_window` | id, device_id, start, end, kind(OPEN/MAINT/BLOCK), source | 开放时段与计划内维护 |
| `device_status_log` | id, device_id, from_status, to_status, at, cause_event_id | 状态回放 |
| `setup_matrix` | device_type_id, from_task_type, to_task_type, minutes | 准备时间 |
| `person` / `person_calendar` | 同设备思路 | 可选 |
| `experiment` | id, name, owner, priority, deadline, deadline_level | |
| `task` | id, experiment_id, type, planned_duration, release_time, deadline, deadline_level, preemptible, status, version | |
| `task_precedence` | pred_id, succ_id, lag_min, lag_max | |
| `task_runtime` | task_id, actual_start, actual_end, actual_duration, device_id | 实际值 |
| `constraint_def` | id, type, scope(jsonb), params(jsonb), level, weight, source, lifecycle, confirmed_by, confirmed_at | |
| `ir_item` | id, session_id, raw_text, ir(jsonb), status(DRAFT/CONFIRMED/REJECTED), back_translation | Agent 抽取记录 |
| `plan_version` | id, parent_id, status, metrics(jsonb), trigger_event_id, created_at, version | 乐观锁 |
| `plan_assignment` | plan_id, task_id, device_id, person_id, planned_start, planned_end | 主键(plan_id, task_id) |
| `event` | id, type, payload(jsonb), occurred_at, source, handled_plan_id, merged_into | 事件合并 |
| `event_impact` | event_id, task_id, impact_kind(DIRECT/PROPAGATED), reason | 影响域记录 |
| `decision_log` | id, plan_id, actor, action, candidates(jsonb), chosen, at | 审计 |
| `sim_run` / `sim_event_log` | 运行元数据与事件流水 | 回放与复现 |
| `llm_trace` | id, session_id, node, prompt_hash, output, latency, tokens, schema_ok | 可观测 |

**设计要点**

- `plan_assignment` 与 `plan_version` 分离：每个版本一套完整分配，diff 通过按 `(plan_id, task_id)` 对比得到。
- `task.version`、`plan_version.version`、`device.version` 用于**乐观锁**，防止仿真、用户和重规划作业并发写同一对象。
- `constraint_def.lifecycle`：`DRAFT → CONFIRMED → ACTIVE → RETIRED`。只有 ACTIVE 约束进入求解。
- 大部分结构化载荷用 `jsonb` 保存，便于 IR 版本演进；热点查询字段（时间、状态、外键）用普通列并建索引：`(device_id, start)`、`(plan_id, task_id)`、`(status)`。

---

## 4. 仿真与设备适配层

### 4.1 为什么需要这一层

没有真实设备时，只建表会得到静态数据，无法产生"状态随时间变化"的动态过程。本层的目的：

1. 让设备与任务状态**随虚拟时间演化**，从而产生可重复的扰动；
2. 通过**适配器接口**把"状态从哪来"与"调度怎么做"隔离；
3. 支持两种使用：**演示时人工操控**，**实验时批量自动运行**。

### 4.2 设备适配器接口

```python
class DeviceAdapter(Protocol):
    def list_devices(self) -> list[DeviceInfo]: ...
    def get_status(self, device_id: str) -> DeviceStatus: ...
    def get_calendar(self, device_id: str, start, end) -> list[Window]: ...
    def start_task(self, device_id: str, task_id: str, at) -> None: ...   # 下发
    def subscribe(self, callback: Callable[[DeviceEvent], None]) -> None: ...  # 状态/事件上报
```

| 实现 | 说明 |
|---|---|
| `SimulatedAdapter` | 由仿真器驱动，状态按规则与随机过程变化（**本文主用**） |
| `ManualAdapter` | 由前端"事件注入面板"驱动，用于现场演示 |
| `RealAdapter`（预留） | 将来对接实验室管理系统或设备 API，本文不实现 |

> 论文中的表述：设备状态通过统一适配器接口读取，仿真实现可被真实设备替换，调度内核与智能体不依赖仿真细节。

### 4.3 离散事件仿真器

**事件类型**

| 事件 | 触发来源 | 效果 |
|---|---|---|
| `TASK_START` | 计划到点且资源就绪 | 任务 RUNNING，采样实际工期，设备 BUSY |
| `TASK_END` | 实际结束时刻 | 任务 DONE，设备 IDLE 或进入 SETUP |
| `SETUP_END` | 准备结束 | 设备 IDLE |
| `DEVICE_FAULT` | 随机过程或人工 | 设备 FAULT，运行中任务按 3.3 规则处理 |
| `DEVICE_RECOVER` | 故障持续时间到 | 设备 IDLE |
| `MAINT_START / MAINT_END` | 计划内维护窗口 | 设备 MAINTENANCE / IDLE |
| `URGENT_ARRIVAL` | 泊松到达或人工 | 新增紧急实验及其任务 |
| `TASK_OVERRUN` | 实际工期 > 计划工期且造成冲突 | 触发重规划（见 4.5） |
| `PERSON_ABSENT`（扩展） | 人工或随机 | 人员日历阻塞 |

**主循环（伪代码）**

```
init(clock = t0, queue = 初始事件, plan = active_plan, rng = Random(seed))
while clock < t_end:
    ev = queue.pop_min()                  # 按 (时间, 优先级) 排序
    clock = ev.time
    apply(ev)                             # 更新设备/任务状态，写日志
    if ev 是扰动事件 或 满足冲突触发条件:
        batch = collect_events_within(window = Δ)       # 事件合并
        resp = scheduler.replan(plan, batch, now = clock)   # 实验模式直接调用内核
        plan = resp.chosen_plan                         # 策略选择或 HITL 选择
        queue.reschedule_future_task_events(plan)       # 用新计划替换尚未开始任务的事件
    record_metrics(clock)
```

### 4.4 扰动模型（可配置、可复现）

| 扰动 | 默认模型 | 可调参数 |
|---|---|---|
| 设备故障 | 每台设备故障间隔指数分布（MTBF），修复时间对数正态 | MTBF、修复时间均值/方差 |
| 计划内维护 | 固定周期窗口 | 周期、时长 |
| 工期偏差 | 实际工期 = 计划工期 × 对数正态因子，截断到 [0.8, 1.6] | 方差 σ |
| 紧急任务 | 泊松到达，任务数、工期、截止期按分布采样 | 到达率 λ、紧急度 |
| 人员缺席 | 伯努利（每日） | 概率 |

> 参数取值应来自 4.8 节的调研或在实验中作灵敏度分析，**不要把某一组随机参数当作"真实实验室的规律"**。

**扰动强度分级**（用于实验）

| 级别 | 描述 | 例 |
|---|---|---|
| 轻 | 单事件，直接影响 < 10% 待执行任务 | 一台设备停用 2 小时 |
| 中 | 2–3 个事件或影响 10%–30% | 设备停用 + 1 个紧急任务 |
| 重 | ≥ 5 个事件，或关键设备长时间停用，影响 > 30% | 多设备故障叠加紧急插入 |

### 4.5 触发与合并策略

| 策略 | 说明 | 目的 |
|---|---|---|
| 事件驱动 | 设备故障、紧急插入立即触发 | 及时响应 |
| 冲突触发 | 工期超时仅在造成**设备冲突或违反先后/截止**时触发 | 避免频繁重规划（计划抖动） |
| 事件合并窗口 Δ | Δ 内到达的多个事件合并为一次重规划（默认 Δ = 5 分钟虚拟时间） | 降低计算量与改动次数 |
| 最小重规划间隔 | 两次重规划之间的冷却时间 | 稳定性 |
| 周期重规划（可选） | 每隔固定时间做一次整体优化 | 对比实验用 |

### 4.6 与调度内核的交互约定

- 仿真器只通过 `replan(plan, events, now)` 调用内核，不了解内核内部。
- 重规划只替换**尚未开始**的任务，RUNNING 与 DONE 不变。
- 仿真器向内核提供**当前冻结信息**：每个 RUNNING 任务的设备、开始时间、预计结束时间（`max(planned_end, now + 剩余估计)`）。

### 4.7 复现与回放

- 随机数用 `numpy.random.Generator(PCG64(seed))`，不同扰动使用**独立子流**，避免增加一种扰动改变其他扰动的序列。
- 每次运行保存：场景配置、种子、完整事件日志（`sim_event_log`）。同一日志可**回放**，并可对同一扰动序列比较不同算法（配对实验）。

### 4.8 数据来源与可信性

| 来源 | 做法 | 作用 |
|---|---|---|
| 实验室调研 | 向 1–2 个实验室了解设备种类与数量、典型实验步骤与耗时、清洗准备时间、开放与维护规律、常见故障 | 提供**参数依据**，避免纯随机 |
| 真实案例 | 选一个真实实验流程（如某门实验课的一周安排）做案例研究 | 贴近实际的证据 |
| 公开基准映射 | 将作业车间/柔性作业车间公开实例映射为设备与任务（如 FT06 等） | 与文献可比 |
| 随机生成器 | 按"规模 × 设备紧张度 × 截止期松紧度 × DAG 深度"生成，固定种子 | 规模与扰动的系统化实验 |

### 4.9 局限（论文中如实说明）

- 没有真实设备上的在线验证，扰动分布为假设模型。
- 仿真假设设备行为独立、状态可观测，真实场景可能存在状态上报延迟或错误。
- 因此结论表述为"在仿真与基准实例上"，不写"已在实验室实际运行"。

---

## 5. 约束体系

### 5.1 三分法

| 类别 | 含义 | 处理方式 |
|---|---|---|
| **HARD** | 物理/安全约束，不可放宽 | 模型中的硬约束；无解时不放宽，只能诊断 |
| **SOFT** | 偏好类，可违反但有代价 | 进入目标函数 |
| **NEGOTIABLE** | 默认按硬处理，但用户可授权放宽（如截止期、人员加班） | 默认硬；无解时进入诊断与松弛，由用户决定 |

### 5.2 硬约束清单

| 编号 | 约束 | CP-SAT 建模 |
|---|---|---|
| H1 | 设备互斥 | 每台设备 `AddNoOverlap` |
| H2 | 设备可用窗口（含维护、故障、非开放时间） | 把不可用窗口建成**固定占位区间**加入该设备的 NoOverlap |
| H3 | 先后关系与时滞 | `s_j ≥ e_i + lag_min`，`s_j ≤ e_i + lag_max` |
| H4 | 设备—任务兼容 | 只为兼容设备创建可选区间 |
| H5 | 人员互斥与技能匹配 | 人员维度的可选区间 + NoOverlap |
| H6 | 释放时间 | `s_i ≥ release_i` |
| H7 | 冻结：运行中/已完成任务不可改 | 固定 `s_i`、`d_i`；运行中任务的占用到预计结束时刻 |
| H8 | 准备/清洗时间 | MVP：按"目标任务类型 + 设备"的固定前置准备时间扩展区间；扩展：序列相关准备时间用 `AddCircuit` |
| H9 | 设备容量 > 1 | `AddCumulative`，需求为样品数 |
| H10 | 硬截止期（`deadline_level = HARD`） | `e_i ≤ dl_i` |

### 5.3 软约束与目标项

| 编号 | 内容 |
|---|---|
| S1 | 延期代价 `w_i · max(0, e_i − dl_i)`（NEGOTIABLE 截止期在默认状态下按硬约束处理） |
| S2 | 偏好时段/偏好设备 |
| S3 | 同一实验任务尽量连续，减少样品等待 |
| S4 | 设备负载均衡 |
| S5 | **计划稳定性**（见 6.3，仅用于重规划） |

### 5.4 约束生命周期与来源

```
Agent/用户输入 → DRAFT（仅存在于 ir_item）→ 用户确认 → CONFIRMED
→ 进入求解 → ACTIVE → 被撤销或到期 → RETIRED
```

- **来源**标记为 `system`（基础规则）/ `user`（用户确认）/ `agent`（Agent 建议，需用户确认后才生效）。
- **只有 ACTIVE 约束才进入求解**，保证 Agent 不能绕过确认。
- 新增约束入库前做**冲突预检**：与已有 ACTIVE 约束、冻结任务、日历的显式矛盾（如截止期早于释放时间）。

### 5.5 约束中间表示（IR）

大模型只输出下面这类可校验的 JSON，不输出时间安排。

```json
{
  "kind": "event",
  "type": "DEVICE_OUTAGE",
  "device_ref": {"text": "3号离心机", "resolved_id": "D-03", "confidence": 0.93},
  "start": "2026-11-05T14:00+08:00",
  "end":   "2026-11-06T09:00+08:00",
  "reason": "故障"
}
```

```json
{
  "kind": "constraint",
  "type": "DEADLINE",
  "task_ref": {"text": "样品A的HPLC检测", "resolved_id": "T-117", "confidence": 0.88},
  "value": "2026-11-07T18:00+08:00",
  "level": "NEGOTIABLE",
  "penalty_weight": 5
}
```

```json
{
  "kind": "event",
  "type": "URGENT_TASK_INSERT",
  "experiment": {
    "name": "样品复测", "priority": "HIGH",
    "tasks": [{"id": "U-1", "type": "HPLC", "duration_min": 90}],
    "deadline": "2026-11-05T17:00+08:00", "deadline_level": "NEGOTIABLE"
  }
}
```

**IR 的设计要求**

- 所有实体引用同时保存**原文**、**解析后的 id**、**置信度**；低于阈值必须触发澄清。
- 所有时间带时区，不允许"下午"之类的模糊值入库；模糊时间必须先澄清或由规则解析并回译确认。
- IR 模式带 `schema_version`，便于演进。

---

## 6. 调度内核算法（重点）

### 6.1 初始调度：CP-SAT 模型

**集合与参数**

| 符号 | 含义 |
|---|---|
| `I` | 待排任务集合；`D` 设备集合；`C(i) ⊆ D` 任务 i 的兼容设备 |
| `p_i` | 任务 i 的工期（槽数）；`r_i` 释放时间；`dl_i` 截止期；`w_i` 延期权重 |
| `u_{i,d}` | 任务 i 在设备 d 上的前置准备时长（MVP：由任务类型与设备决定） |
| `B_d` | 设备 d 的固定阻塞区间集合（非开放、维护、故障、运行中任务占用） |
| `Prec` | 先后关系集合 `(i, j, lag_min, lag_max)` |
| `H` | 规划视野上界 |

**决策变量**

- `s_i ∈ [r_i, H − p_i]`：任务开始；`e_i = s_i + p_i`
- `x_{i,d} ∈ {0,1}`：任务 i 是否分配到设备 d，`d ∈ C(i)`
- 可选区间 `J_{i,d}`：起点 `s_i − u_{i,d}`、长度 `p_i + u_{i,d}`，存在性 `x_{i,d}`（与 `s_i` 共享起点变量，便于约束）
- `T_i ≥ 0`：延期量

**约束**

```
Σ_{d∈C(i)} x_{i,d} = 1                                   ∀ i
NoOverlap({J_{i,d}}_{i} ∪ B_d)                            ∀ d          (H1,H2,H8)
Cumulative({J_{i,d}}, demand, capacity_d)                 容量>1 的设备 (H9)
s_j ≥ e_i + lag_min,  s_j ≤ e_i + lag_max                 ∀ (i,j) ∈ Prec  (H3)
e_i ≤ dl_i                                                deadline_level = HARD (H10)
T_i ≥ e_i − dl_i                                          NEGOTIABLE/SOFT 截止期
```

**目标函数**

```
min  Σ_i w_i · T_i  +  λ1 · Cmax  +  λ2 · Imb  +  λ3 · Pref
```

`Cmax` 为最大完工时间，`Imb` 为同类设备间负载的最大差，`Pref` 为偏好违反数。

**工程要点**

1. **阻塞区间**：设备停用、维护、非开放时间统一建为固定区间，不使用 if 语句。
2. **对称性破缺**：同类、同属性设备的任务分配加字典序约束，减少等价搜索。
3. **搜索加速**：任务按 EDD 加优先级给出决策策略；用启发式解通过 `AddHint` 提供初解。
4. **Anytime**：设置时间上限（如 10 秒/60 秒），记录最优界与 gap。
5. **多线程**：`num_workers` 取机器核数，实验中固定为同一值并记录。
6. **规模分层**：小规模求最优；中大规模报告 gap。

### 6.2 事件分类与影响域分析

**事件类型与对模型的作用**

| 事件 | 对模型的作用 | 直接影响集 `A0` |
|---|---|---|
| 设备停用 `[t1, t2)` | 在 `B_d` 中加入阻塞区间；运行中任务按 3.3 处理 | 该设备上与 `[t1, t2)` 重叠的 SCHEDULED 任务；被打断任务 |
| 紧急任务插入 | 新增任务及其先后关系、截止期 | 同类兼容设备上、时间窗与新任务可能冲突的任务 |
| 工期超时 | 运行中任务的预计结束时刻后移 | 该设备上紧随其后的任务及其后继 |
| 人员缺席 | 人员日历加阻塞 | 依赖该人员的任务 |

**影响域算法**

```
ImpactAnalysis(plan0, event, now):
  F  ← {i : planned_start_i < now}                      # 冻结（RUNNING/DONE）
  P  ← I \ F
  A0 ← DirectlyAffected(plan0, event) ∩ P
  A  ← A0
  repeat until 不再扩张（或达到深度/窗口限制）:
      A ← A ∪ Succ(A) ∪ SameDeviceNeighbors(A, window = W)
  U  ← P \ A                                            # 未受影响，默认固定
  return (F, A, U), 影响原因记录
```

**要点**

- `Succ(A)`：沿先后关系传播；`SameDeviceNeighbors(A, W)`：同一设备上时间窗 `W` 内相邻的任务（`W` 默认 4 小时，可配）。
- **影响原因**写入 `event_impact`，供解释使用（"T-52 受影响，因为它是被打断任务的后继"）。
- 复杂度为任务数的线性级（图遍历），相对求解可忽略。

**运行中任务被设备故障打断**

| 任务类型 | 处理 |
|---|---|
| 不可抢占 | 状态置 `INTERRUPTED`，生成"重启任务"副本（完整工期，释放时间为 `max(now, 设备恢复)` 或换设备），纳入 `A` |
| 可抢占 | 剩余工期作为新任务纳入 `A`，保持先后关系 |

### 6.3 稳定性感知目标

设原计划为 `(s_i⁰, d_i⁰)`，新计划为 `(s_i, d_i)`。

```
moved_i    = 1[ s_i ≠ s_i⁰ ]
switched_i = 1[ d_i ≠ d_i⁰ ]
shift_i    = |s_i − s_i⁰| / H
```

**重规划目标**

```
min  α · Σ_i w_i · T_i
   + β1 · Σ_i moved_i + β2 · Σ_i switched_i + β3 · Σ_i shift_i
   + γ  · urgent_delay
```

**CP-SAT 实现**

- `moved_i`：布尔变量，`s_i ≠ s_i⁰` 与 `s_i == s_i⁰` 分别用 `OnlyEnforceIf(moved)` 与 `OnlyEnforceIf(moved.Not())` 表达。
- `switched_i = 1 − x_{i,d_i⁰}`。
- `shift_i`：用 `AddAbsEquality`。

**权重**

- 以"等效延期槽数"为统一单位设初值，例如一次任务改动相当于 `κ` 个槽的延期。初值建议（需灵敏度分析确定）：`β1 = 2`、`β2 = 5`、`β3 = 0.1 / 槽`，`α = 1`，`γ` 较大。
- 来自界面的"偏好滑条"（更稳 ↔ 更少延期），映射到 `α : β` 的比值。
- **两种策略对比（消融）**：加权和 vs 字典序（可行 → 延期 → 改动）。

### 6.4 邻域扩张重规划

**思想**：全量重排改动大且慢；只修补又可能无解。采用从小到大的邻域：邻域越小越快、改动越少；仅当小邻域无解时才扩大。这借鉴大邻域搜索（LNS）的"固定一部分、放开一部分"思想，但以**可行性驱动的确定性扩张**取代随机破坏。

**邻域层级**

| 层级 | 放开的任务集合 `Free_k` | 说明 |
|---|---|---|
| 0 | `A`（影响域）+ 新任务 | 最小改动 |
| 1 | `Free_0` ∪ 受影响设备上 `[now, now+W₁]` 内全部 SCHEDULED 任务 | 资源/时间扩展 |
| 2 | `Free_1` ∪ 涉及任务所属实验的全部 SCHEDULED 任务 | 实验（依赖）扩展 |
| 3 | 全部 SCHEDULED 任务 | 等价于全量重排（带稳定性项） |

**算法**

```
Replan(plan0, events, now, budget):
  apply events to model (阻塞区间 / 新任务 / 工期变化 / 打断处理)
  (F, A, U) ← ImpactAnalysis(...)
  for k = 0 .. K:
      固定 F ∪ (P \ Free_k) 的 (s, d)
      以 plan0 为 warm-start hint
      status, sol ← Solve(目标 6.3, time_limit = τ_k)
      if status ∈ {OPTIMAL, FEASIBLE}:
          记录候选(k, 权重组合)
          if 只需一个解: break
      else if status = INFEASIBLE:        # 小邻域内无解，扩张
          continue
      else:                               # UNKNOWN（超时）
          τ_k ← 放宽；记录；continue
  if 所有层级均无可行解:
      → 6.5 冲突诊断（只在 k = K 时才断言"硬约束下无解"）
  return 候选集
```

**时间预算**：总预算 `T`（如 10 秒），各层按递增分配（如 `τ_k = T · 2^k / (2^{K+1} − 1)`）；小邻域通常能很快证明不可行，所以总开销不大。

**性质（论文中可作为命题并用实验验证）**

- **完备性**：最大层级（k = K）释放全部 SCHEDULED 任务，其可行性与全量重排一致（在同等求解时间内）。因此邻域扩张**不损失可行性**，只是优先尝试改动更小的解。
- **改动量**：层级越低，被允许改动的任务集合越小，改动量不会因放开更多任务而被迫增加。
- **局限**：低层级解的延期代价可能高于高层级解；这正是 6.7 的 Pareto 候选要体现的权衡。

### 6.5 冲突诊断：最小不可满足核（MUS）

**目标**：当硬约束下无解时，告诉用户"为什么"。

```
Diagnose(model, constraint_groups):
  为每个可诊断约束组 g 引入使能文字 a_g，约束表示为 a_g ⇒ C_g
  AddAssumptions({a_g})
  if Solve = INFEASIBLE:
      core ← SufficientAssumptionsForInfeasibility()
      # Deletion filter：精简核
      for g in core:
          尝试去掉 g 对应的假设 → 若仍 INFEASIBLE，永久去掉 g
      return 精简后的核（近似 MUS）
```

**约束分组**（降低诊断粒度、减少求解次数）

- 每个任务的截止期、每个设备停用窗口、每个冻结任务、每个先后关系组、每个设备容量。

**映射为用户语言**

每个假设文字绑定：约束对象、来源、模板文案。Agent 用证据包生成解释，例如："新任务 U-1 需在 17:00 前完成；HPLC-1 在 15:00 前被已开始的 T-12 占用，HPLC-2 当天处于计划内维护，因此无法满足。"

**注意**：MUS 不唯一；记录前 N 个核，并按"用户可放宽性"排序展示。

### 6.6 最小松弛建议

对 NEGOTIABLE 约束引入松弛变量，在硬约束保持的前提下最小化松弛代价：

```
min  Σ_c  ρ_c · δ_c        s.t. HARD 约束全部保持
     例：e_i ≤ dl_i + δ_i  （截止期松弛）
         允许某任务换到备选设备并增加准备时间 u'
         允许在 [t, t'] 加班（移除一段阻塞）
```

- 得到代价最小的松弛方案；再加"禁止已得到的松弛组合"的割（no-good），求出多个**不同**的方案（建议 2–3 个）。
- 每个方案附：放宽了什么、代价是多少、对其他任务的影响。

### 6.7 候选方案生成与 Pareto 筛选

三个目标：`f1` 延期代价、`f2` 改动代价（moved/switched/shift 的加权）、`f3` 紧急任务完成时间。

```
GenerateCandidates:
  候选池 ← ∅
  for 层级 k ∈ {0..K}, 权重组合 (α:β) ∈ 权重网格:
      用 6.4 求解 → 校验 → 加入候选池
  非支配过滤：去掉被其他候选在 (f1, f2, f3) 上全面支配的方案
  去重：起点向量的 L1 距离小于阈值的视为同一方案
  选择 3–5 个并贴标签：
      "最稳"      = f2 最小
      "最少延期"  = f1 最小
      "最早完成紧急任务" = f3 最小
      "均衡"      = 归一化空间中最接近理想点（knee point）
```

每个候选附 **diff**（新增/移动/换设备/延期的任务列表）与指标。

### 6.8 独立校验器（Validator）

与求解器**分离实现**（不复用 CP-SAT 模型，纯 Python 排序扫描，`O(n log n)`）。

| 检查 | 内容 |
|---|---|
| V1 | 每个任务恰有一台兼容设备 |
| V2 | 同设备任务（含准备时间）与阻塞区间无重叠 |
| V3 | 先后关系与时滞 |
| V4 | 释放时间 |
| V5 | 硬截止期 |
| V6 | 设备日历（开放/维护/故障） |
| V7 | 人员互斥与技能 |
| V8 | 冻结任务的设备与开始时间未改 |
| V9 | 设备容量 |
| V10 | 工期一致 |
| V11 | 与父版本相比只改动了允许改动的任务（`Free_k` 之外未变） |

**用途**：(1) 防建模 bug；(2) 展示前的强制关卡；(3) 评估时统一计算"硬约束违反率"，也用于评价基线 B1。

### 6.9 基线与公平性

| 编号 | 方法 | 实现要点 |
|---|---|---|
| **B1a** | 大模型直接生成（单次） | 提示词含任务/设备/日历/当前计划/事件的结构化 JSON，要求输出新计划 JSON；温度 0；同一模型、同一提示模板；用 Validator 评估 |
| **B1b** | 大模型 + 校验反馈（最多 3 轮） | 把 Validator 的违反清单反馈给模型再生成；对应 LLM-Modulo 思路，是更强、更公平的对照 |
| **B2** | 求解器全量重排 | 释放全部 SCHEDULED 任务；目标仅含延期代价（B2s：另含稳定性项，用于消融"去邻域扩张"） |
| **B3** | 规则修复（EDD + 右移） | 受影响任务按 EDD 顺序放到最早可行位置（同设备顺延，或换到最早可用的兼容设备），后继随之右移；紧急任务按优先级插入；不保证满足截止期 |
| **M** | 本文方法 | 影响域 + 邻域扩张 + 稳定性目标 + 候选生成 |

**公平性**：所有方法使用同一实例、同一事件、同一 `now`、同一时间预算（B1 按大模型调用时间计），同一 Validator；大规模实例上 B1 因上下文长度和成本限制，只在小/中规模上评测，并在报告里写明。

### 6.10 参数表（默认值，需灵敏度分析）

| 参数 | 默认 | 说明 |
|---|---|---|
| 时间槽 | 5 分钟 | 可配 |
| 视野 H | 14 天 | |
| 求解时间（初始） | 30 秒 | 中规模 |
| 重规划总预算 T | 10 秒 | 小/中规模 |
| 邻域窗口 W | 4 小时 | |
| `α, β1, β2, β3` | 1, 2, 5, 0.1 | 初值 |
| 事件合并窗口 Δ | 5 分钟（虚拟） | |
| 候选数 | 3–5 | |
| 随机种子数 | 30 | 实验 |

---

## 7. Agent 设计

### 7.1 角色与权限

按**权限与信任边界**划分，而非按职位命名。求解器、影响域、冲突诊断、Pareto 生成是**确定性工具**，不是 Agent。

| 角色 | 是否 LLM | 职责 | 输入 → 输出 | 权限 |
|---|---|---|---|---|
| **需求解析** | 是 | 自然语言 → IR；识别歧义并反问；生成回译卡片 | 用户话语 + 实体清单 → IR 草稿 / 澄清问题 | 只读，只能产出"待确认草稿" |
| **协调** | 是 | 判断意图；选择工具；组织协商（无解时提松弛选项，处理拒绝与偏好调节） | 对话状态 + 工具结果 → 工具调用 / 下一步话术 | 可调用求解类工具，**不可 commit** |
| **解释** | 是 | 把 diff、影响域、冲突核、指标写成可读解释，并同时输出结构化断言 | 证据包 → 解释 + claim 列表 | 无工具权限，只读证据包 |
| **校验** | 主要程序化 | 校验 IR、校验计划、核对解释断言 | IR / 计划 / claim → 通过 / 违反清单 | **有否决权**，失败即打回 |

**自主级别**

| 级别 | 行为 | 例子 |
|---|---|---|
| L0 自动 | 只读、无副作用 | 查询计划、影响分析、试算候选 |
| L1 需确认 | 改变系统对世界的理解 | 新增/修改约束、注入事件 |
| L2 需确认 + 校验 | 改变正式计划 | 选择候选并提交、回滚 |

> 校验角色刻意不用 LLM：用同类模型检查另一个模型的输出，错误容易相关；用程序对照求解结果才可靠。可选地加一个 LLM 评审做软性检查，但不能替代程序校验。

### 7.2 LangGraph 状态图

```
START → Router
Router ─(事件/新需求)→ Extractor → SchemaValidator → AmbiguityCheck
          AmbiguityCheck ─歧义→ Clarify（HITL 反问）→ Extractor
          AmbiguityCheck ─清晰→ BackTranslate → [HITL 约束确认] → Commit_IR
Commit_IR ─(事件)→ ImpactTool → ReplanTool → CandidateBuilder
Commit_IR ─(约束变更)→ ReplanTool
ReplanTool ─可行→ CandidateBuilder → PlanValidator → Explainer → ConsistencyChecker
            ConsistencyChecker ─不一致→ Explainer（重生成，≤N 次，仍失败则模板降级）
            ConsistencyChecker ─一致→ [HITL 方案选择] → Commit_Plan → END
ReplanTool ─无解→ DiagnoseTool → RelaxTool → [HITL 协商] → ReplanTool（循环，限次）
Router ─(询问/解释)→ Explainer
Router ─(回滚/版本)→ VersionTool → [HITL 确认] → END
```

**Agent State**

```python
class AgentState(TypedDict):
    session_id: str
    messages: list
    now: str                         # 业务时间锚点
    parsed_items: list[IRItem]
    confirmed_items: list[IRItem]
    active_plan_id: str
    impact: ImpactReport | None
    candidates: list[PlanCandidate]
    conflict_core: list[ConstraintRef] | None
    relaxation_options: list[Relaxation]
    pending_action: Literal["confirm_constraints", "choose_plan", "negotiate", None]
    retry_count: int
```

HITL 通过 LangGraph 的中断（interrupt）与检查点（checkpointer）实现，会话可断点恢复。

### 7.3 自然语言 → 约束：可信抽取流水线

```
① 意图识别（新建 / 报告事件 / 修改约束 / 询问 / 确认 / 回滚）
② 结构化抽取（函数调用 / JSON Schema 约束输出）
③ 语法校验（pydantic：类型、必填、枚举）
④ 语义校验
     实体解析：别名表 + 模糊匹配（编辑距离/拼音）→ 候选及置信度
     时间解析：规则优先（以 now 为锚）+ LLM 兜底 → 一律输出带时区的绝对时间
     软硬判定：根据措辞（"必须/不能" vs "尽量/最好"）初判，低置信度则追问
     合理性检查：end > start；任务/设备存在；与冻结任务冲突预检
⑤ 歧义检测：多个候选实体、缺失参数、软硬不明 → 反问澄清
⑥ 回译确认：把 IR 渲染回自然语言卡片，用户逐条确认/修改
⑦ 入库：带 confirmed_by / confirmed_at；同时保存原文与 IR
```

**关键点**

- 对"尽量别用 3 号机""除非实在没办法"这类措辞，**默认判为软约束并回译确认**，而不是默认硬禁用或忽略。
- 时间相对表达（"明天下午""下周三"）由规则解析为区间，并在回译卡片上显示绝对时间，**由用户确认而非模型自信**。
- 评测时把"实体歧义""软硬区分""相对时间""缺参数""多约束一句话"作为独立类别统计。

### 7.4 工具清单

| 工具 | 功能 | 级别 | 副作用 |
|---|---|---|---|
| `get_plan` / `get_schedule_view` | 查询计划、设备日历、任务状态 | L0 | 无 |
| `resolve_entity` | 实体解析与候选 | L0 | 无 |
| `parse_time` | 时间解析（以 now 为锚） | L0 | 无 |
| `validate_ir` | 语义校验、冲突预检 | L0 | 无 |
| `analyze_impact` | 事件影响域分析 | L0 | 无 |
| `solve_initial` | 初始调度（产生 draft 版本） | L0/L1 | 写 draft |
| `replan` | 重规划，返回候选集 | L0 | 写 draft |
| `diagnose_infeasibility` | MUS 诊断 | L0 | 无 |
| `suggest_relaxation` | 最小松弛方案 | L0 | 无 |
| `compare_plans` | 候选/版本 diff 与指标 | L0 | 无 |
| `verify_plan` | 独立校验 | L0 | 无 |
| `commit_ir` | 确认后写入约束/事件 | L1 | 写库 |
| `commit_plan` / `rollback_plan` | 提交/回滚计划版本 | L2 | 写库 |

### 7.5 协商与澄清策略

- **先澄清后求解**：存在歧义或缺参数时先反问，每次最多问一个关键问题。
- **无解时**：先给冲突原因（MUS），再给 2–3 个松弛选项（含代价），而不是一次抛出全部。
- **被拒绝的选项**：记入 `decision_log`，下一轮求解把该选项加入禁止集。
- **偏好调节**：滑条调整 α/β，直接映射到权重。

### 7.6 解释生成与一致性校验

**证据包**（解释的唯一数据来源）

```json
{
  "plan_diff":   [{"task":"T-52","change":"MOVED","from":"...","to":"..."}],
  "impact":      [{"task":"T-52","reason":"后继任务","via":"T-47"}],
  "metrics":     {"tardiness": 12, "moved": 3, "switched": 0},
  "conflict_core": null,
  "relaxation":  null
}
```

**流程**

1. 解释 Agent 只读证据包，输出**解释文本 + 结构化断言列表**（如 `{"task":"T-52","claim":"DELAYED","by_min":120}`）。
2. 校验角色用程序把断言与证据包逐条比对。
3. 不一致 → 重生成（≤ N 次）；仍失败 → 降级为模板化解释（保证不出错）。
4. 指标：**解释一致率** = 一致断言数 / 总断言数；以及"降级触发率"。

### 7.7 提示词与结构化输出管理

- 提示词、JSON Schema、few-shot 样例**版本化**，随实验记录。
- 抽取使用函数调用或 Schema 约束输出；格式失败 → 最多 2 次重试 → 回退到**表单式输入**（保证系统可用）。
- 实验中固定模型版本与温度（抽取、解释温度 0）。

### 7.8 错误处理与降级

| 故障 | 处理 |
|---|---|
| LLM 超时/限流 | 重试 → 提示用户并提供表单入口；调度内核不受影响 |
| 输出格式错误 | 重试 ≤ 2 次 → 回退表单 |
| 求解超时 | 返回 anytime 解并标注 gap；无可行解则进入层级扩张/诊断 |
| 无解 | 冲突诊断 + 松弛建议 |
| 版本冲突（乐观锁失败） | 重新拉取最新计划，重新计算影响域 |

### 7.9 可观测性

- 每次 LLM 调用写 `llm_trace`：节点、提示哈希、输出、耗时、token、Schema 是否通过。
- 每次工具调用记录输入、输出摘要、耗时。
- 提供按会话回放的调试视图，支持实验后分析错误案例。

### 7.10 本课题涉及的 Agent 知识点

1. 函数调用 / 结构化输出（JSON Schema、枚举约束、失败重试）
2. 工具增强大模型：大模型作规划/翻译，求解器作验证与执行（神经符号思路）
3. ReAct 与 Plan-and-Execute 对比，及选择受控状态机的理由
4. Human-in-the-Loop：LangGraph interrupt、checkpointer
5. 状态与记忆：会话状态 vs 持久状态、上下文裁剪
6. Guardrails：输入/输出校验、信任边界（把大模型输出视为不可信输入）
7. 幻觉控制：证据驱动解释、claim 级验证
8. 歧义消解与澄清提问（slot filling）
9. 可观测性与评估：程序化指标为主，LLM-as-judge 仅作辅助
10. （可选）多 Agent：Planner/Critic，**须有对比实验证明收益**

---

## 8. 业务后端与接口（Spring Boot）

### 8.1 模块划分

| 模块 | 职责 |
|---|---|
| resource | 设备、人员、日历、准备时间矩阵的 CRUD |
| task | 实验、任务、先后关系的 CRUD 与导入 |
| constraint | 约束与 IR 记录管理，生命周期流转 |
| plan | 计划版本、分配、diff、回滚；乐观锁 |
| event | 事件接收、合并、去重、影响记录 |
| job | 重规划/初始调度的**异步作业队列**（同一实验室同一时间只允许一个重规划作业） |
| agent-gateway | 转发对话、流式返回（SSE）、持久化 Agent 产出 |
| sim-proxy | 控制仿真器（启动、暂停、倍速、注入事件） |
| audit | 决策日志与操作审计 |
| auth | 用户与权限（管理员 / 实验员 / 只读） |

### 8.2 并发与一致性

- **乐观锁**：`version` 字段；提交计划时校验 `base_version` 等于当前 active 版本，不一致则要求重新计算。
- **单作业约束**：同一实验室同一时间只允许一个重规划作业；新事件到达时若作业在运行，则合并进下一批（事件合并窗口）。
- **幂等**：事件带 `event_id`，重复提交不重复处理。
- **事务边界**：`commit_plan` 在一个事务内完成"旧版本置为 superseded、新版本置为 active、写 decision_log"。

### 8.3 接口清单（示意）

| 方法与路径 | 功能 |
|---|---|
| `POST /api/plans/initial` | 提交初始调度作业 |
| `GET  /api/plans/{id}` | 查询计划（含分配） |
| `GET  /api/plans/{id}/diff?base=` | 与指定版本对比 |
| `POST /api/plans/{id}/commit` | 提交候选为 active（需 `base_version`） |
| `POST /api/plans/{id}/rollback` | 回滚 |
| `POST /api/events` | 上报事件（手动/仿真/Agent） |
| `GET  /api/events/{id}/impact` | 查看影响域 |
| `POST /api/agent/chat` | 对话入口（SSE 流式） |
| `POST /api/agent/confirm` | 提交约束确认结果 |
| `POST /api/agent/choose` | 选择候选方案 |
| `GET/POST /api/devices`、`/api/tasks`、`/api/constraints` | 资源与约束管理 |
| `POST /api/sim/start`、`/pause`、`/speed`、`/inject` | 仿真控制 |
| `GET  /api/sim/runs/{id}/metrics` | 仿真运行指标 |

**候选响应示例**

```json
{
  "base_version": 17,
  "candidates": [
    {"label": "最稳",
     "metrics": {"tardiness": 12, "moved": 3, "switched": 0, "urgent_end": "2026-11-05T16:30+08:00"},
     "neighborhood_level": 0,
     "diff": [{"task": "T-52", "change": "MOVED", "from": "2026-11-05T14:00", "to": "2026-11-05T15:30"}]},
    {"label": "最少延期",
     "metrics": {"tardiness": 0, "moved": 9, "switched": 2},
     "neighborhood_level": 1}
  ],
  "validator": {"passed": true, "violations": []},
  "explanation_consistency": 1.0
}
```

---

## 9. 前端设计

### 9.1 页面

| 页面 | 内容 |
|---|---|
| 资源管理 | 设备、人员、日历窗口（开放/维护）、准备时间矩阵 |
| 任务管理 | 实验与任务 DAG 的编辑、导入（CSV/JSON） |
| 计划视图 | 设备视图甘特图 / 实验视图；颜色：冻结、受影响、新增、延期 |
| 重规划工作台 | 事件列表、影响域高亮、候选对比、diff、解释、选择与提交 |
| 对话面板 | 自然语言输入；约束确认卡片；澄清问题；协商选项 |
| 仿真控制台 | 开始/暂停/倍速、注入事件、实时设备状态、指标曲线 |
| 版本与审计 | 版本树、回滚、决策记录 |

### 9.2 关键组件

- **甘特图**：可用现成库（dhtmlx-gantt / vis-timeline）或 ECharts 自定义系列；设备行显示阻塞区间（维护/故障）。
- **Diff 叠加视图**：旧计划为灰色底，新计划为彩色，箭头连接被移动的任务。
- **约束确认卡片**：每条抽取结果显示"系统理解"（回译）与可编辑字段，用户逐条确认。
- **候选对比**：表格 + 雷达图（延期、改动、紧急任务完成时间），每个候选带标签与 diff 摘要。
- **设备状态面板**：状态色块 + 状态时间轴（来自 `device_status_log`）。

### 9.3 交互原则

- 所有写操作都显示"将发生什么"的预览，用户确认后才提交。
- 低置信度的实体与时间用高亮和下拉候选，而不是静默采用。
- 重规划耗时较长时显示进度（邻域层级、已用时间、当前最好解）。

---

## 10. 技术栈与工程规范

### 10.1 技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| 前端 | Vue 3 + TypeScript + Element Plus + ECharts | 甘特图可用 dhtmlx-gantt/vis-timeline |
| 业务后端 | Spring Boot 3 + MyBatis-Plus（或 JPA） | 与课题表述一致 |
| 数据库 | PostgreSQL（或 MySQL）+ 可选 Redis | 载荷用 jsonb |
| Agent 服务 | Python 3.11 + FastAPI + LangGraph + Pydantic v2 | HITL 用 interrupt + checkpointer |
| 求解器 | **OR-Tools CP-SAT**（主）；Z3 可选 | CP-SAT 对可选区间、NoOverlap、Cumulative、hint、assumptions 支持成熟 |
| 大模型 | Qwen / DeepSeek / 智谱等 API | 适配层封装，实验中固定版本与温度 |
| 仿真 | 自研离散事件仿真（heapq + numpy） | 不依赖外部仿真框架，便于与内核集成 |
| 部署 | Docker Compose | 一键启动前端、后端、Agent、数据库 |
| 实验 | pandas + matplotlib + scipy | 结果 CSV + 绘图 |

### 10.2 目录结构

```
project/
├─ frontend/                  # Vue3
├─ backend/                   # Spring Boot
├─ agent/                     # FastAPI + LangGraph
│   ├─ graph/ (nodes, state)
│   ├─ tools/
│   ├─ prompts/ (版本化)
│   └─ eval/ (抽取与解释评测集与脚本)
├─ scheduler_core/            # 纯 Python 包
│   ├─ model/ (实体、IR)
│   ├─ solve/ (cpsat_model, initial, replan)
│   ├─ impact/ diagnose/ relax/ pareto/
│   ├─ validate/              # 独立校验器
│   └─ baselines/ (b1_llm, b2_full, b3_rule)
├─ simulator/                 # 纯 Python 包
│   ├─ clock.py events.py state_machine.py
│   ├─ adapters/ (simulated, manual, real_stub)
│   └─ scenarios/
├─ experiments/               # 实例生成、批量运行、指标、绘图、配置
├─ docs/
└─ docker-compose.yml
```

### 10.3 测试策略

| 层 | 方法 |
|---|---|
| 内核 | 单元测试 + **属性测试**（随机实例下，求解输出必须通过 Validator；影响域之外的任务必须未变） |
| 校验器 | 手工构造违反用例，确保每类违反都被检出（含反例） |
| 仿真器 | 状态机迁移合法性测试；同种子同日志（确定性回放） |
| Agent | 评测集回归（抽取 F1、解释一致率不得低于基线） |
| 集成 | 端到端脚本：注入事件 → 重规划 → 提交 → 状态更新 |
| 回归 | 把实验用例固定为回归集，防止改算法导致结果漂移 |

### 10.4 工程规范

- 配置（权重、时间预算、种子）全部外置到 YAML，实验配置随结果一起存档。
- 日志结构化（JSON），含 trace_id，贯穿前端 → 后端 → Agent → 内核。
- 所有实验结果带元数据：代码版本（git commit）、模型版本、求解器版本、种子、机器配置。

---

## 11. 评估方案

### 11.1 研究问题与实验映射

| 实验 | 内容 | 对应 RQ |
|---|---|---|
| E1 | 初始调度：CP-SAT vs EDD 规则 vs B1（大模型直接生成），随规模扩展 | RQ1 |
| E2 | **单事件重规划微基准**：B1a/B1b/B2/B3/M，规模 × 扰动强度 | RQ1、RQ2、RQ3 |
| E3 | **滚动仿真**：连续多事件，比较累计指标 | RQ2 |
| E4 | 消融：去稳定性项、去邻域扩张、去影响域、字典序 vs 加权 | RQ2、RQ3 |
| E5 | 参数灵敏度：β/α、邻域窗口 W、时间预算、时间槽粒度 | RQ2 |
| E6 | Agent 约束抽取评测（评测集 150–200 条） | RQ4 |
| E7 | 解释一致性评测 | RQ5 |
| E8 | 人机协同评估：模拟用户批量 + 小规模真人可用性 | RQ4、RQ6 |
| E9 | 案例研究：一个真实实验流程 | 补充 |

### 11.2 实例与扰动

| 规模 | 任务数 | 设备数 | 实验（DAG）数 |
|---|---|---|---|
| 小 | 20 | 5 | 6 |
| 中 | 60 | 10 | 15 |
| 大 | 150 | 20 | 35 |

- 设备紧张度（利用率）：60% / 80% / 95%；截止期松紧度因子：宽松 / 中等 / 紧。
- 扰动强度：轻 / 中 / 重（见 4.4）。
- 每组 **≥ 30 个随机种子**；固定求解时间上限与线程数。
- **配对设计**：同一实例与同一事件序列上比较所有方法。
- 大模型基线成本较高，仅在小/中规模各抽取子集评测，并写明。

### 11.3 指标定义

| 类别 | 指标 | 定义 |
|---|---|---|
| 可行性 | 硬约束违反率 | 含至少一条硬约束违反的方案数 / 方案总数（由 Validator 判定） |
| | 可行方案比例 | 求解/生成成功且通过校验的比例 |
| 质量 | 总延期代价 | `Σ w_i · T_i` |
| | 紧急任务完成时间 | 紧急任务 `e_i` 与其截止期之差 |
| 稳定性 | 改动数 / 换设备数 | `Σ moved_i`、`Σ switched_i` |
| | 平均偏移 | `mean(|s_i − s_i⁰|)`（仅对被改动任务） |
| 效率 | 求解耗时 | 墙钟时间，含建模 |
| | 层级分布 | 成功时的邻域层级占比 |
| | 最优性 gap | CP-SAT 报告的界 |
| 滚动仿真 | 累计延期、累计改动、重规划次数、平均每次改动数、计划偏差（实际 vs 计划开始）、设备利用率 | 在整个仿真视野内累计 |
| Agent | 约束抽取 P/R/F1 | 以 `(类型, 实体 id, 时间/数值)` 精确匹配 |
| | 实体解析准确率 | 解析 id 与标注一致的比例 |
| | 澄清触发 P/R | 应澄清的样本是否确实澄清 / 澄清是否必要 |
| | 解释一致率 | 一致断言数 / 总断言数；降级触发率 |
| 人机 | 交互轮数、任务完成时间、SUS 得分 | 模拟用户与真人 |

### 11.4 评测集构建（E6）

| 类别 | 占比建议 | 例 |
|---|---|---|
| 正常明确 | 25% | "D-03 在 11 月 5 日 14:00 到 11 月 6 日 9:00 停用" |
| 相对时间 | 15% | "明天下午""下周三""提前一天" |
| 实体歧义 | 15% | "3 号机"对应多个设备 |
| 缺参数 | 10% | 没有说明时长或设备 |
| 软硬不明 | 15% | "尽量别用 3 号机，除非实在没办法" |
| 多约束一句话 | 10% | 一句话含 3–5 条要求 |
| 与现有计划冲突 | 10% | 截止期早于释放时间、与冻结任务矛盾 |

- 每条标注标准 IR；至少两人独立标注并计算一致性（如 Cohen's κ）。
- 划分开发集与测试集，提示词调优只用开发集。

### 11.5 统计方法

- 配对比较用 **Wilcoxon 符号秩检验**，多重比较用 **Holm 校正**；报告效应量与 bootstrap 置信区间。
- 对随机性来源（求解多线程、大模型采样）重复运行并报告方差。
- 所有图表由脚本从原始 CSV 生成，保证可复现。

### 11.6 预期结论的写法（以实验为准）

- B1a 的硬约束违反率显著高于 0，且随规模上升；B1b 能降低但不保证为 0。
- B2 延期最小或接近，但改动数大。
- B3 耗时最短，但延期与可行性较差。
- M 在硬约束违反率为 0 的前提下，用较小改动达到接近 B2 的延期代价。
- 若某项不成立，需分析原因并如实报告（例如邻域扩张在小规模上优势不明显）。

---

## 12. 里程碑与交付物

| 阶段 | 内容 | 完成标准（DoD） |
|---|---|---|
| 1 | 需求分析、数据模型、状态模型；**内核 v0**（初始调度 + Validator）；实例生成器 | 命令行可跑通；属性测试通过 |
| 2 | **仿真器 v0**（状态机、事件队列、扰动模型、适配器接口）；基线 B2、B3 | 同种子可回放；基线完成 |
| 3 | 影响域 + 稳定性目标 + 邻域扩张；MUS 与松弛；Pareto 候选 | **核心算法完成**；内核实验初步结果 |
| 4 | Agent：IR 抽取流水线、LangGraph 状态图、HITL、解释与一致性；基线 B1 | Agent 服务可用；评测集初版 |
| 5 | Spring Boot 后端 + 前端（甘特图、diff、确认、对比、仿真控制台）；版本管理 | 演示模式端到端跑通 |
| 6 | 全面实验（E1–E9）、消融、灵敏度、可用性测试 | 数据与图表齐全，可复现脚本 |
| 7 | 论文撰写、答辩准备、演示视频 | 论文定稿；演示稿与备份 |

**建议顺序**：先内核与仿真器，后 Agent，最后界面；先实验后美化。预留约 15% 缓冲时间。

---

## 13. 风险与应对

| 风险 | 应对 |
|---|---|
| 没有真实设备，评审质疑真实性 | 适配器接口 + 调研参数 + 真实案例 + 公开基准映射；如实写局限 |
| 大规模求解过慢 | 时间上限 + anytime；邻域重规划缓解；必要时放宽时间槽 |
| MUS 抽取不稳定 | 约束分组降低粒度；限时；保留近似核 |
| 大模型输出波动 | 固定模型与温度；多层校验；评测多次运行取均值 |
| 大模型基线成本高 | 小/中规模抽样；缓存提示与输出；如实说明 |
| 工作量失控 | 多 Agent、偏好学习、序列相关准备时间等列为可选；主线不依赖 |
| 退化为问答系统 | 每阶段对照 1.5 自检清单 |
| 创新点与已有工作撞车 | 论文中明确差异；写作前补充检索知网与学位论文库；不写"首创" |

---

## 14. 文献依据与差异定位

> 以下文献通过公开检索获得。带"预印本"的尚未经同行评审；引用前请核对原文的作者、卷期与数字。我没有读到所有文献的全文，部分只看到摘要。

### 14.1 为什么需要求解器与校验器

| 文献 | 相关结论 |
|---|---|
| [1] TravelPlanner（ICML 2024） | 多约束旅行规划基准，GPT-4-Turbo 的最终通过率仅 0.6% |
| [2] NATURAL PLAN（2024） | 行程规划中 GPT-4、Gemini 1.5 Pro 求解率约 31%–35%；城市数增至 10 时所有模型低于 5% |
| [3] LLM-Modulo（ICML 2024，立场论文） | 主张大模型生成候选，外部验证器把关，人可参与 |
| [8] SCHEDBench（2026 预印本） | 自然语言调度基准，同一问题的不同表述会使模型表现不稳 |
| [12] DScheLLM（2026 预印本，全文） | 微调 7B 模型处理动态事件；仅在 FT06 上测试，快思考模式可行率 73.33%、最优率 46.67% |

### 14.2 为什么需要确认与澄清

| 文献 | 相关结论 |
|---|---|
| [4] Amonkar 等（预印本） | 大模型把问题形式化给求解器时，语义错误多来自约束定义错误（Qwen3 样本中占 95%，人工标注样本较小），且求解器无法发现 |
| [5] CLAMBER（ACL 2024） | 大模型识别并澄清歧义问题的能力有限 |
| [6] Flex-TravelPlanner（2025 研讨会） | 约束优先级处理不佳，新偏好可能压过既有约束 |
| [7] U-Define（2026 预印本） | 硬/软约束分开处理与验证 |

### 14.3 相近的"大模型 + 求解/验证"与实验室调度工作

| 文献 | 内容 | 与本课题差异 |
|---|---|---|
| [9] SafeRun（2026 预印本） | 大模型翻译为求解器规格，确定性求解器保证硬约束 | 领域为跑步计划，无扰动重规划 |
| [10] IMA-LLM（Computers & Industrial Engineering, 2026） | 多智能体 + 生成—验证闭环用于作业车间建模 | 侧重静态建模 |
| [11] 李明星等（工程科学学报, 2026） | 多智能体协同推理架构，摘要称建模成功率提高 29.65% | 侧重建模，无稳定重规划与人机协商 |
| [13] McDannald 等（2026 预印本，来自第三方摘要页） | 实验室机器人调度建为作业车间 + CP；新实验加入时对剩余任务整体重算 | 无稳定性目标，无自然语言接口 |
| [14] Angelopoulos 等（2026 预印本） | 实验室自动化智能体：工具调用 + 协议校验与错误反馈 | 重点在协议生成而非调度优化 |
| [15] Destouet 等（J. Intell. Manuf., 2025） | 动态柔性作业车间调度综述 | 综述，用于梳理扰动与指标 |
| [16] Hancerliogullari Koksalmis 等（Aeronautical Journal, 2025） | 重调度以与初始计划一致性为稳定性指标，比较修复与再生成 | 机场跑道领域，属类比 |

### 14.4 差异定位

- 在我检索到的材料中，**未见**将下列几项放在同一系统中：① 自然语言约束的回译确认；② 扰动下对延期与计划改动的显式权衡及邻域扩张；③ 无解时的冲突核与最小松弛协商；④ 解释与求解证据的一致性校验；⑤ 面向实验室设备调度并提供仿真评估框架。
- 该判断依赖检索范围。**写作前请再用知网、Web of Science、Google Scholar 检索一轮**（关键词见下），并在论文中写为"现有工作较少关注……"，不要写"首次提出"。
- 建议检索关键词——中文：大语言模型 + 作业车间/实验室调度、动态重调度 + 稳定性、插单重排、人机协同调度、可解释调度、约束规划 + 大模型；英文：LLM job shop dynamic rescheduling, LLM constraint programming scheduling, stability-aware rescheduling, reactive scheduling schedule deviation, human-in-the-loop scheduling LLM, laboratory scheduling constraint programming。

### 14.5 参考文献（本文件内编号，与旧版附录不同）

[1] Xie J, et al. TravelPlanner: A Benchmark for Real-World Planning with Language Agents. ICML, 2024. arXiv:2402.01622.
[2] Zheng H S, et al. NATURAL PLAN: Benchmarking LLMs on Natural Language Planning. arXiv:2406.04520, 2024.
[3] Kambhampati S, et al. Position: LLMs Can't Plan, But Can Help Planning in LLM-Modulo Frameworks. ICML, PMLR 235, 2024. arXiv:2402.01817.
[4] Amonkar R, Kayan C E, Lai M, Le Bras R, Zhang L. Large Language Models as Formalizers on Constraint Satisfaction Problems. arXiv:2505.13252（预印本）.
[5] Zhang T, et al. CLAMBER: A Benchmark of Identifying and Clarifying Ambiguous Information Needs in Large Language Models. ACL 2024. arXiv:2405.12063.
[6] Oh J, Kim E, Oh A. Flex-TravelPlanner: A Benchmark for Flexible Planning with Language Agents. ICLR 2025 Workshop on Reasoning and Planning for LLMs. arXiv:2506.04649.
[7] U-Define: Designing User Workflows for Hard and Soft Constraints in LLM-Based Planning. arXiv:2605.02765, 2026（预印本）.
[8] SCHEDBench: A Benchmark for Evaluating LLM Constraint Faithfulness in Natural-Language Combinatorial Scheduling. arXiv:2608.00991, 2026（预印本）.
[9] SafeRun: Enabling Determinism in LLM Planning for Running. arXiv:2606.09027, 2026（预印本）.
[10] Yan J, Ji S. Industrial mechanism-aware multi-agent collaboration of large language models for job shop scheduling optimization. Computers & Industrial Engineering, 2026, 217: 112079.
[11] 李明星, 周曲, 陈柳诗, 唐辉君, 屈挺. 大模型和智能体AI驱动的生产–物流先进计划与调度建模推理方法[J]. 工程科学学报, 2026. DOI: 10.13374/j.issn2095-9389.2026.03.22.001.
[12] Zhang L, Zhao C, Gao Q, Zhao X, Bai G, Lv J. DScheLLM: Enabling Dynamic Scheduling through a Fine-Tuned Dual-System Large Language Model. arXiv:2601.09100, 2026（预印本）.
[13] McDannald A, Tisaranni J, Joress H. Optimal Resource Utilization for Autonomous Laboratory Orchestrators. arXiv:2607.01188, 2026（预印本）.
[14] Angelopoulos A, et al. From Prompts to Protocols: An AI Agent for Laboratory Automation. arXiv:2605.16552, 2026（预印本）.
[15] Destouet C, Tlahig H, Bettayeb B, Mazari B. Systematic Review and Future Directions in Dynamic Flexible Job Shop Scheduling: A Decade of Research. Journal of Intelligent Manufacturing, 2025. DOI: 10.1007/s10845-025-02645-x.
[16] Hancerliogullari Koksalmis G, Rabadi G, Kharbeche M, Al-Salem M. A mathematical model and heuristic approaches for runway rescheduling. The Aeronautical Journal, 2025. DOI: 10.1017/aer.2025.16.

---

## 15. 论文大纲与模块对应

| 章 | 标题（建议） | 对应本文档 |
|---|---|---|
| 1 | 绪论：背景、问题、相关工作、研究内容与贡献 | 1、14 |
| 2 | 需求分析与总体设计 | 2、3 |
| 3 | 多约束调度建模与初始计划生成 | 5、6.1 |
| 4 | 动态事件下的稳定性感知重规划 | 6.2–6.8 |
| 5 | 人机协同智能体设计 | 7 |
| 6 | 仿真环境与系统实现 | 4、8、9、10 |
| 7 | 实验与分析 | 11 |
| 8 | 总结与展望（含局限：无真实设备在线验证） | 4.9、13 |

---

## 16. 范围控制：最低可交付（MVP）与加分项

**MVP（必须完成）**

- 多约束建模 + CP-SAT 初始调度 + 独立 Validator
- 设备状态机 + 离散事件仿真 + 事件注入面板 + 适配器接口
- 设备停用、紧急插入两类事件的重规划，含稳定性目标与邻域扩张
- NL → IR 抽取 + 回译确认
- 候选方案（≥ 3 个）对比与 diff 展示；版本与确认记录
- 基线 B1/B2/B3 与主对比实验（E1、E2）、消融（E4）、Agent 抽取评测（E6）

**加分项（按收益排序）**

1. 滚动仿真评估（E3）与参数灵敏度（E5）
2. 冲突核诊断与最小松弛建议
3. 解释一致性校验（E7）
4. 真实案例研究（E9）与真人可用性测试
5. 工期超时、人员缺席等更多事件类型；序列相关准备时间（`AddCircuit`）
6. 多种邻域规则对比；偏好反馈调权

---

## 附录 A：关键表 DDL（示意，PostgreSQL）

```sql
CREATE TABLE device (
  id           TEXT PRIMARY KEY,
  type_id      TEXT NOT NULL REFERENCES device_type(id),
  name         TEXT NOT NULL,
  capacity     INT  NOT NULL DEFAULT 1,
  status       TEXT NOT NULL CHECK (status IN ('IDLE','SETUP','BUSY','MAINTENANCE','FAULT','OFFLINE')),
  version      BIGINT NOT NULL DEFAULT 0
);

CREATE TABLE device_calendar_window (
  id         BIGSERIAL PRIMARY KEY,
  device_id  TEXT NOT NULL REFERENCES device(id),
  start_at   TIMESTAMPTZ NOT NULL,
  end_at     TIMESTAMPTZ NOT NULL,
  kind       TEXT NOT NULL CHECK (kind IN ('OPEN','MAINT','BLOCK')),
  source     TEXT NOT NULL,
  CHECK (end_at > start_at)
);
CREATE INDEX idx_dcw_device_time ON device_calendar_window(device_id, start_at);

CREATE TABLE task (
  id                 TEXT PRIMARY KEY,
  experiment_id      TEXT NOT NULL REFERENCES experiment(id),
  type               TEXT NOT NULL,
  planned_duration   INT  NOT NULL,         -- 分钟
  release_time       TIMESTAMPTZ,
  deadline           TIMESTAMPTZ,
  deadline_level     TEXT NOT NULL DEFAULT 'NEGOTIABLE' CHECK (deadline_level IN ('HARD','NEGOTIABLE')),
  preemptible        BOOLEAN NOT NULL DEFAULT FALSE,
  status             TEXT NOT NULL CHECK (status IN
                     ('PENDING','SCHEDULED','RUNNING','DONE','INTERRUPTED','FAILED','CANCELLED')),
  version            BIGINT NOT NULL DEFAULT 0
);

CREATE TABLE plan_version (
  id               BIGSERIAL PRIMARY KEY,
  parent_id        BIGINT REFERENCES plan_version(id),
  status           TEXT NOT NULL CHECK (status IN ('draft','confirmed','active','superseded','rejected')),
  metrics          JSONB,
  trigger_event_id BIGINT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  version          BIGINT NOT NULL DEFAULT 0
);
-- 同一时刻只允许一个 active 版本
CREATE UNIQUE INDEX uq_plan_active ON plan_version((1)) WHERE status = 'active';

CREATE TABLE plan_assignment (
  plan_id        BIGINT NOT NULL REFERENCES plan_version(id),
  task_id        TEXT   NOT NULL REFERENCES task(id),
  device_id      TEXT   NOT NULL REFERENCES device(id),
  person_id      TEXT,
  planned_start  TIMESTAMPTZ NOT NULL,
  planned_end    TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (plan_id, task_id)
);
```

## 附录 B：术语表

| 术语 | 含义 |
|---|---|
| HARD / SOFT / NEGOTIABLE | 硬约束 / 软约束 / 可协商约束 |
| IR | 约束与事件的中间表示（结构化 JSON） |
| 冻结集 F | 已开始或已完成、不可改动的任务 |
| 影响域 A | 受事件直接或间接影响的待执行任务 |
| 邻域层级 | 重规划时放开的任务集合的大小级别 |
| MUS | 最小不可满足核 |
| 回译确认 | 把结构化约束翻译回自然语言给用户确认 |
| HITL | Human-in-the-Loop，人在回路 |
| 适配器 | 设备状态的统一接口，仿真与真实设备可互换 |
| 滚动仿真 | 在连续多个事件下运行整个视野的评估方式 |
