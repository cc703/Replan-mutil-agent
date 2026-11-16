import pytest
from simulator.states import (
    DeviceState,
    IllegalTransition,
    derive_device_state,
    transition_device,
    transition_task,
)


def test_transitions() -> None:
    expected = {
        "IDLE": "BUSY SETUP MAINTENANCE FAULT OFFLINE",
        "SETUP": "BUSY FAULT IDLE MAINTENANCE OFFLINE",
        "BUSY": "IDLE FAULT SETUP MAINTENANCE OFFLINE",
        "MAINTENANCE": "IDLE FAULT OFFLINE SETUP BUSY",
        "FAULT": "IDLE MAINTENANCE OFFLINE SETUP BUSY",
        "OFFLINE": "IDLE FAULT MAINTENANCE SETUP BUSY",
    }
    for old in DeviceState:
        for new in DeviceState:
            if new.value in expected[old.value].split():
                assert transition_device(old, new) == new
            else:
                with pytest.raises(IllegalTransition):
                    transition_device(old, new)
    assert transition_task("RUNNING", "INTERRUPTED") == "INTERRUPTED"
    with pytest.raises(IllegalTransition):
        transition_task("DONE", "RUNNING")


def test_aggregate() -> None:
    assert derive_device_state(2, 1, []) == DeviceState.BUSY
    assert derive_device_state(0, 1, []) == DeviceState.SETUP
    assert derive_device_state(0, 0, []) == DeviceState.IDLE
    assert derive_device_state(2, 1, ["MAINT", "OFFLINE", "FAULT"]) == DeviceState.FAULT
    assert derive_device_state(2, 1, ["MAINT", "OFFLINE"]) == DeviceState.OFFLINE
    assert derive_device_state(2, 1, ["MAINT"]) == DeviceState.MAINTENANCE
