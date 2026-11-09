# P1-0 契约提案交接

状态：DONE（四份文档工程交付，待独立 G3）；NEEDS-DECISION（业务 G4 PENDING，P1-A 不得启动）。派发配置 gpt-6.1-terra / high / fork none；运行时实际模型无法独立查询，按派发记录。起点 f145a1a409c13d81e48c1ec79ecef48cae133760；起点共享树已有 dispatch-log、registry、PROGRESS 修改和 dispatch 提示词未跟踪，未覆盖。

文件：`docs/planning/p1-contract-proposal.md` 为提案和裁决；`docs/decisions/0006-personnel-contract-proposal.md` 为人员 ADR；`docs/work-packages/p1-contract-review.md` 为卡片和 21 模型、2 别名清单；本文件为交接。仅四文件为本包写入，不提交、不推送、不安装、不创建业务源码。

验证：`python tools/verify_source.py` 退出 0，三份原文全部核验 PASS。设置 PYTHONDONTWRITEBYTECODE=1，RUFF_CACHE_DIR 与 MYPY_CACHE_DIR 指向 artifacts/tmp，运行 `uv run --python 3.11 --group dev python tools/check.py`：布局、导入、原文、ruff、格式、mypy 通过，pytest 33 passed、1 skipped（symlinks unavailable）；该入口内部未禁用 cacheprovider。另运行 `uv run --python 3.11 --group dev python -m pytest -q -p no:cacheprovider tests/governance` 退出 0，33 passed、1 skipped、1 warning（禁用插件后 unknown config option cache_dir）。治理检查不构成业务验收。

## 原文引用核对表

| 来源与行 | 实际核对内容 |
|---|---|
| `docs/source/codex_spec_v1.1.original.md:278–285` | Slot 与 TimeAxis |
| `docs/source/codex_spec_v1.1.original.md:287–338` | Device 至 Assignment 声明，含容量、任务、日历、准备与实例 |
| `docs/source/codex_spec_v1.1.original.md:340–430` | PlanMetrics 至 ReplanResult，含事件、校验、重规划 |
| `docs/source/codex_spec_v1.1.original.md:443–446` | solve_initial 返回 Plan 或 None |
| `docs/source/design_v2.original.md:211–217` | Task 技能、Person 与 PlanAssignment |
| `docs/source/design_v2.original.md:224–228` | 时间槽、阻塞日历和时区 |
| `docs/source/design_v2.original.md:357` | PERSON_ABSENT 扩展 |
| `docs/source/design_v2.original.md:441` | NEGOTIABLE 默认硬且可授权 |
| `docs/source/design_v2.original.md:448–456` | 日历、人员、冻结、准备、容量、硬截止 |
| `docs/source/design_v2.original.md:462` | S1 与默认硬 |
| `docs/source/design_v2.original.md:555` | NEGOTIABLE/SOFT 迟延变量 |
| `docs/source/design_v2.original.md:584` | 人员缺席影响 |
| `docs/source/design_v2.original.md:753–762` | V2、V5、V7–V11 |

候选勘误为人员字段与 V7 不一致、放宽凭证缺失；不修改原文或 ERRATA。最小八项裁决、替代和最晚阻塞点见提案；三个 OPEN-DATA-SOURCE 独立列出。OSS 参考固定版本与局限见调研稿；无复制和新增依赖，Hypothesis 未来引入 G4 PENDING。B1、双 profile 仍 DEFERRED-BY-USER。

限制：提案为评审草案，存在需独立复核的等价类完整性、引用上下文及人员准备/历史/冻结边界；不声称 G3 ACCEPT。建议独立 reviewer 审核后由总设计师汇总 G4，用户裁决前不启动 P1-A。

## P1-0 G3 REWORK 定向返工交接

保留以上首次交付记录；独立审查在 `docs/agents/handoffs/p1-review.md` 的 P1-0 工程 G3 REWORK 段列出 R1–R5。本次 G2 文档修订完成，待独立 G3 复审；G4 PENDING，P1-A 未授权。

| 发现 | 修复位置与内容 |
|---|---|
| R1 | 主提案 G3 返工人员边界与 ADR 追加：准备、DONE、冻结 person 各给选项、推荐及影响，区分 V8/V11 |
| R2 | 主提案时间接口：原签名适配与专用 API 候选、时长转换和边界、非法/预检查不可行/求解不可行 |
| R3 | 工作包卡 G3 返工：四个精确路径、只读与禁止范围、G0–G5 责任状态、返工与本地提交边界 |
| R4 | 主提案三个完整 JSON 文档示例及变体、预期、短路和拟测范围 |
| R5 | 主提案 RUNNING/V10 三套判断、超时与提前预测、缺来源、调用方路线未定；保留三个 OPEN-DATA-SOURCE |

补充引用核对：`docs/source/codex_spec_v1.1.original.md:297` 确认 duration 为整数槽；`:527–528` 确认不可行黄金例断言 None 及诊断核。上述新建议均 PROPOSED；结构化返回的适配和黄金用例变更须 G4。

本次真实命令：`python tools/check_repo_layout.py` 退出 0、Layout PASS；`python -c` 使用标准库提取主提案三段 JSON 并逐一 `json.loads`，退出 0，3 段有效；人工核对原文 297、527–528 行；`git status --short` 与 `git diff --name-only` 检查共享树，观察 reviewer 的 p1-review 与总设计师 dispatch-log、registry、PROGRESS 已改，四份本包文件未跟踪；未认作本包越界或覆盖。Git 提示其他共享文件存在 CRLF 转换警告。纯文档返工未重复全套治理、网络核查；首轮检查结果见上。无新增依赖、安装、源码、提交或推送。范围检查为共享树快照，未跟踪文件不在普通 diff 中，须由 reviewer 再核对。下一步总设计师派独立复审，接受前不称 G3 通过。

### 定向复审后补充修订

R3 流程措辞已修正：G3 通过后可在 G4 PENDING 时由总设计师保存提案文档本地检查点，该检查点不代表业务批准、完整 G5 或远端同步；业务实施提交及完整 G5 仍按 G4 已解决或 N/A，远端暂缓。裁决项 4 同时明确推荐通用 `to_slot` 拒绝非整槽、外部适配层按字段保守舍入，理由是原签名无字段语义；该推荐仍待 G4。

本次实际定向检查：`rg -n` 核对工作包门禁和提案裁决项及时间接口段落，结果与上述措辞一致；未重跑全套测试。本次仅修订工作包卡、契约提案与本交接；独立复审结果待 reviewer 记录。
