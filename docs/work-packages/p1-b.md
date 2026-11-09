# P1-B 独立校验器实施包

日期：2026-11-09 Asia/Shanghai；基线ac0ba9f，分支codex/p0-governance。用户工程细节已委托；GitHub暂缓。
G0 PASS；G1 PENDING：消息70初版及消息72完整Δ-B1修订已取回。归档后页面明确显示Claude五小时额度耗尽，触发用户“没有额度就停止”的条件；停止G1后续复核与源码派发。未创建validate.py/validation_context.py，也没有P1-B实施专项。
来源：https://claude.ai/chat/54ab7bfe-2bca-4714-9759-e3ae3e5474e7 消息70，DOM innerText渲染捕获，非原始Markdown；归档时去除表格空单元格产生的行尾制表符，提示词正文未改。以下包含原完整计划和两份派发提示词，不单拆新准备文件；后续增量是同包必读输入。

额度证据：浏览器页面显示“You hit your 5-hour message limit”，并显示8:40 PM恢复；仅记录页面原样提示，不设自动恢复或升级服务。截图位于本地忽略目录artifacts/tmp/p1-b-claude-plan.png，不入库。

恢复入口：用户恢复后先确认Claude可用，再复核消息70+72完整计划与源码范围、CB契约及测试矩阵，G1通过才派发Terra/high实施与独立审查。消息72覆盖原CB2和相关DONE/RUNNING窗口/复杂度，不能只读初版。测试穷举或随机性的实现方式仍需按现行AGENTS核对，未在本检查点批准。GitHub仍不上传。

<!-- BEGIN CLAUDE P1-B 70 -->
Claude responded: P1-B 独立 Validator：计划与提示词
Ran a command

Ran a command
P1-B 独立 Validator：计划与提示词

以下为提议，我没有改本地仓库，也没有写实现。读取原文后，已核对你给的行号：S:439-441 是 validate 签名，S:512-543 是黄金与篡改测试，D:746-764 是 V1–V11 表，D:260 与 D:409 是 RUNNING 冻结与预计结束。

一、计划

顺序：实施，再独立 review，最后总设计师本地提交。GitHub 不上传，不装新库，不改 pyproject.toml、uv.lock、tools/check.py。B1 外移与双 profile 保持延期。

实施 Agent 允许写入	审查 Agent 只写	总设计师写
src/scheduler_core/validate.py、validation_context.py	docs/agents/handoffs/p1-b-review.md	AGENTS、ADR、进度、日志、提示词归档、git 提交
tests/unit/test_validate.py、test_validation_context.py
data/fixtures/mini.json（手工，仅实例）
README.md（必要说明）
docs/work-packages/p1-b.md、docs/agents/handoffs/p1-b.md

models.py、axis.py、__init__.py 保持不动。

验收命令：


uv run python -m pytest tests -q -p no:cacheprovider
uv run python tools/check.py
uv run python tools/check_repo_layout.py
uv run python tools/verify_source.py
git diff --name-only

要求：62 通过加新增测试全部通过，原 1 项跳过不增，无新增 skip 或 xfail，mypy、ruff 全绿，diff 只含上表文件。

二、契约附录 CB（两个提示词都要附上）

CB-1 签名与报告


validate(inst: Instance, plan: Plan, *, base: Plan | None = None,
         free: AbstractSet[str] | None = None,
         context: ValidationContext | None = None) -> ValidationReport
原三参数调用保持兼容。
不修改任何入参；语义上有问题的输入不抛异常，只返回违规，仅类型错误抛 TypeError。
Violation.code 仍只用 V1–V11。细分原因写入 detail，格式固定为 reason=TOKEN; k=v; ...，列表一律排序。
违规排序键：(V 序号, 排序后的 task_ids, device_id, detail)。passed 当且仅当 violations 为空。

CB-2 validation_context.py（Pydantic、extra=forbid、可 JSON 往返；只序列化往返，不落盘）

