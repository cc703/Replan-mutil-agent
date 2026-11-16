"""Deterministic callback fixtures for scripted simulator tests."""

from collections import deque
from scheduler_core.models import Instance, Plan
from simulator.events import SimEvent


class ScriptedScheduler:
    """Return independent copies of queued plans in callback order."""

    def __init__(self, plans: list[Plan | None]) -> None:
        self.plans = deque(plans)
        self.calls: list[tuple[Instance, Plan, list[SimEvent]]] = []

    def __call__(self, instance: Instance, base: Plan, events: list[SimEvent]) -> Plan | None:
        self.calls.append(
            (
                instance.model_copy(deep=True),
                base.model_copy(deep=True),
                [event.model_copy(deep=True) for event in events],
            )
        )
        if not self.plans:
            return None
        result = self.plans.popleft()
        return result.model_copy(deep=True) if result is not None else None


def greedy_schedule(instance: Instance, base: Plan, _events: list[SimEvent]) -> Plan | None:
    """Test-only greedy scheduler; return None when its deterministic search cannot find a plan."""
    from scheduler_core.models import Assignment, TaskOverrun
    from scheduler_core.validate import validate
    from scheduler_core.validation_context import (
        ExecutionRecord,
        ExecutionSnapshot,
        FrozenEndChange,
        ValidationContext,
    )

    tasks = {task.id: task for task in instance.tasks}
    devices = {device.id: device for device in instance.devices}
    assignments: dict[str, Assignment] = {}
    records: list[ExecutionRecord] = []
    changes: list[FrozenEndChange] = []
    overruns = {event.task_id: event for event in _events if isinstance(event.payload, TaskOverrun)}
    for task in instance.tasks:
        if task.status not in ("RUNNING", "DONE"):
            continue
        old = base.assignments.get(task.id)
        if old is None:
            return None
        assignments[task.id] = old.model_copy(deep=True)
        if task.status == "RUNNING":
            overrun = overruns.get(task.id)
            known_end = old.end
            if overrun is not None:
                assert isinstance(overrun.payload, TaskOverrun)
                known_end = max(old.end, overrun.payload.new_end)
                if known_end > old.end:
                    assignments[task.id] = old.model_copy(update={"end": known_end})
                    changes.append(
                        FrozenEndChange(
                            task_id=task.id,
                            plan_id=base.id + ".greedy",
                            base_plan_id=base.id,
                            old_end=old.end,
                            new_end=known_end,
                            event_id=f"overrun:{overrun.seq}",
                            acted_at=overrun.time,
                        )
                    )
            records.append(
                ExecutionRecord(
                    task_id=task.id,
                    status="RUNNING",
                    device_id=old.device_id,
                    person_id=old.person_id,
                    start=old.start,
                    planned_end=old.end,
                    remaining_estimate=max(0, known_end - instance.now),
                    event_id=f"stub-start:{task.id}",
                )
            )
        else:
            records.append(
                ExecutionRecord(
                    task_id=task.id,
                    status="DONE",
                    device_id=old.device_id,
                    person_id=old.person_id,
                    start=old.start,
                    actual_end=old.end,
                    event_id=f"stub-end:{task.id}",
                )
            )
    context = ValidationContext(
        snapshot=ExecutionSnapshot(
            plan_id=base.id, as_of=instance.now, base_as_of=0, records=records
        ),
        end_changes=changes,
    )
    pending = {t.id for t in instance.tasks if t.status in ("PENDING", "SCHEDULED")}
    setups: dict[tuple[str, str], int] = {}
    for rule in instance.setups:
        key = (rule.device_id, rule.task_type)
        setups[key] = max(setups.get(key, 0), rule.slots)
    while pending:
        ready = sorted(
            tid
            for tid in pending
            if all(
                edge.pred in assignments
                or tasks[edge.pred].status in ("INTERRUPTED", "CANCELLED", "FAILED")
                for edge in instance.precedences
                if edge.succ == tid
            )
        )
        if not ready:
            return None
        tid = ready[0]
        task = tasks[tid]
        options: list[Assignment] = []
        for device_id in sorted(task.compatible_devices):
            device = devices[device_id]
            setup = setups.get((device_id, task.type), 0)
            if task.demand > device.capacity:
                continue
            people: list[str | None] = (
                [p.id for p in instance.persons if task.required_skills <= p.skills]
                if task.needs_person
                else [None]
            )
            for person_id in people:
                for start in range(
                    max(instance.now + setup, task.release),
                    instance.axis.horizon_slots - task.duration + 1,
                ):
                    end = start + task.duration
                    if task.deadline is not None and end > task.deadline:
                        break
                    if any(
                        edge.pred in assignments
                        and (
                            start - assignments[edge.pred].end < edge.lag_min
                            or (
                                edge.lag_max is not None
                                and start - assignments[edge.pred].end > edge.lag_max
                            )
                        )
                        for edge in instance.precedences
                        if edge.succ == tid
                    ):
                        continue
                    if any(
                        w.device_id == device_id and w.start < end and start - setup < w.end
                        for w in instance.blocked
                    ):
                        continue
                    if person_id is not None:
                        person = next(p for p in instance.persons if p.id == person_id)
                        if any(w.start < end and start < w.end for w in person.blocked):
                            continue
                    feasible = True
                    for slot in range(start - setup, end):
                        used = sum(
                            tasks[other].demand
                            for other, old in assignments.items()
                            if old.device_id == device_id
                            and old.start
                            - (
                                0
                                if tasks[other].status in ("RUNNING", "DONE")
                                else setups.get((device_id, tasks[other].type), 0)
                            )
                            <= slot
                            < old.end
                        )
                        if used + task.demand > device.capacity:
                            feasible = False
                            break
                    if not feasible or any(
                        person_id is not None
                        and old.person_id == person_id
                        and old.start < end
                        and start < old.end
                        for old in assignments.values()
                    ):
                        continue
                    options.append(
                        Assignment(
                            task_id=tid,
                            device_id=device_id,
                            person_id=person_id,
                            start=start,
                            end=end,
                        )
                    )
                    break
        if not options:
            return None
        assignments[tid] = min(options, key=lambda a: (a.start, a.device_id, a.person_id or ""))
        pending.remove(tid)
    result = Plan(id=base.id + ".greedy", parent_id=base.id, assignments=assignments)
    return result if validate(instance, result, base=base, context=context).passed else None
