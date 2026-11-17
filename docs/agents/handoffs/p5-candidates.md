# P5 候选部分交接

状态：候选部分完成并停写；核心停写后的最终必要联调通过。P5 整体仍待 root G2 和独立 G3。作者实际模型 gpt-6.1-terra，high，fork_turns=none。来源：`docs/work-packages/p5.md` 的工程细化与 `p5-claude-plan.v001.md`，以及 root 对证据绑定的工程决定。

- `pareto.py`：验证通过的严格非支配筛选、资源敏感 L1 去重、确定性标签和限制数量选择。
- `plan_diff.py`：按任务 ID 返回新增、移除、起点移动、设备和人员变化，副本隔离输入。
- `replanning/pool.py`：事件只应用一次；层级与网格求解；以参考参数重算指标；逐候选校验；总预算和状态区分。候选 ID 为 `{base.id}.replan.l{level}.w{grid_index}`，网格序号从 0 开始，可供上游准确绑定授权。已有授权仅用于匹配原始 ID，不更改授权；运行超时证据由执行观察按 P4 核对重建。存在任意截止授权时保守不输出基于 base 授权口径的冲突核，避免把局部冲突声称为多候选共同冲突。
- `tests/unit/diagnostics/test_pareto.py`、`test_plan_diff.py`、`test_replan_candidates.py`：覆盖支配、同分资源、去重边界、标签、输入顺序、diff、网格统一指标、双候选、超时、事件一次性、授权边界和运行超时证据。

验证：

- `uv run --python 3.11 --group dev python -m pytest tests/unit/diagnostics/test_pareto.py tests/unit/diagnostics/test_plan_diff.py tests/unit/diagnostics/test_replan_candidates.py tests/unit/test_p4_impact.py tests/unit/test_p4_objective.py tests/unit/test_p4_oracle.py -q -p no:cacheprovider`：63 passed，pytest 配置 `cache_dir` 警告 1 条；核心停写后复跑。
- `uv run --python 3.11 --group dev python -m ruff check` 加上述源码及测试路径：通过。
- `uv run --python 3.11 --group dev python -m mypy` 加上述 6 个源码及测试路径：通过。

限制：诊断和松弛以可协商截止期冲突实例完成联测；模型 `ReplanParams` 构造时会将 bool 强制转为数值，候选池无法恢复原始类型，此项已报 root，模型不在写入范围。不可提交推送。



## G3 REWORK1 修复

候选求解不再覆盖调用方 `num_workers`；诊断自身单线程策略不变。新增参数捕获回归，确认调用方传 4 时求解器接收 4。实际运行：`uv run --python 3.11 --group dev python -m pytest tests/unit/diagnostics/test_replan_candidates.py -q -p no:cacheprovider` 为 20 passed、1 条 pytest `cache_dir` 配置警告；对 `pool.py` 和该测试的 Ruff check 及 mypy 均通过。修复后停写，等待独立复核。
