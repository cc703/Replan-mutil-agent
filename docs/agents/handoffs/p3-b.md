# P3 B 引擎交接

状态：实现已提交 root 待独立审查，不等于 P3 验收。依据侧栏 Claude 计划 v001、工作包 p3.md 与 root 的事件订阅澄清；模型 gpt-6.1-terra，high，fork_turns=none。专项未提交或推送。

交付：`engine.py` 实现事件堆、半开续跑、可复现扰动、注入、计划派生事件的按任务失效及运行视图；`runtime.py` 实现状态与事件应用、故障和维护中断、重启、资源就绪与日历索引；`trigger.py` 实现合并、冷却、重试与放弃；`gate.py` 生成快照与延长证据并调用独立校验器决定采纳；`replay.py` 支持精确和配对回放；`metrics.py` 计算运行指标。事件入队、拒绝候选由 A 的规范日志记录，确保重建与校验。真实事件订阅通过 `add_event_listener`，事件应用后通知，异常回滚该事件；`add_status_listener` 仍提供 StatusChange。`calendar` 提供带 device_id 的 BlockedWindow，由 C 转换为 CalendarWindow。

验收证据（2026-11-16，包含当时 C 文件，不代替最终全量门禁）：
- `uv run --python 3.11 --group dev pytest tests/simulator -q`：94 passed。
- `uv run --python 3.11 --group dev mypy --explicit-package-bases tests/simulator src/simulator`：37 files success。
- `uv run --python 3.11 --group dev ruff check src/simulator tests/simulator`：通过；`ruff format --check src/simulator tests/simulator`：37 files formatted。
- `uv run --python 3.11 --group dev python tools/check_import_boundaries.py`：Imports PASS；`python tools/verify_source.py`：来源全部 PASS（启动时执行）。未运行全仓 `tools/check.py`，交 root 在阶段集成后执行。

覆盖重点：半开同槽与续跑、容量 2 并发准备及双任务故障中断、维护抢占、重复中断与重启 ID、无冲突超时派生及设备/人员/截止期/前后约束冲突触发、V1/V2/V7/parent/DONE 拒绝、RUNNING 证据逐字段断言、新计划仅变更任务的旧事件失效、事件监听异常回滚、带入队证据的无抽样精确回放及配对外生流、紧急流对故障流独立性。独立逐槽参考覆盖 100 个单任务故障参数组合（部分组合重复）、80 个容量 2 双任务 setup/故障组合、36 个提前/超时组合、一个脚本化重规划；不声称覆盖全部参数或状态边。规模探针：10^9 槽稀疏场景 2 事件；2000 任务/50 设备无扰动 4000 次入队和 4000 事件，单故障入队小于 4100。

局限与待审：测试助手仅提供脚本调度器，计划所述完整贪心测试调度器未实现；冻结人员/设备改写、所有 gate 拒绝组合、独立参考更广泛的重规划和边复制组合未穷尽。设备/人员日历查询为二分索引，但添加故障窗口重建该设备索引；存在监听器时为满足异常回滚而复制事件前状态，不能声称该路径的每事件 O(log n)。队列操作使用 heapq，规模探针未在订阅模式下覆盖上述开销。当前自洽日志不能在没有可信外部摘要时证明任意单字段被篡改；保证范围以工作包记录的结构、哈希与重演一致性为准。独立 G3 需复核这些限制、真实事件订阅与全部要求，不得根据本交接自行宣称 ACCEPT。

## G3 返工（待复审）

scheduler 回调抛异常时，调用不提交窗口或调用日志，异常原样上抛并保留原 seq 的 flush 供续跑；若此后同槽注入更高优先级事件，先应用该事件并并入重规划批次。新增无异常结果对照、精确回放、同槽注入回归。设备查找、运行与 setup demand、人员 setup 及设备 setup 数量改为索引或增量计数，忙碌时长按首个运行任务开始、最后一个结束累计；新计划改变正在准备的任务时释放旧准备占用。新增 50 设备/200 事件不遍历设备集合或全体准备任务探针、并发任务跨多次 run 的忙碌时长、准备中改计划场景。

验证：`uv run --python 3.11 --group dev pytest tests/simulator -q`：99 passed；`ruff check src/simulator tests/simulator`、`ruff format --check src/simulator tests/simulator`、`mypy --explicit-package-bases tests/simulator src/simulator` 均通过。最后复跑 `pytest tests/simulator/test_trigger.py tests/simulator/test_engine_order.py tests/simulator/test_engine_scale.py -q --durations=3`：16 passed，2000 任务无扰动 1.05 秒、单故障 1.43 秒、50 设备无扫描探针 0.04 秒，耗时仅记录而非门槛；mypy 37 files success。

剩余复杂度限制：故障窗口插入重建该设备索引；故障实例与中断重启构造仍复制全实例；启用监听器时为了事件异常回滚复制状态；回放生成事件检索扫描日志。故障及订阅路径尚不能声称普遍每事件 O(log n)，须由独立 G3 裁定。未复跑全仓 tools/check.py。

## 追加返工与阻断（待 G3 复核）

回放在初始化时一次索引生成事件；设备窗口采用增量 AVL 区间树。测试贪心 helper 已实现冻结、已报告超时、设备容量、setup、人员技能与日历、release、前驱 lag、截止和独立 validate 自检；未宣称求解完备。自动超时冲突的回调事件现携带 TaskOverrun 的准确 new_end。新增 AVL 对扫描差分、日志只遍历一次、贪心冻结/人员/lag、容量/setup/阻塞、超时证据测试。

监听器事务改为 history 长度截断、事件堆及 epoch 的嵌套撤销日志；监听器重入 run 并注入事件后异常，与无监听直接运行的结果逐项相同。运行态/实例仍逐事件快照，故该路径仍非 O(log n)。同一实测：50 任务/100 事件无监听 0.014 秒、空监听 0.149 秒；300 任务/600 事件无监听 0.099 秒、空监听 3.887 秒。故障窗口插入现已 O(log w)；故障事件本身的实例及重启副本仍需全实例复制。本次分组 `pytest tests/simulator -q` 105 passed，ruff check 与 mypy 37 files 通过；未重新运行全仓检查。

阻断：scheduler_core/validation/index.py:67-75 将旧计划 start < inst.now 的 PENDING/SCHEDULED 冻结。U4 迟开在 t 触发、默认 t+1 重规划时，迟开任务已满足该条件，不能修改旧计划的开始和结束，独立校验会报 V8/V11；不得绕过校验或擅改 P1。已报告 root 和 G3，须先按项目流程确定契约处理。
