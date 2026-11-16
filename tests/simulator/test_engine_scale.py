from datetime import datetime, timezone

from scheduler_core.axis import TimeAxis
from scheduler_core.models import Assignment, Device, Instance, Plan, Task
from simulator.engine import Simulator
from simulator.scenarios import Scenario


def test_sparse_large_horizon_does_not_step_through_slots() -> None:
    inst = Instance(
        axis=TimeAxis(
            t0=datetime(2026, 1, 1, tzinfo=timezone.utc), slot_minutes=1, horizon_slots=10**9
        ),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=1, compatible_devices=["d"])],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=1, end=2)})
    result = Simulator(inst, plan, Scenario(duration_sigma=0.0), lambda *_: None, 1).run(10**9)
    assert result.counters["events"] == 2
    assert result.final_instance.tasks[0].status == "DONE"


def test_two_thousand_tasks_enqueue_linearly() -> None:
    devices = [Device(id=f"d{i}", type="x") for i in range(50)]
    tasks = [
        Task(id=f"t{i}", experiment_id="e", type="x", duration=1, compatible_devices=[f"d{i % 50}"])
        for i in range(2000)
    ]
    assignments = {
        task.id: Assignment(task_id=task.id, device_id=f"d{i % 50}", start=i // 50, end=i // 50 + 1)
        for i, task in enumerate(tasks)
    }
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=100),
        devices=devices,
        tasks=tasks,
    )
    result = Simulator(
        inst,
        Plan(id="p", assignments=assignments),
        Scenario(duration_sigma=0.0),
        lambda *_: None,
        1,
    ).run(42)
    assert result.counters["events"] == 4000
    assert result.counters["enqueued"] == 4000
    assert all(task.status == "DONE" for task in result.final_instance.tasks)


def test_two_thousand_tasks_with_single_fault_preserves_linear_queue() -> None:
    from scheduler_core.models import DeviceOutage

    devices = [Device(id=f"d{i}", type="x") for i in range(50)]
    tasks = [
        Task(id=f"t{i}", experiment_id="e", type="x", duration=1, compatible_devices=[f"d{i % 50}"])
        for i in range(2000)
    ]
    assignments = {
        task.id: Assignment(task_id=task.id, device_id=f"d{i % 50}", start=i // 50, end=i // 50 + 1)
        for i, task in enumerate(tasks)
    }
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=100),
        devices=devices,
        tasks=tasks,
    )
    engine = Simulator(
        inst,
        Plan(id="p", assignments=assignments),
        Scenario(duration_sigma=0.0, delta_slots=1),
        lambda *_: None,
        1,
    )
    engine.inject(DeviceOutage(device_id="d0", start=10, end=12), 10)
    result = engine.run(42)
    assert result.counters["enqueued"] < 4100
    assert result.counters["replan_calls"] > 0


def test_resource_checks_do_not_scan_devices_or_setup_set_per_event() -> None:
    from typing import Iterator
    from scheduler_core.models import SetupRule

    class CountedDevices(list[Device]):
        iterations = 0

        def __iter__(self) -> Iterator[Device]:
            self.iterations += 1
            return super().__iter__()

    class NoIterationSet(set[str]):
        def __iter__(self) -> Iterator[str]:
            raise AssertionError("per-event setup scan")

    devices = [Device(id=f"d{i}", type="x") for i in range(50)]
    tasks = [
        Task(id=f"t{i}", experiment_id="e", type="x", duration=1, compatible_devices=[f"d{i}"])
        for i in range(50)
    ]
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=10),
        devices=devices,
        tasks=tasks,
        setups=[SetupRule(device_id=d.id, task_type="x", slots=1) for d in devices],
    )
    plan = Plan(
        id="p",
        assignments={
            t.id: Assignment(task_id=t.id, device_id=t.compatible_devices[0], start=1, end=2)
            for t in tasks
        },
    )
    engine = Simulator(inst, plan, Scenario(duration_sigma=0.0), lambda *_: None, 1)
    measured = CountedDevices(engine.instance.devices)
    engine.instance.devices = measured
    engine.setups = NoIterationSet()
    result = engine.run(3)
    assert result.counters["events"] == 200
    assert measured.iterations < 10
    assert all(value == 1 for value in result.metrics["busy_slots"].values())
