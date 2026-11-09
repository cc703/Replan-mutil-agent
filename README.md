# 动态调度与重规划 Agent

本科毕业设计项目：把自然语言需求解析、约束求解、独立校验和用户确认连接起来，以仿真验证动态调度与重规划。

当前进入 **P1 业务源码开发**。P1-A 已实现数据模型与时间轴，正在按工作包审查；独立业务校验器、求解器、仿真器和应用尚未实现。阶段验收状态以项目进度为准。

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
| src/scheduler_core/ | 数据模型与精确 UTC 整数槽时间轴；后续扩展调度核心 |
| apps/ | 后续阶段的 Spring Boot 与 Vue 应用 |
| experiments/ | 后续实验代码、配置与实验性基线 |
| data/ | 允许入库且来源明确的输入数据 |

尚不存在的目录在对应阶段按需创建，不为展示骨架而创建占位业务代码。

## 协作

用户裁决重大设计问题；Claude 在每个实施工作包前出计划和提示词；Codex 总设计师审查、派发、集成、验收并同步 GitHub。专项智能体仅在各自文件范围内实施。角色定义保存在仓库，运行实例随任务创建，不意味着后台永久运行。
