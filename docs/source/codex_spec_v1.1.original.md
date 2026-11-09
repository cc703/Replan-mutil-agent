# Codex 开发规格包 v1.1
# 面向多约束场景的任务动态调度与重规划 Agent

> 用途：配合《毕业设计_完整设计框架_v2.md》，把设计变成 Codex 可分阶段执行的任务。
> 设计文档回答"做什么、为什么"；本文件回答"接口长什么样、怎么算做完"。
> v1.1 新增：文件与产出物规范（第 2 节）——精简的目录结构、中间产物统一存放、命名与清理规则、仓库卫生检查。

---

## 0. 使用方式（先读）

1. 把第 1 节的内容保存为仓库根目录的 `AGENTS.md`。
2. 把《完整设计框架 v2》放到 `docs/design_v2.md`，把本文件放到 `docs/codex_spec.md`。
3. **一次只给 Codex 一个阶段任务**（第 6 节），做完跑验收测试、你审查、提交，再进入下一阶段。不要一次要求全部完成。
4. 每个阶段开始前，让 Codex 先阅读 `AGENTS.md`、对应设计章节和本文件对应小节，并**先给出计划，经你确认再动手**。
5. 第 7 节记录了已定的技术决策，Codex 不得擅自更改。

> **现实提醒**：即使有这份规格，Codex 也不能一次做完整个系统。算法正确性（尤其重规划和冲突诊断）和前端体验需要你审查与调参。

---

## 1. AGENTS.md（放仓库根目录）

```markdown
# AGENTS.md

## 项目
面向多约束场景的任务动态调度与重规划 Agent（本科毕业设计）。
设计文档：docs/design_v2.md；开发规格：docs/codex_spec.md。

## 核心原则（不可违反）
1. 计划只能由约束求解器（OR-Tools CP-SAT）生成，大模型不得直接输出调度结果。
2. 任何展示给用户或写入正式版本的计划，必须先通过 scheduler_core.validate（独立校验器，不复用 CP-SAT 模型）。
3. scheduler_core 与 simulator 是纯 Python 包：不得依赖数据库、Web 框架或大模型。
4. 改变正式计划的操作必须经过用户确认（L2），改变系统理解的操作（约束/事件）需要确认（L1）。
5. 大模型输出一律视为不可信输入，必须经 Pydantic 校验与语义校验。

## 技术约定
- Python 3.11；类型标注必须完整；使用 pydantic v2。
- 内部时间一律用整数"槽"（slot），通过 TimeAxis 与 datetime 互转；数据库存 UTC，业务时区 Asia/Shanghai。
- 随机性只用 numpy.random.Generator(PCG64(seed))；不同扰动使用独立子流。
- 所有可调参数放 YAML 配置，不写死在代码里。
- 日志用结构化 JSON，带 trace_id。

## 大模型约定
- 服务：DeepSeek API；所有调用经 `src/agent/llm.py` 适配层，其他代码不得直接调用。
- 模型名与参数只从 `src/agent/defaults.yaml` 读取，不得写死；密钥只从环境变量 `DEEPSEEK_API_KEY` 读取。
- 使用前先查阅官方文档确认当前可用的模型 id 与参数，不要凭记忆写。
- 抽取与解释用非思考模式、温度 0；所有输出必须经 Pydantic 校验，不依赖服务端 strict。

## 依赖与 API 使用
- 依赖版本以锁文件为准；新增依赖前先说明理由。
- 使用 OR-Tools、LangGraph 等库的 API 前，先查看**已安装版本**的文档或源码确认签名，不要凭记忆写。
- 遇到不确定的 API，写最小可运行示例验证，再接入主代码。

## 工作方式
- 每次任务开始先给出计划与将创建/修改的文件列表，等待确认。
- 每个模块先写测试再写实现；完成后运行全部测试并报告结果。
- 不修改与当前任务无关的文件；不做未被要求的重构。
- 不确定的设计问题，列出选项和你的推荐，由我决定；不要擅自决定。

## 文件与产出物规则（不可违反）
1. 所有机器生成的中间产物（实例缓存、运行结果、日志、LLM trace、图表草稿、临时文件）只能写入 `artifacts/`，且必须通过 `scheduler_core.io.artifacts.ArtifactStore` 创建路径；禁止在代码里硬编码输出路径，禁止写到仓库根目录或源码目录。
2. 每次运行的目录名为 `<run_id>`，格式 `YYYYMMDD-HHMMSS_<git短哈希>_<标签>`；目录内必须有 `manifest.json`（字段见 docs/codex_spec.md 2.4）。已完成（status=completed）的运行目录视为只读，重跑必须产生新的 run_id。
3. 路径与文件名只用小写 ASCII、数字、下划线、连字符，不含空格和中文；中文只出现在文档内容里。
4. 临时文件放 `artifacts/tmp/`，测试里用 pytest 的 `tmp_path`；任何代码不得依赖 tmp 里的内容。仓库内不保留一次性脚本；确需临时脚本，放 `artifacts/tmp/`，用完即删。可复用的维护脚本放 `tools/` 并写明用途。
5. 入库的"输入类"数据放 `data/`，实验与场景配置放 `experiments/configs/`，入库的"最终结果"放 `docs/results/`（只有经我审核的图表和表格）。其余生成物一律不入库。
6. 不得在仓库里留下未说明的文件：笔记、草稿、截图、.log、.csv、.png 等不能出现在源码目录。每个任务结束时列出"新增/修改/删除文件清单"，并说明每个新增文件的用途。
7. 提示词、评测集一律版本化：`src/agent/prompts/<name>/v001.md`、`data/eval_sets/<name>/v001.jsonl`，不覆盖旧版本，改动产生新版本并写入 CHANGELOG。
8. 不得提交密钥与个人信息：使用 `.env`（不入库）与 `.env.example`；LLM trace 写盘前必须脱敏。
9. 每次提交前运行 `make check`（含仓库布局检查）；未通过不得结束任务。

## 命令
- 安装：`uv sync`（或 pip install -e .[dev]）
- 测试：`pytest -q`
- 类型检查：`mypy src`
- 格式化：`ruff check . && ruff format .`

## 完成的定义（Definition of Done）
- 对应阶段的验收测试全部通过；mypy 和 ruff 无错误。
- 公共函数有 docstring，说明输入输出与约束。
- 新增行为有测试覆盖；README 或 docs 更新了使用方式。
```

