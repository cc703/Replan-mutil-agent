# 动态调度与重规划 Agent

本科毕业设计项目：把自然语言需求解析、约束求解、独立校验和用户确认连接起来，以仿真验证动态调度与重规划。

当前阶段是 **P0 治理与协作基础**。本仓库尚未实现业务模型、求解器、仿真器或应用，不以治理检查通过代替业务验收。

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

完整设计框架 v2 与开发规格原文由总设计师导入 `docs/design_v2.md`、`docs/codex_spec.md`；是否已导入以文件和进度记录为准，不用摘要冒充原文。

## 执行检查

在仓库根目录运行 `python tools/check.py`。它是 P0 的跨平台入口；有 make 时可用 `make check`。
目标环境建立后使用 `uv run --python 3.11 --group dev python tools/check.py`。无需在 P0 安装业务依赖。
检查项的存在与执行结果以工具实际输出为准，不把未来命令列为已经运行的验证。

## 目录职责

| 目录 | 职责 |
|---|---|
| docs/ | 设计、规格、规范、专项智能体、工作包、进度、决策与审核结果 |
| tools/ | 可复用治理检查与维护工具 |
| tests/ | 治理与未来业务测试 |
| artifacts/ | 本地生成物；仅 README.md 入库 |
| src/ | 后续阶段的 Python 核心、仿真器与应用 Agent |
| apps/ | 后续阶段的 Spring Boot 与 Vue 应用 |
| experiments/ | 后续实验代码、配置与实验性基线 |
| data/ | 允许入库且来源明确的输入数据 |

后四个目录在对应阶段按需创建，不为展示骨架而创建占位业务代码。

## 协作

用户裁决重大设计问题；Claude 在每个实施工作包前出计划和提示词；Codex 总设计师审查、派发、集成、验收并同步 GitHub。专项智能体仅在各自文件范围内实施。角色定义保存在仓库，运行实例随任务创建，不意味着后台永久运行。
