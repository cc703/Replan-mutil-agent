<!-- 来源: docs/work-packages/continuation-claude-v001.md:144-223; 来源 SHA256: 1f25a8e433493f28cea45a3555a5438ebf2eb25e0f8024d7646ca9011f32d312; 摘录 SHA256: 00e28088c597db3f151a2bf90025d476820340acf4edb89560e9e82561e344fb; 原文逐字，历史内容须服从现行 AGENTS 与用户裁决。 -->
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
