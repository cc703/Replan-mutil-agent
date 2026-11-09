# Claude prompt excerpt

Source: docs/work-packages/p1-claude-plan.v002.md ; message 64, code block 2.
Capture: exact DOM code.textContent; sha256 f416d1c94ca4121bb12c61735ae3cabb33d53911a891a4914e6eb4ce22d38d8f.

Source capture SHA256: 5f95467e7f6bfd38b95769b2ac356604562226ffb3bd2b3d9be140e5b21355a9; lines 95-164.

<!-- BEGIN CLAUDE PROMPT -->
[附公共前言、增量 v002 与"本轮共同规则"] 运行配置：GPT-6.1 Terra，推理 high，fork none。

# 角色
P1-0 契约评审与人员资源提案 Agent。只写提案，不批准、不冻结、不改契约。

# 目标
(a) 人员资源契约补充提案；(b) 对其他契约缺口给出可审查的明确推荐；(c) 把无法由推荐解决的数据来源问题列为未决。所有条目状态 PROPOSED。

# 允许写入
docs/planning/p1-contract-proposal.md
docs/decisions/0006-personnel-contract-proposal.md（状态 PROPOSED）
docs/work-packages/p1-contract-review.md
docs/agents/handoffs/p1-contract.md
其余只读。不创建 src/，不写源码，不升级 v1.2，不冻结字段，不安装依赖。

# 前置
先确认 docs/planning/p1-oss-research.md 已获 ACCEPT 并读取；否则 BLOCKED。OSS 结果只作参考，提案不得复制代码、不得暗示批准依赖或复制。

# 输入（只读，行号须对照 docs/source 原文复核）
规格 v1.1：TimeAxis 280–285；Device.capacity 290；Task 293–306（release/deadline 298–299，deadline_level 300，demand 306）；Assignment 334；TaskOverrun 368–371；Violation 376–380；ReplanResult.status 424；solve_initial 443–446；不可行用例 527–528。
v2：Task.required_skill 211；Person 214；PlanAssignment.person_id 217、298、1377；工作日历"非开放时间以阻塞区间建模" 226；TASK_OVERRUN 356；PERSON_ABSENT 357、584；NEGOTIABLE 441、462、555；H5 451；H7 约 453；H9 455；H10 456；V2 753、V7 758、V9 760、V10 761。
基线事实：规格第 3 节有 21 个模型与 2 个别名（Slot、Event），无 Person、required_skill、person_id，但 Violation.code 含 V7。
D-001（B1 外移）、D-002（双 profile）为 DEFERRED-BY-USER，不得写成已批准。

# 任务
A 人员资源提案（向后兼容：不含人员的旧数据行为不变）
1 用伪定义（非源码）给出 Person、人员日历、Task 的技能与人员需求字段、Assignment.person_id、Instance 新增集合；新增字段全带默认值。
  v2 的 required_skill 为单数，给选项并推荐集合形式（默认空）。
2 人员日历遵循 v2:226：用"不可用阻塞窗口"表示，默认空日历 = 无阻塞 = 全时段可用，不得解读为全不可用。
  对比"开放窗口式"，说明与设备日历的一致性与差异。
3 语义：
  必需人员：要求技能非空，或显式声明需要人员（处理"无技能但需人员"：给出显式开关与"非空技能即必需"的组合选项并推荐）；
  非必需：无技能要求且未声明需要人员，person_id 可为 None。
  必需却无 persons、无分配、人员未知，一律校验失败，禁止静默通过。
  可选分配：非必需任务若填了 person_id，仍须校验人员互斥与人员日历（技能为空则技能检查平凡通过）。
4 V7 失败码：覆盖缺分配、未知人员、技能不足、同一人员重叠、落入不可用窗口；V7 不外溢到其他码，不重编号。
  表达方式给选项（可选 subcode 或仅 detail）并推荐，同时指出新增 subcode 属于对 Violation 契约的修改，需 G4。
5 能力覆盖矩阵与正反例：(有无 persons)×(任务需否人员)×(分配状态)×(技能足否)×(重叠与否)×(日历内外)×(必需/可选分配)，
  每格给期望结果与最小示例（文字，不写代码）；标明 P1 测与不测的。
6 影响面：PERSON_ABSENT、重规划、生成器，仅列影响不扩展设计。
B 缺口推荐（各写：依据、问题、选项、推荐、影响面、待裁决点；只写推荐，不扩大范围）
7 V2 与 V9：capacity=1 由 V2；capacity>1 由 V9；同一违规只由一个码报告；demand>capacity；阻塞窗口占满容量。
8 TimeAxis 取整：release 与 duration 向上、deadline 向下、阻塞窗口起点向下终点向上（保守）；对比"拒绝非整槽输入"；
  naive datetime；取整致不可行时的处理。
9 solve_initial 返回 None 无法区分超时与不可行：选项（结构化结果 / None 加异常 / 对齐 ReplanResult.status），推荐结构化结果，
  状态区分最优、可行、不可行、超时未知、模型非法。
C 未决数据来源（G4-未决）：以下三项独立成条，每项给选项与影响，推荐可写但必须标注"推荐≠批准"，且其他条款不得依赖这些推荐成立
10 V10 与 overrun：TaskOverrun.new_end 在 Instance 中无持久字段；校验与重规划时"当前预计结束"从何而来。
   候选：新增 Instance/Task 字段、挂在 Plan 元数据、由调用方传参；说明各自对 V10 的影响。
   含"V10 对 RUNNING 与未开始任务分别如何要求"的候选表述。
11 冻结任务的 end 变化对 V11 的影响：V8 只固定设备与开始时间，overrun 使冻结任务 end 变化时，V11 是否视为违规；给选项。
12 NEGOTIABLE 放宽凭证缺字段：规格 300 默认 NEGOTIABLE，v2 441、462 默认按硬、555 入目标，三处并存；
   放宽后的截止期与授权记录在现有字段中无处表示，V5 无法知道已授权。给"默认按硬 + 显式放宽记录"与"默认入目标"两条路线，
   并列出各路线需要新增的字段；状态 OPEN-DATA-SOURCE。
D 评审组织
13 契约评审清单：对规格第 3 节每个模型（21 个）与 2 个别名列"原文是否有缺口"，只引用不改写；涉及 ERRATA 的仅引编号。
14 OSS 借鉴：引用 p1-oss-research 条目编号，写可借鉴点与不适用点，不含代码。
15 最小裁决项清单（≤10 条，各含推荐与不裁决的后果），其中第 10–12 项标注 OPEN-DATA-SOURCE。
16 工作包卡片：文件清单、输入、验收、依赖、阻塞；注明用户裁决前不得启动 P1-A。

# 验收
- 四个文件存在，全部条目状态 PROPOSED，无"已批准/已冻结"字样；第 10–12 项明确为 OPEN-DATA-SOURCE。
- 每个引用为"文件:行号"，交接单附逐条核对表。
- 任务 1–6 完整；覆盖矩阵含必需与可选分配、空日历与非空日历的正反例；"旧数据行为不变"逐条说明。
- 缺人员的各种情形均明确为失败，无静默通过路径。
- git diff 仅含上述四个文件；docs/source、规格与设计副本、ERRATA、依赖文件无改动；无 src/。
- 治理测试、ruff、mypy、布局检查、verify_source 通过（pytest 用 -p no:cacheprovider）。

# 交接
公共前言 H 格式。另附：引用核对表、候选勘误、最小裁决项、所用模型/推理档/fork 模式。
<!-- END CLAUDE PROMPT -->
