"""Structural acceptance tests for execution evidence."""

import pytest
from pydantic import BaseModel, ValidationError

from scheduler_core.validation_context import (
    DeadlineAuthorization,
    ExecutionRecord,
    ExecutionSnapshot,
    FrozenEndChange,
    RunningBlockBinding,
    ValidationContext,
)


def test_snapshot_roundtrip_and_independent_defaults() -> None:
    record = ExecutionRecord(
        task_id=" a ",
        status="RUNNING",
        device_id="d",
        start=1,
        planned_end=3,
        remaining_estimate=0,
        event_id="e",
    )
    snapshot = ExecutionSnapshot(plan_id="p", as_of=2, records=[record])
    context = ValidationContext(snapshot=snapshot)
    assert ValidationContext.model_validate_json(context.model_dump_json()) == context
    assert record.task_id == "a"
    assert ValidationContext().end_changes is not ValidationContext().end_changes


@pytest.mark.parametrize("value", [True, 1.0, -1])
def test_slot_rejects_invalid_values(value: object) -> None:
    with pytest.raises(ValidationError):
        ExecutionSnapshot.model_validate({"plan_id": "p", "as_of": value})


def test_snapshot_rejects_duplicate_and_future_records() -> None:
    rec = {
        "task_id": "a",
        "status": "RUNNING",
        "device_id": "d",
        "start": 1,
        "planned_end": 3,
        "remaining_estimate": 0,
        "event_id": "e",
    }
    for data in (
        {"plan_id": "p", "as_of": 1, "records": [rec, rec]},
        {"plan_id": "p", "as_of": 0, "records": [rec]},
    ):
        with pytest.raises(ValidationError):
            ExecutionSnapshot.model_validate(data)


def test_extra_and_deadline_bounds_rejected() -> None:
    with pytest.raises(ValidationError):
        ExecutionRecord.model_validate(
            {
                "task_id": "a",
                "status": "DONE",
                "device_id": "d",
                "start": 0,
                "actual_end": 1,
                "event_id": "e",
                "confirmation_id": "x",
            }
        )


CASES: list[tuple[type[BaseModel], dict[str, object], list[str], list[str]]] = [
    (
        ExecutionRecord,
        {
            "task_id": "a",
            "status": "RUNNING",
            "device_id": "d",
            "start": 1,
            "planned_end": 3,
            "remaining_estimate": 1,
            "event_id": "e",
        },
        ["start", "planned_end", "remaining_estimate"],
        ["task_id", "device_id", "event_id"],
    ),
    (
        ExecutionSnapshot,
        {"plan_id": "p", "as_of": 2, "base_as_of": 1},
        ["as_of", "base_as_of"],
        ["plan_id"],
    ),
    (
        FrozenEndChange,
        {
            "task_id": "a",
            "plan_id": "p",
            "base_plan_id": "b",
            "old_end": 3,
            "new_end": 4,
            "event_id": "e",
            "acted_at": 2,
        },
        ["old_end", "new_end", "acted_at"],
        ["task_id", "plan_id", "base_plan_id", "event_id"],
    ),
    (
        DeadlineAuthorization,
        {
            "task_id": "a",
            "plan_id": "p",
            "original_deadline": 3,
            "relaxed_deadline": 4,
            "confirmation_id": "c",
            "acted_at": 1,
            "valid_until": 2,
        },
        ["original_deadline", "relaxed_deadline", "acted_at", "valid_until"],
        ["task_id", "plan_id", "confirmation_id"],
    ),
    (
        RunningBlockBinding,
        {"task_id": "a", "device_id": "d", "start": 1, "end": 3},
        ["start", "end"],
        ["task_id", "device_id"],
    ),
    (ValidationContext, {}, [], []),
]


@pytest.mark.parametrize("cls,data,slots,ids", CASES)
def test_all_context_contracts(
    cls: type[BaseModel], data: dict[str, object], slots: list[str], ids: list[str]
) -> None:
    obj = cls.model_validate(data)
    assert cls.model_validate_json(obj.model_dump_json()) == obj
    with pytest.raises(ValidationError):
        cls.model_validate({**data, "unexpected": 1})
    for field in slots:
        for value in (True, 1.0, -1):
            with pytest.raises(ValidationError):
                cls.model_validate({**data, field: value})
    for field in ids:
        with pytest.raises(ValidationError):
            cls.model_validate({**data, field: "  "})
        assert getattr(cls.model_validate({**data, field: " x "}), field) == "x"


