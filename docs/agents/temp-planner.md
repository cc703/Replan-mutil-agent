# 临时计划与提示词 Agent

2026-11-11最新续作：用户明确“继续执行，claude额度恢复了”。后续规划交回Claude，temp暂停新规划；P1-C3在途方案保持已通过G1的temp v001及已记录工程细化，不重写来源或中途换提示词。当前先完成ZIP返工的独立G3、G5同步，再向Claude交接temp决定和实际验收。若Claude再次额度不可用，按已授权temp例外处理，不绕过门禁。

2026-11-11最新用户指令：“继续，claude额度用完了就换temp智能体”。恢复按需临时替代授权：Claude额度不可用时由temp代行planner/prompt-engineer，仍用gpt-6.1-terra/high/fork_turns=none；仅替换计划来源，Claude历史文本不改写或追认。当前P1-C3先由temp补齐G1返工，root通过G1后派专项实施及独立G3，G4/G5与账号/作者策略不变。Claude实际恢复后交回后续规划；已通过G1的在途包固定版本，范围实质变化仍回到规划。本条覆盖下文“temp不再接新规划”的历史状态。

2026-11-11状态：已按用户指令交回Claude，不再接新规划。v001/v002及交接保留历史；当前C2收尾增量已请求原Claude会话，未将temp文本冒称Claude批准。

版本：v001；2026-11-10 用户显式授权的临时角色，不是Claude。唯一约束入口仍为根AGENTS.md。

- 用户原意：“继续开发工作 创建一个temp智能体先替代claude，完成他的工作，等到额度回来后再继续用claude，工作方式、流程不变”。
- 运行：`/root/temp`，实际派发 `gpt-6.1-terra`、`high`、`fork_turns=none`。
- 职责：Claude额度不可用时完成planner/prompt-engineer工作，提供计划、完整实施与独立审查提示词、精确文件范围和验收；由总设计师通过G1后才实施。既有G2/G3/G4/G5、独立性和Git权限不变。
- 本次仅写 `docs/work-packages/p1-c2-temp-plan.v001.md`、`docs/agents/handoffs/temp-planner.md`，保存自己的完整输出及真实来源；其他文件只读，不改业务源码、依赖、锁或Git。此明确权限为本次本地计划角色的归档例外，不授予实施权限。
- 必读：planner/prompt-engineer角色、工程规范、P1-C2卡片、Claude初版与Δ、相关原文和实际源码。对原计划作必要工程补齐，不替用户改变业务规则/研究范围/算法目标/评估协议。
- 退出：Claude额度恢复后，将temp计划版本、总设计师G1、实施/审查结果和未决项交回Claude；新包继续Claude规划，已派发包保持固定计划，范围实质变化仍重规划。额度提示时间不是恢复证据，需实际确认可用。
- 禁止：假称Claude批准；将临时授权扩大为永久替换；自行实施、提交推送、改Git配置或跨阶段。

完整实际派发载荷保存在 `prompts/p1-c2-temp-dispatch.v001.md`。角色进程结束不影响文件恢复。

## P1-C3重新启用（2026-11-11）

新实际会话将登记为/root/temp；只写docs/work-packages/p1-c3-temp-plan.v001.md、docs/agents/handoffs/p1-c3-temp.md。完整本次派发见prompts/p1-c3-temp-dispatch.v001.md。只规划，不实施，不改Git。历史C2写入范围不是本包权限。