---

## 2. 仓库骨架与产出物规范

### 2.1 目录总览（根目录只保留这些）

```
project/
├─ AGENTS.md  README.md  Makefile  pyproject.toml  uv.lock  docker-compose.yml
├─ docs/          文档：设计、规格、决策记录、最终结果
├─ src/           Python 核心代码
│   ├─ scheduler_core/    建模、求解、重规划、校验、基线
│   ├─ simulator/         状态机、事件仿真、适配器
│   └─ agent/             LangGraph、工具、提示词
├─ apps/          可部署应用
│   ├─ backend/           Spring Boot
│   └─ frontend/          Vue 3
├─ experiments/   实验代码与实验配置
├─ data/          入库的输入数据（测试实例、评测集、调研参数）
├─ tests/         测试
├─ tools/         仓库维护工具
└─ artifacts/     机器生成物（不入库，布局见 2.3）
```

隐藏文件仅限 `.gitignore`、`.env.example`。除此之外，根目录不得新增任何文件或目录。

### 2.2 各目录内部结构

| 目录 | 内部结构 |
|---|---|
| `docs/` | `design_v2.md`、`codex_spec.md`；`decisions/`（设计决策，编号命名如 `0001-time-slot.md`）；`results/`（`figures/`、`tables/`、`INDEX.md`，经审核的最终结果） |
| `src/scheduler_core/` | `models.py` `axis.py` `validate.py` `generate.py` `solve_initial.py` `impact.py` `replan.py` `diagnose.py` `relax.py` `pareto.py`；子包 `baselines/`（`b2_full.py` `b3_rule.py` `b1_llm.py`）、`io/`（`artifacts.py` `manifest.py`） |
| `src/simulator/` | `states.py` `events.py` `engine.py` `scenarios.py`；子包 `adapters/`（`base.py` `simulated.py` `manual.py`） |
| `src/agent/` | `graph/` `tools/` `eval/`；`prompts/<name>/v001.md`（版本化）；`defaults.yaml` |
| `apps/backend/` | Spring Boot 工程；数据库迁移 `db/migration/V001__init.sql` |
| `apps/frontend/` | Vue 3 工程 |
| `experiments/` | `run.py` `metrics.py` `stats.py` `plots.py`；`configs/scenarios/`、`configs/experiments/`（如 `E2.yaml`） |
| `data/` | `fixtures/`（测试最小实例）、`eval_sets/<name>/`（`v001.jsonl`、`CHANGELOG.md`）、`survey/`（调研记录）、`benchmarks/`（基准映射说明，不放大文件） |
| `tests/` | `unit/` `property/` `integration/` |
| `tools/` | `check_repo_layout.py` `clean_artifacts.py` `archive_run.py` `make_report.py` |

**三类数据的区别**

| 类别 | 位置 | 是否入库 | 谁写入 |
|---|---|---|---|
| 输入类（人工维护） | `data/`、`experiments/configs/` | 是 | 你与 Codex（需说明） |
| 中间产物（可再生） | `artifacts/` | **否** | 程序，经 `ArtifactStore` |
| 最终结果（经审核） | `docs/results/` | 是 | 只能由 `tools/make_report.py` 从某次运行复制 |

