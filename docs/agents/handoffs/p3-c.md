# P3-C 交接

- 角色：专项实施；gpt-6.1-terra / high / fork none。来源：`docs/work-packages/p3-claude-plan.v001.md` C 与 CB-P3、root G1 工程澄清。
- `base.py` 定义协议、不可变日历窗口和回调异常；`simulated.py` 实现查询、日历映射、计划开工确认和事件订阅；`manual.py` 转发三种外部事件；`__init__.py` 导出公共接口。测试 `tests/simulator/adapters/test_runtime_conformance.py` 以真实 Simulator 检查协议、时间与事件、回滚及注入。
- 协议对应：list_devices→list_devices，get_status→device_status，get_calendar→calendar（BlockedWindow 映射并使用引擎的裁剪），start_task→confirm_start，subscribe→add_event_listener，手动注入→inject。原 add_status_listener 继续提供 StatusChange；新事件监听由 B 提供真实 SimEvent，dispatch 后通知并对异常回滚当前事件。root 已裁定此接口细化。
- 限制：start_task 只确认当前计划，不触发开工；RealAdapter 仅文档预留；事件合法性和运行态验证由引擎负责。
- 验证：`python tools/verify_source.py` 全部 PASS；`uv run --python 3.11 --group dev pytest tests/simulator/adapters -q` 5 passed；`uv run --python 3.11 --group dev ruff check src/simulator/adapters tests/simulator/adapters` 通过；`uv run --python 3.11 --group dev mypy src/simulator/adapters tests/simulator/adapters` 通过；`git diff --check` 通过（现有进度文件 CRLF 提示）。
- 未提交、未推送。引擎在途，整体独立审查和全量检查由 root 组织。
