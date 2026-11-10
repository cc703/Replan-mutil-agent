# 项目进度

更新日期：2026-11-10（Asia/Shanghai）。用户已重新授权继续开发并强调简单完整、目录清晰、代码可读；当前P1-B-R1最终G3 ACCEPT且G5已完成，唯一结构返工已闭环，提交ead0c62已推送核验。原P1-B已ACCEPTED，162 passed/1既有系统skip；799ea56已同步。P1整体尚未完成。

当前授权：用户已恢复开发，覆盖上一轮“完成后暂停”；Claude无额度即停止条件保留。先整理523行单函数与1184行测试，再推进C1产物存储和C2实例生成，各包先有Claude计划与G1，完成后检查/审查/同步。

## 最新同步回执（P1-B-R1，2026-11-10）

ead0c62087e933748a824426f32c37676c4d230b（refactor(core): split validator into readable rule modules）已由cc703普通push至codex/p0-governance，ls-remote与本地HEAD一致，工作区干净。原记录中的P1-B暂停已被用户恢复开发覆盖。后续仍原顺序先C1存储，再C2生成；当前未批准阶段调整。163收集ID由总设计师实际复核：前后各163，缺失/额外/重复均0；完整check162 passed/1原skip，30文件ruff/mypy通过。

## 上一轮交付与停止回执（2026-11-10）

- P1-B正式提交：1255113bb22b87ffc6c51a3d8de0ab18cc5774f3（feat(core): add independent schedule validation）。普通push至origin/codex/p0-governance成功，ls-remote与本地HEAD逐字一致。main仍40cdafd47c66d3dd075d16a81d004eee088b97ab，无覆盖或强推。
- 总设计师最终完整检查162 passed/1既有skip，ruff/format/mypy15文件、layout/import/source PASS；14文件2447行新增/28行删除，显式暂存已审查清单，密钥常见模式未命中，未含环境/缓存/临时捕获。原Claude70/72捕获保护区与前一HEAD逐段一致。
- 本轮已完成并按用户要求停止。P1剩余实例生成与ArtifactStore，P2–P8仍TODO；恢复须用户新指令与下一包Claude完整计划，不自动继续。
- 本回执是后续进度提交，引用已实际同步的P1-B SHA，不自引用当前回执提交。

## GitHub 恢复同步与目录复核（2026-11-10）

- 新授权覆盖下文历史“用户暂缓/不上传”记录；实际新回执在本节及表内记录。
- GitHub连接账号核验为cc703；本地作者为chm，origin为cc703/Replan-mutil-agent。用户完成设备登录后，Git凭证通过GitHub /user核验为cc703；未使用其他账号。
- fetch发现远端main为40cdafd47c66d3dd075d16a81d004eee088b97ab（独立最小演示，包含根main.py等5文件），不覆盖、不合并其内容到已审查集成树。推送现有codex/p0-governance并保留其完整13个历史提交。
- 已阅读用户提供的lingxyz目录规范，参考映射记录在file-storage-standard.md；现有源码/测试/文档/产物职责保持既定布局，无批量搬迁或预建占位目录。
- 实测完整检查：62 passed、1 skipped（系统符号链接权限）；layout/import/source/ruff/format/mypy全部通过。Git跟踪102个文件，常见凭证与私钥模式未命中；未将忽略的环境、缓存或临时捕获纳入提交。
- 当前同步回执：d37f2d6a4634334fa08ca4d738908247e2b3257e 已普通推送至codex/p0-governance，ls-remote与本地HEAD一致；远端main仍为40cdafd47c66d3dd075d16a81d004eee088b97ab。完整历史保留，无强推。
- Claude原会话已正常回复Δ-B2，确定性穷举替代随机取样，不新增依赖；P1-B G1 PASS，已派发源码实施，尚未G2/G3验收。

## 当前工作包

