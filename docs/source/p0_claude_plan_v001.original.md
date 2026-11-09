# p0_claude_plan_v001

> 留档说明：本文件为计划 / 提示词 Agent 在 P0 阶段给出的完整计划与三个专项 Agent 提示词，按当时回复原文留档，版本 v001。
> 后续对契约的变更（如 B1 迁移、求解器配置档新增字段）以总设计师记录的 PROPOSED 状态与用户裁决为准，不在本文件中回改。

---

# P0 治理与协作基础：计划、提示词与门禁

**声明**：以下全部是**提议**，我没有对你的本地仓库做过任何修改。我的运行环境无法访问你的本地仓库和 GitHub，所以提交和推送只能由你或总设计师（Codex）执行。

## 0. v2 能否从本会话取回

**能**，但有三点限制。我刚才用命令核对过，会话文件区里有这三份文件：

| 文件 | 行数 | 处理建议 |
|---|---|---|
| `毕业设计_完整设计框架_v2.md` | 1397 | 导入为 `docs/design_v2.md` |
| `Codex开发规格_v1.md`（内部版本 v1.1） | 645 | 导入为 `docs/codex_spec.md`，**同时应用第 2 节的修正，升为 v1.2** |
| `毕业设计_项目设计文档.md`（v1） | 738 | 已被 v2 取代，**不导入**，避免两套设计并存 |

限制如下：

1. 这些文件在会话文件区里，我不能替你拷进仓库。取回方式是下载我之前回复里附的文件卡片。
2. 会话文件区可能在会话结束后被清理，所以请**现在**下载，放到仓库外的暂存目录（如 `~/incoming/`），再由 WP-A 导入。
3. v2 全文约 1400 行，不适合贴在对话里，我没有把它改写成摘要来替代。

## 1. 协作角色

| 角色 | 职责 | 不可做 |
|---|---|---|
| 用户 | 最终裁决设计问题 | — |
| 总设计师（Codex） | 审查提示词与交付、集成、提交、推送 | 不绕过门禁 |
| 计划 / 提示词 Agent（我） | 出计划、出可派发提示词、出裁决请求单 | 不写仓库、不提交 |
| 专项 Agent（按提示词执行） | 在允许写入范围内产出文件 | 不提交、不推送、不越界、不改 git 配置 |

## 2. 规格冲突修正建议（P0 文档与检查器都依赖，先定）

### 2.1 小写规则与约定文件冲突

**问题**：规格要求"文件名小写 ASCII"，但 `AGENTS.md`、`README.md`、`CHANGELOG.md`、`Makefile` 以及 Flyway 的 `V001__init.sql` 都含大写。

**建议**：命名规则按路径前缀分层，例外**显式登记**，不用全局正则。

```text
R-N1  artifacts/**、data/**、experiments/configs/**、docs/results/**、src/**/*.py：
      小写 ASCII、数字、_ - .；Python 包与模块用 snake_case。
R-N2  docs/**（docs/results 除外）：允许中文与大写；文件名建议英文小写连字符；
      决策记录用 NNNN-slug.md。
R-N3  根目录约定文件例外：AGENTS.md README.md CHANGELOG.md LICENSE Makefile
      Dockerfile .gitignore .gitattributes .editorconfig .env.example
      .pre-commit-config.yaml
R-N4  框架约定例外（仅限所列路径）：
      apps/backend/**：Java 类 PascalCase；pom.xml；
        Flyway 迁移 V<版本>__<描述>.sql，路径为
        apps/backend/src/main/resources/db/migration/（Spring Boot 默认位置，
        原规格写的 apps/backend/db/migration/ 应一并更正）
      apps/frontend/**：package.json、PascalCase.vue、vite.config.ts 等
R-N5  其他例外必须登记到 tools/layout_rules.toml 的 [exceptions]，写明理由；
      禁止使用 ** 通配的全局例外。
```

### 2.2 根白名单与本地 .venv/.env/缓存/.git 冲突

**问题**：白名单按"磁盘上有什么"检查，会把 `.git`、`.venv`、`.env` 等本地项当成违规。

