# 模型策略

用户指定所有未来 Codex 专项子智能体使用 GPT-6.1 Terra，推理 high。派发时设置 `model="gpt-6.1-terra"`、`reasoning_effort="high"`、`fork_turns="none"`，并提供自包含上下文与绝对工作目录；提示词头部写明配置。交接记录实际模型与推理档，不能确认则标未能确认。本次 agent-resume 按上述配置成功启动；这不证明未来可用性。不可用时停止并报告，不自动降级。例外与策略变更须用户裁决并记录。外部 Claude 的 planner 和 prompt-engineer 不适用此策略。历史会话模型未记录，不推定为 Terra。
