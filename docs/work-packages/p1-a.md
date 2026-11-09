# P1-A 数据模型与 TimeAxis 实施包

日期：2026-11-09 Asia/Shanghai；基线452b2be，共享分支codex/p0-governance。
G0/G1 PASS：总设计师审查Claude消息66完整计划与提示词，范围仅模型/TimeAxis及必要构建检查；用户已委托按原设计和推荐决定工程细节，见AGENTS、ADR0006。GitHub继续暂缓。
来源：https://claude.ai/chat/54ab7bfe-2bca-4714-9759-e3ae3e5474e7 消息66，DOM innerText渲染捕获，不冒称原始Markdown。完整提示词在下方同一捕获内，供实施/审查直接读取，避免拆出更多准备文件。
实施提示词DOM code.textContent SHA256：750ae8daecfd45c1c46c62c024d1a50dc54746ac1a7af4269b374c4a6f08a673
审查提示词DOM code.textContent SHA256：646cfa64c9a7c19ae4e6d99391d35d7f7d75bae33d9a7f398df83e49fda29697

G1实际派发解释：
- 历史P0公共前言中的“不创建src”被当前P1-A明确源码清单取代；原文仍只读，B1与双profile仍延期。
- axis.py/models.py等省略目录的清单项均在src/scheduler_core/；不创建根axis.py/models.py。
- 本文件从BEGIN到END为总设计师归档保护区，实施者只在END之后补本包卡片/实际验收记录，不改捕获和哈希。总设计师独占AGENTS/ADR/PROGRESS/CHANGELOG/registry/RESUME及本捕获；合法共享树改动不是作者越界。
- 检查工具可在已忽略artifacts/tmp写缓存；pytest用-p no:cacheprovider并报告配置警告，不为关闭缓存改测试语义。
- API、标量限制、默认容器隔离等工程细节在交接与测试中记录；原规格语义不变，模型不得代替未来V1-V11独立校验器。新增派生属性不计序列化字段。
- 三个数据来源延后在P1-B前按工程委托落实；P1-A不实现验证/调度，不因这些来源未定停工，也不判业务已验证。
- 若固定依赖源与先前证据不符，先查官方具体版本；不得静默换栈或安装未来阶段依赖。

<!-- BEGIN CLAUDE P1-A CAPTURE -->
Claude responded: P1-A 计划与提示词
Writing the implementation and review prompts

Writing the implementation and review prompts
P1-A 计划与提示词

以下为提议，我没有修改本地仓库，也没有写代码。

一、计划

范围：P1-A 只做数据契约的模型代码（21 个原模型、Slot/Event 两个别名，加 2 个新模型）和基础测试。校验器、求解器、生成器和 P2 以后都不做。

顺序：先实施，再独立审查，最后由总设计师本地提交；GitHub 不上传。

文件范围

实施 Agent 允许写入	说明
src/scheduler_core/__init__.py、axis.py、models.py	新建
tests/unit/test_axis.py、tests/unit/test_models.py	新建
pyproject.toml、uv.lock	加依赖与 src 配置
tools/check.py	改为覆盖全部 tests、src 的类型与 ruff
docs/engineering/dependency-register.md、README.md	必要说明
docs/work-packages/p1-a.md、docs/agents/handoffs/p1-a.md	本包卡片与交接
独立审查只写	总设计师唯一写
docs/agents/handoffs/p1-a-review.md	AGENTS.md、ADR（含 0006 更新）、PROGRESS、CHANGELOG、提示词归档、git 提交

依赖：只装 pydantic==2.14.3，pydantic-core 作为传递依赖必须锁定为 2.50.4。numpy、hypothesis、ortools 本包不装，Hypothesis 的 MPL 许可未获授权也不装。

命令（Windows 直接入口）


uv add pydantic==2.14.3
uv lock --check
uv sync
uv run python -c "import pydantic, pydantic_core; print(pydantic.VERSION, pydantic_core.__version__)"
uv run python -m pytest tests -q -p no:cacheprovider
uv run python tools/check.py
uv run python tools/check_repo_layout.py
uv run python tools/verify_source.py

