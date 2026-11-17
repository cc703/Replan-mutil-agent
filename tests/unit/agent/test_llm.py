"""Transport stubs verify model lookup, bounded failure and secret redaction."""

import json
from typing import Any

import pytest

from agent.llm import DeepSeek, online_extractor, online_router
from agent.explain import Fact, explain
from tests.unit.agent.test_store import make_world


def test_model_lookup_and_tool_call() -> None:
    calls: list[tuple[str, bytes | None, float]] = []

    def transport(url: str, headers: dict[str, str], body: bytes | None, timeout: float) -> bytes:
        calls.append((url, body, timeout))
        if body is None:
            return b'{"data":[{"id":"deepseek-flash"}]}'
        return (
            b'{"choices":[{"message":{"tool_calls":[{"function":{"arguments":"{\\"x\\":1}"}}]}}]}'
        )

    client = DeepSeek("secret", transport)
    assert client.extract([{"role": "user", "content": "test"}], {}) == {"x": 1}
    body = json.loads(calls[1][1] or b"{}")
    assert body["temperature"] == 0 and body["thinking"] == {"type": "disabled"}
    assert calls[0][0].endswith("/models") and calls[1][2] > 0


def test_model_lookup_failure_is_redacted() -> None:
    def failure(url: str, headers: dict[str, str], body: bytes | None, timeout: float) -> bytes:
        raise OSError("secret")

    with pytest.raises(RuntimeError, match="DeepSeek request failed") as exc:
        DeepSeek("secret", failure)
    assert "secret" not in str(exc.value)


def test_missing_configured_model_stops_online_mode() -> None:
    with pytest.raises(RuntimeError, match="unavailable"):
        DeepSeek("key", lambda *args: b'{"data":[]}')


def test_evidence_explanation_retries_then_uses_valid_claim() -> None:
    bodies: list[dict[str, Any]] = []

    def transport(url: str, headers: dict[str, str], body: bytes | None, timeout: float) -> bytes:
        if body is None:
            return b'{"data":[{"id":"deepseek-flash"}]}'
        request = json.loads(body)
        bodies.append(request)
        unit = "槽" if len(bodies) == 1 else "分钟"
        claims = {"claims": [{"key": "延后", "kind": "number", "value": 10, "unit": unit}]}
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {"function": {"arguments": json.dumps(claims, ensure_ascii=False)}}
                            ]
                        }
                    }
                ]
            },
            ensure_ascii=False,
        ).encode()

    client = DeepSeek("private", transport)
    facts = {"延后": Fact("number", 10, "分钟")}
    result = explain(facts, lambda: client.explain_claims(facts))
    assert not result.fallback and result.text == "延后：10分钟。"
    assert (result.correct, result.total) == (1, 2) and len(bodies) == 2
    assert bodies[0]["thinking"] == {"type": "disabled"}
    assert bodies[0]["tools"][0]["function"]["name"] == "explain_evidence"


def test_fabricated_extra_text_is_rejected() -> None:
    def transport(url: str, headers: dict[str, str], body: bytes | None, timeout: float) -> bytes:
        if body is None:
            return b'{"data":[{"id":"deepseek-flash"}]}'
        response = {"claims": [], "text": "invented fact"}
        return json.dumps(
            {
                "choices": [
                    {"message": {"tool_calls": [{"function": {"arguments": json.dumps(response)}}]}}
                ]
            }
        ).encode()

    client = DeepSeek("key", transport)
    with pytest.raises(RuntimeError, match="invalid"):
        client.explain_claims({"delay": Fact("number", 5, "min")})


def test_online_router_uses_versioned_prompt_and_restricts_actions() -> None:
    seen: list[dict[str, Any]] = []

    def transport(url: str, headers: dict[str, str], body: bytes | None, timeout: float) -> bytes:
        if body is None:
            return b'{"data":[{"id":"deepseek-flash"}]}'
        request = json.loads(body)
        seen.append(request)
        data = {"action": "query"}
        return json.dumps(
            {
                "choices": [
                    {"message": {"tool_calls": [{"function": {"arguments": json.dumps(data)}}]}}
                ]
            }
        ).encode()

    assert online_router(DeepSeek("key", transport))("what is planned?") == {"action": "query"}
    assert seen[0]["tools"][0]["function"]["name"] == "route_request"
    assert "never constitutes permission" in seen[0]["messages"][0]["content"]


@pytest.mark.parametrize(
    "suggestion",
    [
        {"action": "query", "confirmed": True},
        {"action": "rollback", "target": 42},
        {"action": "erase"},
    ],
)
def test_online_router_rejects_invalid_suggestions(suggestion: dict[str, Any]) -> None:
    def transport(url: str, headers: dict[str, str], body: bytes | None, timeout: float) -> bytes:
        if body is None:
            return b'{"data":[{"id":"deepseek-flash"}]}'
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [{"function": {"arguments": json.dumps(suggestion)}}]
                        }
                    }
                ]
            }
        ).encode()

    with pytest.raises(RuntimeError, match="invalid"):
        online_router(DeepSeek("key", transport))("request")


def test_online_extractor_receives_trusted_directory_and_business_clock() -> None:
    seen: list[dict[str, Any]] = []

    def transport(url: str, headers: dict[str, str], body: bytes | None, timeout: float) -> bytes:
        if body is None:
            return b'{"data":[{"id":"deepseek-flash"}]}'
        seen.append(json.loads(body))
        return b'{"choices":[{"message":{"tool_calls":[{"function":{"arguments":"{\\"changes\\":[]}"}}]}}]}'

    world = make_world()
    client = DeepSeek("key", transport)
    online_extractor(client, world)("明天操作设备")
    context = json.loads(seen[0]["messages"][1]["content"])["context"]
    assert context["devices"][0]["id"] == "d" and context["now_slot"] == 0
    assert context["now_utc"].endswith("+00:00") and context["duration_unit"] == "minutes"
