"""EDD rule-repair baseline, independently checked before return."""

from collections.abc import Sequence
import time

from scheduler_core.impact import EventType, analyze_impact, neighborhoods
from scheduler_core.models import Assignment, Instance, Plan, ReplanParams, UrgentInsert
from scheduler_core.replanning.events import prepare_post
from scheduler_core.replanning.params import validate_params
from scheduler_core.validate import validate
from scheduler_core.validation_context import ValidationContext


def b3(
    inst: Instance,
    base: Plan,
    events: Sequence[EventType],
    context: ValidationContext,
    params: ReplanParams | None = None,
) -> Plan | None:
    """Place impacted tasks by urgent priority and deadline; reject invalid repairs."""
    started = time.perf_counter()
    p = params or ReplanParams()
    validate_params(p)
    post = prepare_post(inst, base, events, context)
    impact = analyze_impact(post, base, events, p.window_slots, context=context)
    free = neighborhoods(post, base, impact, p.window_slots)[0]
    tasks = {t.id: t for t in post.tasks}
    urgent = {t.id for event in events if isinstance(event, UrgentInsert) for t in event.tasks}
    assigned = {
        tid: a.model_copy(deep=True)
        for tid, a in base.assignments.items()
        if tid not in free and tasks[tid].status in ("PENDING", "SCHEDULED", "RUNNING", "DONE")
    }
    remaining = {tid for tid in free if tasks[tid].status in ("PENDING", "SCHEDULED")}
    setups = {(s.device_id, s.task_type): s.slots for s in post.setups}
    devices = {d.id: d for d in post.devices}
    while remaining:
        ready = [
            tid
            for tid in remaining
            if not any(e.succ == tid and e.pred in remaining for e in post.precedences)
        ]
        if not ready:
            return None
        tid = min(
            ready,
            key=lambda x: (x not in urgent, tasks[x].deadline is None, tasks[x].deadline or 0, x),
        )
        task = tasks[tid]
        earliest = max(post.now, task.release)
        for edge in post.precedences:
            if edge.succ == tid and edge.pred in assigned:
                earliest = max(earliest, assigned[edge.pred].end + edge.lag_min)
        best: Assignment | None = None
        for did in sorted(set(task.compatible_devices)):
            device = devices.get(did)
            if device is None or task.demand > device.capacity:
                continue
            setup = setups.get((did, task.type), 0)
            candidates: list[str | None] = (
                [person.id for person in post.persons if task.required_skills <= person.skills]
                if task.needs_person
                else [None]
            )
            for pid in candidates:
                for start in range(
                    max(earliest, setup), post.axis.horizon_slots - task.duration + 1
                ):
                    if time.perf_counter() - started >= p.total_budget_s:
                        return None
                    end = start + task.duration
                    if any(
                        w.device_id == did and w.start < end and start - setup < w.end
                        for w in post.blocked
                    ):
                        continue
                    relevant = [(a, tasks[k]) for k, a in assigned.items() if a.device_id == did]
                    if any(
                        sum(
                            t.demand
                            for a, t in relevant
                            if a.start
                            - (
                                0
                                if t.status in ("RUNNING", "DONE")
                                else setups.get((did, t.type), 0)
                            )
                            <= slot
                            < a.end
                        )
                        + task.demand
                        > device.capacity
                        for slot in range(start - setup, end)
                    ):
                        continue
                    person = next((person for person in post.persons if person.id == pid), None)
                    if pid is not None and (
                        any(
                            a.person_id == pid and a.start < end and start < a.end
                            for a in assigned.values()
                        )
                        or person is None
                        or any(w.start < end and start < w.end for w in person.blocked)
                    ):
                        continue
                    choice = Assignment(
                        task_id=tid, device_id=did, person_id=pid, start=start, end=end
                    )
                    if best is None or (
                        choice.end,
                        choice.start,
                        choice.device_id,
                        choice.person_id or "",
                    ) < (best.end, best.start, best.device_id, best.person_id or ""):
                        best = choice
                    break
        if best is None:
            return None
        assigned[tid] = best
        remaining.remove(tid)
    candidate = Plan(id=f"{base.id}.b3", parent_id=base.id, assignments=assigned)
    return (
        candidate
        if validate(post, candidate, base=base, free=free, context=context).passed
        else None
    )
