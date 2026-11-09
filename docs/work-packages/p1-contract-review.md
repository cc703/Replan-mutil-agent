# P1-0 契约工作包与评审清单

总设计师集成回执：返工已完成，独立 reviewer 最终文档工程 G3 ACCEPT，见 ../agents/handoffs/p1-review.md；下文首轮/返工待审为历史过程。业务 G4 仍 PENDING，不代表批准契约或远端同步。

状态：PROPOSED，文档工程待独立 G3；业务 G4 PENDING。用户裁决前不得启动 P1-A。输入：已核验原文、Claude v002、G1、OSS 工程 G3 ACCEPT；输出：契约提案、ADR 0006、本卡、交接。验收：字段和旧数据默认、分层等价类、V7、六项议题和三个独立数据来源、逐模型清单及引用核验；独立 reviewer 判 G3。阻塞：G4 尚未裁决，不得冻结或实现。

## 规格第 3 节逐项问题

原文统一为 `docs/source/codex_spec_v1.1.original.md`，编号为核对行。以下为评审问题，非改写原文；未列缺口不代表全局无缺陷。

| 项目 | 行 | 缺口 / 问题 |
|---|---:|---|
| Slot | 278 | 时间转换舍入策略？ |
| TimeAxis | 280 | 非整槽与 naive 时间如何处理？ |
| Device | 287 | capacity 正数和阻塞容量占用？ |
| Task | 293 | 人员字段、需求、NEGOTIABLE 授权及运行预计 end 缺失？ |
| Precedence | 308 | 引用、时滞边界如何验？ |
| BlockedWindow | 314 | 重叠阻塞与容量规则？ |
| SetupRule | 320 | 人员占准备与容量需求？ |
| Instance | 325 | 人员集合及运行预计 end 来源？ |
| Assignment | 334 | person_id 缺失？ |
| PlanMetrics | 340 | 计算口径何处定义？ |
| Plan | 350 | 放宽授权及事件预计 end 来源？ |
| DeviceOutage | 357 | 事件区间与已有阻塞如何合并？ |
| UrgentInsert | 363 | 新任务引用和 ID 冲突如何处理？ |
| TaskOverrun | 368 | new_end 如何持久并供 V10 使用？ |
| Event | 373 | 缺 PERSON_ABSENT，是否纳入后续阶段？ |
| Violation | 376 | V7 细因仅 detail 或新增 subcode？ |
| ValidationReport | 382 | passed 与 violations 一致性？ |
| ReplanParams | 387 | 参数边界和非法组合？ |
| ImpactReport | 400 | 三集合是否互斥且完整？ |
| Candidate | 406 | 校验失败候选是否允许返回？ |
| ConflictCore | 414 | group_id 来源及稳定性？ |
| RelaxationOption | 418 | 放宽凭证与生效范围？ |
| ReplanResult | 423 | 超时有可行候选如何表示？ |

勘误候选：人员缺字段与 V7 的契约缺口、NEGOTIABLE 授权记录缺失；仅建议另行审查，不改 ERRATA。更多议题、推荐、替代和最晚裁决点见 [提案](../planning/p1-contract-proposal.md)。

## G3 返工：精确范围和门禁

唯一允许写入：

1. `docs/planning/p1-contract-proposal.md`：字段、例子和裁决提案。
2. `docs/decisions/0006-personnel-contract-proposal.md`：人员 ADR 提案。
3. `docs/work-packages/p1-contract-review.md`：本工作包卡与模型清单。
4. `docs/agents/handoffs/p1-contract.md`：检查、来源及交接。

其余正式文件只读；禁止修改原文、ERRATA、PROGRESS、registry、CHANGELOG、依赖及锁、检查器和测试；不创建 src/apps/experiments，不写业务代码、安装、复制第三方代码或修改 Git 配置。临时材料仅允许 artifacts/tmp。依赖是 Claude v002 与 G1、原文哈希核验、OSS 工程 G3 ACCEPT。验收为四文件、原文引用、21 模型及两别名、人员兼容和等价类、六议题与三条独立数据来源、≤10 裁决项、真实检查交接；独立复核为 G3，业务裁决为 G4。

| 门禁 | 责任 | 当前状态 |
|---|---|---|
| G0 | 总设计师明确目标、范围、依赖 | PASS（已派发） |
| G1 | Claude 提供计划和提示词，总设计师审查 | PASS（见 p1-claude-review） |
| G2 | 专项执行、自检、交接 | 本次返工完成后交接，待总设计师核对 |
| G3 | 独立 reviewer 审查，总设计师集成 | 首轮 REWORK，返工待复审；未 ACCEPT |
| G4 | 用户选择，总设计师记录 | PENDING，P1-A 不得启动 |
| G5 | 总设计师核验并提交同步 | PENDING；用户暂缓远端，当前只允许本地提交，远端同步待恢复授权且核验 SHA |

失败回退：G2 发现范围、检查或证据缺口时修订本包并重新自检；G3 REWORK 回作者修订后独立复审，ESCALATE 交总设计师；G4 未决定仅阻塞依赖的实现，用户作决定后记录，不以建议代替决定。G3 通过后，即使 G4 仍 PENDING，总设计师可保存提案文档本地检查点；这不等于业务 G4 批准、完整 G5 验收或远端同步。业务实施提交和完整 G5 仍须 G3 通过且 G4 已解决或 N/A，并核验范围与检查；远端暂缓，未同步不得标记同步成功。范围或验收实质变化须回 Claude/G1 重规划。
