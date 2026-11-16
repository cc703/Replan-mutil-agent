# P2-1 temp 计划 v001（待 root G1）

来源：temp，gpt-6.1-terra/high/fork_turns=none；Claude 消息94仅以 p2-1.md 中 root 摘要为输入，不是 Claude 原文。设计原文 verify_source.py 本轮 PASS。此文不是 G1 通过或实施授权。保留原签名、30s/8 workers/seed 0；仅 PENDING，其他状态明示拒绝（含 SCHEDULED），不进入 P3/P4。NEGOTIABLE 未提供放宽授权时与 validator 一致视为硬截止，因此本包 tardiness 为零。不存在偏好输入，非零 Pref 权重必须拒绝，不能称完整 SOFT 接口。

## 目标与决策

原设计目标 ΣwT + λ1 Cmax + λ2 Imb + λ3 Pref；原文未规定权重数值和负载量度。建议 root 在 G1 确认工程细化：默认 makespan=1、imbalance=0.1、preference=0；Imb 为每类型全部设备（含零负载）按分配任务 duration × demand 求和，同类型最大减最小，跨类型取最大；空集/单设备为零，准备时间不计。该定义是可追踪提议，不声称原文唯一解；若 root 判断改变算法语义，目标部分暂停并提用户裁决，模型与约束、依赖和独立测试可先行，不用猜测默认值交付正式结果。权重字段名称及缺省规则在公共 docstring 明确；未知键、负值、NaN/Inf、非零 preference 明确 ValueError。float 用其十进制字符串的精确有理数表示，公分母和最大公约数化简为最小整系数；对参数位数、系数和整个表达式可证 int64 安全上界严格检查，超界拒绝，不 round 或静默丢项；显式零权重合法。

## 实施 prompt（G1 后整体派发，Terra/high/fork none）

工作目录 D:/Default/Replan-mutil agent。先读 AGENTS.md、PROGRESS 开头、本计划、p2-1.md、工程/门禁、设计5/6.1、spec 3/4.1/5/P2、ERRATA、ADR0002/0003/0006、现有 models/axis/validate 和 validation 全部。先运行 verify_source.py；勿重复 P1 全量。只写 `src/scheduler_core/solve_initial.py`、新建 `src/scheduler_core/solving/*.py`（按职责适量拆分）、`tests/unit/test_solve_initial*.py`、`tests/property/test_solve_initial*.py`、`pyproject.toml`、`uv.lock`、`docs/engineering/dependency-register.md`、`docs/agents/handoffs/p2-1-implementation.md`。路径布局不符先报告 root；不要改 models、validator、生成器、原文、既有测试断言或其他文档；不得提交/推送/改 Git 配置。多人时 root 先固定接口，建模独占 solving，接口/依赖独占 solve_initial、依赖及登记，测试独占新增测试，互不写同一路径；集成后各自停写，root 审查协调。

依赖：官方核实固定 OR-Tools 9.15.6755 与 Python 3.11 API、Windows wheel 和传递依赖许可证/来源，使用现有 uv 工作流锁定，确保既有 NumPy 2.4.6、Pydantic 2.14.3、PyYAML 6.0.3 与其他旧依赖不被意外升级；记录实际变更。根 wheel Apache-2.0 不代表其捆绑组件均同许可；开发使用和未来分发的义务如实登记，实际许可疑问报告 root，不自行更改项目许可证。不得添加其他依赖。

模型：保留 spec 的 solve_initial 原签名与返回 Plan|None；新增详细 API 返回明确 OPTIMAL、FEASIBLE、INFEASIBLE、UNKNOWN、MODEL_INVALID，附计划、求解信息与界限（可用时），区分无解、超时未知、模型错误；原接口无解/UNKNOWN 返回 None，模型错误或参数错误抛明确异常，不把 UNKNOWN 冒充 INFEASIBLE。有效解提取 Plan 后必须调用独立 validate，未通过立刻抛内部错误、附报告，绝不返回。输入不修改。验证 task/status/空实例、参数、引用、越界及非法实例边界；无可选设备/人员导致真实无解应有清晰状态，不用异常掩盖。对 validator 认为实例自身无效与可行性不足的界线明确记录。

每任务选恰一兼容设备；执行时长与窗口、释放、now、规划视野、截止和前驱 min/max lag 与 validator 一致。可选设备占用 [start-setup,end)，准备不能越 now/视野；单容量 NoOverlap，多容量 Cumulative，以 demand 计含准备。阻塞先按设备合并重叠/相邻并集，再满容量占用；人员按技能选恰一，人员只占执行段，考虑日历及互斥。具体边界逐条对照 validator，不能复制其实现或修改校验器。建模目标 Cmax 和 Imb 使用等式/MaxEquality/MinEquality 约束为真实值，即使 FEASIBLE 或系数为零也不能使用仅优化时收紧的不等式；从赋值独立重算真实指标，验证目标与求解器值一致并保护精度。空任务的 Cmax/Imb 定义为零。禁止把任意中间辅助变量当实际指标；如 API 返回 bound/gap，标明缩放及空值边界，绝不可冒称最优。

测试：小型独立穷举枚举开始、设备、人员，用现有 validate 判断可行、独立计算目标，覆盖多个权重和容量、准备、日历、技能、先后/截止，检验最优值；独立 golden mini makespan=10；固定种子随机小实例输出均通过 validator，少量精心覆盖边界而非机械大规模重复。分别测试模型的正反约束、无解、空实例、非 PENDING、输入不变、零/小数/超界权重、偏好拒绝、状态映射（含模拟 UNKNOWN/MODEL_INVALID）与短时限的合法多结果；FEASIBLE 必须检查重算目标。保持测试执行预算并记录实际数量/时间，不因时间限制将所有短时限强断言为 UNKNOWN。默认 8 worker/seed 0 用相同实例和参数多次真实运行比较状态、目标、完整分配，记录版本/次数/时限；多线程差异如实上报，阻塞相应确定性验收，不能改断言、skip、xfail 或偷偷改默认、引入双 profile；评估协议改变请求用户裁决。定向测试及静态先行，联合稳定后完整 `uv run --python 3.11 --group dev python tools/check.py` 一次；失败按必要修复重跑，不每步全量。交接列实际文件、命令、输出、状态与证据、限制及未决；G2 不代替 G3。

## 独立 G3 prompt（另一个 Terra/high/fork none，实施者停写后）

只读以上资料、实施交接及实际变更，唯一写入 `docs/agents/handoffs/p2-1-review.md`；禁止改源码、依赖、测试或 Git。核查实际变更范围和原始签名/参数、固定依赖及锁保留、许可证证据；独立走读建模与 validator 语义，重点准备区间、容量阻塞并集、人员技能和执行区间、NEGOTIABLE、每个状态、精确目标缩放和 int64 上界、FEASIBLE 真实指标、校验失败拒绝、输入不修改。自行构造至少一组与实施测试不同的微型穷举及约束反例，独立检查目标和计划；查 golden 10、随机案例及实际定向与完整 check 输出。检查 8 worker 重复真实证据，发现差异必须如实标注对应验收阻塞，不能以测试通过代替确定性。验证实施未越权改动、未跨阶段、未夸大 SOFT；区分发现、证据、复现、影响和必要返工，给 ACCEPT 或 REWORK，未实际做的检查标明未做。交 root，不自行批准 G5。
