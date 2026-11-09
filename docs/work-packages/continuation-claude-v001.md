# 下一步：SOURCE 与 AGENT-RESUME 的计划、提示词，以及备用传递

以下为提议，我没有修改你的本地仓库。模型配置"GPT-6.1 Terra、推理 high"按你的指示写入提示词，我无法核实该模型是否可用。

## 1. 执行计划

| 步骤 | 内容 | 执行者 |
|---|---|---|
| T1 | 备用传递：三份原文按 ≤200 行分批以代码块逐字给出，每批附字节数与 SHA256 | 我（外部 Claude） |
| S | WP-S SOURCE：重建原文、哈希核验、勘误独立记录 | 专项 Agent |
| R1 | WP-R AGENT-RESUME 第一阶段：角色索引、模型策略、恢复清单、批注（与 S 并行，互斥写入） | 专项 Agent |
| R2 | WP-R 第二阶段：提示词库、交接记录、P1 开工准备设计（**S 通过 G3 后才开始**） | 同一专项 Agent |
| G3/G5 | 总设计师审查，统一 git 提交（本地，不上传） | 总设计师 |

并行数为 2，未用满上限 3。可选加一个**只读**的独立复核 Agent，只运行校验并核对哈希，不写文件。

**对范围的两个假设**：

1. "三文件原文"我按你上次收到的三份理解：v2、开发规格 v1.1、`p0_claude_plan_v001`。旧版 v1（`毕业设计_项目设计文档.md`）**不导入**，只在 MANIFEST 里记录其哈希（`f82d9766…9a4e`）。
2. 原文入库为只读来源 `docs/source/*.original.md`，**不覆盖**任何已存在的 `docs/design_v2.md` 或 `docs/codex_spec.md`，也不产生 v1.2。

## 2. 公共前言增量（附在 P0 公共前言之后，冲突时以本增量为准）

````text
# 公共前言增量 v002

运行配置：模型 GPT-6.1 Terra，推理 high（用户指定，由总设计师在派发界面设置）。
交接单必须写明实际使用的模型与推理档；无法确认则写"未能确认"，不得猜测。

新增规则
1. 不得静默升级规格：不产生 v1.2，不改写 docs/design_v2.md、docs/codex_spec.md 及 docs/source 下的原文。
   发现的错误或冲突一律记录到勘误或讨论文件，状态词只用 OPEN / DEFERRED-BY-USER / RESOLVED。
2. 用户已决定"B1 外移"与"求解器双 profile"两条建议暂不改；只做批注，状态为 DEFERRED-BY-USER，不得改动原契约。
3. 环境为 Windows：所有命令用 python 直接入口，不依赖 make。
4. GitHub 暂不上传：不登录、不 push、不配置远端凭据。Git 账号标识 cc703，作者标识 chm；
   文件中不得出现邮箱、真实姓名或任何密钥。
5. 不创建 src/ apps/ experiments/ 目录，不写任何 P1 及以后的业务代码，不冻结数据契约。
6. 不执行 git commit / push，不改 git 配置；提交由总设计师统一进行。
7. 现有治理测试（23 项）、ruff、mypy 必须保持通过；任何触及它们的改动先报告。
8. 遇到必须裁决的问题立即停手，按裁决请求单格式上报。
````

## 3. WP-S：SOURCE（原设计逐字取回与哈希核验）

**目标**：把三份原文逐字入库为只读来源，用哈希核验，勘误独立记录，不改任何规格。

| 项 | 内容 |
|---|---|
| **允许写入** | `docs/source/design_v2.original.md`、`docs/source/codex_spec_v1.1.original.md`、`docs/source/p0_claude_plan_v001.original.md`、`docs/source/manifest.json`、`docs/source/MANIFEST.md`、`docs/source/ERRATA.md`、`docs/source/README.md`、`tools/verify_source.py`、`tests/governance/test_verify_source.py`、`.gitattributes`（**仅追加**字节保护规则） |
| **输入** | 本消息的批次清单与原文批次（经总设计师转交）；勘误种子清单；仓库当前状态 |
| **依赖** | 上游为 T1 传递完成。三份文件可分别 BLOCKED，互不牵连 |
| **阻塞** | 某文件批次未收齐或哈希不符，该文件标 BLOCKED，不入库 |

````text
[附上 P0 公共前言与"公共前言增量 v002"]

# 角色
你是 SOURCE 专项 Agent。只负责原文逐字入库、哈希核验和勘误记录，不解释、不修改、不升级任何规格内容。

# 目标
在 docs/source/ 建立三份只读原文及其哈希清单，并提供可重复运行的核验工具。

