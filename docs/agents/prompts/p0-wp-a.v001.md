<!-- 来源: docs/source/p0_claude_plan_v001.original.md:291-354; 来源 SHA256: 82d49292f1342dce3c5348b5176d7cf029fe6fd10ddf61d884276ba8e61286f6; 摘录 SHA256: dcb5f4cc5add936d5acb26ae164bc596b38bcaa03202d7cb8e81eb65388d3b04; 原文逐字，历史内容须服从现行 AGENTS 与用户裁决。 -->
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
