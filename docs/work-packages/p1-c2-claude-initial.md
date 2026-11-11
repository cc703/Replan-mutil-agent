# P1-C2 Claude 初版完整捕获

2026-11-10，来源 https://claude.ai/chat/54ab7bfe-2bca-4714-9759-e3ae3e5474e7 ，消息82，页面Sonnet 5.5 Medium。以下为DOM innerText捕获，不是原始Markdown。G1未通过；已请求Δ-C2，不得直接实施本初版。

<!-- BEGIN CLAUDE P1-C2 INITIAL -->
Claude responded: P1-C2 实例生成器：计划、契约与提示词
Ran a command

Ran a command
P1-C2 实例生成器：计划、契约与提示词

以下为提议，我没有修改本地仓库。

输入核对：已读取并核对原文，spec 的 sha256 为 59e84a27…cb651c，与你给的一致；S:41、139、212、470-471、553 与 D:413、423、1131-1137 均核对无误，原文无缺。未在本会话读到 C1 源码，所以 paths.py 的函数名和 ArtifactStore.root 属性是否存在要由实施 Agent 先读源码确认，这不构成阻塞。

一、范围与文件清单

范围：只做生成器、规范序列化和缓存。不做求解、仿真、事件、前后端、实验评估、清理归档，不返回正式 Plan。

不引入 YAML 解析库：C4 的核心依赖白名单不含 YAML，而 C2 不需要读文件。参数用类型化的 GeneratorParams（默认值即规格表）。YAML 加载留给实验运行包（P8），那时再单独核实依赖并更新边界。这是工程决定，不涉及业务规则。

新增依赖只有 numpy：官方固定版本、许可证、Python 3.11 与 Windows wheel 由实施 Agent 在编码前核实，不凭记忆写最新版本。Hypothesis 不引入。

类别	精确文件
源码（新建）	src/scheduler_core/generate.py（入口，保持规格路径）；src/scheduler_core/generation/__init__.py、params.py、rng.py、resources.py、workflow.py、timing.py、canonical.py；src/scheduler_core/io/instance_cache.py
测试（新建）	tests/unit/generation/generation_oracle.py（独立 oracle，不 import 生成模块）、test_generate_inputs.py、test_generate_structure.py、test_generate_factors.py、test_generate_determinism.py、test_generate_canonical.py；tests/unit/io/test_instance_cache.py
依赖（限定）	pyproject.toml（仅加 numpy 固定版本）、uv.lock（uv lock 重新生成）、docs/engineering/dependency-register.md（仅 numpy 一行）
文档	README.md（生成器与缓存的简短用法）、docs/work-packages/p1-c2.md、docs/agents/handoffs/p1-c2.md
条件限定	src/scheduler_core/io/paths.py：仅在缺少可复用的函数时，新增包内公开别名或小函数，不改既有语义；src/scheduler_core/io/artifacts.py：仅在没有公开只读 root 时，加一个只读属性。两处都须写入交接单，新测试只放 test_instance_cache.py，不改既有测试
审查只写	docs/agents/handoffs/p1-c2-review.md

禁止改：models.py、axis.py、validate*、validation*、io 的 manifest/errors/provenance、tools/、layout_rules.toml、data/fixtures、docs/source、原设计文档。

root 单写：PROGRESS、CHANGELOG、registry、RESUME、派发日志，以及 Git。提交用 cc703，作者 chm，普通 push 并核验远端 SHA，不碰 main。

二、契约 CB-C2（两个提示词都引用）

text
# 1 公开 API
from scheduler_core.generate import generate_instance
generate_instance(scale: Literal["S","M","L"], utilization: float, deadline_tightness: float, seed: int,
                  *, params: GeneratorParams | None = None) -> Instance
