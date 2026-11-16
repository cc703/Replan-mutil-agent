from datetime import datetime, timezone
from typing import Any

from scheduler_core.axis import TimeAxis
from scheduler_core.models import Assignment, Device, Instance, Plan, Task
from simulator.engine import Simulator
from simulator.replay import replay
from simulator.scenarios import Scenario


def test_blocked_task_can_replan_after_default_delay_and_replay() -> None:
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[
            Task(id=tid, experiment_id="e", type="x", duration=duration, compatible_devices=["d"])
            for tid, duration in (("a", 3), ("b", 2))
        ],
    )
    plan = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=3),
            "b": Assignment(task_id="b", device_id="d", start=3, end=5),
        },
    )
    calls = []

    def schedule(post: Any, base: Any, batch: Any, context: Any) -> Plan:
        calls.append((post.now, context.model_copy(deep=True)))
        context.not_started.clear()  # Callback cannot alter the gate snapshot.
        return Plan(
            id="p2",
            parent_id=base.id,
            assignments={
                "a": Assignment(task_id="a", device_id="d", start=0, end=5),
                "b": Assignment(task_id="b", device_id="d", start=5, end=7),
            },
        )

    scenario = Scenario(duration_sigma=0.0, duration_factor_min=1.5, duration_factor_max=1.5)
    engine = Simulator(inst, plan, scenario, None, 1, scheduler_with_context=schedule)
    result = engine.run(10)
    assert calls[0][0] == 4
    assert calls[0][1].not_started[0].task_id == "b"
    assert result.final_plan.id == "p2.ov1"
    assert result.final_instance.tasks[1].status == "DONE"
    assert replay(result.log) == result


def test_failed_attempt_retains_blocked_fact_for_retry() -> None:
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[
            Task(id=tid, experiment_id="e", type="x", duration=duration, compatible_devices=["d"])
            for tid, duration in (("a", 3), ("b", 2))
        ],
    )
    plan = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=3),
            "b": Assignment(task_id="b", device_id="d", start=3, end=5),
        },
    )
    seen = []

    def schedule(post: Any, base: Any, batch: Any, context: Any) -> Plan | None:
        seen.append(context.not_started[0].event_id)
        if len(seen) == 1:
            return None
        return Plan(
            id="p2",
            parent_id=base.id,
            assignments={
                "a": Assignment(task_id="a", device_id="d", start=0, end=5),
                "b": Assignment(task_id="b", device_id="d", start=5, end=7),
            },
        )

    scenario = Scenario(
        duration_sigma=0.0, duration_factor_min=1.5, duration_factor_max=1.5, cooldown_slots=1
    )
    result = Simulator(inst, plan, scenario, None, 1, scheduler_with_context=schedule).run(10)
    assert len(seen) == 2 and seen[0] == seen[1]
    assert result.final_instance.tasks[1].status == "DONE"
    assert replay(result.log) == result


def test_status_listener_reentrant_run_completes_and_replays() -> None:
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=2, compatible_devices=["d"])],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=2)})
    scenario = Scenario(duration_sigma=0.0)
    engine = Simulator(inst, plan, scenario, lambda *_: None, 1)
    changes = []

    def listener(change: Any) -> None:
        changes.append(change)
        if len(changes) == 1:
            engine.run(5)

    engine.add_status_listener(listener)
    result = engine.run(1)
    assert result.final_instance.tasks[0].status == "DONE"
    assert engine.clock == 5
    assert len(changes) == 2
    assert replay(result.log) == result


def test_status_listener_reentrant_failure_restores_event() -> None:
    import pytest

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=2, compatible_devices=["d"])],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=2)})
    scenario = Scenario(duration_sigma=0.0)
    engine = Simulator(inst, plan, scenario, lambda *_: None, 1)
    entered = False

    def listener(_change: Any) -> None:
        nonlocal entered
        if not entered:
            entered = True
            engine.run(5)
            raise RuntimeError("outer failure")

    engine.add_status_listener(listener)
    with pytest.raises(RuntimeError, match="outer failure"):
        engine.run(1)
    engine.listeners.clear()
    result = engine.run(5)
    baseline = Simulator(inst, plan, scenario, lambda *_: None, 1).run(5)
    assert result == baseline


def test_person_busy_during_setup_does_not_block_preparation() -> None:
    from scheduler_core.models import Person, SetupRule
    from simulator.log import StartBlocked, DeviceStateRecord, parse_log

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=20),
        devices=[Device(id="d1", type="x"), Device(id="d2", type="y")],
        persons=[Person(id="p", skills={"s"})],
        tasks=[
            Task(
                id="a",
                experiment_id="e",
                type="x",
                duration=3,
                compatible_devices=["d1"],
                required_skills={"s"},
            ),
            Task(
                id="b",
                experiment_id="e",
                type="y",
                duration=2,
                compatible_devices=["d2"],
                required_skills={"s"},
            ),
        ],
        setups=[SetupRule(device_id="d2", task_type="y", slots=3)],
    )
    plan = Plan(
        id="p0",
        assignments={
            "a": Assignment(task_id="a", device_id="d1", person_id="p", start=0, end=3),
            "b": Assignment(task_id="b", device_id="d2", person_id="p", start=4, end=6),
        },
    )
    result = Simulator(inst, plan, Scenario(duration_sigma=0.0), lambda *_: None, 1).run(8)
    entries = parse_log(result.log)
    assert not any(isinstance(item, StartBlocked) for item in entries)
    assert any(
        isinstance(item, DeviceStateRecord)
        and item.device_id == "d2"
        and item.new == "SETUP"
        and item.time == 1
        for item in entries
    )
    assert result.final_instance.tasks[1].status == "DONE"
    assert replay(result.log) == result
