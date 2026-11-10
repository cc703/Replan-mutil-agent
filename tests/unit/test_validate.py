"""Acceptance checks for independent schedule validation."""

import ast
from copy import deepcopy
from datetime import datetime, timezone
from itertools import combinations_with_replacement, product
from pathlib import Path
from typing import Literal

from scheduler_core.axis import TimeAxis
from scheduler_core.models import (
    Assignment,
    BlockedWindow,
    Device,
    Instance,
    Person,
    PersonBlockedWindow,
    Plan,
    Precedence,
    SetupRule,
    Task,
)
from scheduler_core.validate import validate
from scheduler_core.validation_context import (
    DeadlineAuthorization,
    ExecutionRecord,
    ExecutionSnapshot,
    FrozenEndChange,
    RunningBlockBinding,
    ValidationContext,
)
import pytest


def instance() -> Instance:
    return Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=40),
        devices=[Device(id="d", type="x")],
        tasks=[
            Task(id=x, experiment_id="e", type="x", duration=4, compatible_devices=["d"])
            for x in ("a", "b")
        ],
    )


def test_overlap_and_half_open_boundary() -> None:
    inst = instance()
    plan = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=4),
            "b": Assignment(task_id="b", device_id="d", start=3, end=7),
        },
    )
    report = validate(inst, plan)
    assert any(
        v.code == "V2" and "reason=DEVICE_OVERLAP;" in v.detail and v.task_ids == ["a", "b"]
        for v in report.violations
    )
    plan.assignments["b"] = Assignment(task_id="b", device_id="d", start=4, end=8)
    assert validate(inst, plan).passed


def test_missing_assignment() -> None:
    report = validate(instance(), Plan(id="p", assignments={}))
    assert any(
        v.code == "V1" and "reason=MISSING_ASSIGNMENT;" in v.detail and v.task_ids == ["a"]
        for v in report.violations
    )


def test_exhaustive_overlap_oracle() -> None:
    spans = [(s, e) for s in range(5) for e in range(s + 1, 6)]
    count = 0
    observed: set[str] = set()
    cases = list(combinations_with_replacement(spans, 3)) + [
        ((0, 2), (1, 3), (3, 5), (4, 5)),
        ((0, 5), (0, 3), (1, 2), (4, 5)),
        ((0, 1), (1, 2), (2, 3), (3, 4)),
    ]
    for intervals in cases:
        n = len(intervals)
        if any(a == b for i, a in enumerate(intervals) for b in intervals[i + 1 :]):
            observed.add("identical")
        if any(
            a[0] == b[0] and a != b for i, a in enumerate(intervals) for b in intervals[i + 1 :]
        ):
            observed.add("same_start")
        if any(
            a[1] == b[1] and a != b for i, a in enumerate(intervals) for b in intervals[i + 1 :]
        ):
            observed.add("same_end")
        if any(a[0] < b[0] and b[1] < a[1] for a in intervals for b in intervals):
            observed.add("nested")
        if any(a[1] == b[0] for a in intervals for b in intervals):
            observed.add("touching")
        if intervals == ((0, 2), (1, 3), (3, 5), (4, 5)):
            observed.add("two_components")
        if intervals == ((0, 1), (1, 2), (2, 3), (3, 4)):
            observed.add("touching_chain")
        for mask in (0, 3, (1 << n) - 1):
            tasks = [
                Task(
                    id=str(i), experiment_id="e", type="x", duration=e - s, compatible_devices=["d"]
                )
                for i, (s, e) in enumerate(intervals)
            ]
            inst = Instance(
                axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=10),
                devices=[Device(id="d", type="x")],
                tasks=tasks,
                persons=[Person(id="p")],
            )
            plan = Plan(
                id="p",
                assignments={
                    str(i): Assignment(
                        task_id=str(i),
                        device_id="d",
                        start=s,
                        end=e,
                        person_id="p" if mask & (1 << i) else None,
                    )
                    for i, (s, e) in enumerate(intervals)
                },
            )
            report = validate(inst, plan)
            for code, reason, indices in (
                ("V2", "DEVICE_OVERLAP", range(n)),
                ("V7", "PERSON_OVERLAP", [i for i in range(n) if mask & (1 << i)]),
            ):
                pairs = [
                    (str(i), str(j))
                    for i in indices
                    for j in indices
                    if i < j
                    and intervals[i][0] < intervals[j][1]
                    and intervals[j][0] < intervals[i][1]
                ]
                expected = {x for pair in pairs for x in pair}
                violations = [
                    v
                    for v in report.violations
                    if v.code == code and f"reason={reason};" in v.detail
                ]
                assert {x for v in violations for x in v.task_ids} == expected
                assert len(violations) <= max(0, len(indices) - 1)
                for left, right in pairs:
                    component = {left, right}
                    while True:
                        expanded = component | {
                            x for pair in pairs if component.intersection(pair) for x in pair
                        }
                        if expanded == component:
                            break
                        component = expanded
                    assert any(component.intersection(v.task_ids) for v in violations)
            count += 1
    assert count == 2049
    assert observed == {
        "identical",
        "same_start",
        "same_end",
        "nested",
        "touching",
        "two_components",
        "touching_chain",
    }


