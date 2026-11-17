"""Validate that a caller supplied a post-event instance without reapplying events."""

from collections.abc import Sequence

from scheduler_core.models import DeviceOutage, Instance, Plan, TaskOverrun, UrgentInsert
from scheduler_core.validation_context import ValidationContext

EventType = DeviceOutage | TaskOverrun | UrgentInsert


def prepare_post(
    inst: Instance, base: Plan, events: Sequence[EventType], context: ValidationContext
) -> Instance:
    """Copy and check post-event data; never transform or apply an event here."""
    snap = context.snapshot
    if snap is None or snap.plan_id != base.id or snap.as_of != inst.now:
        raise ValueError("matching execution snapshot required")
    tasks = {t.id: t for t in inst.tasks}
    for event in events:
        if isinstance(event, DeviceOutage):
            if not any(
                w.kind == "FAULT"
                and w.device_id == event.device_id
                and w.start == event.start
                and w.end == event.end
                for w in inst.blocked
            ):
                raise ValueError("outage is not applied")
        elif isinstance(event, UrgentInsert):
            if len({t.id for t in event.tasks}) != len(event.tasks):
                raise ValueError("duplicate urgent task")
            for task in event.tasks:
                actual = tasks.get(task.id)
                if actual is None or task.id in base.assignments:
                    raise ValueError("urgent insertion is not applied")
                expected = task.model_dump(exclude={"release", "status"})
                if actual.model_dump(
                    exclude={"release", "status"}
                ) != expected or not task.release <= actual.release <= max(task.release, inst.now):
                    raise ValueError("urgent task differs from event")
            if any(edge not in inst.precedences for edge in event.precedences):
                raise ValueError("urgent precedence is not applied")
        else:
            record = next((r for r in snap.records if r.task_id == event.task_id), None)
            assignment = base.assignments.get(event.task_id)
            if record is None or record.status != "RUNNING" or assignment is None:
                raise ValueError("overrun requires running evidence")
            if (
                record.remaining_estimate is None
                or max(assignment.end, inst.now + record.remaining_estimate) != event.new_end
            ):
                raise ValueError("overrun does not match evidence")
    return inst.model_copy(deep=True)


def prepare_raw(
    inst: Instance, base: Plan, events: Sequence[EventType], context: ValidationContext
) -> tuple[Instance, ValidationContext]:
    """Apply raw events once, reconstructing interruption from matching snapshot facts."""
    from scheduler_core.models import BlockedWindow

    snap = context.snapshot
    if snap is None or snap.plan_id != base.id or snap.as_of != inst.now:
        raise ValueError("matching execution snapshot required")
    result = inst.model_copy(deep=True)
    evidence = context.model_copy(deep=True)
    assert evidence.snapshot is not None
    for event in events:
        if isinstance(event, DeviceOutage):
            if any(
                w.kind == "FAULT"
                and w.device_id == event.device_id
                and w.start == event.start
                and w.end == event.end
                for w in result.blocked
            ):
                raise ValueError("outage already applied")
            if event.device_id not in {d.id for d in result.devices}:
                raise ValueError("unknown device")
            interrupted = [
                r
                for r in evidence.snapshot.records
                if r.status == "RUNNING"
                and r.device_id == event.device_id
                and event.start <= inst.now
                and r.start < event.end
                and r.remaining_estimate is not None
                and max(r.planned_end or 0, inst.now + r.remaining_estimate) > event.start
            ]
            if interrupted and event.start != inst.now:
                raise ValueError("past interruption requires execution history")
            for record in interrupted:
                old = base.assignments.get(record.task_id)
                if (
                    old is None
                    or record.device_id != old.device_id
                    or record.person_id != old.person_id
                    or record.planned_end != old.end
                ):
                    raise ValueError("inconsistent interruption assignment evidence")
                result = _interrupt(result, base, record.task_id, record.start, event.start)
                evidence.snapshot.records = [
                    r for r in evidence.snapshot.records if r.task_id != record.task_id
                ]
            result.blocked.append(
                BlockedWindow(
                    device_id=event.device_id, start=event.start, end=event.end, kind="FAULT"
                )
            )
        elif isinstance(event, UrgentInsert):
            if {t.id for t in result.tasks} & {t.id for t in event.tasks}:
                raise ValueError("urgent task already exists")
            result.tasks.extend(
                t.model_copy(deep=True, update={"release": max(inst.now, t.release)})
                for t in event.tasks
            )
            result.precedences.extend(e.model_copy(deep=True) for e in event.precedences)
        else:
            overrun_record = next((r for r in snap.records if r.task_id == event.task_id), None)
            if overrun_record is None or overrun_record.status != "RUNNING":
                raise ValueError("overrun requires running evidence")
    result = Instance.model_validate(result.model_dump())
    return prepare_post(result, base, events, evidence), evidence


def _interrupt(inst: Instance, base: Plan, tid: str, start: int, at: int) -> Instance:
    from scheduler_core.models import Precedence

    task = next((t for t in inst.tasks if t.id == tid), None)
    old = base.assignments.get(tid)
    if task is None or task.status != "RUNNING" or old is None or old.start != start or at < start:
        raise ValueError("inconsistent interruption evidence")
    parts = tid.rsplit("~r", 1)
    root = parts[0] if len(parts) == 2 and parts[1].isdigit() else tid
    ids = {t.id for t in inst.tasks}
    index = 1
    while f"{root}~r{index}" in ids:
        index += 1
    restart_id = f"{root}~r{index}"
    duration = max(1, task.duration - (at - start)) if task.preemptible else task.duration
    restart = task.model_copy(
        deep=True,
        update={"id": restart_id, "status": "PENDING", "release": at, "duration": duration},
    )
    updated = [
        t.model_copy(deep=True, update={"status": "INTERRUPTED"})
        if t.id == tid
        else t.model_copy(deep=True)
        for t in inst.tasks
    ]
    edges = [edge.model_copy(deep=True) for edge in inst.precedences]
    edges.extend(
        Precedence(
            pred=restart_id if e.pred == tid else e.pred,
            succ=restart_id if e.succ == tid else e.succ,
            lag_min=e.lag_min,
            lag_max=e.lag_max,
        )
        for e in inst.precedences
        if e.pred == tid or e.succ == tid
    )
    data = inst.model_dump()
    data.update(tasks=[*updated, restart], precedences=edges)
    return Instance.model_validate(data)
