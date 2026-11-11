# C2 Claude 收尾增量（2026-11-11）

来源：https://claude.ai/chat/54ab7bfe-2bca-4714-9759-e3ae3e5474e7 消息86；页面Sonnet 5.5 Medium。以下按实际DOM文字转录完整计划与提示词，去除按钮/装饰并恢复代码块排版；不是原始Markdown。Claude明确仅依据交接摘要，未声称读过本地temp文件。

## Δ-C2 收尾：消除 assign_times 对输入的原地修改

已接回合作。我恢复 planner / prompt-engineer 角色，沿用 G0–G5 与独立 G3。我没有读过本地文件，也没有读过 temp v001/v002，下面完全依据你给的摘要。我不对 temp 的决定背书，也没有复核已落盘的代码，本包只做这一处修正。

### 一、写入范围（精确）

实施（Terra / high / fork none）：src/scheduler_core/generation/timing.py、src/scheduler_core/generate.py、tests/unit/generation/test_generate_factors.py（只追加新测试，不改既有断言；如追加后单文件超过约350行，停止上报，不擅自新建文件）、docs/agents/handoffs/p1-c2-generation.md（已存在则追加一节“收尾修正”，不改既有内容）。

独立G3只写docs/agents/handoffs/p1-c2-review.md。root管理提示词归档、进度、CHANGELOG、RESUME、派发日志；最终G3 ACCEPT后写回归锁、最终check、提交与推送。

