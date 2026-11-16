"""Metrics from immutable simulation history and resource windows."""

from typing import Any
from scheduler_core.models import Instance, Plan
from .log import ReplanCalled, ReplanResultRecord, ReplanTriggered, SimEventRecord, TaskStateRecord


def _union_length(intervals: list[tuple[int, int]]) -> int:
    total = 0
    previous_start = previous_end = 0
    for start, end in sorted(intervals):
        if start >= previous_end:
            total += previous_end - previous_start
            previous_start, previous_end = start, end
        else:
            previous_end = max(previous_end, end)
    return total + previous_end - previous_start


def calculate_metrics(
    inst: Instance,
    plan: Plan,
    history: list[SimEventRecord],
    start: int,
    end: int,
    busy: dict[str, int],
) -> dict[str, Any]:
    """Calculate execution metrics for the current snapshot without modifying it."""
    starts = [r for r in history if isinstance(r, TaskStateRecord) and r.new == "RUNNING"]
    ends = [r for r in history if isinstance(r, TaskStateRecord) and r.new == "DONE"]
    tasks = {t.id: t for t in inst.tasks}
    deviations = [
        abs(r.time - plan.assignments[r.task_id].start)
        for r in starts
        if r.task_id in plan.assignments
    ]
    tardiness = 0.0
    for record in ends:
        task = tasks[record.task_id]
        if task.deadline is not None:
            tardiness += task.weight * max(0, record.time - task.deadline)
    outcomes: list[str] = []
    called = False
    for item in history:
        if isinstance(item, ReplanCalled):
            called = True
        elif called and isinstance(item, ReplanResultRecord):
            outcomes.append(item.result)
            called = False
    available = {}
    for device in inst.devices:
        intervals = [
            (max(start, w.start), min(end, w.end))
            for w in inst.blocked
            if w.device_id == device.id and w.kind != "RUNNING" and w.start < end and w.end > start
        ]
        available[device.id] = end - start - _union_length(intervals)
    return {
        "events": 0,
        "replans": {
            "triggered": sum(isinstance(r, ReplanTriggered) for r in history),
            "adopted": outcomes.count("adopted"),
            "rejected": outcomes.count("rejected"),
            "none": outcomes.count("none"),
        },
        "plan_deviation_mean": sum(deviations) / len(deviations) if deviations else 0.0,
        "realized_tardiness": tardiness,
        "unfinished": sum(t.status not in ("DONE", "INTERRUPTED") for t in inst.tasks),
        "interrupted": sum(t.status == "INTERRUPTED" for t in inst.tasks),
        "busy_slots": dict(busy),
        "available_slots": available,
    }
