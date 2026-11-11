# 动态调度与重规划 Agent

本科毕业设计项目：把自然语言需求解析、约束求解、独立校验和用户确认连接起来，以仿真验证动态调度与重规划。

当前为 **P1 基础源码阶段**：数据模型、时间轴、独立业务校验器、实例生成器、ArtifactStore、清理与归档工具已实现。求解器、仿真器和应用尚未实现；工程验收及远端同步状态以项目进度为准。

## 开始阅读

- [AGENTS.md](AGENTS.md)：所有智能体的唯一约束入口；口头称 AGENT.md 即本文件。
- [项目进度](docs/progress/PROGRESS.md)：阶段、工作包、验收与 GitHub 同步状态。
- [专项智能体](docs/agents/README.md)：职责、复用和派发方法。
- [代码规范](docs/engineering/coding-standards.md)。
- [文件存储规范](docs/engineering/file-storage-standard.md)：最优先检查的工程约束。
- [开源工具规范](docs/engineering/open-source-policy.md)及[依赖登记](docs/engineering/dependency-register.md)。
- [审查门禁](docs/engineering/review-gates.md)及[Git 工作流](docs/engineering/git-workflow.md)。
- [变更记录](CHANGELOG.md)。
- [本轮 Claude 计划审查与派发提示词](docs/work-packages/p0-claude-review.md)。

完整设计框架 v2、开发规格 v1.1 与历史完整计划已逐字导入 [来源目录](docs/source/README.md)，全文及分块哈希通过核验；旧路径引用统一映射到 `docs/source/*.original.md`，不建立易漂移副本。勘误独立保存，不静默升级原文。

[智能体恢复入口](docs/agents/RESUME.md) · [模型策略](docs/agents/model-policy.md) · [P1 开工准备](docs/planning/p1-readiness.md) · [P1-A 工作包](docs/work-packages/p1-a.md)。

## 执行检查

在仓库根目录先运行 `uv sync` 安装锁定依赖，再运行 `uv run --python 3.11 --group dev python tools/check.py`。也可在已安装依赖的 Python 3.11 环境中运行 `python tools/check.py`；有 make 时可用 `make check`。检查项和执行结果以工具实际输出为准。

## 目录职责

| 目录 | 职责 |
|---|---|
| docs/ | 设计、规格、规范、专项智能体、工作包、进度、决策与审核结果 |
| tools/ | 可复用治理检查与维护工具 |
| tests/ | 治理测试与业务单元测试 |
| artifacts/ | 本地生成物；仅 README.md 入库 |
| src/scheduler_core/ | 数据模型、精确 UTC 时间轴、独立 V1–V11 校验器与验证上下文 |
| apps/ | 后续阶段的 Spring Boot 与 Vue 应用 |
| experiments/ | 后续实验代码、配置与实验性基线 |
| data/ | 允许入库且来源明确的输入数据 |

尚不存在的目录在对应阶段按需创建，不为展示骨架而创建占位业务代码。

## 协作

用户裁决重大设计问题；Claude 在每个实施工作包前出计划和提示词；Codex 总设计师审查、派发、集成、验收并同步 GitHub。专项智能体仅在各自文件范围内实施。角色定义保存在仓库，运行实例随任务创建，不意味着后台永久运行。


## 独立计划校验

```python
from scheduler_core.models import Instance, Plan
from scheduler_core.validate import validate

# inst 和 plan 分别为已解析的 Instance 与 Plan
report = validate(inst, plan)
if not report.passed:
    for violation in report.violations:
        print(violation.code, violation.task_ids, violation.detail)
```

`validate(inst, plan, base=base, free=free, context=context)` 接受可选的基准计划、邻域和验证上下文。`free=None` 不检查邻域，空集合则不允许非冻结任务改变；有基准时计划须绑定其父版本。输入不被修改，违规按代码、任务、设备和详情稳定排序。`detail` 以 `reason=令牌;` 开头。区间为半开区间，设备占用包括准备时间（RUNNING/DONE 除外），人员占用不含准备时间。窗口合并、排序扫描和事件扫描按 `O(n log n + 输出规模)` 处理，不按视野逐槽扫描。

`ValidationContext` 保存执行快照、RUNNING 延长证据、截止期授权和运行窗口绑定；事件 ID 是执行证据，授权确认 ID 由上层 L1/L2 负责真实性，校验器只检查结构及绑定，不以布尔值豁免约束。RUNNING 窗口有效绑定时只按任务自身需求计数；无绑定窗口只有发生占用时才报告。DONE 的新完成时间可早于或晚于基准计划，但不能改写基准生成时已完成的历史。独立校验不能由 OR-Tools 或 PyJobShop 示例替代，也不证明计划最优。