def test_exhaustive_capacity_oracle() -> None:
    spans = [(0, 1), (0, 3), (1, 2), (1, 4), (3, 4)]
    count = 0
    combinations_seen: set[tuple[int, int]] = set()
    for intervals in combinations_with_replacement(spans, 3):
        for demands in product((1, 2, 3), repeat=3):
            for cap in (1, 2, 3, 4):
                combinations_seen.update((cap, demand) for demand in demands)
                tasks = [
                    Task(
                        id=str(i),
                        experiment_id="e",
                        type="x",
                        duration=e - s,
                        compatible_devices=["d"],
                        demand=demands[i],
                    )
                    for i, (s, e) in enumerate(intervals)
                ]
                inst = Instance(
                    axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=10),
                    devices=[Device(id="d", type="x", capacity=cap)],
                    tasks=tasks,
                )
                plan = Plan(
                    id="p",
                    assignments={
                        str(i): Assignment(task_id=str(i), device_id="d", start=s, end=e)
                        for i, (s, e) in enumerate(intervals)
                    },
                )
                report = validate(inst, plan)
                if cap == 1:
                    pairs = [
                        (str(i), str(j))
                        for i in range(3)
                        for j in range(i + 1, 3)
                        if demands[i] <= cap
                        and demands[j] <= cap
                        and intervals[i][0] < intervals[j][1]
                        and intervals[j][0] < intervals[i][1]
                    ]
                    overlaps = [
                        v
                        for v in report.violations
                        if v.code == "V2" and "reason=DEVICE_OVERLAP;" in v.detail
                    ]
                    assert {tid for v in overlaps for tid in v.task_ids} == {
                        tid for pair in pairs for tid in pair
                    }
                    assert {
                        v.task_ids[0]
                        for v in report.violations
                        if v.code == "V9" and "reason=DEMAND_EXCEEDS_CAPACITY;" in v.detail
                    } == {str(i) for i, d in enumerate(demands) if d > cap}
                    assert not reasons(report, "V9", "CAPACITY_EXCEEDED")
                    count += 1
                    continue
                segments: list[tuple[int, int, set[str]]] = []
                points = sorted({x for pair in intervals for x in pair})
                for start, end in zip(points, points[1:]):
                    active = {
                        str(i)
                        for i, (s, e) in enumerate(intervals)
                        if s <= start and end <= e and demands[i] <= cap
                    }
                    if sum(demands[int(i)] for i in active) > cap:
                        if segments and segments[-1][1] == start:
                            prev = segments.pop()
                            segments.append((prev[0], end, prev[2] | active))
                        else:
                            segments.append((start, end, active))
                violations = [
                    v
                    for v in report.violations
                    if v.code == "V9" and "reason=CAPACITY_EXCEEDED;" in v.detail
                ]
                assert len(violations) == len(segments)
                for start, end, active in segments:
                    assert any(
                        set(v.task_ids) == active
                        and f"start={start};" in v.detail
                        and f"end={end};" in v.detail
                        for v in violations
                    )
                assert {
                    v.task_ids[0]
                    for v in report.violations
                    if v.code == "V9" and "reason=DEMAND_EXCEEDS_CAPACITY;" in v.detail
                } == {str(i) for i, d in enumerate(demands) if d > cap}
                count += 1
    assert count == 3780
    assert combinations_seen == set(product((1, 2, 3, 4), (1, 2, 3)))


def reasons(report: object, code: str, reason: str) -> list[list[str]]:
    from scheduler_core.models import ValidationReport

    assert isinstance(report, ValidationReport)
    return [
        v.task_ids for v in report.violations if v.code == code and f"reason={reason};" in v.detail
    ]


def execution_case(
    status: Literal["RUNNING", "DONE"],
    end: int,
    *,
    base_as_of: int | None = 5,
    actual: int = 8,
    remaining: int = 4,
) -> tuple[Instance, Plan, Plan, ValidationContext]:
    now = 10 if status == "RUNNING" else max(12, actual)
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=40),
        now=now,
        devices=[Device(id="d", type="x")],
        tasks=[
            Task(
                id="a",
                experiment_id="e",
                type="x",
                duration=10,
                compatible_devices=["d"],
                status=status,
            )
        ],
    )
    base = Plan(
        id="base", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=10)}
    )
    plan = Plan(
        id="new",
        parent_id="base",
        assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=end)},
    )
    if status == "RUNNING":
        rec = ExecutionRecord(
            task_id="a",
            status="RUNNING",
            device_id="d",
            start=0,
            planned_end=10,
            remaining_estimate=remaining,
            event_id="event",
        )
    else:
        rec = ExecutionRecord(
            task_id="a", status="DONE", device_id="d", start=0, actual_end=actual, event_id="event"
        )
    ctx = ValidationContext(
        snapshot=ExecutionSnapshot(plan_id="base", as_of=now, base_as_of=base_as_of, records=[rec])
    )
    return inst, plan, base, ctx


def test_running_end_evidence_matrix() -> None:
    inst, plan, base, ctx = execution_case("RUNNING", 14)
    change = FrozenEndChange(
        task_id="a",
        plan_id="new",
        base_plan_id="base",
        old_end=10,
        new_end=14,
        event_id="event",
        acted_at=10,
    )
    assert reasons(
        validate(inst, plan, base=base, context=ctx), "V11", "FROZEN_END_NO_EVIDENCE"
    ) == [["a"]]
    ctx.end_changes.append(change)
    assert validate(inst, plan, base=base, context=ctx).passed


@pytest.mark.parametrize(
    "field,value",
    [
        ("task_id", "other"),
        ("plan_id", "other"),
        ("base_plan_id", "other"),
        ("old_end", 9),
        ("new_end", 15),
        ("acted_at", 11),
    ],
)
def test_running_end_evidence_scope(field: str, value: object) -> None:
    inst, plan, base, ctx = execution_case("RUNNING", 14)
    change = FrozenEndChange(
        task_id="a",
        plan_id="new",
        base_plan_id="base",
        old_end=10,
        new_end=14,
        event_id="event",
        acted_at=10,
    )
    ctx.end_changes = [change]
    assert validate(inst, plan, base=base, context=ctx).passed
    ctx.end_changes = [change.model_copy(update={field: value})]
    report = validate(inst, plan, base=base, context=ctx)
    assert reasons(report, "V11", "FROZEN_END_EVIDENCE_INVALID") == (
        [["other"]] if field == "task_id" else [["a"]]
    )
    ctx.end_changes[0] = change.model_copy(update={"base_plan_id": "wrong"})
    assert reasons(
        validate(inst, plan, base=base, context=ctx), "V11", "FROZEN_END_EVIDENCE_INVALID"
    ) == [["a"]]
    ctx.end_changes = [change, change]
    assert reasons(
        validate(inst, plan, base=base, context=ctx), "V11", "FROZEN_END_EVIDENCE_INVALID"
    ) == [["a"]]
    plan.assignments["a"] = plan.assignments["a"].model_copy(update={"end": 9})
    assert reasons(validate(inst, plan, base=base, context=ctx), "V10", "END_MISMATCH") == [["a"]]
    inst, plan, base, ctx = execution_case("RUNNING", 10, remaining=0)
    ctx.end_changes = [change]
    assert reasons(
        validate(inst, plan, base=base, context=ctx), "V11", "FROZEN_END_EVIDENCE_INVALID"
    ) == [["a"]]
    ctx.end_changes = []
    assert validate(inst, plan, base=base, context=ctx).passed


