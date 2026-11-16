from typing import Any

from datetime import datetime, timezone

from scheduler_core.axis import TimeAxis
from scheduler_core.models import Assignment, Device, Instance, Plan, Task
from simulator.engine import Simulator
from simulator.replay import replay
from simulator.scenarios import Scenario


def test_replay_uses_recorded_sample(monkeypatch: Any) -> None:
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=3, compatible_devices=["d"])],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=3)})
    result = Simulator(inst, plan, Scenario(duration_sigma=0.0), lambda *_: None, 1).run(5)

    def fail(*_args: Any) -> None:
        raise AssertionError("sample called during replay")

    monkeypatch.setattr("simulator.runtime.actual_duration", fail)
    assert replay(result.log) == result


def test_generated_future_event_replay_has_no_random_sampling(monkeypatch: Any) -> None:
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=100),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=3, compatible_devices=["d"])],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=3)})
    scenario = Scenario(duration_sigma=0.0, fault_enabled=True, mtbf_slots=20.0)
    result = Simulator(inst, plan, scenario, lambda *_: None, 12).run(5)

    def fail(*_args: Any) -> None:
        raise AssertionError("random sampling during exact replay")

    monkeypatch.setattr("simulator.runtime.actual_duration", fail)
    monkeypatch.setattr("simulator.engine.next_fault_gap", fail)
    monkeypatch.setattr("simulator.engine.repair_duration", fail)
    assert replay(result.log) == result


def test_replay_rejected_plan_and_injected_fault() -> None:
    from scheduler_core.models import DeviceOutage

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=6, compatible_devices=["d"])],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=6)})

    def invalid(_inst: Any, original: Any, _events: Any) -> Any:
        return original.model_copy(update={"id": "bad", "parent_id": "wrong"})

    engine = Simulator(inst, plan, Scenario(duration_sigma=0.0), invalid, 1)
    engine.inject(DeviceOutage(device_id="d", start=2, end=4), 2)
    result = engine.run(5)
    assert replay(result.log) == result


def test_paired_replay_keeps_external_and_duration_streams() -> None:
    from simulator.log import DeviceFault, DurationSampled, parse_log

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=100),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=3, compatible_devices=["d"])],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=3)})
    scenario = Scenario(duration_sigma=0.0, fault_enabled=True, mtbf_slots=10.0)
    result = Simulator(inst, plan, scenario, lambda *_: None, 12).run(25)
    assert replay(result.log) == result

    def rejected(_inst: Any, base: Any, _batch: Any) -> Any:
        return base.model_copy(update={"id": "bad", "parent_id": "wrong"})

    paired = replay(result.log, scheduler=rejected)

    def values(data: bytes) -> list[Any]:
        return [
            (r.kind, r.time, getattr(r, "actual", None), getattr(r, "end", None))
            for r in parse_log(data)
            if isinstance(r, (DeviceFault, DurationSampled))
        ]

    assert values(result.log) == values(paired.log)


def test_enabling_urgent_does_not_change_generated_faults() -> None:
    from simulator.log import DeviceFault, parse_log

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=100),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=2, compatible_devices=["d"])],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=2)})
    base = Scenario(duration_sigma=0.0, fault_enabled=True, mtbf_slots=10.0)
    enabled = base.model_copy(update={"urgent_enabled": True, "urgent_rate_per_day": 20.0})
    first = Simulator(inst, plan, base, lambda *_: None, 5).run(60)
    second = Simulator(inst, plan, enabled, lambda *_: None, 5).run(60)

    def faults(data: bytes) -> list[Any]:
        return [(r.time, r.end) for r in parse_log(data) if isinstance(r, DeviceFault)]

    assert faults(first.log) == faults(second.log)


def test_replay_external_events_are_indexed_once() -> None:
    from typing import Iterator
    from simulator.log import DurationSampled, SimEventRecord, parse_log

    class SinglePass(list[SimEventRecord]):
        calls = 0

        def __iter__(self) -> Iterator[SimEventRecord]:
            self.calls += 1
            if self.calls > 1:
                raise AssertionError("replay log rescanned")
            return super().__iter__()

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=100),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=3, compatible_devices=["d"])],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=3)})
    scenario = Scenario(duration_sigma=0.0, fault_enabled=True, mtbf_slots=5.0)
    original = Simulator(inst, plan, scenario, lambda *_: None, 12).run(40)
    entries = parse_log(original.log)
    replay_engine = Simulator(
        inst, plan, scenario, lambda *_: None, 12, replay_external=SinglePass(entries)
    )
    replay_engine.replay_samples = {
        (r.task_id, r.attempt): r.actual for r in entries if isinstance(r, DurationSampled)
    }
    replay_engine.replay_exact = True
    assert replay_engine.run(40) == original
