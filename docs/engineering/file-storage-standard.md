# 文件存储规范

版本：v001；阶段：P0；机器规则唯一来源：`tools/layout_rules.toml`。
本文解释规则与操作流程；出现差异时停止相关交付，由总设计师同步修正规则及说明，不能静默选一边绕过。

## 三类数据

| 类别 | 位置 | 入库 | 写入方式 |
|---|---|---|---|
| 人工维护的输入 | data/、experiments/configs/ | 是，来源清晰且不含秘密 | 工作包明确授权，保留数据版本 |
| 可再生中间产物 | artifacts/ | 否，README.md 例外 | P1 后经 ArtifactStore；每运行独立目录 |
| 审核后的最终结果 | docs/results/ | 是 | 用户审核后，由报告工具复制并登记来源 |

设计、规范、工作包和进度本身是需版本管理的项目文档，放 docs/；它们不是实验中间产物。

## 目录职责

| 目录 | 允许内容 | 禁止内容 |
|---|---|---|
| docs/ | 设计、工程规范、决策、角色、工作包、进度 | 未说明的临时实验输出 |
| src/ | 核心、仿真与 Agent 源码；版本化提示词 | 运行日志、数据集、截图、实验图表 |
| apps/ | 前后端源码、局部框架资源 | 构建输出、依赖目录、运行日志 |
| experiments/ | 可复用实验代码、configs/ | 实验生成的 CSV、日志和图表 |
| data/ | fixtures、eval_sets、survey、基准映射 | 私人原始数据、下载的大文件、缓存 |
| tests/ | 测试代码与小型明确 fixture | 测试运行后留下的临时文件 |
| tools/ | 检查和维护工具、机器规则 | 一次性脚本、运行结果 |
| artifacts/ | instances、runs、llm_traces、logs、archive、tmp | 入库的生成物、秘密 |

P0 不创建 src/apps/experiments 的占位业务代码。实际目录按实施阶段需要创建。

### 用户提供的目录规范参考（2026-11-10）

