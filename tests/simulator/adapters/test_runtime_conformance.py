from datetime import datetime, timezone

import pytest
from scheduler_core.axis import TimeAxis
from scheduler_core.models import (
    Assignment,
    BlockedWindow,
    Device,
    DeviceOutage,
    Instance,
    Plan,
    Task,
    TaskOverrun,
)
from simulator.adapters import (
    AdapterCallbackError,
    CalendarWindow,
    ControllableAdapter,
    DeviceAdapter,
    ManualAdapter,
    RuntimeView,
    SimulatedAdapter,
)
from simulator.engine import Simulator
from simulator.events import EventKind, SimEvent
from simulator.scenarios import Scenario


def make_engine() -> Simulator:
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=3, compatible_devices=["d"])],
        blocked=[BlockedWindow(device_id="d", start=10, end=15, kind="MAINT")],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=3)})
    return Simulator(inst, plan, Scenario(duration_sigma=0.0), lambda *_: None, 1)


def test_protocol_and_calendar() -> None:
    engine = make_engine()
    adapter = SimulatedAdapter(engine)
    assert isinstance(engine, RuntimeView)
    assert isinstance(adapter, DeviceAdapter) and isinstance(adapter, ControllableAdapter)
    assert isinstance(ManualAdapter(engine), ControllableAdapter)
    assert adapter.list_devices()[0].id == "d"
    assert adapter.get_status("d") == "IDLE"
    assert adapter.get_calendar("d", 12, 20) == [CalendarWindow(12, 15, "MAINT")]
    adapter.start_task("d", "a", 0)
    with pytest.raises(ValueError):
        adapter.start_task("d", "a", 1)
    with pytest.raises(ValueError):
        adapter.get_calendar("d", True, 20)


def test_actual_events_and_callback_rollback() -> None:
    engine = make_engine()
    adapter = SimulatedAdapter(engine)
    events: list[SimEvent] = []
    adapter.subscribe(events.append)
    engine.run(4)
    assert [e.kind for e in events] == [EventKind.TASK_START, EventKind.TASK_END]
    assert [e.time for e in events] == [0, 3]
    engine = make_engine()
    adapter = SimulatedAdapter(engine)

    def fail(_event: object) -> None:
        raise RuntimeError("failed")

    adapter.subscribe(fail)
    with pytest.raises(AdapterCallbackError) as exc:
        engine.run(1)
    assert isinstance(exc.value.__cause__, RuntimeError)
    assert engine.clock == 0 and engine.device_status("d") == "IDLE"
    assert engine.instance.tasks[0].status == "SCHEDULED"


def test_manual_validation_and_deferred_application() -> None:
    engine = make_engine()
    adapter = ManualAdapter(engine)
    with pytest.raises(ValueError):
        adapter.inject_outage(DeviceOutage(device_id="unknown", start=1, end=2), 1)
    with pytest.raises(ValueError):
        adapter.inject_outage(DeviceOutage(device_id="d", start=2, end=3), 1)
    with pytest.raises(ValueError):
        adapter.inject_overrun(TaskOverrun(task_id="a", new_end=5), 0)
    adapter.inject_outage(DeviceOutage(device_id="d", start=4, end=6), 4)
    assert adapter.get_status("d") == "IDLE"
    engine.run(5)
    assert adapter.get_status("d") == "FAULT"
    with pytest.raises(ValueError):
        adapter.inject_outage(DeviceOutage(device_id="d", start=1, end=2), 1)


def test_urgent_is_deferred() -> None:
    from scheduler_core.models import UrgentInsert

    engine = make_engine()
    adapter = ManualAdapter(engine)
    urgent = UrgentInsert(
        tasks=[Task(id="u", experiment_id="e", type="x", duration=1, compatible_devices=["d"])]
    )
    adapter.inject_urgent(urgent, 4)
    assert [task.id for task in engine.instance.tasks] == ["a"]
    engine.run(5)
    assert [task.id for task in engine.instance.tasks] == ["a", "u"]


def test_static_protocol_assignment() -> None:
    runtime: RuntimeView = make_engine()
    device: DeviceAdapter = SimulatedAdapter(runtime)
    controllable: ControllableAdapter = ManualAdapter(runtime)
    assert device.get_status("d") == controllable.get_status("d")
