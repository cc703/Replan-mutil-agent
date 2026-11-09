# Claude prompt excerpt

Source: docs/work-packages/p1-claude-plan.v002.md ; message 64, code block 1.
Capture: exact DOM code.textContent; sha256 3cb33168792343ef951c5555ea7a14e921b37f7608b0e5e43bfd2987ef368b8c.

Source capture SHA256: 5f95467e7f6bfd38b95769b2ac356604562226ffb3bd2b3d9be140e5b21355a9; lines 42-91.

<!-- BEGIN CLAUDE PROMPT -->
[附公共前言、增量 v002 与"本轮共同规则"] 运行配置：GPT-6.1 Terra，推理 high，fork none。

# 角色
OSS-1：项目级开源调研 Agent。只读调研，只写两个文件。

# 目标
为调度、校验、日历与测试的契约设计找可借鉴的开源实现，并核实 P1 依赖版本；结论分三类：仅参考 / 拟复制代码 / 新增依赖。

# 允许写入
docs/planning/p1-oss-research.md
docs/agents/handoffs/p1-oss.md
其余只读。

# 不可违反
- 既定方案是 OR-Tools CP-SAT，调研结果不得提出替换它；不得提出引入与之竞争的求解框架作为主线。
- 不安装、不下载包、不改依赖文件与锁。
- 许可证未核实的代码不得归入"拟复制代码"，一律"仅参考"。
- 所有事实必须来自官方来源（项目仓库、官方文档、PyPI 官方页面），记录检索日期；记不清的写"未核实"，不得凭记忆。

# 任务
A 项目级调研（必选）
1. OR-Tools 官方 job-shop、flexible job-shop 示例，以及人员排班类示例（如 nurse/shift scheduling 一类，以官方实际目录为准）。
2. PyJobShop。核实其求解后端、建模对象（资源、技能、约束）、测试组织方式。
3. 可选：1–3 个其他多技能资源调度或 RCPSP 类开源项目，自行检索，说明入选理由；不凑数。
对每个项目固定 release 标签或完整 commit SHA，记录：仓库与官方文档链接；LICENSE 与 NOTICE 的文件路径及结论；
Python 3.11 与 Windows 支持（依据 requires_python、classifiers、官方说明，写明依据）；
官方模块路径与相关文件路径（在固定版本下逐一核对存在）；
可借鉴点，分四类：建模、校验、日历/不可用窗口、测试；局限；分类（仅参考/拟复制/新增依赖）及理由；
若归入"拟复制代码"：给出许可证义务（署名、NOTICE 等）与需用户裁决的事项。

B 依赖版本核实（不安装）
4. pydantic（v2 系列）、numpy、pytest（现有 8.3.5）、hypothesis：
   当前最新稳定版本及发布日期；适用于 Python 3.11 + Windows 的推荐固定版本（有对应 cp311 win_amd64 wheel，或说明为纯 Python）；
   与 pytest 8.3.5 的兼容性依据；许可证；"最新版是否更适合"的判断与理由（最新未必兼容）。
5. 附带：ortools 的同类核实，仅为对齐官方示例版本，不引入。

C 借鉴映射
6. 把调研结果映射到 P1-0 的六个议题：人员资源建模、人员日历（以阻塞窗口表示）、V7 人员校验、设备容量（V2 与 V9）、
   时间取整策略、测试方法（含属性测试）。每个映射写：来源条目编号、可借鉴做法、不适用之处。
7. 列出未核实项与风险；列出需要用户裁决的事项。

# 验收
- 每个项目条目含：固定版本、检索日期、LICENSE/NOTICE 路径与结论、Python 3.11/Windows 依据、官方模块路径、借鉴点四类、局限、分类。
- 依赖矩阵每行含版本、发布日期、requires_python、wheel 情况、许可证、来源链接。
- 没有"拟复制代码"条目缺少许可证证据；没有建议替换 CP-SAT。
- git diff 仅含上述两个文件；依赖文件与锁文件无变化；无 src/。
- 治理测试、ruff、mypy、布局检查、verify_source 通过（运行测试时使用 -p no:cacheprovider）。

# 交接
公共前言 H 格式。另附：项目清单与分类汇总表；未核实项；需用户裁决事项；所用模型、推理档、fork 模式。
<!-- END CLAUDE PROMPT -->
