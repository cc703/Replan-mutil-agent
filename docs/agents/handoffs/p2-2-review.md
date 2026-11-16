# P2-2 独立 G3 审查

结论：**REWORK**。2026-11-16，gpt-6.1-terra/high/fork none；对照基线 129a79b，审查 Claude v001 及 root G1、交接、原设计 6.1 和实际源码。仅本报告写入；审查探针通过 stdin 运行。

## 必须修复

`search.add_hint` 与 `hint.build_hint` 的预算时钟，以及 `run.run_model` 的搜索耗时均使用 `time.monotonic`。当前 Windows/Python 3.11 实测 `time.get_clock_info('monotonic')`：GetTickCount64、分辨率 0.015625 秒；`perf_counter`：QueryPerformanceCounter、分辨率 0.0000001 秒。root 实测 Hint 构造 0.422–2.693 ms 而 monotonic 记录为零；很短的 time_limit 下，5% 预算可以小于一个时钟刻度，构造与校验实际超预算后仍被认为未超限并添加 Hint，搜索时间也可能未从求解预算扣除。与 G1 的构造和校验共同受预算约束不符。建议统一采用高分辨率单调 perf_counter，整个 deadline 链和求解剩余时间不得混用时钟；调整故障注入并复审。

## 已核验

- `python tools/verify_source.py` 全部 PASS；`git diff --check` 无空白错误（Git 提示 run.py CRLF 转 LF）；实际变更与授权范围一致，新增文件亦逐项核对；校验器、基线及依赖未改。无新增 skip/xfail。
- 独立手写枚举（不用作者 oracle 或 validator 判可行）192 例，2–3 台设备、人员、准备、阻塞、lag 与硬截止，86 可行、106 不可行；穷举设备和整数起始时间，手算 Cmax 与同类负载差。开启与关闭搜索共 384 次，状态及最优目标全部相同；可行计划另经独立 validator 通过。近似等价维度及人为错误合并的有效反例由定向测试验证；本次手写枚举未另覆盖全部近似等价组合，不能扩大为已独立穷举该部分的声明。
- 审查设备类型、容量、capabilities、合并窗口、全部准备规则及逐任务兼容性构成保守等价键；破缺只规定设备第一次出现次序，人员未重命名；设备置换保持同类负载多重集与目标。Hint 是 AddHint，非约束；独立构建含人员例检查 s/x/y 共 4 个变量各一次，且代码先检查完整分配和 validator。
- `uv run --locked --python 3.11 --group dev pytest tests/unit/test_initial_search.py -q`：15 passed in 1.82s，含异常、超时、部分、非法、验证拒绝和近似等价反例。预算时钟粒度问题不被这些模拟时钟测试捕获。
- 代表实跑 S/M seed 0，各 1/8 线程及基线、Hint+破缺、再加策略：12 组均 OPTIMAL 且 validator PASS；S 目标 118.1，M 目标 150.1。M 单线程耗时 2.6285/1.3435/2.3121 秒，8 线程 0.5047/0.3632/0.5534 秒，仅为机器负载下样本。默认关闭额外策略有证据；8 线程不比较排程。
- root 报告联合完整 check 为 874 passed、1 既有 skip，ruff/format/mypy 98 文件及布局/导入/来源通过；遵循 G1 一次联合全量，本审查未重复运行。

## 限制与待复验

修复后重新核对超短预算边界、完整 Hint 及回退，并视变更重跑必要测试；此报告为首轮结论，不表示 G3 已通过。性能证据为本机有限样本，不构成普遍加速保证。

## 返工补审，2026-11-16

**最终结论：ACCEPT。** 首轮时钟缺陷已修复：search 与 hint 使用同一 `perf_counter` 绝对截止，run 以 `perf_counter` 扣减搜索耗时；不存在混用 monotonic。新回归以 6 ms 的构造耗时超过 5 ms Hint 预算，断言未加 Hint；另断言 10 ms 总预算扣去 6 ms 后 CP-SAT 得到 4 ms。审查当前代码并重新执行 `uv run --locked --python 3.11 --group dev pytest tests/unit/test_initial_search.py -q`：17 passed in 2.02s。`git diff --check` 通过，只有 Git CRLF 提示。此前 192 例独立枚举、代表性能检查和联合全量结果适用的限制仍如上所述；修后联合全量由 root 执行，须以其实测结果作为 G2/G5 依据。