类型	字段
ExecutionRecord	task_id、status（RUNNING/DONE）、device_id、`person_id
ExecutionSnapshot	plan_id、as_of、records
FrozenEndChange	task_id、plan_id、base_plan_id、old_end、new_end、confirmation_id、acted_at（仅超时延长）
DeadlineAuthorization	task_id、plan_id、original_deadline、relaxed_deadline、confirmation_id、acted_at、`valid_until
RunningBlockBinding	device_id、start、end、task_id
ValidationContext	`snapshot

声明：这只是结构校验，不证明授权真伪，confirmation_id 是不透明字符串，校验器不核实其存在。真实性由上层 L1/L2 负责，不能靠传一个 bool 豁免硬约束。

CB-3 失败码职责与 reason 令牌

码	职责	令牌
V1	应排任务恰一台已知兼容设备；计划不含未知或不可排任务	MISSING_ASSIGNMENT、UNKNOWN_TASK、UNKNOWN_DEVICE、DEVICE_NOT_COMPATIBLE、EMPTY_COMPATIBLE_LIST、UNKNOWN_DEVICE_REF、TASK_NOT_SCHEDULABLE
V2	cap=1 设备上任务（含准备时间）互斥；RUNNING 占用窗口	DEVICE_OVERLAP、RUNNING_BLOCK_OVERLAP、RUNNING_BLOCK_UNBOUND、RUNNING_BLOCK_BINDING_INVALID、SETUP_RULE_CONFLICT
V3	先后与时滞（含等号）；引用与环	PRECEDENCE_MIN_LAG、PRECEDENCE_MAX_LAG、PRECEDENCE_UNKNOWN_TASK、PRECEDENCE_CYCLE
V4	释放时间；非冻结任务 start≥now	RELEASE_VIOLATED、START_BEFORE_NOW
V5	截止期与授权	DEADLINE_EXCEEDED、AUTH_NOT_APPLICABLE、AUTH_EXPIRED、AUTH_FUTURE、AUTH_OUT_OF_SCOPE、AUTH_DUPLICATE
V6	CLOSED/MAINT/FAULT 窗口（含准备时间）与视野	CALENDAR_BLOCKED、HORIZON_EXCEEDED、SETUP_BEFORE_ORIGIN
V7	人员	MISSING_PERSON、UNKNOWN_PERSON、SKILL_MISSING、PERSON_OVERLAP、PERSON_UNAVAILABLE
V8	冻结任务设备与开始时间	FROZEN_DEVICE_CHANGED、FROZEN_START_CHANGED、NO_FROZEN_REFERENCE、FROZEN_MISSING
V9	cap>1 累计需求；单任务 demand>capacity	CAPACITY_EXCEEDED、DEMAND_EXCEEDS_CAPACITY
V10	工期与执行快照	DURATION_MISMATCH、RUNNING_NO_SNAPSHOT、SNAPSHOT_STALE、SNAPSHOT_PLAN_MISMATCH、SNAPSHOT_RECORD_INVALID、END_MISMATCH、DONE_NO_EVIDENCE、DONE_END_AFTER_NOW
V11	父版本、free、冻结 end 证据、冻结 person	PARENT_MISMATCH、BASE_REQUIRED、FREE_UNKNOWN_TASK、FREE_CONTAINS_FROZEN、ADDED_NOT_FREE、REMOVED_NOT_FREE、BASE_TASK_UNKNOWN、NONFREE_CHANGED、FROZEN_PERSON_CHANGED、FROZEN_END_NO_EVIDENCE、FROZEN_END_EVIDENCE_INVALID

可按需增加令牌，但必须在 README 登记且有测试。

CB-4 语义规则

冻结集 F：状态为 RUNNING 或 DONE；或有 base 且 base 中该任务 start<now（PENDING 或 SCHEDULED）。
状态覆盖：
PENDING 与 SCHEDULED：必须有分配，非冻结者 start≥now，end−start 等于 duration。
RUNNING：必须有分配与快照记录。设备与 start 等于快照，end 等于 max(planned_end, as_of+remaining_estimate)。只接受证据支持的超时延长，不预测提前；实际提前完成属 DONE 与后续仿真事件。
DONE：有 actual_end 证据则 end 等于它；无证据则分配必须与 base 完全一致，否则 DONE_NO_EVIDENCE；且 end≤now。
FAILED、CANCELLED、INTERRUPTED：不得有分配。历史由 base 保留，若 base 有其分配则该任务须在 free 内。
快照绑定：snapshot.plan_id 等于 base.id；无 base 时等于 plan.id。as_of 须等于 inst.now。
V8、V11：
冻结任务的设备与 start 以 base 为参照，无 base 则以快照为参照，都没有则失败。
有 base 时，冻结任务 end 变化须有匹配的 FrozenEndChange（绑定 task、plan、base，old_end 等于 base end，new_end 等于计划 end 且大于 old，acted_at≤now，且与快照预计一致），否则失败。
冻结任务 person 变化为 V11。
有 base 时要求 plan.parent_id==base.id。
free=None 表示不检查邻域范围（V11-b 跳过），set() 表示任何任务都不能变。free 给定而 base 缺失为 BASE_REQUIRED。
非冻结且不在 free 的任务，其 device、start、end、person 任一变化为 NONFREE_CHANGED；新增与删除任务同理。
容量：占用区间为 [start−setup, end)；RUNNING 与 DONE 任务不含准备时间。setup 缺省 0，同 (设备, 类型) 值冲突报 SETUP_RULE_CONFLICT 并取较大值。cap=1 做 V2 排序扫描；cap>1 做 V9 差分累计，半开区间且先结束后开始。demand>capacity 的任务只报 V9，不进入扫描。
窗口：CLOSED、MAINT、FAULT 先合并并集，每个任务每个合并窗口只报一次 V6，含准备时间，不报 V2。RUNNING 类窗口：经 RunningBlockBinding 与快照匹配的，只豁免其所有者自身，且要求设备相同、window.end 等于计划 end、window.start 在 [record.start, as_of] 内；未绑定的按满容量阻塞，不得猜测归属。
视野：end>horizon 报 HORIZON_EXCEEDED；非冻结任务 start−setup<0 报 SETUP_BEFORE_ORIGIN。
人员：执行区间 [start,end)，不含准备时间。需人员（needs_person）者必须有已知人员且技能全覆盖（AND）。可选填人的任务同样验证已知、互斥与日历。空日历表示无阻塞，边界半开。
截止期：HARD 不可放宽。NEGOTIABLE 默认按硬，仅在存在完整、适用、未过期的授权时用 relaxed_deadline，且只影响 V5。作用于 HARD、未知任务、原值不符、plan 不符的授权，一律报 V5，不静默忽略。
防御：对用 model_construct 或事后修改造成的坏模型（未知引用、空兼容列表、环）也要报告，不崩溃。
三、实施提示词

text
[附公共前言、增量 v002、P1-A 实施的通用约束与契约附录 CB] 运行配置：GPT-6.1 Terra，推理 high，fork none。

# 角色与目标
P1-B 实施 Agent。实现独立 Validator V1–V11。纯 Python 标准库加既有 models，不 import ortools、numpy、random，不复用任何求解逻辑。

# 允许写入
src/scheduler_core/validate.py  validation_context.py
tests/unit/test_validate.py  tests/unit/test_validation_context.py
data/fixtures/mini.json  README.md
docs/work-packages/p1-b.md  docs/agents/handoffs/p1-b.md
其余只读。不改 models.py、axis.py、pyproject、uv.lock、tools/check.py；不实现 solver、replan、simulator、生成器、ArtifactStore；不装新库；不 skip/xfail；不提交、不上传。B1 外移与双 profile 保持延期。

# 输入
规格 S:439-441、512-543；设计 D:260、D:409、D:746-764；契约附录 CB（本提示词附带）；docs/planning/p1-oss-research.md 中已核的 OR-Tools 与 PyJobShop 问题分解，只借鉴思路，不复制源码。

# 任务
1 先在 docs/work-packages/p1-b.md 写入三项 OPEN 数据来源的最小可序列化工程契约（执行快照、冻结 end 变更证据、NEGOTIABLE 截止期授权），逐字对应 CB-2，并声明"结构校验不证明授权真伪，上层 L1/L2 负责，不得以 bool 豁免硬约束"；再实现 validation_context.py 及其测试（完整性、非负槽、拒绝 bool 与浮点、relaxed≥original、JSON 往返、extra 拒绝）。
2 实现 validate.py：按 CB-1 至 CB-4。排序加扫描，禁止按 horizon 逐槽循环与全任务两两比较；冲突报告用"当前最大 end 持有者"法，保证每个冲突至少被报一次且输出数量不超过任务数。输入不可变，报告顺序稳定，对打乱输入顺序结果一致。
3 手工写 data/fixtures/mini.json（仅实例）：D1、D2 容量 1；视野 40；now=0；A(4)、B(4，前驱 A)、C(6)、D(6)，均兼容两台设备。
4 测试，断言必须精确到 code、reason、task_ids：
  每个令牌至少一正一反；V2、V3、V4、V5、V9 等号相接通过；缺失上下文；伪造或不适用证据（任务、plan、base、原值、过期、未来、重复、HARD）；
  容量含准备时间；重复与重叠阻塞窗口只报一次；RUNNING 自占用、绑定与未绑定、故障窗口；视野边界与负准备起点；
  人员矩阵（需人而无 persons、可选填人仍验互斥与日历、技能 AND、空日历、半开边界）；
  状态覆盖（PENDING、SCHEDULED、RUNNING、DONE、FAILED、CANCELLED、INTERRUPTED）与历史不丢；free=None、set()、base 缺失、parent 不符、新增、删除、未知任务；
  确定性与不变性（deepcopy 或 model_dump 前后相等）；用 model_construct 构造坏引用、空兼容列表、环；
  巨大视野（如 10**9）仍瞬时通过；AST 扫描 validate.py 与 validation_context.py 无 ortools 与其他禁用 import；
  mini 手工计划（D1：A 0–4、C 4–10；D2：D 0–6、B 6–10）通过，篡改重叠与先后关系分别检出对应码。不宣称其为最优解。
5 README 增加 Validator 用法、CB-3 令牌表、CB-4 要点、并说明：OR-Tools 与 PyJobShop 示例不能替代独立验证。
6 交接单须含：令牌与测试的覆盖对照表（每个令牌对应的正反测试名）；工程保守取值清单（INTERRUPTED 与 FAILED 的处理、setup 冲突取较大值、视野映射到 V6、parent 必须等于 base.id、free=None 语义、快照绑定、RUNNING 窗口绑定）；遇到的业务歧义只报告证据，不自行改规则；验收命令的真实输出；模型、推理档、fork 模式。

# 验收
全部验收命令通过；diff 仅含允许文件；覆盖对照表无空缺；未发现的令牌都已在 README 登记。
四、独立审查提示词

text
[附公共前言、增量 v002 与契约附录 CB] 运行配置：GPT-6.1 Terra，推理 high，fork none。
角色：P1-B 独立 G3 审查。只读，只写 docs/agents/handoffs/p1-b-review.md，不读作者会话。
运行命令加 -p no:cacheprovider；探针用 python -c 在内存中构造对象，不得在仓库产生文件。

审查项
1 范围：git diff 只含允许文件；models.py、axis.py、依赖与 checks 未变；无求解、重规划、仿真、生成、ArtifactStore；无 skip 或 xfail；docs/source 哈希不变。
2 独立性：AST 确认无 ortools、numpy、random 与 solve 类 import；无按 horizon 逐槽循环、无全量两两比较。
3 签名：原三参数调用兼容；入参不变；报告排序稳定；passed 等价无违规；语义问题不抛异常。
4 逐条核对 CB-3 与 CB-4：V1–V11 职责与令牌；状态覆盖；冻结集；快照绑定；RUNNING 预计结束、只接受证据延长；DONE 证据；free 与 base 语义；容量含准备时间；V2、V6、V9 去重；窗口先合并；RUNNING 窗口绑定与未绑定；视野；人员矩阵与空日历；截止期与授权。
5 上下文：三项 OPEN 契约与 CB-2 一致；字段完整、可往返；没有任何以 bool 或空上下文放行硬约束的路径；缺、错、过期、越范围都返回对应码。
6 探针（至少）：需人无 persons；可选填人重叠；free=None 与 set()；绑定与未绑定 RUNNING 窗口；setup 占用叠加；重复阻塞合并；DONE 无证据且 base 不变与已变；对 HARD 的授权；打乱输入顺序；10**9 视野；model_construct 坏引用与环。
7 测试质量：每个令牌正反例；断言含 code、reason、task_ids，不是只断言 passed；覆盖对照表与测试名逐一对应；mini 黄金与篡改。
8 重跑验收命令并记录真实输出。

输出：ACCEPT / REWORK / ESCALATE；发现列表（严重度、文件:行、证据、建议）；探针结果；工程保守取值清单的评价（是否改变业务规则）；未能核实项；模型、推理档、fork 模式。
五、两点提示
V10 与 V11 的耦合：RUNNING 的预计结束在 V10 里由快照推出，在 V11 里由 FrozenEndChange 证明变更，两处必须自洽（new_end 等于预计结束）。审查要专门探测"快照与证据不一致"。
容量与阻塞去重是最容易重复计数的地方，已在 CB-4 第 5、6 条钉死：calendar 类窗口只报 V6，task 间只报 V2 或 V9，RUNNING 类窗口只报 V2。





4 minutes ago
<!-- END CLAUDE P1-B 70 -->

## Claude 修订 Δ-B1（消息72，2026-11-09）

本增量覆盖原CB2及对应DONE/RUNNING窗口/复杂度条款；DOM innerText渲染捕获。

<!-- BEGIN CLAUDE P1-B 72 -->
Claude responded: P1-B 契约附录最小修订
Writing test cases for the window binding and early completion rules

Writing test cases for the window binding and early completion rules
P1-B 契约附录最小修订

以下为对 CB 的最小修订，其余原计划不变，我没有改本地仓库。

一、CB-2（完整替换，一个文本块）

text
# 通用：全部为 Pydantic BaseModel，extra=forbid，可 JSON 往返，只做结构校验。
# Slot 沿用 axis.Slot（非负整数，拒绝 bool 与 float）。所有 *_id 为去首尾空白后非空的 str。
# 列表默认空且实例间隔离。字段写法：名称: 类型 = 默认值   # 约束

ExecutionRecord
  task_id: str
  status: Literal["RUNNING", "DONE"]            # 必填
  device_id: str
  person_id: str | None = None
  start: Slot
  planned_end: Slot | None = None               # RUNNING 必填且 > start；含义=base 版本中该任务的 end；DONE 必须为 None
  remaining_estimate: Slot | None = None        # RUNNING 必填（≥0）；DONE 必须为 None
  actual_end: Slot | None = None                # DONE 必填且 > start；RUNNING 必须为 None
  event_id: str                                 # 执行事件 ID：RUNNING 为最近状态上报，DONE 为 TASK_END 事件。
                                                # 不是人类确认，禁止命名或解释为 confirmation

ExecutionSnapshot
  plan_id: str
  as_of: Slot
  base_as_of: Slot | None = None                # 生成 base 版本时的 now，≤ as_of；有 base 且含 DONE 记录时校验器要求非 None
  records: list[ExecutionRecord] = []           # 同一 task_id 至多一条（模型层拒绝重复）
                                                # 约束：RUNNING 记录 start ≤ as_of；DONE 记录 actual_end ≤ as_of

FrozenEndChange                                 # 仅用于"仍在 RUNNING 的任务因超时延长 end"
  task_id: str
  plan_id: str                                  # 绑定新计划 plan.id
  base_plan_id: str                             # 绑定 base.id
  old_end: Slot
  new_end: Slot                                 # 约束：new_end > old_end
  event_id: str                                 # TASK_OVERRUN 执行事件 ID，不是人类确认
  acted_at: Slot                                # 事件时间

DeadlineAuthorization                           # 唯一表示"上层 L1 人类确认"的类型
  task_id: str
  plan_id: str
  original_deadline: Slot
  relaxed_deadline: Slot                        # 约束：≥ original_deadline
  confirmation_id: str                          # 校验器只做结构与绑定检查，不证明真伪，不核实其存在
  acted_at: Slot
  valid_until: Slot | None = None               # 非 None 时 ≥ acted_at

RunningBlockBinding                             # 把 RUNNING 类阻塞窗口绑定到其所有者任务
  device_id: str
  start: Slot
  end: Slot                                     # 约束：end > start
  task_id: str

ValidationContext
  snapshot: ExecutionSnapshot | None = None
  end_changes: list[FrozenEndChange] = []
  deadline_authorizations: list[DeadlineAuthorization] = []
  running_block_bindings: list[RunningBlockBinding] = []
二、CB-3 与 CB-4 的修订

CB-3 令牌

V2：删除 RUNNING_BLOCK_OVERLAP；RUNNING_BLOCK_UNBOUND 仅在未绑定窗口被某任务占用重叠时报告，窗口未被占用则不报。
V10：新增 DONE_HISTORY_REWRITTEN。

CB-4 条款替换

第 2 条 RUNNING 与 DONE 行

区分执行证据与人类确认。ExecutionRecord 与 FrozenEndChange 的 event_id 是执行事件 ID；只有 DeadlineAuthorization.confirmation_id 表示上层 L1 确认。
RUNNING：end 必须等于 max(planned_end, as_of+remaining_estimate)。有 base 时，record.planned_end 必须等于 base 中该任务 end，否则 V10 SNAPSHOT_RECORD_INVALID。plan end 不等于 base end 时，必须有匹配的 FrozenEndChange：task、plan.id、base.id 吻合，old_end 等于 base end，new_end 等于 plan end 且等于预计结束，acted_at≤now；缺失为 V11 FROZEN_END_NO_EVIDENCE，不符为 FROZEN_END_EVIDENCE_INVALID。plan end 等于 base end 却带了 FrozenEndChange，同样为 FROZEN_END_EVIDENCE_INVALID，不静默忽略。缩短 end 违反预计结束等式，报 V10 END_MISMATCH。
DONE：end 必须等于 actual_end（TASK_END 执行事件，不需要 FrozenEndChange）。
允许真实完成时间早于或晚于 base end，但只限"新完成"：有 base 且 base 含该任务分配时，若 actual_end > snapshot.base_as_of，plan 的 end 可与 base 不同；若 actual_end ≤ base_as_of（完成早于 base 的生成时刻），分配必须与 base 完全一致，否则 V10 DONE_HISTORY_REWRITTEN，用于禁止改写已完成的历史。
有 base 且有 DONE 记录而 base_as_of 为 None，报 V10 SNAPSHOT_RECORD_INVALID。
无 DONE 记录时，分配须与 base 完全一致，否则 V10 DONE_NO_EVIDENCE。
DONE 的设备或 start 变化报 V8；person 与 base 或记录不一致报 V11 FROZEN_PERSON_CHANGED。
删除原"所有冻结 end 变化都需 FrozenEndChange"一句；该证据只适用于仍在 RUNNING 的任务。

第 3 条 增加 base_as_of 的绑定说明。

第 6 条 RUNNING 窗口（替换）

RUNNING 类窗口本质是 owner 占用在 Plan 中已有的重复表示。
有效绑定：绑定与窗口完全一致，要求同时满足：
快照中有该任务的 RUNNING 记录；
设备相同；
window.end 等于计划 end；
window.start 在 [record.start, as_of] 内；
无重复绑定。
有效绑定后，该窗口不新增任何阻塞，owner 按自身 demand 在 V2 或 V9 扫描里只计一次。因此容量 4 的设备上，demand 为 1 的 owner 与其它 demand 为 1 的任务可以合法并行。
绑定无效：任一条件不满足，包括缺少快照记录、任务不是 RUNNING、任务没有分配、绑定指向不存在的窗口，都报 V2 RUNNING_BLOCK_BINDING_INVALID，与是否重叠无关。
未绑定窗口：按满容量保守处理，仅当某任务与其重叠时报 V2 RUNNING_BLOCK_UNBOUND；未重叠则通过，不凭猜测豁免。

第 5 条复杂度与报告（替换原"每个冲突至少报一次且不超过任务数"）

V2 与 V7 的重叠采用"按 start 排序、当前最大 end 持有者"扫描。验收口径：
凡参与任意重叠的任务，至少出现在一条违规的 task_ids 中；
每个冲突连通分量至少产生一条违规；
同一资源上的重叠违规条数不超过该资源任务数减 1；
不声称枚举全部重叠对。
V9 在每个最大溢出段内，报告该段内出现过的活跃任务并集。
复杂度写作 O(n log n + 输出规模)，禁止隐藏的全量两两比较和按 horizon 逐槽循环。
V6 窗口合并后用二分定位，复杂度为 O((n+m) log(n+m)+输出规模)。
三、实施提示词增量（附在原实施提示词之后，冲突以本增量为准）

text
增量 Δ-B1
1 任务 1 中三项 OPEN 的契约改为逐字使用本次 CB-2 文本块，写入 docs/work-packages/p1-b.md 与 validation_context.py；
  声明：event_id 是执行事件 ID，不是人类确认；只有 DeadlineAuthorization.confirmation_id 由上层 L1 负责且校验器不证明其真伪。
2 任务 2 的报告与复杂度口径改为 CB-4 第 5 条修订；DONE、RUNNING 与窗口语义按 CB-4 第 2、3、6 条修订；令牌按 CB-3 修订并更新 README。
3 任务 4 必须新增以下正反测试（断言精确到 code、reason、task_ids）：
  a 容量 4 设备：RUNNING owner（demand 1）加有效绑定窗口，与 3 个 demand 1 的任务并行合法；总需求超 4 时只报 V9 一次，owner 只计一次。
  b 有效绑定不新增阻塞；容量 1 设备上其它任务与 owner 重叠，只报一条 V2 DEVICE_OVERLAP，不出现 RUNNING_BLOCK 令牌。
  c 未绑定 RUNNING 窗口：与任务重叠报 RUNNING_BLOCK_UNBOUND；任务避开窗口则通过（容量 4 与容量 1 各一例）。
  d 绑定无效各一例：缺快照记录、任务非 RUNNING、任务无分配、设备不符、window.end≠计划 end、window.start 越出 [record.start, as_of]、
    窗口不存在、重复绑定；均报 RUNNING_BLOCK_BINDING_INVALID，且与是否重叠无关。
  e 真实 DONE 提前完成：base end=10，record.actual_end=8，base_as_of=5，plan end=8，通过且无需 FrozenEndChange；end=9 报 END_MISMATCH；
    无记录且 end 变化报 DONE_NO_EVIDENCE。
  f 真实 DONE 超时完成：actual_end=12>base end，base_as_of 早于 12，通过。
  g 历史不可改：actual_end≤base_as_of 而 plan end 与 base 不同报 DONE_HISTORY_REWRITTEN；一致则通过；
    有 base 与 DONE 记录而 base_as_of 为 None 报 SNAPSHOT_RECORD_INVALID；DONE 的设备或 start 变化报 V8。
  h RUNNING 延长：证据正确通过；缺证据报 FROZEN_END_NO_EVIDENCE；缩短报 END_MISMATCH；end 未变却带证据报 FROZEN_END_EVIDENCE_INVALID；
    FrozenEndChange 与 ExecutionRecord 传入 confirmation_id 被 extra=forbid 拒绝，DeadlineAuthorization 缺 confirmation_id 被拒绝。
  i 复杂度与覆盖：用固定种子随机小实例，在测试中用 O(n²) 暴力法作为预言机：
    V2 与 V7 违规的 task_ids 并集等于暴力法得到的"参与任意重叠的任务集合"；违规条数≤资源任务数−1；
    n 个完全相同区间只产生不超过 n−1 条而非 n(n−1)/2 条；V9 的溢出段与逐点求和一致；保留 10**9 视野的瞬时测试。
4 交接单的令牌覆盖表补充上述新增令牌与测试名；其余不变。
四、审查提示词增量

text
增量 Δ-B1（审查）
1 核对 docs/work-packages/p1-b.md 与 validation_context.py 的字段、类型、默认、约束与 CB-2 文本块逐字一致；
  ExecutionRecord 与 FrozenEndChange 不含 confirmation_id；只有 DeadlineAuthorization 含，且无任何用 bool 或空上下文放行硬约束的路径。
2 DONE 路线与 V11 一致：真实提前或延后完成通过且无需 FrozenEndChange；历史（actual_end≤base_as_of）不可改；无记录且变化则失败；
  RUNNING 只接受证据支持的超时延长；缩短失败。
3 RUNNING 窗口：有效绑定不新增阻塞，容量大于 1 时 owner 只按自身 demand 计一次；未绑定仅冲突时失败，避开则通过；
  任何绑定无效（含缺 record）失败，且不凭猜测豁免。
4 复杂度与报告：确认没有声称枚举全部重叠对、没有逐 horizon 循环或隐藏的全量两两比较；暴力法预言机测试存在且有效；
  违规条数上界成立；V9 报告口径为段内活跃任务并集；README 复杂度表述为 O(n log n + 输出规模)。
5 复跑上述 a–i 对应测试，并用内存探针补测：容量 4 owner 加并行、未绑定窗口避开、DONE 提前、DONE 改写、RUNNING 缩短、多余证据。
结论仍为 ACCEPT / REWORK / ESCALATE，其余沿用原审查提示词。

简评：本次修订把"执行证据"与"人类确认"在类型层面分开，所以重规划不再误拒真实的提前完成。扫描器的覆盖口径也改成了可由暴力预言机检验的说法，不再声称枚举全部重叠对。






1 minute ago
<!-- END CLAUDE P1-B 72 -->