@pytest.mark.parametrize("actual", [8, 12])
def test_done_real_completion(actual: int) -> None:
    inst, plan, base, ctx = execution_case("DONE", actual, actual=actual)
    assert validate(inst, plan, base=base, context=ctx).passed
    plan.assignments["a"] = plan.assignments["a"].model_copy(update={"end": actual + 1})
    assert reasons(validate(inst, plan, base=base, context=ctx), "V10", "END_MISMATCH") == [["a"]]
    ctx.snapshot = None
    assert reasons(validate(inst, plan, base=base, context=ctx), "V10", "DONE_NO_EVIDENCE") == [
        ["a"]
    ]


def test_done_history_and_missing_base_as_of() -> None:
    inst, plan, base, ctx = execution_case("DONE", 8, actual=8, base_as_of=8)
    assert reasons(
        validate(inst, plan, base=base, context=ctx), "V10", "DONE_HISTORY_REWRITTEN"
    ) == [["a"]]
    base.assignments["a"] = plan.assignments["a"]
    assert validate(inst, plan, base=base, context=ctx).passed
    assert ctx.snapshot is not None
    ctx.snapshot.base_as_of = None
    assert reasons(
        validate(inst, plan, base=base, context=ctx), "V10", "SNAPSHOT_RECORD_INVALID"
    ) == [["a"]]
    ctx.snapshot.base_as_of = 8
    plan.assignments["a"] = plan.assignments["a"].model_copy(
        update={"start": 1, "device_id": "other"}
    )
    report = validate(inst, plan, base=base, context=ctx)
    assert reasons(report, "V8", "FROZEN_START_CHANGED") == [["a"]]
    assert reasons(report, "V8", "FROZEN_DEVICE_CHANGED") == [["a"]]


@pytest.mark.parametrize("capacity", [1, 4])
def test_running_unbound_windows(capacity: int) -> None:
    inst = instance()
    inst.devices[0].capacity = capacity
    inst.blocked = [BlockedWindow(device_id="d", start=5, end=8, kind="RUNNING")]
    plan = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=4),
            "b": Assignment(task_id="b", device_id="d", start=8, end=12),
        },
    )
    assert not reasons(validate(inst, plan), "V2", "RUNNING_BLOCK_UNBOUND")
    plan.assignments["b"] = plan.assignments["b"].model_copy(update={"start": 7, "end": 11})
    assert reasons(validate(inst, plan), "V2", "RUNNING_BLOCK_UNBOUND") == [["b"]]


def test_running_binding_capacity_and_deduplication() -> None:
    inst, plan, base, ctx = execution_case("RUNNING", 10, remaining=0)
    inst.devices[0].capacity = 4
    inst.blocked = [BlockedWindow(device_id="d", start=5, end=10, kind="RUNNING")]
    ctx.running_block_bindings = [RunningBlockBinding(device_id="d", start=5, end=10, task_id="a")]
    for i in range(3):
        tid = str(i)
        inst.tasks.append(
            Task(id=tid, experiment_id="e", type="x", duration=2, compatible_devices=["d"])
        )
        plan.assignments[tid] = Assignment(task_id=tid, device_id="d", start=10, end=12)
    # Move snapshot and now so simultaneous tasks are non-frozen and legal.
    inst.now = 5
    assert ctx.snapshot is not None
    ctx.snapshot.as_of = 5
    for tid in ("0", "1", "2"):
        plan.assignments[tid] = plan.assignments[tid].model_copy(update={"start": 5, "end": 7})
    assert validate(inst, plan, base=base, context=ctx).passed
    inst.tasks.append(
        Task(id="3", experiment_id="e", type="x", duration=2, compatible_devices=["d"])
    )
    plan.assignments["3"] = Assignment(task_id="3", device_id="d", start=5, end=7)
    report = validate(inst, plan, base=base, context=ctx)
    assert reasons(report, "V9", "CAPACITY_EXCEEDED") == [["0", "1", "2", "3", "a"]]
    assert not reasons(report, "V2", "RUNNING_BLOCK_UNBOUND")
    inst.devices[0].capacity = 1
    inst.tasks = inst.tasks[:2]
    plan.assignments = {k: v for k, v in plan.assignments.items() if k in ("a", "0")}
    report = validate(inst, plan, base=base, context=ctx)
    assert reasons(report, "V2", "DEVICE_OVERLAP") == [["0", "a"]]
    assert not reasons(report, "V2", "RUNNING_BLOCK_UNBOUND")


@pytest.mark.parametrize(
    "case",
    [
        "no_record",
        "not_running",
        "no_assignment",
        "device",
        "end",
        "start",
        "no_window",
        "duplicate",
    ],
)
def test_invalid_running_bindings(case: str) -> None:
    inst, plan, base, ctx = execution_case("RUNNING", 10, remaining=0)
    inst.blocked = [BlockedWindow(device_id="d", start=5, end=10, kind="RUNNING")]
    binding = RunningBlockBinding(device_id="d", start=5, end=10, task_id="a")
    assert ctx.snapshot is not None
    if case == "no_record":
        ctx.snapshot.records.clear()
    elif case == "not_running":
        inst.tasks[0].status = "PENDING"
    elif case == "no_assignment":
        plan.assignments.clear()
    elif case == "device":
        binding.device_id = "other"
        inst.blocked[0].device_id = "other"
    elif case == "end":
        binding.end = 9
        inst.blocked[0].end = 9
    elif case == "start":
        binding.start = 11
        binding.end = 12
        inst.blocked[0].start = 11
        inst.blocked[0].end = 12
    elif case == "no_window":
        inst.blocked.clear()
    ctx.running_block_bindings = [binding, binding] if case == "duplicate" else [binding]
    assert reasons(
        validate(inst, plan, base=base, context=ctx), "V2", "RUNNING_BLOCK_BINDING_INVALID"
    ) == [["a"]]
    ctx.running_block_bindings = []
    assert not reasons(
        validate(inst, plan, base=base, context=ctx), "V2", "RUNNING_BLOCK_BINDING_INVALID"
    )


