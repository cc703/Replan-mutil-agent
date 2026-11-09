# Claude P1-0 v001 — rendered message capture

Source: https://claude.ai/chat/54ab7bfe-2bca-4714-9759-e3ae3e5474e7 ; message 62 ; 2026-11-09.
Capture: DOM innerText, not original Markdown; code-block line breaks preserved. UI labels may be included.

Claude responded: 以下是提案，我没有修改你的本地仓库。引用的行号来自我刚读取的会话原文，与 docs/source 原文行号一致，派发给 Agent 前请让它逐条复核。
Checking the acceptance criteria and handoff requirements for the review package

Checking the acceptance criteria and handoff requirements for the review package

以下是提案，我没有修改你的本地仓库。引用的行号来自我刚读取的会话原文，与 docs/source 原文行号一致，派发给 Agent 前请让它逐条复核。

一、主提示词（P1-0 契约评审与人员资源补充提案）

text
[附 P0 公共前言 + 增量 v002] 运行配置：GPT-6.1 Terra，推理 high。

# 角色
P1-0 契约评审与人员资源提案 Agent。只写提案，不批准、不冻结、不改契约。

# 目标
(a) 写出人员资源契约补充提案；(b) 对另外五项契约缺口给出可审查的明确推荐。所有条目状态 PROPOSED。

# 输入（只读，行号须自行对照 docs/source 原文复核）
规格 v1.1：TimeAxis 280–285；Device.capacity 290；Task 293–306（release/deadline 298–299，deadline_level 300，demand 306）；Assignment 334；TaskOverrun 368–371；Violation 376–380；ReplanResult.status 424；solve_initial 443–446；不可行用例 527–528。
v2：Task.required_skill 211；Person 214；PlanAssignment.person_id 217、298、1377；TASK_OVERRUN 356；PERSON_ABSENT 357、584；NEGOTIABLE 441、462、555；H5 451；H7 约 453；H9 455；H10 456；校验器 V2 753、V7 758、V9 760、V10 761。
已知缺口：规格第 3 节无 Person、required_skill、person_id，但 Violation.code 含 V7。
docs/source/ERRATA.md 与 docs/planning/open-discussions.md 只读；D-001（B1 外移）、D-002（双 profile）为 DEFERRED-BY-USER，不得写成已批准。

# 允许写入
docs/planning/p1-contract-proposal.md
docs/decisions/0006-personnel-contract-proposal.md（状态 PROPOSED）
docs/work-packages/p1-contract-review.md
其余只读。不创建 src/，不写源码，不升级 v1.2，不冻结字段，不安装依赖。发现的原文问题写入提案"候选勘误"节，由总设计师决定是否进 ERRATA。

