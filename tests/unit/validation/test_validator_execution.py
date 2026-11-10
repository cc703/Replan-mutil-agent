"""Acceptance checks for independent schedule validation."""

from scheduler_core.models import (
    Assignment,
    Plan,
)
from scheduler_core.validate import validate
from scheduler_core.validation_context import (
    FrozenEndChange,
)
import pytest


from .validation_helpers import execution_case, instance, reasons


def test_running_end_evidence_matrix() -> None:
    inst, plan, base, ctx = execution_case("RUNNING", 14)
    change = FrozenEndChange(
        task_id="a",
        plan_id="new",
        base_plan_id="base",
        old_end=10,
        new_end=14,
        event_id="event",
        acted_at=10,
    )
    assert reasons(
        validate(inst, plan, base=base, context=ctx), "V11", "FROZEN_END_NO_EVIDENCE"
    ) == [["a"]]
    ctx.end_changes.append(change)
    assert validate(inst, plan, base=base, context=ctx).passed


@pytest.mark.parametrize(
    "field,value",
    [
        ("task_id", "other"),
        ("plan_id", "other"),
        ("base_plan_id", "other"),
        ("old_end", 9),
        ("new_end", 15),
        ("acted_at", 11),
    ],
)
def test_running_end_evidence_scope(field: str, value: object) -> None:
    inst, plan, base, ctx = execution_case("RUNNING", 14)
    change = FrozenEndChange(
        task_id="a",
        plan_id="new",
        base_plan_id="base",
        old_end=10,
        new_end=14,
        event_id="event",
        acted_at=10,
    )
    ctx.end_changes = [change]
    assert validate(inst, plan, base=base, context=ctx).passed
    ctx.end_changes = [change.model_copy(update={field: value})]
    report = validate(inst, plan, base=base, context=ctx)
    assert reasons(report, "V11", "FROZEN_END_EVIDENCE_INVALID") == (
        [["other"]] if field == "task_id" else [["a"]]
    )
    ctx.end_changes[0] = change.model_copy(update={"base_plan_id": "wrong"})
    assert reasons(
        validate(inst, plan, base=base, context=ctx), "V11", "FROZEN_END_EVIDENCE_INVALID"
    ) == [["a"]]
    ctx.end_changes = [change, change]
    assert reasons(
        validate(inst, plan, base=base, context=ctx), "V11", "FROZEN_END_EVIDENCE_INVALID"
    ) == [["a"]]
    plan.assignments["a"] = plan.assignments["a"].model_copy(update={"end": 9})
    assert reasons(validate(inst, plan, base=base, context=ctx), "V10", "END_MISMATCH") == [["a"]]
    inst, plan, base, ctx = execution_case("RUNNING", 10, remaining=0)
    ctx.end_changes = [change]
    assert reasons(
        validate(inst, plan, base=base, context=ctx), "V11", "FROZEN_END_EVIDENCE_INVALID"
    ) == [["a"]]
    ctx.end_changes = []
    assert validate(inst, plan, base=base, context=ctx).passed


@pytest.mark.parametrize("actual", [8, 12])
def test_done_real_completion(actual: int) -> None:
    inst, plan, base, ctx = execution_case("DONE", actual, actual=actual)
    assert validate(inst, plan, base=base, context=ctx).passed
    plan.assignments["a"] = plan.assignments["a"].model_copy(update={"end": actual + 1})
    assert reasons(validate(inst, plan, base=base, context=ctx), "V10", "END_MISMATCH") == [["a"]]
    ctx.snapshot = None
    assert reasons(validate(inst, plan, base=base, context=ctx), "V10", "DONE_NO_EVIDENCE") == [
        ["a"]
    ]


