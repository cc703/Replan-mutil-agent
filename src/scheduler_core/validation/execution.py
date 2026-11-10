"""Baseline, snapshot and execution-evidence rules."""

from collections import Counter, defaultdict
from typing import AbstractSet
from ..validation_context import FrozenEndChange
from ..models import Assignment, Instance, Plan, Task
from ..validation_context import ValidationContext
from .index import ValidationIndex
from .report import ViolationCollector


def check_neighborhood(
    plan: Plan,
    base: Plan | None,
    free: AbstractSet[str] | None,
    index: ValidationIndex,
    collector: ViolationCollector,
) -> None:
    add = collector.add
    tasks, frozen, old, assigned = index.tasks, index.frozen, index.old, index.assigned
    if base and plan.parent_id != base.id:
        add("V11", "PARENT_MISMATCH")
    if free is not None and base is None:
        add("V11", "BASE_REQUIRED")
    if free is not None:
        for tid in sorted(free - tasks.keys()):
            add("V11", "FREE_UNKNOWN_TASK", [tid])
        for tid in sorted(free & frozen):
            add("V11", "FREE_CONTAINS_FROZEN", [tid])
    if base:
        for tid in sorted(old.keys() - tasks.keys()):
            add("V11", "BASE_TASK_UNKNOWN", [tid])
        if free is not None:
            for tid in sorted((old.keys() | assigned.keys()) - free - frozen):
                if tid not in old:
                    add("V11", "ADDED_NOT_FREE", [tid])
                elif tid not in assigned:
                    add("V11", "REMOVED_NOT_FREE", [tid])
                elif old[tid] != assigned[tid]:
                    add("V11", "NONFREE_CHANGED", [tid])


def check_snapshot(
    inst: Instance,
    plan: Plan,
    base: Plan | None,
    ctx: ValidationContext,
    index: ValidationIndex,
    collector: ViolationCollector,
) -> None:
    add = collector.add
    tasks, old = index.tasks, index.old
    snap = ctx.snapshot
    if snap:
        if snap.as_of != inst.now:
            add("V10", "SNAPSHOT_STALE")
        if snap.plan_id != (base.id if base else plan.id):
            add("V10", "SNAPSHOT_PLAN_MISMATCH")
        counts = Counter(r.task_id for r in snap.records)
        for r in snap.records:
            t = tasks.get(r.task_id)
            if (
                not t
                or t.status != r.status
                or counts[r.task_id] > 1
                or (snap.base_as_of is not None and snap.base_as_of > snap.as_of)
                or (r.status == "RUNNING" and r.start > snap.as_of)
                or (r.status == "DONE" and r.actual_end is not None and r.actual_end > snap.as_of)
                or (base is not None and r.status == "DONE" and snap.base_as_of is None)
                or (
                    base is not None
                    and r.status == "RUNNING"
                    and (r.task_id not in old or r.planned_end != old[r.task_id].end)
                )
            ):
                add("V10", "SNAPSHOT_RECORD_INVALID", [r.task_id])


def check_end_changes(
    inst: Instance,
    plan: Plan,
    base: Plan | None,
    ctx: ValidationContext,
    index: ValidationIndex,
    collector: ViolationCollector,
) -> None:
    add = collector.add
    frozen, tasks, assigned, old, records = (
        index.frozen,
        index.tasks,
        index.assigned,
        index.old,
        index.records,
    )
    snap = ctx.snapshot
    changes_by_task: dict[str, list[FrozenEndChange]] = defaultdict(list)
    for change in ctx.end_changes:
        changes_by_task[change.task_id].append(change)
    for tid in sorted(frozen):
        t = tasks.get(tid)
        current = assigned.get(tid)
        changes = changes_by_task.get(tid, [])
        if not t or not current:
            if changes:
                add("V11", "FROZEN_END_EVIDENCE_INVALID", [tid])
            continue
        a = current
        if t.status == "RUNNING" and base and tid in old:
            if a.end != old[tid].end and not changes:
                add("V11", "FROZEN_END_NO_EVIDENCE", [tid])
            if changes:
                rec = records.get(tid)
                expected = (
                    max(rec.planned_end, snap.as_of + rec.remaining_estimate)
                    if (
                        rec
                        and snap
                        and rec.planned_end is not None
                        and rec.remaining_estimate is not None
                    )
                    else None
                )
                if len(changes) != 1 or any(
                    c.plan_id != plan.id
                    or c.base_plan_id != base.id
                    or c.old_end != old[tid].end
                    or c.new_end != a.end
                    or c.new_end != expected
                    or c.acted_at > inst.now
                    or a.end == old[tid].end
                    for c in changes
                ):
                    add("V11", "FROZEN_END_EVIDENCE_INVALID", [tid])
        elif changes:
            add("V11", "FROZEN_END_EVIDENCE_INVALID", [tid])
        elif t.status not in ("RUNNING", "DONE") and base and tid in old and a.end != old[tid].end:
            add("V11", "FROZEN_END_NO_EVIDENCE", [tid])
    for c in ctx.end_changes:
        if c.task_id not in frozen:
            add("V11", "FROZEN_END_EVIDENCE_INVALID", [c.task_id])


def check_assignment_execution(
    inst: Instance,
    base: Plan | None,
    ctx: ValidationContext,
    index: ValidationIndex,
    tid: str,
    t: Task,
    a: Assignment,
    collector: ViolationCollector,
) -> None:
    add = collector.add
    records, old, frozen, snap = index.records, index.old, index.frozen, ctx.snapshot
    rec = records.get(tid)
    if t.status == "RUNNING":
        if rec is None or rec.status != "RUNNING":
            add("V10", "RUNNING_NO_SNAPSHOT", [tid])
        elif snap and rec.planned_end is not None and rec.remaining_estimate is not None:
            if a.end != max(rec.planned_end, snap.as_of + rec.remaining_estimate):
                add("V10", "END_MISMATCH", [tid])
    if t.status == "DONE":
        if a.end > inst.now:
            add("V10", "DONE_END_AFTER_NOW", [tid])
        if rec and rec.status == "DONE":
            if a.end != rec.actual_end:
                add("V10", "END_MISMATCH", [tid])
            if (
                base
                and tid in old
                and snap
                and snap.base_as_of is not None
                and rec.actual_end is not None
                and rec.actual_end <= snap.base_as_of
                and a != old[tid]
            ):
                add("V10", "DONE_HISTORY_REWRITTEN", [tid])
        elif tid not in old or a != old[tid]:
            add("V10", "DONE_NO_EVIDENCE", [tid])
    if tid in frozen:
        ref = old.get(tid) if base else rec
        if ref is None:
            add("V8", "NO_FROZEN_REFERENCE", [tid])
        else:
            if a.device_id != ref.device_id or (rec and a.device_id != rec.device_id):
                add("V8", "FROZEN_DEVICE_CHANGED", [tid])
            if a.start != ref.start or (rec and a.start != rec.start):
                add("V8", "FROZEN_START_CHANGED", [tid])
            if a.person_id != ref.person_id or (rec and a.person_id != rec.person_id):
                add("V11", "FROZEN_PERSON_CHANGED", [tid])
