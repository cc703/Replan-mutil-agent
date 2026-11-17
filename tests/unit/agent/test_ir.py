"""Untrusted proposals cannot silently become hard constraints."""

from datetime import datetime, timezone
import json
from typing import Any

import pytest
from pydantic import ValidationError

from agent.ir import check_proposal, normalize_relative, parse_draft, proposal_adapter
from scheduler_core.axis import TimeAxis
from scheduler_core.models import Device, Instance


def test_outage_requires_known_reference_and_aligned_time() -> None:
    instance = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=24),
        devices=[Device(id="d1", type="x")],
        tasks=[],
    )
    payload: dict[str, Any] = {
        "kind": "DEVICE_OUTAGE",
        "strength": "HARD",
        "device": {"original": "d1", "resolved_id": "d1", "confidence": 1.0},
        "start": "2026-01-01T00:05:00Z",
        "end": "2026-01-01T00:15:00Z",
    }
    proposal = proposal_adapter.validate_json(json.dumps(payload))
    check_proposal(proposal, instance)
    payload["strength"] = "SOFT"
    with pytest.raises(ValueError, match="soft preference"):
        check_proposal(proposal_adapter.validate_json(json.dumps(payload)), instance)
    payload["strength"] = "HARD"
    payload["end"] = "2026-01-01T00:16:00Z"
    with pytest.raises(ValueError, match="unaligned"):
        check_proposal(proposal_adapter.validate_json(json.dumps(payload)), instance)
    payload["confirmed"] = True
    with pytest.raises(ValidationError):
        proposal_adapter.validate_json(json.dumps(payload))


def test_relative_time_uses_business_clock_and_aliases_must_be_unique() -> None:
    instance = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=400),
        devices=[Device(id="d1", type="x"), Device(id="d2", type="x")],
        tasks=[],
    )
    payload: dict[str, Any] = {
        "kind": "DEVICE_OUTAGE",
        "strength": "HARD",
        "device": {"original": "仪器", "resolved_id": "d1", "confidence": 1.0},
        "start": "今天 09:00",
        "end": "今天 09:05",
    }
    draft = normalize_relative(payload, instance)
    proposal = proposal_adapter.validate_json(json.dumps(draft, ensure_ascii=False))
    check_proposal(proposal, instance, {"仪器": {"d1"}})
    with pytest.raises(ValueError, match="clarification"):
        check_proposal(proposal, instance, {"仪器": {"d1", "d2"}})
    payload["device"] = {"original": "仪器", "resolved_id": None, "confidence": 1.0}
    normalized, _ = parse_draft(payload, instance, {"仪器": {"d1"}})
    assert isinstance(normalized["device"], dict)
    assert normalized["device"]["resolved_id"] == "d1"
    payload["device"] = {"original": "仪器", "resolved_id": "d1", "confidence": 1.0}
    with pytest.raises(ValueError, match="clarification"):
        parse_draft(payload, instance, {"仪器": {"d1", "d2"}})
