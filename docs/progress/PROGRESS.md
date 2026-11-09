# 项目进度

更新日期：2026-11-09（Asia/Shanghai）。当前推进原设计核验、专项智能体持久恢复与 P1 开工设计准备；P1–P8 业务实现尚未开始。

## 当前工作包

| ID | 名称 | 负责专项 | 分支 | 状态 | 门禁 | 工程验收 | 远端同步 | 验收日期 | 提交证据 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P0-A | 治理与规范 | governance | codex/p0-governance | IN-REVIEW | G1/G2/G3 通过；G5 用户暂缓 | 总设计师与独立审查通过 | 用户选择稍后登录，仅保留本地 | 2026-11-09 | 610ab30（本地已提交） |
| P0-B | 协作机制 | collaboration_docs | codex/p0-governance | IN-REVIEW | G1/G2/G3 通过；G5 用户暂缓 | 独立审查发现循环门槛，修复后 ACCEPT | 用户选择稍后登录，仅保留本地 | 2026-11-09 | b9d94cff318ad1ef89394214eb2d9f132d12e7bd |
| P0-C | 机器门禁 | machine_gates | codex/p0-governance | IN-REVIEW | G1/G2/G3 通过；G5 用户暂缓 | 配置驱动缺口修复后独立复审 ACCEPT | 用户选择稍后登录，仅保留本地 | 2026-11-09 | 4024077b3f9b4659ba82d5cd55c08bbe25059377 |
| SOURCE | 原始设计与 Claude 原文导入 | source_terra | codex/p0-governance | IN-REVIEW | G1/G2/G3 通过；G5 仅本地 | review_terra 修复后复审 ACCEPT | 用户暂缓，仅本地 | 2026-11-09 | checkpoint 提交主题见下 |
| AGENT-RESUME-R1 | 模型策略、角色索引及恢复 | resume_terra | codex/p0-governance | IN-REVIEW | G1/G2/G3 通过 | 独立 review_terra ACCEPT | 用户暂缓，仅本地 | 2026-11-09 | 本次待提交 |
| AGENT-RESUME-R2 | 提示词库及 P1 开工设计 | resume_terra | codex/p0-governance | TODO | 等待 SOURCE G3 | 尚未启动 | 用户暂缓，仅本地 | — | 无 |

分支为共享集成分支，不表示每个专项都有独立工作树。验收、检查、提交及远端 SHA 必须由总设计师按实际执行结果补记。

## 后续阶段

| 阶段 | 目标 | 状态 |
| --- | --- | --- |
| P1 | 数据契约、校验与产出物基础设施 | TODO |
| P2 | 初始调度 | TODO |
| P3 | 仿真器 | TODO |
| P4 | 重规划 | TODO |
| P5 | 诊断、松弛和候选 | TODO |
| P6 | 业务 Agent | TODO |
| P7 | 后端和前端 | TODO |
| P8 | 实验框架 | TODO |

## 决策与来源

