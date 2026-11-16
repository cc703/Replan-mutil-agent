from typing import Any

from datetime import datetime, timezone

from scheduler_core.axis import TimeAxis
from scheduler_core.models import Assignment, Device, Instance, Plan, Task
from simulator.engine import Simulator
from simulator.scenarios import Scenario


def test_two_contiguous_tasks_finish_in_order_and_resume() -> None:
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[
            Task(id="a", experiment_id="e", type="x", duration=3, compatible_devices=["d"]),
            Task(id="b", experiment_id="e", type="x", duration=3, compatible_devices=["d"]),
        ],
    )
    plan = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=3),
            "b": Assignment(task_id="b", device_id="d", start=3, end=6),
        },
    )
    scenario = Scenario(duration_sigma=0.0)
    simulator = Simulator(inst, plan, scenario, lambda *_: None, 1)
    simulator.run(3)
    result = simulator.run(7)
    direct = Simulator(inst, plan, scenario, lambda *_: None, 1).run(7)
    assert result.log == direct.log
    assert [t.status for t in result.final_instance.tasks] == ["DONE", "DONE"]


def test_fault_overlaps_setup_and_recovers_to_setup() -> None:
    from scheduler_core.models import DeviceOutage, SetupRule
    from simulator.log import DeviceStateRecord, parse_log

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        setups=[SetupRule(device_id="d", task_type="x", slots=4)],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=2, compatible_devices=["d"])],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=4, end=6)})
    engine = Simulator(inst, plan, Scenario(duration_sigma=0.0, delta_slots=10), lambda *_: None, 1)
    engine.inject(DeviceOutage(device_id="d", start=1, end=3), 1)
    result = engine.run(7)
    transitions = [
        (record.old, record.new)
        for record in parse_log(result.log)
        if isinstance(record, DeviceStateRecord)
    ]
    assert transitions == [
        ("IDLE", "SETUP"),
        ("SETUP", "FAULT"),
        ("FAULT", "SETUP"),
        ("SETUP", "IDLE"),
        ("IDLE", "BUSY"),
        ("BUSY", "IDLE"),
    ]


def test_listener_failure_restores_event_boundary() -> None:
    import pytest

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=2, compatible_devices=["d"])],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=2)})
    engine = Simulator(inst, plan, Scenario(duration_sigma=0.0), lambda *_: None, 1)

    def fail(_change: Any) -> None:
        raise RuntimeError("listener failed")

    engine.add_status_listener(fail)
    with pytest.raises(RuntimeError, match="listener failed"):
        engine.run(1)
    assert engine.instance.tasks[0].status == "SCHEDULED"
    assert engine.device_status("d") == "IDLE"
    engine.listeners.clear()
    assert engine.run(3).final_instance.tasks[0].status == "DONE"


def test_capacity_two_allows_simultaneous_setups() -> None:
    from scheduler_core.models import SetupRule

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x", capacity=2)],
        setups=[SetupRule(device_id="d", task_type="x", slots=2)],
        tasks=[
            Task(id="a", experiment_id="e", type="x", duration=2, compatible_devices=["d"]),
            Task(id="b", experiment_id="e", type="x", duration=2, compatible_devices=["d"]),
        ],
    )
    assignments = {
        tid: Assignment(task_id=tid, device_id="d", start=2, end=4) for tid in ("a", "b")
    }
    result = Simulator(
        inst,
        Plan(id="p", assignments=assignments),
        Scenario(duration_sigma=0.0),
        lambda *_: None,
        1,
    ).run(5)
    assert [task.status for task in result.final_instance.tasks] == ["DONE", "DONE"]


