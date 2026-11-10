"""Stable lookup tables for one validation call."""

from collections import Counter
from dataclasses import dataclass

from ..models import Assignment, Device, Instance, Person, Plan, Task
from ..validation_context import ExecutionRecord, ValidationContext
from .report import ViolationCollector


@dataclass(frozen=True)
class ValidationIndex:
    tasks: dict[str, Task]
    devices: dict[str, Device]
    persons: dict[str, Person]
    records: dict[str, ExecutionRecord]
    assigned: dict[str, Assignment]
    old: dict[str, Assignment]
    frozen: set[str]


def build_index(
    inst: Instance,
    plan: Plan,
    base: Plan | None,
    ctx: ValidationContext,
    collector: ViolationCollector,
) -> ValidationIndex:
    """Build stable indexes and report duplicate IDs and assignment keys."""
    add = collector.add
    for entity, code, reason in (
        (inst.tasks, "V1", "DUPLICATE_TASK_ID"),
        (inst.devices, "V1", "DUPLICATE_DEVICE_ID"),
        (inst.persons, "V7", "DUPLICATE_PERSON_ID"),
    ):
        for identifier, count in sorted(Counter(item.id for item in entity).items()):
            if count > 1:
                if reason == "DUPLICATE_TASK_ID":
                    add(code, reason, [identifier])
                elif reason == "DUPLICATE_DEVICE_ID":
                    add(code, reason, device=identifier)
                else:
                    add(code, reason, person_id=identifier)
    tasks = {t.id: t for t in sorted(inst.tasks, key=lambda item: item.model_dump_json())}
    devices = {d.id: d for d in sorted(inst.devices, key=lambda item: item.model_dump_json())}
    persons = {p.id: p for p in sorted(inst.persons, key=lambda item: item.model_dump_json())}
    records = (
        {
            r.task_id: r
            for r in sorted(ctx.snapshot.records, key=lambda item: item.model_dump_json())
        }
        if ctx.snapshot
        else {}
    )
    assigned = plan.assignments
    old = base.assignments if base else {}
    for source, assignments in (("plan", assigned), ("base", old)):
        for key, assignment in sorted(assignments.items()):
            if key != assignment.task_id:
                add(
                    "V1",
                    "ASSIGNMENT_KEY_MISMATCH",
                    sorted({key, assignment.task_id}),
                    assignment.device_id,
                    source=source,
                )
    frozen = {
        t.id
        for t in inst.tasks
        if t.status in ("RUNNING", "DONE")
        or (
            base is not None
            and t.status in ("PENDING", "SCHEDULED")
            and t.id in old
            and old[t.id].start < inst.now
        )
    }
    return ValidationIndex(tasks, devices, persons, records, assigned, old, frozen)