### 2.3 artifacts/ 布局（所有生成物只能放这里）

```
artifacts/
├─ README.md        # 唯一入库的文件
├─ instances/       # 实例缓存：<scale>_u<util>_t<tight>_s<seed>/instance.json
├─ runs/            # 所有运行：<kind>/<name>/<run_id>/
├─ llm_traces/      # <yyyy-mm-dd>/<session_id>.jsonl（已脱敏）
├─ logs/            # <service>/<yyyy-mm-dd>.jsonl
├─ archive/         # 已完成并压缩的运行
└─ tmp/             # 临时文件，可随时清空，任何代码不得依赖
```

`runs/` 下 `kind` 取 `experiment`、`sim`、`agent_eval` 三种。**一次运行的所有输出都放在它自己的目录里**，包括求解器日志，不再另设顶层目录。

**一个运行目录的内部结构**

```
artifacts/runs/experiment/E2_replan_micro/20261110-153000_a1b2c3d_small-light/
├─ manifest.json    # 必须有，见 2.4
├─ config.yaml      # 本次运行实际使用的配置副本
├─ raw.csv          # 逐样本原始结果（方法 × 实例 × 种子）
├─ summary.csv      # 汇总指标（由 raw.csv 生成）
├─ events/          # 事件日志（jsonl），用于回放
├─ plans/           # 各方法产生的计划（json）
├─ figs/            # 图表草稿
└─ logs/            # 运行与求解器日志（jsonl）
```

**命名与格式**

| 项 | 约定 |
|---|---|
| `run_id` | `YYYYMMDD-HHMMSS_<git短哈希>_<标签>`；标签为短小写词，如 `small-light`、`ablate-no-stab` |
| 表格 | CSV（UTF-8，首行表头，时间用 ISO 8601，布尔用 true/false） |
| 日志与事件 | JSON Lines |
| 单个对象 | JSON；配置用 YAML |
| 图表 | 草稿 png；入库版本用 svg 或 pdf |
| 路径与文件名 | 小写 ASCII、数字、`_`、`-`；无空格、无中文 |

### 2.4 manifest.json（每次运行必须生成）

```json
{
  "run_id": "20261110-153000_a1b2c3d_small-light",
  "kind": "experiment",
  "name": "E2_replan_micro",
  "status": "completed",
  "started_at": "2026-11-10T15:30:00+08:00",
  "ended_at":   "2026-11-10T16:12:40+08:00",
  "command": "python -m experiments.run --config experiments/configs/experiments/E2.yaml",
  "git": {"commit": "a1b2c3d...", "dirty": false},
  "config_sha256": "…",
  "seeds": [0, 1, 2],
  "versions": {"python": "3.11.x", "ortools": "x.y.z", "langgraph": "x.y.z"},
  "llm": {"provider": "…", "model": "…", "temperature": 0},
  "inputs": ["artifacts/instances/small_u0.8_t0.5_s0/instance.json"],
  "outputs": ["raw.csv", "summary.csv", "figs/f1_tardiness.png"]
}
```

- `status`：`running`、`completed`、`failed`、`partial`。开始即写 `running`，结束时更新。
- `dirty = true`（工作区有未提交改动）的运行，不得用于 `docs/results/`。

### 2.5 写入规则

1. 所有产出物路径由 `ArtifactStore` 提供：

```python
store = ArtifactStore(root="artifacts")
run = store.new_run(kind="experiment", name="E2_replan_micro", tag="small-light")
run.path("raw.csv")                       # 返回 Path，并确保父目录存在
run.write_json("plans/inst1_m.json", obj)
run.finish(status="completed", outputs=[...])   # 更新 manifest，并把目录设为只读
```

2. 禁止硬编码输出路径（如 `open("results.csv","w")`、`plt.savefig("fig.png")`），禁止写入 `src/`、`experiments/` 等源码目录和仓库根目录。
3. 已完成的运行目录只读；重跑一律新建 `run_id`，不覆盖。
4. 实例缓存按内容寻址（由 `scale/utilization/tightness/seed` 决定目录名），已存在则复用。
5. LLM trace 写盘前脱敏（去除密钥与个人信息）。

### 2.6 保留、清理与最终结果入库

| 对象 | 规则 |
|---|---|
| `artifacts/tmp/` | 保留不超过 7 天 |
| 失败或中断的运行（status ≠ completed） | 保留 14 天，之后可清 |
| 已完成的运行 | 保留；论文定稿后用 `tools/archive_run.py` 压缩到 `artifacts/archive/` |
| 被 `docs/results/INDEX.md` 引用的运行 | **永不清理** |
| 清理命令 | `python tools/clean_artifacts.py --kind tmp --older-than 7d`（默认 dry-run，加 `--apply` 才删除） |