def test_adoption_invalidates_only_changed_task_events() -> None:
    from scheduler_core.models import UrgentInsert
    from simulator.replay import replay

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

    def scheduler(_post: Any, base: Any, _batch: Any) -> Any:
        return Plan(
            id="next",
            parent_id=base.id,
            assignments={
                "a": base.assignments["a"],
                "b": Assignment(task_id="b", device_id="d", start=8, end=10),
                "u": Assignment(task_id="u", device_id="d", start=3, end=5),
            },
        )

    engine = Simulator(inst, plan, Scenario(duration_sigma=0.0), scheduler, 1)
    engine.inject(UrgentInsert(tasks=[urgent]), 2)
    result = engine.run(11)
    assert result.final_plan.id == "next"
    assert result.stale_skipped == 1
    assert result.counters["enqueued"] == 9
    assert [t.status for t in result.final_instance.tasks] == ["DONE", "DONE", "DONE"]
    assert replay(result.log) == result


def test_event_listener_observes_applied_event_and_rolls_back_failure() -> None:
    import pytest

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=2, compatible_devices=["d"])],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=2)})
    engine = Simulator(inst, plan, Scenario(duration_sigma=0.0), lambda *_: None, 1)

    def fail(event: Any) -> None:
        assert event.kind == "TASK_START"
        assert engine.device_status("d") == "BUSY"
        raise RuntimeError("event listener")

    engine.add_event_listener(fail)
    with pytest.raises(RuntimeError, match="event listener"):
        engine.run(1)
    assert engine.device_status("d") == "IDLE"
    assert engine.instance.tasks[0].status == "SCHEDULED"
    engine.event_listeners.clear()
    assert engine.run(3).final_instance.tasks[0].status == "DONE"


def test_replan_while_setup_active_releases_old_reservation() -> None:
    from scheduler_core.models import SetupRule, UrgentInsert

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d1", type="x"), Device(id="d2", type="y")],
        setups=[SetupRule(device_id="d1", task_type="x", slots=4)],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=2, compatible_devices=["d1"])],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d1", start=4, end=6)})
    urgent = Task(id="u", experiment_id="u", type="y", duration=1, compatible_devices=["d2"])

    def scheduler(_inst: Any, base: Plan, _events: Any) -> Plan:
        return Plan(
            id="next",
            parent_id=base.id,
            assignments={
                "a": Assignment(task_id="a", device_id="d1", start=6, end=8),
                "u": Assignment(task_id="u", device_id="d2", start=2, end=3),
            },
        )

    engine = Simulator(inst, plan, Scenario(duration_sigma=0.0), scheduler, 1)
    engine.inject(UrgentInsert(tasks=[urgent]), 1)
    result = engine.run(9)
    assert result.final_plan.id == "next"
    assert [t.status for t in result.final_instance.tasks] == ["DONE", "DONE"]
    assert engine.setup_demand["d1"] == 0
    assert result.metrics["busy_slots"] == {"d1": 2, "d2": 1}


def test_busy_time_counts_concurrent_tasks_once_across_run_cutoffs() -> None:
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x", capacity=2)],
        tasks=[
            Task(id="a", experiment_id="e", type="x", duration=3, compatible_devices=["d"]),
            Task(id="b", experiment_id="e", type="x", duration=5, compatible_devices=["d"]),
        ],
    )
    plan = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=3),
            "b": Assignment(task_id="b", device_id="d", start=1, end=6),
        },
    )
    engine = Simulator(inst, plan, Scenario(duration_sigma=0.0), lambda *_: None, 1)
    assert engine.run(2).metrics["busy_slots"] == {"d": 2}
    assert engine.run(4).metrics["busy_slots"] == {"d": 4}
    assert engine.run(7).metrics["busy_slots"] == {"d": 6}