三个 OPEN 数据来源（new_end 持久字段、冻结任务 end 对 V11 的影响、NEGOTIABLE 放宽凭证）：P1-A 不新增相关字段，也不构成阻塞。交接单要列出这三项"有意缺席"，并声明没有任何代码把缺数据当通过；工程方在 P1-B 前记录类型与接口。

二、实施提示词

text
[附 P0 公共前言、增量 v002] 运行配置：GPT-6.1 Terra，推理 high，fork none。

# 角色与目标
P1-A 实施 Agent。实现数据契约模型与 TimeAxis，只含结构与基础语义校验。

# 允许写入
src/scheduler_core/__init__.py  axis.py  models.py
tests/unit/test_axis.py  tests/unit/test_models.py
pyproject.toml  uv.lock  tools/check.py
docs/engineering/dependency-register.md  README.md
docs/work-packages/p1-a.md  docs/agents/handoffs/p1-a.md
其余只读。不写 AGENTS.md、ADR、PROGRESS、CHANGELOG，不提交，不上传。
不得实现业务校验器、求解器、生成器、P2 及以后；不改 docs/source、B1 外移、双 profile；不复制第三方源码。

# 输入
docs/source/codex_spec_v1.1.original.md 第 3 节（以原文为准，全部 21 个类加 Slot、Event）；
v2 第 3 节人员与日历；docs/decisions/0006 与 docs/planning/p1-contract-proposal.md 的推荐路线。
默认值与字段一律读原文，不凭记忆。ReplanParams 保留原 num_workers 默认值，不加 profile 字段，Violation 不改。

# 任务
1 依赖：先 uv add pydantic==2.14.3，确认 uv.lock 中 pydantic-core 为 2.50.4，不符则停止上报。
  用临时脚本（放 artifacts/tmp）实测要用的 API：ConfigDict、field_validator、model_validator、
  Field 约束、Field(discriminator)、strict 整数、model_validate_json、TypeAdapter，结果记入交接。
  配置 src：保持 package=false，用 pytest pythonpath 与 mypy_path 指向 src；如另有更好办法须在交接说明理由。
  依赖登记表登记直接与传递依赖（版本取自锁文件，许可证取自已安装元数据）。
2 axis.py 定义 Slot 与 TimeAxis，不得 import models；models.py 从 axis 导入并在 __all__ 重导出，
  保持 scheduler_core.models.TimeAxis 与 .Slot 可用。测试无论先 import 哪个都不循环，且 models.TimeAxis is axis.TimeAxis。
3 TimeAxis 保持原签名 to_slot、to_dt：t0 须带时区，运算统一转 UTC 并用整数 timedelta 运算，不用浮点；
  不对齐槽边界抛 ValueError；naive datetime、bool、非整数槽拒绝；slot_minutes>0、horizon_slots>0；
  槽范围为 0 至 horizon_slots，端点含 horizon 合法，负槽与越界抛 ValueError，类型错误抛 TypeError，
  并在测试中固定异常类型。保守舍入属后续适配层，本包不做。
4 models.py：21 个原模型全部实现并导出，另增 PersonBlockedWindow(start,end，左闭右开) 与
  Person(id, skills:set[str]=空, blocked:list[PersonBlockedWindow]=空)；
  Task 增 required_skills:set[str]=空（多技能为 AND）、requires_person:bool=False（无技能也可要求人）；
  Instance 增 persons=空列表；Assignment 增 person_id:str|None=None。空日历即无阻塞，不得解读为全不可用。
  可提供只读的 needs_person 派生属性（非空技能或 requires_person），不得存为字段。
5 校验边界：只做形状与基础语义：
  正工期、容量、需求；非负槽、权重；时间区间 start<end；PlanMetrics 各值有限且非负（gap 可为 None）；
  Instance 内 devices/tasks/persons 各自 ID 唯一；先后关系两端须存在于 tasks 且非自环；
  Plan.assignments 的键等于 task_id；Event 判别联合可解析，未知 type 拒绝；Slot 类字段拒绝 bool 与 float；
  extra 默认 forbid（有异议须在交接说明）。
  禁止在模型中拦截：未知人员、兼容设备不存在或不兼容、需人员却无 persons、
  截止期早于释放时间加工期（规格 5.2 的不可行例必须能构造）、环、跨实体业务违例；这些留给独立 validator。
  模型默认可变，不设 frozen。