# 任务
A 人员资源提案（向后兼容优先：不含人员的旧数据与用例行为不变）
1 用伪定义（非源码）给出 Person、人员日历窗口、Task 要求技能、Assignment.person_id、Instance 新增集合的字段草案（类型、默认值、约束）；新增字段全部有默认值。与 v2 命名差异（required_skill 单数）给选项与推荐（推荐 required_skills 集合，默认空）。
2 语义：人员"非必需"（无要求技能且未声明需人员 → person_id 可为 None，不适用 V7）；"必需"（要求技能非空 → 必须分配人员）。需人员但无人员、无分配、人员未知，一律校验失败，禁止静默通过；persons 为空时同样失败。
3 V7 子类：缺分配、未知人员、技能不足、同一人员重叠、落入不可用窗口；给表达选项（V7 码加可选 subcode / 仅 detail 文本）与推荐。
4 能力覆盖矩阵与正反例：(有无 persons)×(任务需否人员)×(分配状态)×(技能足否)×(重叠与否)×(日历内外)，每格给期望结果与最小示例（表格与文字，不写代码）；标明 P1 要测的与不测的。
5 仅列对 PERSON_ABSENT、重规划、生成器的影响面，不扩展设计。
B 五项缺口（各写：依据、问题、选项、推荐、影响面、待裁决点）
6 V2 与 V9：capacity=1 由 V2 判重叠，capacity>1 由 V9；同一违规只由一个码报告；demand>capacity 的处理；阻塞窗口占满容量。
7 TimeAxis：release 与 duration 向上取整、deadline 向下取整、阻塞窗口起点向下终点向上（保守，缩小可行域），对比"拒绝非整槽输入"；naive datetime 的处理；取整致窗口不可行时的处理。
8 RUNNING 与 overrun、V10：V10 只对未开始任务要求 end−start=duration；RUNNING 要求 end≥start+duration，且等于最新预计结束（TaskOverrun.new_end）；DONE 实际值不进 Plan；说明与冻结 H7 的关系。
9 NEGOTIABLE：指出 v2 441/462（默认按硬）与 555、规格 300（默认 NEGOTIABLE）的张力；选项 A 默认按硬、放宽须显式记录；选项 B 默认入目标；推荐 A，并说明 V5 与放宽记录的表示方式。
10 solve_initial 返回 None 无法区分超时与不可行：选项（结构化结果 / None 加异常 / 对齐 ReplanResult.status），推荐结构化结果，状态须区分最优、可行、不可行、超时未知、模型非法。
C 评审组织
11 契约评审清单：对规格第 3 节每个模型列"原文是否有缺口"，只引用不改写；涉及 ERRATA 的只引编号。
12 最小裁决项清单（≤8 条，各含推荐与不裁决的后果）。
13 工作包卡片：文件清单、输入、验收、依赖、阻塞；注明用户裁决前不得启动 P1-A。

# 验收
- 三文件存在，全部条目状态 PROPOSED，无"已批准/已冻结"字样。
- 每个引用为"文件:行号"，交接单附逐条核对表。
- 任务 1–5 完整；六项缺口各有依据、选项、推荐。
- 明确并逐条说明"不含人员的旧数据行为不变"。
- git diff 仅含上述三文件；docs/source、规格与设计副本、ERRATA 无改动；无 src/。
- 33 项治理测试（1 项跳过）、ruff、mypy、布局检查、verify_source 全部通过。
- B1 外移与双 profile 仅作 DEFERRED-BY-USER 引用。

# 交接
公共前言 H 格式。另附：引用核对表、候选勘误、最小裁决项、所用模型与推理档。
二、可选并行包：OSS 调研（不安装依赖）

text
[附公共前言与增量 v002] 运行配置同上。
角色：OSS 调研 Agent。允许写入：docs/planning/p1-oss-research.md。
任务：调研 pydantic v2、numpy、pytest、hypothesis 的当前稳定版本、许可证、官方文档链接、Windows 与 Python 3.11 兼容性、替代方案，并写明检索日期。只查官方来源，不安装、不改 pyproject、不改依赖登记表；查不到的写"未核实"。
验收：每项含来源链接与日期；无其他文件改动。交接：公共前言 H 格式。
三、最小用户裁决项（括号内为推荐）
编号	裁决点	推荐
1	要求技能非空即"必需人员"，还是另设显式开关	非空即必需
2	技能字段用 required_skills 集合，还是沿用 v2 的单数	集合，默认空
3	V7 子类用可选 subcode，还是只写 detail	可选 subcode
4	时间取整：保守取整，还是拒绝非整槽输入	保守取整
5	NEGOTIABLE：默认按硬加显式放宽，还是默认入目标	默认按硬
6	solve_initial 返回结构化结果，还是保持 None	结构化结果
7	V2/V9 分工与 V10 对 RUNNING 的处理	同意提案推荐

以上都只是授权提案，不是批准具体字段或开始业务实现。

范围控制：第 6 至 10 项是原文里的真实缺口，但每项只要求"依据、选项、推荐"，不要求展开设计，避免 P1-0 变成重写契约。

依赖与阻塞：P1-A 契约实现必须等你完成上面的裁决；独立 G3 建议覆盖"旧数据兼容性"和"缺人员不能静默通过"两个点。






4 minutes ago