| 代码 | reason 令牌 |
| --- | --- |
| V1 | MISSING_ASSIGNMENT, UNKNOWN_TASK, UNKNOWN_DEVICE, DEVICE_NOT_COMPATIBLE, EMPTY_COMPATIBLE_LIST, UNKNOWN_DEVICE_REF, TASK_NOT_SCHEDULABLE, ASSIGNMENT_KEY_MISMATCH, DUPLICATE_TASK_ID, DUPLICATE_DEVICE_ID |
| V2 | DEVICE_OVERLAP, RUNNING_BLOCK_UNBOUND, RUNNING_BLOCK_BINDING_INVALID, SETUP_RULE_CONFLICT |
| V3 | PRECEDENCE_MIN_LAG, PRECEDENCE_MAX_LAG, PRECEDENCE_UNKNOWN_TASK, PRECEDENCE_CYCLE |
| V4 | RELEASE_VIOLATED, START_BEFORE_NOW |
| V5 | DEADLINE_EXCEEDED, AUTH_NOT_APPLICABLE, AUTH_EXPIRED, AUTH_FUTURE, AUTH_OUT_OF_SCOPE, AUTH_DUPLICATE |
| V6 | CALENDAR_BLOCKED, HORIZON_EXCEEDED, SETUP_BEFORE_ORIGIN |
| V7 | MISSING_PERSON, UNKNOWN_PERSON, SKILL_MISSING, PERSON_OVERLAP, PERSON_UNAVAILABLE, DUPLICATE_PERSON_ID |
| V8 | FROZEN_DEVICE_CHANGED, FROZEN_START_CHANGED, NO_FROZEN_REFERENCE, FROZEN_MISSING |
| V9 | CAPACITY_EXCEEDED, DEMAND_EXCEEDS_CAPACITY |
| V10 | DURATION_MISMATCH, RUNNING_NO_SNAPSHOT, SNAPSHOT_STALE, SNAPSHOT_PLAN_MISMATCH, SNAPSHOT_RECORD_INVALID, END_MISMATCH, DONE_NO_EVIDENCE, DONE_END_AFTER_NOW, DONE_HISTORY_REWRITTEN |
| V11 | PARENT_MISMATCH, BASE_REQUIRED, FREE_UNKNOWN_TASK, FREE_CONTAINS_FROZEN, ADDED_NOT_FREE, REMOVED_NOT_FREE, BASE_TASK_UNKNOWN, NONFREE_CHANGED, FROZEN_PERSON_CHANGED, FROZEN_END_NO_EVIDENCE, FROZEN_END_EVIDENCE_INVALID |

### ArtifactStore 用法

在仓库根目录的 PowerShell 中先执行 `$env:PYTHONPATH="src"`，然后运行以下 Python 代码（项目 `package=false`）：

```python
from scheduler_core.io import ArtifactStore

store = ArtifactStore(root="artifacts")
run = store.new_run(kind="experiment", name="e2_replan_micro", tag="small-light")
raw_path = run.path("raw.csv")
raw_path.write_text("a,b\n1,2\n", encoding="utf-8")
run.write_json("plans/inst1_m.json", {"k": 1})
run.finish(status="completed", outputs=["raw.csv", "plans/inst1_m.json"])
```

`config=None` 保存空配置及其真实哈希；`clock`、`metadata`、`inputs` 和显式 `git` 为调用方提供的工程扩展。调用方负责命令、配置与元数据脱敏以及显式 git 证据真实性。终态文件设置只读；Windows 只读属性不是目录 ACL，不防并发替换或手工改权限。失败的 finish 可能已将部分文件设为只读，需要修改时应新建运行。

### 实例生成与缓存

在仓库根目录设置上文的 `$env:PYTHONPATH="src"` 后，以下 Python 代码加载 YAML 并创建或复用缓存：

```python
from pathlib import Path
from scheduler_core.io import ArtifactStore
from scheduler_core.io.generator_config import load_generator_config
from scheduler_core.instance_cache import InstanceCache

config = load_generator_config(Path("experiments/configs/generator/default.yaml"))
result = InstanceCache(ArtifactStore("artifacts")).get_or_generate(
    "S", 0.8, 0.5, 0, params=config.params, verify_regeneration=True
)
print(result.key, result.directory, result.reused, result.regeneration_verified)
instance = result.instance
```

纯函数 `generate_instance("S", 0.8, 0.5, 0, params=config.params)` 直接返回内存中的实例，不读写文件；缓存接口返回含实例、路径和复用状态的 `CacheResult`，并可能写入缓存。实例时间采用整数槽，默认每槽 5 分钟；两者均不生成正式计划。`verify_regeneration=True` 会重新生成并比较规范字节。

缓存 SHA-256 用于发现意外损坏，不能证明数据未遭篡改；若数据和元数据的哈希被一起修改，普通复用不会证明其来源。重新生成比较依赖相同生成器版本与 NumPy 版本。缓存发布采用平台 no-replace 原语并拒绝已知链接；不声称能防止恶意并发替换路径。

### 产物清理

`uv run --python 3.11 --group dev python tools/clean_artifacts.py --kind tmp` 默认只检查，显式添加 `--apply` 才删除；`--kind failed-runs` 检查失败和中断运行，默认保留 14 天。可使用 `--root`、`--index`、`--older-than 7d` 和 `--format json`；运行中的运行和完成的运行不会自动清理。结果索引必须包含完整运行 ID 或完整的 `artifacts/runs/<kind>/<name>` 路径才能保护引用；不识别缩写或口头描述。索引歧义或无法读取时拒绝删除。执行前确认输出，文件系统并发变化不能完全防护。


### 运行归档与核验

`uv run --python 3.11 --group dev python tools/archive_run.py --run RUN_ID` 默认只列计划，可用 `--kind KIND --name NAME` 消除重名、`--root artifacts` 指定根目录、`--format json` 输出结构化结果。显式 `--apply` 将 completed 运行归档为 ZIP 和 sidecar，源运行保留；论文定稿前不对真实运行执行归档。任一目标已存在均拒绝覆盖。

`--verify` 只读核对归档内容、内嵌 manifest 与 sidecar，不依赖源运行仍存在，不解压。它只证明内部一致，合法归档时间、空目录记录或整套自洽重写可能通过，不能证明原始来源未变。发布目前验证并支持 Windows，其他平台明确拒绝。ZIP 与 sidecar 分两次发布；失败或崩溃可能留下不完整归档，复跑不会覆盖，需人工检查。路径检查不抵抗恶意并发替换，Windows 只读属性也不是防篡改保证。
