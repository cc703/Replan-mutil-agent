from simulator.events import EventKind, SimEvent
from simulator.trigger import TriggerWindow


def test_batch_cooldown_and_abandonment() -> None:
    window = TriggerWindow(delta_slots=1, cooldown_slots=6, max_consecutive_failures=1)
    first = SimEvent(time=2, kind=EventKind.TASK_OVERRUN, task_id="a", seq=2)
    second = SimEvent(time=2, kind=EventKind.TASK_OVERRUN, task_id="b", seq=1)
    assert window.add(first) == 3
    assert window.add(second) == 3
    assert [event.task_id for event in window.batch()] == ["b", "a"]
    window.called(3)
    assert window.failed(3) == 9
    window.called(9)
    assert window.failed(9) is None
    assert window.batch() == []
    assert window.add(SimEvent(time=10, kind=EventKind.TASK_OVERRUN, task_id="c")) == 15


def test_periodic_triggers_and_retry_abandonment() -> None:
    from datetime import datetime, timezone
    from scheduler_core.axis import TimeAxis
    from scheduler_core.models import Assignment, Device, Instance, Plan, Task
    from simulator.engine import Simulator
    from simulator.log import ReplanAbandoned, parse_log
    from simulator.scenarios import Scenario

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=1, compatible_devices=["d"])],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=1)})
    scenario = Scenario(
        duration_sigma=0.0, periodic_slots=4, cooldown_slots=2, max_consecutive_failures=1
    )
    result = Simulator(inst, plan, scenario, lambda *_: None, 1).run(8)
    assert result.counters["replan_calls"] == 2
    assert sum(isinstance(record, ReplanAbandoned) for record in parse_log(result.log)) == 1


def test_scheduler_exception_preserves_flush_for_resume_and_replay() -> None:
    from datetime import datetime, timezone
    from typing import Any

    import pytest
    from scheduler_core.axis import TimeAxis
    from scheduler_core.models import Assignment, Device, DeviceOutage, Instance, Plan, Task
    from simulator.engine import Simulator
    from simulator.replay import replay
    from simulator.scenarios import Scenario

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=6, compatible_devices=["d"])],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=6)})
    calls = 0

    def fail_once(_inst: Any, _base: Any, _events: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary scheduler failure")
        return None

    scenario = Scenario(duration_sigma=0.0)
    interrupted = Simulator(inst, plan, scenario, fail_once, 1)
    interrupted.inject(DeviceOutage(device_id="d", start=2, end=4), 2)
    with pytest.raises(RuntimeError, match="temporary scheduler failure"):
        interrupted.run(5)
    assert interrupted.window.due == 3
    assert len(interrupted.window.events) == 1
    result = interrupted.run(10)
    assert calls == 3  # failed call, resumed call, then cooldown retry
    direct = Simulator(inst, plan, scenario, lambda *_: None, 1)
    direct.inject(DeviceOutage(device_id="d", start=2, end=4), 2)
    assert result == direct.run(10)
    assert replay(result.log) == result


def test_injection_after_callback_failure_obeys_same_slot_priority() -> None:
    from datetime import datetime, timezone
    from typing import Any
    import pytest
    from scheduler_core.axis import TimeAxis
    from scheduler_core.models import Assignment, Device, DeviceOutage, Instance, Plan, Task
    from simulator.engine import Simulator
    from simulator.replay import replay
    from simulator.scenarios import Scenario

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d1", type="x"), Device(id="d2", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=6, compatible_devices=["d1"])],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d1", start=0, end=6)})
    seen: list[list[SimEvent]] = []

    def scheduler(_inst: Any, _plan: Any, batch: list[SimEvent]) -> None:
        seen.append(batch)
        if len(seen) == 1:
            raise RuntimeError("failure")
        return None

    engine = Simulator(inst, plan, Scenario(duration_sigma=0.0), scheduler, 1)
    engine.inject(DeviceOutage(device_id="d1", start=2, end=4), 2)
    with pytest.raises(RuntimeError):
        engine.run(5)
    engine.inject(DeviceOutage(device_id="d2", start=3, end=4), 3)
    result = engine.run(5)
    assert [event.device_id for event in seen[1]] == ["d1", "d2"]
    assert replay(result.log) == result
