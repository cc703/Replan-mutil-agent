# P3 迟开证据实施交接

来源：root 派发，P3 temp v001 已通过增量 G1；证据字段与校验器专项对齐。未提交或推送，未宣称 G3 通过。

- runtime.py 在真实 setup/start 阻塞时记录绑定当前计划及事件的未开工事实，任务开始时撤销；采用变更的任务撤销，未变且仍未开工任务由引擎重新观察并绑定新基准。
- gate.py 在调用前生成内部快照，四参回调获得独立副本；旧回调及超时派生验证使用相同事实。失败/重试不清除事实。
- runtime、gate、trigger 接入事件撤销日志，触发窗口使用写时复制，设备窗口 AVL 写路径复制，状态监听采用回调快照。
- test_not_started.py 覆盖默认一槽阻塞、四参快照隔离、重排后执行、失败重试及精确回放。

验证：`python tools/verify_source.py` 全通过；`uv run --python 3.11 --group dev pytest tests/simulator -q` 108 passed（加入第二个测试前）；`uv run --python 3.11 --group dev pytest tests/simulator/test_not_started.py -q` 2 passed。独立 G3 仍需完整覆盖多次重绑定、回滚和边界。回调外部副作用不能由事务撤销。

G3 返工：状态变更先更新状态与日志，通知延后至事件完整派发和入队之后，仍在事务提交前；嵌套运行各自保存通知批次。新增状态监听重入运行完成与精确回放，以及内层完成后外层异常回滚的对照回归。`uv run --python 3.11 --group dev pytest tests/simulator -q`：112 passed。

G3 多次重绑定探索：默认延迟下 TASK_START 阻塞于 planned_start，下一槽 V4 START_BEFORE_NOW 禁止原 assignment 维持，因此该路径不能采纳不变 assignment。SETUP_START 可早于 planned_start，存在不同时间窗口；尝试实际超时占用导致准备阻塞，候选受运行记录和资源约束拒绝，此尝试不足以证明所有准备阻塞不可达；该项仍待独立 G3 验证，未新增不真实的端到端测试。

G3 人员语义返工：设备准备仅检查设备可用和容量；任务执行才检查人员日历及运行占用，其他设备上的准备不占人员。新增人员执行其他任务期间正常准备、之后执行及精确回放测试。`uv run --python 3.11 --group dev pytest tests/simulator -q`：116 passed。
