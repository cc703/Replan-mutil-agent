# P3 A 独立检查与测试类型修正交接

检查角色：Codex 专项审查；模型 gpt-6.1-terra，high，fork_turns=none。依据 P3 Claude 计划 v001、工作包卡及实际源码；本次不是 P3 A 完整验收。

- 范围：检查 states、events、queue、log、sampling、scenarios、config 及指定测试；仅对 test_states、test_events、test_queue、test_log 做类型修正，不改变测试意图。test_states 后续交由 root 修改状态边断言。
- 发现：设备真实派生状态可能直接从 SETUP 或 BUSY 转入 MAINTENANCE，维护结束也可能返回 SETUP 或 BUSY；原状态表不允许这些边，日志记录亦引用该表。这与已裁定维护按时开始、显示真实状态冲突。已报告 root；需结合引擎处理和测试修正，不能虚构中间 IDLE。
- 检查结论：事件优先级表、队列键与惰性失效、采样的流索引和实体键、规范日志结构在所读范围内与计划基本一致；这不是穷尽性证明。未独立复核所有日志 kind 的正反例、所有采样边界、引擎及回放行为，也未完成 A 全量或 G3。
- 实际验证：`python tools/verify_source.py` 全部 PASS；`uv run --python 3.11 --group dev mypy tests/simulator/test_states.py tests/simulator/test_events.py tests/simulator/test_queue.py tests/simulator/test_log.py`：4 files 无问题；对应 `pytest -q`：18 passed。以上在 root 接手状态表之前运行，后续变更需重新验证。`git diff --check` 未报告空白错误（Git 对已有进度文件提示 CRLF）。
- 交付：四个测试的返回注解、可选值与联合类型收窄、负例使用 model_validate 保留运行时验证；DurationSampled 负例补齐必填 source，使其只针对严格类型失败。
- 未完成：完整 A 验收、计划要求的全部测试覆盖核验、维护状态边修复及端到端验证、全量检查与独立 G3；由 root 统筹。