6 测试（要有实质断言，不是只测能 import）：21 个原类加 2 别名齐全并与原文默认值逐项一致；
  新增字段默认与向后兼容（无人员的旧 JSON 加载后行为一致，序列化往返）；
  容器默认值实例间隔离；有限非负指标；正工期/容量/区间；ID 重复；先后引用；
  判别事件的正反例；"该建模层不拦截"的反例（须能构造的业务违例各至少一例）；TimeAxis 各边界与异常；import 顺序。
7 tools/check.py：覆盖全部 tests、src 的 mypy（可启用 pydantic 自带的 mypy 插件）与 ruff，并保持对 tools 与治理测试的原有检查。
  若首次创建 src 使布局检查或依赖边界检查失败，先上报，不得放宽规则。

# 验收
命令全部通过（见上列），治理测试加新增测试通过（原跳过项保持跳过），ruff、mypy 无错；
只装了 pydantic（含传递依赖），无 numpy/hypothesis/ortools；git diff 仅含允许文件；
docs/source 原文与哈希不变；src 下无校验、求解、生成逻辑。

# 交接
公共前言 H 格式，另含：API 实测结果；锁文件中的版本；公开 API 清单；各校验决策与理由；
三项 OPEN 数据来源"有意缺席"清单；所用模型、推理档、fork 模式。
三、独立审查提示词

text
[附公共前言、增量 v002] 运行配置：GPT-6.1 Terra，推理 high，fork none。
角色：P1-A 独立 G3 审查，只读，只写 docs/agents/handoffs/p1-a-review.md，不读作者会话。
运行命令加 -p no:cacheprovider，不得产生仓库内新文件。

审查项
1 逐项对照 codex_spec_v1.1.original.md 第 3 节：21 个类加 Slot、Event 全部存在，字段、类型、默认值一致；
  ReplanParams 保持原 num_workers 默认值且无 profile 字段；Violation 未改。
2 新增项：Person、PersonBlockedWindow、required_skills、requires_person、Instance.persons、Assignment.person_id 与推荐一致；
  技能 AND；无技能可要求人；空日历非全不可用。
3 旧 JSON 兼容：无新字段数据加载与往返；默认容器隔离测试真实有效。
4 职责边界：模型没有提前拦截未知人员、兼容设备、需人员无 persons、规格 5.2 不可行例、环；
  有"能构造这些违例"的反例测试；没有业务校验、求解、生成代码。
5 TimeAxis：原签名；UTC 整数运算；对齐；naive、bool、非整数、负槽、越界；horizon 端点合法；异常类型有测试固定；
  axis 不 import models；models 重导出且无循环。
6 依赖：仅 pydantic==2.14.3，锁中 pydantic-core 2.50.4；无 numpy、hypothesis、ortools；
  依赖登记含传递依赖与许可证来源；uv lock --check 通过。
7 工程：tools/check.py 覆盖全部 tests、src 的类型与 ruff；pyproject 的 src 配置合理；
  布局与依赖边界检查未被放宽；断言质量（排查"只测 import"类空测试）。
8 范围：git diff 仅含允许文件；docs/source 与哈希不变；无 AGENTS/ADR/PROGRESS 改动；无第三方源码复制；
  交接单声明与实际复跑结果一致；三项 OPEN 数据来源确实"有意缺席"，且没有把缺数据当通过的代码。
9 重跑全部验收命令并记录真实输出。

输出：ACCEPT / REWORK / ESCALATE；发现列表（严重度、文件:行、证据、建议）；
命令复跑结果；未能核实项；所用模型、推理档、fork 模式。
四、说明与小提示
提示词中的"禁止在模型里拦截"是为了保证后续 V1、V7 等校验器有构造违例的空间，不要让实施 Agent 为了"更安全"而加严。
数值与版本（pydantic 2.14.3、pydantic-core 2.50.4）按你已核的 PyPI 结论写入，我没有独立核实，提示词已要求实施 Agent 对锁文件做一致性检查。
总设计师更新 ADR 0006 时，请把本轮"工程细节由工程方决定，业务规则变化再问用户"的授权原文一并记录。