其余一律不动，包括workflow.py、resources.py、dag.py、integrity.py、params.py、README、依赖、io/*、tools、既有测试断言。

建议（可选）：root派发前把timing.py与generate.py现状复制到仓库外临时目录，并在派发日志记录sha256，方便reviewer对照。C2尚未提交，没有git基线可diff。

### 二、实施提示词

```text
[附公共前言、增量 v002] 运行配置：gpt-6.1-terra，推理 high，fork_turns=none。你没有任何先前上下文，以下为全部背景。

# 角色与目标
P1-C2 收尾实施 Agent。修正一处违反 AGENTS "函数不原地修改输入"的问题，其余行为不变。不提交、不推送。

# 背景
generation/timing.py 的 assign_times(tasks, groups, edges, devices, persons, u, tau, params, random)
返回 tuple[int, list[BlockedWindow]]，但会原地修改传入的 Task（release、deadline、deadline_level）与 Person（blocked），
再由 generate.py 组装。磁盘上尚未修复。

# 允许写入
src/scheduler_core/generation/timing.py
src/scheduler_core/generate.py
tests/unit/generation/test_generate_factors.py（只追加新测试，不改、不删既有断言）
docs/agents/handoffs/p1-c2-generation.md（已存在则追加"收尾修正"一节）
其余一律只读。不得改公开签名 generate_instance、输出规则、依赖、README、models、axis、validate*、io/*、tools、docs/source；
不新增 skip 或 xfail；不写黄金哈希常量到任何测试；B1 外移与双 profile 保持延期。

# 修正方案
1 assign_times 保持原参数顺序与含义。开头只对 tasks 与 persons 做深拷贝（model_copy(deep=True) 或等价），其余 groups、edges、devices、params 只读。
2 在副本上执行与原来完全相同的赋值与计算；random（numpy Generator）作为显式消费流继续推进，不复制，不改变抽取的次数、顺序与种类。
3 返回改为 NamedTuple TimingResult(horizon: int, blocked: list[BlockedWindow], tasks: list[Task], persons: list[Person])，
  仍可按四元组解包；返回的 tasks、persons 顺序与输入完全一致，且与输入不共享任何对象或嵌套容器
  （包括 required_skills、compatible_devices、blocked 及其元素）。
4 若 groups 或 edges 内部持有的是 Task 对象引用而不是 id 或下标，不得再用旧对象引用去修改副本：改为按任务 id 建立"id→副本"映射并经映射解析，
  且不得修改 groups 与 edges 本身。若有此情形，在交接单说明处理方式。
5 generate.py 接收 TimingResult，并改用其中的 tasks 与 persons 组装 Instance；不再依赖对原对象的副作用。
6 更新 assign_times 的 docstring：说明输入不被修改、返回新的 tasks 与 persons、random 会被消耗及其抽取顺序不变、返回类型字段含义；
  检查 generate.py 与 timing.py 中没有残留"原地修改"的描述。
7 只读审计：浏览 generation/ 其余模块与 generate.py，查找其他对入参的原地修改；发现则只报告（文件、行、对象），不得修改，状态记为 NEEDS-DECISION。

# 新增回归测试（追加到 test_generate_factors.py，断言到值）
a 输入不变：按 generate.py 的同一调用顺序构造 assign_times 的真实输入（用 params 使 person_absence_prob=1.0、hard_deadline_fraction>0，
  确保每类字段都会被改），对 tasks、persons、devices、groups、edges、params 做 model_dump（或等价深快照），调用前后逐项相等；
  输入任务仍保持调用前的 release、deadline、deadline_level，输入人员的 blocked 仍为调用前内容。
b 返回确有更新且不 alias：返回 tasks 中至少有任务的 release 与 deadline 已被设置、levels 按 params 变化；返回 persons 中至少有人的 blocked 非空；
  对每个任务与人员断言 new is not old，以及 required_skills、compatible_devices、skills、blocked 容器与其元素均不是同一对象；
  顺序与输入一一对应。
c 副作用不再存在：对同一份输入连续调用两次（各用新建的同种子 Generator），两次返回逐字段相等，且调用后输入快照仍等于调用前；
  random 的状态推进两次一致。
d 集成：用 monkeypatch 包装 generate 模块中的 assign_times，记录调用前后的输入深快照，调用 generate_instance 后断言每次调用前后输入相等；
  generate_instance 对同参数两次调用的规范字节相同；传入的 params 对象调用前后不变。
e 若 groups 或 edges 持有对象引用，加一例证明副本与映射一致：返回任务的实验归属、前驱关系与改动前一致。

# 哈希回归（一次性核对，不得写入任何仓库文件）
用 uv run python -c，在 PYTHONHASHSEED 为 0、1、2024 的三个子进程中，对下列参数计算 canonical.instance_to_bytes 的 SHA256，并与期望值逐一比对（共 9 次）：
  S, 0.8, 0.5, seed 0 → d0e16c15f5b841ec6b0b1d00219d25b70164d0c58fccb8579f5845bf7b09869d
  M, 0.6, 0.25, seed 1 → 712e9aebfca29641f62a63d9152d67af1f7562bdcc19dbe4be919d80dbbbf5e5
  L, 0.95, 0.75, seed 2 → a494cad109ae890732063c2631da2c7aca015862a656f1e11ec6bc7d808d1f77
任一不符：停止，记录实际值并上报，不得为"凑哈希"改动抽取顺序。

# 验收命令（真实输出写入交接单）
uv run --python 3.11 --group dev python -m pytest tests/unit/generation -q -p no:cacheprovider
uv run --python 3.11 --group dev python -m ruff check src tests
uv run --python 3.11 --group dev python -m ruff format --check src tests
uv run --python 3.11 --group dev python -m mypy src/scheduler_core/generation src/scheduler_core/generate.py tests/unit/generation
uv run --python 3.11 --group dev python tools/check.py        # 全量检查，仅在上述通过后运行一次
git diff --check
基线：此前联合 G2 为 717 passed、1 个既有 symlink 权限 skip；本次应为 717 加新增测试数，skip 仍为 1，67 个文件的静态检查全过。

# 验收标准
输入不被修改且返回对象不 alias（测试 a 至 e 通过）；三组哈希在三种 PYTHONHASHSEED 下全部一致；
generate_instance 公开签名与输出规则不变；docstring 已更新且无过期描述；
diff 只含允许文件，无新增 skip 或 xfail，无哈希常量入库；其他模块的原地修改审计已报告。

# 交接
公共前言 H 格式，另附：改动清单；groups 与 edges 持有的是 id 还是对象引用及处理；审计结果；9 次哈希核对的真实输出；
全部验收命令的真实输出与通过数；模型、推理档、fork 模式。
```

### 三、独立 G3 提示词

```text
[附公共前言、增量 v002] 运行配置：gpt-6.1-terra，推理 high，fork_turns=none。
角色：P1-C2 收尾独立 G3 审查。只读，只写 docs/agents/handoffs/p1-c2-review.md，不读作者会话。
运行命令加 -p no:cacheprovider；探针只在仓库之外的系统临时目录进行，不得在仓库产生文件。

背景：C2 已有联合 G2 与此前独立 G3（135 实例、180 个 DAG、10007 浮点键等矩阵已验证，不需要机械重跑）。
唯一正式 REWORK 是 API docstring，已补未复审；本次另修正 assign_times 对输入 Task 与 Person 的原地修改。

审查项
1 范围：改动只在 timing.py、generate.py、test_generate_factors.py（仅追加）、p1-c2-generation.md；
  公开签名 generate_instance 不变；依赖、README、其他模块、既有断言未改；无新增 skip 或 xfail；无哈希常量入库；
  若 root 提供了修正前的快照路径，用它做 diff 并核对 sha256。
2 数据不变性（独立探针，不复用作者测试）：按 generate.py 的调用顺序自行构造 assign_times 输入，深快照前后比较，
  覆盖 person_absence_prob=1.0 与 hard_deadline_fraction>0 的情形；确认输入 Task 的 release、deadline、deadline_level 与 Person.blocked 未变；
  确认返回的 tasks、persons 与输入不共享对象及嵌套容器，顺序一致，且字段确有更新；
  若 groups 或 edges 持有对象引用，核对映射处理正确且未被修改。
3 行为不变：random 抽取次数与顺序不变（同种子两次调用 random 状态一致）；
  自行在 PYTHONHASHSEED 为 0、1、2024 的子进程中计算 (S,0.8,0.5,0)、(M,0.6,0.25,1)、(L,0.95,0.75,2) 的规范字节 SHA256，
  与以下期望值逐一比对并记录真实输出：
  d0e16c15f5b841ec6b0b1d00219d25b70164d0c58fccb8579f5845bf7b09869d / 712e9aebfca29641f62a63d9152d67af1f7562bdcc19dbe4be919d80dbbbf5e5 / a494cad109ae890732063c2631da2c7aca015862a656f1e11ec6bc7d808d1f77。
4 docstring：复审 API docstring 的 REWORK 是否已解决（公开函数与类、参数、返回、异常、不修改输入、random 消耗说明）；
  assign_times 的 docstring 与返回类型一致；没有"原地修改"的过期表述；README 短用法与实际行为一致。
5 审计：独立查找 generation/ 其余模块与 generate.py 是否仍有对入参的原地修改，核对作者的审计结论。
6 测试质量：新增测试 a 至 e 有实质断言（快照比较、is not、更新确有发生），而不是只断言不抛异常。
7 复跑交接单中的全部验收命令并记录真实输出，包括全量 check 的通过数；与 717 加新增数的基线核对，skip 仍为 1。
结论 ACCEPT / REWORK / ESCALATE；发现列表（严重度、文件:行、证据、建议）；探针与哈希的真实输出；
未能核实项；模型、推理档、fork 模式。
```

### 四、root 流程

root审G1通过后派发；实施完成后审G3前置材料再派独立G3。独立G3 ACCEPT后root才冻结三组哈希，写tests/unit/generation/test_generate_golden.py，注明“回归锁，不是正确性证据”，同时写入numpy与generator_version。最终全量check，更新进度、CHANGELOG、RESUME，以chm提交，用cc703普通push并核验远端SHA。

推送凭证：CLI此前没有cc703凭证、插件是cc703，若最终仍无法确认推送与远端SHA来源，进度写“未同步”，不能写已同步。清理归档与P2不在本包，待本包同步后另取新包计划。

## root G1 结论

2026-11-11 G1 PASS。本增量明确局部数据副本与RNG显式消费边界，输入输出、随机抽取顺序和规范字节保持。允许的四文件写入明确，独立复审与G5顺序完整；temp历史版本保留来源，不作Claude追认。原文字句“哈希不得写入任何仓库文件”按上下文约束实施测试不得冻结黄金常量，交接仍按其明确要求记录真实哈希输出；既有归档计划中的哈希证据不删除。root额外135样本修正前合并摘要（scale S/M/L→u .6/.8/.95→tau .25/.5/.75→seed0..4依序，对每个canonical字节取SHA256 digest再串联SHA256）为2e976fbbb2358436b516b434d52b90dd065282bc221a30fc9f4564824b2aae9e，供修后差分核对。

独立复审补充：Claude建议的修前源码快照为可选项，root未保存，不能提供真实原件路径或SHA做精确逐行差分，也不将重建版本冒充原件。已提供修前/修后135样本摘要一致、三组历史/9跨hashseed、当前源码与独立不变性探针作为行为证据；此限制须在review交接如实披露，不扩大成无条件全部输入等价证明。
