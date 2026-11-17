"""Impact analysis and deterministic expanding neighborhoods."""

from collections import deque
from collections.abc import Sequence

from .models import DeviceOutage, ImpactReport, Instance, Plan, TaskOverrun, UrgentInsert
from .validation.index import build_index
from .validation.execution import check_snapshot
from .validation.report import ViolationCollector
from .validation_context import ValidationContext

EventType = DeviceOutage | TaskOverrun | UrgentInsert


def analyze_impact(
    inst: Instance,
    base: Plan,
    events: Sequence[EventType],
    window_slots: int = 48,
    *,
    context: ValidationContext | None = None,
) -> ImpactReport:
    """Find directly and transitively impacted movable tasks on a post-event instance."""
    if window_slots < 0:
        raise ValueError("window must be nonnegative")
    collector = ViolationCollector()
    ctx = context or ValidationContext()
    idx = build_index(inst, base, base, ctx, collector)
    check_snapshot(inst, base, base, ctx, idx, collector)
    if collector.report().violations:
        raise ValueError("invalid execution evidence")
    movable = {t.id for t in inst.tasks if t.status in ("PENDING", "SCHEDULED")} - idx.frozen
    added = movable - base.assignments.keys()
    reasons = {tid: "new task" for tid in sorted(added)}
    for event in events:
        if isinstance(event, DeviceOutage):
            for tid, a in sorted(base.assignments.items()):
                if (
                    tid in movable
                    and a.device_id == event.device_id
                    and a.start < event.end
                    and event.start < a.end
                ):
                    reasons.setdefault(tid, f"outage:{event.device_id}")
        elif isinstance(event, TaskOverrun):
            old = base.assignments.get(event.task_id)
            if old is None:
                raise ValueError("overrun task absent from base")
            for tid, a in sorted(base.assignments.items()):
                if tid in movable and a.device_id == old.device_id and a.start >= old.end:
                    reasons.setdefault(tid, f"overrun:{event.task_id}")
        else:
            for task in event.tasks:
                for tid, a in sorted(base.assignments.items()):
                    end = task.deadline if task.deadline is not None else inst.axis.horizon_slots
                    if (
                        tid in movable
                        and a.device_id in task.compatible_devices
                        and a.start < end
                        and task.release < a.end
                    ):
                        reasons.setdefault(tid, f"urgent:{task.id}")
    successors: dict[str, list[str]] = {}
    for edge in inst.precedences:
        successors.setdefault(edge.pred, []).append(edge.succ)
    for event in events:
        if isinstance(event, TaskOverrun):
            pending = deque([event.task_id])
            visited = {event.task_id}
            while pending:
                source = pending.popleft()
                for successor in sorted(successors.get(source, [])):
                    if successor not in visited:
                        visited.add(successor)
                        pending.append(successor)
                        if successor in movable:
                            reasons.setdefault(successor, f"successor:{source}")
    # Sorted interval components form the transitive closure of device neighbors.
    # Keep an explicit witness edge for each member and traverse each edge once.
    by_device: dict[str, list[tuple[int, int, str]]] = {}
    for tid, assignment in base.assignments.items():
        if tid in movable:
            by_device.setdefault(assignment.device_id, []).append(
                (assignment.start, assignment.end, tid)
            )
    adjacency: dict[str, list[str]] = {}
    for spans in by_device.values():
        maximum_end = -1
        owner = ""
        for start, end, tid in sorted(spans):
            if owner and start < maximum_end + window_slots:
                adjacency.setdefault(owner, []).append(tid)
                adjacency.setdefault(tid, []).append(owner)
            if not owner or start >= maximum_end + window_slots or end > maximum_end:
                maximum_end, owner = end, tid
    queue = deque(sorted(reasons))
    while queue:
        tid = queue.popleft()
        neighbors = [(s, f"successor:{tid}") for s in sorted(successors.get(tid, []))]
        neighbors.extend((s, f"device-neighbor:{tid}") for s in sorted(adjacency.get(tid, [])))
        for other, reason in neighbors:
            if other in movable and other not in reasons:
                reasons[other] = reason
                queue.append(other)
    affected = set(reasons)
    return ImpactReport(
        frozen=idx.frozen, affected=affected, unaffected=movable - affected, reasons=reasons
    )


def neighborhoods(
    inst: Instance, base: Plan, impact: ImpactReport, window_slots: int
) -> tuple[set[str], ...]:
    """Return monotone free sets, never releasing frozen tasks."""
    if window_slots < 0:
        raise ValueError("window must be nonnegative")
    movable = {t.id for t in inst.tasks if t.status in ("PENDING", "SCHEDULED")} - impact.frozen
    removed = {
        t.id
        for t in inst.tasks
        if t.id in base.assignments and t.status in ("INTERRUPTED", "FAILED", "CANCELLED")
    }
    first = (impact.affected & movable) | removed
    devices = {base.assignments[t].device_id for t in first if t in base.assignments}
    second = first | {
        tid
        for tid, a in base.assignments.items()
        if tid in movable
        and a.device_id in devices
        and a.start < inst.now + window_slots
        and inst.now < a.end
    }
    experiments = {t.experiment_id for t in inst.tasks if t.id in second}
    third = second | {
        t.id for t in inst.tasks if t.id in movable and t.experiment_id in experiments
    }
    return first, second, third, movable | removed
