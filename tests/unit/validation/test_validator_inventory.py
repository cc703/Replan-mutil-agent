"""Acceptance checks for independent schedule validation."""

import ast
from pathlib import Path


REASON_COVERAGE: dict[str, tuple[str, ...]] = {
    "test_v1_reason_matrix": (
        "MISSING_ASSIGNMENT",
        "UNKNOWN_TASK",
        "UNKNOWN_DEVICE",
        "DEVICE_NOT_COMPATIBLE",
        "EMPTY_COMPATIBLE_LIST",
        "UNKNOWN_DEVICE_REF",
        "TASK_NOT_SCHEDULABLE",
    ),
    "test_assignment_key_mismatch_after_mutation": ("ASSIGNMENT_KEY_MISMATCH",),
    "test_duplicate_ids_after_mutation": (
        "DUPLICATE_TASK_ID",
        "DUPLICATE_DEVICE_ID",
        "DUPLICATE_PERSON_ID",
    ),
    "test_exhaustive_overlap_oracle": ("DEVICE_OVERLAP", "PERSON_OVERLAP"),
    "test_running_unbound_windows": ("RUNNING_BLOCK_UNBOUND",),
    "test_invalid_running_bindings": ("RUNNING_BLOCK_BINDING_INVALID",),
    "test_time_and_setup_reason_matrix": (
        "SETUP_RULE_CONFLICT",
        "RELEASE_VIOLATED",
        "START_BEFORE_NOW",
        "HORIZON_EXCEEDED",
        "DURATION_MISMATCH",
    ),
    "test_precedence_reasons_and_boundaries": (
        "PRECEDENCE_MIN_LAG",
        "PRECEDENCE_MAX_LAG",
        "PRECEDENCE_UNKNOWN_TASK",
        "PRECEDENCE_CYCLE",
    ),
    "test_deadline_authorization_matrix": (
        "DEADLINE_EXCEEDED",
        "AUTH_NOT_APPLICABLE",
        "AUTH_EXPIRED",
        "AUTH_FUTURE",
        "AUTH_OUT_OF_SCOPE",
        "AUTH_DUPLICATE",
    ),
    "test_setup_calendar_and_half_open": ("CALENDAR_BLOCKED", "SETUP_BEFORE_ORIGIN"),
    "test_person_skill_and_calendar": (
        "MISSING_PERSON",
        "UNKNOWN_PERSON",
        "SKILL_MISSING",
        "PERSON_UNAVAILABLE",
    ),
    "test_done_history_and_missing_base_as_of": (
        "FROZEN_DEVICE_CHANGED",
        "FROZEN_START_CHANGED",
        "DONE_HISTORY_REWRITTEN",
    ),
    "test_snapshot_and_frozen_reason_matrix": (
        "NO_FROZEN_REFERENCE",
        "FROZEN_MISSING",
        "RUNNING_NO_SNAPSHOT",
        "SNAPSHOT_STALE",
        "SNAPSHOT_PLAN_MISMATCH",
        "SNAPSHOT_RECORD_INVALID",
        "DONE_END_AFTER_NOW",
        "FROZEN_PERSON_CHANGED",
    ),
    "test_exhaustive_capacity_oracle": ("CAPACITY_EXCEEDED", "DEMAND_EXCEEDS_CAPACITY"),
    "test_done_real_completion": ("END_MISMATCH", "DONE_NO_EVIDENCE"),
    "test_neighborhood_reasons": (
        "PARENT_MISMATCH",
        "BASE_REQUIRED",
        "FREE_UNKNOWN_TASK",
        "FREE_CONTAINS_FROZEN",
        "ADDED_NOT_FREE",
        "REMOVED_NOT_FREE",
        "BASE_TASK_UNKNOWN",
        "NONFREE_CHANGED",
    ),
    "test_running_end_evidence_matrix": ("FROZEN_END_NO_EVIDENCE",),
    "test_running_end_evidence_scope": ("FROZEN_END_EVIDENCE_INVALID",),
}


def test_reason_coverage_inventory() -> None:
    expected = set(
        """MISSING_ASSIGNMENT UNKNOWN_TASK UNKNOWN_DEVICE DEVICE_NOT_COMPATIBLE EMPTY_COMPATIBLE_LIST UNKNOWN_DEVICE_REF TASK_NOT_SCHEDULABLE ASSIGNMENT_KEY_MISMATCH DUPLICATE_TASK_ID DUPLICATE_DEVICE_ID DUPLICATE_PERSON_ID DEVICE_OVERLAP RUNNING_BLOCK_UNBOUND RUNNING_BLOCK_BINDING_INVALID SETUP_RULE_CONFLICT PRECEDENCE_MIN_LAG PRECEDENCE_MAX_LAG PRECEDENCE_UNKNOWN_TASK PRECEDENCE_CYCLE RELEASE_VIOLATED START_BEFORE_NOW DEADLINE_EXCEEDED AUTH_NOT_APPLICABLE AUTH_EXPIRED AUTH_FUTURE AUTH_OUT_OF_SCOPE AUTH_DUPLICATE CALENDAR_BLOCKED HORIZON_EXCEEDED SETUP_BEFORE_ORIGIN MISSING_PERSON UNKNOWN_PERSON SKILL_MISSING PERSON_OVERLAP PERSON_UNAVAILABLE FROZEN_DEVICE_CHANGED FROZEN_START_CHANGED NO_FROZEN_REFERENCE FROZEN_MISSING CAPACITY_EXCEEDED DEMAND_EXCEEDS_CAPACITY DURATION_MISMATCH RUNNING_NO_SNAPSHOT SNAPSHOT_STALE SNAPSHOT_PLAN_MISMATCH SNAPSHOT_RECORD_INVALID END_MISMATCH DONE_NO_EVIDENCE DONE_END_AFTER_NOW DONE_HISTORY_REWRITTEN PARENT_MISMATCH BASE_REQUIRED FREE_UNKNOWN_TASK FREE_CONTAINS_FROZEN ADDED_NOT_FREE REMOVED_NOT_FREE BASE_TASK_UNKNOWN NONFREE_CHANGED FROZEN_PERSON_CHANGED FROZEN_END_NO_EVIDENCE FROZEN_END_EVIDENCE_INVALID""".split()
    )
    assert {token for tokens in REASON_COVERAGE.values() for token in tokens} == expected
    test_names = {
        node.name
        for path in Path(__file__).parent.glob("test_*.py")
        for node in ast.parse(path.read_text(encoding="utf-8")).body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    }
    assert all(name in test_names for name in REASON_COVERAGE)