def test_mini_fixture_golden_and_tamper() -> None:
    path = Path(__file__).resolve().parents[2] / "data/fixtures/mini.json"
    inst = Instance.model_validate_json(path.read_text(encoding="utf-8"))
    plan = Plan(
        id="gold",
        assignments={
            "A": Assignment(task_id="A", device_id="D1", start=0, end=4),
            "C": Assignment(task_id="C", device_id="D1", start=4, end=10),
            "D": Assignment(task_id="D", device_id="D2", start=0, end=6),
            "B": Assignment(task_id="B", device_id="D2", start=6, end=10),
        },
    )
    assert validate(inst, plan).passed
    plan.assignments["C"] = plan.assignments["C"].model_copy(update={"start": 3, "end": 9})
    assert reasons(validate(inst, plan), "V2", "DEVICE_OVERLAP") == [["A", "C"]]
    plan.assignments["B"] = plan.assignments["B"].model_copy(update={"start": 0, "end": 4})
    assert reasons(validate(inst, plan), "V3", "PRECEDENCE_MIN_LAG") == [["A", "B"]]


def test_deterministic_immutable_huge_and_import_boundary() -> None:
    inst = instance()
    inst.axis.horizon_slots = 10**9
    plan = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=4),
            "b": Assignment(task_id="b", device_id="d", start=2, end=6),
        },
    )
    before = deepcopy((inst.model_dump(), plan.model_dump()))
    report = validate(inst, plan)
    assert (inst.model_dump(), plan.model_dump()) == before
    inst.tasks.reverse()
    plan.assignments = dict(reversed(list(plan.assignments.items())))
    assert validate(inst, plan) == report
    root = Path(__file__).resolve().parents[2] / "src/scheduler_core"
    for name in ("validate.py", "validation_context.py"):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        imports = [
            a.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for a in node.names
        ]
        imports += [
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        ]
        assert not {"ortools", "numpy", "random"}.intersection(imports)


def test_single_demand_above_capacity_only_v9() -> None:
    inst = instance()
    inst.tasks = inst.tasks[:1]
    inst.tasks[0].demand = 2
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=4)})
    report = validate(inst, plan)
    assert reasons(report, "V9", "DEMAND_EXCEEDS_CAPACITY") == [["a"]]
    assert not reasons(report, "V2", "DEVICE_OVERLAP")
    inst.tasks[0].demand = 1
    assert validate(inst, plan).passed


def test_setup_calendar_and_half_open() -> None:
    inst = instance()
    inst.tasks = inst.tasks[:1]
    inst.setups = [SetupRule(device_id="d", task_type="x", slots=2)]
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=4)})
    report = validate(inst, plan)
    assert reasons(report, "V6", "SETUP_BEFORE_ORIGIN") == [["a"]]
    assert not reasons(report, "V2", "DEVICE_OVERLAP")
    plan.assignments["a"] = plan.assignments["a"].model_copy(update={"start": 3, "end": 7})
    inst.blocked = [
        BlockedWindow(device_id="d", kind="FAULT", start=0, end=2),
        BlockedWindow(device_id="d", kind="MAINT", start=1, end=2),
    ]
    assert reasons(validate(inst, plan), "V6", "CALENDAR_BLOCKED") == [["a"]]
    plan.assignments["a"] = plan.assignments["a"].model_copy(update={"start": 4, "end": 8})
    assert validate(inst, plan).passed


def test_person_skill_and_calendar() -> None:
    inst = instance()
    inst.tasks = inst.tasks[:1]
    inst.tasks[0].required_skills = {"x", "y"}
    inst.persons = [Person(id="p", skills={"x"}, blocked=[PersonBlockedWindow(start=4, end=6)])]
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=4)})
    assert reasons(validate(inst, plan), "V7", "MISSING_PERSON") == [["a"]]
    plan.assignments["a"].person_id = "missing"
    assert reasons(validate(inst, plan), "V7", "UNKNOWN_PERSON") == [["a"]]
    plan.assignments["a"].person_id = "p"
    assert reasons(validate(inst, plan), "V7", "SKILL_MISSING") == [["a"]]
    inst.persons[0].skills.add("y")
    assert validate(inst, plan).passed
    plan.assignments["a"] = plan.assignments["a"].model_copy(update={"start": 1, "end": 5})
    assert reasons(validate(inst, plan), "V7", "PERSON_UNAVAILABLE") == [["a"]]
    inst.persons[0].blocked.clear()
    assert validate(inst, plan).passed


