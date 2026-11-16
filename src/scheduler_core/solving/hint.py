"""Budgeted greedy construction of an optional initial-solve hint."""

from time import perf_counter

from scheduler_core.models import Assignment, Instance, Plan, Precedence

# Limit pair evaluations independently of the horizon length.
_MAX_PAIRS = 100_000


def _fits(
    start: int, end: int, demand: int, capacity: int, intervals: list[tuple[int, int, int]]
) -> bool:
    events = [(start, demand), (end, -demand)]
    for left, right, used in intervals:
        if left < end and start < right:
            events.extend(((max(start, left), used), (min(end, right), -used)))
    load = 0
    for _, delta in sorted(events):
        load += delta
        if load > capacity:
            return False
    return True


def build_hint(inst: Instance, ordered_ids: list[str], deadline: float) -> Plan | None:
    """Build a complete greedy plan before an absolute perf_counter deadline, or return None.

    The caller must independently validate the result and check any symmetry rules.
    The search uses interval endpoints rather than scanning the planning horizon.
    """
    tasks = {t.id: t for t in inst.tasks}
    if len(ordered_ids) != len(tasks) or set(ordered_ids) != set(tasks):
        return None
    devices = {d.id: d for d in inst.devices}
    setup = {(s.device_id, s.task_type): s.slots for s in inst.setups}
    occupied: dict[str, list[tuple[int, int, int]]] = {d.id: [] for d in inst.devices}
    people: dict[str, list[tuple[int, int, int]]] = {p.id: [] for p in inst.persons}
    for w in inst.blocked:
        occupied[w.device_id].append((w.start, w.end, devices[w.device_id].capacity))
    for p in inst.persons:
        people[p.id].extend((w.start, w.end, 1) for w in p.blocked)
    predecessors: dict[str, list[Precedence]] = {tid: [] for tid in tasks}
    for edge in inst.precedences:
        predecessors[edge.succ].append(edge)
    result: dict[str, Assignment] = {}
    evaluations = 0
    for tid in ordered_ids:
        if perf_counter() >= deadline:
            return None
        task = tasks[tid]
        earliest = max(inst.now, task.release)
        latest = (
            min(
                inst.axis.horizon_slots,
                task.deadline if task.deadline is not None else inst.axis.horizon_slots,
            )
            - task.duration
        )
        for edge in predecessors[tid]:
            if edge.pred not in result:
                return None
            earliest = max(earliest, result[edge.pred].end + edge.lag_min)
            if edge.lag_max is not None:
                latest = min(latest, result[edge.pred].end + edge.lag_max)
        best: tuple[int, str, str | None] | None = None
        for did in sorted(set(task.compatible_devices)):
            if perf_counter() >= deadline:
                return None
            device = devices[did]
            if task.demand > device.capacity:
                continue
            prep = setup.get((did, task.type), 0)
            candidates = {max(earliest, prep)}
            candidates.update(end + prep for _, end, _ in occupied[did])
            eligible = sorted(p.id for p in inst.persons if task.required_skills <= p.skills)
            person_ids: list[str | None] = list(eligible) if task.needs_person else [None]
            for pid in person_ids:
                if perf_counter() >= deadline:
                    return None
                starts = candidates | ({end for _, end, _ in people[pid]} if pid else set())
                for start in sorted(starts):
                    evaluations += 1
                    if evaluations > _MAX_PAIRS or perf_counter() >= deadline:
                        return None
                    if start < max(earliest, prep) or start > latest:
                        continue
                    end = start + task.duration
                    if not _fits(start - prep, end, task.demand, device.capacity, occupied[did]):
                        continue
                    if pid is not None and not _fits(start, end, 1, 1, people[pid]):
                        continue
                    choice = (start, did, pid)
                    if best is None or (start, did, pid or "") < (best[0], best[1], best[2] or ""):
                        best = choice
                    break
        if best is None:
            return None
        start, did, pid = best
        end = start + task.duration
        result[tid] = Assignment(task_id=tid, device_id=did, person_id=pid, start=start, end=end)
        occupied[did].append((start - setup.get((did, task.type), 0), end, task.demand))
        if pid is not None:
            people[pid].append((start, end, 1))
    return Plan(id="greedy-hint", assignments=result)
