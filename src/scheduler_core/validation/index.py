"""Stable lookup tables for one validation call."""

from collections import Counter
from dataclasses import dataclass

from pydantic import ValidationError

from ..models import Assignment, Device, Instance, Person, Plan, Task
from ..validation_context import ExecutionRecord, NotStartedEvidence, ValidationContext
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
    counts = Counter(e.task_id for e in ctx.not_started)
    valid_not_started: set[str] = set()
    snap = ctx.snapshot
    for evidence in ctx.not_started:
        tid = evidence.task_id
        task, previous = tasks.get(tid), old.get(tid)
        try:
            NotStartedEvidence.model_validate(evidence.model_dump())
            valid = (
                counts[tid] == 1
                and base is not None
                and snap is not None
                and snap.plan_id == base.id
                and snap.as_of == inst.now
                and snap.base_as_of is not None
                and evidence.base_plan_id == base.id
                and task is not None
                and task.status in ("PENDING", "SCHEDULED")
                and previous is not None
                and previous.task_id == tid
                and evidence.planned_device_id == previous.device_id
                and evidence.planned_start == previous.start
                and evidence.planned_end == previous.end
                and evidence.planned_person_id == previous.person_id
                and evidence.blocked_at <= evidence.observed_at <= snap.as_of
                and evidence.observed_at >= snap.base_as_of
                and tid not in records
            )
        except (ValidationError, TypeError, ValueError):
            valid = False
        if valid:
            valid_not_started.add(tid)
        else:
            add("V10", "NOT_STARTED_EVIDENCE_INVALID", [tid])
    frozen = {
        t.id
        for t in inst.tasks
        if t.status in ("RUNNING", "DONE")
        or (
            base is not None
            and t.status in ("PENDING", "SCHEDULED")
            and t.id in old
            and old[t.id].start < inst.now
            and t.id not in valid_not_started
        )
    }
    return ValidationIndex(tasks, devices, persons, records, assigned, old, frozen)