# 前四个参数保持原签名；params 是仅关键字的兼容扩展，None 表示默认。
# 纯函数：不读写文件，不读当前时间，不用全局随机状态，不修改入参，返回新对象。
# 返回的任务一律 PENDING，now=0，无 RUNNING、FAULT 阻塞，无授权。不返回 Plan，不涉及求解。
# 输入检查：类型错误 TypeError；值错误 ValueError。
#   scale 必须是 str 且属于 {"S","M","L"}；utilization、deadline_tightness 为 int 或 float，拒绝 bool、NaN、inf；
#   utilization ∈ [0.05, 1.0]；deadline_tightness ∈ [0.0, 1.0]；seed 为 int（拒绝 bool），0 ≤ seed ≤ 2**63-1。

# 2 规模表（取自 D:1131-1137，不可覆盖）
S: 20 任务 / 5 设备 / 6 实验；M: 60 / 10 / 15；L: 150 / 20 / 35。实验数即 DAG 连通块数，数量必须精确相等。

# 3 参数含义（这是生成参数，不是求解指标，不声称可行或最优）
时间锚点常量 ANCHOR_T0 = 2026-01-05T00:00:00+00:00，slot_minutes=5，一天 288 槽，now=0。
任务负载 W = Σ duration × demand（不含准备时间）。
设备开放容量 C(H) = Σ_d capacity_d × open_d(H)，open_d(H) 为 [0,H) 内不在 CLOSED 窗口中的槽数。MAINT 不计入此定义。
nominal_utilization = W / C(H)。
视野：H_u = 满足 nominal_utilization ≤ utilization 的最小 H；H = max(H_u, max_e CP_e)。
H 被关键路径抬高（clamped）时 nominal < utilization，utilization 是上界。
实验 e 的 ef_i = duration_i + max(0, max over 前驱 p 的 (ef_p + lag_min))，CP_e = max_i ef_i。
实验释放 r_e = floor(U_e × release_span × (H − CP_e))，U_e ∈ [0,1) 取自 releases 子流；实验内所有任务 release = r_e。
截止期：m(τ) = 1 + (1 − τ) × K（K = deadline_slack_span，默认 3.0）；
        deadline_i = min(H, r_e + ceil(m × ef_i))。τ=1 即只留关键路径，τ=0 即最松。
        命名档位（文档约定，不解析）：宽松 0.25，中等 0.5，紧 0.75。
        deadline_level 默认 NEGOTIABLE；hard_deadline_fraction 默认 0.0（取非零时按 deadline 子流抽取 HARD）。
DAG 深度：每个实验有 k 个任务，层数 L = clamp(ceil(dag_depth_ratio × k), 1, k)，默认 dag_depth_ratio=0.6；
        k 个任务分入 L 层（每层 ≥1，用 workflow 子流抽切点）；除第 0 层外每个任务必有 1 条来自上一层的前驱，
        其余跨层前向边按 extra_edge_prob（默认 0.15）加入；边只从低层指向高层，故无环，且实验内最长链恰为 L。
        lag_min 在 [0, lag_min_max] 内均匀取整（默认 2），lag_max 本包不生成。
深度只能通过 params 改变，原四参数签名下取默认。实验间不生成任何边。

# 4 随机子流（numpy，核实官方 API 后实施）
STREAMS = ("resources","workflow","attributes","lags","setups","skills","persons","calendars","maintenance","releases","weights")，只追加不重排。
每个子流 = Generator(PCG64(SeedSequence(seed, spawn_key=(索引,))))，各子流互相独立；同一子流的抽取次数只取决于 scale、params、seed。
依赖关系：workflow、attributes、resources、setups、skills、lags、weights 不依赖 utilization 与 deadline_tightness；
        H、releases、maintenance、person 窗口依赖 utilization；deadline 只依赖 deadline_tightness 及上游结果。
这是对"Generator(PCG64(seed)) 加独立子流"的工程解释，须在交接单明确写出，供 root 在 G1 确认。

