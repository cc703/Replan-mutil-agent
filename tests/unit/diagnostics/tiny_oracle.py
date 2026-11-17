"""Independent enumeration for tiny one-device scheduling instances."""

from itertools import product
from scheduler_core.models import Instance


def feasible(inst: Instance, groups: set[str]) -> bool:
    h = inst.axis.horizon_slots
    tasks = inst.tasks
    for starts in product(range(h + 1), repeat=len(tasks)):
        intervals = {t.id: (s, s + t.duration) for t, s in zip(tasks, starts)}
        if any(s < max(inst.now, t.release) or e > h for t in tasks for s, e in [intervals[t.id]]):
            continue
        if any(
            f"deadline:{t.id}" in groups
            and t.deadline is not None
            and intervals[t.id][1] > t.deadline
            for t in tasks
        ):
            continue
        if "capacity:D" in groups and any(
            intervals[a.id][0] < intervals[b.id][1] and intervals[b.id][0] < intervals[a.id][1]
            for i, a in enumerate(tasks)
            for b in tasks[i + 1 :]
        ):
            continue
        return True
    return False
