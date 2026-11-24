"""Application event and confirmed constraint input, with exact time conversion."""

import json
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BeforeValidator, Field
from agent.changes import prepare_change
from agent.ir import Deadline, proposal_adapter
from scheduler_core.generation.integrity import check_instance_integrity
from scheduler_core.models import (
    Contract,
    DeviceOutage,
    Instance,
    Plan,
    Precedence,
    Task,
    UrgentInsert,
)
from scheduler_core.replanning.events import prepare_raw
from scheduler_core.validation_context import ExecutionSnapshot, ValidationContext

from .errors import ServiceError


def _iso_timestamp(value: object) -> object:
    if not isinstance(value, datetime) and (
        not isinstance(value, str) or len(value) < 17 or value[10] != "T"
    ):
        raise ValueError("timestamp must be an ISO-8601 string with offset")
    return value


Timestamp = Annotated[AwareDatetime, BeforeValidator(_iso_timestamp)]


class Outage(Contract):
    type: Literal["DEVICE_OUTAGE"]
    device_id: str
    start: Timestamp
    end: Timestamp


class UrgentTask(Contract):
    id: str
    experiment_id: str
    type: str
    duration_minutes: int = Field(strict=True, gt=0)
    release: Timestamp | None = None
    deadline: Timestamp | None = None
    deadline_level: Literal["HARD", "NEGOTIABLE"] = "NEGOTIABLE"
    weight: float = 1
    compatible_devices: list[str] = Field(min_length=1)
    demand: int = Field(default=1, strict=True, gt=0)
    required_skills: set[str] = Field(default_factory=set)
    requires_person: bool = False


class Edge(Contract):
    pred: str
    succ: str
    lag_min_minutes: int = Field(default=0, strict=True, ge=0)
    lag_max_minutes: int | None = Field(default=None, strict=True, ge=0)


class Urgent(Contract):
    type: Literal["URGENT_INSERT"]
    tasks: list[UrgentTask] = Field(min_length=1)
    precedences: list[Edge] = Field(default_factory=list)


class Overrun(Contract):
    type: Literal["TASK_OVERRUN"]
    task_id: str | None = None
    end: Timestamp | None = None


class Constraint(Contract):
    type: Literal["CONSTRAINT_CHANGE"]
    ir: dict[str, object]


Event = Annotated[Outage | Urgent | Overrun | Constraint, Field(discriminator="type")]
CoreEvent = DeviceOutage | UrgentInsert


def execution_context(instance: Instance, base: Plan) -> ValidationContext:
    """Derive the empty observation list only for the supported manual, unstarted world."""
    if (
        any(t.status != "PENDING" for t in instance.tasks)
        or any(a.start < instance.now for a in base.assignments.values())
        or any(w.kind == "RUNNING" for w in instance.blocked)
    ):
        raise ServiceError(
            "PLAN_INTEGRITY_ERROR", "No trusted execution evidence for this world", 422
        )
    return ValidationContext(snapshot=ExecutionSnapshot(plan_id=base.id, as_of=instance.now))


def _slot(inst: Instance, value: datetime) -> int:
    try:
        return inst.axis.to_slot(value)
    except ValueError as exc:
        raise ServiceError("TIME_NOT_ALIGNED", str(exc)) from exc


def _duration(inst: Instance, minutes: int) -> int:
    slots, remainder = divmod(minutes, inst.axis.slot_minutes)
    if remainder:
        raise ServiceError("TIME_NOT_ALIGNED", "Duration must be a multiple of the slot size")
    return slots


def normalize(inst: Instance, event: Outage | Urgent) -> CoreEvent:
    devices = {device.id for device in inst.devices}
    if isinstance(event, Outage):
        if event.device_id not in devices:
            raise ServiceError("UNKNOWN_ENTITY", "Unknown device")
        start, end = _slot(inst, event.start), _slot(inst, event.end)
        if start < inst.now:
            raise ServiceError("INVALID_EVENT", "An outage cannot begin before business now")
        return DeviceOutage(device_id=event.device_id, start=start, end=end)
    tasks = []
    for task in event.tasks:
        if not set(task.compatible_devices) <= devices:
            raise ServiceError("UNKNOWN_ENTITY", "Unknown compatible device")
        tasks.append(
            Task.model_validate(
                {
                    **task.model_dump(exclude={"duration_minutes", "release", "deadline"}),
                    "duration": _duration(inst, task.duration_minutes),
                    "release": _slot(inst, task.release) if task.release else inst.now,
                    "deadline": _slot(inst, task.deadline) if task.deadline else None,
                }
            )
        )
    task_ids = {task.id for task in inst.tasks} | {task.id for task in tasks}
    if any(edge.pred not in task_ids or edge.succ not in task_ids for edge in event.precedences):
        raise ServiceError("UNKNOWN_ENTITY", "Unknown task in urgent precedence")
    edges = [
        Precedence(
            pred=edge.pred,
            succ=edge.succ,
            lag_min=_duration(inst, edge.lag_min_minutes),
            lag_max=_duration(inst, edge.lag_max_minutes)
            if edge.lag_max_minutes is not None
            else None,
        )
        for edge in event.precedences
    ]
    return UrgentInsert(tasks=tasks, precedences=edges)


def apply_fact(
    instance: Instance, base: Plan, event: Event, context: ValidationContext
) -> tuple[Instance, CoreEvent | None, ValidationContext]:
    """Apply one independently confirmed manual event or P6 deadline change."""
    if isinstance(event, Overrun):
        raise ServiceError("UNSUPPORTED_EVENT", "P7 does not observe running tasks")
    if isinstance(event, Constraint):
        proposal = proposal_adapter.validate_json(json.dumps(event.ir))
        if not isinstance(proposal, Deadline):
            raise ServiceError("UNSUPPORTED_CONSTRAINT_TYPE", "Only deadline changes are supported")
        post, _, evidence = prepare_change(proposal, instance, base, context)
        return post, None, evidence
    raw = normalize(instance, event)
    if isinstance(raw, UrgentInsert):
        ids = [task.id for task in raw.tasks]
        if len(ids) != len(set(ids)):
            raise ServiceError("INVALID_EVENT", "Duplicate inserted task ID")
    post, evidence = prepare_raw(instance, base, [raw], context)
    check_instance_integrity(post)
    return post, raw, evidence


def apply_facts(
    instance: Instance, base: Plan, facts: list[Event], context: ValidationContext
) -> tuple[Instance, list[CoreEvent], ValidationContext]:
    events = []
    for index, fact in enumerate(facts):
        try:
            instance, event, context = apply_fact(instance, base, fact, context)
        except (ValueError, ServiceError) as exc:
            raise ServiceError("INVALID_EVENT", str(exc), index=index) from exc
        if event is not None:
            events.append(event)
    return instance, events, context
