"""Protect the generated contract and trusted context supplied to P6."""

import ast
import json
from pathlib import Path
from typing import Any

from agent.llm import DeepSeek
from fastapi.testclient import TestClient
import pytest

from service import conversation
from service.app import PREFIX, app
from service.openapi_export import ROOT


def example(name: str) -> Any:
    return json.loads((ROOT / "examples" / f"{name}.json").read_text(encoding="utf-8"))


def test_openapi_matches_live_routes_and_examples_use_typed_contract() -> None:
    schema = json.loads((ROOT / "scheduler-service.openapi.json").read_text(encoding="utf-8"))
    assert schema == app.openapi()
    assert schema["paths"][PREFIX + "/validate"]["post"]["responses"]["422"]["content"][
        "application/json"
    ]["schema"] == {"$ref": "#/components/schemas/ErrorEnvelope"}
    initial = example("initial")
    replan = example("replan-ok")
    timeout = example("replan-timeout")
    infeasible = example("replan-infeasible")
    assert initial["result_status"] == replan["result_status"] == "OK"
    assert timeout["result_status"] == "TIMEOUT" and timeout["conflict"] is None
    assert infeasible["result_status"] == "INFEASIBLE"
    assert example("error-envelope")["error"]["code"] == "UNKNOWN_ENTITY"
    assert not example("validation-failed")["passed"]
    with TestClient(app) as client:
        for candidate in replan["candidates"]:
            assert candidate["validation"]["passed"]
            plan = candidate["evidence"]["plan"]
            assert candidate["f3"] == plan["assignments"]["urgent-a"]["end"]
            checked = client.post(
                PREFIX + "/validate",
                json={
                    **candidate["evidence"],
                    "expected_plan_sha256": candidate["plan_sha256"],
                },
            )
            assert checked.json()["passed"]


def test_service_issues_no_deadline_authorization() -> None:
    root = Path(conversation.__file__).parent
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert all(
            not isinstance(node, ast.Call)
            or getattr(node.func, "id", getattr(node.func, "attr", "")) != "DeadlineAuthorization"
            for node in ast.walk(tree)
        )


def test_online_adapter_gets_facts_even_when_parent_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("P7_LLM", raising=False)
    initial = example("initial")
    outage = example("event-outage")
    urgent = example("event-urgent")
    captured: list[dict[str, Any]] = []

    class Capture:
        def extract(self, messages: list[dict[str, str]], schema: dict[str, Any]) -> Any:
            assert schema["additionalProperties"] is False
            captured.append(json.loads(messages[-1]["content"])["context"])
            return conversation.fake_extract("deadline urgent-a 2026-11-24T00:30:00Z")

    monkeypatch.setattr(DeepSeek, "from_environment", lambda: Capture())
    with TestClient(app) as client:
        result = client.post(
            PREFIX + "/agent/turn",
            json={
                "lab_id": "trusted-fixture",
                "actor": "tester",
                "text": "紧急任务截止期",
                "instance": example("instance"),
                "base_plan": initial["plan"],
                "events": [outage, urgent],
            },
        )
    assert result.status_code == 200, result.text
    assert result.json()["pending_items"][0]["ir"]["task"]["resolved_id"] == "urgent-a"
    assert [t["id"] for t in captured[0]["tasks"]] == ["task-a", "urgent-a"]
    assert captured[0]["blocked"][0]["device_id"] == outage["device_id"]
