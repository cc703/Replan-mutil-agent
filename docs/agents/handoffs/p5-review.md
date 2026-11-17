# P5 独立 G3 审查

审查者：/root/p5_review，gpt-6.1-terra/high/fork_turns=none；合同 p5.md 与 p5-claude-plan.v001，基线 681f34de0a3a776afea894b3b7d1acef0f2eeaf0。独立于两作者。状态：REWORK，复审进行中；不代表阶段验收。

## 发现与复验

1. 候选池覆盖调用者 num_workers 为 1，违反网格配置合同。原作者已去除覆盖，静态复核调用参数及新增捕获测试通过。
2. 重排模型预算耗尽仍启动求解。原作者修复后，独立将 CpSolver.solve 替换为抛异常探针、传 time_limit=0，得到 UNKNOWN，未调用求解。
3. 松弛提前返回绕过执行证据检查。原作者复用 prepare 后，缺 snapshot 的 base 和空核复现改为 ValueError。
4. DONE 观察工期可能不同于名义工期，移除 frozen 组时模型改用名义工期，破坏删除约束的单调性。独立例：duration=4，实际 [0,2)，deadline=2，now=2；保留 frozen、deadline、capacity 为 OPTIMAL，移除 frozen 后 INFEASIBLE。修复及复验待完成。

## 独立证据

- 运行 source verify 全部通过。OR-Tools 9.15.6755 实测 NoOverlap、Cumulative 守卫：关闭 OPTIMAL、打开 INFEASIBLE。
- 自写整数枚举：X duration 4/deadline 3 返回唯一截止组且移除此组可行；最优松弛 1，代价 1。
- 两任务 duration 2/deadline 2/单设备容量1/视野4：枚举原问题不可行，分别移除两个截止或容量均可行，与返回三组 minimal 核一致。
- 上述双任务均为 NEGOTIABLE，权重2和3：枚举两个互不包含支持分别 X+2 代价4、Y+2 代价6，与返回和最优标记一致。

## 未覆盖与限制

未独立完成全部合同指定的窗口、人员、RUNNING/DONE 和授权组合、旧版差分、完整候选状态网格、输入不可变及预算嵌套探针；作者报告的回归数字未经本审查复跑。故当前不能声称完整 G3 通过。未运行全仓 check；由 root 负责。未提交或推送。

## 返工后续审（最终）

REWORK4 独立重跑 DONE 提前结束反例：启用及移除 frozen 均 OPTIMAL，已恢复该反例的单调性。窗口微例 duration=2、deadline=2、设备 [0,2) 停用、视野4，返回 capacity、deadline 和窗口三组 minimal 核；枚举可知同时启用无解，去任一组可行。人员微例两独立设备、同一人员、两任务 duration=2/deadline=2/视野4，返回两截止和人员组 minimal 核；枚举同时开始冲突，任一截止或人员组移除可错开或并行。DONE 有效快照及缺失快照拒绝均经独立探针；未穷举执行事实组合。

从基线 git show 在内存加载旧 P2/P4 模型，单线程各运行一个可行微例：旧新 P2 均 OPTIMAL、目标4、独立校验通过；旧新 P4 均 OPTIMAL、目标0、独立校验通过。该差分仅代表所测实例。独立 Pareto 四候选全排列测试保留两个同指标不同资源计划、排除被支配计划，24 种顺序结果相同；候选池模拟各层 UNKNOWN 返回 TIMEOUT、无冲突。模型超时不启动求解的替身探针见上。模型参数修复后静态核对调用方 worker 不再覆盖。

结论：ACCEPT（代表性验收）。四项阻断均经修复并复核；此结论不声称穷举所有窗口、人员、授权、网格、预算及事实组合，也不代替 root 全仓检查、G4/G5 或同步。原报告中“复审进行中”和“修复及复验待完成”为当时状态，以本节最终结论为准。作者自身的定向回归和静态检查数字仍只引用交接，非本人运行。
