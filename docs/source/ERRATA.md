# 勘误与待讨论事项

原文保持不变；建议仅供后续裁决。

## E-001
- 文件：`codex_spec_v1.1.original.md:65`
- 原文摘录：3. 路径与文件名只用小写 ASCII、数字、下划线、连字符，不含空格和中文；中文只出现在文档内容里。
- 问题：命名规则与约定文件和迁移名冲突
- 类型：冲突
- 建议修正：限定例外范围
- 状态：OPEN
- 备注：原规格未修改。

## E-002
- 文件：`codex_spec_v1.1.original.md:109`
- 原文摘录：隐藏文件仅限 `.gitignore`、`.env.example`。除此之外，根目录不得新增任何文件或目录。
- 问题：限制与 Git、环境及缓存目录冲突
- 类型：冲突
- 建议修正：明确本地环境例外
- 状态：OPEN
- 备注：原规格未修改。

## E-003
- 文件：`codex_spec_v1.1.original.md:398`
- 原文摘录：    num_workers: int = 8
- 问题：多线程配置与完全确定性要求存在潜在冲突（另见第 542 行）
- 类型：冲突
- 建议修正：在实施求解器前讨论确定性方案
- 状态：DEFERRED-BY-USER
- 备注：原规格未修改。

## E-004
- 文件：`codex_spec_v1.1.original.md:116`
- 原文摘录：| `src/scheduler_core/` | `models.py` `axis.py` `validate.py` `generate.py` `solve_initial.py` `impact.py` `replan.py` `diagnose.py` `relax.py` `pareto.py`；子包 `baselines/`（`b2_full.py` `b3_rule.py` `b1_llm.py`）、`io/`（`artifacts.py` `manifest.py`） |
- 问题：B1 位置与核心包不依赖大模型原则冲突
- 类型：冲突
- 建议修正：对应模块实施前讨论位置
- 状态：DEFERRED-BY-USER
- 备注：原规格未修改。

## E-005
- 文件：`codex_spec_v1.1.original.md:171`
- 原文摘录：| 图表 | 草稿 png；入库版本用 svg 或 pdf |
- 问题：没有规定图表转换或生成方式
- 类型：过时
- 建议修正：明确原生生成及格式验证方式
- 状态：OPEN
- 备注：原规格未修改。

## E-006
- 文件：`codex_spec_v1.1.original.md:119`
- 原文摘录：| `apps/backend/` | Spring Boot 工程；数据库迁移 `db/migration/V001__init.sql` |
- 问题：迁移路径与 Spring Boot 默认约定需核实
- 类型：冲突
- 建议修正：实施时核对配置与官方约定
- 状态：OPEN
- 备注：原规格未修改。

## E-007
- 文件：`codex_spec_v1.1.original.md:240`
- 原文摘录：| 源码目录无生成物 | `src/`、`apps/`、`experiments/`（`experiments/configs` 除外）下不得出现 `.log .csv .jsonl .png .svg .tmp` 等 |
- 问题：源码目录资源禁令及第 244 行体积限制可能影响前端资源与锁文件
- 类型：冲突
- 建议修正：按路径和文件用途制定例外
- 状态：OPEN
- 备注：原规格未修改。

## E-008
- 文件：`codex_spec_v1.1.original.md:76`
- 原文摘录：- 类型检查：`mypy src`
- 问题：src 尚不存在时该命令可能失败
- 类型：过时
- 建议修正：按阶段选择检查目标
- 状态：OPEN
- 备注：原规格未修改。
