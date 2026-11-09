# P1 调研与契约提案：G0/G1 与实际派发

日期：2026-11-09，Asia/Shanghai。总设计师负责本记录。工作树 `D:/Default/Replan-mutil agent`，分支 `codex/p0-governance`，起点 `c8e1243`，起点工作区干净。

## 用户授权与目标

用户恢复开发，并要求检索可借鉴的开源项目；已选择补齐人员资源契约提案、保留 V7。此选择只授权提案方向。GitHub 登录与上传仍暂缓，所有交付只做本地提交。B1 外移、双 profile 保持 DEFERRED-BY-USER。

## Claude 证据

原会话 https://claude.ai/chat/54ab7bfe-2bca-4714-9759-e3ae3e5474e7 已恢复响应。

- 消息62：[v001渲染文本](p1-claude-plan.v001.md)。其依赖调研不足以覆盖类似项目，因此未直接派发。
- 消息64：[v002渲染文本](p1-claude-plan.v002.md)。包括完整 OSS、提案、独立审查提示词；三个代码块通过 DOM code.textContent 精确取回，提示词文件记录内容 SHA256。渲染捕获不是原始 Markdown，不冒称字节级恢复原始 Markdown。
- 提示词：[OSS](../agents/prompts/p1-oss.v001.md)、[提案v002](../agents/prompts/p1-contract.v002.md)、[审查](../agents/prompts/p1-review.v001.md)。[提案v001](../agents/prompts/p1-contract.v001.md) 保留，已被 v002 取代，未派发。

## G0/G1 总设计师结论：PASS（仅文档调研与提案）

顺序为 OSS-1 → OSS 独立 G3 ACCEPT → P1-0 提案 → 提案独立 G3 → 用户 G4 → 后续实施计划。当前不创建 src，不冻结契约，不安装业务依赖、不改锁、不复制第三方源码。未核实事实不能用于实施。

文件所有权：

| 角色 | 本包唯一允许写入 |
|---|---|
| OSS Scout | docs/planning/p1-oss-research.md；docs/agents/handoffs/p1-oss.md |
| P1-0 提案角色 | docs/planning/p1-contract-proposal.md；docs/decisions/0006-personnel-contract-proposal.md；docs/work-packages/p1-contract-review.md；docs/agents/handoffs/p1-contract.md |
| 独立 reviewer | docs/agents/handoffs/p1-review.md |
| 总设计师 | 本记录、Claude捕获与提示词归档、registry/RESUME/PROGRESS/CHANGELOG、提交集成 |

提案角色是本工作包的文档专项，不是对 contract-engineer 既有源码写入权限的扩大。所有专项派发实际设置 `model=gpt-6.1-terra`、`reasoning_effort=high`、`fork_turns=none`，自包含上下文，不自动降级。

## 实际派发的解释与边界

- 附 P0 公共前言、增量v002、v002本轮共同规则及本包提示词全文；上下文通过仓库持久文件传递。更具体的当前阶段文件清单优先于历史 P0 清单。新增文件通过文件清单声明，不把“只新增有默认值字段”误解释为 Person.id 可以缺失；这指旧模型新增字段，候选新实体自身应有完整约束。
- v002要求阶段1先G3，但审查提示词也列全部提案文件：独立 reviewer 分两次执行，同一报告先记录 OSS 的 G3，其余明确 NOT-STARTED，提案交付后追加完整审查。前置 ACCEPT 是工程审查结论，不是要求 GitHub 同步后的工作包 ACCEPTED，避免循环。
- 各专项先记录派发起点；共享树中 root 归档和其他专项授权文件不计自身越界。仅检查自己的改动，不能把共享树合法改动删除或回退。
- pytest加 `-p no:cacheprovider`，尽量设置 PYTHONDONTWRITEBYTECODE；必要检查工具的忽略缓存只允许工程规范的 artifacts/tmp bootstrap 范围，不把生成缓存当正式交付。测试隔离使用临时目录。禁止改测试、检查器或配置来获取通过。
- 模型/术语/行号由原文复核。原计划中“无已批准/已冻结字样”指不能声称提案已获批准；如“尚未批准”或用户已确认提案方向，应如实描述，不能机械删除审批状态。
- 覆盖矩阵需完整表达有效组合、无效组合和短路检查顺序，可用分层决策表与等价类，不能以不合理的全笛卡尔积制造无法成立情形。不改变所要求的边界覆盖。
- 当前仅调研已有项目，不表示将其作为新增依赖。许可证说明记录一手文本与实际义务，必要用户裁决仍保留。未来依赖新增按实际工作包授权和 open-source-policy 执行。
- 用户裁决前先完成可评审提案、独立检查与本地检查点，不以 G4 未决为由丢弃或不保存交付；G4 未决只阻塞受影响的业务实现。

## 恢复基线验证

总设计师执行 `uv run --python 3.11 --group dev python tools/check.py`：布局、导入边界、三份原文全文与14批核验 PASS；33 passed、1 skipped in 8.47s（本机符号链接权限不可用）；ruff check/format PASS；mypy 4 source files PASS。这是治理检查，不是 P1 业务验收。

## 当前状态

G0/G1 PASS。OSS-1 与 P1-0 文档工程独立 G3 均已 ACCEPT；发现和返工历史见 p1-review.md。业务 G4 PENDING；文档仅保存本地检查点，完整 G5 与远端同步未完成。具体接口/字段与三个 OPEN-DATA-SOURCE 未冻结，下一步用户审阅提案八项选择。实际交接、后续命令和提交证据以进度与 handoffs 为准。
