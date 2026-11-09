"""Scheduler data contracts; independent business validation is separate."""

from typing import Annotated, Literal, Union
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .axis import Slot, TimeAxis

Positive = Annotated[int, Field(strict=True, gt=0)]
Nonnegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Nonempty = Annotated[str, Field(min_length=1)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Device(Contract):
    id: str
    type: str
    capacity: Positive = 1
    capabilities: set[str] = Field(default_factory=set)


class Task(Contract):
    id: str
    experiment_id: str
    type: str
    duration: Positive
    release: Slot = 0
    deadline: Slot | None = None
    deadline_level: Literal["HARD", "NEGOTIABLE"] = "NEGOTIABLE"
    weight: Nonnegative = 1.0
    compatible_devices: list[str]
    preemptible: bool = False
    status: Literal[
        "PENDING", "SCHEDULED", "RUNNING", "DONE", "INTERRUPTED", "FAILED", "CANCELLED"
    ] = "PENDING"
    demand: Positive = 1
    required_skills: set[Nonempty] = Field(default_factory=set)
    requires_person: bool = False

    @property
    def needs_person(self) -> bool:
        """Whether explicit or skill-based personnel is required."""
        return self.requires_person or bool(self.required_skills)


class Precedence(Contract):
    pred: str
    succ: str
    lag_min: Slot = 0
    lag_max: Slot | None = None


class Window(Contract):
    start: Slot
    end: Slot

    @model_validator(mode="after")
    def ordered(self) -> "Window":
        if self.start >= self.end:
            raise ValueError("start must precede end")
        return self


class BlockedWindow(Window):
    device_id: str
    kind: Literal["CLOSED", "MAINT", "FAULT", "RUNNING"]


class PersonBlockedWindow(Window):
    pass


class Person(Contract):
    id: Nonempty
    skills: set[Nonempty] = Field(default_factory=set)
    blocked: list[PersonBlockedWindow] = Field(default_factory=list)


class SetupRule(Contract):
    device_id: str
    task_type: str
    slots: Slot


class Instance(Contract):
    axis: TimeAxis
    now: Slot = 0
    devices: list[Device]
    tasks: list[Task]
    precedences: list[Precedence] = Field(default_factory=list)
    blocked: list[BlockedWindow] = Field(default_factory=list)
    setups: list[SetupRule] = Field(default_factory=list)
    persons: list[Person] = Field(default_factory=list)

    @model_validator(mode="after")
    def references(self) -> "Instance":
        for items in (self.devices, self.tasks, self.persons):
            ids = [item.id for item in items]
            if len(ids) != len(set(ids)):
                raise ValueError("duplicate id")
        task_ids = {task.id for task in self.tasks}
        if any(
            p.pred == p.succ or p.pred not in task_ids or p.succ not in task_ids
            for p in self.precedences
        ):
            raise ValueError("invalid precedence reference")
        return self


class Assignment(Window):
    task_id: str
    device_id: str
    person_id: str | None = None


class PlanMetrics(Contract):
    tardiness: Nonnegative = 0.0
    makespan: Slot = 0
    moved: Slot = 0
    switched: Slot = 0
    shift_total: Slot = 0
    urgent_delay: Nonnegative = 0.0
    solve_seconds: Nonnegative = 0.0
    gap: Nonnegative | None = None


class Plan(Contract):
    id: str
    parent_id: str | None = None
    assignments: dict[str, Assignment]
    metrics: PlanMetrics = Field(default_factory=PlanMetrics)

    @model_validator(mode="after")
    def keys_match(self) -> "Plan":
        if any(key != assignment.task_id for key, assignment in self.assignments.items()):
            raise ValueError("assignment key differs from task_id")
        return self


class DeviceOutage(Window):
    type: Literal["DEVICE_OUTAGE"] = "DEVICE_OUTAGE"
    device_id: str


class UrgentInsert(Contract):
    type: Literal["URGENT_INSERT"] = "URGENT_INSERT"
    tasks: list[Task]
    precedences: list[Precedence] = Field(default_factory=list)


class TaskOverrun(Contract):
    type: Literal["TASK_OVERRUN"] = "TASK_OVERRUN"
    task_id: str
    new_end: Slot


Event = Annotated[Union[DeviceOutage, UrgentInsert, TaskOverrun], Field(discriminator="type")]


class Violation(Contract):
    code: Literal["V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9", "V10", "V11"]
    task_ids: list[str] = Field(default_factory=list)
    device_id: str | None = None
    detail: str


class ValidationReport(Contract):
    passed: bool
    violations: list[Violation] = Field(default_factory=list)


class ReplanParams(Contract):
    alpha: float = 1.0
    beta_moved: float = 2.0
    beta_switched: float = 5.0
    beta_shift: float = 0.1
    gamma: float = 5.0
    total_budget_s: float = 10.0
    window_slots: int = 48
    max_level: int = 3
    weight_grid: list[tuple[float, float]] = Field(
        default_factory=lambda: [(1.0, 0.5), (1.0, 1.0), (1.0, 2.0), (1.0, 4.0)]
    )
    seed: int = 0
    num_workers: int = 8


class ImpactReport(Contract):
    frozen: set[str]
    affected: set[str]
    unaffected: set[str]
    reasons: dict[str, str]


class Candidate(Contract):
    plan: Plan
    level: int
    weights: tuple[float, float]
    f1: float
    f2: float
    f3: float
    label: str | None = None
    validation: ValidationReport


class ConflictCore(Contract):
    group_ids: list[str]
    descriptions: list[str]


class RelaxationOption(Contract):
    description: str
    cost: float
    relaxed_groups: list[str]


class ReplanResult(Contract):
    status: Literal["OK", "INFEASIBLE", "TIMEOUT"]
    candidates: list[Candidate] = Field(default_factory=list)
    impact: ImpactReport | None = None
    level_reached: int | None = None
    conflict: ConflictCore | None = None
    relaxations: list[RelaxationOption] = Field(default_factory=list)


__all__ = [
    "Slot",
    "TimeAxis",
    "Device",
    "Task",
    "Precedence",
    "BlockedWindow",
    "SetupRule",
    "Instance",
    "Assignment",
    "PlanMetrics",
    "Plan",
    "DeviceOutage",
    "UrgentInsert",
    "TaskOverrun",
    "Event",
    "Violation",
    "ValidationReport",
    "ReplanParams",
    "ImpactReport",
    "Candidate",
    "ConflictCore",
    "RelaxationOption",
    "ReplanResult",
    "Person",
    "PersonBlockedWindow",
]