**最终结果入库流程**

```
artifacts/runs/.../<run_id>/figs/f1.png  --(你审核)-->  python tools/make_report.py --run <run_id> --select figs/f1.png
  → 复制到 docs/results/figures/<name>__f1_tardiness.svg
  → 在 docs/results/INDEX.md 追加：文件名、run_id、git commit、生成命令、一句话说明
```

`make_report.py` 拒绝 `dirty=true` 或 `status≠completed` 的运行。论文里的每张图表都必须能在 `INDEX.md` 找到来源。

### 2.7 仓库卫生检查（tools/check_repo_layout.py，纳入 pytest 与 `make check`）

| 检查 | 规则 |
|---|---|
| 根目录白名单 | 只允许：`AGENTS.md README.md Makefile pyproject.toml uv.lock docker-compose.yml .gitignore .env.example docs src apps experiments data tests tools artifacts` |
| 源码目录无生成物 | `src/`、`apps/`、`experiments/`（`experiments/configs` 除外）下不得出现 `.log .csv .jsonl .png .svg .tmp` 等 |
| `artifacts/` 不入库 | 除 `artifacts/README.md` 外必须被 `.gitignore` 忽略 |
| 运行目录完整 | `artifacts/runs/*/*/*` 每个目录必须有合法的 `manifest.json` |
| 文件名规范 | 非 `docs/` 路径只允许小写 ASCII、数字、`_`、`-`、`.` |
| 体积 | 入库文件 ≤ 1 MB（`data/fixtures` 与白名单例外） |
| 无缓存入库 | 不得入库 `__pycache__`、`.pytest_cache`、`.venv`、`node_modules` |
| 版本化文件 | `src/agent/prompts/<name>/` 与 `data/eval_sets/<name>/` 下文件必须形如 `v###.*`，已有版本不得被修改 |

**.gitignore（要点）**

```
artifacts/*
!artifacts/README.md
.env
__pycache__/  .pytest_cache/  .mypy_cache/  .ruff_cache/  .venv/  node_modules/
*.log
```

**Makefile 目标**

```
make check        # ruff + mypy + pytest + check_repo_layout
make clean-tmp    # 清理 artifacts/tmp（dry-run）
make report RUN=<run_id> SELECT=<path>
```

---

## 3. 数据契约（src/scheduler_core/models.py）

> 这是全项目的"公共语言"。Codex 在阶段 1 先实现并**冻结**这些模型；之后修改必须经你确认。

