"""Tests of canonical log snapshots and strict interchange."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from scheduler_core.axis import TimeAxis
from scheduler_core.models import Device, Instance, Plan
from simulator.events import EventKind, SimEvent
from simulator.scenarios import Scenario
from simulator.log import (
    DeviceFault,
    EventEnqueued,
    DurationSampled,
    Header,
    ReplayMismatch,
    ReplanResultRecord,
    SimEventRecord,
    canonical_json,
    content_hash,
    log_hash,
    parse_log,
    serialize_log,
)


def test_snapshot_and_round_trip() -> None:
    device = Device(id="d", type="x", capabilities={"b", "a"})
    instance = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=10),
        devices=[device],
        tasks=[],
    )
    scene, plan = Scenario(), Plan(id="p", assignments={})
    snapshot = canonical_json(instance)
    record = Header(
        index=0,
        time=0,
        priority=0,
        seq=0,
        seed=1,
        version="1",
        scene_json=canonical_json(scene),
        instance_json=snapshot,
        plan_json=canonical_json(plan),
        scene_hash=content_hash(scene),
        instance_hash=content_hash(instance),
        plan_hash=content_hash(plan),
    )
    device.capabilities.add("c")
    assert record.instance_json == snapshot
    assert '"capabilities":["a","b"]' in snapshot
    records: list[SimEventRecord] = [
        record,
        DeviceFault(index=1, time=1, priority=3, seq=1, device_id="d", end=3, source="generated"),
    ]
    assert serialize_log(parse_log(serialize_log(records))) == serialize_log(records)
    assert log_hash(records) == log_hash(parse_log(serialize_log(records)))


@pytest.mark.parametrize(
    "data",
    [
        b'{"index":0,"index":0}\n',
        b'{"x":NaN}\n',
        b"{}\n",
        b"{}\r\n",
        b'{ "kind":"DEVICE_FAULT"}\n',
        b"\n",
        b"{}",
    ],
)
def test_reject_bad_jsonl(data: bytes) -> None:
    with pytest.raises((ValueError, ValidationError)):
        parse_log(data)


def test_strict_and_adoption() -> None:
    with pytest.raises(ValidationError):
        DurationSampled(
            index=True,
            time=0,
            priority=0,
            seq=0,
            task_id="t",
            attempt=0,
            planned=1,
            actual=1,
            source="sampled",
        )
    with pytest.raises(ValidationError):
        ReplanResultRecord(index=0, time=0, priority=0, seq=0, result="adopted")
    mismatch = ReplayMismatch(3, "a", "b")
    assert (mismatch.index, mismatch.expected, mismatch.actual) == (3, "a", "b")


def test_header_rejects_invalid_or_tampered_snapshots() -> None:
    scene = Scenario()
    instance = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=10),
        devices=[],
        tasks=[],
    )
    plan = Plan(id="p", assignments={})
    fields = dict(
        index=0,
        time=0,
        priority=0,
        seq=0,
        seed=1,
        version="1",
        scene_json=canonical_json(scene),
        instance_json=canonical_json(instance),
        plan_json=canonical_json(plan),
        scene_hash=content_hash(scene),
        instance_hash=content_hash(instance),
        plan_hash=content_hash(plan),
    )
    with pytest.raises(ValidationError):
        Header.model_validate(fields | {"plan_hash": "0" * 64})
    with pytest.raises(ValidationError):
        Header.model_validate(fields | {"plan_json": "{}", "plan_hash": content_hash({})})


def test_adopted_plan_round_trip_and_hash_validation() -> None:
    plan = Plan(id="p", assignments={})
    record = ReplanResultRecord(
        index=0,
        time=1,
        priority=6,
        seq=1,
        result="adopted",
        plan_json=canonical_json(plan),
        plan_hash=content_hash(plan),
    )
    assert parse_log(serialize_log([record])) == [record]
    with pytest.raises(ValidationError):
        ReplanResultRecord(
            index=0,
            time=1,
            priority=6,
            seq=1,
            result="adopted",
            plan_json=canonical_json(plan),
            plan_hash="bad",
        )


def test_enqueue_snapshot_preserves_future_event_and_sequence() -> None:
    event = SimEvent(
        time=50, kind=EventKind.TASK_START, device_id="d", task_id="t", seq=19, plan_epoch=2
    )
    record = EventEnqueued(
        index=1, time=0, priority=6, seq=0, event_json=canonical_json(event), source="plan"
    )
    parsed = parse_log(serialize_log([record]))
    assert parsed == [record]
    assert SimEvent.model_validate_json(record.event_json) == event
    with pytest.raises(ValidationError):
        EventEnqueued(index=1, time=0, priority=6, seq=0, event_json="{}", source="plan")
    with pytest.raises(ValidationError):
        EventEnqueued.model_validate(
            {
                "index": 1,
                "time": 0,
                "priority": 6,
                "seq": 0,
                "event_json": canonical_json(event),
                "source": "unknown",
            }
        )


def test_rejected_candidate_is_complete_and_replayable() -> None:
    plan = Plan(id="candidate", parent_id="base", assignments={})
    record = ReplanResultRecord(
        index=3,
        time=4,
        priority=6,
        seq=8,
        result="rejected",
        plan_json=canonical_json(plan),
        plan_hash=content_hash(plan),
        code="V1",
        reason="missing task",
    )
    assert parse_log(serialize_log([record])) == [record]
    with pytest.raises(ValidationError):
        ReplanResultRecord(index=3, time=4, priority=6, seq=8, result="rejected")
    with pytest.raises(ValidationError):
        ReplanResultRecord(
            index=3,
            time=4,
            priority=6,
            seq=8,
            result="rejected",
            plan_json=canonical_json(plan),
            plan_hash="bad",
        )
    with pytest.raises(ValidationError):
        ReplanResultRecord(
            index=3,
            time=4,
            priority=6,
            seq=8,
            result="none",
            plan_json=canonical_json(plan),
            plan_hash=content_hash(plan),
        )