def test_reentrant_listener_failure_rolls_back_queue_and_history() -> None:
    import pytest
    from scheduler_core.models import DeviceOutage

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=3, compatible_devices=["d"])],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=3)})
    scenario = Scenario(duration_sigma=0.0)
    engine = Simulator(inst, plan, scenario, lambda *_: None, 1)
    entered = False

    def listener(_event: Any) -> None:
        nonlocal entered
        if entered:
            return
        entered = True
        engine.inject(DeviceOutage(device_id="d", start=1, end=2), 1)
        engine.run(2)
        raise RuntimeError("outer listener failure")

    engine.add_event_listener(listener)
    with pytest.raises(RuntimeError, match="outer listener failure"):
        engine.run(4)
    engine.event_listeners.clear()
    result = engine.run(4)
    direct = Simulator(inst, plan, scenario, lambda *_: None, 1).run(4)
    assert result == direct


def test_reentrant_run_advances_outer_cutoff_and_replays() -> None:
    from simulator.replay import replay

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=4, compatible_devices=["d"])],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=4)})
    engine = Simulator(inst, plan, Scenario(duration_sigma=0.0), lambda *_: None, 1)
    entered = False

    def listener(_event: Any) -> None:
        nonlocal entered
        if not entered:
            entered = True
            engine.run(6)

    engine.add_event_listener(listener)
    result = engine.run(3)
    assert engine.clock == result.final_instance.now == 6
    assert result.final_instance.tasks[0].status == "DONE"
    assert replay(result.log) == result
    assert engine.run(7) == Simulator(
        inst, plan, Scenario(duration_sigma=0.0), lambda *_: None, 1
    ).run(7)


def test_listener_removal_rolls_back_for_both_lists_and_nested_runs() -> None:
    import pytest

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=2, compatible_devices=["d"])],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=2)})
    engine = Simulator(inst, plan, Scenario(duration_sigma=0.0), lambda *_: None, 1)
    seen: list[str] = []

    def status(_change: Any) -> None:
        seen.append("status")

    def second(_event: Any) -> None:
        seen.append("second")

    entered = False

    def first(_event: Any) -> None:
        nonlocal entered
        if entered:
            return
        entered = True
        seen.append("first")
        engine.listeners.remove(status)
        engine.event_listeners.remove(second)
        engine.run(3)
        raise RuntimeError("rollback")

    engine.add_status_listener(status)
    engine.add_event_listener(first)
    engine.add_event_listener(second)
    with pytest.raises(RuntimeError, match="rollback"):
        engine.run(1)
    assert engine.listeners == [status]
    assert engine.event_listeners == [first, second]
    assert seen == ["status", "first"]
    engine.event_listeners.remove(first)
    engine.run(1)
    assert seen[-2:] == ["status", "second"]


def test_listener_mutation_keeps_current_notification_snapshot() -> None:
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=2, compatible_devices=["d"])],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=2)})
    engine = Simulator(inst, plan, Scenario(duration_sigma=0.0), lambda *_: None, 1)
    seen: list[str] = []

    def later(_event: Any) -> None:
        seen.append("later")

    def added(_event: Any) -> None:
        seen.append("added")

    def first(_event: Any) -> None:
        seen.append("first")
        engine.event_listeners.remove(later)
        engine.event_listeners.append(added)

    engine.event_listeners.extend([first, later])
    engine.run(1)
    assert seen == ["first", "later"]
    assert engine.event_listeners == [first, added]


def test_listener_replacement_rolls_back_and_stays_transactional() -> None:
    import pytest

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=2, compatible_devices=["d"])],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=2)})
    engine = Simulator(inst, plan, Scenario(duration_sigma=0.0), lambda *_: None, 1)

    def status(_change: Any) -> None:
        pass

    def fail(_event: Any) -> None:
        engine.listeners = []
        engine.event_listeners = []
        engine.event_listeners.append(fail)
        raise RuntimeError("rollback replacement")

    engine.listeners = [status]
    engine.event_listeners = [fail]
    with pytest.raises(RuntimeError, match="rollback replacement"):
        engine.run(1)
    assert engine.listeners == [status]
    assert engine.event_listeners == [fail]
    with pytest.raises(RuntimeError, match="rollback replacement"):
        engine.run(1)
    assert engine.listeners == [status]
    assert engine.event_listeners == [fail]
