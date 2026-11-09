# 跨会话恢复清单

## 当前续作入口（2026-11-09）

用户已恢复开发，历史 Claude 额度阻塞已解除。按 [P1 G1与派发](../work-packages/p1-claude-review.md) 的开源调研及契约提案已完成独立文档 G3，下一步审阅 [提案八项选择](../planning/p1-contract-proposal.md) 并记录用户 G4；三个 OPEN-DATA-SOURCE 的路线与细节须区分。完整 Claude 捕获为 p1-claude-plan.v001.md / v002.md，精确代码块摘录见 prompts/p1-*.md，实际派发全文见 prompts/p1-dispatch-log.v001.md。角色状态以 registry、PROGRESS 和实际 handoffs 为准，不假设旧运行仍存活。P1-A 尚未获实施授权；GitHub 仍不上传。

## 通用恢复步骤

1. 阅读根 AGENTS.md、进度 PROGRESS.md、工程规范、门禁、角色索引、模型策略、工作包卡片、Claude 完整计划与派发提示词、最近交接；按需阅读已核验的设计原文与勘误。
2. 在仓库根目录运行 `git status --short` 看未提交改动，`git log --oneline -n 10` 核对本地提交；运行 `python tools/check_repo_layout.py`，PASS 才为布局通过；运行 `python -m pytest tests/governance -q`，看退出码与测试数；SOURCE 合入后运行 `python tools/verify_source.py`，退出码 0 才为核验通过。未就绪不等于通过。检查变动所属工作包，不覆盖他人工作。
3. 状态以 PROGRESS、工作包、门禁证据与实际 Git 状态综合判断；本地提交不代表同步。R2 需总设计师确认 SOURCE G3 通过，并先复跑源文件校验。
4. 重新派发先取得本包 Claude 计划、完整提示词及 G1；当前 [Claude v001](../work-packages/continuation-claude-v001.md) 第 2、3、4 节为本轮原始提示词来源，P0 实际派发见 [审查记录](../work-packages/p0-claude-review.md)。逐字摘录及来源哈希见 `docs/agents/prompts/`；实际派发调整另见 R2 交接。按模型策略设置并提供自包含上下文、绝对目录、写入范围与验收；不得假设旧会话仍在运行。
5. 待裁决事项见 [讨论](../planning/open-discussions.md) 与 ADR；B1 和 solver 建议保持延期。禁止改写原文、扩大范围、提前实施业务、改契约、提交推送或改 Git 配置。GitHub 用户暂缓登录和上传。
6. 恢复外部 Claude 时提供 AGENTS、进度、相关工作包、审查记录、三份原文与全文哈希、逐 200 行批次哈希清单、勘误和用户裁决。原文可经已验证整文件 Copy 加全文哈希传递，仍逐批核对；缺失或不匹配不得声称核验。

本轮 SOURCE G3 已 ACCEPT，见 [SOURCE 交接](handoffs/source-g3.md)；本地 checkpoint `5dbcdee`，未推送。恢复时仍须复核当前状态。
