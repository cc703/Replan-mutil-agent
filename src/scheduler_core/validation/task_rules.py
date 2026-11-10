"""Deadline and precedence rules."""

from collections import defaultdict, deque
from ..validation_context import DeadlineAuthorization
from ..models import Assignment, Device, Instance, Plan, Task
from ..validation_context import ValidationContext
from .index import ValidationIndex
from .report import ViolationCollector


def check_deadlines(
    inst: Instance,
    plan: Plan,
    ctx: ValidationContext,
    index: ValidationIndex,
    collector: ViolationCollector,
) -> None:
    add = collector.add
    tasks, assigned = index.tasks, index.assigned
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


def check_precedences(
    inst: Instance, index: ValidationIndex, collector: ViolationCollector
) -> None:
    add = collector.add
    tasks, assigned = index.tasks, index.assigned
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


def check_task_references(index: ValidationIndex, collector: ViolationCollector) -> None:
    add = collector.add
    tasks, devices, assigned, frozen = index.tasks, index.devices, index.assigned, index.frozen
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


def check_assignment(
    inst: Instance,
    tid: str,
    t: Task,
    a: Assignment,
    index: ValidationIndex,
    setups: dict[tuple[str, str], int],
    collector: ViolationCollector,
) -> tuple[Device | None, int]:
    add = collector.add
    devices, frozen = index.devices, index.frozen
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
    return d, start