已阅读 [lingxyz/standard《项目目录结构规范》](https://github.com/lingxyz/standard/blob/master/drafts/项目目录结构规范.md)。采纳语义清晰、根目录按职责划分、源码按功能与业务组织、内容资源归属明确的原则；仅作结构参考，不复制原文或代码、不引入依赖。
本项目沿用已审查的 Python 与多应用布局：核心源码在 `src/scheduler_core/`，测试在 `tests/unit/`（治理测试在 `tests/governance/`），人工实例在 `data/fixtures/`，应用代码按需进入 `apps/`，中间产物只在 `artifacts/`。参考中的前端示例目录按实际应用需要建立，不预建空目录；本次不迁移既有文件、不修改机器规则。
2026-11-10 对当前 Git 文件执行布局、导入边界、来源校验及完整检查，布局通过。后续新增代码仍由 `tools/layout_rules.toml` 与工作包文件清单约束。

## 可机器检查规则

### R-root：根目录与检查范围

允许的根项：`AGENTS.md README.md CHANGELOG.md LICENSE Makefile pyproject.toml uv.lock docker-compose.yml .gitignore .gitattributes .editorconfig .env.example .pre-commit-config.yaml .github docs src apps experiments data tests tools artifacts`。
允许不等于必须创建：LICENSE 必须由用户决定项目许可后才能添加；.github 配置按工作包需要建立。

检查以 Git 视角为准：`git ls-files -co --exclude-standard`，涵盖已跟踪项与未忽略的新文件。`.git` 是 Git 元数据，不是项目输出；忽略项不因存在磁盘上而违规，但已跟踪的秘密或缓存必须被检出。

### R-naming：命名分层与例外

- 生成物、data/、experiments/configs/、docs/results/ 默认只用小写 ASCII、数字、下划线、连字符和扩展名点；路径无空格、中文，不允许 `..` 路径逃逸。
- Python 包、模块与函数用 snake_case；不得把全路径大小写统一替换作为修复方式。
- 根约定文件按 R-root 精确列名；README.md、AGENTS.md、CHANGELOG.md 等并非违规。
- docs/ 的一般文档允许中文与大写，推荐英文小写连字符；ADR 使用 NNNN-slug.md。docs/results/ 仍用生成物命名规则。
- Java 类允许 PascalCase；Flyway 仅在 `apps/backend/src/main/resources/db/migration/` 使用 `V<版本>__<描述>.sql`。
- Vue 组件允许 PascalCase.vue，package.json、vite.config.ts 等遵循框架约定。例外只限定相应框架路径，不能放宽 data/ 等位置。
- 新例外在 tools/layout_rules.toml 登记路径、原因与关联工作包，经过总设计师审查。禁止全局 `**` 豁免。

命名例外以 `[[exceptions]]` 数组登记，字段为 `rule`、`scope`、`target`、`pattern`、`reason`；工作包关联在审查记录保留。当前支持 `rule="R-naming"`，`target` 为 `path` 或 `filename`。scope 必须是非全局、固定的相对目录前缀，以 `/` 结尾，不得含 glob、盘符或 `..`；pattern 是首尾锚定的正则表达式，reason 不可空。修改该配置会实际改变检查结果，无需在检查器里再新增硬编码分支。

```toml
[[exceptions]]
rule = "R-naming"
scope = "apps/frontend/"
target = "filename"
pattern = '^[A-Z][A-Za-z0-9]*\.vue$'
reason = "Vue 组件名遵循局部框架约定。"
```

### R-generated：源码不混入生成物

src/、apps/、experiments/ 禁止运行生成的 .log、.csv、.jsonl、.tmp 及实验图表。实验配置留在 experiments/configs/，不能把生成物伪装配置。
前端设计资源在 `apps/frontend/src/assets/`、`apps/frontend/public/` 中允许 .png/.svg；它们是明确的源资源，不是实验输出。文档或工具需要其他资源时必须登记局部例外。

### R-size：体积

一般入库文件不得超过 1 MiB（1,048,576 字节）。uv.lock、前端 package-lock.json 等锁文件按机器规则登记体积例外；fixture 等大文件仍须显式登记，不默认整棵 data/ 放行。
不得拆分无用片段、编码为文本或滥用例外绕过限制；大数据说明来源和获取方式，缓存留 artifacts/。

### R-artifacts：产出物不入库

artifacts/ 唯一可入库文件是 README.md；.gitignore 必须保留该例外并忽略其他所有内容。
被 `git add -f` 强行跟踪的生成物同样违规；已忽略不能成为已跟踪生成物的免责理由。

### R-manifest：运行可追溯

每个 `artifacts/runs/<kind>/<name>/<run_id>/` 目录都必须有合法 manifest.json。kind 取 experiment、sim、agent_eval。name 与标签用小写，例如 e2_replan_micro。
run_id 基式是 `YYYYMMDD-HHMMSS_<git短哈希>_<标签>`；同秒同标签冲突时拒绝覆盖并生成唯一后缀或新的时间标识，实际策略在 ArtifactStore 验收时固定。

| 必填字段 | 含义与约束 |
|---|---|
| run_id、kind、name | 与运行路径一致 |
| status | running / completed / failed / partial |
| started_at、ended_at | UTC 的带时区 ISO 8601；运行中 ended_at 可空 |
| command | 可复现命令，移除秘密 |
| git.commit、git.dirty | 代码提交与是否有未提交改动；不得虚报干净 |
| config_sha256 | 实际配置内容哈希，配置副本须脱敏 |
| seeds | 使用的随机种子 |
| versions | Python、依赖、系统等实际版本信息 |

inputs、outputs、LLM 模型/参数/token 用量、求解器配置为需要时记录的追溯内容；用户暂缓新增 solver_profile 等公共字段，见 ADR 0003（DEFERRED），P0 不以新契约拒绝原规格运行。
运行开始即写 running，结束时原子更新状态；completed 目录不可修改、覆盖或重跑。异常必须保存失败状态；不得伪造 completed。

### R-magic：格式必须真实

PNG 内容应具有 PNG 文件签名；PDF 应具有 %PDF 签名；SVG 应能作为含 svg 根元素的 XML 检查。扩展名与内容不符则拒绝。
绘图阶段原生导出预览 PNG 与最终 SVG/PDF；报告工具复制已有文件，不改扩展名“转换”。仅有 PNG 时保留真实格式并注明限制，是否用作最终结果由用户审核；不能声称它是矢量图。

### R-ignore：本地项隔离

.gitignore 覆盖 `.venv/ .env .mypy_cache/ .ruff_cache/ .pytest_cache/ __pycache__/ node_modules/ .idea/ .vscode/ .DS_Store`；.env.example 可入库且只含占位。
根据后续框架输出增加 build/dist/target 等局部忽略规则；不要把整个源码、工作包或输入数据目录忽略以藏住问题。

## 写入与路径安全

P1 后所有机器产出路径通过 `scheduler_core.io.artifacts.ArtifactStore`；禁止 `open("results.csv", "w")` 或 `savefig("fig.png")` 在当前工作目录留下文件。
路径必须解析并校验处于目标根目录内；拒绝绝对路径、盘符、`..`、指向根外的符号链接或 junction。生成目录时不得追随链接越界。

**P0 bootstrap 例外**：ArtifactStore 尚未实现。总设计师与治理工具可直接创建 `artifacts/tmp/` 的临时治理材料；不能由此绕开业务运行 manifest 或声称已验证 ArtifactStore。测试使用系统临时目录/tmp_path，结束不留仓库文件。调研结论、提示词和验收摘要应提炼为 docs/ 中的正式记录，原始临时捕获不入库。

## 运行布局

一次运行含 manifest.json、config.yaml、raw.csv、summary.csv、events/、plans/、figs/、logs/。求解器日志跟随本次运行，禁止另存无法对应运行的结果目录。
实例缓存应覆盖所有影响生成的参数、生成器版本与种子；仅用一部分参数命名不得宣称内容寻址或可安全复用。
LLM trace 在写盘前去掉 API key、授权头、个人信息与不必要的原始需求；秘密只从环境变量读取。

## 保留与清理

| 对象 | 保留规则 |
|---|---|
| artifacts/tmp/ | 不超过 7 天；程序不得依赖其内容 |
| 失败/中断运行 | 保留 14 天后可清理 |
| completed 运行 | 保留，可在论文定稿后归档 |
| docs/results/INDEX.md 引用的运行 | 永不自动清理，包括其归档映射 |

清理默认 dry-run，列出解析后的绝对路径、依据、大小和引用检查。实际删除需要显式 apply；拒绝根目录、链接越界、正在运行与受引用目录。Windows 清理只操作校验后的目标；不能用递归权限改动影响其他目录。只读标志不等于不可篡改保证，应用层也必须拒绝写入 completed。

## 最终结果与变更

用户审核 → 报告工具检查 completed、git.dirty=false、真实格式和来源 → 复制到 docs/results/figures 或 tables → INDEX.md 登记文件、run_id、完整 commit、配置哈希、生成命令、格式、简述。不得由改名得到 SVG；不得引用不存在的运行。
版本化提示词/评测集使用 v001、v002；不覆盖旧版本。CHANGELOG.md 为明确的元数据例外，不应被 v###.* 规则误拒绝。专项开发提示词见 docs/agents/，与产品内提示词 src/agent/prompts/ 分开。

## 示例

| 违规 | 正确处理 |
|---|---|
| src/solver/results.csv | 通过 ArtifactStore 写 artifacts/runs/.../raw.csv |
| 根目录 notes.txt | 需要长期保留则纳入 docs/ 对应文档；临时则 artifacts/tmp/ |
| experiments/e2/figure.svg 中装 PNG | 原生导出 SVG，或保留 .png 并登记真实格式 |
| data/ProductionDump.sql 含个人数据 | 不提交；先明确授权与脱敏，再决定是否建立合成 fixture |
| 完成运行直接重跑覆盖 | 新建 run_id，保留旧结果及来源 |

P0 验证入口：`python tools/check.py`。当前工具检查 Git 视角文件、规定的忽略路径、格式、体积，以及本地运行目录的 manifest 字段/身份/状态基本完整性；被忽略的运行目录仍接受 manifest 检查。UTC时间语义、run_id 唯一性、哈希真实性、只读生命周期、清理与报告复制属于后续 ArtifactStore/维护工具验收，P0 不声称已经实现全部。
