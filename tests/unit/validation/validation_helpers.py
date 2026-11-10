"""Acceptance checks for independent schedule validation."""

from datetime import datetime, timezone
from typing import Literal

from scheduler_core.axis import TimeAxis
from scheduler_core.models import (
    Assignment,
    Device,
    Instance,
    Person,
    Plan,
    Task,
)
from scheduler_core.validation_context import (
    ExecutionRecord,
    ExecutionSnapshot,
    ValidationContext,
)


def instance() -> Instance:
    return Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=40),
        devices=[Device(id="d", type="x")],
        tasks=[
            Task(id=x, experiment_id="e", type="x", duration=4, compatible_devices=["d"])
            for x in ("a", "b")
        ],
    )


def reasons(report: object, code: str, reason: str) -> list[list[str]]:
    from scheduler_core.models import ValidationReport

    assert isinstance(report, ValidationReport)
    return [
        v.task_ids for v in report.violations if v.code == code and f"reason={reason};" in v.detail
    ]


def execution_case(
    status: Literal["RUNNING", "DONE"],
    end: int,
    *,
    base_as_of: int | None = 5,
    actual: int = 8,
    remaining: int = 4,
) -> tuple[Instance, Plan, Plan, ValidationContext]:
    now = 10 if status == "RUNNING" else max(12, actual)
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=40),
        now=now,
        devices=[Device(id="d", type="x")],
        tasks=[
            Task(
                id="a",
                experiment_id="e",
                type="x",
                duration=10,
                compatible_devices=["d"],
                status=status,
            )
        ],
    )
    base = Plan(
        id="base", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=10)}
    )
    plan = Plan(
        id="new",
        parent_id="base",
        assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=end)},
    )
    if status == "RUNNING":
        rec = ExecutionRecord(
            task_id="a",
            status="RUNNING",
            device_id="d",
            start=0,
            planned_end=10,
            remaining_estimate=remaining,
            event_id="event",
        )
    else:
        rec = ExecutionRecord(
            task_id="a", status="DONE", device_id="d", start=0, actual_end=actual, event_id="event"
        )
    ctx = ValidationContext(
        snapshot=ExecutionSnapshot(plan_id="base", as_of=now, base_as_of=base_as_of, records=[rec])
    )
    return inst, plan, base, ctx


def overlap_case(intervals: tuple[tuple[int, int], ...], mask: int) -> tuple[Instance, Plan]:
    tasks = [
        Task(id=str(i), experiment_id="e", type="x", duration=e - s, compatible_devices=["d"])
        for i, (s, e) in enumerate(intervals)
    ]
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=10),
        devices=[Device(id="d", type="x")],
        tasks=tasks,
        persons=[Person(id="p")],
    )
    plan = Plan(
        id="p",
        assignments={
            str(i): Assignment(
                task_id=str(i),
                device_id="d",
                start=s,
                end=e,
                person_id="p" if mask & (1 << i) else None,
            )
            for i, (s, e) in enumerate(intervals)
        },
    )
    return inst, plan


def capacity_case(
    intervals: tuple[tuple[int, int], ...], demands: tuple[int, ...], cap: int
) -> tuple[Instance, Plan]:
    tasks = [
        Task(
            id=str(i),
            experiment_id="e",
            type="x",
            duration=e - s,
            compatible_devices=["d"],
            demand=demands[i],
        )
        for i, (s, e) in enumerate(intervals)
    ]
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=10),
        devices=[Device(id="d", type="x", capacity=cap)],
        tasks=tasks,
    )
    plan = Plan(
        id="p",
        assignments={
            str(i): Assignment(task_id=str(i), device_id="d", start=s, end=e)
            for i, (s, e) in enumerate(intervals)
        },
    )
    return inst, plan