# 允许写入
docs/source/design_v2.original.md
docs/source/codex_spec_v1.1.original.md
docs/source/p0_claude_plan_v001.original.md
docs/source/manifest.json   docs/source/MANIFEST.md   docs/source/ERRATA.md   docs/source/README.md
tools/verify_source.py   tests/governance/test_verify_source.py
.gitattributes（只追加一行字节保护规则，不改动已有行）
其余一律只读。

# 输入
- 三份原文，来自对话代码块批次（总设计师转交），或总设计师直接提供的原文件。
- 期望值（来自外部 Claude 的核对）：
  codex_spec_v1.1  645 行  33962 字节  sha256 59e84a27ed5055eca83f23e73b8d89cdfee6a05ff27b74c64d753c8355cb651c
  design_v2        1397 行 74171 字节  sha256 f5589dd322b8f9caf45221482f952b9fd3ecba3f69a88919e4185f0177dd6677
  p0_claude_plan   548 行  34844 字节  sha256 82d49292f1342dce3c5348b5176d7cf029fe6fd10ddf61d884276ba8e61286f6
  旧版 v1（只记录，不导入）738 行 45627 字节 sha256 f82d9766fc84357e739310727ee086025f989294408aebcaace5f66431299a4e
- 各文件的分批行范围与批次 SHA256（见总设计师提供的批次清单）。
- 批次定义：第 N 批 = 原文第 a 至 b 行，每行以 LF 结尾；批次内容即这些行的字节串。
- 原文编码：UTF-8，无 BOM，LF 换行，无制表符，无行尾空格。

# 任务
1. 检查仓库：git status --short；列出 docs/ 现状。若 docs/design_v2.md 或 docs/codex_spec.md 已存在，
   计算其哈希并与期望值比对，把比对结果写入 MANIFEST，不修改这些文件。
2. 重建原文：把每个批次文本写入 artifacts/tmp/source_batches/<文件>/<批次号>.txt
   （Python：write_text(..., encoding="utf-8", newline="\n")，确保以 LF 结尾）。
   逐批核验字节数与 SHA256；全部通过才合并为完整文件并核验全文。
   任一批次不符：该文件 BLOCKED，不入库，在交接单列出不符批次与实际哈希。
