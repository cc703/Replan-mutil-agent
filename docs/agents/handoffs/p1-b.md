# P1-B 实施交接（G2，自检完成，待 G3）

实施模型：GPT-6.1 Terra，high，fork_turns=none。测试专项独占两个测试文件；总设计师负责集成、进度、Git 与同步。计划来源：`docs/work-packages/p1-b.md` 中 Claude 消息 70、72 与 Δ-B2；原始设计见 `docs/source/`，开源项目仅参考问题分解，没有复制代码、增加依赖或使用随机来源。

## 文件与边界

- `src/scheduler_core/validation_context.py`：六类 Pydantic 执行证据和授权结构；事件 ID 不是人类确认，授权真实性由上层 L1/L2 负责。
- `src/scheduler_core/validate.py`：独立 V1–V11、排序及资源扫描；未使用求解器。
- `tests/unit/test_validation_context.py`、`tests/unit/test_validate.py`：结构、令牌正反、确定性和独立穷举 oracle。
- `data/fixtures/mini.json`：人工实例；黄金计划仅验证可行性，不声称最优。
- `README.md`：使用方式、令牌与语义；本工作包原文未修改。

## 实际检查（2026-11-10）

- `uv run --python 3.11 --group dev python -m pytest tests -q -p no:cacheprovider`：162 passed，1 skipped，1 warning，9.00s。跳过为现有 `test_verify_source.py:164` 系统符号链接权限；关闭 cacheprovider 的现有 cache_dir 配置产生警告。
- `uv run --python 3.11 --group dev python tools/check.py`：162 passed，1 skipped；layout、import、source、ruff、format、mypy 全 PASS，mypy 覆盖 15 个源文件。
- `uv run --python 3.11 --group dev python tools/check_repo_layout.py`：PASS。
- `uv run --python 3.11 --group dev python tools/verify_source.py`：所有来源文件与分块 PASS。
- `git diff --check`：无空白错误（README 的 Git 行尾转换提示不影响检查）。共享树中的进度/派发文件属于总设计师的独立改动。

穷举使用 `itertools`，未使用随机来源。重叠 oracle：15 个区间的三重可重复组合 680×3 人员掩码，加 3 个四任务特例×3，共 2049 例；容量 oracle：5 区间三重组合 35×27 需求×4 容量，共 3780 例，覆盖需求 1/2/3 与容量 1/2/3/4 全部 12 种组合。独立 oracle 与被测实现分离。测试声明实例下限，检查参与集合、连通分量、报告条数上界、最大溢出段和参与任务并集。

工程保守取值：FAILED/CANCELLED/INTERRUPTED 不得分配；冲突 setup 取较大值并报告；视野越界归 V6；有 base 必须匹配 parent；`free=None` 不检查邻域，空集禁止非冻结任务变化；快照绑定 base（无 base 时绑定 plan）和当前时槽；RUNNING 窗口仅有效绑定时去重，未绑定且发生占用时报告；事件与确认的真实性不由校验器证明。求解器、仿真器、ArtifactStore 和后续阶段均不属于本包。

## 令牌正反覆盖

每行所列同一测试包含产生该令牌和不产生该令牌的情形；参数化测试名为 pytest 函数名。映射由测试中的 `REASON_COVERAGE` 逐项展开；`test_reason_coverage_inventory` 核对 61 个令牌的清单与测试名。

