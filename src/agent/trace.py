"""Persist only whitelisted execution metadata, never prompt or response text."""

import hashlib
from importlib.metadata import version
from collections.abc import Mapping
from pathlib import Path

import yaml

from scheduler_core.io.artifacts import ArtifactStore, Run


class Trace:
    def __init__(self, mode: str, prompt: bytes) -> None:
        if mode not in {"offline", "online"}:
            raise ValueError("invalid trace mode")
        self._hash = hashlib.sha256(prompt).hexdigest()
        self._prompt_hashes = {
            name: hashlib.sha256(
                (Path(__file__).parent / "prompts" / name / "v001.md").read_bytes()
            ).hexdigest()
            for name in ("route", "extract", "explain")
        }
        config = Path(__file__).with_name("defaults.yaml").read_bytes()
        model = yaml.safe_load(config)["llm"]["model"]
        self.run: Run = ArtifactStore().new_run(
            "agent_eval",
            "session",
            mode,
            command="agent session",
            config=config,
            versions={"langgraph": version("langgraph")},
            metadata={"mode": mode, "prompt_version": "v001", "configured_model": model},
        )
        self._events: list[dict[str, str | int | float | bool | None]] = []
        self._metrics = {"claims_correct": 0, "claims_total": 0, "fallbacks": 0, "explanations": 0}

    def record(
        self,
        node: str,
        *,
        elapsed_ms: float,
        tokens: int | None,
        schema_ok: bool | None,
        status: str,
        source: str = "graph",
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None:
        """Append a bounded summary using closed field and status sets."""
        if node not in {"route", "extract", "clarify", "change", "solve", "explain", "commit"}:
            raise ValueError("invalid trace node")
        if (
            status not in {"ok", "failed", "rejected", "unknown"}
            or elapsed_ms < 0
            or source not in {"graph", "model_call"}
        ):
            raise ValueError("invalid trace summary")
        if any(value is not None and value < 0 for value in (tokens, input_tokens, output_tokens)):
            raise ValueError("invalid token count")
        self._events.append(
            {
                "node": node,
                "source": source,
                "elapsed_ms": elapsed_ms,
                "tokens": tokens,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "schema_ok": schema_ok,
                "status": status,
                "prompt_hash": self._prompt_hashes.get(node),
            }
        )

    def explanation(self, correct: int, total: int, fallback: bool) -> None:
        if not 0 <= correct <= total:
            raise ValueError("invalid claim counts")
        self._metrics["claims_correct"] += correct
        self._metrics["claims_total"] += total
        self._metrics["fallbacks"] += int(fallback)
        self._metrics["explanations"] += 1

    def finish(self, metrics: Mapping[str, int | float]) -> None:
        allowed = {"claims_correct", "claims_total", "fallbacks", "explanations"}
        if not set(metrics) <= allowed:
            raise ValueError("invalid metric")
        merged: dict[str, int | float] = dict(self._metrics)
        merged.update(metrics)
        count = merged["explanations"]
        merged["fallback_rate"] = merged["fallbacks"] / count if count else 0
        self.run.write_json("trace.json", {"events": self._events, "metrics": merged})
        self.run.finish("completed", outputs=["trace.json"])