# 5 实体规则（默认值为工程默认，不是评估协议）
GeneratorParams（pydantic，strict、extra=forbid、frozen），字段含默认：
  dag_depth_ratio=0.6, extra_edge_prob=0.15, lag_min_max=2, duration_min=3, duration_max=18,
  device_type_count={S:3,M:4,L:5}, cap_gt1_fraction=0.2, demand2_prob=0.15, multi_type_prob=0.2,
  setup_prob=0.3, setup_max=3, closed_calendar_fraction=0.4（每日 20:00 至次日 08:00 的 CLOSED 窗口，含起始 [0,96)）,
  maint_fraction=0.3, maint_min=6, maint_max=24, release_span=0.5, deadline_slack_span=3.0, hard_deadline_fraction=0.0,
  persons_per_device=0.6（人数 max(2, ceil(设备数×该比例))）, skill_count=3, min_skill_holders=2,
  skill_task_prob=0.4, two_skill_prob=0.2, person_no_skill_prob=0.1, person_absence_prob=0.3。
设备：类型轮转分配（每类至少 1 台）；部分设备容量 2 至 4；capabilities 含其类型标签。
任务：type 对应一个主设备类型，multi_type_prob 概率可兼容第二类；demand 为 1 或 2；
      compatible_devices = 满足 capacity ≥ demand 的候选设备，若为空则 demand 降为 1；duration 取整数 [duration_min, duration_max]。
人员：技能子集，每项技能持有者 ≥ min_skill_holders；任务技能组合必须被某一人员完整覆盖（AND）；
      requires_person=True 且无技能的任务由 person_no_skill_prob 抽取；人员窗口为至多一个缺勤 PersonBlockedWindow。
设备窗口：仅生成 CLOSED（周期）与 MAINT；不生成 FAULT 与 RUNNING。MAINT 位置在 [0, H−长度) 内，可与 CLOSED 重叠。
准备时间：SetupRule 对 (设备, 任务类型) 唯一，slots ∈ [1, setup_max]。
ID：experiment "e001"，任务 "e001-t01"，设备 "d01"，人员 "p01"。输出列表顺序固定。

# 6 规范序列化（canonical.py）
instance_to_bytes：Instance → UTF-8 JSON，键排序，集合转为排序列表，datetime 为 UTC ISO，allow_nan=False，末尾换行。
instance_from_bytes：严格解析并校验。相同对象在任何 PYTHONHASHSEED 下字节完全一致。

# 7 缓存（io/instance_cache.py）
InstanceCache(store: ArtifactStore)：路径由 store 的 root 派生，复用 C1 的路径守卫、链接拒绝、原子写、只读函数，不另写一套，不直接 open 落盘。
get_or_generate(scale, utilization, deadline_tightness, seed, *, params=None, verify_regeneration=False) -> Instance
目录：<root>/instances/<scale_token>_u<repr(float u)>_t<repr(float τ)>_s<seed>，scale_token = small、medium、large；
      params 非默认时追加 _p<params_sha256 前 8 位>。内含 instance.json（规范字节）与 meta.json。
meta.json（严格模型、extra=forbid）：schema, generator_version, scale, utilization, deadline_tightness, seed,
      params_sha256, instance_sha256, numpy_version（仅信息，不参与校验）。
流程：目录存在则严格校验后复用——meta 与键一致、generator_version 与 params_sha256 一致、instance 字节哈希一致、
      解析后再规范序列化与原字节一致；verify_regeneration=True 时再重新生成并逐字节比较。
      任一不符抛 CacheConflictError（ArtifactError 的子类），绝不覆盖、绝不静默重建。
      不存在则：mkdtemp(stage-…) 写入两文件并设只读，再 os.rename 为最终目录；失败清理 stage，不留半成品；
      目标已存在（并发）则丢弃自己的 stage，转而校验并复用。
输入先校验，非法输入不创建任何目录。
缓存是实例数据，不是运行，不写 run manifest；清理与归档不在本包。
三、实施提示词

text
[附公共前言、增量 v002、契约 CB-C2] 运行配置：gpt-6.1-terra，推理 high，fork_turns=none。

# 角色与目标
P1-C2 实施 Agent。实现实例生成器、规范序列化与缓存。简单完整，职责清楚，函数约 20–60 行、文件约 150–300 行，
无框架与万能 utils。不提交、不推送。

