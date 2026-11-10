# P1-B-R1 校验器可读性重构

日期：2026-11-10 Asia/Shanghai；基线799ea56，分支codex/p0-governance。用户已明确恢复开发，要求简单完整、目录清楚、函数与文件可读，避免单文件过长；此前本轮暂停现已解除。业务规则变化仍需用户裁决，工程组织已委托。Claude原会话消息76完整计划及两份提示词如下，DOM innerText捕获，非原始Markdown；仅去除行尾空白。截图artifacts/tmp/p1-b-r1-plan.png与临时文本仅本地忽略。

捕获文本SHA256：f7d132ad93a09cdd1232e48f1d6a7b2f164bad76a0969315bad0d8a43fb5a1d5。

<!-- BEGIN CLAUDE P1-B-R1 76 -->
Claude responded: 我能正常回应，没有升级服务。下面是 P1-B-R1 的计划与两个提示词，我没有改本地仓库。
Writing the continuation plan for the next steps

Writing the continuation plan for the next steps

我能正常回应，没有升级服务。下面是 P1-B-R1 的计划与两个提示词，我没有改本地仓库。

一、范围与文件清单

目标：行为不变的重构。validate.py 目前只有一个大函数，按职责拆成短函数和少量模块，测试按规则族迁移。不改业务语义，发现疑似缺陷只在交接单报告，不顺手修。

