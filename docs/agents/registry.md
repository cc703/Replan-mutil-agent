# 角色索引

当前P1-B-R1：/root/p1br1_code_terra已实际spawn，gpt-6.1-terra/high/fork_turns=none，G1/G2/G3最终PASS。完整Claude消息76/计划/提示词在工作包p1-b-r1.md，root实际载荷在prompts/p1-dispatch-log.v001.md最前；读该清单恢复。独立/root/p1br1_review_terra已按同模型策略G3预审及正式审查，首轮结构REWORK已关闭，最终ACCEPT；同一实现/审查会话均已交付。所有Git/进度仍总设计师单写。

2026-11-10本轮P1-B G2/G3已完成，独立ACCEPT。实际会话/root/p1b_code_terra、/root/p1b_tests_terra、/root/p1b_review_terra均gpt-6.1-terra/high/fork_turns=none。作者写两个源码/mini/README/卡片/交接，测试独占两个测试文件，reviewer仅写handoffs/p1-b-review.md；完整提示词与实际派发在[p1-b工作包](../work-packages/p1-b.md)及[日志](prompts/p1-dispatch-log.v001.md)。[实施交接](handoffs/p1-b.md)/[独立审查](handoffs/p1-b-review.md)为恢复依据，不依赖会话常驻。G5已由总设计师完成，1255113推送核验一致；本轮结束按用户要求暂停，三个专项均已交付，未启动新包。实际回执见PROGRESS。

当前源码交付：`/root/p1a_code_terra` 已完成P1-A；实际派发 gpt-6.1-terra/high/fork_turns=none，独立 reviewer `/root/p1_review_terra` 同策略复用会话，工程G3 ACCEPT。完整Claude计划、实施及审查提示词与限定类型增补合并在 [P1-A工作包](../work-packages/p1-a.md)，[实施交接](handoffs/p1-a.md)、[独立审查](handoffs/p1-a-review.md)可恢复。进度和Git仍由总设计师单写。用户工程委托已取代历史逐字段G4阻塞。

持久化定义、派发全文和交接用于恢复，不意味着进程常驻。未来 Codex 专项模型策略见 [model-policy](model-policy.md)。实际历史模型未记录。账号 cc703，作者 chm。

| id | 角色 / 类型 | 定义 | 提示词 / 版本 | 模型 | 写入范围 | 状态 / 最近交接 | 恢复入口 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| planner | 计划 / 外部 Claude | [定义](planner.md) | 每包 Claude 原文 | 外部 Claude，具体未记录 | 计划及提示词交付，实际文件由总设计师管理 | 可派发 / NOT-RECORDED | [恢复](RESUME.md) |
| prompt-engineer | 提示词 / 外部 Claude | [定义](prompt-engineer.md) | 每包 Claude 原文 | 外部 Claude，具体未记录 | 同上 | 可派发 / NOT-RECORDED | [恢复](RESUME.md) |
| architect | 总设计师 | [分工](README.md) | 每次任务 | 未记录 | 集成、进度、Git；按授权 | 活跃 / 进度文档 | [恢复](RESUME.md) |
| reviewer | 独立审查 / Codex 专项 | [定义](reviewer.md) | 每包派发 | 历史未记录；未来见策略 | 只读；未参与该包实施 | 可派发 / NOT-RECORDED | [恢复](RESUME.md) |
| storage-steward | 存储 / Codex 专项 | [定义](storage-steward.md) | 每包派发 | 历史未记录；未来见策略 | 仅经 G1 指定 | 可派发 / NOT-RECORDED | [恢复](RESUME.md) |
| oss-scout | 依赖调研 / Codex 专项 | [定义](oss-scout.md) | 每包派发 | 历史未记录；未来见策略 | 仅经 G1 指定 | 可派发 / NOT-RECORDED | [恢复](RESUME.md) |
| wp-a | P0 治理 / Codex 专项 | [P0](../work-packages/P0.md) | [实际派发 v001](../work-packages/p0-claude-review.md) | 未记录 | P0-A 卡片所列 | 本地提交，待同步 / 原始交接 NOT-RECORDED | [P0](../work-packages/P0.md) |
| wp-b | P0 协作 / Codex 专项 | [P0](../work-packages/P0.md) | [实际派发 v001](../work-packages/p0-claude-review.md) | 未记录 | P0-B 卡片所列 | 本地提交，待同步 / 原始交接 NOT-RECORDED | [P0](../work-packages/P0.md) |
| wp-c | P0 门禁 / Codex 专项 | [P0](../work-packages/P0.md) | [实际派发 v001](../work-packages/p0-claude-review.md) | 未记录 | P0-C 卡片所列 | 本地提交，待同步 / 原始交接 NOT-RECORDED | [P0](../work-packages/P0.md) |
| source | 原文导入 / Codex 专项 | [工作包](../work-packages/source.md) | [Claude v001 第3节](../work-packages/continuation-claude-v001.md) | 本次 GPT-6.1 Terra / high | SOURCE 卡片所列 | G3 ACCEPT / [交接](handoffs/source-g3.md) | [工作包](../work-packages/source.md) |
| agent-resume | 恢复 / Codex 专项 | [工作包](../work-packages/agent-resume.md) | [Claude v001 第4节](../work-packages/continuation-claude-v001.md) | 本次 GPT-6.1 Terra / high | R 卡片所列 | R2 交审 / [交接](handoffs/agent-resume-r2.md) | [恢复](RESUME.md) |
| oss-1 | 项目调研 / Codex 专项 | [定义](oss-scout.md) | [Claude OSS v001](prompts/p1-oss.v001.md)；[实际派发解释](../work-packages/p1-claude-review.md) | 本次 GPT-6.1 Terra / high / fork none | p1-oss-research.md、handoffs/p1-oss.md | G2 DONE、独立G3 ACCEPT；/root/p1_oss_terra 已交付；[交接](handoffs/p1-oss.md) | [G1记录](../work-packages/p1-claude-review.md) |
| p1-contract-proposal | P1-0 提案 / Codex 专项 | [本包文档角色](../work-packages/p1-claude-review.md) | [Claude v002](prompts/p1-contract.v002.md)；[实际上下文](prompts/p1-contract-dispatch.v001.md) | 本次 Terra / high / fork none | 本包四份提案/交接文档 | G2 DONE、文档G3 ACCEPT；/root/p1_contract_terra 已交付；[交接](handoffs/p1-contract.md)；业务 G4 PENDING | [G1记录](../work-packages/p1-claude-review.md) |
| p1-review | P1 独立审查 / Codex 专项 | [定义](reviewer.md) | [Claude v001](prompts/p1-review.v001.md)；[实际派发](prompts/p1-dispatch-log.v001.md) | 本次 Terra / high / fork none | handoffs/p1-review.md | 档案 PASS、OSS 与 P1-0文档 G3 ACCEPT；/root/p1_review_terra 已完成；[交接](handoffs/p1-review.md) | [G1记录](../work-packages/p1-claude-review.md) |

本次运行会话映射：`/root/resume_terra` → agent-resume；`/root/source_terra` → source；`/root/review_terra` → SOURCE 独立审查，均 GPT-6.1 Terra / high。会话标识仅作追踪，不作为恢复依赖。

原始 Claude 提示词摘录见 [提示词库](prompts/agent-resume.v001.md)，实际派发内容及总设计师审查调整以 [R2 交接](handoffs/agent-resume-r2.md) 和 [P0 派发记录](../work-packages/p0-claude-review.md) 为准，不能与原文混称。