**建议**：检查对象改为 **git 视角**，即 `git ls-files -co --exclude-standard`（已跟踪文件加上未被忽略的未跟踪文件）。被忽略的本地项不参与白名单检查，但 `.gitignore` 必须覆盖它们，并由测试验证。

```text
根目录允许（已跟踪 / 未忽略）：
  AGENTS.md README.md CHANGELOG.md LICENSE(可选) Makefile pyproject.toml uv.lock
  docker-compose.yml .gitignore .gitattributes .editorconfig .env.example
  .pre-commit-config.yaml .github
  docs src apps experiments data tests tools artifacts
本地忽略（不检查，但 .gitignore 必须包含）：
  .git(git 本身不会列出) .venv .env .mypy_cache .ruff_cache .pytest_cache
  __pycache__ node_modules .idea .vscode .DS_Store
```

### 2.3 num_workers=8 与完全确定性冲突

**问题**：CP-SAT 多线程搜索通常不保证结果逐次一致，尤其用墙钟时间限制终止时。规格同时要求"黄金测试可复现"和"num_workers=8"，两者矛盾。

**建议**：设两个求解配置档，并写进数据契约。

| 配置档 | 用途 | 设置要点 |
|---|---|---|
| `reproducible`（默认） | 黄金测试、属性测试、论文主表的质量指标 | `num_workers=1`，固定随机种子，终止条件优先用**确定性时间**而非墙钟 |
| `performance` | 规模与耗时实验 | 多线程，墙钟限制，**重复多次**并报告方差 |

```text
ReplanParams（修正）：
  solver_profile: Literal["reproducible","performance"] = "reproducible"
  num_workers: int | None = None   # None 按档位取值；reproducible→1
  random_seed: int = 0
  limit_kind: Literal["deterministic","wall"]
  limit_value: float
manifest 增加：solver_profile、num_workers、random_seed、limit_kind、求解器版本
```

**注意**：同版本、同平台下才可期待逐次一致，跨平台和跨版本不保证，所以要在 manifest 里记版本。具体参数名（如确定性时间上限、随机种子）以**已安装版本的官方文档**为准，由 P2 的实施 Agent 核实。

### 2.4 独立核心与 b1_llm 依赖冲突

**问题**：`scheduler_core` 要求"不依赖大模型"，但基线 B1 需要调用大模型，却被放在 `scheduler_core/baselines/`。

**建议**：把 B1 移出核心，并规定依赖方向。

```text
experiments → agent → scheduler_core
experiments → simulator → scheduler_core
apps/*  →  只通过 HTTP 调用 agent 服务
scheduler_core：仅允许 标准库 + ortools + numpy + pydantic；
                不得 import agent / simulator / experiments / 任何大模型 SDK
simulator：可依赖 scheduler_core.models；不得依赖 agent
b1_llm 位置：experiments/baselines/b1_llm.py（通过 agent.llm 适配层调用）
b2_full、b3_rule 留在 scheduler_core/baselines/（不含大模型）
```

用 AST 静态检查（`tools/check_import_boundaries.py`）强制，不靠自觉。

### 2.5 png 不能靠改扩展名变 svg

**问题**：规格写"草稿 png，入库版本用 svg 或 pdf"，但 `make_report` 只"复制"，没有矢量源时容易有人直接改扩展名。

**建议**：

- 绘图脚本必须同时输出 `png`（预览）与 `svg` 或 `pdf`（入库用），由绘图库原生导出。
- `make_report.py` 只复制已存在的文件，**不做格式转换**；只有 png 时就入库 png，并在 `INDEX.md` 注明格式。
- 布局检查加**魔数校验**：png 文件头、`%PDF`、svg 以 `<svg` 或 `<?xml` 开头，扩展名与内容不一致即失败。

### 2.6 我额外发现的冲突

