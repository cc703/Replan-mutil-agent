# P3 订阅事务专项交接

来源：root 分派，采用 temp v001 已通过 G1 的订阅事务方案。仅修改 engine.py、新增 transaction.py 和 tests/simulator/test_transaction.py；runtime/gate/trigger 写点由并行专项负责。未提交、推送。

UndoJournal 按写入记录逆操作，嵌套提交合并至父事务，回滚逆序执行；engine 在订阅或父事务存在时建立事件事务，联动现有嵌套队列事务，记录事件历史追加、统计、注入、生成事件、订阅新增和时钟，事件通知使用订阅快照。内部回调的外部 I/O 和用户对象副作用不可撤销。新证据表及上下文回调入口初始化由 engine 提供，业务生命周期由并行专项负责。队列失败回滚仍按堆大小扫描；正常处理不全量复制队列。held events 快照只涉及当前重入持有事件，不复制历史或实例。

验证：python tools/verify_source.py 全部 PASS；uv run --python 3.11 --group dev pytest tests/simulator/test_engine_order.py tests/simulator/test_queue.py tests/simulator/test_transaction.py -q：14 passed；uv run --python 3.11 --group dev pytest tests/simulator -q：107 passed；uv run --python 3.11 --group dev ruff check src/simulator/engine.py src/simulator/transaction.py tests/simulator/test_transaction.py：通过。第一次定向测试在运行态钩子尚未合入时有 3 失败，后续合入后通过。

局限：独立 G3 尚未进行；需重点审计所有运行态及门禁写点、回调异常和嵌套情形、复杂度及回放。完整项目检查由 root 协调。

G3 返工：事件监听器成功重入并推进到更晚时间时，外层 run 的结果截止取请求截止与已推进时钟的最大值，确保状态、指标和 END_RUN 一致。新增成功重入、精确回放及继续运行对照测试。tests/simulator 110 passed；engine mypy、ruff 通过。状态监听器中途重入的事件完整性另交运行态专项处理。
