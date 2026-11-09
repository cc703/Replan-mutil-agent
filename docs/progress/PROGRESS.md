# 项目进度

更新日期：2026-11-09（Asia/Shanghai）。P1-A 数据模型与TimeAxis源码及测试已完成，独立工程G3 ACCEPT；完整检查62 passed、1 skipped，布局/导入/原文/ruff/全量mypy通过。用户工程委托已落实，GitHub仍暂缓上传；P1整体尚未完成，独立校验器/生成器/产物基础设施后续实施。

## 当前工作包

| ID | 名称 | 负责专项 | 分支 | 状态 | 门禁 | 工程验收 | 远端同步 | 验收日期 | 提交证据 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P0-A | 治理与规范 | governance | codex/p0-governance | IN-REVIEW | G1/G2/G3 通过；G5 用户暂缓 | 总设计师与独立审查通过 | 用户选择稍后登录，仅保留本地 | 2026-11-09 | 610ab30（本地已提交） |
| P0-B | 协作机制 | collaboration_docs | codex/p0-governance | IN-REVIEW | G1/G2/G3 通过；G5 用户暂缓 | 独立审查发现循环门槛，修复后 ACCEPT | 用户选择稍后登录，仅保留本地 | 2026-11-09 | b9d94cff318ad1ef89394214eb2d9f132d12e7bd |
| P0-C | 机器门禁 | machine_gates | codex/p0-governance | IN-REVIEW | G1/G2/G3 通过；G5 用户暂缓 | 配置驱动缺口修复后独立复审 ACCEPT | 用户选择稍后登录，仅保留本地 | 2026-11-09 | 4024077b3f9b4659ba82d5cd55c08bbe25059377 |
| SOURCE | 原始设计与 Claude 原文导入 | source_terra | codex/p0-governance | IN-REVIEW | G1/G2/G3 通过；G5 仅本地 | review_terra 修复后复审 ACCEPT | 用户暂缓，仅本地 | 2026-11-09 | 5dbcdee |
| AGENT-RESUME-R1 | 模型策略、角色索引及恢复 | resume_terra | codex/p0-governance | IN-REVIEW | G1/G2/G3 通过 | 独立 review_terra ACCEPT | 用户暂缓，仅本地 | 2026-11-09 | 5dbcdee |
| AGENT-RESUME-R2 | 提示词库及 P1 开工设计 | resume_terra | codex/p0-governance | IN-REVIEW | G1/G2/G3 通过；G5 仅本地 | review_terra ACCEPT，7份摘录及21类/2别名覆盖已核对 | 用户暂缓，仅本地 | 2026-11-09 | 1dd1b3e |
| P1-PLAN | Claude 续作计划与实际派发归档 | 总设计师 | codex/p0-governance | IN-REVIEW | G1 PASS；档案独立前置 PASS；G5 仅本地 | 四份提示词payload/行范围/捕获哈希一致 | 不上传 | 2026-11-09 | 8a5914d |
| OSS-1 | 类似开源项目与 P1 依赖核实 | p1_oss_terra | codex/p0-governance | IN-REVIEW | G0/G1/G2/G3 PASS；G5 仅本地 | R1修复后独立工程 ACCEPT；仅参考，不安装/改锁 | 不上传 | 2026-11-09 | f145a1a |
| P1-0 | 人员资源与契约缺口提案 | p1_contract_terra | codex/p0-governance | IN-REVIEW | G1/G2/G3 PASS；G4 已获工程委托；G5 仅本地 | 已审查推荐按用户新授权落实 | 不上传 | 2026-11-09 | 452b2be；授权更新见 ADR 0006 |
| P1-A | 全数据模型与 TimeAxis 源码 | p1a_code_terra | codex/p0-governance | IN-REVIEW | G0/G1/G2/G3 PASS；G4工程委托；G5仅本地 | 独立ACCEPT，62 passed/1 skipped，全部检查通过 | 用户暂缓，不上传 | 2026-11-09 | 本地提交主题 feat(core): implement scheduling contracts and exact time axis |

分支为共享集成分支，不表示每个专项都有独立工作树。验收、检查、提交及远端 SHA 必须由总设计师按实际执行结果补记。

## 后续阶段

| 阶段 | 目标 | 状态 |
| --- | --- | --- |
| P1 | 数据契约、校验与产出物基础设施 | IN-PROGRESS（模型/TimeAxis已工程验收；校验/生成/产物后续） |
| P2 | 初始调度 | TODO |
| P3 | 仿真器 | TODO |
| P4 | 重规划 | TODO |
| P5 | 诊断、松弛和候选 | TODO |
| P6 | 业务 Agent | TODO |
| P7 | 后端和前端 | TODO |
| P8 | 实验框架 | TODO |