@pytest.mark.parametrize(
    "token",
    [
        "MISSING_ASSIGNMENT",
        "UNKNOWN_TASK",
        "UNKNOWN_DEVICE",
        "DEVICE_NOT_COMPATIBLE",
        "EMPTY_COMPATIBLE_LIST",
        "UNKNOWN_DEVICE_REF",
        "TASK_NOT_SCHEDULABLE",
    ],
)
def test_v1_reason_matrix(token: str) -> None:
    inst = instance()
    inst.tasks = inst.tasks[:1]
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=4)})
    assert not reasons(validate(inst, plan), "V1", token)
    if token == "MISSING_ASSIGNMENT":
        plan.assignments.clear()
        ids = ["a"]
    elif token == "UNKNOWN_TASK":
        plan.assignments["z"] = Assignment(task_id="z", device_id="d", start=5, end=9)
        ids = ["z"]
    elif token == "UNKNOWN_DEVICE":
        plan.assignments["a"].device_id = "z"
        ids = ["a"]
    elif token == "DEVICE_NOT_COMPATIBLE":
        inst.devices.append(Device(id="z", type="x"))
        plan.assignments["a"].device_id = "z"
        ids = ["a"]
    elif token == "EMPTY_COMPATIBLE_LIST":
        inst.tasks[0].compatible_devices = []
        ids = ["a"]
    elif token == "UNKNOWN_DEVICE_REF":
        inst.tasks[0].compatible_devices.append("z")
        ids = ["a"]
    else:
        inst.tasks[0].status = "FAILED"
        ids = ["a"]
    assert reasons(validate(inst, plan), "V1", token) == [ids]


@pytest.mark.parametrize("status", ["FAILED", "CANCELLED", "INTERRUPTED"])
def test_unschedulable_statuses(status: str) -> None:
    inst = instance()
    inst.tasks = inst.tasks[:1]
    inst.tasks[0].status = status  # type: ignore[assignment]
    plan = Plan(id="p", assignments={})
    assert validate(inst, plan).passed
    plan.assignments["a"] = Assignment(task_id="a", device_id="d", start=0, end=4)
    assert reasons(validate(inst, plan), "V1", "TASK_NOT_SCHEDULABLE") == [["a"]]


@pytest.mark.parametrize(
    "token",
    ["PRECEDENCE_MIN_LAG", "PRECEDENCE_MAX_LAG", "PRECEDENCE_UNKNOWN_TASK", "PRECEDENCE_CYCLE"],
)
def test_precedence_reasons_and_boundaries(token: str) -> None:
    inst = instance()
    inst.devices.append(Device(id="e", type="x"))
    inst.tasks[1].compatible_devices.append("e")
    plan = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=4),
            "b": Assignment(task_id="b", device_id="e", start=5, end=9),
        },
    )
    inst.precedences = [Precedence(pred="a", succ="b", lag_min=1, lag_max=1)]
    assert validate(inst, plan).passed
    if token == "PRECEDENCE_MIN_LAG":
        plan.assignments["b"] = plan.assignments["b"].model_copy(update={"start": 4, "end": 8})
    elif token == "PRECEDENCE_MAX_LAG":
        plan.assignments["b"] = plan.assignments["b"].model_copy(update={"start": 6, "end": 10})
    elif token == "PRECEDENCE_UNKNOWN_TASK":
        inst.precedences.append(Precedence(pred="a", succ="z"))
    else:
        inst.precedences.append(Precedence(pred="b", succ="a"))
    ids = ["a", "z"] if token == "PRECEDENCE_UNKNOWN_TASK" else ["a", "b"]
    assert reasons(validate(inst, plan), "V3", token) == [ids]


@pytest.mark.parametrize(
    "token",
    [
        "RELEASE_VIOLATED",
        "START_BEFORE_NOW",
        "HORIZON_EXCEEDED",
        "DURATION_MISMATCH",
        "SETUP_RULE_CONFLICT",
    ],
)
def test_time_and_setup_reason_matrix(token: str) -> None:
    inst = instance()
    inst.tasks = inst.tasks[:1]
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=2, end=6)})
    code = {
        "RELEASE_VIOLATED": "V4",
        "START_BEFORE_NOW": "V4",
        "HORIZON_EXCEEDED": "V6",
        "DURATION_MISMATCH": "V10",
        "SETUP_RULE_CONFLICT": "V2",
    }[token]
    assert not reasons(validate(inst, plan), code, token)
    if token == "RELEASE_VIOLATED":
        inst.tasks[0].release = 3
    elif token == "START_BEFORE_NOW":
        inst.now = 3
    elif token == "HORIZON_EXCEEDED":
        inst.axis.horizon_slots = 5
    elif token == "DURATION_MISMATCH":
        inst.tasks[0].duration = 5
    else:
        inst.setups = [
            SetupRule(device_id="d", task_type="x", slots=1),
            SetupRule(device_id="d", task_type="x", slots=2),
        ]
    assert reasons(validate(inst, plan), code, token) == (
        [[]] if token == "SETUP_RULE_CONFLICT" else [["a"]]
    )


@pytest.mark.parametrize(
    "token",
    [
        "DEADLINE_EXCEEDED",
        "AUTH_NOT_APPLICABLE",
        "AUTH_EXPIRED",
        "AUTH_FUTURE",
        "AUTH_OUT_OF_SCOPE",
        "AUTH_DUPLICATE",
    ],
)
def test_deadline_authorization_matrix(token: str) -> None:
    inst = instance()
    inst.tasks = inst.tasks[:1]
    inst.now = 2
    inst.tasks[0].deadline = 5
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=2, end=6)})
    auth = DeadlineAuthorization(
        task_id="a",
        plan_id="p",
        original_deadline=5,
        relaxed_deadline=6,
        confirmation_id="human",
        acted_at=1,
        valid_until=3,
    )
    ctx = ValidationContext(deadline_authorizations=[auth])
    assert validate(inst, plan, context=ctx).passed
    if token == "DEADLINE_EXCEEDED":
        ctx.deadline_authorizations = []
    elif token == "AUTH_NOT_APPLICABLE":
        inst.tasks[0].deadline_level = "HARD"
    elif token == "AUTH_EXPIRED":
        auth.valid_until = 1
    elif token == "AUTH_FUTURE":
        auth.acted_at = 3
    elif token == "AUTH_OUT_OF_SCOPE":
        auth.plan_id = "wrong"
    else:
        ctx.deadline_authorizations.append(auth.model_copy())
    assert reasons(validate(inst, plan, context=ctx), "V5", token) == [["a"]]


