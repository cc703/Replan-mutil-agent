# P4 独立 G3 审查

结论：REWORK（初审，待修复后续审）。审查者 gpt-6.1-terra/high，未参与实施。依据工作包 v001、最终 G1 PASS 与用户紧急完成时间求和裁决。

1. **P1：未来故障错误拒绝**。`src/scheduler_core/replanning/events.py` 的 `prepare_raw` 把同设备所有 RUNNING 记录视为中断，要求 outage.start == now。独立探针：now=2，设备 d 上 a 实际 [0,6)、remaining_estimate=4，事件 d [8,10)，调用 `prepare_raw` 抛 `ValueError: interruption requires outage at snapshot time`；任务在停用前完成，合法未来事件无法处理。应依据实际占用与故障区间处理，不能虚构未来执行状态。
2. **P1：raw overrun 无法通过发布校验**。同实例将 remaining_estimate 改为 6，调用 `replan(inst, base, [TaskOverrun(task_id="a", new_end=8)], context=ctx)` 抛 `RuntimeError`，validator 报 V11 `FROZEN_END_NO_EVIDENCE`。`prepare_raw` 未生成候选专用 `FrozenEndChange`，仅 simulator adapter 为其 post 路径生成；合法 raw 超时无法交付计划。修复须保留独立证据核验及一次应用。

独立执行 `python tools/verify_source.py` 全部 PASS；`uv run --python 3.11 --group dev pytest tests/unit/test_p4_impact.py tests/unit/test_p4_objective.py tests/unit/test_p4_oracle.py -q` 18 passed。上述两个探针为自行构造，不包含在 18 项中。未运行全仓 check；由 root 负责。待修复后复验并补充结论；本记录不代表其余路径已全部通过。

3. **P1：overrun 跨设备后继遗漏**。`src/scheduler_core/impact.py` 的 TaskOverrun 分支只以同设备后续待排任务作为传播种子。独立探针：now=2，a RUNNING、d1、旧 [0,6)、remaining=6、新结束 8；b 在 d2 旧 [6,8)，有 a→b 先后关系。`analyze_impact` 返回 `affected=set(), unaffected={'b'}`，b 实际须右移，level 0 漏掉受影响后继；需从超时任务本身向后继传播，维持冻结。

4. **P2：非有限预算未拒绝**。`replan.py` 仅检查 `<= 0`，单任务实例传 `ReplanParams(total_budget_s=float("nan"))` 返回 TIMEOUT、传 `inf` 返回 OK；这既非有限总预算，也把非法参数包装为超时。B3 同样仅检查 `<= 0`。应在入口拒绝非有限值。

## 返工独立复审：ACCEPT

四项原探针重新执行：未来 [8,10) 停用保留 RUNNING 并添加一次故障；raw overrun 返回 OK 且跨设备后继 b 开始不早于 8；b 进入 level 0，四层集合单调；NaN/inf 预算均抛 ValueError。将 RUNNING 记录设备篡改为 d2 后 raw overrun 被拒绝。实施代码停写后独立运行 `uv run --python 3.11 --group dev pytest tests/unit/test_p4_impact.py tests/unit/test_p4_oracle.py tests/unit/test_p4_objective.py -q`，30 passed。前述四项均关闭。

静态核对：目标以有理数同比例整数化，shift 系数含 H，urgent 采用本批新任务完成时间之和；目标系数/上界有溢出拒绝。raw/post 明确区分，求解结果经独立 validator，UNKNOWN 与局部 INFEASIBLE 不被当全局无解；B2 仅延期、B2s 完整目标并直接 level 3，B3 规则候选经相同 validator。hint 仅作为提示。现有旧测试文件未修改；新增源文件处于实施白名单（含参数模块），未发现生成物。模型主函数偏长但有独立日历与目标辅助函数，行数为审查参考，记为维护限制而非阻断；raw 中断复制 P3 规则，未来需同步。B3 为保守规则，可能未找到可行解；不作完整性保证。

边界：上述为代表性探针及定向测试，非穷举；执行证据的真实性仍由上游提供和确认，validator 核对结构和一致性。未执行全仓 check，由 root 负责。G3 ACCEPT 不代替 G5 和远端同步。
