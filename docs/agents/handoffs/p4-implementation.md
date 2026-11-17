# P4 实施交接

来源：temp v001 和 root 最终 G1/用户紧急完成时间求和裁决；未冒称 Claude。未提交或推送。

- `impact.py`：影响分析、执行证据索引、同设备排序传播和四级邻域。
- `replanning/events.py`：区分 raw 一次应用和 post 仅检查；按运行快照重建 raw 中断；`model.py`：P4 CP-SAT；`objective.py`：有理数整数化及范围检查；`replan.py`：预算、扩层、指标和独立验证。
- `baselines/b2_full.py`、`b3_rule.py` 提供规格公共入口；`b2.py`、`b3.py` 分别为全量解算与 EDD 修复实现；`simulator/replan_adapter.py` 消费已应用事件和 P3 快照，为超时证据生成候选专用结束变更。
- `tests/unit/test_p4_impact.py`、`test_p4_oracle.py`、`test_p4_objective.py` 覆盖代表性故障、冻结、层级、完整释放、P3 抢占/重启/超时、UNKNOWN、预算、规则基线拒绝、三任务有限枚举和数值缩放。

实际验证：`python tools/verify_source.py` 全部 PASS；`uv run --python 3.11 --group dev pytest tests/unit/test_p4_impact.py tests/unit/test_p4_oracle.py tests/unit/test_p4_objective.py tests/unit/test_solve_initial_oracle.py tests/unit/validation tests/simulator/test_engine_interrupt.py tests/simulator/test_not_started.py -q` 134 passed；对上述 P4 源文件及测试运行 `ruff check` 通过；对 P4 源文件运行 `mypy` 通过。未运行全仓 check，留 root。

审查注意：raw 中断实现按 P3 相同规则重建，代码目前独立实现，未来 P3 规则变化需同步；模型主函数已抽取日历和目标 helper，但变量及任务约束主体仍较长。B3 是有时间预算的保守规则修复，找到候选仍必须独立校验，无法保证找出所有可行解。预算状态、输入证据一致性、执行结束授权和中断重接请 G3 独立重点核验。

## G3 两项返工

`replanning/events.py` 对未来停用仅添加故障窗口，按当前执行区间及故障发生时间判断中断；已发生且历史不明的交叠拒绝推断。`replan.py` 在 raw 工期超时中检查运行状态、原分配、快照剩余与新结束一致后，为候选和父计划绑定结束变更；引用调用者提供的执行观察 `event_id`，并以快照时刻作为观察时刻，不声称独立事件真实性；已有结束变更由独立校验器核验，不覆盖。输入保持不变。

定向：`uv run --python 3.11 --group dev pytest tests/unit/test_p4_impact.py tests/unit/test_p4_oracle.py tests/unit/test_p4_objective.py -q`：20 passed；`ruff check` 针对修改源文件及测试通过；`mypy` 针对两个源文件通过。未跑全仓检查。

## G3 第三、四项返工

`impact.py` 从超时源沿后继关系传播，冻结任务保持冻结，跨设备待排后继进入影响域。新增可复现 RUNNING d1 至 SCHEDULED d2 的 level 0 修复测试。`replanning/params.py` 统一校验有限正预算、非负窗口、0–3 层级及 CP-SAT workers/seed 范围；`replan` 与 B3 共用，公共 B2/B3 入口随之拒绝非法值。

`uv run --python 3.11 --group dev pytest tests/unit/test_p4_impact.py tests/unit/test_p4_oracle.py tests/unit/test_p4_objective.py -q`：30 passed；修改源文件及测试的 `ruff check` 通过，四个修改源文件的 `mypy` 通过。未运行全仓检查。