```python
from __future__ import annotations
from datetime import datetime
from typing import Literal, Annotated, Union
from pydantic import BaseModel, Field

Slot = int  # 距 TimeAxis.t0 的槽数

class TimeAxis(BaseModel):
    t0: datetime                      # 带时区
    slot_minutes: int = 5
    horizon_slots: int                # 视野 H
    def to_slot(self, dt: datetime) -> Slot: ...
    def to_dt(self, slot: Slot) -> datetime: ...

class Device(BaseModel):
    id: str
    type: str
    capacity: int = 1                 # >1 时用 Cumulative
    capabilities: set[str] = set()

class Task(BaseModel):
    id: str
    experiment_id: str
    type: str
    duration: int                     # 槽
    release: Slot = 0
    deadline: Slot | None = None
    deadline_level: Literal["HARD", "NEGOTIABLE"] = "NEGOTIABLE"
    weight: float = 1.0               # 延期权重 w_i
    compatible_devices: list[str]
    preemptible: bool = False
    status: Literal["PENDING","SCHEDULED","RUNNING","DONE",
                    "INTERRUPTED","FAILED","CANCELLED"] = "PENDING"
    demand: int = 1                   # 占用设备容量

class Precedence(BaseModel):
    pred: str
    succ: str
    lag_min: int = 0
    lag_max: int | None = None

class BlockedWindow(BaseModel):
    device_id: str
    start: Slot
    end: Slot                         # 左闭右开
    kind: Literal["CLOSED", "MAINT", "FAULT", "RUNNING"]

class SetupRule(BaseModel):           # MVP：按(设备, 目标任务类型)的固定前置准备
    device_id: str
    task_type: str
    slots: int

class Instance(BaseModel):
    axis: TimeAxis
    now: Slot = 0
    devices: list[Device]
    tasks: list[Task]
    precedences: list[Precedence] = []
    blocked: list[BlockedWindow] = []
    setups: list[SetupRule] = []

class Assignment(BaseModel):
    task_id: str
    device_id: str
    start: Slot
    end: Slot

class PlanMetrics(BaseModel):
    tardiness: float = 0.0            # Σ w_i T_i
    makespan: int = 0
    moved: int = 0
    switched: int = 0
    shift_total: int = 0
    urgent_delay: float = 0.0
    solve_seconds: float = 0.0
    gap: float | None = None

class Plan(BaseModel):
    id: str
    parent_id: str | None = None
    assignments: dict[str, Assignment]   # task_id -> Assignment
    metrics: PlanMetrics = PlanMetrics()

# ---- 事件（可判别联合）----
class DeviceOutage(BaseModel):
    type: Literal["DEVICE_OUTAGE"] = "DEVICE_OUTAGE"
    device_id: str
    start: Slot
    end: Slot

class UrgentInsert(BaseModel):
    type: Literal["URGENT_INSERT"] = "URGENT_INSERT"
    tasks: list[Task]
    precedences: list[Precedence] = []

class TaskOverrun(BaseModel):
    type: Literal["TASK_OVERRUN"] = "TASK_OVERRUN"
    task_id: str
    new_end: Slot

Event = Annotated[Union[DeviceOutage, UrgentInsert, TaskOverrun], Field(discriminator="type")]

# ---- 校验 ----
class Violation(BaseModel):
    code: Literal["V1","V2","V3","V4","V5","V6","V7","V8","V9","V10","V11"]
    task_ids: list[str] = []
    device_id: str | None = None
    detail: str

class ValidationReport(BaseModel):
    passed: bool
    violations: list[Violation] = []

# ---- 重规划 ----
class ReplanParams(BaseModel):
    alpha: float = 1.0
    beta_moved: float = 2.0
    beta_switched: float = 5.0
    beta_shift: float = 0.1
    gamma: float = 5.0
    total_budget_s: float = 10.0
    window_slots: int = 48            # 邻域窗口 W（5 分钟槽下 4 小时）
    max_level: int = 3
    weight_grid: list[tuple[float, float]] = [(1, 0.5), (1, 1), (1, 2), (1, 4)]
    seed: int = 0
    num_workers: int = 8

class ImpactReport(BaseModel):
    frozen: set[str]
    affected: set[str]
    unaffected: set[str]
    reasons: dict[str, str]           # task_id -> 原因

class Candidate(BaseModel):
    plan: Plan
    level: int
    weights: tuple[float, float]
    f1: float; f2: float; f3: float
    label: str | None = None
    validation: ValidationReport

class ConflictCore(BaseModel):
    group_ids: list[str]              # 约束组 id
    descriptions: list[str]

class RelaxationOption(BaseModel):
    description: str
    cost: float
    relaxed_groups: list[str]

class ReplanResult(BaseModel):
    status: Literal["OK", "INFEASIBLE", "TIMEOUT"]
    candidates: list[Candidate] = []
    impact: ImpactReport | None = None
    level_reached: int | None = None
    conflict: ConflictCore | None = None
    relaxations: list[RelaxationOption] = []
```

---

## 4. 模块接口签名

### 4.1 scheduler_core

```python
# validate.py —— 独立实现：不得 import ortools
def validate(inst: Instance, plan: Plan, *, base: Plan | None = None,
             free: set[str] | None = None) -> ValidationReport: ...

# solve_initial.py
def solve_initial(inst: Instance, *, time_limit_s: float = 30,
                  num_workers: int = 8, seed: int = 0,
                  objective_weights: dict[str, float] | None = None) -> Plan | None: ...

# impact.py
def analyze_impact(inst: Instance, plan: Plan, events: list[Event],
                   window_slots: int) -> ImpactReport: ...
def apply_events(inst: Instance, events: list[Event]) -> Instance: ...   # 产生新实例，不原地修改

# replan.py
def replan(inst: Instance, plan0: Plan, events: list[Event],
           params: ReplanParams) -> ReplanResult: ...

# diagnose.py
def diagnose(inst: Instance, plan0: Plan | None, free: set[str],
             *, time_limit_s: float = 5) -> ConflictCore | None: ...

# relax.py
def suggest_relaxations(inst: Instance, plan0: Plan | None, free: set[str],
                        core: ConflictCore, *, k: int = 3) -> list[RelaxationOption]: ...

# pareto.py
def select_candidates(pool: list[Candidate], *, max_n: int = 5,
                      dedupe_l1: int = 3) -> list[Candidate]: ...

# generate.py
def generate_instance(scale: Literal["S","M","L"], utilization: float,
                      deadline_tightness: float, seed: int) -> Instance: ...

# baselines
def b2_full_replan(inst, plan0, events, params, *, with_stability: bool = False) -> Plan | None: ...
def b3_rule_repair(inst, plan0, events) -> Plan: ...
def b1_llm_replan(inst, plan0, events, llm, *, feedback_rounds: int = 0) -> Plan | None: ...
```

