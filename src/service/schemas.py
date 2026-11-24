"""Typed internal scheduler request contracts."""

from typing import Any

from pydantic import Field
from scheduler_core.models import Contract, Instance, Plan, ReplanParams
from scheduler_core.validation_context import ValidationContext

from .schemas_events import Event


class HashRequest(Contract):
    payload: Any


class InstanceRequest(Contract):
    instance: Instance


class InitialParams(Contract):
    time_limit_s: float = Field(default=30, gt=0, le=120)
    num_workers: int = Field(default=8, strict=True, ge=1, le=32)
    seed: int = Field(default=0, strict=True, ge=0, le=2147483647)
    objective_weights: dict[str, float] | None = None


class InitialRequest(InstanceRequest):
    params: InitialParams = Field(default_factory=InitialParams)
    revision: int = Field(default=0, ge=0)


class WorldRequest(InstanceRequest):
    base_plan: Plan
    context: ValidationContext | None = None


class PreviewRequest(WorldRequest):
    event: Event
    pending_events: list[Event] = Field(default_factory=list)


class ReplanRequest(WorldRequest):
    events: list[Event] = Field(max_length=50)
    params: ReplanParams = Field(default_factory=ReplanParams)
    max_candidates: int = Field(default=5, ge=1, le=10)
    explain: bool = True
    budget_s: float | None = Field(default=None, gt=0, le=120)
    revision: int = Field(default=0, ge=0)


class Evidence(InstanceRequest):
    plan: Plan
    base_plan: Plan | None = None
    free: set[str] | None = None
    context: ValidationContext | None = None
    revision: int = Field(default=0, ge=0)


class ValidateRequest(Evidence):
    expected_plan_sha256: str | None = None
    additional_events: list[Event] = Field(default_factory=list)
    current_base_plan: Plan | None = None


class DiffRequest(InstanceRequest):
    base_plan: Plan
    plan: Plan


class RollbackRequest(WorldRequest):
    target_plan: Plan
    events: list[Event] = Field(default_factory=list)
    revision: int = Field(default=0, ge=0)


class TurnRequest(WorldRequest):
    lab_id: str
    session_id: str | None = None
    text: str = Field(min_length=1, max_length=8000, pattern=r"\S")
    actor: str = Field(min_length=1, max_length=128)
    events: list[Event] = Field(default_factory=list)
    revision: int = Field(default=0, ge=0)
