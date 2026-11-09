# 专项智能体目录

版本：v001。当前阶段：P0。角色定义可复用，运行时会话会结束；本目录不代表所有智能体已经常驻启动。

## 分工

| 角色 | 执行主体 | 用途 | 启动门槛 |
| --- | --- | --- | --- |
| [planner](planner.md) | 侧边栏 Claude | 工作包计划、风险、依赖、验收 | 每个新实施工作包 |
| [prompt-engineer](prompt-engineer.md) | 侧边栏 Claude | 生成可派发的完整提示词 | 计划完成后 |
| [storage-steward](storage-steward.md) | Codex 专项会话 | 文件存储、例外与可追溯性 | 总设计师派发 |
| [oss-scout](oss-scout.md) | Codex 专项会话 | 官方资料、工具和许可证核实 | 新依赖或 API 调研 |
| [reviewer](reviewer.md) | 未参与对应实现的专项会话 | 独立审查与验收建议 | G2 完成 |
| [contract-engineer](contract-engineer.md) | Codex 专项会话 | 数据契约与独立校验 | P1 工作包获准 |
| [solver-engineer](solver-engineer.md) | Codex 专项会话 | 建模、求解、重规划和诊断 | P2/P4/P5 工作包获准 |
| [simulation-engineer](simulation-engineer.md) | Codex 专项会话 | 状态机、仿真和回放 | P3 工作包获准 |
| [agent-engineer](agent-engineer.md) | Codex 专项会话 | 业务 Agent、抽取、解释 | P6 工作包获准 |
| [app-engineer](app-engineer.md) | Codex 专项会话 | 前后端与部署接口 | P7 工作包获准 |
| [experiment-engineer](experiment-engineer.md) | Codex 专项会话 | 实验协议实现、统计和复现 | P8 工作包获准 |

领域角色目前仅定义，不代表 P1–P8 已经启动。planner 和 prompt-engineer 是同一侧边栏 Claude 的两种职责；不得用本地同名代理冒充 Claude 回复。总设计师 Codex 负责架构审查、派发、集成、进度和 Git 同步。

## 派发与重用

1. 总设计师读取 [进度](../progress/PROGRESS.md)、[门禁](../engineering/review-gates.md) 和当前源文档；准备工作包上下文。
2. 先向侧边栏 Claude 请求本工作包的计划与提示词。将原文、会话链接、版本及时间保存到工作包记录；已有模板不能代替本次 Claude 输出。
3. 总设计师审查范围、输入、允许写入路径、验收与并行风险，通过 G1 后派发。明确的用户授权覆盖常规工程选择；重大未决设计按 G4 询问用户。
4. 同时最多三个实施会话，每个工作包的实际写入集合互斥。可多个角色顺序参与同一工作包；独立审查者只读，不与实施者同时改同一文件。
5. 同一共享工作树内，专项会话不得切换分支、提交、推送或修改 Git 配置。需要隔离时由总设计师创建和登记工作树，不得假称已有隔离。
6. 角色升级新版本时记录版本、原因及影响；正在实施的工作包固定已审查提示词版本，范围变化先重规划。

## 通用交接合同 H

每个角色输出：状态（DONE / BLOCKED / NEEDS-DECISION）、新增/修改文件及用途、真实执行命令与结果、来源与未核实项、偏离提示词之处、未决问题、需要裁决的问题、下一步建议。DONE 只表示专项交付，不表示 G3/G5 已通过。发现阻塞及时向总设计师报告，仅暂停受影响部分。

## 跨会话恢复

读取根 AGENTS.md、本角色定义、当前工作包、PROGRESS.md、已审查的 Claude 提示词、最近交接和真实 git status/log。核对尚未提交的他人改动，不覆盖、不重新执行未核实的动作。确认 G1 记录存在才恢复实施；缺失则回到 Claude 规划。不要依赖旧会话内存、进程句柄或自动持续运行的假设。

## 恢复资料

[角色索引](registry.md) · [模型策略](model-policy.md) · [恢复清单](RESUME.md) · 提示词库 `prompts/`（R2 待建立） · [交接](handoffs/agent-resume-r1.md)
