# 模型策略

2026-11-11已按用户要求交回Claude规划/提示词，temp退出新规划。Codex实施和独立审查仍统一gpt-6.1-terra/high/fork_turns=none，不受计划角色切换影响；下方临时策略保留历史来源。

2026-11-10用户临时授权：Claude额度不可用期间由temp代行计划与提示词，配置仍为gpt-6.1-terra/high/fork_turns=none。不是自动降级，不改变实施及独立审查模型。恢复Claude的边界见[temp角色](temp-planner.md)与根AGENTS；历史Claude文本仍按原来源保留。

用户指定所有未来 Codex 专项子智能体使用 GPT-6.1 Terra，推理 high。派发时设置 `model="gpt-6.1-terra"`、`reasoning_effort="high"`、`fork_turns="none"`，并提供自包含上下文与绝对工作目录；提示词头部写明配置。交接记录实际模型与推理档，不能确认则标未能确认。本次 agent-resume 按上述配置成功启动；这不证明未来可用性。不可用时停止并报告，不自动降级。例外与策略变更须用户裁决并记录。外部 Claude 的 planner 和 prompt-engineer 不适用此策略。历史会话模型未记录，不推定为 Terra。