**约定**

- 所有函数**不修改入参**；返回新对象。
- `replan` 返回的每个候选都已通过 `validate`；未通过的不得进入 `candidates`。
- 冻结任务（`status` 为 RUNNING/DONE，或 `start < inst.now`）的 `(device, start)` 在任何结果中不得改变。

### 4.2 simulator

```python
# adapters/base.py
class DeviceAdapter(Protocol):
    def list_devices(self) -> list[Device]: ...
    def get_status(self, device_id: str) -> str: ...
    def subscribe(self, cb: Callable[[SimEvent], None]) -> None: ...

# engine.py
class Simulator:
    def __init__(self, inst: Instance, plan: Plan, scenario: Scenario,
                 scheduler: Callable[[Instance, Plan, list[Event]], Plan | None],
                 seed: int): ...
    def run(self, t_end: Slot) -> SimResult: ...       # SimResult 含事件日志、指标
    def inject(self, ev: Event, at: Slot) -> None: ...
    def replay(self, log: list[SimEventRecord]) -> SimResult: ...
```

### 4.3 Agent 工具（src/agent/tools）

工具函数的输入输出一律使用第 3 节的 Pydantic 模型；每个工具标注级别 L0/L1/L2（见设计文档 7.4）。**写操作工具必须校验"已确认标志"，未确认直接拒绝。**

---

## 5. 示例数据与黄金测试

### 5.1 最小实例 `data/fixtures/mini.json`

- 设备：D1、D2（同类型，容量 1）；视野 40 槽，`now = 0`。
- 任务（均可用 D1、D2）：A（4 槽）、B（4 槽，前驱 A）、C（6 槽）、D（6 槽）。

**黄金断言（初始调度，目标仅为最大完工时间）**

| 断言 | 说明 |
|---|---|
| `validate(...)` 通过 | 必须 |
| 最优 makespan = 10 | 总工作量 20、两台设备，下界 10；例如 D1：A(0–4)、C(4–10)；D2：D(0–6)、B(6–10) |
| 任一任务不重叠、A 在 B 之前 | |

### 5.2 不可行用例

- 任务 X：duration = 4，`deadline = 3`，`deadline_level = HARD`。
- 断言：`solve_initial` 返回 None；`diagnose` 返回的核**只包含** X 的截止期组，不含无关约束。

### 5.3 稳定性用例

- 在 5.1 的计划上，于 `now = 2` 对 D2 注入停用 `[6, 10)`。
- 断言（属性，不写死具体解）：
  - 所有候选通过校验；冻结任务（`start < 2`）不变；
  - 层级 0 的候选只改动影响域内任务（`validate` 的 V11 通过）；
  - 与 `b2_full_replan` 相比，`moved` 不大于 B2（在同等延期代价约束下）。

### 5.4 属性测试（hypothesis）

- 随机生成小实例（≤ 12 任务、≤ 4 设备）：`solve_initial` 的输出必过 `validate`。
- 随机事件：`replan` 的候选必过 `validate`；影响域之外任务不变。
- 同种子同输入 → 输出完全一致（确定性）。
- 对**人为篡改**的计划（制造重叠/违反先后），`validate` 必须检出对应的违反码。

---

## 6. 分阶段任务（每阶段给 Codex 的指令模板）

> 每段指令末尾都加上：`先阅读 AGENTS.md、docs/design_v2.md 的 X 章与 docs/codex_spec.md 第 3、4、5 节，先给出计划与文件清单，等我确认再动手。`

| 阶段 | 目标 | 要创建 | 验收 |
|---|---|---|---|
| **P1 契约、校验器与产出物基础设施** | 实现 `models.py`、`axis.py`、`validate.py`、`generate.py`，以及 `src/scheduler_core/io/artifacts.py`、`io/manifest.py`、`tools/check_repo_layout.py`、`tools/clean_artifacts.py`、`.gitignore`、`Makefile` | 第 3 节全部模型；V1–V11 检查；实例生成器；`ArtifactStore`；manifest 写入与校验；仓库布局检查 | 篡改计划能检出对应违反码；生成器同种子同结果；`make check` 通过；故意在源码目录放一个 `.csv` 时布局检查报错；`run.finish()` 后目录只读 |
| **P2 初始调度** | `solve_initial.py`，含可选区间、NoOverlap、阻塞区间、先后关系、Cumulative、准备时间、目标函数 | CP-SAT 模型与参数 | 5.1 黄金断言；5.4 前两条属性测试 |
| **P3 仿真器** | 设备/任务状态机、事件队列、扰动模型、适配器接口、回放 | `src/simulator/` | 非法状态迁移抛错；同种子同日志；回放结果一致；可注入事件 |
| **P4 重规划** | `impact.py`、`replan.py`（邻域层级、稳定性目标、warm start）、B2、B3 | 影响域、邻域扩张、基线 | 5.3 全部；层级 3 与 B2 可行性一致 |
| **P5 诊断/松弛/候选** | `diagnose.py`、`relax.py`、`pareto.py` | MUS（假设文字 + deletion filter）、最小松弛、Pareto | 5.2；候选互不支配；标签正确 |
| **P6 Agent** | LangGraph 状态图、IR 抽取流水线、工具、解释与一致性校验 | `src/agent/` | 写操作工具无确认标志即拒绝；抽取评测集脚本可跑；解释断言与证据包比对 |
| **P7 后端 + 前端** | Spring Boot 接口、乐观锁、作业队列；Vue 页面 | `apps/backend/`、`apps/frontend/` | 端到端：注入事件 → 候选 → 选择 → 提交 → 状态更新 |
| **P8 实验框架** | 批量运行、指标、统计检验、绘图 | `experiments/` | 一条命令复现 E1–E5 的表和图 |