3. 入库：通过核验的文件写入 docs/source/*.original.md，字节级与期望一致。
4. .gitattributes：先用 git check-attr -a 与 git ls-files --eol 检查现有规则是否会改变这些文件的换行；
   若会，追加 docs/source/*.original.md -text（或等价的字节保护规则）；若不会，也要追加一行并说明理由。
5. manifest.json（机器可读，核验工具的唯一依据）：
   每个文件含 原始中文文件名、入库路径、行数、字节数、sha256、批次表（行范围、字节数、sha256）、
   编码与换行说明、来源渠道、核验时间（ISO 8601）。
6. MANIFEST.md（人类可读镜像，必须与 manifest.json 一致）：表格呈现上述内容，
   并包含"与现有 docs/design_v2.md、docs/codex_spec.md 的比对结果"。
7. ERRATA.md：勘误独立记录，不改原文。每条含：编号 E-xxx、文件、行号、原文摘录（不超过一行，须与原文一致）、
   问题描述、类型（冲突/笔误/过时）、建议修正（仅文字描述）、状态、备注。
   行号必须由你在入库后的原文中定位并核对，不得凭记忆。种子清单（主题已确定，行号由你定位）：
   E-001 小写文件名规则与 AGENTS.md、README.md、Makefile、CHANGELOG.md、Flyway 迁移名冲突
   E-002 "根目录不得新增任何文件或目录"与本地 .git/.venv/.env/缓存冲突
   E-003 num_workers=8 与"完全确定性/可复现"冲突。状态 DEFERRED-BY-USER（用户暂不改，求解器双 profile 建议留待讨论）
   E-004 b1_llm 位于 scheduler_core/baselines 与"scheduler_core 不依赖大模型"冲突。状态 DEFERRED-BY-USER（B1 外移暂不改）
   E-005 "草稿 png，入库版本用 svg 或 pdf"未规定转换方式，易被改扩展名冒充
   E-006 Flyway 迁移路径写作 apps/backend/db/migration，与 Spring Boot 默认位置不一致
   E-007 "源码目录无 png/svg、文件 ≤1MB"与前端资源、锁文件冲突
   E-008 AGENTS.md 中 mypy src 等命令在 src/ 尚不存在的阶段会失败
   以上若在原文中找不到对应位置，状态写 OPEN 并注明"未定位"；另有新发现的问题按同样格式追加，编号顺延。
8. tools/verify_source.py：仅用标准库；读取 docs/source/manifest.json，校验三份文件的存在、字节数、行数、
   sha256、批次 sha256、无 BOM、无 CRLF；输出每项结果；全部通过退出码 0，否则非 0；支持 --root 参数。
9. tests/governance/test_verify_source.py：在 tmp_path 构造小仓库，覆盖：通过；篡改一个字节失败；缺文件失败；
   出现 CRLF 失败；批次哈希不符失败。测试不得在仓库留下文件。
10. docs/source/README.md：说明目录用途、只读约定、如何核验、勘误流程；写明"原文不得修改，修订走 ERRATA 与新版本"。

# 验收
- 三份入库文件的行数、字节数、sha256 与期望完全一致；python tools/verify_source.py 退出码 0。
- 篡改任一字节，核验工具退出码非 0（有测试覆盖）。
- git ls-files --eol 显示这三份文件 i/lf w/lf，无换行转换。
- docs/source 之外除 .gitattributes 追加行、tools/verify_source.py、tests/governance/test_verify_source.py 外无其他写入；
  已存在的 docs/design_v2.md、docs/codex_spec.md 未被修改。
- ERRATA 每条摘录与原文对应行逐字一致（用脚本核对并在交接单给出结果）。
- 23 项治理测试加新增测试全部通过；ruff、mypy、python tools/check_repo_layout.py 均通过。
- 没有出现 v1.2，没有规格内容被改写。

# 交接
按公共前言 H 格式。额外列出：每个批次的核验结果表；与现有 docs 副本的比对结果；ERRATA 条目清单（编号、状态）；
所使用的模型与推理档。
````

## 4. WP-R：AGENT-RESUME（持久角色索引 + P1 开工准备）

**目标**：让专项智能体的定义、提示词、模型策略、交接状态和恢复清单可跨会话恢复；并基于原始 v2 与规格写出 P1 开工准备设计。

| 项 | 内容 |
|---|---|
| **允许写入** | `docs/agents/registry.md`、`docs/agents/model-policy.md`、`docs/agents/RESUME.md`、`docs/agents/README.md`（**仅追加**指向新文件的链接）、`docs/agents/prompts/*.v001.md`、`docs/agents/handoffs/*.md`、`docs/work-packages/source.md`、`docs/work-packages/agent-resume.md`、`docs/planning/open-discussions.md`、`docs/planning/p1-readiness.md` |
| **不得写入** | `docs/progress/PROGRESS.md`（单一写入者是总设计师，你在交接单里给出"建议更新内容"）、`docs/source/**`、契约相关文件 |
| **输入** | P0 已有的 `docs/agents/*.md`、`docs/work-packages/*`、`docs/progress/PROGRESS.md`、git 历史；R2 阶段另需 `docs/source/*.original.md`；SOURCE 与本包提示词全文（总设计师提供） |
| **依赖** | R1 无依赖；**R2 依赖 SOURCE 通过 G3** |
| **阻塞** | v2 或 p0 plan 批次未收齐；P0 交接原始记录若不在仓库中，对应条目标 NOT-RECORDED |

````text
[附上 P0 公共前言与"公共前言增量 v002"]

# 角色
你是 AGENT-RESUME 专项 Agent。职责：把协作体系持久化、可恢复，并为 P1 开工做设计准备。不写业务代码，不冻结或修改数据契约。

# 目标
R1：建立角色索引、模型策略、恢复清单、工作包卡片、讨论批注。
R2：建立提示词库与交接记录，并写出基于原始 v2 与规格的 P1 开工准备设计。

# 允许写入
docs/agents/registry.md  docs/agents/model-policy.md  docs/agents/RESUME.md
docs/agents/README.md（只追加链接，不改已有内容）
docs/agents/prompts/*.v001.md   docs/agents/handoffs/*.md
docs/work-packages/source.md    docs/work-packages/agent-resume.md
docs/planning/open-discussions.md   docs/planning/p1-readiness.md
其余一律只读。不得写 docs/progress/PROGRESS.md。

# 输入
R1：现有 docs/agents/*.md、docs/work-packages/_template.md 与 P0.md、docs/progress/PROGRESS.md、git log。
R2：docs/source/design_v2.original.md、docs/source/codex_spec_v1.1.original.md、docs/source/p0_claude_plan_v001.original.md、
    docs/source/ERRATA.md；总设计师提供的 SOURCE 与本包提示词全文；P0 交接记录（若在仓库中）。
事实（来自用户与总设计师的报告，未经你核实时必须标注"报告，未独立核实"）：
P0 A/B/C 已完成；治理测试 23 项加 ruff/mypy 通过并经审查；已本地提交；GitHub 暂不上传；账号 cc703，作者 chm。

# R1 任务（立即开始）
1. registry.md：角色索引表。列：id、角色、类型（Codex 专项子智能体 / 外部 Claude / 总设计师）、定义文件、
   提示词文件与版本、模型、允许写入范围、当前状态、最近交接、恢复入口。
   必须覆盖：planner 与 prompt-engineer（类型"外部 Claude"）、reviewer（总设计师）、
   storage-steward、oss-scout，P0 的 wp-a、wp-b、wp-c，以及 source、agent-resume。
   仓库身份只写 账号 cc703、作者 chm，不写邮箱。
2. model-policy.md：所有 Codex 专项子智能体：GPT-6.1 Terra，推理 high（用户指定，本文不核实可用性）。
   写明适用范围、例外须用户裁决、派发时在提示词头部注明、交接单记录实际模型与推理档、
   模型不可用时停止并上报不自动降级、外部 Claude 角色不适用本策略（仅登记）、策略变更流程。
3. RESUME.md：恢复清单。按顺序：读哪些文件；运行哪些检查命令并如何判读
   （git status --short；git log --oneline -n 10；python tools/check_repo_layout.py；
   python -m pytest tests/governance -q；python tools/verify_source.py，标注"SOURCE 合入后可用"）；
   如何判断各工作包状态；如何重新派发（提示词路径）；待裁决项在哪里；禁止事项；
   外部 Claude 恢复时需要提供的材料清单（三份原文与哈希、批次清单）。
   每条命令你必须实际运行并在交接单记录真实输出；未运行的不得写成"已验证"。
4. work-packages/source.md、agent-resume.md：按现有模板填写，含文件清单、输入、验收、依赖、阻塞。
5. open-discussions.md：议题格式 编号、背景、选项、影响、当前状态、讨论前置条件、不处理的后果。
   D-001 B1 外移（DEFERRED-BY-USER）；D-002 求解器双 profile（DEFERRED-BY-USER）。
   另列已在 P0 工具层采纳、但规格原文未改的项：命名例外、git 视角检查、原生图表格式、Windows 直接 python 入口，
   状态写 ADOPTED-IN-P0-TOOLING，并注明"规格原文未升级"。不得把任何一项写成已修改规格。
6. README.md 追加链接指向 registry、model-policy、RESUME、prompts、handoffs。

# R2 任务（仅在 SOURCE 通过 G3 后开始；开始前先运行 python tools/verify_source.py，不通过则 BLOCKED）
7. prompts/：把 P0 的公共前言、WP-A、WP-B、WP-C 提示词，从 docs/source/p0_claude_plan_v001.original.md 第 4、5 节逐字摘出，
   存为 p0-common.v001.md、p0-wp-a.v001.md、p0-wp-b.v001.md、p0-wp-c.v001.md；
   另存 common-delta.v002.md、source.v001.md、agent-resume.v001.md（由总设计师提供全文，逐字保存）。
   每个文件头部写：来源文件、行范围、来源 sha256；其余内容不得改动。
8. handoffs/：为 P0 三包与 SOURCE 各建一条交接记录（状态、变更文件、验证、模型、未决问题）。
   只记录可证据化的内容；无证据写 NOT-RECORDED，不得补写。
9. p1-readiness.md：基于原始 v2 与规格写 P1 开工准备设计。必须包含：
   a. P1 目标与边界：以规格第 6 节 P1 行为准；注明 P0 已交付的布局检查器与依赖边界检查器，P1 不重复。
   b. 输入文档映射：每项引用"原文文件:行号"，行号须对照 docs/source 原文核对。
   c. 契约评审清单：逐个列出规格第 3 节 models.py 中的模型及待确认点，表述为"问题"，
      不得改写契约、不得给出冻结版本。与 ERRATA 相关的条目只引用编号。
   d. 候选子工作包：P1-0 契约评审（用户裁决 G4）→ P1-A 契约实现 → P1-B 校验器 与 P1-C 生成器及产出物写入工具；
      各给文件清单、依赖、验收（对应规格 5.1 与 5.4 中属于 P1 的测试）、并行性说明（最多 3 个并行，写入互斥）。
   e. 开工前置：Windows 环境检查（Python 3.11、依赖安装方式）、依赖登记（pydantic、numpy、pytest、hypothesis 等
      需经 oss-scout 核对许可证与版本，不得凭记忆）、src/ 首次创建对布局检查与依赖边界检查的影响。
   f. 风险与需用户裁决的问题清单。
   g. 明确"不做"：不创建 src/，不写业务代码，不冻结契约。

# 验收
R1：
- 所有 R1 文件存在且非空；registry 覆盖列出的全部角色且字段齐全；
- model-policy 如实记录 GPT-6.1 Terra / high 为用户指定、未核实；
- RESUME 中的命令均已实际运行且交接单有真实输出；
- open-discussions 中 D-001、D-002 状态恰为 DEFERRED-BY-USER，且 git diff 显示规格与 docs/source 无改动；
- 现有治理测试、ruff、mypy、布局检查通过。
R2：
- 提示词库文件与来源逐字一致（附比对哈希）；
- p1-readiness 中每个引用都有"文件:行号"且已核对；无任何契约改写；未创建 src/；
- 通过 python tools/verify_source.py。

# 交接
按公共前言 H 格式。额外列出：registry 摘要；各命令的实际输出；对 PROGRESS.md 的建议更新内容（不要自己改）；
所使用的模型与推理档。
````

## 5. 批次清单与校验方法

### 5.1 三份原文（已核对：UTF-8、无 BOM、LF、无制表符、无行尾空格）

| 文件 | 批 | 行范围 | 字节 | SHA256 |
|---|---|---|---|---|
| **开发规格 v1.1**（全文 645 行 / 33962 字节） | | | | `59e84a27ed5055eca83f23e73b8d89cdfee6a05ff27b74c64d753c8355cb651c` |
| | 01 | 1–200 | 11609 | `f787f8f3b351938fa570abbc902153745d18546a5ea14e6880b16e48dbddbb60` |
| | 02 | 201–400 | 6984 | `7a2116a58455008ba266784194b83978a09887bdf87e4c2d4ec0e936b63e75cd` |
| | 03 | 401–600 | 11711 | `5517b20d04f7556dd6a745995cb23650d63d800ba467a581aa98acba18bf372c` |
| | 04 | 601–645 | 3658 | `5db6b2eb635809f2a5161867b8d4db61be61e6cf7e669638ec6f18e8b95b7e12` |
| **完整设计框架 v2**（全文 1397 行 / 74171 字节） | | | | `f5589dd322b8f9caf45221482f952b9fd3ecba3f69a88919e4185f0177dd6677` |
| | 01 | 1–200 | 12290 | `f4f556ccd28fb2913d08cca34f25bdcf3e3793f43318fcd0735a67d812da4e58` |
| | 02 | 201–400 | 11329 | `0e55b37e5fb2a9633c9d5c25401c961997198c54fa4bd64de6e2302ced7065fe` |
| | 03 | 401–600 | 8969 | `be2bfd391dd3ac4454737ae2f93a28d47587981f2c498409ec819cee6cc12469` |
| | 04 | 601–800 | 9195 | `bff0a1b6858972fe522aa27afe259c68c9dbfdbc4a59075b1b6b1a51c761083f` |
| | 05 | 801–1000 | 10415 | `1243de356f903a032712e7c4654c45da352ce658a53419090d93385721f73d8c` |
| | 06 | 1001–1200 | 9630 | `dc1734932c8fb1cd1bde71242d7271d0850eb858a835a58b7513bfaf4e5a2b22` |
| | 07 | 1201–1397 | 12343 | `31a4fc0acbb316aec4eb89a5e44f029b5f811d7869711d9c026610a23c1561d5` |
| **p0_claude_plan_v001**（全文 548 行 / 34844 字节） | | | | `82d49292f1342dce3c5348b5176d7cf029fe6fd10ddf61d884276ba8e61286f6` |
| | 01 | 1–200 | 12406 | `8ebb0a43d50a26b822496a7d12646dd60bd736e1c5f6d3da566a056381c48010` |
| | 02 | 201–400 | 12610 | `6bcc75d80dc41d28cfa7c75b8c9b4d33d410a8a5708e065facfe526943226ac7` |
| | 03 | 401–548 | 9828 | `96d56d1dfb5f5fd9467ac90f44c92261b64794733318eef5be8f52ee435dbbe9` |

批次哈希的计算方式：第 a 到 b 行，每行以 LF 结尾，拼成的字节串的 SHA256。

### 5.2 传递规则

- 每批的代码块内**只有原文**，没有行号、没有注释。开发规格与 v2 用 5 个反引号作外层围栏，`p0_claude_plan_v001` 用 6 个（因其正文含 4 反引号围栏）。
- 顺序：开发规格 4 批 → v2 7 批 → p0 plan 3 批。每批发完等你回复 `NEXT`。
- 某批校验不符，回复 `RESEND <文件> <批号>`，我会重发；仍失败则改用 ≤100 行的小批次。

### 5.3 接收端的核验（Windows，跨平台 Python）

```python
# artifacts/tmp/verify_batch.py（临时文件，不入库）
import hashlib, pathlib, sys
p = pathlib.Path(sys.argv[1]); expected = sys.argv[2].lower()
b = p.read_bytes()
h = hashlib.sha256(b).hexdigest()
print(len(b), b.count(b"\n"), h)
print("OK" if h == expected else "MISMATCH")
```

写入批次文件时，把从代码块取到的文本 `t` 用下面的方式保存，保证 LF 且以换行结尾：

```python
import pathlib
pathlib.Path(dst).write_text(t if t.endswith("\n") else t + "\n", encoding="utf-8", newline="\n")
```

## 6. 首批原文：`Codex开发规格_v1.md`，第 1 批，第 1–200 行

批次字节数 11609，SHA256 `f787f8f3b351938fa570abbc902153745d18546a5ea14e6880b16e48dbddbb60`。

`````text
# Codex 开发规格包 v1.1
# 面向多约束场景的任务动态调度与重规划 Agent

> 用途：配合《毕业设计_完整设计框架_v2.md》，把设计变成 Codex 可分阶段执行的任务。
> 设计文档回答"做什么、为什么"；本文件回答"接口长什么样、怎么算做完"。
> v1.1 新增：文件与产出物规范（第 2 节）——精简的目录结构、中间产物统一存放、命名与清理规则、仓库卫生检查。

---

## 0. 使用方式（先读）

1. 把第 1 节的内容保存为仓库根目录的 `AGENTS.md`。
2. 把《完整设计框架 v2》放到 `docs/design_v2.md`，把本文件放到 `docs/codex_spec.md`。
3. **一次只给 Codex 一个阶段任务**（第 6 节），做完跑验收测试、你审查、提交，再进入下一阶段。不要一次要求全部完成。
4. 每个阶段开始前，让 Codex 先阅读 `AGENTS.md`、对应设计章节和本文件对应小节，并**先给出计划，经你确认再动手**。
5. 第 7 节记录了已定的技术决策，Codex 不得擅自更改。

> **现实提醒**：即使有这份规格，Codex 也不能一次做完整个系统。算法正确性（尤其重规划和冲突诊断）和前端体验需要你审查与调参。

---

## 1. AGENTS.md（放仓库根目录）

```markdown
# AGENTS.md

## 项目
面向多约束场景的任务动态调度与重规划 Agent（本科毕业设计）。
设计文档：docs/design_v2.md；开发规格：docs/codex_spec.md。

## 核心原则（不可违反）
1. 计划只能由约束求解器（OR-Tools CP-SAT）生成，大模型不得直接输出调度结果。
2. 任何展示给用户或写入正式版本的计划，必须先通过 scheduler_core.validate（独立校验器，不复用 CP-SAT 模型）。
3. scheduler_core 与 simulator 是纯 Python 包：不得依赖数据库、Web 框架或大模型。
4. 改变正式计划的操作必须经过用户确认（L2），改变系统理解的操作（约束/事件）需要确认（L1）。
5. 大模型输出一律视为不可信输入，必须经 Pydantic 校验与语义校验。

## 技术约定
- Python 3.11；类型标注必须完整；使用 pydantic v2。
- 内部时间一律用整数"槽"（slot），通过 TimeAxis 与 datetime 互转；数据库存 UTC，业务时区 Asia/Shanghai。
- 随机性只用 numpy.random.Generator(PCG64(seed))；不同扰动使用独立子流。
- 所有可调参数放 YAML 配置，不写死在代码里。
- 日志用结构化 JSON，带 trace_id。

## 大模型约定
- 服务：DeepSeek API；所有调用经 `src/agent/llm.py` 适配层，其他代码不得直接调用。
- 模型名与参数只从 `src/agent/defaults.yaml` 读取，不得写死；密钥只从环境变量 `DEEPSEEK_API_KEY` 读取。
- 使用前先查阅官方文档确认当前可用的模型 id 与参数，不要凭记忆写。
- 抽取与解释用非思考模式、温度 0；所有输出必须经 Pydantic 校验，不依赖服务端 strict。

## 依赖与 API 使用
- 依赖版本以锁文件为准；新增依赖前先说明理由。
- 使用 OR-Tools、LangGraph 等库的 API 前，先查看**已安装版本**的文档或源码确认签名，不要凭记忆写。
- 遇到不确定的 API，写最小可运行示例验证，再接入主代码。

## 工作方式
- 每次任务开始先给出计划与将创建/修改的文件列表，等待确认。
- 每个模块先写测试再写实现；完成后运行全部测试并报告结果。
- 不修改与当前任务无关的文件；不做未被要求的重构。
- 不确定的设计问题，列出选项和你的推荐，由我决定；不要擅自决定。

## 文件与产出物规则（不可违反）
1. 所有机器生成的中间产物（实例缓存、运行结果、日志、LLM trace、图表草稿、临时文件）只能写入 `artifacts/`，且必须通过 `scheduler_core.io.artifacts.ArtifactStore` 创建路径；禁止在代码里硬编码输出路径，禁止写到仓库根目录或源码目录。
2. 每次运行的目录名为 `<run_id>`，格式 `YYYYMMDD-HHMMSS_<git短哈希>_<标签>`；目录内必须有 `manifest.json`（字段见 docs/codex_spec.md 2.4）。已完成（status=completed）的运行目录视为只读，重跑必须产生新的 run_id。
3. 路径与文件名只用小写 ASCII、数字、下划线、连字符，不含空格和中文；中文只出现在文档内容里。
4. 临时文件放 `artifacts/tmp/`，测试里用 pytest 的 `tmp_path`；任何代码不得依赖 tmp 里的内容。仓库内不保留一次性脚本；确需临时脚本，放 `artifacts/tmp/`，用完即删。可复用的维护脚本放 `tools/` 并写明用途。
5. 入库的"输入类"数据放 `data/`，实验与场景配置放 `experiments/configs/`，入库的"最终结果"放 `docs/results/`（只有经我审核的图表和表格）。其余生成物一律不入库。
6. 不得在仓库里留下未说明的文件：笔记、草稿、截图、.log、.csv、.png 等不能出现在源码目录。每个任务结束时列出"新增/修改/删除文件清单"，并说明每个新增文件的用途。
7. 提示词、评测集一律版本化：`src/agent/prompts/<name>/v001.md`、`data/eval_sets/<name>/v001.jsonl`，不覆盖旧版本，改动产生新版本并写入 CHANGELOG。
8. 不得提交密钥与个人信息：使用 `.env`（不入库）与 `.env.example`；LLM trace 写盘前必须脱敏。
9. 每次提交前运行 `make check`（含仓库布局检查）；未通过不得结束任务。

## 命令
- 安装：`uv sync`（或 pip install -e .[dev]）
- 测试：`pytest -q`
- 类型检查：`mypy src`
- 格式化：`ruff check . && ruff format .`

## 完成的定义（Definition of Done）
- 对应阶段的验收测试全部通过；mypy 和 ruff 无错误。
- 公共函数有 docstring，说明输入输出与约束。
- 新增行为有测试覆盖；README 或 docs 更新了使用方式。
```

---

## 2. 仓库骨架与产出物规范

### 2.1 目录总览（根目录只保留这些）

```
project/
├─ AGENTS.md  README.md  Makefile  pyproject.toml  uv.lock  docker-compose.yml
├─ docs/          文档：设计、规格、决策记录、最终结果
├─ src/           Python 核心代码
│   ├─ scheduler_core/    建模、求解、重规划、校验、基线
│   ├─ simulator/         状态机、事件仿真、适配器
│   └─ agent/             LangGraph、工具、提示词
├─ apps/          可部署应用
│   ├─ backend/           Spring Boot
│   └─ frontend/          Vue 3
├─ experiments/   实验代码与实验配置
├─ data/          入库的输入数据（测试实例、评测集、调研参数）
├─ tests/         测试
├─ tools/         仓库维护工具
└─ artifacts/     机器生成物（不入库，布局见 2.3）
```

隐藏文件仅限 `.gitignore`、`.env.example`。除此之外，根目录不得新增任何文件或目录。

### 2.2 各目录内部结构

| 目录 | 内部结构 |
|---|---|
| `docs/` | `design_v2.md`、`codex_spec.md`；`decisions/`（设计决策，编号命名如 `0001-time-slot.md`）；`results/`（`figures/`、`tables/`、`INDEX.md`，经审核的最终结果） |
| `src/scheduler_core/` | `models.py` `axis.py` `validate.py` `generate.py` `solve_initial.py` `impact.py` `replan.py` `diagnose.py` `relax.py` `pareto.py`；子包 `baselines/`（`b2_full.py` `b3_rule.py` `b1_llm.py`）、`io/`（`artifacts.py` `manifest.py`） |
| `src/simulator/` | `states.py` `events.py` `engine.py` `scenarios.py`；子包 `adapters/`（`base.py` `simulated.py` `manual.py`） |
| `src/agent/` | `graph/` `tools/` `eval/`；`prompts/<name>/v001.md`（版本化）；`defaults.yaml` |
| `apps/backend/` | Spring Boot 工程；数据库迁移 `db/migration/V001__init.sql` |
| `apps/frontend/` | Vue 3 工程 |
| `experiments/` | `run.py` `metrics.py` `stats.py` `plots.py`；`configs/scenarios/`、`configs/experiments/`（如 `E2.yaml`） |
| `data/` | `fixtures/`（测试最小实例）、`eval_sets/<name>/`（`v001.jsonl`、`CHANGELOG.md`）、`survey/`（调研记录）、`benchmarks/`（基准映射说明，不放大文件） |
| `tests/` | `unit/` `property/` `integration/` |
| `tools/` | `check_repo_layout.py` `clean_artifacts.py` `archive_run.py` `make_report.py` |

**三类数据的区别**

| 类别 | 位置 | 是否入库 | 谁写入 |
|---|---|---|---|
| 输入类（人工维护） | `data/`、`experiments/configs/` | 是 | 你与 Codex（需说明） |
| 中间产物（可再生） | `artifacts/` | **否** | 程序，经 `ArtifactStore` |
| 最终结果（经审核） | `docs/results/` | 是 | 只能由 `tools/make_report.py` 从某次运行复制 |

### 2.3 artifacts/ 布局（所有生成物只能放这里）

```
artifacts/
├─ README.md        # 唯一入库的文件
├─ instances/       # 实例缓存：<scale>_u<util>_t<tight>_s<seed>/instance.json
├─ runs/            # 所有运行：<kind>/<name>/<run_id>/
├─ llm_traces/      # <yyyy-mm-dd>/<session_id>.jsonl（已脱敏）
├─ logs/            # <service>/<yyyy-mm-dd>.jsonl
├─ archive/         # 已完成并压缩的运行
└─ tmp/             # 临时文件，可随时清空，任何代码不得依赖
```

`runs/` 下 `kind` 取 `experiment`、`sim`、`agent_eval` 三种。**一次运行的所有输出都放在它自己的目录里**，包括求解器日志，不再另设顶层目录。

**一个运行目录的内部结构**

```
artifacts/runs/experiment/E2_replan_micro/20261110-153000_a1b2c3d_small-light/
├─ manifest.json    # 必须有，见 2.4
├─ config.yaml      # 本次运行实际使用的配置副本
├─ raw.csv          # 逐样本原始结果（方法 × 实例 × 种子）
├─ summary.csv      # 汇总指标（由 raw.csv 生成）
├─ events/          # 事件日志（jsonl），用于回放
├─ plans/           # 各方法产生的计划（json）
├─ figs/            # 图表草稿
└─ logs/            # 运行与求解器日志（jsonl）
```

**命名与格式**

| 项 | 约定 |
|---|---|
| `run_id` | `YYYYMMDD-HHMMSS_<git短哈希>_<标签>`；标签为短小写词，如 `small-light`、`ablate-no-stab` |
| 表格 | CSV（UTF-8，首行表头，时间用 ISO 8601，布尔用 true/false） |
| 日志与事件 | JSON Lines |
| 单个对象 | JSON；配置用 YAML |
| 图表 | 草稿 png；入库版本用 svg 或 pdf |
| 路径与文件名 | 小写 ASCII、数字、`_`、`-`；无空格、无中文 |

### 2.4 manifest.json（每次运行必须生成）

```json
{
  "run_id": "20261110-153000_a1b2c3d_small-light",
  "kind": "experiment",
  "name": "E2_replan_micro",
  "status": "completed",
  "started_at": "2026-11-10T15:30:00+08:00",
  "ended_at":   "2026-11-10T16:12:40+08:00",
  "command": "python -m experiments.run --config experiments/configs/experiments/E2.yaml",
  "git": {"commit": "a1b2c3d...", "dirty": false},
  "config_sha256": "…",
  "seeds": [0, 1, 2],
  "versions": {"python": "3.11.x", "ortools": "x.y.z", "langgraph": "x.y.z"},
  "llm": {"provider": "…", "model": "…", "temperature": 0},
  "inputs": ["artifacts/instances/small_u0.8_t0.5_s0/instance.json"],
  "outputs": ["raw.csv", "summary.csv", "figs/f1_tardiness.png"]
}
```

- `status`：`running`、`completed`、`failed`、`partial`。开始即写 `running`，结束时更新。
- `dirty = true`（工作区有未提交改动）的运行，不得用于 `docs/results/`。

### 2.5 写入规则

1. 所有产出物路径由 `ArtifactStore` 提供：
`````

**第 1 批结束**（开发规格第 1–200 行）。回复 `NEXT` 我发第 2 批（第 201–400 行）。

**请你核对**：第 200 行应为"1. 所有产出物路径由 `ArtifactStore` 提供："；第 1 批文本经 LF 换行保存后应为 11609 字节，SHA256 与上表一致。我在这一轮的写出环节无法自己比对字节，所以逐字无误只能由你的哈希核验来确认，若有不符请回复 `RESEND`。
