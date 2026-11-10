"""Structural execution evidence and deadline authorization contracts.

Event IDs are execution evidence, not human confirmations. Confirmation IDs are
opaque: authenticity is the responsibility of the application L1/L2 workflow.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .axis import Slot

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class _Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExecutionRecord(_Evidence):
    task_id: Identifier
    status: Literal["RUNNING", "DONE"]
    device_id: Identifier
    person_id: Identifier | None = None
    start: Slot
    planned_end: Slot | None = None
    remaining_estimate: Slot | None = None
    actual_end: Slot | None = None
    event_id: Identifier

    @model_validator(mode="after")
    def consistent(self) -> "ExecutionRecord":
        if self.status == "RUNNING":
            if (
                self.planned_end is None
                or self.planned_end <= self.start
                or self.remaining_estimate is None
                or self.actual_end is not None
            ):
                raise ValueError("invalid RUNNING record")
        elif (
            self.actual_end is None
            or self.actual_end <= self.start
            or self.planned_end is not None
            or self.remaining_estimate is not None
        ):
            raise ValueError("invalid DONE record")
        return self


class ExecutionSnapshot(_Evidence):
    plan_id: Identifier
    as_of: Slot
    base_as_of: Slot | None = None
    records: list[ExecutionRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent(self) -> "ExecutionSnapshot":
        if self.base_as_of is not None and self.base_as_of > self.as_of:
            raise ValueError("base_as_of exceeds as_of")
        ids = [record.task_id for record in self.records]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate record")
        for record in self.records:
            if record.status == "RUNNING" and record.start > self.as_of:
                raise ValueError("RUNNING starts after snapshot")
            if (
                record.status == "DONE"
                and record.actual_end is not None
                and record.actual_end > self.as_of
            ):
                raise ValueError("DONE ends after snapshot")
        return self


class FrozenEndChange(_Evidence):
    task_id: Identifier
    plan_id: Identifier
    base_plan_id: Identifier
    old_end: Slot
    new_end: Slot
    event_id: Identifier
    acted_at: Slot

    @model_validator(mode="after")
    def consistent(self) -> "FrozenEndChange":
        if self.new_end <= self.old_end:
            raise ValueError("new_end must extend old_end")
        return self


class DeadlineAuthorization(_Evidence):
    task_id: Identifier
    plan_id: Identifier
    original_deadline: Slot
    relaxed_deadline: Slot
    confirmation_id: Identifier
    acted_at: Slot
    valid_until: Slot | None = None

    @model_validator(mode="after")
    def consistent(self) -> "DeadlineAuthorization":
        if self.relaxed_deadline < self.original_deadline:
            raise ValueError("relaxed deadline precedes original")
        if self.valid_until is not None and self.valid_until < self.acted_at:
            raise ValueError("authorization expires before action")
        return self


class RunningBlockBinding(_Evidence):
    device_id: Identifier
    start: Slot
    end: Slot
    task_id: Identifier

    @model_validator(mode="after")
    def consistent(self) -> "RunningBlockBinding":
        if self.end <= self.start:
            raise ValueError("end must follow start")
        return self


class ValidationContext(_Evidence):
    snapshot: ExecutionSnapshot | None = None
    end_changes: list[FrozenEndChange] = Field(default_factory=list)
    deadline_authorizations: list[DeadlineAuthorization] = Field(default_factory=list)
    running_block_bindings: list[RunningBlockBinding] = Field(default_factory=list)