# 允许写入
src/scheduler_core/generate.py  generation/{__init__,params,rng,resources,workflow,timing,canonical}.py  io/instance_cache.py
tests/unit/generation/{generation_oracle,test_generate_inputs,test_generate_structure,test_generate_factors,test_generate_determinism,test_generate_canonical}.py
tests/unit/io/test_instance_cache.py（及 __init__.py）
pyproject.toml（仅 numpy）  uv.lock  docs/engineering/dependency-register.md（仅 numpy 一行）
README.md（简短用法）  docs/work-packages/p1-c2.md  docs/agents/handoffs/p1-c2.md
条件限定：io/paths.py 与 io/artifacts.py 仅按 CB-C2 第 7 节的前提做最小增补，并在交接单记录。
其余只读。禁止：改 models、axis、validate*、validation*、io 的 manifest/errors/provenance、tools、layout_rules.toml、data、docs/source；
引入 YAML、Hypothesis 或其他新依赖；solver、仿真、事件、实验、清理；新增 skip 或 xfail；业务源码 import random。
B1 外移与双 profile 保持延期。

# 先做（无输出文件，结果记入交接单）
1 uv run python tools/verify_source.py。
2 读取 C1 源码（io/paths.py、io/artifacts.py）：确认可复用的路径守卫、链接检查、原子写、只读函数名与 ArtifactStore 的 root 属性。
3 核实 numpy：官方来源（PyPI 元数据、numpy 官方文档与 LICENSE）确定固定版本、发布日期、许可证、requires-python 含 3.11、
  Windows cp311 wheel；核实与 mypy 1.15.0 的类型兼容；核实官方对 Generator 跨版本流稳定性的说明。
  然后 uv add numpy==<版本>，uv lock --check，并在 dependency-register 登记。核实不过关则停止上报。
4 在已装版本上用 uv run python -c 实测要用的 API：SeedSequence(entropy, spawn_key=…)、PCG64(seedseq)、
  Generator.integers（含 endpoint）、random、permutation、choice(replace=False)，结果记入交接单，不凭记忆写。

# 任务
按 CB-C2 实现。顺序：params 与 rng → canonical → workflow → resources → timing → generate 入口 → instance_cache。每步跑全量测试。
入口 generate.py 只做输入校验、取子流、调用各职责模块并组装 Instance，约 50 行以内。
对各因素的抽取次数只依赖自身输入（保证子流隔离）。任何模块不得使用 numpy 全局随机状态。

# 测试（tmp_path；断言精确到值；独立 oracle 只用标准库，不 import 生成模块）
输入：scale 为 None、"XL"、"s"、1；utilization 与 deadline_tightness 为 True、nan、inf、-inf、0.049、1.001、-0.1、"0.5"；
  seed 为 True、-1、1.0、"1"、2**63；边界值 0.05、1.0、0.0、1.0、0、2**63-1 通过；GeneratorParams 拒绝额外字段与错误类型；
  入参与 params 调用前后不变；非法输入不创建任何文件。
结构（三个规模 × utilization {0.6, 0.8, 0.95} × deadline_tightness {0.25, 0.5, 0.75} × seed 0 至 4）：
  任务数、设备数、实验数与规模表精确相等；ID 唯一；全部引用存在；无环（oracle 自写拓扑）；
  每个实验最长链恰为 L = clamp(ceil(0.6×k),1,k)；边不跨实验；同实验任务 release 相同；
  duration 为范围内正整数；compatible_devices 非空且 capacity ≥ demand；
  技能组合被某人员完整覆盖，每项技能持有者数达到 min_skill_holders；needs_person 语义与字段一致；
  窗口 start<end、在 [0,H] 内、人员窗口按序；设备窗口仅 CLOSED 与 MAINT；SetupRule 的 (设备, 类型) 唯一；
  时间轴 UTC aware、now=0；全部任务 PENDING，无授权；
  用 validate(inst, 空 Plan) 断言违规的 reason 集合恰好是 {MISSING_ASSIGNMENT}，不出现 EMPTY_COMPATIBLE_LIST、UNKNOWN_DEVICE_REF、
  PRECEDENCE_UNKNOWN_TASK、PRECEDENCE_CYCLE 等结构类令牌。
