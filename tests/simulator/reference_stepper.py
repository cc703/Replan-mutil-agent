"""Small, deliberately slot-stepped reference for scripted single-device cases."""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class ReferenceTask:
    id: str
    start: int
    actual_duration: int
    demand: int = 1
    setup: int = 0


def step(
    tasks: list[ReferenceTask],
    capacity: int,
    faults: list[tuple[int, int]],
    cutoff: int,
    replans: dict[int, dict[str, int]] | None = None,
) -> tuple[dict[str, tuple[int, int]], set[str], list[str]]:
    """Return completed intervals, interrupted IDs and per-slot device states."""
    running: dict[str, tuple[int, int, int]] = {}
    complete: dict[str, tuple[int, int]] = {}
    interrupted: set[str] = set()
    states: list[str] = []
    preparing: set[str] = set()
    blocked: set[str] = set()
    scheduled = list(tasks)
    for now in range(cutoff):
        for tid, (start, end, _) in list(running.items()):
            if end == now:
                complete[tid] = (start, end)
                del running[tid]
        down = any(start <= now < end for start, end in faults)
        if down:
            interrupted.update(running)
            running.clear()
        if replans is not None and now in replans:
            changes = replans[now]
            scheduled = [
                replace(task, start=changes[task.id]) if task.id in changes else task
                for task in scheduled
            ]
        for task in scheduled:
            if task.setup and task.start - task.setup == now:
                if down:
                    blocked.add(task.id)
                else:
                    preparing.add(task.id)
            if task.start == now:
                preparing.discard(task.id)
                used = sum(demand for _, _, demand in running.values())
                if task.id not in blocked and not down and used + task.demand <= capacity:
                    running[task.id] = (now, now + task.actual_duration, task.demand)
        states.append("FAULT" if down else "BUSY" if running else "SETUP" if preparing else "IDLE")
    return complete, interrupted, states
