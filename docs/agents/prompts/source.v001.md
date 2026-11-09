<!-- 来源: docs/work-packages/continuation-claude-v001.md:55-128; 来源 SHA256: 1f25a8e433493f28cea45a3555a5438ebf2eb25e0f8024d7646ca9011f32d312; 摘录 SHA256: 23db0cccf117a00a8265b78e61cae66b15a6e83eb5af87605d028310d324e44b; 原文逐字，历史内容须服从现行 AGENTS 与用户裁决。 -->
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
