import pytest
from simulator.events import EventKind, SimEvent
from simulator.queue import EventQueue


def test_order_batch_and_stale() -> None:
    q = EventQueue()
    q.push(SimEvent(time=5, kind=EventKind.TASK_START, device_id="x", task_id="x"))
    q.push(SimEvent(time=5, kind=EventKind.TASK_END, device_id="x", task_id="x"))
    q.push_plan_batch(
        [
            SimEvent(time=5, kind=EventKind.TASK_START, device_id="b", task_id="b", plan_epoch=1),
            SimEvent(time=5, kind=EventKind.TASK_START, device_id="a", task_id="a", plan_epoch=1),
        ]
    )
    q.set_epoch("a", 2)
    assert q.pop().kind == EventKind.TASK_END
    assert q.pop().task_id == "x"
    assert q.pop().task_id == "b"
    assert q.stale_skipped == 1
    with pytest.raises(IndexError):
        q.pop()


def test_cutoff_and_injection() -> None:
    q = EventQueue()
    q.push(SimEvent(time=5, kind=EventKind.TASK_START, device_id="d", task_id="t", plan_epoch=1))
    q.set_epoch("t", 2)
    assert q.pop_before(5) is None
    assert q.stale_skipped == 0
    q.push(SimEvent(time=5, kind=EventKind.MAINT_START, device_id="d"))
    event = q.pop_before(6)
    assert event is not None
    assert event.kind == EventKind.MAINT_START
    assert q.pop_before(6) is None
    assert q.stale_skipped == 1


def test_payload_isolation() -> None:
    from scheduler_core.models import DeviceOutage

    payload = DeviceOutage(device_id="d", start=1, end=4)
    event = SimEvent(time=1, kind=EventKind.DEVICE_FAULT, device_id="d", payload=payload)
    q = EventQueue()
    returned = q.push(event)
    payload.end = 9
    assert isinstance(returned.payload, DeviceOutage)
    returned.payload.end = 8
    popped = q.pop()
    assert isinstance(popped.payload, DeviceOutage)
    assert popped.payload.end == 4
