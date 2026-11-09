<!-- 来源: docs/source/p0_claude_plan_v001.original.md:424-490; 来源 SHA256: 82d49292f1342dce3c5348b5176d7cf029fe6fd10ddf61d884276ba8e61286f6; 摘录 SHA256: 6b2dc1ba440b6fefb63c881f674e9f2939488e930cd5e3f4b25439ca9ddee0d0; 原文逐字，历史内容须服从现行 AGENTS 与用户裁决。 -->
[附上公共前言]

# 角色
你是"机器门禁 Agent"。职责：把文件存储规范和依赖边界变成可自动运行的检查，并为 P0 提供最小工具配置。

# 目标
实现 tools/layout_rules.toml（规则唯一来源）、仓库布局检查器、依赖边界检查器、治理测试，以及配套配置文件。

# 允许写入
tools/layout_rules.toml  tools/check_repo_layout.py  tools/check_import_boundaries.py
tests/governance/*
.gitignore  .gitattributes  .editorconfig  .pre-commit-config.yaml
Makefile  pyproject.toml  artifacts/README.md
其余一律只读。

# 输入
公共合同 C1–C6；本提示词。

# 任务
1. tools/layout_rules.toml：机器可读规则，分 [root]、[naming]、[forbidden_extensions]、
   [size]、[magic]、[artifacts]、[exceptions] 等段；规则编号 R-xx 与公共合同一致；
   [exceptions] 每条有 path、reason。
2. tools/check_repo_layout.py：
   - 命令行：python tools/check_repo_layout.py [--root PATH] [--format text|json]，违规时退出码非 0
   - 检查对象：git ls-files -co --exclude-standard；被忽略的本地项不参与检查
   - 检查项：根目录白名单；命名规则（分层与例外）；源码目录无生成物；.png/.svg 仅允许目录；
     体积限制与例外；artifacts/ 除 README.md 外不得入库；artifacts/runs 下每个运行目录有合法 manifest.json（含必填字段）；
     文件魔数与扩展名一致（png、pdf、svg）；.gitignore 必须包含合同列出的本地忽略项
   - 输出：每条违规含 规则编号、路径、原因；支持 JSON
   - 不依赖第三方库（只用标准库 + 调用 git）
3. tools/check_import_boundaries.py：
   用标准库 ast 扫描 src/ 下的包（P0 阶段 src/ 不存在时应正常通过），按合同 C4 检查依赖方向；
   规则从脚本内的常量表读取，不硬编码在各处。
4. tests/governance/：用 pytest，在 tmp_path 里 git init 构造小仓库，覆盖至少以下用例：
   a 被忽略的 .venv/.env 不触发违规；
   b 根目录出现 notes.txt → R-root 违规；
   c src/ 下出现 .csv → 违规；
   d AGENTS.md、README.md 合法；
   e apps/backend/src/main/resources/db/migration/V001__init.sql 合法，大写 data/Foo.csv 违规；
   f 扩展名 .svg 但内容为 png 魔数 → 违规；
   g artifacts/ 下除 README.md 外被跟踪 → 违规；
   h artifacts/runs/... 缺少 manifest.json → 违规；
   i 超过 1MB 的普通文件违规，uv.lock 例外通过；
   j .gitignore 缺少 .venv → 违规；
   k import 边界：scheduler_core 引用 agent → 违规；simulator 引用 agent → 违规；experiments 引用 agent 合法。
   测试自身不得在仓库中留下文件。
5. Makefile：薄委托，目标 check（layout + boundaries + governance tests）、check-layout、test-governance、clean-tmp（dry-run）；
   真实逻辑在 tools/*.py；P0 阶段不引用 mypy src 等尚不存在的目标。
6. pyproject.toml：只含工具配置（pytest、ruff、mypy 的配置段），不声明包、不声明业务依赖。
7. .gitignore：artifacts/* 与 !artifacts/README.md；合同列出的本地忽略项；*.log。
   .gitattributes（行尾规范）、.editorconfig、.pre-commit-config.yaml（只声明，不执行安装）。
   使用的工具与版本须来自官方来源，在交接单里列出来源与许可证；不确定则标"未核实"，并通知总设计师登记。
8. artifacts/README.md：说明布局与规则（引用 file-storage-standard，路径文字一致）。

# 约束
- 本包写的是治理工具，不是业务代码；不要创建 src/ apps/ experiments/ 目录。
- 不使用第三方依赖实现检查器（仅 pytest 用于测试）。
- 规则与合同冲突时以合同为准，并在交接单"偏差"栏说明。

# 验收
- 在干净工作区运行 make check，全部通过（P0 版）。
- 每个测试用例对应一个违规或合法场景，且每个违规类型都有至少一个用例。
- 故意放置违规文件时，检查器退出码非 0 且输出规则编号。
- layout_rules.toml 的规则编号与 file-storage-standard 一致（交接单附对照表）。

# 交接
按公共前言 H 格式。额外列出：规则编号对照表；每个测试用例的结果；已知误报或漏报风险。