| reason | 正例测试 | 反例测试 |
| --- | --- | --- |
| ADDED_NOT_FREE | `test_neighborhood_reasons` | `test_neighborhood_reasons` |
| ASSIGNMENT_KEY_MISMATCH | `test_assignment_key_mismatch_after_mutation` | `test_assignment_key_mismatch_after_mutation` |
| AUTH_DUPLICATE | `test_deadline_authorization_matrix` | `test_deadline_authorization_matrix` |
| AUTH_EXPIRED | `test_deadline_authorization_matrix` | `test_deadline_authorization_matrix` |
| AUTH_FUTURE | `test_deadline_authorization_matrix` | `test_deadline_authorization_matrix` |
| AUTH_NOT_APPLICABLE | `test_deadline_authorization_matrix` | `test_deadline_authorization_matrix` |
| AUTH_OUT_OF_SCOPE | `test_deadline_authorization_matrix` | `test_deadline_authorization_matrix` |
| BASE_REQUIRED | `test_neighborhood_reasons` | `test_neighborhood_reasons` |
| BASE_TASK_UNKNOWN | `test_neighborhood_reasons` | `test_neighborhood_reasons` |
| CALENDAR_BLOCKED | `test_setup_calendar_and_half_open` | `test_setup_calendar_and_half_open` |
| CAPACITY_EXCEEDED | `test_exhaustive_capacity_oracle` | `test_exhaustive_capacity_oracle` |
| DEADLINE_EXCEEDED | `test_deadline_authorization_matrix` | `test_deadline_authorization_matrix` |
| DEMAND_EXCEEDS_CAPACITY | `test_exhaustive_capacity_oracle` | `test_exhaustive_capacity_oracle` |
| DEVICE_NOT_COMPATIBLE | `test_v1_reason_matrix` | `test_v1_reason_matrix` |
| DEVICE_OVERLAP | `test_exhaustive_overlap_oracle` | `test_exhaustive_overlap_oracle` |
| DONE_END_AFTER_NOW | `test_snapshot_and_frozen_reason_matrix` | `test_snapshot_and_frozen_reason_matrix` |
| DONE_HISTORY_REWRITTEN | `test_done_history_and_missing_base_as_of` | `test_done_history_and_missing_base_as_of` |
| DONE_NO_EVIDENCE | `test_done_real_completion` | `test_done_real_completion` |
| DUPLICATE_DEVICE_ID | `test_duplicate_ids_after_mutation` | `test_duplicate_ids_after_mutation` |
| DUPLICATE_PERSON_ID | `test_duplicate_ids_after_mutation` | `test_duplicate_ids_after_mutation` |
| DUPLICATE_TASK_ID | `test_duplicate_ids_after_mutation` | `test_duplicate_ids_after_mutation` |
| DURATION_MISMATCH | `test_time_and_setup_reason_matrix` | `test_time_and_setup_reason_matrix` |
| EMPTY_COMPATIBLE_LIST | `test_v1_reason_matrix` | `test_v1_reason_matrix` |
| END_MISMATCH | `test_done_real_completion` | `test_done_real_completion` |
| FREE_CONTAINS_FROZEN | `test_neighborhood_reasons` | `test_neighborhood_reasons` |
| FREE_UNKNOWN_TASK | `test_neighborhood_reasons` | `test_neighborhood_reasons` |
| FROZEN_DEVICE_CHANGED | `test_done_history_and_missing_base_as_of` | `test_done_history_and_missing_base_as_of` |
| FROZEN_END_EVIDENCE_INVALID | `test_running_end_evidence_scope` | `test_running_end_evidence_scope` |
| FROZEN_END_NO_EVIDENCE | `test_running_end_evidence_matrix` | `test_running_end_evidence_matrix` |
| FROZEN_MISSING | `test_snapshot_and_frozen_reason_matrix` | `test_snapshot_and_frozen_reason_matrix` |
| FROZEN_PERSON_CHANGED | `test_snapshot_and_frozen_reason_matrix` | `test_snapshot_and_frozen_reason_matrix` |
| FROZEN_START_CHANGED | `test_done_history_and_missing_base_as_of` | `test_done_history_and_missing_base_as_of` |
| HORIZON_EXCEEDED | `test_time_and_setup_reason_matrix` | `test_time_and_setup_reason_matrix` |
| MISSING_ASSIGNMENT | `test_v1_reason_matrix` | `test_v1_reason_matrix` |
| MISSING_PERSON | `test_person_skill_and_calendar` | `test_person_skill_and_calendar` |
| NONFREE_CHANGED | `test_neighborhood_reasons` | `test_neighborhood_reasons` |
| NO_FROZEN_REFERENCE | `test_snapshot_and_frozen_reason_matrix` | `test_snapshot_and_frozen_reason_matrix` |
| PARENT_MISMATCH | `test_neighborhood_reasons` | `test_neighborhood_reasons` |
| PERSON_OVERLAP | `test_exhaustive_overlap_oracle` | `test_exhaustive_overlap_oracle` |
| PERSON_UNAVAILABLE | `test_person_skill_and_calendar` | `test_person_skill_and_calendar` |
| PRECEDENCE_CYCLE | `test_precedence_reasons_and_boundaries` | `test_precedence_reasons_and_boundaries` |
| PRECEDENCE_MAX_LAG | `test_precedence_reasons_and_boundaries` | `test_precedence_reasons_and_boundaries` |
| PRECEDENCE_MIN_LAG | `test_precedence_reasons_and_boundaries` | `test_precedence_reasons_and_boundaries` |
| PRECEDENCE_UNKNOWN_TASK | `test_precedence_reasons_and_boundaries` | `test_precedence_reasons_and_boundaries` |
| RELEASE_VIOLATED | `test_time_and_setup_reason_matrix` | `test_time_and_setup_reason_matrix` |
| REMOVED_NOT_FREE | `test_neighborhood_reasons` | `test_neighborhood_reasons` |
| RUNNING_BLOCK_BINDING_INVALID | `test_invalid_running_bindings` | `test_invalid_running_bindings` |
| RUNNING_BLOCK_UNBOUND | `test_running_unbound_windows` | `test_running_unbound_windows` |
| RUNNING_NO_SNAPSHOT | `test_snapshot_and_frozen_reason_matrix` | `test_snapshot_and_frozen_reason_matrix` |
| SETUP_BEFORE_ORIGIN | `test_setup_calendar_and_half_open` | `test_setup_calendar_and_half_open` |
| SETUP_RULE_CONFLICT | `test_time_and_setup_reason_matrix` | `test_time_and_setup_reason_matrix` |
| SKILL_MISSING | `test_person_skill_and_calendar` | `test_person_skill_and_calendar` |
| SNAPSHOT_PLAN_MISMATCH | `test_snapshot_and_frozen_reason_matrix` | `test_snapshot_and_frozen_reason_matrix` |
| SNAPSHOT_RECORD_INVALID | `test_snapshot_and_frozen_reason_matrix` | `test_snapshot_and_frozen_reason_matrix` |
| SNAPSHOT_STALE | `test_snapshot_and_frozen_reason_matrix` | `test_snapshot_and_frozen_reason_matrix` |
| START_BEFORE_NOW | `test_time_and_setup_reason_matrix` | `test_time_and_setup_reason_matrix` |
| TASK_NOT_SCHEDULABLE | `test_v1_reason_matrix` | `test_v1_reason_matrix` |
| UNKNOWN_DEVICE | `test_v1_reason_matrix` | `test_v1_reason_matrix` |
| UNKNOWN_DEVICE_REF | `test_v1_reason_matrix` | `test_v1_reason_matrix` |
| UNKNOWN_PERSON | `test_person_skill_and_calendar` | `test_person_skill_and_calendar` |
| UNKNOWN_TASK | `test_v1_reason_matrix` | `test_v1_reason_matrix` |