1. **前端资源与体积**：`apps/frontend` 里合法含 png、svg 图标，`package-lock.json` 可能超过 1MB，与"源码目录无 png/svg、文件 ≤1MB"冲突。需给 `apps/frontend/src/assets/`、`apps/frontend/public/` 和锁文件登记例外。
2. **P0 阶段命令会失败**：AGENTS.md 里的 `mypy src` 等命令在 `src/` 尚不存在时会报错。P0 的 `make check` 只跑布局、依赖边界和治理测试，其余目标**条件执行**。
3. **Windows 没有 make**：我不知道你的操作系统（见第 7 节）。Makefile 应只做薄委托，真实逻辑放在 `tools/*.py`，这样没有 make 也能直接运行。
4. **运行目录只读与清理工具**：只读目录在 Windows 上删除语义不同，清理工具需先改权限再删除。
5. **文件名映射**：会话里的中文文件名导入时改为英文名，并在 ADR 里记录来源。
6. **AGENT.md**：Codex 读取的是 `AGENTS.md`。只保留一个 `AGENTS.md`，不创建 `AGENT.md` 副本，在 README 中注明"用户口头称 AGENT.md，即本文件"。允许后续在子目录放嵌套的 `AGENTS.md`。

## 3. P0 计划

### 3.1 范围

**包含**：AGENTS.md、代码规范、文件存储规范（最高重点）、开源工具检索与使用规范、可复用的专项智能体定义、项目进度 MD、门禁与提交流程、机器可检查的仓库布局规则、设计文档导入与规格修正。
**不包含**：P1–P8 的任何业务代码（模型、求解器、仿真器、Agent、前后端）。`src/`、`apps/`、`experiments/` 目录在 P0 **不创建**。

**范围需总设计师确认**：布局检查器原属 P1，我建议提前到 P0，因为它是"文件存储规范"的执行机制。

### 3.2 步骤与并行关系

```text
S0（总设计师）：创建起始空提交（git commit --allow-empty），让各工作包可从同一基线分支
S1（并行，三个工作包，写入文件互不重叠）：
    WP-A 治理与规范      WP-B 协作机制      WP-C 机器门禁
S2（总设计师）：逐个 G3 审查；做一致性交叉检查（规范文档 ↔ layout_rules.toml）
S3（总设计师）：集成、跑 make check、处理 G4 裁决项
S4（总设计师）：提交、推送、更新进度与变更日志、打 p0-accepted 标签
```

**一致性机制**：`tools/layout_rules.toml` 是机器可读规则的**唯一来源**，由 WP-C 编写；WP-A 的 `file-storage-standard.md` 是它的人类可读镜像。两者内容由本文第 4 节的公共合同统一给出，S2 时交叉比对。

### 3.3 文件清单与归属

| 工作包 | 允许写入的文件 |
|---|---|
| **WP-A** | `AGENTS.md`、`README.md`、`CHANGELOG.md`、`docs/design_v2.md`、`docs/codex_spec.md`、`docs/engineering/coding-standards.md`、`docs/engineering/file-storage-standard.md`、`docs/engineering/open-source-policy.md`、`docs/engineering/dependency-register.md`、`docs/decisions/0000-template.md`、`docs/decisions/0001-*.md` 至 `0005-*.md` |
| **WP-B** | `docs/agents/README.md`、`docs/agents/planner.md`、`docs/agents/prompt-engineer.md`、`docs/agents/storage-steward.md`、`docs/agents/oss-scout.md`、`docs/agents/reviewer.md`、`docs/progress/PROGRESS.md`、`docs/work-packages/_template.md`、`docs/work-packages/P0.md`、`docs/engineering/review-gates.md`、`docs/engineering/git-workflow.md` |
| **WP-C** | `tools/layout_rules.toml`、`tools/check_repo_layout.py`、`tools/check_import_boundaries.py`、`tests/governance/*`、`.gitignore`、`.gitattributes`、`.editorconfig`、`.pre-commit-config.yaml`、`Makefile`、`pyproject.toml`（只含工具配置）、`artifacts/README.md` |

**建议的决策记录**（WP-A 编写，每条一页以内）：

- 0001 仓库布局与命名规则分层（对应 2.1、2.2）
- 0002 依赖方向与 b1_llm 位置（2.4）
- 0003 求解器确定性配置档（2.3）
- 0004 图表格式与魔数校验（2.5）
- 0005 语言与提交约定：文档用中文，标识符与命令用英文，提交信息用英文 Conventional Commits（**默认约定，用户可改**）