## 决策与来源

决策索引见 [docs/decisions/](../decisions/)。已取回的完整设计 v2、开发规格 v1.1 和历史 P0 原计划分别保存在 docs/source/*.original.md；全文与14个分块均已对照外部预期值验证。原文不静默升级或改写，勘误见 docs/source/ERRATA.md。

计划/提示词来源：[Claude 原会话](https://claude.ai/chat/54ab7bfe-2bca-4714-9759-e3ae3e5474e7)，2026-11-09 P0 计划。具体版本、原文和审查证据见 [P0 工作包](../work-packages/P0.md)。

## 风险与阻塞

- 原设计缺失阻塞及核验器返工均已解除：三份全文与14分块哈希匹配，清单完整性、重复条目、分块覆盖和路径边界修复后独立复审 ACCEPT。R2 可按已审查的 Claude 计划启动。
- 原规格命名与缓存约束需要治理修复。用户已裁决 B1 外移和 solver 双 profile 两项建议暂不修改（DEFERRED，见 ADR 0002/0003），按原规格推进并保留批注；对应模块实施前再讨论，P0 不因此阻塞。
- 文件检查提前至 P0，只完成治理机制不等于 P1 的 ArtifactStore 已实现。
- 用户决定本项目统一使用 cc703。仓库局部 Git credential username 已设 cc703，已连接 GitHub 插件也是 cc703 且有 push 权限。用户随后选择先保留本地提交、稍后登录，设备登录等待已结束；不继续推送或改用插件上传。此前推送403，不能计为已同步。提交作者仍为 chm。
- 2026-11-09 隐私核对：项目根目录与 Git common-dir 均指向 D:/Default/Replan-mutil agent 内，只有一个工作树，未共享其他仓库的 .git。远端 ls-remote 无分支引用，GitHub 仓库 size=0，未发现本轮提交已上传；仓库当前为 public。未来上传到公开仓库的文件和提交作者邮箱可被公众读取，本次未修改可见性或作者邮箱。
- 浏览器读取可能超时；无本工作包 Claude 完整提示词时不能绕过 G1。
- 用户指定后续所有 Codex 专项均为 GPT-6.1 Terra/high；本次 source_terra、resume_terra、review_terra 已以 model=gpt-6.1-terra、reasoning_effort=high、fork_turns=none 实际派发。旧 P0 会话不追溯冒称同模型。角色索引/模型策略/交接/恢复清单见 docs/agents/。
- 历史用户选择“补齐人员资源契约提案，保留 V7”后，现已进一步授权“按原设计和推荐推进，工程细节你们决定，业务规则变化再问我”。总设计师与Claude落实已审查字段、接口与测试选择，按ADR0006记录，不再让用户逐字段审批；仅真实业务变化重新裁决。B1/双profile仍延期。
- 历史额度阻塞已解除：用户恢复开发后，Claude 原会话消息62完成旧请求，消息64补齐类似开源项目、依赖核实、提案与独立审查完整提示词。此前确实停止并保存 c8e1243，见 [历史阻塞](../work-packages/p1-planning-blocker.md)；不把历史暂停写成当前阻塞。当前计划与实际派发解释见 [G1记录](../work-packages/p1-claude-review.md)。
- 当前阻塞边界：用户工程委托已解除P1-A原G4阻塞，Claude实施计划G1通过。RUNNING预计结束、冻结end证据、NEGOTIABLE授权的具体类型/API在P1-B前由工程方审定记录；P1-A不实现校验器，不因未来上下文停工。缺来源不能把正式计划判通过。许可、费用、业务规则变化仍按独立门禁处理。
- OSS-1 核实 OR-Tools v9.15、PyJobShop v0.0.9 的固定提交/源码/许可证文件及仓库树 NOTICE 范围，并核实五项依赖的版本与平台元数据。全部仅参考，复制与新增依赖为0；Python 3.11 Windows 动态安装联测 NOT-RUN，不能把元数据支持当运行验证。Hypothesis 的 MPL-2.0 未来实际引入前须用户 G4，PENDING；原规格要求未删除。详见 docs/planning/p1-oss-research.md。

## 本轮验证与审查证据

- P1-A：外部Claude消息66与全量类型检查增补消息68完整保存在 docs/work-packages/p1-a.md，G1通过；src/scheduler_core仅三个源码文件，tests/unit仅两个单元测试文件。21个原模型、两别名、Person/PersonBlockedWindow及人员默认兼容、精确UTC整槽TimeAxis已实现，不含独立validator/solver/generator。
- P1-A独立审查关闭TimeAxis极端日期/终点溢出、依赖来源登记、治理测试不准确嵌套类型标注三项。增补只修旧测试类型和必要cast，数据/断言/skip保持不变；mypy覆盖tools/tests/src全部11源码文件，无缩小目录或放宽配置。独立完整check为62 passed、1 skipped（符号链接权限），ruff/format/mypy/layout/source PASS；最后类型收窄后定向测试及全量类型/静态复查再次通过。关闭cacheprovider时原cache_dir产生配置警告，如实保留。详见 docs/agents/handoffs/p1-a-review.md 与 p1-a.md。
- 总设计师运行模型示例：UTC+8的08:00时间轴，第2槽为00:10 UTC，转回槽号2；技能需求启用needs_person，空人员日历为无阻塞。这仅验证模型与时间轴，不等于V7或排程已实现。

- P1-PLAN：p1_review_terra 独立档案前置 PASS，见 docs/agents/handoffs/p1-review.md；该结论不代表尚未交付的 OSS/契约提案已验收。总设计师再次完整运行 check.py：33 passed、1 skipped in 8.03s（符号链接权限），布局/导入/来源/ruff/mypy 全通过。
- OSS-1：p1_review_terra 对官方固定版本、树、许可、PyPI 和 PyJobShop 日历语义独立复核；唯一 R1 为 Hypothesis 未来 G4 前置，作者补齐后定向复审 ACCEPT。审查者实测33 passed、1 skipped（cacheprovider关闭后另有cache_dir配置警告），布局/导入/来源/ruff/mypy PASS。报告保留首次 REWORK 与复审历史。
- P1-0：首轮5项 REWORK 涉人员边界、时间接口、卡片范围/门禁、JSON示例、RUNNING候选判定；作者逐项补齐，第二轮仅剩文档本地检查点流程措辞，修复后最终文档工程 G3 ACCEPT。21模型/2别名、引用、3份JSON与旧必填字段/槽范围通过独立核对。治理33 passed、1 skipped，其他检查通过，仍非业务验收。审查与交接见 docs/agents/handoffs/p1-review.md / p1-contract.md。

- 续作前由总设计师执行 `uv run --python 3.11 --group dev python tools/check.py`：来源全文及14批 PASS；33 passed、1 skipped in 7.68s；ruff check/format PASS；mypy 4 source files PASS。唯一跳过为本机不能创建符号链接，代码边界已审查，未宣称动态验证该项。
- SOURCE G3：review_terra 定向复核 ACCEPT；其单独来源测试10 passed、1 skipped，全文及14批校验退出0。索引的三份原文均为 `i/lf w/lf attr/-text`。
- 本地 checkpoint 主题：`chore(checkpoint): preserve verified sources and agent resume state`。保存 SOURCE、R1、完整 Claude 续作计划和交接，R2 尚未完成；这不是全部业务阶段完成或远端同步声明。

- Claude 实际计划、审查调整、派发提示词 v001 及原文预期哈希见 [审查记录](../work-packages/p0-claude-review.md)。其与逐字原文的区别已明确，不伪造缺失原文。
- 总设计师执行 `uv run --python 3.11 --group dev python tools/check.py`：Layout PASS、Imports PASS、23 passed in 7.50s、ruff check/format PASS、mypy 3 source files PASS。
- 文档内部链接核对：50 条通过；AGENTS.md 73 行。未实现或测试 P1–P8 业务。
- P0-C 独立审查发现 TOML 例外未生效，专项返工为配置驱动，添加有效负例后复审 ACCEPT。
- P0-B 独立审查发现计划/提示词 G1 前置循环，总设计师修复为先读 G0、输出后 G1，复审 ACCEPT。
- 已检查待入库清单：仅治理源码、配置、锁文件、规范与角色文档；不包含 .venv、运行缓存、密钥或原始私人数据。

## 更新责任

单一写入者为 Codex 总设计师。专项本次创建初稿后交总设计师接管，后续专项不直接修改本文件。工作包验收的同次提交更新进度，Git 回执可在下一次更新记入；范围/阻塞变化也应及时记录，不能隐瞒到验收后。状态仅使用 TODO / IN-PROGRESS / IN-REVIEW / ACCEPTED / BLOCKED。

工程验收通过、同步待执行时保持 IN-REVIEW；远端同步成功且 SHA 一致后才能 ACCEPTED。哈希不自引用，当前交付以提交主题/工作包 ID 查询，下一次进度更新记录上一交付真实 SHA。变更清单见根 CHANGELOG.md，证据输出与临时产物按文件存储规范处理。