def test_authorization_unknown_wrong_original_and_hard() -> None:
    inst = instance()
    inst.tasks = inst.tasks[:1]
    inst.tasks[0].deadline = 4
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=4)})
    auth = DeadlineAuthorization(
        task_id="z",
        plan_id="p",
        original_deadline=4,
        relaxed_deadline=6,
        confirmation_id="c",
        acted_at=0,
    )
    ctx = ValidationContext(deadline_authorizations=[auth])
    assert reasons(validate(inst, plan, context=ctx), "V5", "AUTH_NOT_APPLICABLE") == [["z"]]
    auth.task_id = "a"
    auth.original_deadline = 3
    assert reasons(validate(inst, plan, context=ctx), "V5", "AUTH_OUT_OF_SCOPE") == [["a"]]
    auth.original_deadline = 4
    assert validate(inst, plan, context=ctx).passed


@pytest.mark.parametrize("source", ["plan", "base"])
def test_assignment_key_mismatch_after_mutation(source: str) -> None:
    inst = instance()
    plan = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=4),
            "b": Assignment(task_id="b", device_id="d", start=4, end=8),
        },
    )
    base = plan.model_copy(deep=True)
    base.id = "base"
    plan.parent_id = "base"
    assert not reasons(validate(inst, plan, base=base), "V1", "ASSIGNMENT_KEY_MISMATCH")
    target = plan if source == "plan" else base
    target.assignments["a"].task_id = "b"
    report = validate(inst, plan, base=base)
    assert reasons(report, "V1", "ASSIGNMENT_KEY_MISMATCH") == [["a", "b"]]
    assert any(
        f"source={source};" in v.detail
        for v in report.violations
        if "reason=ASSIGNMENT_KEY_MISMATCH;" in v.detail
    )


@pytest.mark.parametrize(
    "token",
    [
        "PARENT_MISMATCH",
        "BASE_REQUIRED",
        "FREE_UNKNOWN_TASK",
        "FREE_CONTAINS_FROZEN",
        "ADDED_NOT_FREE",
        "REMOVED_NOT_FREE",
        "BASE_TASK_UNKNOWN",
        "NONFREE_CHANGED",
    ],
)
def test_neighborhood_reasons(token: str) -> None:
    inst = instance()
    plan = Plan(
        id="p",
        parent_id="base",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=4),
            "b": Assignment(task_id="b", device_id="d", start=4, end=8),
        },
    )
    base = plan.model_copy(deep=True)
    base.id = "base"
    assert validate(inst, plan, base=base, free=set()).passed
    free: set[str] | None = set()
    effective_base: Plan | None = base
    ids: list[str] = []
    if token == "PARENT_MISMATCH":
        plan.parent_id = "wrong"
    elif token == "BASE_REQUIRED":
        effective_base = None
    elif token == "FREE_UNKNOWN_TASK":
        free = {"z"}
        ids = ["z"]
    elif token == "FREE_CONTAINS_FROZEN":
        inst.now = 1
        free = {"a"}
        ids = ["a"]
    elif token == "ADDED_NOT_FREE":
        del base.assignments["b"]
        ids = ["b"]
    elif token == "REMOVED_NOT_FREE":
        del plan.assignments["b"]
        ids = ["b"]
    elif token == "BASE_TASK_UNKNOWN":
        base.assignments["z"] = Assignment(task_id="z", device_id="d", start=9, end=10)
        ids = ["z"]
    else:
        plan.assignments["b"] = plan.assignments["b"].model_copy(update={"start": 5, "end": 9})
        ids = ["b"]
    assert reasons(validate(inst, plan, base=effective_base, free=free), "V11", token) == [ids]
    if token == "NONFREE_CHANGED":
        assert not reasons(validate(inst, plan, base=base, free=None), "V11", token)
        assert not reasons(validate(inst, plan, base=base, free={"b"}), "V11", token)


@pytest.mark.parametrize(
    "token",
    [
        "RUNNING_NO_SNAPSHOT",
        "SNAPSHOT_STALE",
        "SNAPSHOT_PLAN_MISMATCH",
        "SNAPSHOT_RECORD_INVALID",
        "NO_FROZEN_REFERENCE",
        "FROZEN_MISSING",
        "FROZEN_PERSON_CHANGED",
        "DONE_END_AFTER_NOW",
    ],
)
def test_snapshot_and_frozen_reason_matrix(token: str) -> None:
    inst, plan, base, ctx = execution_case("RUNNING", 10, remaining=0)
    assert validate(inst, plan, base=base, context=ctx).passed
    code = (
        "V8"
        if token in ("NO_FROZEN_REFERENCE", "FROZEN_MISSING")
        else "V11"
        if token == "FROZEN_PERSON_CHANGED"
        else "V10"
    )
    ids: list[str] = ["a"]
    if token == "RUNNING_NO_SNAPSHOT":
        ctx.snapshot = None
    elif token == "SNAPSHOT_STALE":
        assert ctx.snapshot is not None
        ctx.snapshot.as_of = 9
        ids = []
    elif token == "SNAPSHOT_PLAN_MISMATCH":
        assert ctx.snapshot is not None
        ctx.snapshot.plan_id = "wrong"
        ids = []
    elif token == "SNAPSHOT_RECORD_INVALID":
        assert ctx.snapshot is not None
        ctx.snapshot.records[0].planned_end = 9
    elif token == "NO_FROZEN_REFERENCE":
        ctx.snapshot = None
        base = None  # type: ignore[assignment]
    elif token == "FROZEN_MISSING":
        plan.assignments.clear()
    elif token == "FROZEN_PERSON_CHANGED":
        plan.assignments["a"].person_id = "p"
    else:
        inst, plan, base, ctx = execution_case("DONE", 13, actual=12)
    assert reasons(validate(inst, plan, base=base, context=ctx), code, token) == [ids]


