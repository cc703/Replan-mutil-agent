# P1-C2 Claude 修订完整捕获

2026-11-10，来源 https://claude.ai/chat/54ab7bfe-2bca-4714-9759-e3ae3e5474e7 ，消息84，页面Sonnet 5.5 Medium。以下为DOM innerText捕获，不是原始Markdown。G1仍未通过；页面额度用尽，提示20:50恢复，未升级或继续发送。

<!-- BEGIN CLAUDE P1-C2 DELTA -->
Claude responded: Δ-C2：C2 最小修订
Specifying the test cases for integrity, canonical bytes and cache

Specifying the test cases for integrity, canonical bytes and cache
Δ-C2：C2 最小修订

以下是对上一版 CB-C2 与提示词的增量，未提到的部分不变（基线 250 passed 加 1 个原 symlink skip、模型策略 gpt-6.1-terra/high/fork_turns=none、业务非目标、root 单写与 Git）。我没有改本地仓库。

一、写入范围增量
类别	精确文件
新增	experiments/configs/generator/default.yaml；src/scheduler_core/io/generator_config.py；src/scheduler_core/io/cache_area.py；src/scheduler_core/generation/dag.py、integrity.py；tests/unit/io/test_generator_config.py、test_cache_area.py；tests/unit/generation/test_generate_dag.py
改为确定修改	src/scheduler_core/io/artifacts.py（只增一个 cache() 方法）；pyproject.toml（numpy、PyYAML 为运行依赖，types-PyYAML 为 dev 依赖）；uv.lock；docs/engineering/dependency-register.md（三行）
条件限定	tools/check_import_boundaries.py：仅当它确实拒绝 io/generator_config.py 引入 yaml 时，对常量表做最小修改，同时新增 tests/governance/test_import_boundaries_yaml.py；io/paths.py 仅在需要时新增公开别名
删除	原计划中的黄金哈希测试文件不由实施 Agent 写（见 R6）

其余清单、禁止项、审查只写自身交接不变。若 layout 检查拒绝 experiments/configs/generator/default.yaml，实施 Agent 停止上报，由 root 决定，不得改 layout_rules.toml。

二、契约替换块
R1 YAML 外置（取代原"本包不引入 YAML"）

