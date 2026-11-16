from datetime import datetime, timezone

from scheduler_core.axis import TimeAxis
from scheduler_core.models import Device, DeviceOutage, Instance, Precedence, Task, UrgentInsert
from simulator.runtime import apply_outage, apply_urgent, interrupt_task


def test_interruption_preserves_history_and_reconnects_dependencies() -> None:
    task = Task(
        id="a",
        experiment_id="e",
        type="x",
        duration=10,
        compatible_devices=["d"],
        status="RUNNING",
        preemptible=True,
    )
    successor = Task(id="b", experiment_id="e", type="x", duration=1, compatible_devices=["d"])
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=100),
        devices=[Device(id="d", type="x")],
        tasks=[task, successor],
        precedences=[Precedence(pred="a", succ="b")],
    )
    updated, restart = interrupt_task(inst, "a", 4, 3)
    assert inst.tasks[0].status == "RUNNING"
    assert updated.tasks[0].status == "INTERRUPTED"
    assert (restart.id, restart.duration, restart.release) == ("a~r1", 7, 4)
    assert {(edge.pred, edge.succ) for edge in updated.precedences} == {("a", "b"), ("a~r1", "b")}
    fault = apply_outage(updated, DeviceOutage(device_id="d", start=4, end=8))
    assert fault.blocked[-1].kind == "FAULT"
    urgent = Task(id="u", experiment_id="u", type="x", duration=1, compatible_devices=["d"])
    arrived = apply_urgent(fault, UrgentInsert(tasks=[urgent]), 5)
    assert arrived.tasks[-1].release == 5
    assert not inst.blocked


def test_test_greedy_scheduler_respects_constraints_and_validates() -> None:
    import runpy
    from pathlib import Path
    from scheduler_core.models import Assignment, Person, PersonBlockedWindow, Plan, SetupRule

    helper = runpy.run_path(str(Path(__file__).with_name("stub_schedulers.py")))["greedy_schedule"]
    running = Task(
        id="a", experiment_id="e", type="x", duration=3, status="RUNNING", compatible_devices=["d"]
    )
    pending = Task(
        id="b",
        experiment_id="e",
        type="x",
        duration=2,
        release=2,
        compatible_devices=["d"],
        required_skills={"trained"},
    )
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=20),
        now=1,
        devices=[Device(id="d", type="x", capacity=2)],
        tasks=[running, pending],
        precedences=[Precedence(pred="a", succ="b", lag_min=1, lag_max=3)],
        setups=[SetupRule(device_id="d", task_type="x", slots=1)],
        persons=[Person(id="p", skills={"trained"}, blocked=[PersonBlockedWindow(start=1, end=3)])],
    )
    base = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=3)})
    candidate = helper(inst, base, [])
    assert candidate is not None
    assert candidate.assignments["a"] == base.assignments["a"]
    assert (
        candidate.assignments["b"].start,
        candidate.assignments["b"].end,
        candidate.assignments["b"].person_id,
    ) == (4, 6, "p")


def test_window_index_matches_interval_scan_after_incremental_insertions() -> None:
    from simulator.runtime import WindowIndex

    intervals = [(i * 7 % 103, i * 7 % 103 + 1 + i % 11) for i in range(200)]
    index = WindowIndex([])
    added = []
    for begin, end in intervals:
        index.add(begin, end)
        added.append((begin, end))
        for query_start in (0, 20, 50, 90, 110):
            query_end = query_start + 3
            assert index.overlaps(query_start, query_end) == any(
                start < query_end and query_start < stop for start, stop in added
            )
    assert index.root is not None
    assert index.root.height <= 16


def test_test_greedy_scheduler_enforces_setup_capacity_and_blocked_windows() -> None:
    import runpy
    from pathlib import Path
    from scheduler_core.models import BlockedWindow, Plan, SetupRule
    from scheduler_core.validate import validate

    helper = runpy.run_path(str(Path(__file__).with_name("stub_schedulers.py")))["greedy_schedule"]
    tasks = [
        Task(
            id=tid,
            experiment_id="e",
            type="x",
            duration=2,
            demand=2,
            release=1,
            compatible_devices=["d"],
        )
        for tid in ("a", "b")
    ]
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=20),
        devices=[Device(id="d", type="x", capacity=2)],
        tasks=tasks,
        setups=[SetupRule(device_id="d", task_type="x", slots=1)],
        blocked=[BlockedWindow(device_id="d", start=0, end=2, kind="CLOSED")],
    )
    base = Plan(id="p", assignments={})
    candidate = helper(inst, base, [])
    assert candidate is not None
    assert (candidate.assignments["a"].start, candidate.assignments["a"].end) == (3, 5)
    assert (candidate.assignments["b"].start, candidate.assignments["b"].end) == (6, 8)
    assert validate(inst, candidate, base=base).passed


def test_test_greedy_scheduler_respects_reported_frozen_overrun() -> None:
    import runpy
    from pathlib import Path
    from scheduler_core.models import Assignment, Plan, TaskOverrun
    from simulator.events import EventKind, SimEvent

    helper = runpy.run_path(str(Path(__file__).with_name("stub_schedulers.py")))["greedy_schedule"]
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=20),
        now=4,
        devices=[Device(id="d", type="x")],
        tasks=[
            Task(
                id="a",
                experiment_id="e",
                type="x",
                duration=3,
                status="RUNNING",
                compatible_devices=["d"],
            ),
            Task(
                id="b",
                experiment_id="e",
                type="x",
                duration=2,
                status="SCHEDULED",
                compatible_devices=["d"],
            ),
        ],
    )
    base = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=3),
            "b": Assignment(task_id="b", device_id="d", start=4, end=6),
        },
    )
    event = SimEvent(
        time=3,
        kind=EventKind.TASK_OVERRUN,
        task_id="a",
        payload=TaskOverrun(task_id="a", new_end=5),
    )
    result = helper(inst, base, [event])
    assert result is not None
    assert result.assignments["a"].end == 5
    assert result.assignments["b"].start == 5
