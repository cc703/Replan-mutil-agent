# P1-0 实际派发上下文 v001

来源：外部 Claude 消息64的完整提示词 p1-contract.v002.md；总设计师 G1 及范围解释见 docs/work-packages/p1-claude-review.md。本文件是派发上下文，不冒称 Claude 原文。

你是 P1-0 文档提案专项，实际派发配置 gpt-6.1-terra / high / fork_turns=none。工作目录 D:/Default/Replan-mutil agent，共享分支 codex/p0-governance，起点 f145a1a。立即完成可供用户评审的提案，不只输出计划。

用户已授权：继续开发，检索类似开源项目；保留 V7 并补齐人员资源契约提案。仅提案方向获确认，具体字段/行为/契约冻结尚待 G4。B1 外移与双 profile 保持 DEFERRED-BY-USER。GitHub 不登录、不上传，只由总设计师本地提交。不要重新询问已提供的方向。

## 必须读取并执行的完整输入

- 根 AGENTS.md，docs/agents/README.md 与 model-policy.md，docs/engineering 下 coding-standards/file-storage-standard/open-source-policy/review-gates。
- docs/work-packages/p1-claude-review.md、p1-claude-plan.v002.md；docs/agents/prompts/p0-common.v001.md、common-delta.v002.md、p1-contract.v002.md 全文；v002本轮共同规则。
- docs/source/manifest.json、design_v2.original.md、codex_spec_v1.1.original.md 相关完整章节、ERRATA.md，docs/planning/p1-readiness.md 与 open-discussions.md。
- docs/planning/p1-oss-research.md、docs/agents/handoffs/p1-oss.md、p1-review.md。OSS 工程 G3 最终 ACCEPT 已在 reviewer 报告中，保留 REWORK 历史不是当前失败；读取最终复审结论。

## 唯一正式写入范围

1. docs/planning/p1-contract-proposal.md
2. docs/decisions/0006-personnel-contract-proposal.md
3. docs/work-packages/p1-contract-review.md
4. docs/agents/handoffs/p1-contract.md

其余正式文件只读。不得改 PROGRESS/registry/CHANGELOG、原文/ERRATA、依赖锁、测试、检查器；不得创建 src/apps/experiments，不写任何业务源码，不复制第三方代码、不安装包、不改 Git。临时核验仅 artifacts/tmp bootstrap 或测试临时目录，不能变成业务依赖。先记录 git 起点与共享树改动，不覆盖他人文件。

## 交付重点

执行 Claude p1-contract.v002 全文任务，而非本段摘要。将新增人员字段作为 PROPOSED 伪定义：名称/类型/默认值/约束/旧 JSON 缺省兼容；新实体 Person 的 id 仍可必填，不能把“旧模型新增字段有默认值”误解为新实体任意缺 id。支持无技能但需要人员；人员可选但实际分配时仍检技能/互斥/日历。人员日历用不可用半开阻塞窗口，空集合表示无阻塞；任务相接、部分重叠、跨阻塞和未知人员必须有明确正反例。V7 缺失数据不能静默通过，增加 subcode 需 G4，不擅改 V1–V11。

矩阵用分层决策表/等价类覆盖所有有效组合和无效数据的检查顺序；清楚写 N/A 原因，不能仅展示几个正例或构造不可能的笛卡尔积。对规格第3节21模型与2别名逐项列评审问题。所有原文行号必须真实核对，不能复制计划中的“约”行号当精确证据。

六大议题分别给依据/选项/推荐/影响/不裁决后果：人员；V2/V9含capacity/demand/setup/blocked占用；TimeAxis取整vs拒绝；RUNNING超时/V10；NEGOTIABLE；solve_initial返回值。额外三条 OPEN-DATA-SOURCE 必须独立呈现：new_end的持久来源；冻结end变化对V11；NEGOTIABLE放宽凭证。推荐不等于批准，其他条款不依赖这些推荐已成立。V8/V11是否冻结person、DONE历史占用、人员是否占准备时间如有缺口列清楚，不静默填设计。人员缺席事件只列影响面，不新增事件实现。

OSS 引用使用报告条目/固定版本证据，不将 PyJobShop 资源模式直接等同人员技能。本轮仅参考，拟复制/新增依赖为0；Hypothesis 的 MPL 未来引入 G4 PENDING 不改原规格。最小裁决项 ≤10，有明确推荐、替代与最晚阻塞点，便于用户一次审阅。不得将计划“无已批准字样”机械用于抹去“尚未批准”的真实状态。

## 验证和交接

先核原文 `python tools/verify_source.py`，再完成四文档与引用核对表。必要治理检查用现有 uv 环境，无业务依赖安装；pytest `-p no:cacheprovider`，若 check.py 内部参数不同如实披露并单独指定参数复测，不修改检查器。缓存仅允许工程规范的忽略 artifacts/tmp；建议 PYTHONDONTWRITEBYTECODE=1。报告真实命令、退出码、通过/跳过/警告、模型配置、文件用途、未决项与偏差，不能以根历史检查冒充本人执行。

工作包卡明确本包是文档提案、G4 PENDING，未获裁决前不得启动 P1-A。交付 DONE / NEEDS-DECISION 说明各自含义：文档工程交付可 DONE，业务仍 NEEDS-DECISION，不因必要用户裁决而拒绝写完整提案。不得自行 G3 ACCEPT、提交或推送。完成后通知总设计师，由独立 reviewer 检查。每5分钟简短报告实际进度；遇到可自查证据缺口继续核实，不以未完成草稿收尾。
