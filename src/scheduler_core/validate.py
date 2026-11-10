"""Independent semantic checks for schedules, with half-open interval scans."""

from bisect import bisect_right
from collections import Counter, defaultdict, deque
from heapq import heappop, heappush
from typing import AbstractSet, Literal, cast

from .models import Instance, Plan, ValidationReport, Violation
from .validation_context import (
    DeadlineAuthorization,
    FrozenEndChange,
    RunningBlockBinding,
    ValidationContext,
)


def validate(
    inst: Instance,
    plan: Plan,
    *,
    base: Plan | None = None,
    free: AbstractSet[str] | None = None,
    context: ValidationContext | None = None,
) -> ValidationReport:
    """Check a plan against an instance and optional prior-plan evidence.

    ``inst`` provides the constraints and integer-slot axis; ``plan`` provides
    assignments. Resource intervals are half-open. ``base`` is the optional
    parent plan; ``free=None`` disables neighborhood checks, while an empty set
    allows no non-frozen changes. ``context`` carries optional execution and
    authorization evidence, whose authenticity is the caller's responsibility.

    Inputs are not mutated. Return a report sorted by code, task IDs, device ID
    and detail; ``passed`` is true exactly when there are no violations.
    Semantic failures are reported as violations; incorrect top-level argument
    types raise TypeError.
    """
    if not isinstance(inst, Instance) or not isinstance(plan, Plan):
        raise TypeError("inst and plan must be Instance and Plan")
    if base is not None and not isinstance(base, Plan):
        raise TypeError("base must be a Plan or None")
    if context is not None and not isinstance(context, ValidationContext):
        raise TypeError("context must be a ValidationContext or None")
    if free is not None and not isinstance(free, AbstractSet):
        raise TypeError("free must be a set or None")
    ctx = context if context is not None else ValidationContext()
    out: list[Violation] = []

    def add(
        code: str,
        reason: str,
        ids: list[str] | None = None,
        device: str | None = None,
        **values: object,
    ) -> None:
        detail = f"reason={reason};" + "".join(f" {k}={values[k]};" for k in sorted(values))
        out.append(
            Violation(
                code=cast(
                    Literal["V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9", "V10", "V11"],
                    code,
                ),
                task_ids=sorted(ids or []),
                device_id=device,
                detail=detail,
            )
        )

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
    setup_values: dict[tuple[str, str], set[int]] = defaultdict(set)
    for rule in inst.setups:
        setup_values[(rule.device_id, rule.task_type)].add(rule.slots)
    setups: dict[tuple[str, str], int] = {}
    for (device_id, task_type), values in sorted(setup_values.items()):
        if device_id not in devices:
            add("V1", "UNKNOWN_DEVICE_REF", device=device_id)
        if len(values) > 1:
            add("V2", "SETUP_RULE_CONFLICT", device=device_id, task_type=task_type)
        setups[(device_id, task_type)] = max(values)
    for tid in sorted(tasks):
        t = tasks[tid]
        if not t.compatible_devices:
            add("V1", "EMPTY_COMPATIBLE_LIST", [tid])
        for did in sorted(set(t.compatible_devices) - devices.keys()):
            add("V1", "UNKNOWN_DEVICE_REF", [tid], did)
        if t.status in ("PENDING", "SCHEDULED", "RUNNING", "DONE") and tid not in assigned:
            add("V1", "MISSING_ASSIGNMENT", [tid])
        if tid in frozen and tid not in assigned:
            add("V8", "FROZEN_MISSING", [tid])
    for tid in sorted(assigned.keys() - tasks.keys()):
        add("V1", "UNKNOWN_TASK", [tid])

    # Store only valid known assignments for subsequent resource scans.
    device_intervals: dict[str, list[tuple[int, int, str, int]]] = defaultdict(list)
    person_intervals: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
    occupancy: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
    person_windows: dict[str, tuple[list[tuple[int, int]], list[int]]] = {}
    for person_item in persons.values():
        merged_person: list[tuple[int, int]] = []
        for ws, we in sorted((w.start, w.end) for w in person_item.blocked):
            if merged_person and ws <= merged_person[-1][1]:
                merged_person[-1] = (merged_person[-1][0], max(we, merged_person[-1][1]))
            else:
                merged_person.append((ws, we))
        person_windows[person_item.id] = (merged_person, [we for _, we in merged_person])
    for tid, a in sorted(assigned.items()):
        t = tasks.get(tid)
        if t is None:
            continue
        if t.status in ("FAILED", "CANCELLED", "INTERRUPTED"):
            add("V1", "TASK_NOT_SCHEDULABLE", [tid])
        d = devices.get(a.device_id)
        if d is None:
            add("V1", "UNKNOWN_DEVICE", [tid], a.device_id)
        elif a.device_id not in t.compatible_devices:
            add("V1", "DEVICE_NOT_COMPATIBLE", [tid], a.device_id)
        setup = 0 if t.status in ("RUNNING", "DONE") else setups.get((a.device_id, t.type), 0)
        start = a.start - setup
        if start < 0 and tid not in frozen:
            add("V6", "SETUP_BEFORE_ORIGIN", [tid], a.device_id)
        if a.end > inst.axis.horizon_slots:
            add("V6", "HORIZON_EXCEEDED", [tid], a.device_id)
        if a.start < t.release:
            add("V4", "RELEASE_VIOLATED", [tid])
        if tid not in frozen and a.start < inst.now:
            add("V4", "START_BEFORE_NOW", [tid])
        if t.status in ("PENDING", "SCHEDULED") and a.end - a.start != t.duration:
            add("V10", "DURATION_MISMATCH", [tid])
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
        if d:
            occupancy[d.id].append((start, a.end, tid))
            if t.demand > d.capacity:
                add("V9", "DEMAND_EXCEEDS_CAPACITY", [tid], d.id)
            else:
                device_intervals[d.id].append((start, a.end, tid, t.demand))
        if t.needs_person and a.person_id is None:
            add("V7", "MISSING_PERSON", [tid])
        if a.person_id is not None:
            person = persons.get(a.person_id)
            if person is None:
                add("V7", "UNKNOWN_PERSON", [tid])
            else:
                if not t.required_skills <= person.skills:
                    add("V7", "SKILL_MISSING", [tid])
                person_intervals[person.id].append((a.start, a.end, tid))
                windows, ends = person_windows[person.id]
                index = bisect_right(ends, a.start)
                if index < len(windows) and windows[index][0] < a.end:
                    add("V7", "PERSON_UNAVAILABLE", [tid])

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

    auths: dict[str, list[DeadlineAuthorization]] = defaultdict(list)
    for auth in ctx.deadline_authorizations:
        auths[auth.task_id].append(auth)
    for tid, group in sorted(auths.items()):
        t = tasks.get(tid)
        if len(group) > 1:
            add("V5", "AUTH_DUPLICATE", [tid])
        for auth in group:
            if not t or t.deadline_level != "NEGOTIABLE" or t.deadline is None:
                add("V5", "AUTH_NOT_APPLICABLE", [tid])
            elif auth.plan_id != plan.id or auth.original_deadline != t.deadline:
                add("V5", "AUTH_OUT_OF_SCOPE", [tid])
            if auth.acted_at > inst.now:
                add("V5", "AUTH_FUTURE", [tid])
            if auth.valid_until is not None and auth.valid_until < inst.now:
                add("V5", "AUTH_EXPIRED", [tid])
    for tid, a in sorted(assigned.items()):
        t = tasks.get(tid)
        if not t or t.deadline is None:
            continue
        deadline = t.deadline
        group = auths.get(tid, [])
        if len(group) == 1:
            auth = group[0]
            if (
                t.deadline_level == "NEGOTIABLE"
                and auth.plan_id == plan.id
                and auth.original_deadline == deadline
                and auth.acted_at <= inst.now
                and (auth.valid_until is None or auth.valid_until >= inst.now)
            ):
                deadline = auth.relaxed_deadline
        if a.end > deadline:
            add("V5", "DEADLINE_EXCEEDED", [tid])

    indegree = {tid: 0 for tid in tasks}
    edges: dict[str, list[str]] = defaultdict(list)
    for p in inst.precedences:
        if p.pred not in tasks or p.succ not in tasks:
            add("V3", "PRECEDENCE_UNKNOWN_TASK", [p.pred, p.succ])
            continue
        indegree[p.succ] += 1
        edges[p.pred].append(p.succ)
        if p.pred in assigned and p.succ in assigned:
            lag = assigned[p.succ].start - assigned[p.pred].end
            if lag < p.lag_min:
                add("V3", "PRECEDENCE_MIN_LAG", [p.pred, p.succ])
            if p.lag_max is not None and lag > p.lag_max:
                add("V3", "PRECEDENCE_MAX_LAG", [p.pred, p.succ])
    queue = deque(sorted(k for k, v in indegree.items() if v == 0))
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for nxt in edges[node]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    if visited < len(tasks):
        add("V3", "PRECEDENCE_CYCLE", sorted(k for k, v in indegree.items() if v))

    def overlap_scan(
        intervals: list[tuple[int, int, str]], code: str, reason: str, device: str | None = None
    ) -> None:
        max_end: int | None = None
        owner = ""
        for start, end, tid in sorted(intervals):
            if max_end is not None and start < max_end:
                add(code, reason, [owner, tid], device)
            if max_end is None or end > max_end:
                max_end, owner = end, tid

    for did, intervals in sorted(device_intervals.items()):
        cap = devices[did].capacity
        if cap == 1:
            overlap_scan([(s, e, t) for s, e, t, _ in intervals], "V2", "DEVICE_OVERLAP", did)
        else:
            events: dict[int, list[tuple[bool, str, int]]] = defaultdict(list)
            for s, e, tid, demand in intervals:
                events[s].append((True, tid, demand))
                events[e].append((False, tid, demand))
            active: set[str] = set()
            load = 0
            begin: int | None = None
            involved: set[str] = set()
            for point in sorted(events):
                entering_ids: set[str] = set()
                for entering, tid, demand in sorted(events[point]):
                    if entering:
                        entering_ids.add(tid)
                        active.add(tid)
                        load += demand
                    else:
                        active.discard(tid)
                        load -= demand
                if load > cap:
                    if begin is None:
                        begin = point
                        involved.update(active)
                    else:
                        involved.update(entering_ids)
                elif begin is not None:
                    add("V9", "CAPACITY_EXCEEDED", sorted(involved), did, start=begin, end=point)
                    begin, involved = None, set()
    for pid, person_spans in sorted(person_intervals.items()):
        overlap_scan(person_spans, "V7", "PERSON_OVERLAP")

    # Merge calendar windows and locate the first candidate via binary search.
    calendars: dict[str, list[tuple[int, int]]] = defaultdict(list)
    running = set()
    for window in inst.blocked:
        if window.device_id not in devices:
            add("V1", "UNKNOWN_DEVICE_REF", device=window.device_id)
        if window.kind == "RUNNING":
            running.add((window.device_id, window.start, window.end))
        else:
            calendars[window.device_id].append((window.start, window.end))
    for did, windows in calendars.items():
        merged: list[tuple[int, int]] = []
        for s, e in sorted(windows):
            if merged and s <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(e, merged[-1][1]))
            else:
                merged.append((s, e))
        ends = [e for _, e in merged]
        for s, e, tid in occupancy.get(did, []):
            pos = bisect_right(ends, s)
            while pos < len(merged) and merged[pos][0] < e:
                add("V6", "CALENDAR_BLOCKED", [tid], did, start=merged[pos][0], end=merged[pos][1])
                pos += 1
    bindings: dict[tuple[str, int, int], list[RunningBlockBinding]] = defaultdict(list)
    for binding in ctx.running_block_bindings:
        bindings[(binding.device_id, binding.start, binding.end)].append(binding)
    valid: set[tuple[str, int, int]] = set()
    for block_key, binding_group in sorted(bindings.items()):
        b = binding_group[0]
        rec = records.get(b.task_id)
        binding_assignment = assigned.get(b.task_id)
        binding_task = tasks.get(b.task_id)
        if (
            len(binding_group) == 1
            and block_key in running
            and snap
            and rec
            and rec.status == "RUNNING"
            and binding_task
            and binding_task.status == "RUNNING"
            and binding_assignment
            and binding_assignment.device_id == b.device_id
            and rec.device_id == b.device_id
            and b.end == binding_assignment.end
            and rec.start <= b.start <= snap.as_of
        ):
            valid.add(block_key)
        else:
            add(
                "V2",
                "RUNNING_BLOCK_BINDING_INVALID",
                sorted({b.task_id for b in binding_group}),
                block_key[0],
            )
    unbound: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for did, s, e in sorted(running - valid):
        if (did, s, e) not in bindings:
            unbound[did].append((s, e))
    # Sweep starts; each emitted pair is one reported overlap.
    for did, windows in unbound.items():
        scan_events: list[tuple[int, int, int, str]] = []
        for index, (start, end) in enumerate(windows):
            scan_events.append((start, 1, end, str(index)))
        for start, end, tid in occupancy.get(did, []):
            scan_events.append((start, 0, end, tid))
        active_tasks: dict[str, int] = {}
        active_windows: dict[str, int] = {}
        task_heap: list[tuple[int, str]] = []
        window_heap: list[tuple[int, str]] = []
        for start, kind, end, ident in sorted(scan_events):
            while task_heap and task_heap[0][0] <= start:
                _, expired = heappop(task_heap)
                active_tasks.pop(expired, None)
            while window_heap and window_heap[0][0] <= start:
                _, expired = heappop(window_heap)
                active_windows.pop(expired, None)
            if kind == 0:
                for _ in active_windows:
                    add("V2", "RUNNING_BLOCK_UNBOUND", [ident], did)
                active_tasks[ident] = end
                heappush(task_heap, (end, ident))
            else:
                for tid in active_tasks:
                    add("V2", "RUNNING_BLOCK_UNBOUND", [tid], did)
                active_windows[ident] = end
                heappush(window_heap, (end, ident))
    out.sort(
        key=lambda v: (
            int(v.code[1:]),
            v.task_ids,
            (v.device_id is not None, v.device_id or ""),
            v.detail,
        )
    )
    return ValidationReport(passed=not out, violations=out)
