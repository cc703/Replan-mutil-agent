# P0 Claude 计划、提示词与总设计师审查记录

日期：2026-11-09，Asia/Shanghai。工作包：P0-A / P0-B / P0-C。

## 来源与真实性

- 计划及提示词实际由[侧边栏 Claude 会话](https://claude.ai/chat/54ab7bfe-2bca-4714-9759-e3ae3e5474e7)生成；回复标题为“P0 治理与协作基础：计划、提示词与门禁”，会话消息 54。
- 总设计师在读取公共前言、三个专项提示词及门禁后派发专项会话。此文件是审查与实际派发内容的持久记录，不冒充 Claude 逐字原文。
- Claude 在消息 56 重新附上两份原设计和 p0_claude_plan_v001.md。浏览器能读取对话，但附件下载、打开动作反复超时，未得到本地文件，不能宣称逐字导入或哈希验证完成。
- 原始计划仍可从会话读取；原文文件入库作为独立导入项保留，不以摘要取代原始设计。

## Claude 提出的实施计划

1. P0 仅建立治理与协作基础，不实施 P1–P8 业务。
2. 三个互斥工作包并行：A 治理规范、B 协作机制、C 机器门禁。
3. 总设计师逐包审查，复跑检查，核对人类规范与机器规则一致性。
4. 每包交付后更新进度、提交、普通推送并核验远端提交。
5. 缺原文的导入项单独受阻，其余工作继续。

## 总设计师审查结论：PROMPT-OK

用户本轮已授权文档建设、多个专项 Agent、进度维护和 GitHub 同步。常规工程实施不再重复确认。

相对 Claude 建议的审查调整：

- 不创建 AGENT.md 副本，AGENTS.md 为唯一入口。
- 空仓直接产生实际交付提交；共享工作树使用 codex/p0-governance，不虚构空基线或每包独立分支。
- 文件布局检查提前 P0；Python 入口为 tools/check.py，适应 Windows 无 make 的环境。
- 文件命名使用局部例外，Git 视角检查与被忽略源码生成物巡检结合。
- P0 不实现 ArtifactStore，只允许 artifacts/tmp 的治理暂存；生命周期能力不宣称已完成。
- 仅锁定 P0 实际使用的开发工具，不安装业务依赖；pre-commit 配置可选而非假称已安装。
- B1 迁移、求解器双配置档及其公共字段不采纳为既定契约，按用户随后裁决延期讨论。
- 扩充可复用领域角色定义，仍不启动对应业务实现。
- 总设计师统一写进度、commit、push，专项代理不操作 Git 状态。

## 实际派发公共提示词 v001

你在 D:/Default/Replan-mutil agent 执行 P0。先阅读 AGENTS.md、相关规范和本包卡片；Claude 的本包计划及提示词已由总设计师审查。只编辑所分配文件，不创建 src/、apps/、experiments/ 业务目录，不执行 git commit/push/config/checkout，不覆盖其他专项改动。

文档使用中文；路径、标识符与命令使用英文。不得编造设计来源、依赖版本、许可证、测试或远端同步。信息不确定时读取官方资料或实际安装元数据，无法核实则明确标记。

文件规则使用 tools/layout_rules.toml 与可读存储规范交叉核对。生成物只在 artifacts/，唯一入库例外 artifacts/README.md；P0 尚无 ArtifactStore，治理暂存只在 artifacts/tmp/，测试用 tmp_path。文档、模板和正式开发提示词是人工维护的工程资产，可以进入 docs/。

遇到论文范围、算法目标、评估协议、公共契约、已定技术栈、版权/公开范围、真实数据或未授权费用等变更，向总设计师报告并由用户裁决。仅阻塞依赖该问题的任务，独立工作继续。

交接格式：DONE/BLOCKED/NEEDS-DECISION；变更文件与用途；真实验证命令和结果；来源及待核实项；与计划偏差；未决问题；下一步。短期会话可复用，跨会话按角色文件和进度恢复，不声称永久后台运行。

## WP-A 实际派发提示词 v001：治理与规范

角色：长期治理规范专项。输入：已读开发规格 v1.1、Claude 公共合同与 WP-A 提示词、总设计师审查调整、机器规则。

允许写入：AGENTS.md、README.md、CHANGELOG.md；docs/engineering/coding-standards.md、file-storage-standard.md、open-source-policy.md、dependency-register.md；docs/decisions/0000-template.md 及 0001–0005 ADR。原设计导入由总设计师负责，未取得原文不得自行生成替代文件。

任务：

1. AGENTS.md 控制约 120 行以内，作为唯一入口，链接规范、协作与进度；每个工作包须 Claude 先出计划和提示词，由 Codex 审查派发。
2. README 提供导航和真实可运行 P0 命令；CHANGELOG 记录实际交付，不写业务完成。
3. 代码规范覆盖 Python 3.11、完整类型、Pydantic v2、整数槽、时区、随机子流、配置外置、JSON 日志、不可变输入、错误与超时区分、独立验证及有意义测试。
4. 文件规范最优先：目录职责与输入/中间/最终三类资产、Git 与本地忽略区别、命名例外、源码生成物禁令、1MB 及精确例外、run_id/manifest、路径防逃逸、完成运行不覆盖、保留清理、追溯、脱敏和真实图表格式。
5. OSS 规范：标准库→已登记依赖→新增工具；官方文档与源码核对已装 API，锁版本，登记用途/版本/许可/来源/日期/理由/替代项/状态；不自行为本项目选择 LICENSE，不重复要求已选 DeepSeek 的选择授权。
6. ADR 0001 记录布局命名修复，0004 记录真实图表格式，0005 记录语言/提交约定；0002/0003 记录设计冲突和用户延期意见。

验收：文件非空、无越界、AGENTS 有效导航，8类存储规则与机器配置一致，来源/建议/已实施清晰，未核实内容明确，源文档未导入不得假称完成。按公共格式交接。

## WP-B 实际派发提示词 v001：协作机制

角色：长期协作和进度规范维护者。输入：Claude 公共合同、WP-B 提示词、总设计师审查调整。

允许写入：docs/agents/README.md、planner.md、prompt-engineer.md、storage-steward.md、oss-scout.md、reviewer.md、contract-engineer.md、solver-engineer.md、simulation-engineer.md、agent-engineer.md、app-engineer.md、experiment-engineer.md；docs/engineering/review-gates.md、git-workflow.md；docs/progress/PROGRESS.md；docs/work-packages/_template.md、P0.md。

任务：

1. 定义 11 个可持续复用角色：名称版本、用途触发、必读输入、按包限定的写入范围、禁令、交付、验收、交接、失败模式、跨会话恢复。
2. planner/prompt-engineer 对应真实侧边栏 Claude，不冒充已运行本地智能体；领域角色为后续定义，不启动 P1–P8。
3. 定义 G0 立项、G1 Claude 计划提示词审查、G2 实施自检、G3 独立工程审查、G4 必要用户裁决、G5 提交同步。
4. 一步定义为可验收工作包；范围内自检修复无需再次询问 Claude，实质扩大范围则重规划。模板不能代替新包的 Claude 计划。
5. 最多 3 个实施会话并行、文件所有权互斥；共享 checkout 不各自切换分支。总设计师单写进度和 Git。
6. 工作包和进度记录目标/非目标/输入/范围/验收/风险/门禁/来源/提交/同步；验收与同步分字段；状态只用 TODO/IN-PROGRESS/IN-REVIEW/ACCEPTED/BLOCKED。
7. 初始 P0 三包进行中，P1–P8 TODO；不得编造自引用 SHA 或远端状态；用户延期项加入风险。

验收：角色字段、路径和链接完整；工作包写入边界清晰；授权/裁决分明；同步核验可执行；原始设计导入项独立记录。按公共格式交接，并将进度维护权交还总设计师。

## WP-C 实际派发提示词 v001：机器门禁

角色：长期治理工具与检查专项。输入：Claude 公共合同、WP-C 提示词、总设计师审查调整。

允许写入：tools/layout_rules.toml、tools/check_repo_layout.py、tools/check_import_boundaries.py、tools/check.py；tests/governance/*；.gitignore、.gitattributes、.editorconfig、.pre-commit-config.yaml、Makefile、pyproject.toml、uv.lock；artifacts/README.md。

任务：

1. 标准库实现检查器，规则编号为 R-root/R-naming/R-generated/R-size/R-artifacts/R-manifest/R-magic/R-ignore；配置与存储文档对齐。
2. Git 跟踪+未忽略文件检查；不能让忽略规则隐藏强制入库缓存/生成物。扫描本地运行 manifest 即使被 Git 忽略。
3. 白名单、分层命名、Java/Vue/Flyway 局部例外、源码生成物、前端资源局部例外、体积、PNG/PDF/SVG 真格式、必须忽略项检查。
4. manifest 使用原规格基础字段；校验状态、类型、目录标识、时间带时区及输出路径不逃逸，不强制新增 solver 字段，不实现 ArtifactStore。
5. AST 依赖边界覆盖直接和相对导入；src 不存在时通过；明确动态导入能力局限。不修改原 B1 位置。
6. 提供 --root 与 text/json 输出和可靠失败退出码。真实工具配置和锁文件使用 Python 3.11；只安装当前所需 pytest、ruff、mypy。
7. tmp_path 构造临时 Git 仓库做合法/违规回归：忽略环境、根杂文件、源码 CSV/忽略日志、约定文件、Flyway 与非法大写数据、伪 SVG、强制入库 artifacts/缓存、缺 manifest、大文件/锁例外、忽略规则缺失、非法核心/仿真导入与合法实验依赖。
8. tools/check.py 编排全部 P0 门禁；Makefile 薄委托；不对不存在的业务目录运行 mypy src；可选 local pre-commit 不假称已安装。

验收：`uv run --python 3.11 --group dev python tools/check.py` 真实通过，违规用例退出非零且有编号，无业务实现，无越界编辑；按公共格式交接并披露误报/漏报。

## 用户后续裁决（优先于最初建议）

2026-11-09，用户明确：B1 外移“暂不改，后续再讨论，但是做好批注”；双求解配置档“暂不改，按照计划进行，做好标注后续讨论”。两项均为 DEFERRED，保持原规格。详见 ADR 0002/0003。此裁决不影响 P0 独立治理交付。

## 原文待导入登记

以下哈希、行数和字节数由 Claude 消息 56 提供，尚未在本机核验；不是已完成的校验结论。

| 目标 | 来源文件 | 字节 | 行数 | 预期 SHA256 |
| --- | --- | ---: | ---: | --- |
| docs/design_v2.md | 毕业设计_完整设计框架_v2.md | 74171 | 1397 | f5589dd322b8f9caf45221482f952b9fd3ecba3f69a88919e4185f0177dd6677 |
| docs/codex_spec.md | Codex开发规格_v1.md，内部v1.1 | 33962 | 645 | 59e84a27ed5055eca83f23e73b8d89cdfee6a05ff27b74c64d753c8355cb651c |
| docs/work-packages/p0_claude_plan_v001.md | p0_claude_plan_v001.md | 34844 | 548 | 82d49292f1342dce3c5348b5176d7cf029fe6fd10ddf61d884276ba8e61286f6 |

取回后先逐字保存并核验；规格修订通过独立勘误/ADR呈现，不静默改掉用户要求保留的 B1 与求解参数。当前不创建虚假的 design_v2.md 或 codex_spec.md 占位正文。