**每个阶段的通用补充约束**

- 不得跨阶段实现功能（例如 P2 不要写重规划）。
- 完成后输出：改动文件列表、测试命令与结果、已知局限、需要我决定的问题。
- 所有输出文件通过 `ArtifactStore` 写入 `artifacts/`；不得在仓库中留下未说明的文件；结束前运行 `make check`，并在报告中附"新增/修改/删除文件清单及用途"。
- 每个阶段的运行结果都要有 manifest；阶段性的测试输出摘要放在 `artifacts/` 下，不要写入源码目录或仓库根目录。

---

## 7. 技术决策记录（已决定）

> 这一节记录已定下的选择。Codex 不得更改；如需变更，先在 `docs/decisions/` 新增一条决策记录并经你确认。

| 编号 | 事项 | 决定 | 理由与约束 |
|---|---|---|---|
| D1 | 大模型服务 | **DeepSeek API** | 见 7.1 |
| D2 | 数据库 | **PostgreSQL** | `jsonb`、部分唯一索引（保证同时只有一个 active 计划版本）、事务与乐观锁支持成熟 |
| D3 | 甘特图库 | **vis-timeline** | 设备作为分组（行）、任务作为条目、停用/维护窗口用背景条目，天然匹配"设备×时间"视图；MIT/Apache 许可；比 dhtmlx-gantt 少许可证顾虑；比 ECharts 自绘省工。需在 P7 开始前确认所选版本的 API 与许可 |
| D4 | Python 包管理 | **uv** | 速度快，锁文件清晰，`uv sync` 一条命令复现环境；若个别依赖安装有问题再回退 pip，但仍保留锁文件 |
| D5 | 时间槽 | **5 分钟** | 实验步骤多以十几分钟到数小时计，5 分钟足够细；14 天视野约 4032 槽，CP-SAT 可处理。大规模（L）实例若求解过慢，改用 10 分钟并在 E5 灵敏度实验中报告。短于 5 分钟的任务向上取整 |
| D6 | 后端策略 | **保留 Spring Boot，做成薄层；P7 才启动** | 见 7.2 |
| D7 | 评测集 | **人工把关的半自动构建** | 见 7.3 |

### 7.1 D1：DeepSeek 的使用约定

1. **模型名不得写死在代码里**：放 `src/agent/defaults.yaml`（`llm.model`），并在启动时调用"列出模型"接口校验。原因：我检索到的材料显示 DeepSeek 的 `deepseek-chat` 与 `deepseek-reasoner` 旧别名已安排在 2026-07-24 下线，并出现了新一代模型（如 V4 系列）。这些信息来自第三方页面，**具体可用的模型 id 与参数请以 DeepSeek 官方文档为准**，在 P6 开始时由 Codex 查阅官方文档后写入配置。
2. **接入方式**：接口兼容 OpenAI 风格，可用 `langchain-deepseek`（`ChatDeepSeek`）或 OpenAI 兼容客户端；统一封装在 `src/agent/llm.py` 的适配层，其他代码不得直接调用。
3. **结构化输出**：
   - 抽取优先使用**函数调用**；JSON 模式要求提示词里出现 "json" 字样并给出示例结构，且 `max_tokens` 要足够，否则可能返回空内容。
   - **不要依赖服务端的 strict 校验**：不同来源对 `strict` 是否生效说法不一。所有输出一律经 Pydantic 校验，这与设计里"大模型输出视为不可信输入"一致。
