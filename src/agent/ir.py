"""Untrusted, versioned change proposals and deterministic reference checks."""

from __future__ import annotations

from datetime import datetime, timedelta
from collections.abc import Mapping, Set
import re
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from scheduler_core.models import Instance, Precedence, Task


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EntityRef(StrictModel):
    original: str = Field(min_length=1)
    resolved_id: str | None = None
    confidence: float = Field(ge=0, le=1)


class Change(StrictModel):
    version: Literal["v001"] = "v001"
    strength: Literal["HARD", "SOFT"]


class Outage(Change):
    kind: Literal["DEVICE_OUTAGE"]
    device: EntityRef
    start: datetime
    end: datetime


class Deadline(Change):
    kind: Literal["DEADLINE"]
    task: EntityRef
    deadline: datetime
    level: Literal["HARD", "NEGOTIABLE"]
    weight: float = Field(ge=0, allow_inf_nan=False)


class UrgentTask(StrictModel):
    id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    duration_minutes: int = Field(gt=0)
    release: datetime
    deadline: datetime
    deadline_level: Literal["HARD", "NEGOTIABLE"] = "NEGOTIABLE"
    weight: float = Field(default=1.0, ge=0, allow_inf_nan=False)
    compatible_devices: list[str] = Field(min_length=1)
    preemptible: bool = False
    demand: int = Field(default=1, gt=0)
    required_skills: list[str] = Field(default_factory=list)
    requires_person: bool = False


class Urgent(Change):
    kind: Literal["URGENT_TASK_INSERT"]
    tasks: list[UrgentTask] = Field(min_length=1)
    precedences: list[Precedence] = Field(default_factory=list)


class Overrun(Change):
    kind: Literal["TASK_OVERRUN"]
    task: EntityRef
    end: datetime


Proposal = Annotated[Outage | Deadline | Urgent | Overrun, Field(discriminator="kind")]
proposal_adapter: TypeAdapter[Proposal] = TypeAdapter(Proposal)


def check_proposal(
    proposal: Proposal, instance: Instance, aliases: Mapping[str, Set[str]] | None = None
) -> None:
    """Reject unsupported soft changes, unresolved references and invalid times."""
    if proposal.strength == "SOFT":
        raise ValueError("soft preference is not executable")
    if isinstance(proposal, Urgent):
        existing = {task.id for task in instance.tasks}
        devices = {device.id for device in instance.devices}
        ids = [task.id for task in proposal.tasks]
        if len(ids) != len(set(ids)) or any(task.id in existing for task in proposal.tasks):
            raise ValueError("urgent task already exists or is duplicated")
        for task in proposal.tasks:
            if (
                not task.compatible_devices
                or not set(task.compatible_devices) <= devices
                or instance.axis.to_slot(task.release) < instance.now
                or instance.axis.to_slot(task.deadline) <= instance.axis.to_slot(task.release)
                or task.duration_minutes % instance.axis.slot_minutes != 0
            ):
                raise ValueError("urgent task needs deadline, compatible devices and valid window")
        return
    ref = proposal.device if isinstance(proposal, Outage) else proposal.task
    valid_ids = (
        {device.id for device in instance.devices}
        if isinstance(proposal, Outage)
        else {task.id for task in instance.tasks}
    )
    matches = ({ref.original} if ref.original in valid_ids else set()) | (
        set((aliases or {}).get(ref.original, set())) & valid_ids
    )
    if ref.confidence < 0.8 or matches != {ref.resolved_id}:
        raise ValueError("entity needs clarification")
    if isinstance(proposal, Outage):
        start = instance.axis.to_slot(proposal.start)
        end = instance.axis.to_slot(proposal.end)
        if start < instance.now or start >= end:
            raise ValueError("invalid outage interval")
    else:
        time = proposal.deadline if isinstance(proposal, Deadline) else proposal.end
        if instance.axis.to_slot(time) < instance.now:
            raise ValueError("time precedes business now")


def normalize_relative(draft: dict[str, object], instance: Instance) -> dict[str, object]:
    """Resolve supported Chinese relative clock times against the business clock."""
    result = dict(draft)
    now = instance.axis.to_dt(instance.now).astimezone(ZoneInfo("Asia/Shanghai"))
    for key in ("start", "end", "deadline", "release"):
        value = result.get(key)
        if not isinstance(value, str):
            continue
        match = re.fullmatch(r"(今天|明天)\s*(\d{1,2}):(\d{2})", value)
        if match:
            day = now.date() + timedelta(days=int(match.group(1) == "明天"))
            resolved = datetime(
                day.year,
                day.month,
                day.day,
                int(match.group(2)),
                int(match.group(3)),
                tzinfo=now.tzinfo,
            )
            result[key] = resolved.isoformat()
    tasks = result.get("tasks")
    if isinstance(tasks, list):
        result["tasks"] = [
            normalize_relative(item, instance) if isinstance(item, dict) else item for item in tasks
        ]
    return result


def parse_draft(
    draft: dict[str, object], instance: Instance, aliases: Mapping[str, Set[str]] | None = None
) -> tuple[dict[str, object], Proposal]:
    """Normalize and validate the same untrusted proposal in production and evaluation."""
    import json

    normalized = normalize_relative(draft, instance)
    kind = normalized.get("kind")
    key = "device" if kind == "DEVICE_OUTAGE" else "task"
    reference = normalized.get(key)
    if isinstance(reference, dict):
        reference = dict(reference)
        original = reference.get("original")
        ids = (
            {device.id for device in instance.devices}
            if key == "device"
            else {task.id for task in instance.tasks}
        )
        if isinstance(original, str):
            matches = ({original} if original in ids else set()) | (
                set((aliases or {}).get(original, set())) & ids
            )
            reference["resolved_id"] = next(iter(matches)) if len(matches) == 1 else None
        normalized[key] = reference
    proposal = proposal_adapter.validate_json(json.dumps(normalized))
    check_proposal(proposal, instance, aliases)
    return normalized, proposal


def urgent_core(task: UrgentTask, instance: Instance) -> Task:
    """Convert aware timestamps and exact minute duration to internal integer slots."""
    fields = task.model_dump(exclude={"duration_minutes", "release", "deadline"})
    fields.update(
        duration=task.duration_minutes // instance.axis.slot_minutes,
        release=instance.axis.to_slot(task.release),
        deadline=instance.axis.to_slot(task.deadline),
        required_skills=set(task.required_skills),
    )
    return Task.model_validate(fields)