决策索引见 [docs/decisions/](../decisions/)。已取回的完整设计 v2、开发规格 v1.1 和历史 P0 原计划分别保存在 docs/source/*.original.md；全文与14个分块均已对照外部预期值验证。原文不静默升级或改写，勘误见 docs/source/ERRATA.md。

计划/提示词来源：[Claude 原会话](https://claude.ai/chat/54ab7bfe-2bca-4714-9759-e3ae3e5474e7)，2026-11-09 P0 计划。具体版本、原文和审查证据见 [P0 工作包](../work-packages/P0.md)。

## 风险与阻塞

- 原设计缺失阻塞及核验器返工均已解除：三份全文与14分块哈希匹配，清单完整性、重复条目、分块覆盖和路径边界修复后独立复审 ACCEPT。R2 可按已审查的 Claude 计划启动。
- 原规格命名与缓存约束需要治理修复。用户已裁决 B1 外移和 solver 双 profile 两项建议暂不修改（DEFERRED，见 ADR 0002/0003），按原规格推进并保留批注；对应模块实施前再讨论，P0 不因此阻塞。
- 文件检查提前至 P0，只完成治理机制不等于 P1 的 ArtifactStore 已实现。
- 用户决定本项目统一使用 cc703。仓库局部 Git credential username 已设 cc703，已连接 GitHub 插件也是 cc703 且有 push 权限。用户随后选择先保留本地提交、稍后登录，设备登录等待已结束；不继续推送或改用插件上传。此前推送403，不能计为已同步。提交作者仍为 chm。
- 2026-11-09 隐私核对：项目根目录与 Git common-dir 均指向 D:/Default/Replan-mutil agent 内，只有一个工作树，未共享其他仓库的 .git。远端 ls-remote 无分支引用，GitHub 仓库 size=0，未发现本轮提交已上传；仓库当前为 public。未来上传到公开仓库的文件和提交作者邮箱可被公众读取，本次未修改可见性或作者邮箱。
- 浏览器读取可能超时；无本工作包 Claude 完整提示词时不能绕过 G1。
- 用户指定后续所有 Codex 专项均为 GPT-6.1 Terra/high；本次 source_terra、resume_terra、review_terra 已以 model=gpt-6.1-terra、reasoning_effort=high、fork_turns=none 实际派发。旧 P0 会话不追溯冒称同模型。角色索引/模型策略/交接/恢复清单见 docs/agents/。

## 本轮验证与审查证据

- 续作前由总设计师执行 `uv run --python 3.11 --group dev python tools/check.py`：来源全文及14批 PASS；33 passed、1 skipped in 7.68s；ruff check/format PASS；mypy 4 source files PASS。唯一跳过为本机不能创建符号链接，代码边界已审查，未宣称动态验证该项。
- SOURCE G3：review_terra 定向复核 ACCEPT；其单独来源测试10 passed、1 skipped，全文及14批校验退出0。索引的三份原文均为 `i/lf w/lf attr/-text`。
- 本地 checkpoint 主题：`chore(checkpoint): preserve verified sources and agent resume state`。保存 SOURCE、R1、完整 Claude 续作计划和交接，R2 尚未完成；这不是全部业务阶段完成或远端同步声明。

- Claude 实际计划、审查调整、派发提示词 v001 及原文预期哈希见 [审查记录](../work-packages/p0-claude-review.md)。其与逐字原文的区别已明确，不伪造缺失原文。
- 总设计师执行 `uv run --python 3.11 --group dev python tools/check.py`：Layout PASS、Imports PASS、23 passed in 7.50s、ruff check/format PASS、mypy 3 source files PASS。
- 文档内部链接核对：50 条通过；AGENTS.md 73 行。未实现或测试 P1–P8 业务。
- P0-C 独立审查发现 TOML 例外未生效，专项返工为配置驱动，添加有效负例后复审 ACCEPT。
- P0-B 独立审查发现计划/提示词 G1 前置循环，总设计师修复为先读 G0、输出后 G1，复审 ACCEPT。
- 已检查待入库清单：仅治理源码、配置、锁文件、规范与角色文档；不包含 .venv、运行缓存、密钥或原始私人数据。

## 更新责任

单一写入者为 Codex 总设计师。专项本次创建初稿后交总设计师接管，后续专项不直接修改本文件。工作包验收的同次提交更新进度，Git 回执可在下一次更新记入；范围/阻塞变化也应及时记录，不能隐瞒到验收后。状态仅使用 TODO / IN-PROGRESS / IN-REVIEW / ACCEPTED / BLOCKED。

工程验收通过、同步待执行时保持 IN-REVIEW；远端同步成功且 SHA 一致后才能 ACCEPTED。哈希不自引用，当前交付以提交主题/工作包 ID 查询，下一次进度更新记录上一交付真实 SHA。变更清单见根 CHANGELOG.md，证据输出与临时产物按文件存储规范处理。
