"""Device and task state transitions and aggregate device state."""

from enum import StrEnum
from collections.abc import Iterable
from typing import Literal


class DeviceState(StrEnum):
    IDLE = "IDLE"
    SETUP = "SETUP"
    BUSY = "BUSY"
    MAINTENANCE = "MAINTENANCE"
    FAULT = "FAULT"
    OFFLINE = "OFFLINE"


TaskState = Literal["PENDING", "SCHEDULED", "RUNNING", "DONE", "INTERRUPTED", "FAILED", "CANCELLED"]

# Aggregate occupancy can change while a device is unavailable.
DEVICE_TRANSITIONS = {
    DeviceState.IDLE: frozenset(
        {
            DeviceState.BUSY,
            DeviceState.SETUP,
            DeviceState.MAINTENANCE,
            DeviceState.FAULT,
            DeviceState.OFFLINE,
        }
    ),
    DeviceState.SETUP: frozenset(
        {
            DeviceState.BUSY,
            DeviceState.FAULT,
            DeviceState.IDLE,
            DeviceState.MAINTENANCE,
            DeviceState.OFFLINE,
        }
    ),
    DeviceState.BUSY: frozenset(
        {
            DeviceState.IDLE,
            DeviceState.FAULT,
            DeviceState.SETUP,
            DeviceState.MAINTENANCE,
            DeviceState.OFFLINE,
        }
    ),
    DeviceState.MAINTENANCE: frozenset(
        {
            DeviceState.IDLE,
            DeviceState.FAULT,
            DeviceState.OFFLINE,
            DeviceState.SETUP,
            DeviceState.BUSY,
        }
    ),
    DeviceState.FAULT: frozenset(
        {
            DeviceState.IDLE,
            DeviceState.MAINTENANCE,
            DeviceState.OFFLINE,
            DeviceState.SETUP,
            DeviceState.BUSY,
        }
    ),
    DeviceState.OFFLINE: frozenset(
        {
            DeviceState.IDLE,
            DeviceState.FAULT,
            DeviceState.MAINTENANCE,
            DeviceState.SETUP,
            DeviceState.BUSY,
        }
    ),
}
TASK_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    "PENDING": frozenset({"SCHEDULED", "CANCELLED"}),
    "SCHEDULED": frozenset({"SCHEDULED", "RUNNING"}),
    "RUNNING": frozenset({"DONE", "INTERRUPTED", "FAILED"}),
    "DONE": frozenset(),
    "INTERRUPTED": frozenset({"PENDING"}),
    "FAILED": frozenset(),
    "CANCELLED": frozenset(),
}


class IllegalTransition(ValueError):
    """A transition is absent from the specified state machine."""


def transition_device(old: DeviceState, new: DeviceState) -> DeviceState:
    """Validate and return the next device state."""
    if new not in DEVICE_TRANSITIONS[old]:
        raise IllegalTransition(f"{old} -> {new}")
    return new


def transition_task(old: TaskState, new: TaskState) -> TaskState:
    """Validate and return the next task state."""
    if new not in TASK_TRANSITIONS[old]:
        raise IllegalTransition(f"{old} -> {new}")
    return new


def derive_device_state(
    running_demand: int, setups: int, down_causes: Iterable[Literal["FAULT", "OFFLINE", "MAINT"]]
) -> DeviceState:
    """Derive displayed state from nonnegative occupancy and down causes."""
    if (
        type(running_demand) is not int
        or type(setups) is not int
        or running_demand < 0
        or setups < 0
    ):
        raise ValueError("occupancy counts must be nonnegative integers")
    causes = set(down_causes)
    if not causes <= {"FAULT", "OFFLINE", "MAINT"}:
        raise ValueError("unknown down cause")
    for cause, state in (
        ("FAULT", DeviceState.FAULT),
        ("OFFLINE", DeviceState.OFFLINE),
        ("MAINT", DeviceState.MAINTENANCE),
    ):
        if cause in causes:
            return state
    return DeviceState.BUSY if running_demand else DeviceState.SETUP if setups else DeviceState.IDLE
