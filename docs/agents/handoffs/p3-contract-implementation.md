# P3 contract implementation: validator

来源：已通过 G1 的 `docs/work-packages/p3-contract-temp-plan.v001.md`，实施专项；未进行 G3。

- `validation_context.py` 增加结构化 `NotStartedEvidence` 与 `ValidationContext.not_started`；字段为 task_id、base_plan_id、planned_device_id、planned_start、planned_end、planned_person_id、blocked_at、observed_at、event_id。
- `validation/index.py` 验证快照、基准、时间、原分配、状态、记录与唯一性；非法证据产生 V10 NOT_STARTED_EVIDENCE_INVALID 且不解除冻结；有效证据仅解除旧开始时间推定。其余规则不变。事件真实性由调用方负责。
- `tests/unit/validation/test_validator_execution.py` 覆盖合法、缺失、错误字段、重复、快照不匹配、执行记录冲突及运行状态。

验证：`python tools/verify_source.py` 全部 PASS；`uv run --python 3.11 --group dev pytest tests/unit/validation tests/unit/test_validation_context.py -q` 101 passed；`uv run --python 3.11 --group dev ruff check src/scheduler_core/validation_context.py src/scheduler_core/validation/index.py tests/unit/validation/test_validator_execution.py` 通过；`uv run --python 3.11 --group dev mypy src/scheduler_core/validation_context.py src/scheduler_core/validation/index.py` 通过。全项目检查及独立 G3 由 root 组织。
