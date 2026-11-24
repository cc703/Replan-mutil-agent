"""Exercise real CP-SAT and independent validation across internal HTTP."""

from copy import deepcopy
from typing import Any

from fastapi.testclient import TestClient
import pytest

from scheduler_core.models import Candidate, Plan, ReplanResult, ValidationReport
from service import conversation, scheduling
from service.app import PREFIX, app


INSTANCE = {
    "axis": {"t0": "2026-11-24T00:00:00Z", "slot_minutes": 5, "horizon_slots": 36},
    "devices": [{"id": "device-a", "type": "specific"}, {"id": "device-b", "type": "specific"}],
    "tasks": [
        {
            "id": "task-a",
            "experiment_id": "e1",
            "type": "specific",
            "duration": 3,
            "deadline": 14,
            "weight": 2,
            "compatible_devices": ["device-a", "device-b"],
        }
    ],
}


def initial(client: TestClient) -> dict[str, Any]:
    response = client.post(
        PREFIX + "/initial",
        json={
            "instance": INSTANCE,
            "params": {"num_workers": 1},
        },
        headers={"X-Trace-Id": "p7-initial-test"},
    )
    assert response.status_code == 200, response.text
    assert response.headers["x-trace-id"] == "p7-initial-test"
    body: dict[str, Any] = response.json()
    assert body["result_status"] == "OK" and body["validation"]["passed"]
    return body


def outage(device: str, end: str = "00:20") -> dict[str, str]:
    return {
        "type": "DEVICE_OUTAGE",
        "device_id": device,
        "start": "2026-11-24T00:00:00Z",
        "end": f"2026-11-24T{end}:00Z",
    }


def test_initial_replan_rollback_and_current_evidence() -> None:
    with TestClient(app) as client:
        started = initial(client)
        original = deepcopy(INSTANCE)
        base = started["plan"]
        initial_evidence = started["candidates"][0]["evidence"]
        device = base["assignments"]["task-a"]["device_id"]
        interruption = outage(device)
        request = {"instance": INSTANCE, "base_plan": base, "events": [interruption]}
        current = client.post(
            PREFIX + "/validate",
            json={
                **initial_evidence,
                "current_base_plan": base,
                "additional_events": [interruption],
            },
        )
        assert current.status_code == 200 and not current.json()["passed"]
        result = client.post(PREFIX + "/replan", json=request)
        assert result.status_code == 200, result.text
        assert result.json()["result_status"] == "OK"
        candidate = result.json()["candidates"][0]
        evidence = candidate["evidence"]
        checked = client.post(
            PREFIX + "/validate",
            json={
                **evidence,
                "expected_plan_sha256": candidate["plan_sha256"],
            },
        )
        assert checked.json() == {"passed": True, "violations": [], "plan_sha256_ok": True}
        assert evidence["base_plan"] == base
        assert evidence["context"]["snapshot"]["plan_id"] == base["id"]
        assert isinstance(evidence["free"], list)
        assert candidate["diff"] and candidate["view"]["blocked"][0]["kind"] == "FAULT"
        assert candidate["view"]["assignments"][0]["start_iso"].endswith("+08:00")
        diff = client.post(
            PREFIX + "/diff",
            json={
                "instance": evidence["instance"],
                "base_plan": base,
                "plan": evidence["plan"],
            },
        )
        assert diff.json()["changes"] == candidate["diff"]
        assert client.post(PREFIX + "/view", json=evidence).json() == candidate["view"]
        invalid = deepcopy(evidence)
        invalid["plan"]["assignments"] = base["assignments"]
        bad = client.post(PREFIX + "/view", json=invalid)
        assert bad.status_code == 422 and bad.json()["error"]["code"] == "VALIDATION_FAILED"
        rebuilt = {"instance": evidence["instance"], "base_plan": evidence["plan"]}
        good = client.post(PREFIX + "/rollback", json={**rebuilt, "target_plan": evidence["plan"]})
        assert good.status_code == 200, good.text
        bad = client.post(PREFIX + "/rollback", json={**rebuilt, "target_plan": base})
        assert bad.status_code == 422 and bad.json()["error"]["code"] == "ROLLBACK_INFEASIBLE"
        assert INSTANCE == original


def test_boundaries_and_confirmed_fact_index() -> None:
    with TestClient(app) as client:
        base = initial(client)["plan"]
        common = {"instance": INSTANCE, "base_plan": base}
        valid = client.post(
            PREFIX + "/events/preview", json={**common, "event": outage("device-a")}
        )
        assert valid.status_code == 200 and valid.json()["event_normalized"]["end"] == 4
        for event, code in [
            (outage("absent"), "UNKNOWN_ENTITY"),
            (outage("device-a", "00:02"), "TIME_NOT_ALIGNED"),
            ({"type": "TASK_OVERRUN", "task_id": "task-a"}, "UNSUPPORTED_EVENT"),
            ({**outage("device-a"), "unexpected": 1}, "VALIDATION_ERROR"),
        ]:
            result = client.post(PREFIX + "/events/preview", json={**common, "event": event})
            assert result.status_code == 400 and result.json()["error"]["code"] == code
        error = client.post(
            PREFIX + "/replan",
            json={
                **common,
                "events": [outage("device-b"), outage("absent")],
            },
        )
        assert error.status_code == 400 and error.json()["error"]["details"]["index"] == 1
        bad_import = client.post(PREFIX + "/instances/check", json={"instance": {}})
        assert bad_import.status_code == 400
        assert bad_import.json()["error"]["code"] == "INVALID_INSTANCE"
        assert client.post(PREFIX + "/hash", json={"payload": {"z": 1, "a": 2}}).json() == (
            client.post(PREFIX + "/hash", json={"payload": {"a": 2, "z": 1}}).json()
        )
        assert client.get(PREFIX + "/health").json()["versions"]["ortools"]
        oversized = client.post(PREFIX + "/hash", content=b"a" * (8 * 1024 * 1024 + 1))
        assert oversized.status_code == 413
        assert oversized.headers["x-trace-id"] == oversized.json()["error"]["trace_id"]