### 3.4 P0 验收标准

1. 三个工作包的交接单齐全，且通过 G3。
2. 在干净工作区运行 `make check`（P0 版：布局、依赖边界、治理测试）全部通过。
3. `docs/engineering/file-storage-standard.md` 与 `tools/layout_rules.toml` 逐条一致。
4. `docs/codex_spec.md` 已应用第 2 节修正，并在文首列出修正清单。
5. 无 P1 及以后的业务代码；无密钥、个人敏感信息。
6. `PROGRESS.md`、`CHANGELOG.md` 已更新；每个裁决项已有决策记录。

### 3.5 Git 提交与同步

- 分支：`wp/p0-a-governance`、`wp/p0-b-collab`、`wp/p0-c-gates`，从 S0 起始提交拉出，验收后合入 `main`。
- 每个工作包验收后一次提交，格式 `type(scope): subject`，scope 为工作包编号，正文列出门禁证据。
- 推送：`git push -u origin main`；**不强制推送、不改写历史**。推送前：`make check` 通过、`git status` 干净、扫描无密钥。
- P0 全部验收后打标签 `p0-accepted`。

## 4. 公共前言（附在每个专项 Agent 提示词最前面）

````text
# 公共前言（所有 P0 专项 Agent 必读）

## 项目与范围
项目：面向多约束场景的任务动态调度与重规划 Agent（本科毕业设计）。
当前阶段：P0 治理与协作基础。你只处理本工作包的文件。
绝对不做：P1–P8 的任何业务代码；不创建 src/ apps/ experiments/ 目录。

## 通用规则
1. 只能写入你的提示词里"允许写入"的文件；其他文件只读。
2. 不执行 git commit / push，不修改 git 配置与 remote；提交由总设计师负责。
3. 遇到"必须裁决"的问题（见下）立即停手，按"裁决请求单"格式提交，不要自行决定。
4. 文档使用中文；代码标识符、命令、路径、提交信息使用英文。
5. 不确定的事实（API、版本、许可证）先查官方来源再写，并在交接单里列出来源；无法核实就写"未核实"。
6. 不得编造文件内容来源；导入的设计文档必须逐字保留，只允许应用提示词中列出的修正。

## 必须裁决的问题（遇到即停）
论文范围或题目表述；算法设计与目标函数；评估协议与基线定义；数据契约；
引入 GPL/LGPL/AGPL/未声明许可证的依赖；外部服务、费用、密钥；
仓库可见性与许可证；偏离 design_v2 或 codex_spec；删除或重命名受保护文件；
改写历史或强制推送；涉及真实实验室数据或真人测试。

## 公共合同

C1 目录（P0 只创建 docs/ tools/ tests/governance/ artifacts/README.md）
   根目录允许（已跟踪/未忽略）：AGENTS.md README.md CHANGELOG.md LICENSE(可选)
   Makefile pyproject.toml uv.lock docker-compose.yml .gitignore .gitattributes
   .editorconfig .env.example .pre-commit-config.yaml .github
   docs src apps experiments data tests tools artifacts
   本地忽略项（不检查，.gitignore 必须包含）：
   .venv .env .mypy_cache .ruff_cache .pytest_cache __pycache__ node_modules
   .idea .vscode .DS_Store
   检查对象：git ls-files -co --exclude-standard

