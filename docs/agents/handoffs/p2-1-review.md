# P2-1 独立 G3 审查

结论：ACCEPT（工程审查；G5 由 root 决定）。基线 a994cd0；审查者独立于实施，gpt-6.1-terra/high/fork_turns=none。计划来源 temp v001，G1 修正和 G4 以工作包为准。无源码、测试、依赖或 Git 修改。

- 原文 `python tools/verify_source.py` 本轮全文及分批 PASS。工作区状态核查：业务新增限 solve_initial、solving 与新测试；依赖及治理文档改动符合工作包及 root 的整合范围。直接依赖固定 OR-Tools 9.15.6755，依赖登记明确 wheel 捆绑许可未完成发行审计和用户限定本地使用；本审查未重新逐个核验 wheel 或旧 lock 版本。
- 走读模型及入口：执行释放/now、截止、前驱上下界；设备准备占用从 start-setup 到 end，允许跨 now 但不跨零，合并阻塞并按满容量占用；人员按技能选择且仅占执行段。成功结果必须独立 validate，失败抛错；测试包含注入校验拒绝、UNKNOWN/MODEL_INVALID 映射。非 PENDING 拒绝，NEGOTIABLE 截止无放宽。输入未原地修改，已有测试覆盖快照。
- Cmax、同类型设备含零负载的极差及跨类型最大均由等式或 max/min 等式定义，并从分配重算整数目标；权重按十进制有理数缩放和整数安全上界拒绝，不静默舍入。无偏好数据时非零偏好拒绝；无授权延期故 tardiness 为零。返回目标及 bound 为浮点展示，极大值的浮点显示精度有固有限制；模型决策仍为整数系数。
- 独立穷举：通过临时 stdin Python（`PYTHONPATH=src; uv run --locked --python 3.11 --group dev python -`），两设备容量 2/1，同类型，一任务 duration=2、demand=2 仅选容量2设备，另一任务 duration=1、截止4可选两设备，含阻塞及另一设备准备，视野5；枚举设备及开始槽，用独立 validator 过滤得到13个可行组合，独立计算负载和目标。四组 (makespan, imbalance) 权重 (1,0)、(0,1)、(1,0.5)、(0,0) 的穷举最优分别为 3、3、4.5、0，单线程求解均 OPTIMAL 且结果相同，返回计划均通过 validator。首次命令未设置 PYTHONPATH 导入失败；设置后成功。此探针不同于实施测试用例。
- 实施测试包含 mini golden 10、8 个固定种子小实例 oracle、容量和准备反例、状态及校验门禁、1/8线程各5次真实 mini；root 报告联合完整检查 859 passed/1 原 symlink skip、95 文件静态通过，API 格式修复后定向格式 PASS；本审查未重复全量及该输出。ADR 0003 记录 20 次各线程实测及用户批准的等价最优排程口径；默认8线程目标最优且合法，逐项排程复现使用显式1线程，未将多线程差异掩盖为一致。
- 限制：独立穷举只覆盖上述小实例及四组权重，不证明所有实例；未独立重复 20 次实测、完整 check、许可证源或全部设计原文逐节比对。有限时间 FEASIBLE 不保证最优；外部分发前仍须完成依赖捆绑许可审查。