@pytest.mark.parametrize(
    "kind,code,token,ids",
    [
        ("task", "V1", "DUPLICATE_TASK_ID", ["a"]),
        ("device", "V1", "DUPLICATE_DEVICE_ID", []),
        ("person", "V7", "DUPLICATE_PERSON_ID", []),
    ],
)
def test_duplicate_ids_after_mutation(kind: str, code: str, token: str, ids: list[str]) -> None:
    inst = instance()
    inst.persons = [Person(id="p")]
    plan = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=4),
            "b": Assignment(task_id="b", device_id="d", start=4, end=8),
        },
    )
    assert not reasons(validate(inst, plan), code, token)
    if kind == "task":
        inst.tasks.append(inst.tasks[0].model_copy(deep=True))
    elif kind == "device":
        inst.devices.append(inst.devices[0].model_copy(deep=True))
    else:
        inst.persons.append(inst.persons[0].model_copy(deep=True))
    report = validate(inst, plan)
    assert reasons(report, code, token) == [ids]
    violation = next(v for v in report.violations if f"reason={token};" in v.detail)
    if kind == "device":
        assert violation.device_id == "d"
    if kind == "person":
        assert "person_id=p;" in violation.detail
    inst.tasks.reverse()
    inst.devices.reverse()
    inst.persons.reverse()
    assert validate(inst, plan) == report


def test_model_construct_invalid_references_and_cycle() -> None:
    inst = instance()
    inst.tasks[0].compatible_devices = []
    inst.precedences = [
        Precedence.model_construct(pred="a", succ="z", lag_min=0, lag_max=None),
        Precedence(pred="a", succ="b"),
        Precedence(pred="b", succ="a"),
    ]
    plan = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=4),
            "b": Assignment(task_id="b", device_id="d", start=4, end=8),
        },
    )
    report = validate(inst, plan)
    assert reasons(report, "V1", "EMPTY_COMPATIBLE_LIST") == [["a"]]
    assert reasons(report, "V3", "PRECEDENCE_UNKNOWN_TASK") == [["a", "z"]]
    assert reasons(report, "V3", "PRECEDENCE_CYCLE") == [["a", "b"]]
    inst.tasks[0].compatible_devices = ["d"]
    inst.precedences = []
    assert validate(inst, plan).passed


def test_wrong_context_and_base_type_rejected() -> None:
    inst = instance()
    plan = Plan(id="p", assignments={})
    with pytest.raises(TypeError):
        validate(inst, plan, base={})  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        validate(inst, plan, context={})  # type: ignore[arg-type]


@pytest.mark.parametrize("status", ["PENDING", "SCHEDULED"])
def test_schedulable_statuses_and_frozen_end(status: str) -> None:
    inst = instance()
    inst.tasks = inst.tasks[:1]
    inst.tasks[0].status = status  # type: ignore[assignment]
    plan = Plan(
        id="p",
        parent_id="base",
        assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=4)},
    )
    base = plan.model_copy(deep=True)
    base.id = "base"
    inst.now = 1
    assert validate(inst, plan, base=base).passed
    inst.tasks[0].duration = 5
    plan.assignments["a"].end = 5
    assert reasons(validate(inst, plan, base=base), "V11", "FROZEN_END_NO_EVIDENCE") == [["a"]]
    plan.assignments.clear()
    assert reasons(validate(inst, plan, base=base), "V8", "FROZEN_MISSING") == [["a"]]


def test_capacity_includes_setup_and_touching_boundary() -> None:
    inst = instance()
    inst.devices[0].capacity = 2
    inst.setups = [SetupRule(device_id="d", task_type="x", slots=1)]
    inst.tasks[0].demand = 2
    plan = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=1, end=5),
            "b": Assignment(task_id="b", device_id="d", start=5, end=9),
        },
    )
    assert reasons(validate(inst, plan), "V9", "CAPACITY_EXCEEDED") == [["a", "b"]]
    plan.assignments["b"] = plan.assignments["b"].model_copy(update={"start": 6, "end": 10})
    assert validate(inst, plan).passed


def test_snapshot_record_base_mismatch() -> None:
    inst, plan, base, ctx = execution_case("RUNNING", 10, remaining=0)
    assert ctx.snapshot is not None
    rec = ctx.snapshot.records[0]
    rec.start = 1
    report = validate(inst, plan, base=base, context=ctx)
    assert reasons(report, "V8", "FROZEN_START_CHANGED") == [["a"]]
    rec.start = 0
    rec.device_id = "z"
    report = validate(inst, plan, base=base, context=ctx)
    assert reasons(report, "V8", "FROZEN_DEVICE_CHANGED") == [["a"]]
    rec.device_id = "d"
    assert validate(inst, plan, base=base, context=ctx).passed


def test_all_inputs_unchanged_and_setup_order_stable() -> None:
    inst, plan, base, ctx = execution_case("RUNNING", 10, remaining=0)
    inst.setups = [
        SetupRule(device_id="d", task_type="x", slots=1),
        SetupRule(device_id="d", task_type="x", slots=2),
    ]
    before = deepcopy(tuple(x.model_dump() for x in (inst, plan, base, ctx)))
    report = validate(inst, plan, base=base, context=ctx, free=set())
    assert tuple(x.model_dump() for x in (inst, plan, base, ctx)) == before
    inst.setups.reverse()
    assert validate(inst, plan, base=base, context=ctx, free=set()) == report


def test_optional_person_still_checked() -> None:
    inst = instance()
    inst.devices.append(Device(id="e", type="x"))
    inst.tasks[1].compatible_devices.append("e")
    inst.persons = [Person(id="p", blocked=[PersonBlockedWindow(start=0, end=1)])]
    plan = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=4, person_id="p"),
            "b": Assignment(task_id="b", device_id="e", start=1, end=5, person_id="p"),
        },
    )
    report = validate(inst, plan)
    assert reasons(report, "V7", "PERSON_UNAVAILABLE") == [["a"]]
    assert reasons(report, "V7", "PERSON_OVERLAP") == [["a", "b"]]
    plan.assignments["a"].person_id = None
    assert validate(inst, plan).passed