C2 命名规则
   R-N1 artifacts/** data/** experiments/configs/** docs/results/** src/**/*.py：
        小写 ASCII、数字、_ - .；Python 用 snake_case
   R-N2 docs/**（docs/results 除外）：允许中文与大写；ADR 用 NNNN-slug.md
   R-N3 根目录约定文件例外：AGENTS.md README.md CHANGELOG.md LICENSE Makefile
        Dockerfile .gitignore .gitattributes .editorconfig .env.example
        .pre-commit-config.yaml
   R-N4 框架例外：apps/backend/**（Java PascalCase、pom.xml、Flyway
        V<版本>__<描述>.sql，位置 apps/backend/src/main/resources/db/migration/）；
        apps/frontend/**（package.json、PascalCase.vue、vite.config.ts 等）
   R-N5 其他例外必须登记到 tools/layout_rules.toml 的 [exceptions]，写明理由，禁止 ** 全局例外

C3 产出物
   所有机器生成物只能在 artifacts/；artifacts/ 只有 README.md 入库。
   运行目录：artifacts/runs/<kind>/<name>/<run_id>/，必须有 manifest.json。
   run_id = YYYYMMDD-HHMMSS_<git短哈希>_<标签>
   manifest 必含：run_id kind name status started_at ended_at command git(commit,dirty)
   config_sha256 seeds versions solver_profile num_workers random_seed limit_kind
   源码目录不得出现 .log .csv .jsonl .tmp；.png .svg 仅 docs/results、
   apps/frontend/src/assets、apps/frontend/public 可出现。
   入库文件 ≤ 1MB；例外：uv.lock、package-lock.json。
   文件魔数必须与扩展名一致（png/pdf/svg）。

C4 依赖方向
   experiments → agent → scheduler_core；experiments → simulator → scheduler_core
   apps/* 仅通过 HTTP 调用 agent 服务
   scheduler_core 仅允许 标准库、ortools、numpy、pydantic；不得 import
   agent / simulator / experiments / 大模型 SDK
   simulator 不得 import agent
   b1_llm 位于 experiments/baselines/b1_llm.py

C5 求解器确定性配置档
   reproducible（默认）：num_workers=1、固定随机种子、确定性时间限制；用于黄金/属性测试与论文质量指标
   performance：多线程、墙钟限制、重复多次报告方差；用于规模与耗时实验
   具体参数名以已安装版本的官方文档为准（P2 核实）

C6 提交约定（供文档引用）
   Conventional Commits：type(scope): subject；scope 为工作包编号；
   一个工作包验收后一次提交；不强制推送、不改写历史。

## H 交接格式（交付时必须按此输出）
状态：DONE / BLOCKED / NEEDS-DECISION
变更文件：路径列表，每个标注 新增/修改，并写一句用途
验证：执行过的命令与结果摘要（复制真实输出，不要概括）
来源：引用的官方文档/外部资料链接与检索日期；未核实项单独列出
与合同的偏差：无 / 逐条说明
未决问题：无 / 列表
需裁决问题：无 / 按"裁决请求单"填写
下一步建议：一句话

## 裁决请求单格式
标题；背景（2-3 句）；选项 A/B(/C) 各含 优点、缺点、影响范围；
你的推荐与理由；不裁决的后果；需要裁决的截止点。
````

## 5. 三个专项 Agent 提示词

### WP-A：治理与规范 Agent

````text
[附上公共前言]

# 角色
你是"治理与规范 Agent"。职责：为仓库建立约束文档、规范与设计文档的规范化导入。

# 目标
产出 AGENTS.md、README、CHANGELOG、代码规范、文件存储规范、开源工具使用规范、依赖登记表、决策记录，并导入设计文档。

# 允许写入
AGENTS.md  README.md  CHANGELOG.md
docs/design_v2.md  docs/codex_spec.md
docs/engineering/coding-standards.md
docs/engineering/file-storage-standard.md
docs/engineering/open-source-policy.md
docs/engineering/dependency-register.md
docs/decisions/0000-template.md  docs/decisions/0001-*.md ... 0005-*.md
其余一律只读。

# 输入
- ~/incoming/ 下的两个设计文件（总设计师会告知准确路径）：
  完整设计框架 v2 → 导入为 docs/design_v2.md（逐字保留）
  Codex 开发规格 v1.1 → 导入为 docs/codex_spec.md，仅应用公共合同 C1–C5 对应的修正，
  并在文首增加"v1.2 修正清单"，逐条写明修改了哪一节、为什么
- 公共合同 C1–C6
- 若 ~/incoming/ 中缺文件：对应导入项标记 BLOCKED，其余照常进行

# 任务
1. AGENTS.md（只保留一个，不创建 AGENT.md）：
   项目摘要；核心原则（计划只能由求解器生成、校验器为独立关卡、核心包纯净、大模型输出视为不可信）；
   工作方式（先计划后实施、不擅自决定设计问题）；文件存储规则摘要（引用 file-storage-standard）；
   依赖与开源工具规则摘要；命令（P0 版：make check 等，不引用尚不存在的目录）；
   完成的定义；"必须裁决的问题"清单。控制在约 120 行内。
2. README.md：项目简介、目录说明、如何运行检查、文档导航；一句注明"口头称 AGENT.md 即 AGENTS.md"。
3. CHANGELOG.md：Keep a Changelog 格式，写入 P0 的 Unreleased 条目。
4. coding-standards.md：Python 3.11、类型标注、pydantic v2、时间用整数槽、随机性用 numpy Generator 且子流隔离、
   配置外置 YAML、结构化 JSON 日志、测试要求、命名（snake_case 等）、docstring、错误处理与不可变约定；
   工具配置只描述不实现（实现归 WP-C）。
5. file-storage-standard.md（最高重点）：把公共合同 C1–C3 写成可执行规则，每条带编号（R-xx），
   含：三类数据（输入/中间/最终）、目录职责表、run_id 与 manifest 字段表、写入规则（统一出口、禁止硬编码路径）、
   保留与清理表、最终结果入库流程、图表格式与魔数规则、体积规则、例外登记流程、违规示例与正确示例。
   必须与 WP-C 的 tools/layout_rules.toml 一一对应，规则编号一致。
6. open-source-policy.md 与 dependency-register.md：
   检索规范：先标准库、再已登记依赖、最后新增；官方文档与源码优先于二手资料；
   必须核对已安装版本的 API，不凭记忆；每次检索记录 日期/查询/来源链接/选择理由；
   许可证分级：允许（MIT、BSD-2/3、Apache-2.0、ISC、MPL-2.0、PSF）；
   需用户裁决（GPL、LGPL、AGPL、SSPL、商业或自定义、无许可证）；
   禁止复制未标注许可证的代码片段；版本固定并提交锁文件；安全扫描要求（pip-audit、npm audit 的使用方式）；
   外部服务（如 DeepSeek）不属于依赖，引入或变更需用户裁决。
   dependency-register.md 为表格：名称、用途、版本、许可证、来源链接、检索日期、维护状态、替代方案、引入工作包、审批级别；
   P0 预填项：只登记 P0 实际使用的工具（如 ruff、mypy、pytest、pre-commit），不预填业务依赖；
   每个预填项的许可证与版本必须现查并写明来源，查不到就写"未核实"。
7. 决策记录 0001–0005：对应本阶段已定的修正（布局与命名分层、依赖方向、确定性配置档、图表格式与魔数、语言与提交约定）；
   每条含 背景/决定/理由/影响/状态。0005 状态标"默认约定，待用户确认"。

# 验收
- 所有"允许写入"文件存在且非空；无多余文件。
- file-storage-standard 的规则编号与公共合同一致，无自相矛盾。
- docs/design_v2.md 与来源文件逐字一致（给出 diff 或哈希比对结果）。
- docs/codex_spec.md 相对来源的全部改动都在"v1.2 修正清单"中列出。
- AGENTS.md 不引用尚不存在的目录或命令。
- 所有外部事实（许可证、版本）附来源或标注"未核实"。

# 交接
按公共前言 H 格式。额外列出：导入文件的来源路径与哈希；对 codex_spec 的改动清单；你认为需要用户裁决的项。
````

### WP-B：协作机制 Agent

````text
[附上公共前言]

# 角色
你是"协作机制 Agent"。职责：定义可复用的专项智能体、门禁、工作包模板、进度记录与 Git 工作流。

# 目标
让后续每个工作包都能按统一格式立项、派发、审查、验收、同步。

# 允许写入
docs/agents/README.md
docs/agents/planner.md  docs/agents/prompt-engineer.md  docs/agents/storage-steward.md
docs/agents/oss-scout.md  docs/agents/reviewer.md
docs/progress/PROGRESS.md
docs/work-packages/_template.md  docs/work-packages/P0.md
docs/engineering/review-gates.md  docs/engineering/git-workflow.md
其余一律只读。

# 输入
公共合同 C1–C6；本提示词；总设计师提供的 P0 计划（工作包 A/B/C 与归属）。

# 任务
1. 专项智能体定义。统一模板，每个定义含：名称与版本、用途、触发条件、输入、允许写入范围（用路径模式）、
   禁止事项、输出与交接格式、验收清单、与其他智能体的边界、已知失败模式与应对。
   需定义五个：
   - planner：出工作包计划、风险、依赖、验收；产出 WP 卡片
   - prompt-engineer：把 WP 卡片转成可直接派发的提示词，含 角色/目标/允许写入/输入/任务/验收/交接
   - storage-steward：执行并审查文件存储规范，处理例外登记、清理与归档提案
   - oss-scout：按开源使用规范检索工具，输出登记表条目与许可证结论，不自行引入依赖
   - reviewer：按门禁清单审查交付，给出 ACCEPT / REWORK / ESCALATE
   agents/README.md：索引表、选择指南、如何派发、如何升级。
2. review-gates.md：定义门禁 G0–G5：
   G0 立项（WP 卡片）；G1 提示词审查；G2 实施自检；G3 工程审查；G4 用户裁决；G5 提交与同步。
   每个门禁写 入口条件、检查项、通过标准、产出物、责任人。
   明确区分"工程审查可决定"与"必须用户裁决"，使用公共前言中的裁决清单作为权威来源，不得删减，可补充示例。
   含停线触发条件（任一满足即暂停该工作包）：越界写入、出现业务代码、密钥或个人信息进入文件、
   规则文档与机器规则不一致、测试被削弱或跳过、未经裁决改动设计。
   含"裁决请求单"模板。
3. git-workflow.md：分支命名、起始空提交说明、提交格式（Conventional Commits，scope 为工作包编号）、
   一个工作包一次提交、推送前检查（make check、git status 干净、无密钥）、不强制推送不改写历史、
   标签规则、回滚办法、合入 main 的步骤；说明专项智能体不提交、由总设计师提交推送。
4. docs/work-packages/_template.md：WP 卡片模板
   （ID、目标、范围、非目标、依赖、允许写入、输入、任务、验收、风险、负责智能体、门禁状态、提交哈希）。
   docs/work-packages/P0.md：按模板填写 WP-A、WP-B、WP-C 三张卡，内容与总设计师提供的计划一致。
5. docs/progress/PROGRESS.md：
   结构：当前阶段与状态；工作包状态表（ID、名称、负责智能体、分支、门禁、验收日期、提交哈希）；
   决策索引（链接到 docs/decisions）；风险与阻塞；变更日志指引。
   更新规则：仅在工作包验收的同一次提交里更新；单一写入者（总设计师）；状态词只用
   TODO / IN-PROGRESS / IN-REVIEW / ACCEPTED / BLOCKED。
   初始内容：P0 三个工作包为 IN-PROGRESS，P1–P8 为 TODO（只列名称，不展开）。

# 验收
- 五个智能体定义字段齐全、允许写入范围互不冲突、无"可提交/可推送"权限。
- 门禁文档中的"必须裁决"清单与公共前言完全一致（逐条可对照）。
- 工作包卡片的允许写入范围与本阶段文件归属表一致、互不重叠。
- PROGRESS.md 的状态词与更新规则自洽。
- 不出现尚不存在的命令或目录引用。

# 交接
按公共前言 H 格式。额外列出：五个智能体的一句话职责；门禁表摘要；你对工作流的任何担忧。
````

### WP-C：机器门禁 Agent

````text
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
````

## 6. 持续协作门禁

### 6.1 门禁流程

| 门禁 | 时机 | 责任人 | 通过标准 |
|---|---|---|---|
| G0 立项 | 工作包开始前 | 计划 Agent 出卡片 | 目标、范围、非目标、允许写入、验收齐全 |
| G1 提示词审查 | 派发前 | 总设计师 | 不越界；允许写入与其他包不重叠；验收可执行；回复 `PROMPT-OK` |
| G2 实施自检 | 交付时 | 专项 Agent | 交接单完整；验证命令有真实输出 |
| G3 工程审查 | G2 之后 | 总设计师 | 复跑验证命令；检查变更文件仅在允许范围；结论 ACCEPT / REWORK / ESCALATE |
| G4 用户裁决 | 仅触发条件满足时 | 用户 | 对裁决请求单给出明确选择；记入决策记录 |
| G5 提交同步 | G3（及 G4）通过后 | 总设计师 | `make check` 绿、工作区干净、无密钥；提交、推送、更新进度与变更日志 |

### 6.2 工程师可决定与必须用户裁决

| 类别 | 总设计师（工程师）可自行决定 | 必须用户裁决 |
|---|---|---|
| 文档 | 措辞、结构、示例、排版 | 题目与论文范围、创新点表述 |
| 算法 | 实现手法的等价改写、性能小优化 | 目标函数、约束语义、邻域层级、冲突诊断策略的**设计变化** |
| 评估 | 脚本结构、绘图样式 | 基线定义、指标定义、统计协议、评测集构成 |
| 数据契约 | 不改语义的字段文档补充 | 契约冻结与任何字段或语义变更 |
| 依赖 | 在已批准许可证范围内的等价工具选择 | GPL/LGPL/AGPL/未声明许可证；任何外部服务、费用、密钥 |
| 仓库 | 命名细节、工具配置、测试补充 | 仓库可见性、许可证；删除或重命名受保护文件；改写历史、强制推送 |
| 流程 | 工作包拆分与顺序微调 | 偏离 design_v2 或 codex_spec；阶段范围变化；进度重排 |
| 研究伦理 | — | 涉及真实实验室数据、真人测试、个人信息 |

**升级规则**：遇到右列事项即发出"裁决请求单"。**未裁决的事项阻塞该项，其他不相关工作可继续**；不得以"先做着看"绕过。

### 6.3 停线触发

任一发生即暂停该工作包并通知总设计师：越界写入；出现 P1+ 业务代码；密钥或个人信息进入文件；规则文档与机器规则不一致；测试被削弱或跳过；未经裁决改动设计。

### 6.4 持续性措施

- 每个后续工作包都按 G0 到 G5 走一遍，计划和提示词先出、先审。
- 进度只在验收提交里更新，避免状态与代码不同步。
- 每次发现规格冲突，先写决策记录再改规格，规格版本号递增并在文首列出修正清单。

## 7. 需要用户解答的真实阻塞

我只列确实需要用户决定、总设计师无法自行探测的事项：

1. **设计文件传递**：请把会话里的 v2 与开发规格两个文件下载到仓库外的暂存目录，并告知路径。否则 WP-A 的导入项会被标为 BLOCKED，其余内容不受影响。
2. **仓库可见性与许可证**：`cc703/Replan-mutil-agent` 是公开还是私有？这决定能否提交调研数据与评测集，也决定是否添加 LICENSE 以及选哪种。**未裁决前：P0 不添加 LICENSE，不提交任何调研原始数据。**
3. **Git 提交者身份**：用于提交的 `user.name` 和邮箱用什么？若仓库公开，建议使用 GitHub 提供的 noreply 邮箱以保护隐私。

下列事项我给了默认值，不构成阻塞，但请顺带确认：

| 事项 | 默认 | 说明 |
|---|---|---|
| 文档与提交语言 | 文档中文，标识符与提交信息英文 | 记录为 ADR 0005，待你确认 |
| 默认分支 | `main` | 总设计师可自行探测远端 |
| 操作系统与 `make` | 未知 | 总设计师可自行探测；Makefile 已设计为薄委托，没有 make 也可直接运行 `tools/*.py` |
| GitHub 认证 | 总设计师先用 `git ls-remote` 探测 | 失败才需要用户处理 |

**还需提醒的一点**：布局检查器提前到 P0 是我的建议，已在 3.1 标注，请总设计师在 G1 时确认。
