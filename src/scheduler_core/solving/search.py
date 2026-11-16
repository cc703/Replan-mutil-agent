"""Conservative symmetry breaking and optional search hints."""

import heapq
import time

from ortools.sat.python import cp_model

from scheduler_core.models import Instance
from scheduler_core.validate import validate
from . import hint


def ordered_task_ids(inst: Instance) -> list[str]:
    """Return stable EDD priority in topological order."""
    tasks = {t.id: t for t in inst.tasks}
    degree = {tid: 0 for tid in tasks}
    successors: dict[str, list[str]] = {tid: [] for tid in tasks}
    for edge in inst.precedences:
        degree[edge.succ] += 1
        successors[edge.pred].append(edge.succ)

    def key(tid: str) -> tuple[bool, int, float, str]:
        t = tasks[tid]
        return (t.deadline is None, t.deadline or 0, -t.weight, tid)

    ready = [key(tid) for tid, n in degree.items() if n == 0]
    heapq.heapify(ready)
    result = []
    while ready:
        tid = heapq.heappop(ready)[3]
        result.append(tid)
        for succ in successors[tid]:
            degree[succ] -= 1
            if degree[succ] == 0:
                heapq.heappush(ready, key(succ))
    if len(result) != len(tasks):
        result.extend(sorted(set(tasks) - set(result), key=key))
    return result


def _merge(windows: list[tuple[int, int]], horizon: int) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(
        (max(0, s), min(horizon, e)) for s, e in windows if s < horizon and e > 0
    ):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def equivalent_device_classes(inst: Instance) -> list[list[str]]:
    """Group devices only when all scheduling-relevant attributes agree."""
    groups: dict[tuple[object, ...], list[str]] = {}
    for d in inst.devices:
        windows = tuple(
            _merge(
                [(w.start, w.end) for w in inst.blocked if w.device_id == d.id],
                inst.axis.horizon_slots,
            )
        )
        rules = tuple(sorted((s.task_type, s.slots) for s in inst.setups if s.device_id == d.id))
        compatibility = tuple(d.id in t.compatible_devices for t in inst.tasks)
        key = (d.type, d.capacity, frozenset(d.capabilities), windows, rules, compatibility)
        groups.setdefault(key, []).append(d.id)
    return [sorted(group) for group in groups.values() if len(group) > 1]


def add_symmetry_breaking(
    model: cp_model.CpModel,
    inst: Instance,
    selected: dict[tuple[str, str], cp_model.IntVar],
    ordered_ids: list[str],
) -> None:
    """Require each device's first use to follow its predecessor's first use."""
    for group in equivalent_device_classes(inst):
        for previous, current in zip(group, group[1:]):
            prefix = None
            for i, tid in enumerate(ordered_ids):
                right = selected.get((tid, current))
                left = selected.get((tid, previous))
                if right is not None:
                    model.add(right <= (prefix if prefix is not None else 0))
                if left is not None and i < len(ordered_ids) - 1:
                    new = model.new_bool_var(f"seen:{previous}:{current}:{i}")
                    if prefix is None:
                        model.add(new == left)
                    else:
                        model.add_max_equality(new, [prefix, left])
                    prefix = new


def add_hint(
    model: cp_model.CpModel,
    inst: Instance,
    ordered_ids: list[str],
    starts: dict[str, cp_model.IntVar],
    selected: dict[tuple[str, str], cp_model.IntVar],
    people: dict[tuple[str, str], cp_model.IntVar],
    time_limit_s: float,
) -> None:
    """Add a complete validated compatible hint, or leave the model untouched."""
    if len(inst.tasks) * len(inst.devices) > 100_000:
        return
    deadline = time.perf_counter() + min(1.0, 0.05 * time_limit_s)
    try:
        plan = hint.build_hint(inst, ordered_ids, deadline)
        if plan is None or time.perf_counter() >= deadline:
            return
        if set(plan.assignments) != set(ordered_ids) or not validate(inst, plan).passed:
            return
        if time.perf_counter() >= deadline:
            return
        for group in equivalent_device_classes(inst):
            seen: set[str] = set()
            for tid in ordered_ids:
                did = plan.assignments[tid].device_id
                if did in group and did not in seen:
                    if did != group[len(seen)]:
                        return
                    seen.add(did)
        values = [(starts[tid], plan.assignments[tid].start) for tid in ordered_ids]
        values += [
            (v, int(plan.assignments[tid].device_id == did)) for (tid, did), v in selected.items()
        ]
        values += [
            (v, int(plan.assignments[tid].person_id == pid)) for (tid, pid), v in people.items()
        ]
        if time.perf_counter() >= deadline:
            return
        for index, (variable, value) in enumerate(values):
            if index % 128 == 0 and time.perf_counter() >= deadline:
                model.clear_hints()  # type: ignore[no-untyped-call]
                return
            model.add_hint(variable, value)
        if time.perf_counter() >= deadline:
            model.clear_hints()  # type: ignore[no-untyped-call]
    except Exception:
        model.clear_hints()  # type: ignore[no-untyped-call]