1 minute ago
<!-- END CLAUDE P1-A CAPTURE -->

## 实施记录（专项只追加本节）

待实施。

实施初版与检查结果见 `docs/agents/handoffs/p1-a.md`；尚需独立审查，测试覆盖局限以交接为准。

G2 自检完成：61 passed、1 skipped，ruff/mypy、布局、依赖边界和原文核验通过；待独立 G3。

## Claude 全量类型检查范围增补（消息68，2026-11-09）

DOM innerText捕获；总设计师G1 PASS，仅增补两份既存治理测试的类型标注修复，不允许改变测试行为或缩小覆盖。实施及审查提示词如下。

<!-- BEGIN CLAUDE P1-A AMENDMENT -->

text
[附公共前言、增量 v002，并沿用 P1-A 实施提示词的全部范围与约束] 运行配置：GPT-6.1 Terra，推理 high，fork none。

# 角色与目标
P1-A 增补实施 Agent。目标：让 mypy 覆盖 tools、tests、src 全部通过，且不改变任何既有测试行为。

# 新增允许写入（在 P1-A 原范围之外，仅此两个文件）
tests/governance/test_gates.py
tests/governance/test_verify_source.py
并可更新 tools/check.py、docs/agents/handoffs/p1-a.md 以反映本次增补。
其余一律只读。不得改动已落盘的 src 实现与 tests/unit，不提交，不上传。

# 已知错误
test_verify_source.py:101 的 dict 缺少类型参数；
test_gates.py:109、117、120 因 manifest 字典的联合类型推断，导致赋值与下标报错。

# 任务
1 先运行 uv run mypy tools tests src，保存增补前的完整错误清单，要求总数为 6 个，且仅出现在上述两个文件；若有其他错误，停止并上报，不得扩大修改。
2 只允许加类型注解（如显式 dict 类型参数、变量标注）与必要的类型收窄（如局部变量标注或 cast）。
  不得修改任何输入值、字典内容、断言、skip/xfail 标记、参数化数据、测试名称或调用顺序，也不得新增或删除测试。
3 禁止使用 type: ignore、noqa、Any 逃逸掩盖错误、放宽或排除 mypy 配置、改 pyproject 中 mypy 设置、缩小检查范围。
  cast 仅在无法用标注表达时使用，并逐处在交接单说明理由。
4 tools/check.py 的 mypy 调用覆盖 tools、tests、src，并保留原有 ruff 与治理检查；不得改为只查子目录。
5 用增补前后对比证明行为不变：两文件的测试收集数量、各测试结果、skip 项与增补前一致（61 通过、1 跳过，除非增补前另有变化，须说明）。

# 验收
uv run mypy tools tests src 零错误；uv run ruff check 与格式检查通过；uv run python tools/check.py、
uv run python -m pytest tests -q -p no:cacheprovider 结果与增补前一致；uv run python tools/check_repo_layout.py、
uv run python tools/verify_source.py 通过；git diff 仅含上述两个测试文件、tools/check.py、交接单；
diff 中除类型注解与收窄外无语义改动，无忽略指令。

# 交接
公共前言 H 格式，另含：增补前后 mypy 错误清单对比、六处修改的逐处说明、cast 使用清单（如有）、
测试收集与结果前后对比、所用模型、推理档、fork 模式。

# Reviewer 核对（独立 G3，只读，只写 p1-a-review.md 的增补节）
1 逐行审查两个测试文件的 diff：确认仅有类型注解与收窄，输入值、断言、skip、参数化、测试数量均未变化。
2 复跑 mypy tools tests src、ruff、pytest、布局与来源检查，记录真实输出。
3 全仓检索新增的 type: ignore、noqa、Any、mypy 配置变化与排除目录，必须为零。
4 核对 tools/check.py 覆盖范围未缩小，且 src、tests/unit 无改动。
结论：ACCEPT / REWORK / ESCALATE。





1 minute ago
<!-- END CLAUDE P1-A AMENDMENT -->
