"""Immutable, canonical simulation log records and strict JSONL interchange."""

import hashlib
import json
from datetime import datetime
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator
from scheduler_core.models import Event, Instance, Plan, UrgentInsert

from .events import SimEvent
from .scenarios import Scenario
from .states import DEVICE_TRANSITIONS, TASK_TRANSITIONS, DeviceState, TaskState


def _normal(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, BaseModel):
        return _normal(value.model_dump(mode="python"))
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("JSON object keys must be strings")
        return {key: _normal(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        items = [_normal(item) for item in value]
        return sorted(
            items,
            key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False, allow_nan=False),
        )
    if isinstance(value, (list, tuple)):
        return [_normal(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    """Encode values deterministically, including P1 models with sets."""
    return json.dumps(
        _normal(value), sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    )


def content_hash(value: Any) -> str:
    """SHA-256 of canonical UTF-8 JSON."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> Any:
    raise ValueError(f"invalid numeric constant: {value}")


def _load(value: str) -> Any:
    return json.loads(value, object_pairs_hook=_object, parse_constant=_constant)


def _snapshot(value: str, adapter: TypeAdapter[Any]) -> None:
    parsed = adapter.validate_json(value, strict=True)
    if canonical_json(parsed) != value:
        raise ValueError("snapshot must contain the complete canonical model")


class Record(BaseModel):
    """Common ordering metadata; embedded data is an immutable JSON snapshot."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    index: int = Field(ge=0)
    time: int = Field(ge=0)
    priority: int = Field(ge=0)
    seq: int = Field(ge=0)

    @model_validator(mode="after")
    def snapshots_are_canonical(self) -> "Record":
        for name in type(self).model_fields:
            if name.endswith("_json"):
                value = getattr(self, name)
                if value is not None and canonical_json(_load(value)) != value:
                    raise ValueError(f"{name} must be canonical JSON")
        return self


class Header(Record):
    kind: Literal["HEADER"] = "HEADER"
    seed: int = Field(ge=0)
    version: str
    scene_json: str
    instance_json: str
    plan_json: str
    scene_hash: str
    instance_hash: str
    plan_hash: str

    @model_validator(mode="after")
    def hashes_match(self) -> "Header":
        adapters: tuple[tuple[str, TypeAdapter[Any]], ...] = (
            ("scene", TypeAdapter(Scenario)),
            ("instance", TypeAdapter(Instance)),
            ("plan", TypeAdapter(Plan)),
        )
        for name, adapter in adapters:
            _snapshot(getattr(self, name + "_json"), adapter)
        for name in ("scene", "instance", "plan"):
            if content_hash(_load(getattr(self, name + "_json"))) != getattr(self, name + "_hash"):
                raise ValueError(f"{name} hash mismatch")
        return self


class EventEnqueued(Record):
    """An actual queue insertion, including its assigned sequence and future payload."""

    kind: Literal["EVENT_ENQUEUED"] = "EVENT_ENQUEUED"
    event_json: str
    source: Literal["generated", "plan", "internal", "injected"]

    @model_validator(mode="after")
    def event_valid(self) -> "EventEnqueued":
        _snapshot(self.event_json, TypeAdapter(SimEvent))
        return self


class DeviceFault(Record):
    kind: Literal["DEVICE_FAULT"] = "DEVICE_FAULT"
    device_id: str
    end: int
    source: Literal["generated", "injected"]

    @model_validator(mode="after")
    def ordered(self) -> "DeviceFault":
        if self.end <= self.time:
            raise ValueError("fault end must follow start")
        return self


class DeviceRecover(Record):
    kind: Literal["DEVICE_RECOVER"] = "DEVICE_RECOVER"
    device_id: str


class MaintenanceStart(Record):
    kind: Literal["MAINT_START"] = "MAINT_START"
    device_id: str
    end: int

    @model_validator(mode="after")
    def ordered(self) -> "MaintenanceStart":
        if self.end <= self.time:
            raise ValueError("maintenance end must follow start")
        return self


class MaintenanceEnd(Record):
    kind: Literal["MAINT_END"] = "MAINT_END"
    device_id: str


class UrgentArrival(Record):
    kind: Literal["URGENT_ARRIVAL"] = "URGENT_ARRIVAL"
    event_json: str
    source: Literal["generated", "injected"]

    @model_validator(mode="after")
    def event_valid(self) -> "UrgentArrival":
        _snapshot(self.event_json, TypeAdapter(UrgentInsert))
        return self


class Injected(Record):
    kind: Literal["INJECTED"] = "INJECTED"
    event_json: str
    at: int = Field(ge=0)

    @model_validator(mode="after")
    def event_valid(self) -> "Injected":
        _snapshot(self.event_json, TypeAdapter(Event))
        if self.at < self.time:
            raise ValueError("injection cannot be scheduled in the past")
        event = _load(self.event_json)
        if event["type"] == "DEVICE_OUTAGE" and event["start"] != self.at:
            raise ValueError("outage start must equal injection time")
        return self


class TaskOverrunRecord(Record):
    kind: Literal["TASK_OVERRUN"] = "TASK_OVERRUN"
    task_id: str
    new_end: int


class DurationSampled(Record):
    kind: Literal["DURATION_SAMPLED"] = "DURATION_SAMPLED"
    task_id: str
    attempt: int = Field(ge=0)
    planned: int = Field(gt=0)
    actual: int = Field(gt=0)
    source: Literal["sampled", "replayed"]


class DeviceStateRecord(Record):
    kind: Literal["DEVICE_STATE"] = "DEVICE_STATE"
    device_id: str
    old: Literal["IDLE", "SETUP", "BUSY", "MAINTENANCE", "FAULT", "OFFLINE"]
    new: Literal["IDLE", "SETUP", "BUSY", "MAINTENANCE", "FAULT", "OFFLINE"]

    @model_validator(mode="after")
    def transition_valid(self) -> "DeviceStateRecord":
        if DeviceState(self.new) not in DEVICE_TRANSITIONS[DeviceState(self.old)]:
            raise ValueError("illegal device transition")
        return self


class TaskStateRecord(Record):
    kind: Literal["TASK_STATE"] = "TASK_STATE"
    task_id: str
    old: TaskState
    new: TaskState
    actual_start: int | None = None
    actual_end: int | None = None

    @model_validator(mode="after")
    def transition_valid(self) -> "TaskStateRecord":
        if self.new not in TASK_TRANSITIONS[self.old]:
            raise ValueError("illegal task transition")
        if self.actual_start is not None and self.actual_start < 0:
            raise ValueError("negative actual start")
        if self.actual_end is not None and (
            self.actual_start is None or self.actual_end <= self.actual_start
        ):
            raise ValueError("invalid actual end")
        if self.new == "DONE" and (self.actual_end != self.time or self.actual_start is None):
            raise ValueError("DONE requires actual start and end at current time")
        return self


class ReplanTriggered(Record):
    kind: Literal["REPLAN_TRIGGERED"] = "REPLAN_TRIGGERED"
    reason: str
    event_json: str | None = None

    @model_validator(mode="after")
    def event_valid(self) -> "ReplanTriggered":
        if self.event_json is not None:
            _snapshot(self.event_json, TypeAdapter(SimEvent))
        return self


class ReplanCalled(Record):
    kind: Literal["REPLAN_CALLED"] = "REPLAN_CALLED"
    events_json: str

    @model_validator(mode="after")
    def events_valid(self) -> "ReplanCalled":
        _snapshot(self.events_json, TypeAdapter(list[SimEvent]))
        return self


class ReplanResultRecord(Record):
    kind: Literal["REPLAN_RESULT"] = "REPLAN_RESULT"
    result: Literal["adopted", "rejected", "none"]
    plan_json: str | None = None
    plan_hash: str | None = None
    code: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def check_plan(self) -> "ReplanResultRecord":
        if self.result in ("adopted", "rejected"):
            if self.plan_json is None or self.plan_hash != content_hash(_load(self.plan_json)):
                raise ValueError("candidate result requires matching plan and hash")
            _snapshot(self.plan_json, TypeAdapter(Plan))
        elif self.plan_json is not None or self.plan_hash is not None:
            raise ValueError("none result cannot contain a plan")
        return self


class StartBlocked(Record):
    kind: Literal["START_BLOCKED"] = "START_BLOCKED"
    device_id: str
    task_id: str
    reason: str


class ReplanAbandoned(Record):
    kind: Literal["REPLAN_ABANDONED"] = "REPLAN_ABANDONED"
    reason: str


class EndRun(Record):
    """Terminal marker added to a result snapshot, never the persistent run log."""

    kind: Literal["END_RUN"] = "END_RUN"
    t_end: int = Field(ge=0)

    @model_validator(mode="after")
    def time_matches(self) -> "EndRun":
        if self.time != self.t_end:
            raise ValueError("end marker time must equal t_end")
        return self


SimEventRecord = Annotated[
    Union[
        Header,
        EventEnqueued,
        DeviceFault,
        DeviceRecover,
        MaintenanceStart,
        MaintenanceEnd,
        UrgentArrival,
        Injected,
        TaskOverrunRecord,
        DurationSampled,
        DeviceStateRecord,
        TaskStateRecord,
        ReplanTriggered,
        ReplanCalled,
        ReplanResultRecord,
        StartBlocked,
        ReplanAbandoned,
        EndRun,
    ],
    Field(discriminator="kind"),
]
_ADAPTER: TypeAdapter[SimEventRecord] = TypeAdapter(SimEventRecord)


def serialize_log(records: list[SimEventRecord]) -> bytes:
    """Return canonical UTF-8 JSONL, with a final newline per record."""
    return b"".join((canonical_json(record) + "\n").encode("utf-8") for record in records)


def parse_log(data: bytes) -> list[SimEventRecord]:
    """Reject ambiguous, noncanonical or structurally invalid JSONL."""
    text = data.decode("utf-8")
    if text and not text.endswith("\n"):
        raise ValueError("missing final newline")
    records: list[SimEventRecord] = []
    for line in text.splitlines():
        value = _load(line)
        record = _ADAPTER.validate_python(value)
        if canonical_json(record) != line:
            raise ValueError("noncanonical record")
        records.append(record)
    if serialize_log(records) != data:
        raise ValueError("noncanonical JSONL")
    return records


def log_hash(records: list[SimEventRecord]) -> str:
    """SHA-256 of serialized log bytes."""
    return hashlib.sha256(serialize_log(records)).hexdigest()


class ReplayMismatch(Exception):
    """First differing replay record, with expected and actual values."""

    def __init__(self, index: int, expected: Any, actual: Any) -> None:
        self.index = index
        self.expected = expected
        self.actual = actual
        super().__init__(f"replay mismatch at {index}: expected {expected!r}, actual {actual!r}")
