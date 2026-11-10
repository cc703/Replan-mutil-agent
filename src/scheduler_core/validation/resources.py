"""Device, person, calendar and running-block validation."""

from collections import defaultdict
from ..models import Instance, Plan
from ..validation_context import RunningBlockBinding, ValidationContext
from .execution import check_assignment_execution
from .index import ValidationIndex
from .intervals import (
    cross_overlaps,
    merge_windows,
    overloaded_segments,
    overlapping_pairs,
    overlapping_windows,
)
from .report import ViolationCollector
from .task_rules import check_assignment


def setup_rules(
    inst: Instance, index: ValidationIndex, collector: ViolationCollector
) -> dict[tuple[str, str], int]:
    add, devices = collector.add, index.devices
    setup_values: dict[tuple[str, str], set[int]] = defaultdict(set)
    for rule in inst.setups:
        setup_values[(rule.device_id, rule.task_type)].add(rule.slots)
    setups: dict[tuple[str, str], int] = {}
    for (device_id, task_type), values in sorted(setup_values.items()):
        if device_id not in devices:
            add("V1", "UNKNOWN_DEVICE_REF", device=device_id)
        if len(values) > 1:
            add("V2", "SETUP_RULE_CONFLICT", device=device_id, task_type=task_type)
        setups[(device_id, task_type)] = max(values)
    return setups


def collect_occupancy(
    inst: Instance,
    base: Plan | None,
    ctx: ValidationContext,
    index: ValidationIndex,
    setups: dict[tuple[str, str], int],
    collector: ViolationCollector,
) -> tuple[
    dict[str, list[tuple[int, int, str, int]]],
    dict[str, list[tuple[int, int, str]]],
    dict[str, list[tuple[int, int, str]]],
]:
    add = collector.add
    tasks, persons, assigned = index.tasks, index.persons, index.assigned
    # Store only valid known assignments for subsequent resource scans.
    device_intervals: dict[str, list[tuple[int, int, str, int]]] = defaultdict(list)
    person_intervals: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
    occupancy: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
    person_windows: dict[str, tuple[list[tuple[int, int]], list[int]]] = {}
    for person_item in persons.values():
        merged_person = merge_windows([(w.start, w.end) for w in person_item.blocked])
        person_windows[person_item.id] = (merged_person, [we for _, we in merged_person])
    for tid, a in sorted(assigned.items()):
        t = tasks.get(tid)
        if t is None:
            continue
        d, start = check_assignment(inst, tid, t, a, index, setups, collector)
        check_assignment_execution(inst, base, ctx, index, tid, t, a, collector)
        if d:
            occupancy[d.id].append((start, a.end, tid))
            if t.demand > d.capacity:
                add("V9", "DEMAND_EXCEEDS_CAPACITY", [tid], d.id)
            else:
                device_intervals[d.id].append((start, a.end, tid, t.demand))
        if t.needs_person and a.person_id is None:
            add("V7", "MISSING_PERSON", [tid])
        if a.person_id is not None:
            person = persons.get(a.person_id)
            if person is None:
                add("V7", "UNKNOWN_PERSON", [tid])
            else:
                if not t.required_skills <= person.skills:
                    add("V7", "SKILL_MISSING", [tid])
                person_intervals[person.id].append((a.start, a.end, tid))
                windows, ends = person_windows[person.id]
                if next(overlapping_windows(windows, ends, a.start, a.end), None) is not None:
                    add("V7", "PERSON_UNAVAILABLE", [tid])

    return device_intervals, person_intervals, occupancy


def check_overlaps(
    index: ValidationIndex,
    device_intervals: dict[str, list[tuple[int, int, str, int]]],
    person_intervals: dict[str, list[tuple[int, int, str]]],
    collector: ViolationCollector,
) -> None:
    add, devices = collector.add, index.devices
    for did, intervals in sorted(device_intervals.items()):
        cap = devices[did].capacity
        if cap == 1:
            for owner, tid in overlapping_pairs([(s, e, t) for s, e, t, _ in intervals]):
                add("V2", "DEVICE_OVERLAP", [owner, tid], did)
        else:
            for begin, end, involved in overloaded_segments(intervals, cap):
                add("V9", "CAPACITY_EXCEEDED", involved, did, start=begin, end=end)
    for pid, person_spans in sorted(person_intervals.items()):
        for owner, tid in overlapping_pairs(person_spans):
            add("V7", "PERSON_OVERLAP", [owner, tid])


def check_calendar(
    inst: Instance,
    index: ValidationIndex,
    occupancy: dict[str, list[tuple[int, int, str]]],
    collector: ViolationCollector,
) -> set[tuple[str, int, int]]:
    add, devices = collector.add, index.devices
    # Merge calendar windows and locate the first candidate via binary search.
    calendars: dict[str, list[tuple[int, int]]] = defaultdict(list)
    running = set()
    for window in inst.blocked:
        if window.device_id not in devices:
            add("V1", "UNKNOWN_DEVICE_REF", device=window.device_id)
        if window.kind == "RUNNING":
            running.add((window.device_id, window.start, window.end))
        else:
            calendars[window.device_id].append((window.start, window.end))
    for did, windows in calendars.items():
        merged = merge_windows(windows)
        ends = [e for _, e in merged]
        for s, e, tid in occupancy.get(did, []):
            for start, end in overlapping_windows(merged, ends, s, e):
                add("V6", "CALENDAR_BLOCKED", [tid], did, start=start, end=end)
    return running


def check_running_blocks(
    ctx: ValidationContext,
    index: ValidationIndex,
    running: set[tuple[str, int, int]],
    occupancy: dict[str, list[tuple[int, int, str]]],
    collector: ViolationCollector,
) -> None:
    add = collector.add
    records, assigned, tasks, snap = index.records, index.assigned, index.tasks, ctx.snapshot
    bindings: dict[tuple[str, int, int], list[RunningBlockBinding]] = defaultdict(list)
    for binding in ctx.running_block_bindings:
        bindings[(binding.device_id, binding.start, binding.end)].append(binding)
    valid: set[tuple[str, int, int]] = set()
    for block_key, binding_group in sorted(bindings.items()):
        b = binding_group[0]
        rec = records.get(b.task_id)
        binding_assignment = assigned.get(b.task_id)
        binding_task = tasks.get(b.task_id)
        if (
            len(binding_group) == 1
            and block_key in running
            and snap
            and rec
            and rec.status == "RUNNING"
            and binding_task
            and binding_task.status == "RUNNING"
            and binding_assignment
            and binding_assignment.device_id == b.device_id
            and rec.device_id == b.device_id
            and b.end == binding_assignment.end
            and rec.start <= b.start <= snap.as_of
        ):
            valid.add(block_key)
        else:
            add(
                "V2",
                "RUNNING_BLOCK_BINDING_INVALID",
                sorted({b.task_id for b in binding_group}),
                block_key[0],
            )
    unbound: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for did, s, e in sorted(running - valid):
        if (did, s, e) not in bindings:
            unbound[did].append((s, e))
    for did, windows in unbound.items():
        for tid in cross_overlaps(windows, occupancy.get(did, [])):
            add("V2", "RUNNING_BLOCK_UNBOUND", [tid], did)
