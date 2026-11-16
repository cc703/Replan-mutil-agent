# P2-2 搜索优化

来源为 2026-11-16 侧栏原 Claude 会话 54ab7bfe-2bca-4714-9759-e3ae3e5474e7，Sonnet 5.5 Medium。以下是可见回复正文，省略界面控件。

## P2-2 计划与提示词

以下为提议，我没有读过本机源码，也没有修改仓库。

范围：新增 search.py、hint.py，并在 run.py 接入；测试只写 tests/unit/test_initial_search.py；交接写 handoffs/p2-2.md。solve_initial 接口、硬约束、目标、独立校验、未授权 NEGOTIABLE 按硬，均不变。不改校验器、基线、双 profile，不加依赖，不跨 P3。

安全等价：同类设备 d 与 d′ 视为等价，当且仅当同时满足：

1. type、capacity、capabilities 相同。
2. 合并后的阻塞窗口集相同。
3. 所有准备规则相同。
4. 每个任务对二者的兼容性一致。

对每个等价类（≥2 台）按任务序加值先出现约束 x[i,d_{k+1}] ≤ Σ_{j<i} x[j,d_k]。人员不参与。任一属性无法确证，就不破缺。排列设备不改变各设备负载的多重集，所以目标不变。

Hint：按 EDD（deadline 升序，无期限最后）、weight 降序、id 的拓扑顺序做贪心可行排程，占用语义与模型相同。

- 预算为 min(1s, 5% time_limit)，并设任务数×设备数上限。
- 结果必须过 validate 才 AddHint（s、x、y 全量），否则不加。
- 超预算、抛异常、校验不过一律回退无 Hint。Hint 不作约束。
- 决策策略按同一优先序，只在中规模实测不劣于关闭时默认启用，否则默认关闭并披露。

### 实施提示词

```text
[附公共前言、增量 v002] gpt-6.1-terra，high，fork_turns=none。目标：实现 P2-2 搜索加速，正确性第一。
只写 src/scheduler_core/solving/{search,hint,run}.py（必要者）、tests/unit/test_initial_search.py、docs/agents/handoffs/p2-2.md。
禁止：改接口、校验器、基线、双 profile、依赖、P3；弱化既有断言；新增 skip 或 xfail；Hint 作约束。
先读 solving/ 与 validate，确认占用语义；在已装 OR-Tools 9.15 核实 AddHint 与 AddDecisionStrategy 的行为，结果入交接单。
实现：等价类检测（保守，见上述条件）、值先出现破缺、EDD 启发式与回退、可关闭的决策策略（内部开关，默认由实测证据决定）。
测试：
1 微型穷举（≥150 个实例，含 2–3 台等价设备、persons、setup、窗口、lag、截止）：破缺开关前后及 oracle 的最优目标与可行性一致；
  近似等价反例（只差 capacity、窗口、准备规则、capabilities 或某任务兼容性之一）必须不被判为等价，目标仍等于 oracle。
2 变异验证：测试内强制把非等价类当等价破缺，须在至少一个反例中得到劣于 oracle 的目标，证明反例有效。
3 Hint 故障注入：构造器抛错、超预算、返回不可行或部分 Hint、校验不过，均回退，状态与目标同无 Hint，计划必过 validate；记录 Hint 构造耗时。
4 小中规模：S 与 M 生成实例各 3 个，30s，1 线程与默认 8 线程各跑关闭与开启，记录状态、目标、gap、耗时；计划必过 validate；
  逐项复现只用 1 线程，8 线程仅比较状态与最优目标；不把性能作为通过条件，除非开启后可行解率低于关闭，此时关闭该特性。
验收：uv run --python 3.11 --group dev python tools/check.py；pytest tests/unit/test_initial_search.py；布局与来源检查；git diff --check；
基线 859 passed 加 1 skip 不降。交接：公共 H 格式，附等价类判定表、Hint 耗时、实测表。
```

### 独立审查提示词

```text
[附公共前言、增量 v002] gpt-6.1-terra，high，fork_turns=none。只读，只写 docs/agents/handoffs/p2-2-review.md；探针在仓库外。
1 范围：diff 仅含允许文件；接口、校验器、基线、依赖、双 profile 未变；无新增 skip 或 xfail；基线 859 passed 加 1 skip。
2 自己写穷举 oracle（不复用作者），构造 ≥150 个含等价与近似等价设备的实例，比较开启前后与 oracle 的目标；
  专门检查：兼容性不一致、窗口不同、准备规则不同、capacity 不同、persons 的交互。
3 审查等价判定是否保守，且只作用于任务序上的值先出现约束；检查不存在对目标、约束或可行域的改动。
4 Hint：确认仅作 Hint；故障注入（异常、超预算、不可行、部分）均回退；任何路径都不返回未过 validate 的计划；预算有上限。
5 复跑小中规模对比（1 线程逐项、8 线程仅状态与最优目标），核对开关取舍有证据，未把 8 线程排程差异当作错误或掩盖。
6 复跑验收命令并记录真实输出。结论 ACCEPT / REWORK / ESCALATE，附发现、探针输出、未能核实项。
```

需要用户裁决的事项：无。若中规模实测显示决策策略劣于关闭，则默认关闭，属工程决定。

## 总设计师 G1，2026-11-16

通过。基线为已远端核验的 129a79b，标签 p2-1-accepted。保留完整原提示；按用户简化流程，性能表一次，独立审查抽查表中代表例，联合全量一次。等价约束只选可重命名的代表元，保留每类至少一个可行代表和原最优值。预算同时覆盖 Hint 构造、校验，避免稠密前缀和、全视野大数组及不可中断的大循环，Hint 按设备首次使用顺序与破缺相容。内部开关供对照及选择默认，沿用公开签名。性能证据优先比较可行解率与同预算目标，耗时单独列。S/M 必须排查全无解的无效比较。search 专项写 search.py、run.py；hint 专项写 hint.py；测试专项写 test_initial_search.py 及实施交接。root 汇总验收。模型均为 gpt-6.1-terra/high/fork none。G4 属已委托的工程选择。
