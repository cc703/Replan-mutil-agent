from datetime import datetime, timezone

from scheduler_core.axis import TimeAxis
from scheduler_core.models import Assignment, Device, DeviceOutage, Instance, Plan, Task
from simulator.engine import Simulator
from simulator.scenarios import Scenario
import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "reference_stepper", Path(__file__).with_name("reference_stepper.py")
)
assert _spec is not None and _spec.loader is not None
_reference = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _reference
_spec.loader.exec_module(_reference)
ReferenceTask = _reference.ReferenceTask
step = _reference.step


def test_reference_for_one_hundred_fault_timings() -> None:
    for case in range(100):
        start = case % 4
        duration = 1 + case % 5
        fault_start = 1 + (case * 7) % 9
        fault_end = fault_start + 2
        cutoff = 12
        inst = Instance(
            axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
            devices=[Device(id="d", type="x")],
            tasks=[
                Task(
                    id="a", experiment_id="e", type="x", duration=duration, compatible_devices=["d"]
                )
            ],
        )
        plan = Plan(
            id="p",
            assignments={
                "a": Assignment(task_id="a", device_id="d", start=start, end=start + duration)
            },
        )
        simulator = Simulator(
            inst, plan, Scenario(duration_sigma=0.0, delta_slots=20), lambda *_: None, 1
        )
        simulator.inject(DeviceOutage(device_id="d", start=fault_start, end=fault_end), fault_start)
        actual_states = []
        for clock in range(1, cutoff + 1):
            result = simulator.run(clock)
            actual_states.append(simulator.device_status("d"))
        complete, interrupted, states = step(
            [ReferenceTask("a", start, duration)], 1, [(fault_start, fault_end)], cutoff
        )
        assert actual_states == states, case
        assert (result.final_instance.tasks[0].status == "DONE") == ("a" in complete), case
        assert (result.final_instance.tasks[0].status == "INTERRUPTED") == ("a" in interrupted), (
            case
        )


def test_reference_capacity_and_setup_cases() -> None:
    from scheduler_core.models import SetupRule

    for duration_a in range(1, 5):
        for duration_b in range(1, 5):
            for fault_start in range(1, 6):
                start = 3
                tasks = [
                    ReferenceTask("a", start, duration_a, setup=2),
                    ReferenceTask("b", start, duration_b, setup=2),
                ]
                inst = Instance(
                    axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=20),
                    devices=[Device(id="d", type="x", capacity=2)],
                    setups=[SetupRule(device_id="d", task_type="x", slots=2)],
                    tasks=[
                        Task(
                            id=t.id,
                            experiment_id="e",
                            type="x",
                            duration=t.actual_duration,
                            compatible_devices=["d"],
                        )
                        for t in tasks
                    ],
                )
                plan = Plan(
                    id="p",
                    assignments={
                        t.id: Assignment(
                            task_id=t.id,
                            device_id="d",
                            start=t.start,
                            end=t.start + t.actual_duration,
                        )
                        for t in tasks
                    },
                )
                engine = Simulator(
                    inst, plan, Scenario(duration_sigma=0.0, delta_slots=15), lambda *_: None, 1
                )
                engine.inject(
                    DeviceOutage(device_id="d", start=fault_start, end=fault_start + 1), fault_start
                )
                actual = []
                for clock in range(1, 11):
                    result = engine.run(clock)
                    actual.append(engine.device_status("d"))
                complete, interrupted, expected = step(
                    tasks, 2, [(fault_start, fault_start + 1)], 10
                )
                assert actual == expected, (duration_a, duration_b, fault_start)
                assert {t.id for t in result.final_instance.tasks if t.status == "DONE"} == set(
                    complete
                )
                assert {
                    t.id for t in result.final_instance.tasks if t.status == "INTERRUPTED"
                } == interrupted


def test_reference_early_and_overrun_execution() -> None:
    for factor in (0.5, 1.5):
        for duration in range(1, 7):
            for start in range(3):
                actual_duration = max(1, int(duration * factor + 0.5))
                reference_task = ReferenceTask("a", start, actual_duration)
                inst = Instance(
                    axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
                    devices=[Device(id="d", type="x")],
                    tasks=[
                        Task(
                            id="a",
                            experiment_id="e",
                            type="x",
                            duration=duration,
                            compatible_devices=["d"],
                        )
                    ],
                )
                plan = Plan(
                    id="p",
                    assignments={
                        "a": Assignment(
                            task_id="a", device_id="d", start=start, end=start + duration
                        )
                    },
                )
                scenario = Scenario(
                    duration_sigma=0.0, duration_factor_min=factor, duration_factor_max=factor
                )
                engine = Simulator(inst, plan, scenario, lambda *_: None, 1)
                actual_states = []
                for clock in range(1, 15):
                    result = engine.run(clock)
                    actual_states.append(engine.device_status("d"))
                complete, interrupted, expected_states = step([reference_task], 1, [], 14)
                assert actual_states == expected_states, (factor, duration, start)
                assert "a" in complete and not interrupted
                assert result.final_instance.tasks[0].status == "DONE"


def test_reference_scripted_replan_with_moved_task() -> None:
    from typing import Any
    from scheduler_core.models import UrgentInsert
    from simulator.log import TaskStateRecord, parse_log

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[
            Task(id="a", experiment_id="e", type="x", duration=2, compatible_devices=["d"]),
            Task(id="b", experiment_id="e", type="x", duration=2, compatible_devices=["d"]),
        ],
    )
    plan = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=2),
            "b": Assignment(task_id="b", device_id="d", start=5, end=7),
        },
    )
    urgent = Task(id="u", experiment_id="u", type="x", duration=2, compatible_devices=["d"])

    def schedule(_inst: Any, base: Plan, _events: Any) -> Plan:
        return Plan(
            id="next",
            parent_id=base.id,
            assignments={
                "a": base.assignments["a"],
                "b": Assignment(task_id="b", device_id="d", start=8, end=10),
                "u": Assignment(task_id="u", device_id="d", start=3, end=5),
            },
        )

    engine = Simulator(inst, plan, Scenario(duration_sigma=0.0), schedule, 1)
    engine.inject(UrgentInsert(tasks=[urgent]), 2)
    states = []
    for time in range(1, 12):
        result = engine.run(time)
        states.append(engine.device_status("d"))
    reference_tasks = [ReferenceTask("a", 0, 2), ReferenceTask("b", 5, 2), ReferenceTask("u", 3, 2)]
    complete, interrupted, expected = step(reference_tasks, 1, [], 11, {3: {"b": 8}})
    assert states == expected
    assert complete == {"a": (0, 2), "u": (3, 5), "b": (8, 10)}
    observed = {
        record.task_id: (record.actual_start, record.actual_end)
        for record in parse_log(result.log)
        if isinstance(record, TaskStateRecord) and record.new == "DONE"
    }
    assert observed == complete
    assert not interrupted
    assert all(t.status == "DONE" for t in result.final_instance.tasks)