因素：oracle 独立计算 nominal_utilization；未 clamped 时 nominal ≤ u 且 H−1 处的 nominal > u（最小性）；clamped 时 nominal < u 且 H 等于最大 CP；
  同 seed 改变 utilization 或 deadline_tightness：DAG、duration、type、demand、技能、设备、setup 逐字相同；
  改变 deadline_tightness：只有 deadline 变化，release、H、其余全部相同，deadline 随 τ 增大单调不增，
  τ=1 时 deadline == min(H, r_e + ef_i)，τ=0 时与公式一致；
  改变 utilization：H 单调不增（u 增大），releases 与 MAINT 随之变化而结构不变；
  改变 params.dag_depth_ratio：深度按公式变化，durations 等不变；改变 maint_fraction：只有 MAINT 窗口变化；
  改变 seed：任意两个不同 seed 的字节哈希不同（至少 10 个 seed 互不相同）。
确定性：同参数重复调用字节一致；subprocess 以 PYTHONHASHSEED 为 0、1、2024 各运行一次，哈希一致
  （用 sys.executable，并显式传 PYTHONPATH）；调用前后 numpy 全局随机状态不变；
  一个固定的黄金哈希回归用例（S, 0.8, 0.5, seed 0），注释说明 numpy 或生成器变更时必须更新并在交接单说明；
  子流隔离：对每个子流独立调用其生成函数，确认互不影响（同一子流重复取得相同序列，不同子流不同）。
规范序列化：往返字节相等；集合以不同插入顺序构造得到相同字节；allow_nan=False 生效；末尾换行；键排序。
缓存（root 为 tmp_path 下的 ArtifactStore）：首次创建目录名符合 CB-C2、两文件只读；再次调用复用且不再调用生成器（monkeypatch 计数为 0）；
  非默认 params 得到带 _p 后缀的独立条目；损坏用例各一：instance 截断、哈希不符、meta 多余字段、meta 缺失、目录下多余文件、
  instance.json 是目录、generator_version 不符、params_sha256 不符；均抛 CacheConflictError 且已有字节不变；
  instance 与 meta 哈希同时被篡改时，普通模式复用（报告为已知限制），verify_regeneration=True 抛 CacheConflictError；
  注入失败（写文件、chmod、rename）后无最终目录且无 stage 残留，随后重试成功；
  并发模拟（最终目录在检查后、rename 前被另一份合法内容建好）时复用；
  Windows 上用 mklink /J 把 instances 层或其子路径设为指向仓库外的 junction，调用失败；
  直接写入只读文件抛 PermissionError；非法输入不创建目录；不 import random 与 ortools（AST 扫描生成与缓存模块）。

# 验收命令
uv run --python 3.11 --group dev python tools/check.py
uv run --python 3.11 --group dev python -m pytest tests/unit/generation tests/unit/io/test_instance_cache.py -q -p no:cacheprovider
uv run --python 3.11 --group dev python tools/check_repo_layout.py
uv run --python 3.11 --group dev python tools/verify_source.py
git diff --check
git diff --name-only

# 验收标准
250 passed 加原 1 symlink skip 的基线不降，新增测试全部通过，无新增 skip 或 xfail；ruff、format、mypy 全绿；
diff 只含允许文件；只新增 numpy 一项依赖且已登记并锁定；仓库中无运行产物与密钥；
新增行为都有对应测试，没有只验证自己的一次输出的用例；模块职责清楚，无框架与万能 utils。

# 交接
公共前言 H 格式，另附：numpy 核实证据（版本、日期、许可证、wheel、官方稳定性说明）；API 实测结果；
对"PCG64 加 SeedSequence 子流"解释的说明；两处条件限定增补（如有）；默认参数清单及"为工程默认、非评估协议"的声明；
行数表；已知限制（含篡改且哈希一致时普通模式不检出）；未做项（YAML、清理、归档）；模型、推理档、fork 模式。
四、独立审查提示词