# Each listed test exercises the named reason and a case in which it is absent.
REASON_COVERAGE: dict[str, tuple[str, ...]] = {
    "test_v1_reason_matrix": (
        "MISSING_ASSIGNMENT",
        "UNKNOWN_TASK",
        "UNKNOWN_DEVICE",
        "DEVICE_NOT_COMPATIBLE",
        "EMPTY_COMPATIBLE_LIST",
        "UNKNOWN_DEVICE_REF",
        "TASK_NOT_SCHEDULABLE",
    ),
    "test_assignment_key_mismatch_after_mutation": ("ASSIGNMENT_KEY_MISMATCH",),
    "test_duplicate_ids_after_mutation": (
        "DUPLICATE_TASK_ID",
        "DUPLICATE_DEVICE_ID",
        "DUPLICATE_PERSON_ID",
    ),
    "test_exhaustive_overlap_oracle": ("DEVICE_OVERLAP", "PERSON_OVERLAP"),
    "test_running_unbound_windows": ("RUNNING_BLOCK_UNBOUND",),
    "test_invalid_running_bindings": ("RUNNING_BLOCK_BINDING_INVALID",),
    "test_time_and_setup_reason_matrix": (
        "SETUP_RULE_CONFLICT",
        "RELEASE_VIOLATED",
        "START_BEFORE_NOW",
        "HORIZON_EXCEEDED",
        "DURATION_MISMATCH",
    ),
    "test_precedence_reasons_and_boundaries": (
        "PRECEDENCE_MIN_LAG",
        "PRECEDENCE_MAX_LAG",
        "PRECEDENCE_UNKNOWN_TASK",
        "PRECEDENCE_CYCLE",
    ),
    "test_deadline_authorization_matrix": (
        "DEADLINE_EXCEEDED",
        "AUTH_NOT_APPLICABLE",
        "AUTH_EXPIRED",
        "AUTH_FUTURE",
        "AUTH_OUT_OF_SCOPE",
        "AUTH_DUPLICATE",
    ),
    "test_setup_calendar_and_half_open": ("CALENDAR_BLOCKED", "SETUP_BEFORE_ORIGIN"),
    "test_person_skill_and_calendar": (
        "MISSING_PERSON",
        "UNKNOWN_PERSON",
        "SKILL_MISSING",
        "PERSON_UNAVAILABLE",
    ),
    "test_done_history_and_missing_base_as_of": (
        "FROZEN_DEVICE_CHANGED",
        "FROZEN_START_CHANGED",
        "DONE_HISTORY_REWRITTEN",
    ),
    "test_snapshot_and_frozen_reason_matrix": (
        "NO_FROZEN_REFERENCE",
        "FROZEN_MISSING",
        "RUNNING_NO_SNAPSHOT",
        "SNAPSHOT_STALE",
        "SNAPSHOT_PLAN_MISMATCH",
        "SNAPSHOT_RECORD_INVALID",
        "DONE_END_AFTER_NOW",
        "FROZEN_PERSON_CHANGED",
    ),
    "test_exhaustive_capacity_oracle": ("CAPACITY_EXCEEDED", "DEMAND_EXCEEDS_CAPACITY"),
    "test_done_real_completion": ("END_MISMATCH", "DONE_NO_EVIDENCE"),
    "test_neighborhood_reasons": (
        "PARENT_MISMATCH",
        "BASE_REQUIRED",
        "FREE_UNKNOWN_TASK",
        "FREE_CONTAINS_FROZEN",
        "ADDED_NOT_FREE",
        "REMOVED_NOT_FREE",
        "BASE_TASK_UNKNOWN",
        "NONFREE_CHANGED",
    ),
    "test_running_end_evidence_matrix": ("FROZEN_END_NO_EVIDENCE",),
    "test_running_end_evidence_scope": ("FROZEN_END_EVIDENCE_INVALID",),
}


def test_reason_coverage_inventory() -> None:
    expected = set(
        """MISSING_ASSIGNMENT UNKNOWN_TASK UNKNOWN_DEVICE DEVICE_NOT_COMPATIBLE EMPTY_COMPATIBLE_LIST UNKNOWN_DEVICE_REF TASK_NOT_SCHEDULABLE ASSIGNMENT_KEY_MISMATCH DUPLICATE_TASK_ID DUPLICATE_DEVICE_ID DUPLICATE_PERSON_ID DEVICE_OVERLAP RUNNING_BLOCK_UNBOUND RUNNING_BLOCK_BINDING_INVALID SETUP_RULE_CONFLICT PRECEDENCE_MIN_LAG PRECEDENCE_MAX_LAG PRECEDENCE_UNKNOWN_TASK PRECEDENCE_CYCLE RELEASE_VIOLATED START_BEFORE_NOW DEADLINE_EXCEEDED AUTH_NOT_APPLICABLE AUTH_EXPIRED AUTH_FUTURE AUTH_OUT_OF_SCOPE AUTH_DUPLICATE CALENDAR_BLOCKED HORIZON_EXCEEDED SETUP_BEFORE_ORIGIN MISSING_PERSON UNKNOWN_PERSON SKILL_MISSING PERSON_OVERLAP PERSON_UNAVAILABLE FROZEN_DEVICE_CHANGED FROZEN_START_CHANGED NO_FROZEN_REFERENCE FROZEN_MISSING CAPACITY_EXCEEDED DEMAND_EXCEEDS_CAPACITY DURATION_MISMATCH RUNNING_NO_SNAPSHOT SNAPSHOT_STALE SNAPSHOT_PLAN_MISMATCH SNAPSHOT_RECORD_INVALID END_MISMATCH DONE_NO_EVIDENCE DONE_END_AFTER_NOW DONE_HISTORY_REWRITTEN PARENT_MISMATCH BASE_REQUIRED FREE_UNKNOWN_TASK FREE_CONTAINS_FROZEN ADDED_NOT_FREE REMOVED_NOT_FREE BASE_TASK_UNKNOWN NONFREE_CHANGED FROZEN_PERSON_CHANGED FROZEN_END_NO_EVIDENCE FROZEN_END_EVIDENCE_INVALID""".split()
    )
    assert {token for tokens in REASON_COVERAGE.values() for token in tokens} == expected
    assert all(callable(globals()[name]) for name in REASON_COVERAGE)
