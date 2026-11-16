import pytest
from pydantic import ValidationError
from simulator.events import EventKind, PRIORITY, SimEvent


def test_priorities_and_strictness() -> None:
    assert [PRIORITY[k] for k in EventKind] == [0, 1, 2, 2, 3, 3, 4, 5, 6, 7, 8]
    with pytest.raises(ValidationError):
        SimEvent(time=True, kind=EventKind.TASK_START)
    with pytest.raises(ValidationError):
        SimEvent.model_validate({"time": 1, "kind": EventKind.TASK_START, "unexpected": 1})


def test_event_specific_validation() -> None:
    from scheduler_core.models import DeviceOutage, TaskOverrun

    with pytest.raises(ValidationError):
        SimEvent(time=1, kind=EventKind.TASK_START)
    with pytest.raises(ValidationError):
        SimEvent(
            time=1,
            kind=EventKind.DEVICE_FAULT,
            device_id="d",
            payload=DeviceOutage(device_id="d", start=2, end=4),
        )
    with pytest.raises(ValidationError):
        SimEvent(
            time=1,
            kind=EventKind.TASK_OVERRUN,
            task_id="t",
            payload=TaskOverrun(task_id="other", new_end=3),
        )
    assert SimEvent(time=1, kind=EventKind.TASK_OVERRUN, task_id="t").payload is None