text
[附公共前言、增量 v002、契约 CB-C2] 运行配置：gpt-6.1-terra，推理 high，fork_turns=none。
角色：P1-C2 独立 G3 审查。只读，只写 docs/agents/handoffs/p1-c2-review.md，不读作者会话。
命令加 -p no:cacheprovider；探针只能在仓库之外的系统临时目录进行。

审查项
1 范围：git diff 只含允许文件；models、axis、validate*、tools、layout_rules.toml、docs/source 未变；无 YAML、Hypothesis；
  依赖只新增 numpy（pyproject 与 uv.lock 一致，uv lock --check 通过）；登记表有版本、许可证、来源；基线 250 passed 加 1 skip 不降；无新增 skip 或 xfail。
2 numpy：独立复核官方来源（版本、许可证、3.11 与 Windows wheel、类型兼容、对 Generator 跨版本流稳定性的说明）；
  核对交接单的 API 实测；确认生成代码不使用全局随机状态，不 import random。
3 契约：逐条核对 CB-C2 的签名、输入范围、规模表、utilization 与 deadline_tightness 的公式、H 规则、DAG 深度规则、
  子流表与依赖关系、实体规则、canonical、缓存目录名与流程；检查生成物不含 RUNNING、FAULT、授权、Plan。
4 独立探针（在内存中，自写 oracle，不复用测试 oracle）：对至少 3 个规模 × 3 个 u × 3 个 τ × 5 个 seed 复核
  规模表、无环、最长链、跨实验无边、引用完整、技能 AND 覆盖、人员与设备窗口、setup 唯一、nominal_utilization 与最小性、
  deadline 公式；对同 seed 变化 u、τ、dag_depth_ratio、maint_fraction，核对"变化的因素变了、无关的因素不变"；
  用不同 PYTHONHASHSEED 子进程核对字节一致；用 validate(inst, 空 Plan) 核对违规 reason 集合恰为 {MISSING_ASSIGNMENT}。
5 缓存与 C1 边界：确认落盘只经 C1 的守卫与原子写，没有直接 open 落盘；复用不重建；
  各类损坏、冲突、失败注入、并发、junction 用例都有断言，且既有字节不变、无 stage 残留；已有内容不会被覆盖；
  "篡改且哈希一致时普通模式不检出、verify_regeneration 可检出"被如实披露；
  对 paths.py 与 artifacts.py 的增补（如有）确认仅为最小公开化、未改语义、未改既有测试。
6 测试质量：没有只自比一次的用例；独立 oracle 不 import 生成模块；输入负例覆盖 bool、NaN、inf、范围外与类型错；
  黄金哈希与 subprocess 用例真实有效。
7 可读性：模块职责与行数表真实；入口约 50 行；无框架、万能 utils、继承。
8 复跑全部验收命令并记录真实输出；确认仓库无生成物与敏感内容。
结论 ACCEPT / REWORK / ESCALATE；发现列表（严重度、文件:行、证据、建议）；探针结果；未能核实项；模型、推理档、fork 模式。
五、顺序与提醒

顺序：root 审 G1，再派发实施，再派独立 G3，最后 root 做 G5 提交并推送。无需向用户提问。

留给 root 的工程点（不涉及业务规则）：

确认"PCG64 加 SeedSequence 子流"这一解释符合 S:41 与 D:413。
确认默认参数只是工程默认，不构成评估协议；P8 通过 params 覆盖。
若坚持要把 YAML 放进本包，须先改 C4 依赖边界并单独核实 PyYAML，建议留给 P8。

已知限制，已写入提示词，不要在验收时当缺陷：

利用率 u 是名义上界，被关键路径抬高视野时实际更低。
篡改后哈希仍自洽的缓存，普通模式检不出，需 verify_regeneration。
生成器不保证可行或最优，lag_max、FAULT、RUNNING 均不生成。





2 minutes ago
<!-- END CLAUDE P1-C2 INITIAL -->