| ID | 名称 | 负责专项 | 分支 | 状态 | 门禁 | 工程验收 | 远端同步 | 验收日期 | 提交证据 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P0-A | 治理与规范 | governance | codex/p0-governance | ACCEPTED | G1/G2/G3 通过；G5 PASS | 总设计师与独立审查通过 | 已同步d37f2d6，ls-remote核验 | 2026-11-09 | 610ab30（本地已提交） |
| P0-B | 协作机制 | collaboration_docs | codex/p0-governance | ACCEPTED | G1/G2/G3 通过；G5 PASS | 独立审查发现循环门槛，修复后 ACCEPT | 已同步d37f2d6，ls-remote核验 | 2026-11-09 | b9d94cff318ad1ef89394214eb2d9f132d12e7bd |
| P0-C | 机器门禁 | machine_gates | codex/p0-governance | ACCEPTED | G1/G2/G3 通过；G5 PASS | 配置驱动缺口修复后独立复审 ACCEPT | 已同步d37f2d6，ls-remote核验 | 2026-11-09 | 4024077b3f9b4659ba82d5cd55c08bbe25059377 |
| SOURCE | 原始设计与 Claude 原文导入 | source_terra | codex/p0-governance | ACCEPTED | G1/G2/G3 通过；G5 PASS | review_terra 修复后复审 ACCEPT | 已同步d37f2d6，ls-remote核验 | 2026-11-09 | 5dbcdee |
| AGENT-RESUME-R1 | 模型策略、角色索引及恢复 | resume_terra | codex/p0-governance | ACCEPTED | G1/G2/G3 通过 ；G5 PASS | 独立 review_terra ACCEPT | 已同步d37f2d6，ls-remote核验 | 2026-11-09 | 5dbcdee |
| AGENT-RESUME-R2 | 提示词库及 P1 开工设计 | resume_terra | codex/p0-governance | ACCEPTED | G1/G2/G3 通过；G5 PASS | review_terra ACCEPT，7份摘录及21类/2别名覆盖已核对 | 已同步d37f2d6，ls-remote核验 | 2026-11-09 | 1dd1b3e |
| P1-PLAN | Claude 续作计划与实际派发归档 | 总设计师 | codex/p0-governance | ACCEPTED | G1 PASS；G5 PASS | 四份提示词payload/行范围/捕获哈希一致 | 已同步d37f2d6，ls-remote核验 | 2026-11-09 | 8a5914d |
| OSS-1 | 类似开源项目与 P1 依赖核实 | p1_oss_terra | codex/p0-governance | ACCEPTED | G0/G1/G2/G3 PASS；G5 PASS | R1修复后独立工程 ACCEPT；仅参考，不安装/改锁 | 已同步d37f2d6，ls-remote核验 | 2026-11-09 | f145a1a |
| P1-0 | 人员资源与契约缺口提案 | p1_contract_terra | codex/p0-governance | ACCEPTED | G1/G2/G3 PASS；G5 PASS | 已审查推荐按用户新授权落实 | 已同步d37f2d6，ls-remote核验 | 2026-11-09 | 452b2be；授权更新见 ADR 0006 |
| P1-A | 全数据模型与 TimeAxis 源码 | p1a_code_terra | codex/p0-governance | ACCEPTED | G0/G1/G2/G3 PASS；G5 PASS | 独立ACCEPT，62 passed/1 skipped，全部检查通过 | 已同步d37f2d6，ls-remote核验 | 2026-11-09 | ac0ba9f |
| P1-B | V1–V11 独立业务校验器 | p1b_code_terra / p1b_tests_terra / p1b_review_terra | codex/p0-governance | ACCEPTED | G0/G1/G2/G3/G5 PASS；G4工程委托 | 独立ACCEPT，162 passed/1 skipped；61reason，5829穷举例 | 已推送1255113并核验 | 2026-11-10 | 1255113bb22b87ffc6c51a3d8de0ab18cc5774f3 |
| P1-B-R1 | 校验器可读性重构（行为不变） | p1br1_code_terra | codex/p0-governance | ACCEPTED | G0/G1/G2/G3/G5 PASS | 6044次差分与35独立边界一致，162 passed/1 skip | 已推送ead0c62并核验 | 2026-11-10 | ead0c62087e933748a824426f32c37676c4d230b |

分支为共享集成分支，不表示每个专项都有独立工作树。验收、检查、提交及远端 SHA 必须由总设计师按实际执行结果补记。

## 后续阶段

| 阶段 | 目标 | 状态 |
| --- | --- | --- |
| P1 | 数据契约、校验与产出物基础设施 | IN-PROGRESS（模型/TimeAxis/校验器已工程验收；实例生成与ArtifactStore待实现） |
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

2026-11-10最新覆盖：用户已恢复开发，上一轮暂停不是当前阻塞。Claude消息76已正常完整生成，P1-B-R1 G1 PASS。保持简单可读及原行为，新旧差分验证必须真实执行；发现旧缺陷另报，不混入本次重构。

2026-11-10覆盖说明：下文额度耗尽及GitHub暂缓为历史检查点；当前Claude已正常回复、P1-B G1 PASS，GitHub已使用cc703推送核验。B1/双profile延期与其余架构约束仍有效。

- 用户本轮明确：Claude没有额度就停止。P1-B消息70与72已完整取回，随后浏览器显示“You hit your 5-hour message limit”；因此停止后续复核与实施，仅保存本地检查点。消息72补齐上下文、DONE执行证据与RUNNING容量去重，尚未通过完整G1或派发专项。页面显示8:40 PM恢复，不设自动恢复，不升级；GitHub仍暂缓。

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

- P1-B-R1最终G3 ACCEPT：纯区间算法提取返工已关闭；入口523→67行、validate函数507→46行；六实现模块最大execution190行，resources179、intervals105，其余不超过135。各源函数<=80，62行的证据检查按完整决策流程保留并说明。原34测试函数/参数化与163收集ID不减不重；61reason/5829oracle保留。root最终独立6042报告+2异常差分一致，reviewer另35边界一致；完整check162 passed/1既有skip与全部静态/来源/布局通过。未变业务规则、新依赖为0。

- P1-B-R1 G3首轮REWORK：6044次完整报告/异常差分与35个额外边界均一致，162 passed/1原skip及全check通过；唯一结构发现为容量、日历与RUNNING扫描仍内嵌resources，未完全落实纯intervals职责。原专项按同一清单最小提取，不改行为，修复后需差分与定向复审，未提前验收或同步。

- P1-B最终G2/G3：六类验证上下文、独立V1–V11与61reason、人工mini、两个测试文件已交付。独立reviewer ACCEPT，完整pytest162 passed、1原符号链接权限skip；关闭cacheprovider时另有既有cache_dir警告。layout/import/source/ruff/format/mypy（15文件）全部PASS。2049重叠+3780容量=5829确定性实例，12种需求/容量组合，独立暴力oracle核对参与集合/组件/输出上界/最大溢出段。源码/测试/审查均Terra/high/fork none，完整派发和交接已归档。原模型/轴/依赖/检查入口及来源未变，没有复制开源代码或新增依赖；仅参考既有OR-Tools/PyJobShop问题分解。

- 2026-11-10 P1-B中间态：作者已写两个源码、mini与README，测试拆给Terra/high独占两个测试文件，独立G3预审已启动。总设计师内存探针：读取mini.json，手工makespan10计划通过；改C为3–9检出V2[A,C]；改B为3–7检出V3[A,B]（同时V2[B,D]）。这不是求解最优或完整验收。穷举与完整错误矩阵仍在编写，不能将阶段性17passed当G2/G3。

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