def test_done_history_and_missing_base_as_of() -> None:
    inst, plan, base, ctx = execution_case("DONE", 8, actual=8, base_as_of=8)
    assert reasons(
        validate(inst, plan, base=base, context=ctx), "V10", "DONE_HISTORY_REWRITTEN"
    ) == [["a"]]
    base.assignments["a"] = plan.assignments["a"]
    assert validate(inst, plan, base=base, context=ctx).passed
    assert ctx.snapshot is not None
    ctx.snapshot.base_as_of = None
    assert reasons(
        validate(inst, plan, base=base, context=ctx), "V10", "SNAPSHOT_RECORD_INVALID"
    ) == [["a"]]
    ctx.snapshot.base_as_of = 8
    plan.assignments["a"] = plan.assignments["a"].model_copy(
        update={"start": 1, "device_id": "other"}
    )
    report = validate(inst, plan, base=base, context=ctx)
    assert reasons(report, "V8", "FROZEN_START_CHANGED") == [["a"]]
    assert reasons(report, "V8", "FROZEN_DEVICE_CHANGED") == [["a"]]


@pytest.mark.parametrize(
    "token",
    [
        "RUNNING_NO_SNAPSHOT",
        "SNAPSHOT_STALE",
        "SNAPSHOT_PLAN_MISMATCH",
        "SNAPSHOT_RECORD_INVALID",
        "NO_FROZEN_REFERENCE",
        "FROZEN_MISSING",
        "FROZEN_PERSON_CHANGED",
        "DONE_END_AFTER_NOW",
    ],
)
def test_snapshot_and_frozen_reason_matrix(token: str) -> None:
    inst, plan, base, ctx = execution_case("RUNNING", 10, remaining=0)
    assert validate(inst, plan, base=base, context=ctx).passed
    code = (
        "V8"
        if token in ("NO_FROZEN_REFERENCE", "FROZEN_MISSING")
        else "V11"
        if token == "FROZEN_PERSON_CHANGED"
        else "V10"
    )
    ids: list[str] = ["a"]
    if token == "RUNNING_NO_SNAPSHOT":
        ctx.snapshot = None
    elif token == "SNAPSHOT_STALE":
        assert ctx.snapshot is not None
        ctx.snapshot.as_of = 9
        ids = []
    elif token == "SNAPSHOT_PLAN_MISMATCH":
        assert ctx.snapshot is not None
        ctx.snapshot.plan_id = "wrong"
        ids = []
    elif token == "SNAPSHOT_RECORD_INVALID":
        assert ctx.snapshot is not None
        ctx.snapshot.records[0].planned_end = 9
    elif token == "NO_FROZEN_REFERENCE":
        ctx.snapshot = None
        base = None  # type: ignore[assignment]
    elif token == "FROZEN_MISSING":
        plan.assignments.clear()
    elif token == "FROZEN_PERSON_CHANGED":
        plan.assignments["a"].person_id = "p"
    else:
        inst, plan, base, ctx = execution_case("DONE", 13, actual=12)
    assert reasons(validate(inst, plan, base=base, context=ctx), code, token) == [ids]


@pytest.mark.parametrize("status", ["PENDING", "SCHEDULED"])
def test_schedulable_statuses_and_frozen_end(status: str) -> None:
    inst = instance()
    inst.tasks = inst.tasks[:1]
    inst.tasks[0].status = status  # type: ignore[assignment]
    plan = Plan(
        id="p",
        parent_id="base",
        assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=4)},
    )
    base = plan.model_copy(deep=True)
    base.id = "base"
    inst.now = 1
    assert validate(inst, plan, base=base).passed
    inst.tasks[0].duration = 5
    plan.assignments["a"].end = 5
    assert reasons(validate(inst, plan, base=base), "V11", "FROZEN_END_NO_EVIDENCE") == [["a"]]
    plan.assignments.clear()
    assert reasons(validate(inst, plan, base=base), "V8", "FROZEN_MISSING") == [["a"]]


def test_snapshot_record_base_mismatch() -> None:
    inst, plan, base, ctx = execution_case("RUNNING", 10, remaining=0)
    assert ctx.snapshot is not None
    rec = ctx.snapshot.records[0]
    rec.start = 1
    report = validate(inst, plan, base=base, context=ctx)
    assert reasons(report, "V8", "FROZEN_START_CHANGED") == [["a"]]
    rec.start = 0
    rec.device_id = "z"
    report = validate(inst, plan, base=base, context=ctx)
    assert reasons(report, "V8", "FROZEN_DEVICE_CHANGED") == [["a"]]
    rec.device_id = "d"
    assert validate(inst, plan, base=base, context=ctx).passed