def test_context_relationships_and_confirmation_separation() -> None:
    invalid: list[tuple[type[BaseModel], dict[str, object]]] = [
        (
            ExecutionRecord,
            {
                "task_id": "a",
                "status": "DONE",
                "device_id": "d",
                "start": 2,
                "actual_end": 2,
                "event_id": "e",
            },
        ),
        (ExecutionSnapshot, {"plan_id": "p", "as_of": 1, "base_as_of": 2}),
        (
            FrozenEndChange,
            {
                "task_id": "a",
                "plan_id": "p",
                "base_plan_id": "b",
                "old_end": 3,
                "new_end": 3,
                "event_id": "e",
                "acted_at": 1,
            },
        ),
        (RunningBlockBinding, {"task_id": "a", "device_id": "d", "start": 2, "end": 2}),
        (
            DeadlineAuthorization,
            {
                "task_id": "a",
                "plan_id": "p",
                "original_deadline": 3,
                "relaxed_deadline": 4,
                "confirmation_id": "c",
                "acted_at": 2,
                "valid_until": 1,
            },
        ),
        (
            DeadlineAuthorization,
            {
                "task_id": "a",
                "plan_id": "p",
                "original_deadline": 3,
                "relaxed_deadline": 4,
                "acted_at": 1,
            },
        ),
        (
            FrozenEndChange,
            {
                "task_id": "a",
                "plan_id": "p",
                "base_plan_id": "b",
                "old_end": 3,
                "new_end": 4,
                "event_id": "e",
                "acted_at": 1,
                "confirmation_id": "c",
            },
        ),
    ]
    for cls, data in invalid:
        with pytest.raises(ValidationError):
            cls.model_validate(data)
    a, b = ValidationContext(), ValidationContext()
    assert a.end_changes is not b.end_changes
    assert a.deadline_authorizations is not b.deadline_authorizations
    assert a.running_block_bindings is not b.running_block_bindings
    assert (
        ExecutionSnapshot(plan_id="p", as_of=0).records
        is not ExecutionSnapshot(plan_id="p", as_of=0).records
    )
    with pytest.raises(ValidationError):
        ValidationContext.model_validate(
            {
                "deadline_authorizations": [
                    {
                        "task_id": "a",
                        "plan_id": "p",
                        "original_deadline": 2,
                        "relaxed_deadline": 1,
                        "confirmation_id": "c",
                        "acted_at": 0,
                    }
                ]
            }
        )


def test_done_record_fields_and_cross_field_relationships() -> None:
    done: dict[str, object] = {
        "task_id": "a",
        "status": "DONE",
        "device_id": "d",
        "person_id": " p ",
        "start": 1,
        "actual_end": 3,
        "event_id": "event",
    }
    obj = ExecutionRecord.model_validate(done)
    assert obj.person_id == "p"
    assert ExecutionRecord.model_validate_json(obj.model_dump_json()) == obj
    for value in (True, 1.0, -1):
        with pytest.raises(ValidationError):
            ExecutionRecord.model_validate({**done, "actual_end": value})
    with pytest.raises(ValidationError):
        ExecutionRecord.model_validate({**done, "person_id": " "})
    for changes in (
        {"actual_end": None},
        {"planned_end": 4},
        {"remaining_estimate": 1},
        {"actual_end": 1},
    ):
        with pytest.raises(ValidationError):
            ExecutionRecord.model_validate({**done, **changes})
    running: dict[str, object] = {
        "task_id": "a",
        "status": "RUNNING",
        "device_id": "d",
        "start": 1,
        "planned_end": 3,
        "remaining_estimate": 0,
        "event_id": "event",
    }
    for changes in (
        {"planned_end": None},
        {"remaining_estimate": None},
        {"actual_end": 2},
        {"planned_end": 1},
    ):
        with pytest.raises(ValidationError):
            ExecutionRecord.model_validate({**running, **changes})
    with pytest.raises(ValidationError):
        ExecutionSnapshot.model_validate({"plan_id": "p", "as_of": 2, "records": [done]})
