"""DeepSeek transport boundary; secrets and server errors never enter traces."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
import json
import os
import time
from pathlib import Path
from typing import Any, cast
from urllib.error import URLError
from urllib.request import Request, urlopen

import yaml

from .explain import Claim, ClaimResponse, Fact
from .trace import Trace
from .store import WorldStore
from .routing import RouteSuggestion

Transport = Callable[[str, dict[str, str], bytes | None, float], bytes]


def _http(url: str, headers: dict[str, str], body: bytes | None, timeout: float) -> bytes:
    request = Request(url, data=body, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return cast(bytes, response.read())


class DeepSeek:
    """Explicit online client; construction checks the configured model exists."""

    def __init__(self, key: str, transport: Transport = _http, trace: Trace | None = None) -> None:
        config = yaml.safe_load(Path(__file__).with_name("defaults.yaml").read_text("utf-8"))["llm"]
        self.model: str = config["model"]
        self.base: str = config["base_url"].rstrip("/")
        self.timeout: float = float(config["timeout_seconds"])
        self.max_tokens: int = int(config["max_tokens"])
        self.retries: int = int(config["retries"])
        self._transport = transport
        self.trace = trace
        self._headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        if not key:
            raise ValueError("DEEPSEEK_API_KEY is required")
        data = self._request("/models", None)
        if self.model not in {item.get("id") for item in data.get("data", [])}:
            raise RuntimeError("configured DeepSeek model is unavailable")

    @classmethod
    def from_environment(cls, trace: Trace | None = None) -> DeepSeek:
        return cls(os.environ.get("DEEPSEEK_API_KEY", ""), trace=trace)

    def _request(self, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        raw = None if body is None else json.dumps(body).encode("utf-8")
        started = time.perf_counter()
        name = body.get("tools", [{}])[0].get("function", {}).get("name", "") if body else ""
        node = {
            "extract_change": "extract",
            "route_request": "route",
            "explain_evidence": "explain",
        }.get(name)
        status = "failed"
        tokens: int | None = None
        input_tokens: int | None = None
        output_tokens: int | None = None
        try:
            result = json.loads(self._transport(self.base + path, self._headers, raw, self.timeout))
            if not isinstance(result, dict):
                raise ValueError("invalid response")
            usage = result.get("usage")
            total = usage.get("total_tokens") if isinstance(usage, dict) else None
            if isinstance(total, int) and not isinstance(total, bool) and total >= 0:
                tokens = total
            prompt_tokens = usage.get("prompt_tokens") if isinstance(usage, dict) else None
            completion_tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
            if (
                isinstance(prompt_tokens, int)
                and not isinstance(prompt_tokens, bool)
                and prompt_tokens >= 0
            ):
                input_tokens = prompt_tokens
            if (
                isinstance(completion_tokens, int)
                and not isinstance(completion_tokens, bool)
                and completion_tokens >= 0
            ):
                output_tokens = completion_tokens
            status = "ok"
            return result
        except (URLError, OSError, ValueError, TypeError):
            raise RuntimeError("DeepSeek request failed") from None
        finally:
            if self.trace and node:
                self.trace.record(
                    node,
                    elapsed_ms=(time.perf_counter() - started) * 1000,
                    tokens=tokens,
                    schema_ok=None,
                    status=status,
                    source="model_call",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

    def extract(self, messages: list[dict[str, str]], schema: dict[str, Any]) -> dict[str, Any]:
        """Request one tool call; return its JSON arguments after bounded retries."""
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "thinking": {"type": "disabled"},
            "max_tokens": self.max_tokens,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "extract_change",
                        "description": "Extract change",
                        "parameters": schema,
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": "extract_change"}},
        }
        for _ in range(self.retries + 1):
            try:
                result = self._request("/chat/completions", body)
                arguments = result["choices"][0]["message"]["tool_calls"][0]["function"][
                    "arguments"
                ]
                parsed = json.loads(arguments)
                if isinstance(parsed, dict) and parsed:
                    return parsed
            except (RuntimeError, KeyError, IndexError, TypeError, ValueError):
                pass
        raise RuntimeError("extraction failed; use structured form")

    def explain_claims(self, facts: dict[str, Fact]) -> list[Claim]:
        """Request one structured claim response; retry policy belongs to the verifier."""
        root = Path(__file__).parent / "prompts" / "explain"
        prompt = (root / "v001.md").read_text(encoding="utf-8")
        schema = json.loads((root / "v001.schema.json").read_text(encoding="utf-8"))
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {key: asdict(fact) for key, fact in facts.items()}, ensure_ascii=False
                    ),
                },
            ],
            "temperature": 0,
            "thinking": {"type": "disabled"},
            "max_tokens": self.max_tokens,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "explain_evidence",
                        "description": "Select verified evidence claims",
                        "parameters": schema,
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": "explain_evidence"}},
        }
        try:
            result = self._request("/chat/completions", body)
            arguments = result["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
            return ClaimResponse.model_validate_json(arguments).claims
        except (KeyError, IndexError, TypeError, ValueError):
            raise RuntimeError("explanation response invalid") from None


def online_explainer(client: DeepSeek | None = None) -> Callable[[dict[str, Fact]], list[Claim]]:
    """Bind the evidence-only model interface after online model verification."""
    checked_client = client or DeepSeek.from_environment()
    return checked_client.explain_claims


def online_extractor(
    client: DeepSeek | None = None, store: WorldStore | None = None
) -> Callable[[str], dict[str, Any]]:
    """Create an online extractor only after the model-list startup check succeeds."""
    checked_client = client or DeepSeek.from_environment()
    root = Path(__file__).parent / "prompts" / "extract"
    prompt = (root / "v001.md").read_text(encoding="utf-8")
    schema = json.loads((root / "v001.schema.json").read_text(encoding="utf-8"))

    def extract(text: str) -> dict[str, Any]:
        if store is None:
            raise ValueError("trusted session context is required")
        instance = store.instance
        context = {
            "devices": [device.model_dump(mode="json") for device in instance.devices],
            "tasks": [{"id": task.id, "type": task.type} for task in instance.tasks],
            "aliases": {name: sorted(ids) for name, ids in store.aliases.items()},
            "axis": instance.axis.model_dump(mode="json"),
            "now_slot": instance.now,
            "now_utc": instance.axis.to_dt(instance.now).isoformat(),
            "display_timezone": "Asia/Shanghai",
            "duration_unit": "minutes",
        }
        return checked_client.extract(
            [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"request": text, "context": context}, ensure_ascii=False
                    ),
                },
            ],
            schema,
        )

    return extract


def online_router(client: DeepSeek) -> Callable[[str], dict[str, str]]:
    """Return only a route suggestion; writes still require independent approval."""
    prompt = (Path(__file__).parent / "prompts" / "route" / "v001.md").read_text("utf-8")
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["action"],
        "properties": {
            "action": {"enum": ["change", "query", "rollback"]},
            "target": {"type": "string"},
        },
    }

    def route(text: str) -> dict[str, str]:
        body = {
            "model": client.model,
            "temperature": 0,
            "thinking": {"type": "disabled"},
            "max_tokens": client.max_tokens,
            "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": text}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "route_request",
                        "description": "Suggest a route",
                        "parameters": schema,
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": "route_request"}},
        }
        try:
            result = client._request("/chat/completions", body)
            data = json.loads(
                result["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
            )
            suggestion = RouteSuggestion.model_validate(data)
            return suggestion.model_dump(exclude_unset=True)
        except (KeyError, IndexError, TypeError, ValueError):
            raise RuntimeError("route response invalid") from None

    return route