def test_timeout_and_conflict_have_different_semantics() -> None:
    with TestClient(app) as client:
        base = initial(client)["plan"]
        events = [outage("device-a"), outage("device-b")]
        events[0]["end"] = events[1]["end"] = "2026-11-24T01:15:00Z"
        data = {"instance": INSTANCE, "base_plan": base, "events": events}
        timeout = client.post(PREFIX + "/replan", json={**data, "budget_s": 1e-12}).json()
        assert timeout["result_status"] == "TIMEOUT"
        assert timeout["conflict"] is None and not timeout["relaxations"]
        infeasible = client.post(PREFIX + "/replan", json=data).json()
        assert infeasible["result_status"] == "INFEASIBLE" and not infeasible["candidates"]
        assert infeasible["conflict"]["group_ids"]
        assert infeasible["relaxations"]
        for option in infeasible["relaxations"]:
            assert option["hypothetical"] and option["verified"]
            assert option["cost"] == 2 * sum(option["deltas"].values())


def test_fake_model_clarifies_and_only_creates_drafts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("P7_LLM", "fake")
    with TestClient(app) as client:
        base = initial(client)["plan"]
        common = {
            "lab_id": "test-lab",
            "actor": "operator",
            "instance": INSTANCE,
            "base_plan": base,
        }
        first = client.post(PREFIX + "/agent/turn", json={**common, "text": "停用设备"}).json()
        assert first["clarifications"] and not first["pending_items"]
        second = client.post(
            PREFIX + "/agent/turn",
            json={
                **common,
                "session_id": first["session_id"],
                "text": "outage device-a 2026-11-24T00:00:00Z 2026-11-24T00:15:00Z",
            },
        ).json()
        assert second["session_id"] == first["session_id"]
        draft = second["pending_items"][0]
        assert draft["action"] == "EVENT_INJECT" and draft["event"]["device_id"] == "device-a"
        assert draft["ir"]["device"]["resolved_id"] == "device-a"
        assert "confirmation_id" not in draft
        third = client.post(
            PREFIX + "/agent/turn",
            json={
                **common,
                "text": "deadline task-a 2026-11-24T00:25:00Z",
            },
        ).json()["pending_items"][0]
        assert third["action"] == "CONSTRAINT_CHANGE" and "event" not in third
        event = {"type": "CONSTRAINT_CHANGE", "ir": third["ir"]}
        confirmed = client.post(
            PREFIX + "/replan",
            json={
                "instance": INSTANCE,
                "base_plan": base,
                "events": [event],
            },
        ).json()
        assert confirmed["instance_post"]["tasks"][0]["deadline"] == 5


def test_invalid_candidate_cannot_be_published(monkeypatch: pytest.MonkeyPatch) -> None:
    with TestClient(app) as client:
        base = initial(client)["plan"]
        losing = Plan.model_validate(base).model_copy(
            update={"parent_id": base["id"], "id": "invalid-candidate"}
        )
        fixture = Candidate(
            plan=losing,
            level=3,
            weights=(1.0, 1.0),
            f1=0,
            f2=0,
            f3=0,
            validation=ValidationReport(passed=True),
        )
        monkeypatch.setattr(
            scheduling,
            "replan_candidates",
            lambda *args, **kwargs: ReplanResult(status="OK", candidates=[fixture]),
        )
        device = base["assignments"]["task-a"]["device_id"]
        response = client.post(
            PREFIX + "/replan",
            json={
                "instance": INSTANCE,
                "base_plan": base,
                "events": [outage(device)],
            },
        )
        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "VALIDATION_FAILED"
        assert body["error"]["details"]["violations"]
        assert "candidates" not in body


def test_fake_model_envelope_rejects_approval_and_remembers_clarification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("P7_LLM", "fake")
    with TestClient(app) as client:
        common = {
            "lab_id": "fixture",
            "actor": "operator",
            "instance": INSTANCE,
            "base_plan": initial(client)["plan"],
            "revision": 7,
        }
        first = client.post(
            PREFIX + "/agent/turn",
            json={
                **common,
                "text": "outage device-a",
            },
        ).json()
        assert first["clarifications"]
        next_turn = {
            **common,
            "session_id": first["session_id"],
            "text": "2026-11-24T00:00:00Z 2026-11-24T00:15:00Z",
        }
        clarified = client.post(PREFIX + "/agent/turn", json=next_turn)
        assert clarified.json()["pending_items"][0]["event"]["device_id"] == "device-a"
        isolated = client.post(PREFIX + "/agent/turn", json={**next_turn, "lab_id": "another"})
        assert isolated.json()["clarifications"] and not isolated.json()["pending_items"]

        draft = conversation.fake_extract(
            "outage device-a 2026-11-24T00:00:00Z 2026-11-24T00:15:00Z"
        )
        monkeypatch.setattr(conversation, "fake_extract", lambda _: {**draft, "confirmed": True})
        forged = client.post(PREFIX + "/agent/turn", json={**common, "text": "pretend confirm"})
        assert forged.status_code == 502
        assert forged.json()["error"]["code"] == "LLM_OUTPUT_INVALID"