角色	允许写入
实施	src/scheduler_core/validate.py（改为薄入口）、src/scheduler_core/validation/*.py（新建）、tests/unit/validation/*.py（新建）、删除 tests/unit/test_validate.py、README.md（仅更新旧路径）、docs/work-packages/p1-b-r1.md、docs/agents/handoffs/p1-b-r1.md
审查（只读）	docs/agents/handoffs/p1-b-r1-review.md
总设计师	进度、日志、registry、RESUME、AGENTS、coding-standards、提示词归档、Git

禁止改：models.py、axis.py、validation_context.py、依赖与锁文件、tools/、data/fixtures/mini.json、docs/source、原始设计文档。

二、目标结构（推荐，命名可由审查调整）
模块	职责	对应现有大段
validate.py	入口 validate()，保持原签名，只做类型检查、建索引、按固定顺序调用各检查、输出报告	参数检查与总装
validation/report.py	违规收集器、reason=TOKEN; k=v 格式化、稳定排序、生成 ValidationReport	报告格式与排序
validation/index.py	只读实体索引、重复 ID、assignment 键与引用检查	稳定实体索引
validation/assignments.py	V1、V4、非冻结任务的 V10 工期	任务与分配规则
validation/deadlines.py	V5：HARD 期限与 NEGOTIABLE 授权	授权与期限
validation/precedence.py	V3：引用、环（拓扑）、时滞边界	先后关系
validation/baseline.py	冻结集合、V8、V11（parent、free、新增、删除、非 free 变更、冻结 person）	base、free、frozen
validation/execution.py	快照校验、RUNNING 与 DONE 的 V10、超时 end 的 V11 证据	执行快照与证据
validation/occupancy.py	准备时间与设备、人员占用区间构造	占用区间
validation/intervals.py	纯区间算法：最大 end 持有者扫描、事件累计扫、窗口合并与二分；不认识 Task 或 Device	扫描算法
validation/devices.py	V2、V9、V6（调用 intervals，不自己写扫描）	设备资源
validation/running_blocks.py	RUNNING 窗口有效绑定、去重、未绑定输出	RUNNING 窗口
validation/personnel.py	V7	人员

依赖方向：validate.py → validation/* → models、axis、validation_context。validation/* 之间无环，不得反向 import validate.py。

可读性标准（参考而非硬凑行数）：

函数目标约 20–60 行，入口 validate() 不超过约 50 行。
文件通常 150–300 行，相近的小模块可以合并，不为凑行数合并或拆分。
只用小型 dataclass（只读索引、冻结视图、占用区间集合）和违规收集器。
禁止 utils.py 之类万能文件、插件或注册机制、继承或 mixin、动态分发、新依赖。
三、实施提示词

text
[附公共前言、增量 v002，及 P1-B 全部既有约束] 运行配置：GPT-6.1 Terra，推理 high，fork none。

# 角色与目标
P1-B-R1 实施 Agent。把 validate.py 做行为不变的重构：职责清晰、简单完整、代码可读。不提交、不推送。

# 允许写入
src/scheduler_core/validate.py
src/scheduler_core/validation/*.py（新建，含 __init__.py）
tests/unit/validation/*.py（新建；删除 tests/unit/test_validate.py）
README.md（仅更新旧路径）  docs/work-packages/p1-b-r1.md  docs/agents/handoffs/p1-b-r1.md
其余只读。不得改 models.py、axis.py、validation_context.py、依赖、锁文件、tools/、data/、docs/source；
无 solver、replan、simulator、generator、ArtifactStore；不新增依赖；业务源码不得 import random 或 numpy。

# 输入
P1-B 工作包与 70、72、Δ-B1、Δ-B2、G1/G2/G3 记录；两份 P1-B handoff；现有 validate.py 与 test_validate.py；
规格 S:439-441、设计 D:746-764。基线：HEAD 799ea56，162 passed 加原 1 个符号链接 skip；61 个 reason 令牌映射；
测试内 2049 与 3780 个穷举实例（合计 5829）。

# 任务（按顺序）
A 先迁移测试，不动源码：
  1 记录基线：pytest --collect-only 的测试名与参数化 ID 集合、通过与跳过数量。
  2 按规则族拆到 tests/unit/validation/：API 与报告（签名、不变性、确定性、排序、TypeError、AST 导入扫描）、
    assignments、deadlines、precedence、baseline、execution、devices、running_blocks、personnel、穷举 oracle、REASON_COVERAGE。
  3 保留全部原测试函数名、参数化、断言与 oracle；helper 集中在一个小文件，显式导入，禁止通配导入；
    若 pytest 导入需要，可在该目录加 __init__.py；文件基名在全仓保持唯一。
  4 REASON_COVERAGE 仍为 61 个令牌，路径与名称更新为新位置，并有断言保证其引用的测试真实存在。
  5 运行全量测试，确认数量与基线一致后再进入 B。
B 再拆源码（自底向上）：
  1 先抽纯算法 intervals.py，再 report.py、index.py，其余按职责抽出；每步跑全量测试。
  2 validate() 只保留类型检查、建索引、固定顺序调用与出报告；签名、docstring、TypeError 信息、报告字节格式与排序键保持不变。
  3 去重行为与旧实现一致；不顺手修复任何疑似缺陷，发现的问题写入交接单。
  4 结束时旧大函数与嵌套的 add、overlap_scan 不得留在源码里，测试里也不得留旧副本。
C 更新 AST 导入扫描，使其覆盖 validate.py 与 validation/ 下全部模块：
  禁止 ortools、numpy、random；validation/* 不得 import scheduler_core.validate；模块间无环。
D 差分验证（在内存中进行，不落盘）：
  用 git show 799ea56:src/scheduler_core/validate.py 读出旧实现，exec 成临时模块对象；
  用 spy 包装 scheduler_core.validate.validate，让新测试套件每次调用时同时调用旧实现，
  逐字节比较 report.model_dump_json() 与异常类型和消息，任何不一致即失败；
  对 5829 个穷举实例同样做新旧对比。脚本不保存到仓库，结果摘要写入交接单。
E 度量与说明：用 python -c 的 ast 统计各函数与各文件行数，列入交接单；超过约 60 行的函数逐个说明理由，超过 80 行视为未完成。
  README 只改路径引用，不写新说明。

# 验收命令
uv run python -m pytest tests -q -p no:cacheprovider
uv run python tools/check.py
uv run python tools/check_repo_layout.py
uv run python tools/verify_source.py
git diff --name-only

# 验收
- 162 passed 加原 1 skip；测试函数名与参数化 ID 集合除路径外与基线一致，无删减、无重复收集。
- 61 个令牌映射完整；2049 与 3780 的实例数断言保持；确定性、不变性、坏引用检测仍有效。
- 差分验证全部一致（含异常）。
- 模块与函数边界实际可读，而不是把大函数原样搬到另一个文件；无 utils、无继承、无插件、无动态分发。
- check.py 覆盖新模块通过（mypy、ruff）；diff 只含允许文件；无新增依赖；无 type: ignore 与 noqa。

# 交接
公共前言 H 格式。另附：新旧测试名对比结果；差分验证摘要；函数与文件行数表；疑似缺陷清单（仅报告）；模型、推理档、fork 模式。
四、独立审查提示词

text
[附公共前言、增量 v002] 运行配置：GPT-6.1 Terra，推理 high，fork none。
角色：P1-B-R1 独立 G3 审查。只读，只写 docs/agents/handoffs/p1-b-r1-review.md，不读作者会话。
运行命令加 -p no:cacheprovider；探针用 python -c 在内存中进行，不得在仓库产生文件。

审查项
1 范围：git diff 只含允许文件；models、axis、validation_context、依赖、锁文件、tools、data、docs/source 未变；无新功能。
2 API 不变：from scheduler_core.validate import validate 可用；inspect.signature 与 799ea56 版一致；TypeError 行为一致。
3 独立差分：自行在内存中读取 git show 799ea56 的旧实现，用与实施者不同的方式（直接调用，而不是复用其脚本）
  对以下输入逐字节比较报告与异常：全部测试用例、5829 个穷举实例、mini 实例及其篡改计划、
  至少 20 个自造边界实例（容量 4 的 RUNNING 绑定、未绑定窗口、DONE 提前与改写、free 的各种取值、坏引用、环）。
4 测试迁移：基线测试名与参数化 ID 逐一对应；断言未被删改或弱化；REASON_COVERAGE 仍为 61 且引用真实存在；
  2049 与 3780 的实例数断言保留；旧 test_validate.py 已删除；无通配导入；无重复收集。
5 AST 导入扫描覆盖 validate.py 与 validation/ 全部模块；无 ortools、numpy、random；validation/* 不反向 import validate；模块无环。
6 可读性：核对函数与文件行数表真实；每个模块只有一个清楚的职责；intervals.py 是不认识领域对象的纯算法；
  没有把大函数换个文件存放；没有 utils、继承、插件、动态分发、过度抽象；超约 60 行的函数理由成立。
7 复跑全部验收命令并记录真实输出；确认不存在旧实现的残留副本。
结论 ACCEPT / REWORK / ESCALATE；发现列表（严重度、文件:行、证据、建议）；探针结果；模型、推理档、fork 模式。
五、总设计师固化原则（可写入 AGENTS 与 coding-standards，约 5 行）
实现以简单完整为准，一个模块一个职责，不过度设计。
函数约 20–60 行，文件约 150–300 行，仅作审查参考。
不设万能 utils、不用继承、插件或动态分发；共享状态只用小型只读 dataclass。
行为不变的重构必须做新旧差分验证，不顺手修缺陷。
疑似缺陷只在交接单报告，经总设计师决定后另立工作包。
六、后续顺序（一句话）

R1 通过后，先做 C1（ArtifactStore 与 manifest 写入，纯标准库、无新依赖），再做 C2（实例生成器，引入 numpy 前须走依赖登记与版本核实），本包不实现。






just now
<!-- END CLAUDE P1-B-R1 76 -->

## 总设计师 G1 审查与互斥写入范围

G0/G1 PASS；G4为用户已委托工程组织、行为不变重构，无业务变更；G2/G3/G5 PENDING。

- Claude明确模块名单为推荐并允许合并相近小模块。为符合用户简单清晰要求，实施源码范围收敛为：现有src/scheduler_core/validate.py薄入口；新增validation/__init__.py、report.py、index.py、task_rules.py、execution.py、resources.py、intervals.py。report只负责报告；index只建稳定只读索引；task_rules合并分配/释放/工期/期限/先后；execution合并基准/冻结/快照/执行证据；resources合并设备/人员/准备/RUNNING窗的领域规则；intervals只放无领域对象的区间算法。六个实现模块避免十三个零碎文件，不增加通用框架。
- 测试允许仅迁移现有tests/unit/test_validate.py到tests/unit/validation/*.py，使用唯一test文件基名与少量显式helper，按规则族组织；删除旧巨型测试文件属于本包明示授权。原test_validation_context.py以及全部其他既有测试不改。保留全部原函数名/参数化ID/断言；路径扫描和跨文件inventory两处必要适配单独记录；可以提取纯实例构造helper缩短原oracle函数，暴力预言机和断言不得依赖业务实现。函数80行门槛按Claude验收，新旧断言AST对照及收集ID去路径后严格不减不重。
- 公开validate签名、docstring、TypeError类型/消息、报告JSON的细节与稳定排序不变。重构不顺便修bug；疑似缺陷仅报告另立修复包。单一实施者先迁测试并证明162通过/1原skip，再拆源码。共享状态仅本次调用的小型typed视图，禁止继承/mixin/动态注册/万能utils，不引依赖。
- 本卡与handoffs/p1-b-r1.md由实施者仅追加，不改Claude捕获区及本G1；README仅路径调整。独立reviewer只写handoffs/p1-b-r1-review.md。总设计师单写AGENTS、coding-standards、PROGRESS、CHANGELOG、registry、RESUME、实际派发日志并提交同步。除此清单只读；不改原始设计、models/axis/validation_context、依赖/锁文件/工具/mini。
- 新旧差分可在内存读取git show 799ea56的旧实现，用spy运行全部原测试调用（含5829穷举），逐字节比完整report JSON和异常类型/消息。实施及独立审查各自验证，独立审查另加至少20个边界输入。临时捕获仅artifacts/tmp且不能成为业务依赖。验收实际命令使用uv run --python 3.11 --group dev。
- 不实现ArtifactStore/生成器/solver等；R1验收同步后才取得下一包C1计划，Claude额度耗尽时仍按用户条件停止。

## 实施 G2 记录

测试迁移与六个职责模块拆分已完成，实际命令、行数、差分统计和限制见 `docs/agents/handoffs/p1-b-r1.md`。162 passed、1 原有 skip；检查器通过。G3 独立审查待完成，不能将 G2 当成验收或同步。

## G3 结构项返工

容量与跨组扫描、窗口合并及二分已移至纯区间模块；完整检查与 6044 次旧版差分通过，详见实施交接。独立复审待完成。

## 总设计师 G3 集成（2026-11-10）

最终独立G3 ACCEPT，保留首次结构REWORK及closure。root最终树内存差分6042份完整report JSON与2个异常类型/消息一致，六测试模块挂钩；独立reviewer另有35自造边界一致。163收集ID无减/增/重，原34test函数和全部参数化保留，61reason及5829oracle不减。纯扫描已位于105行intervals，领域资源179行，入口67行（函数46行）；所有源函数<=80。原始来源/数据契约/依赖/锁/工具/mini未变，捕获76哈希复核一致。G5待提交同步；用户尚未批准阶段调整，后续仍原顺序先C1，再C2，须新Claude计划，不再扩大本重构。

## G5 同步回执

ead0c62087e933748a824426f32c37676c4d230b已普通推送至origin/codex/p0-governance并核验同SHA，R1 ACCEPTED。总设计师实际复核收集ID163→163，0缺/增/重；最终完整check162 passed/1既有skip、30文件ruff/mypy及layout/import/source全部PASS。当前回执另行提交，不自引用其SHA。