4. **思考模式（reasoner/thinking）**：
   - 约束抽取与解释使用**非思考模式**，温度 0，求稳定、省成本。
   - 基线 B1 增加一个**思考模式变体（B1c）**，用来回应"推理模型是不是能直接排计划"的质疑；B1 各变体使用同一提示模板与同一实例。
5. **成本与缓存**：B1 的提示很长（含完整实例）。把固定的系统提示和规则放在提示最前面，以利用服务端的上下文缓存；实验里记录 token 用量与费用，写入 manifest。
6. **密钥**：`DEEPSEEK_API_KEY` 只从环境变量读取，写入 `.env.example` 占位，不入库；LLM trace 写盘前脱敏。
7. **稳定性**：实验里固定模型版本与温度，仍可能有输出波动，因此 Agent 评测要**重复运行 3 次**并报告均值与方差；加限流重试与超时降级（见设计文档 7.8）。

### 7.2 D6：为什么保留 Spring Boot，以及怎么控制风险

**建议**：保留。理由：审批表上的技术栈包含 Spring Boot，求职时全栈经历也有价值。风险是它会占用算法与实验的时间，所以做成"薄层"并延后：

| 要点 | 做法 |
|---|---|
| 职责 | 只做 CRUD、计划版本与乐观锁、事件记录、审计、作业队列、网关；**不放任何算法** |
| 启动时机 | P1–P6 全部通过验收后才开始（P7） |
| 接口先行 | 由 FastAPI 生成 OpenAPI 文档，Spring Boot 与前端都按它对接，减少来回返工 |
| 保底方案 | Python 服务在 P6 结束时就应能**独立演示**（命令行或简易页面）。若 P7 进度吃紧，先用 FastAPI 承担业务接口完成演示，Spring Boot 作为后续补充 |
| 需要确认 | 若最终不用 Spring Boot，需先与郭老师确认是否影响选题要求 |

### 7.3 D7：评测集的构建办法

**目标**：200 条，其中开发集 50、测试集 150；类别配比见设计文档 11.4。

1. **模板生成骨架**：按类别用模板批量生成"标准 IR + 基础说法"，保证标注准确。
2. **多样化改写**：用与被测模型**不同的**模型或人工改写成口语化说法，**避免用同一个模型既出题又被测**，否则成绩虚高。至少 30% 由你手写（相对时间、软硬不明这两类建议全手写）。
3. **人工复核 100%**：你逐条核对标准 IR；再让一位同学独立标注测试集的 30%，计算一致性（如 Cohen's κ），写进论文。
4. **对抗样本**：加入 20 条刻意设计的困难样本，如"别用 3 号机，除非实在没办法""把 A 和 B 换一下""下周三的实验提前一天"。
5. **防泄漏**：提示词的 few-shot 样例只能来自开发集；测试集在最终评测前不看错误细节，避免调提示词时过拟合。
6. **版本化**：存为 `data/eval_sets/extraction/v001.jsonl`，附 `CHANGELOG.md`；修改产生新版本。

---

## 8. 仍需补充的内容（本文件未覆盖）

| 内容 | 建议时机 |
|---|---|
| Agent 提示词全文与 few-shot 样例 | P6 开始前，我可以先写初稿，你再用评测集调 |
| 前端页面线框与交互细节 | P7 开始前 |
| REST 接口的完整请求/响应 Schema 与错误码 | P7 开始前（可由 P1 的模型自动生成 OpenAPI） |
| 配置文件（YAML）完整字段 | 各阶段随实现补 |
| 评测集样例与标注规范 | P6 |
| Docker Compose、部署脚本 | P7 末期 |

---

## 9. 与 Codex 协作的注意事项

1. **查 API 再写**：OR-Tools 的方法名在不同版本有驼峰与下划线两套，Codex 容易写错；AGENTS.md 已要求先确认已安装版本的签名。
2. **算法类任务容易"看起来对"**：重规划和冲突诊断一定要你自己读代码并用 5.3、5.4 的测试验证，不要只看测试是否绿。
3. **接口变动要集中处理**：契约（第 3 节）改了，所有依赖模块都要同步，建议让 Codex 一次性完成并跑全量测试。
4. **保持小步提交**：每个阶段一个分支，通过验收再合并。
5. **留证据**：每个阶段的测试输出和你的审查记录，写论文时可以作为实现与验证的材料。
6. **文件整洁要靠机制，不靠自觉**：Codex 容易随手留下临时脚本、日志和截图。已用 `ArtifactStore` 统一出口、`.gitignore` 和 `check_repo_layout` 三道机制约束；你每次审查时再看一眼 `git status`，有不认识的文件就让它说明用途或删除。
7. **提交前检查**：`git status` 应只显示 `src/`、`apps/`、`experiments/`、`data/`、`docs/`、`tests/`、`tools/` 的改动，不应出现 `artifacts/` 下的内容。
