# 模型策略

2026-11-11最新续作：用户明确“继续执行，claude额度恢复了”。后续规划交回Claude，temp暂停新规划；P1-C3在途方案保持已通过G1的temp v001及已记录工程细化，不重写来源或中途换提示词。当前先完成ZIP返工的独立G3、G5同步，再向Claude交接temp决定和实际验收。若Claude再次额度不可用，按已授权temp例外处理，不绕过门禁。

2026-11-11最新用户指令：“继续，claude额度用完了就换temp智能体”。恢复按需临时替代授权：Claude额度不可用时由temp代行planner/prompt-engineer，仍用gpt-6.1-terra/high/fork_turns=none；仅替换计划来源，Claude历史文本不改写或追认。当前P1-C3先由temp补齐G1返工，root通过G1后派专项实施及独立G3，G4/G5与账号/作者策略不变。Claude实际恢复后交回后续规划；已通过G1的在途包固定版本，范围实质变化仍回到规划。本条覆盖下文“temp不再接新规划”的历史状态。

2026-11-11已按用户要求交回Claude规划/提示词，temp退出新规划。Codex实施和独立审查仍统一gpt-6.1-terra/high/fork_turns=none，不受计划角色切换影响；下方临时策略保留历史来源。

2026-11-10用户临时授权：Claude额度不可用期间由temp代行计划与提示词，配置仍为gpt-6.1-terra/high/fork_turns=none。不是自动降级，不改变实施及独立审查模型。恢复Claude的边界见[temp角色](temp-planner.md)与根AGENTS；历史Claude文本仍按原来源保留。

用户指定所有未来 Codex 专项子智能体使用 GPT-6.1 Terra，推理 high。派发时设置 `model="gpt-6.1-terra"`、`reasoning_effort="high"`、`fork_turns="none"`，并提供自包含上下文与绝对工作目录；提示词头部写明配置。交接记录实际模型与推理档，不能确认则标未能确认。本次 agent-resume 按上述配置成功启动；这不证明未来可用性。不可用时停止并报告，不自动降级。例外与策略变更须用户裁决并记录。外部 Claude 的 planner 和 prompt-engineer 不适用此策略。历史会话模型未记录，不推定为 Terra。
