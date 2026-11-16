from typing import Any

from datetime import datetime, timezone

from scheduler_core.axis import TimeAxis
from scheduler_core.models import Assignment, Device, DeviceOutage, Instance, Plan, Task
from simulator.engine import Simulator
from simulator.scenarios import Scenario


def test_fault_interrupts_and_creates_remaining_copy() -> None:
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[
            Task(
                id="a",
                experiment_id="e",
                type="x",
                duration=6,
                compatible_devices=["d"],
                preemptible=True,
            )
        ],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=6)})
    seen = []

    def scheduler(post: Any, _plan: Any, _events: Any) -> Any:
        seen.append(post)
        return None

    simulator = Simulator(inst, plan, Scenario(duration_sigma=0.0), scheduler, 3)
    simulator.inject(DeviceOutage(device_id="d", start=2, end=4), 2)
    result = simulator.run(4)
    assert [(t.id, t.status, t.duration) for t in result.final_instance.tasks] == [
        ("a", "INTERRUPTED", 6),
        ("a~r1", "PENDING", 4),
    ]
    assert seen[0].blocked[-1].kind == "FAULT"


def test_fault_at_task_end_does_not_interrupt() -> None:
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=3, compatible_devices=["d"])],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=3)})
    engine = Simulator(inst, plan, Scenario(duration_sigma=0.0), lambda *_: None, 1)
    engine.inject(DeviceOutage(device_id="d", start=3, end=5), 3)
    result = engine.run(4)
    assert [t.status for t in result.final_instance.tasks] == ["DONE"]


def test_repeated_interruptions_generate_unique_ids() -> None:
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[
            Task(
                id="a",
                experiment_id="e",
                type="x",
                duration=8,
                compatible_devices=["d"],
                preemptible=True,
            )
        ],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=8)})

    def scheduler(post: Any, base: Any, _batch: Any) -> Any:
        assignments = {
            tid: a
            for tid, a in base.assignments.items()
            if next(t for t in post.tasks if t.id == tid).status != "INTERRUPTED"
        }
        for task in post.tasks:
            if task.status == "PENDING":
                start = max([post.now] + [w.end for w in post.blocked if w.device_id == "d"])
                assignments[task.id] = Assignment(
                    task_id=task.id, device_id="d", start=start, end=start + task.duration
                )
        return Plan(id=base.id + "x", parent_id=base.id, assignments=assignments)

    engine = Simulator(inst, plan, Scenario(duration_sigma=0.0), scheduler, 1)
    engine.inject(DeviceOutage(device_id="d", start=2, end=4), 2)
    engine.inject(DeviceOutage(device_id="d", start=5, end=7), 5)
    result = engine.run(20)
    assert [(t.id, t.status, t.duration) for t in result.final_instance.tasks] == [
        ("a", "INTERRUPTED", 8),
        ("a~r1", "INTERRUPTED", 6),
        ("a~r2", "DONE", 5),
    ]


def test_maintenance_interrupts_overrunning_task() -> None:
    from scheduler_core.models import BlockedWindow

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        blocked=[BlockedWindow(device_id="d", start=5, end=7, kind="MAINT")],
        tasks=[
            Task(
                id="a",
                experiment_id="e",
                type="x",
                duration=4,
                compatible_devices=["d"],
                preemptible=True,
            )
        ],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=4)})
    scenario = Scenario(duration_sigma=0.0, duration_factor_min=1.5, duration_factor_max=1.5)
    engine = Simulator(inst, plan, scenario, lambda *_: None, 1)
    result = engine.run(6)
    assert [(t.id, t.status, t.duration) for t in result.final_instance.tasks] == [
        ("a", "INTERRUPTED", 4),
        ("a~r1", "PENDING", 1),
    ]
    assert engine.device_status("d") == "MAINTENANCE"


def test_fault_interrupts_both_tasks_on_capacity_two_device() -> None:
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x", capacity=2)],
        tasks=[
            Task(id=tid, experiment_id="e", type="x", duration=6, compatible_devices=["d"])
            for tid in ("a", "b")
        ],
    )
    plan = Plan(
        id="p",
        assignments={
            tid: Assignment(task_id=tid, device_id="d", start=0, end=6) for tid in ("a", "b")
        },
    )
    engine = Simulator(inst, plan, Scenario(duration_sigma=0.0), lambda *_: None, 1)
    engine.inject(DeviceOutage(device_id="d", start=2, end=4), 2)
    result = engine.run(3)
    assert [(t.id, t.status) for t in result.final_instance.tasks] == [
        ("a", "INTERRUPTED"),
        ("b", "INTERRUPTED"),
        ("a~r1", "PENDING"),
        ("b~r1", "PENDING"),
    ]
