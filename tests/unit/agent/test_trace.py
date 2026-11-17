"""The persisted trace contains metadata, never the supplied prompt or secrets."""

from pathlib import Path
import json
import hashlib
from typing import Any

import agent.trace as trace_module
from scheduler_core.io.artifacts import ArtifactStore
from scheduler_core.io.manifest import GitInfo
from agent.llm import DeepSeek, online_router
from agent.explain import Fact


def test_trace_redacts_prompt_and_limits_fields(tmp_path: Path, monkeypatch: object) -> None:
    from pytest import MonkeyPatch

    assert isinstance(monkeypatch, MonkeyPatch)
    monkeypatch.setattr(trace_module, "ArtifactStore", lambda: ArtifactStore(tmp_path))
    monkeypatch.setattr(
        "scheduler_core.io.artifacts.git_info", lambda _: GitInfo(commit="a" * 40, dirty=True)
    )
    trace = trace_module.Trace("offline", b"private-sentinel")
    trace.record("extract", elapsed_ms=1.0, tokens=None, schema_ok=True, status="ok")
    trace.explanation(1, 2, True)
    trace.finish({})
    combined = b"".join(path.read_bytes() for path in trace.run.dir.iterdir() if path.is_file())
    assert b"private-sentinel" not in combined
    assert b'"fallback_rate": 1.0' in combined


def test_actual_call_usage_and_prompt_hashes_are_recorded(
    tmp_path: Path, monkeypatch: object
) -> None:
    from pytest import MonkeyPatch

    assert isinstance(monkeypatch, MonkeyPatch)
    monkeypatch.setattr(trace_module, "ArtifactStore", lambda: ArtifactStore(tmp_path))
    monkeypatch.setattr(
        "scheduler_core.io.artifacts.git_info", lambda _: GitInfo(commit="a" * 40, dirty=True)
    )
    trace = trace_module.Trace("online", b"prompt")

    def transport(url: str, headers: dict[str, str], body: bytes | None, timeout: float) -> bytes:
        if body is None:
            return b'{"data":[{"id":"deepseek-flash"}]}'
        request = json.loads(body)
        name = request["tools"][0]["function"]["name"]
        data: dict[str, Any] = (
            {"action": "query"}
            if name == "route_request"
            else {"claims": [{"key": "k", "kind": "number", "value": 1, "unit": "个"}]}
            if name == "explain_evidence"
            else {"changes": []}
        )
        return json.dumps(
            {
                "usage": {"prompt_tokens": 7, "completion_tokens": 4, "total_tokens": 11},
                "choices": [
                    {"message": {"tool_calls": [{"function": {"arguments": json.dumps(data)}}]}}
                ],
            }
        ).encode()

    client = DeepSeek("sensitive-key", transport, trace)
    online_router(client)("private request")
    client.extract([{"role": "user", "content": "private request"}], {})
    client.explain_claims({"k": Fact("number", 1, "个")})
    trace.finish({})
    raw = (trace.run.dir / "trace.json").read_text("utf-8")
    assert "sensitive-key" not in raw and "private request" not in raw
    calls = [event for event in json.loads(raw)["events"] if event["source"] == "model_call"]
    assert {event["node"] for event in calls} == {"route", "extract", "explain"}
    for event in calls:
        prompt = Path("src/agent/prompts") / event["node"] / "v001.md"
        assert event["prompt_hash"] == hashlib.sha256(prompt.read_bytes()).hexdigest()
        assert (event["tokens"], event["input_tokens"], event["output_tokens"]) == (11, 7, 4)