text
generator 与 generation/* 保持纯函数，只接收 typed 的 GeneratorParams，不 import yaml。
experiments/configs/generator/default.yaml：人工维护的版本化默认参数。
  顶层键：schema_version: 1、config_version: "c2-1"、params（GeneratorParams 全部字段，逐一显式写出，缺键即拒绝）。
  不含规模表（D:1131-1137 不可覆盖），不含 seed、utilization、deadline_tightness。
code 默认值 GeneratorParams() 是纯函数的回退值；default.yaml 是实验使用的唯一可编辑来源，
  漂移守卫测试要求"加载 default.yaml 的结果逐字段等于 GeneratorParams()"，这是仅有的两份默认值，且被锁定一致。
src/scheduler_core/io/generator_config.py（唯一允许 import yaml 的模块）：
  load_generator_config(source: bytes | str | Path) -> LoadedGeneratorConfig(params, sha256, config_version)
  读取：Path 读原字节，≤64 KiB，严格 UTF-8，无 BOM；sha256 对原字节。
  解析：基于 PyYAML 的 SafeLoader 子类，拒绝重复键、锚点与别名、非字符串键、自定义标签、多文档、非映射根。
  值：整型字段拒绝 bool、float、字符串；浮点字段接受 int（非 bool）并显式转 float；拒绝 .nan、.inf；
      YAML 1.1 的 yes/no/on/off 出现在数值字段一律拒绝；未知键拒绝；schema_version 必须为 1。
依赖：PyYAML 与 types-PyYAML（dev）须经官方来源核实版本、API、许可证、Python 3.11 与 Windows wheel 后固定并登记；
  不使用 type: ignore，不放宽 mypy。
边界：先运行 tools/check_import_boundaries.py 看是否拒绝；仅在确被拒绝时做模块级最小白名单（只放行
  scheduler_core.io.generator_config 引入 yaml），并加治理测试：该模块可 import yaml；generation/*、validate*、
  io 其他模块 import yaml 仍被拒；现有断言一字不改。
R2 DAG：参数可行域与弱连通构造（取代 CB-C2 第 3 节的 DAG 段）

text
每实验任务数：base = T // E，r = T % E；workflow 子流 permutation(E) 的前 r 个实验得 base+1，其余 base；总和恰为 T。
规模表保证 base 为 S:3、M:4、L:4，实现与测试断言每个实验 k ≥ 3。
有效层数 L = clamp(ceil(Fraction(dag_depth_ratio) × k), 2, k)；dag_depth_ratio ∈ (0,1]，较小的值在 L=2 处饱和。
  因此最小深度为 2，不存在"k>1 而最长链为 1"的矛盾组合。
构造（随机只来自 workflow 与 lags 子流）：
  1 层大小：从 {1..k−1} 无放回抽 L−1 个切点并排序，得到 L 个正整数。
  2 强制前驱：每个第 ℓ≥1 层任务在第 ℓ−1 层均匀选 1 个前驱。
  3 额外边：对 layer(a)<layer(b) 且尚无边的 (a,b)，按升序各抽一次 random()，小于 extra_edge_prob 则加边。
  4 连通补边（无随机）：并查集求弱连通分量；main 为含"id 最小的第 1 层任务"的分量；
    其余分量按最小任务 id 升序处理：取该分量内 id 最小的第 0 层任务 u（必存在），连 u → main 中 id 最小的第 1 层任务，并合并。
    此边由 0 层指向 1 层，保持无环且最长链仍为 L。
  5 lag：对最终边集按 (pred, succ) 升序，从 lags 子流各取 [0, lag_min_max] 的整数；lag_max 为 None。
性质：每个实验弱连通、无环、最长链恰为 L、无跨实验边；全实例弱连通分量数等于实验数。
R3 子流与参数（取代第 4、5 节中对应部分）

text
STREAMS 固定数字索引（只追加，不重排，测试对表）：
  resources 0, workflow 1, attributes 2, lags 3, setups 4, skills 5, persons 6,
  calendars 7, maintenance 8, releases 9, weights 10, deadlines 11。
deadlines 子流：仅当 hard_deadline_fraction>0 时，按任务 id 升序各抽一次 random()，小于该比例者为 HARD；比例为 0 时不消耗。
所有 ceil、floor、比较使用 fractions.Fraction(float) 精确运算（含 m(τ)、r_e、n_persons、层数）。
各"按比例取数量"的规则：count = floor(Fraction(f) × N + 1/2)，再用对应子流 permutation 选对象。

GeneratorParams（pydantic strict、extra=forbid、frozen；float 字段全部有限，拒绝 bool，int 由加载器与构造显式转 float）：
  dag_depth_ratio float (0,1] 0.6 | extra_edge_prob float [0,1] 0.15 | lag_min_max int [0,12] 2
  duration_min int [1,144] 3 | duration_max int [duration_min,144] 18   （144 = 日开放窗口长度）
  device_type_count 键恰为 S,M,L，值 ∈ [1, 该规模设备数] 默认 {S:3,M:4,L:5}
  cap_gt1_fraction [0,1] 0.2 | demand2_prob [0,1] 0.15 | multi_type_prob [0,1] 0.2
  setup_prob [0,1] 0.3 | setup_max int [1,12] 3 | closed_calendar_fraction [0,1] 0.4
  maint_fraction [0,1] 0.3 | maint_min int [1,288] 6 | maint_max int [maint_min,288] 24
  release_span [0,1] 0.5 | deadline_slack_span [0,20] 3.0 | hard_deadline_fraction [0,1] 0.0
  persons_per_device (0,5] 0.6 | skill_count int [1,8] 3 | min_skill_holders int [1,8] 2
  skill_task_prob [0,1] 0.4 | two_skill_prob [0,1] 0.2 | person_no_skill_prob [0,1] 0.1
  person_absence_prob [0,1] 0.3 | absence_min int [1,288] 24 | absence_max int [absence_min,288] 144
跨字段与规模校验 check_params_for_scale(params, scale)，不合法即 ValueError 并指出字段：
  n_persons = max(2, ceil(Fraction(persons_per_device) × n_devices))；要求 min_skill_holders ≤ n_persons；
  device_type_count[scale] ≤ n_devices[scale]。
防空集规则（不得出现空 choice、死循环）：
  技能补足：对持有者不足的技能，候选为"缺该技能的人员"，数量 = n_persons − 持有者 ≥ 所需，由上面的检验保证。
  双技能：有效组合 = 被某一人员完整持有的技能对；为空时（如 skill_count=1）双技能抽取退化为单技能，抽取仍消耗。
  第二设备类型：不存在其他类型时跳过；demand=2 无 capacity≥2 的兼容设备时降为 1。
  MAINT：hi = min(maint_max, H // 4)，hi < maint_min 则该设备跳过；长度 ∈ [maint_min, hi]，起点 ∈ [0, H−长度]。
  人员缺勤：hi = min(absence_max, H // 2)，hi < absence_min 则跳过，同上。
R4 H 的最小性搜索（取代 CB-C2 第 3 节 H 的算法描述）

text
C(H) 为整数：Σ capacity_d × open_d(H)；open_d(H) 由 CLOSED 区间运算得到（按天累计，不按槽循环）。
判定 nominal ≤ utilization 用精确比较 Fraction(W, C(H)) ≤ Fraction(utilization)。
搜索：hi=1，不满足则倍增，直到满足或超过 H_MAX_SLOTS=1_000_000（超过则 ValueError，不死循环）；
      再在 (hi/2, hi] 内二分求最小 H_u（C(H) 非递减）。H = max(H_u, max_e CP_e)。
R5 缓存：经 ArtifactStore 的明确入口（取代第 7 节）

text
ArtifactStore.cache(namespace: Literal["instances"]) -> CacheArea       # artifacts.py 仅增此方法
CacheArea（io/cache_area.py，复用 paths 的段校验、逐层链接检查、原子写、只读）：
  get(key: str) -> dict[str, bytes] | None
      不创建任何目录；逐层检查 root 至 namespace 至 key，链接或 reparse point 即 UnsafePathError；
      条目必须是普通目录，里面只能是普通非链接文件，文件数 ≤ 8，总大小 ≤ 64 MiB；返回 名称→字节。
  put(key: str, files: Mapping[str, bytes]) -> Path
      校验 key 与文件名；逐层创建 namespace 并检查；mkdtemp(prefix="stage-") 作 stage；原子写各文件；设只读；
      os.rename(stage, 最终目录)；最终目录已存在则清理 stage 并抛 FileExistsError（Windows 与 POSIX 行为须在 3.11 上实测并归一）；
      任一步失败清理 stage（先改可写再删），不留半成品；绝不覆盖已有条目。
  key 规则：^[a-z0-9][a-z0-9._-]*$，≤120 字符，不含 ~数字，不以点结尾，非保留名。命名空间白名单 {"instances"}。
InstanceCache(store) 只通过 store.cache("instances") 的 get 与 put 读写，不自行 mkdir、open、rename。
数值键编码：x 先规范化为 float(x)+0.0（消除 -0.0），取 Decimal(repr(x)) 的定点十进制字符串（无指数、无 +、无 -），
  形如 ^[0-9]+\.[0-9]+$；要求 float(token)==x 且长度 ≤ 20，否则 ValueError（不会静默截断）。
  目录名 = <small|medium|large>_u<token>_t<token>_s<seed>；params 非默认（≠ GeneratorParams()）时追加 _p<params_sha256 前 8 位>。
CacheMeta（pydantic strict、extra=forbid、frozen，严格 JSON 解析：拒绝重复键、NaN、Infinity）：
  schema: Literal[1]；canonical_version: Literal[1]；generator_version: str（^c\d+-\d+$，现为 "c2-1"）；
  scale: Literal["S","M","L"]；utilization、deadline_tightness: 有限 float；seed: int ≥ 0；
  params_sha256、instance_sha256: 64 位小写十六进制；instance_bytes: int ≥ 0；numpy_version: 非空 str（仅信息）。
generator_version 语义：生成算法、默认参数、子流索引表、canonical 格式、键编码任一变化必须递增；校验时与当前常量精确相等。
get_or_generate(scale, utilization, deadline_tightness, seed, *, params=None, verify_regeneration=False) -> CacheResult
  CacheResult(instance, key, directory, reused: bool, regeneration_verified: bool)
  复用校验：恰有 instance.json 与 meta.json；meta 与请求逐字段相等（含完整 64 位 params_sha256）；字节数与 sha 一致；
  instance_from_bytes 通过规范与完整性校验，并满足生成画像（见 R6）。
  8 位前缀碰撞：以完整 params_sha256 核验，不符抛 CacheConflictError，绝不覆盖。
  任一不符抛 CacheConflictError（在 instance_cache.py 中定义，继承 ArtifactError，不改 io/errors.py）。
  put 遇 FileExistsError（并发）则丢弃自己的结果，改为 get 并校验后复用。
信任边界（写入 README 与交接单）：sha256 只能发现意外损坏，不证明未被篡改；"篡改且哈希自洽"在普通模式不被发现，
  只有 verify_regeneration=True（相同 generator_version 与相同 numpy 下重新生成并逐字节比较）才给出语义核验；
  比较不符时报错信息提示 numpy 版本差异的可能。缓存条目写入后不可变，本包不删除、不清理。
R6 规范序列化、完整性、黄金哈希（取代第 6 节）

text
instance_to_bytes：键排序，集合输出为排序后的列表，datetime 为 UTC ISO（偏移 +00:00，微秒为 0），allow_nan=False，恰一个末尾换行。
instance_from_bytes(data) 必须拒绝（ValueError）：
  非 UTF-8、BOM、重复 JSON 键、NaN/Infinity/-Infinity、非对象根、尾随垃圾、缺失或多余的末尾换行；
  集合型字段（skills、capabilities 等）出现重复元素或未排序；任何整槽字段不是严格整数（如 4.0、"4"）；
  t0 非 UTC 或有微秒；字节不是规范形式（解析后重新规范序列化与原字节不相等，涵盖键序、空白、转义、数字写法差异）。
integrity.py：
  check_instance_integrity(inst)：compatible_devices、blocked、setups 的设备引用均存在，列表非空且无重复；
    demand ≤ 其兼容设备的最大容量；窗口 0 ≤ start < end ≤ horizon；setup 的 (设备, 类型) 唯一；先后关系无环。
  check_generated_profile(inst, scale)：任务、设备、实验数与规模表一致；全部任务 PENDING；now=0；窗口仅 CLOSED 与 MAINT；
    先后关系不跨实验；每个实验弱连通；release+duration ≤ deadline ≤ H；无授权与 RUNNING 痕迹。
黄金哈希：实施 Agent 不写黄金常量，不把实现的哈希抄进测试。
  独立 G3 在算法定版后，对 (S,0.8,0.5,0)、(M,0.6,0.25,1)、(L,0.95,0.75,2) 在不同 PYTHONHASHSEED 的子进程中
  分别计算规范字节 sha256 并记入审查交接单；G3 ACCEPT 后由 root 把这三个值写成
  tests/unit/generation/test_generate_golden.py，明确标注为"回归锁，不是正确性证据"。
三、实施提示词增量

text
增量 Δ-C2（实施，附在原实施提示词之后，冲突以本增量与 R1–R6 为准）
1 范围：按"写入范围增量"。先核实 numpy、PyYAML、types-PyYAML（官方来源：版本、API、许可证、Python 3.11 与 Windows wheel、与 mypy 的兼容），
  固定并登记，再编码；核实不过关停止上报。不使用 type: ignore，不放宽 mypy。
2 YAML：按 R1 实现；先运行 tools/check_import_boundaries.py 判断是否需要最小白名单，需要才改并加治理测试。
3 DAG、参数、H 搜索、缓存、canonical 按 R2–R6 实现。生成函数保持纯函数；InstanceCache 不得直接落盘；
  cache_area.py 与 generator_config.py 各自职责单一，函数约 20–60 行，文件约 150–300 行。
4 必须新增的正反测试（断言到异常类型与值）：
  YAML：default.yaml 加载结果等于 GeneratorParams() 逐字段，且 sha256 等于文件原字节；
    负例：重复键、锚点与别名、自定义标签、多文档、非映射根、非字符串键、缺键、未知键、schema_version≠1、
    数值字段为 yes/no/on/off、.nan、.inf、布尔、字符串，整型字段为 float，文件超 64 KiB、BOM、非 UTF-8；int 写入 float 字段被转为 float；
    规模表键出现在 YAML 中被拒；generation/* 与 generate.py 无 yaml 导入（AST 扫描）；若改了边界白名单，加治理正反例。
  DAG：对三个规模 × 多个 dag_depth_ratio（0.05、0.3、0.6、1.0）× seed 0 至 9：每实验 k≥3 且 k∈{base, base+1}、总和等于规模表；
    有效层数等于公式（0.05 时为 2）；用独立并查集 oracle 验证每个实验弱连通且全实例连通分量数等于实验数；
    无环（独立 Kahn）；最长链恰为 L；无跨实验边；构造出"补边分支被触发"的实例并断言补边为 0 层到 1 层；
    结果不依赖 utilization、deadline_tightness。
  参数：每个字段的边界值与越界值各一例；duration_min>duration_max、maint_min>maint_max、absence_min>absence_max、
    device_type_count 键缺失或越界、min_skill_holders > n_persons（按规模）、bool 与 NaN 均 ValueError 或 TypeError；
    合法极端组合不死循环、不出现空 choice：skill_count=1 且 two_skill_prob=1、
    min_skill_holders 等于 n_persons、device_type_count 为 1、maint 与 absence 的 hi 小于下限被跳过、
    utilization=0.05 与 1.0 的 H 搜索终止且小于 H_MAX；人为令上限过小时抛 ValueError；
    子流索引表与 R3 逐项相等；hard_deadline_fraction 为 0 与大于 0 时，其他字段不变，只有 deadline_level 变化。
  缓存与 CacheArea：键编码的表驱动用例（0.8、1、0.05、1e-9、-0.0、0.30000000000000004、1e-21 被拒，且无 e、+、- 字符；一组互不相同的浮点得到互不相同的令牌）；
    8 位前缀碰撞（monkeypatch 令两套 params 前缀相同）：第二次抛 CacheConflictError，第一条目字节不变；
    CacheMeta 严格性：seed 为 "1"、1.0、True，utilization 为 NaN，多余字段，重复键，schema 或 canonical_version 错，大写哈希，generator_version 不符，均被拒；
    reused 与 regeneration_verified 标志的断言；"篡改且哈希同时自洽"时普通模式复用（断言 regeneration_verified=False），
    verify_regeneration=True 抛 CacheConflictError；
    CacheArea：get 不创建目录；put 后文件只读；已存在抛 FileExistsError 且无 stage 残留；注入写、chmod、rename 失败后无半成品；
    条目内多余文件、子目录、链接被拒；命名空间或 key 非法被拒；Windows 上 mklink /J 作为 instances 层与 key 层均被拒；
    AST 扫描 instance_cache.py：无 open、mkdir、rename、write_bytes、shutil 调用。
  canonical 与完整性：往返字节相等；R6 列出的每一项拒绝各一例；check_instance_integrity 与 check_generated_profile 的每条规则各一正一反；
    对 generate 产出的全部扫描实例两个检查均通过。
  黄金哈希：不写；只在交接单记录三组规范字节 sha256 与跨 PYTHONHASHSEED 一致性的证据，供 G3 与 root 使用。
5 验收命令、基线与其余约束不变；交接单增列：PyYAML 与 types-PyYAML 核实证据、是否改动边界白名单及理由、
  3.11 上 os.rename 对已存在目录的行为实测、默认参数与 default.yaml 的漂移守卫结果。
四、审查提示词增量

text
增量 Δ-C2（审查，附在原审查提示词之后）
1 YAML：核对 default.yaml 与 GeneratorParams() 逐字段相等且无规模表；加载器的全部拒绝用例；
  generation/* 与 generate.py 不 import yaml，只有 io/generator_config.py 引入；PyYAML 与 types-PyYAML 的版本、许可证、wheel 独立复核；
  若改了边界白名单，确认仅为该模块的最小放行，现有断言未改，且新增反例能证明其他模块 import yaml 仍被拒；未用 type: ignore。
2 DAG：自写 oracle（并查集、拓扑、最长链）对 3 个规模 × 5 个 ratio × 10 个 seed 复核弱连通、连通分量数等于实验数、最长链等于 L、
  无跨实验边、k_e 分配；构造一个会触发补边分支的实例复核；确认没有 k>1 而最长链为 1 的路径；
  确认实现与 R2 逐步一致（尤其补边只会 0 层指向 1 层）。
3 参数：逐字段核对类型与范围；跨字段与规模校验；在极端合法组合下探针确认不死循环、无空 choice；
  H 搜索的终止、上限与最小性（用精确 Fraction 复核 W/C(H) 与 W/C(H−1)）；STREAMS 索引表与 R3 一致且 deadlines 的消耗规则正确。
4 缓存：确认 InstanceCache 没有任何直接落盘或建目录；CacheArea 的链接、junction、非法 key、并发、失败注入、只读、不覆盖；
  键编码的边界与唯一性；8 位前缀碰撞通过完整哈希核验；CacheMeta 严格；
  "哈希自洽的篡改在普通模式不被发现、verify_regeneration 可检出"如实披露，并确认 README 与交接单没有把 sha256 说成防篡改；
  CacheConflictError 定义在 instance_cache.py，io/errors.py 未改；artifacts.py 仅增 cache() 方法。
5 canonical 与完整性：逐项探针 R6 的全部拒绝项；用扫描实例验证两个检查；
  确认没有"严格"表述缺验收。
6 黄金哈希：确认实施 Agent 未写黄金常量；你亲自在不同 PYTHONHASHSEED 的子进程中计算 (S,0.8,0.5,0)、(M,0.6,0.25,1)、(L,0.95,0.75,2)
  的规范字节 sha256，并记入审查交接单，供 root 冻结。
其余审查项、结论格式不变。
五、两点提醒
参数默认值现在有两份（代码回退与 default.yaml），只靠漂移守卫测试保持一致。这是为了让生成器保持纯函数，同时满足"参数外置 YAML"，已在 R1 写明。
黄金哈希由 root 在 G3 ACCEPT 后冻结，所以实施阶段的测试数会少一个文件。这是有意的安排，不是遗漏。





just now
<!-- END CLAUDE P1-C2 DELTA -->
