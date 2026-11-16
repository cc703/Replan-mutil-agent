"""Strict, typed simulation events."""

from enum import StrEnum
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, model_validator
from scheduler_core.models import DeviceOutage, TaskOverrun, UrgentInsert
from .states import DeviceState, TaskState


class EventKind(StrEnum):
    TASK_END = "TASK_END"
    SETUP_END = "SETUP_END"
    DEVICE_RECOVER = "DEVICE_RECOVER"
    MAINT_END = "MAINT_END"
    DEVICE_FAULT = "DEVICE_FAULT"
    MAINT_START = "MAINT_START"
    URGENT_ARRIVAL = "URGENT_ARRIVAL"
    TASK_OVERRUN = "TASK_OVERRUN"
    REPLAN_FLUSH = "REPLAN_FLUSH"
    SETUP_START = "SETUP_START"
    TASK_START = "TASK_START"


PRIORITY = {
    kind: priority
    for priority, kinds in enumerate(
        (
            (EventKind.TASK_END,),
            (EventKind.SETUP_END,),
            (EventKind.DEVICE_RECOVER, EventKind.MAINT_END),
            (EventKind.DEVICE_FAULT, EventKind.MAINT_START),
            (EventKind.URGENT_ARRIVAL,),
            (EventKind.TASK_OVERRUN,),
            (EventKind.REPLAN_FLUSH,),
            (EventKind.SETUP_START,),
            (EventKind.TASK_START,),
        )
    )
    for kind in kinds
}
NonnegativeInt = Annotated[int, Field(strict=True, ge=0)]


class SimEvent(BaseModel):
    """One scheduled event; seq is assigned by the queue."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    time: NonnegativeInt
    kind: EventKind
    seq: NonnegativeInt = 0
    device_id: str | None = None
    task_id: str | None = None
    plan_epoch: NonnegativeInt | None = None
    payload: DeviceOutage | UrgentInsert | TaskOverrun | None = None

    @model_validator(mode="after")
    def validate_event(self) -> "SimEvent":
        """Enforce event-specific identifiers and typed external payloads."""
        task_kinds = {
            EventKind.TASK_END,
            EventKind.SETUP_END,
            EventKind.SETUP_START,
            EventKind.TASK_START,
        }
        device_kinds = task_kinds | {
            EventKind.DEVICE_FAULT,
            EventKind.DEVICE_RECOVER,
            EventKind.MAINT_START,
            EventKind.MAINT_END,
        }
        if self.kind in device_kinds and not self.device_id:
            raise ValueError("event requires device_id")
        if self.kind in task_kinds | {EventKind.TASK_OVERRUN} and not self.task_id:
            raise ValueError("event requires task_id")
        if self.plan_epoch is not None and not self.task_id:
            raise ValueError("plan epoch requires task_id")
        if self.kind == EventKind.DEVICE_FAULT:
            if (
                not isinstance(self.payload, DeviceOutage)
                or self.payload.device_id != self.device_id
                or self.payload.start != self.time
            ):
                raise ValueError("fault requires matching outage starting at event time")
        elif self.kind == EventKind.URGENT_ARRIVAL:
            if not isinstance(self.payload, UrgentInsert):
                raise ValueError("arrival requires urgent payload")
        elif self.kind == EventKind.TASK_OVERRUN:
            if self.payload is not None and (
                not isinstance(self.payload, TaskOverrun)
                or self.payload.task_id != self.task_id
                or self.payload.new_end <= self.time
            ):
                raise ValueError("overrun payload must match task and end after event")
        elif self.payload is not None:
            raise ValueError("unexpected event payload")
        return self

    @property
    def priority(self) -> int:
        """Return fixed ordering priority."""
        return PRIORITY[self.kind]


class StatusChange(BaseModel):
    """A device or task state change emitted by the runtime."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    time: NonnegativeInt
    entity_id: str
    old: DeviceState | TaskState
    new: DeviceState | TaskState
    cause_event_id: str | None = None
