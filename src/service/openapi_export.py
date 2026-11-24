"""Export the internal schema and measured examples from actual service responses."""

import argparse
import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import UUID

from fastapi.testclient import TestClient

from .app import PREFIX, app

ROOT = Path(__file__).resolve().parents[2] / "apps" / "contracts"
INSTANCE: dict[str, Any] = {
    "axis": {"t0": "2026-11-24T00:00:00Z", "slot_minutes": 5, "horizon_slots": 36},
    "devices": [{"id": "device-a", "type": "bench"}, {"id": "device-b", "type": "bench"}],
    "tasks": [
        {
            "id": "task-a",
            "experiment_id": "e1",
            "type": "test",
            "duration": 3,
            "deadline": 14,
            "weight": 2,
            "compatible_devices": ["device-a", "device-b"],
        }
    ],
}
OUTAGE = {"type": "DEVICE_OUTAGE", "start": "2026-11-24T00:00:00Z", "end": "2026-11-24T00:20:00Z"}
URGENT = {
    "type": "URGENT_INSERT",
    "tasks": [
        {
            "id": "urgent-a",
            "experiment_id": "e2",
            "type": "test",
            "duration_minutes": 10,
            "release": "2026-11-24T00:05:00Z",
            "deadline": "2026-11-24T01:00:00Z",
            "deadline_level": "HARD",
            "compatible_devices": ["device-a", "device-b"],
        }
    ],
}


def examples() -> dict[str, Any]:
    """Generate examples from real ASGI requests. Wall-clock measurements can vary."""
    headers = {"X-Trace-Id": "p7-contract-example"}
    with (
        TestClient(app) as client,
        patch(
            "service.scheduling.uuid4", return_value=UUID("00000000-0000-0000-0000-000000000001")
        ),
        patch.dict(os.environ, {"P7_LLM": "fake"}),
    ):

        def post(path: str, body: dict[str, Any], status: int = 200) -> dict[str, Any]:
            response = client.post(PREFIX + path, json=body, headers=headers)
            if response.status_code != status:
                raise ValueError(f"{path} returned {response.status_code}: {response.text}")
            result: dict[str, Any] = response.json()
            return result

        initial = post("/initial", {"instance": INSTANCE, "params": {"num_workers": 1}})
        base = initial["plan"]
        common = {"instance": INSTANCE, "base_plan": base}
        example_outage = {**OUTAGE, "device_id": base["assignments"]["task-a"]["device_id"]}
        ok = post(
            "/replan", {**common, "events": [example_outage, URGENT], "params": {"num_workers": 1}}
        )
        long_outages = [
            {**OUTAGE, "device_id": dev, "end": "2026-11-24T01:15:00Z"}
            for dev in ("device-a", "device-b")
        ]
        infeasible = post(
            "/replan", {**common, "events": long_outages, "params": {"num_workers": 1}}
        )
        timeout = post("/replan", {**common, "events": long_outages, "budget_s": 1e-12})
        ev = initial["candidates"][0]["evidence"]
        failed = post(
            "/validate", {**ev, "current_base_plan": base, "additional_events": [example_outage]}
        )
        error = post(
            "/events/preview", {**common, "event": {**OUTAGE, "device_id": "unknown"}}, 400
        )
        return {
            "instance": INSTANCE,
            "initial": initial,
            "replan-ok": ok,
            "replan-infeasible": infeasible,
            "replan-timeout": timeout,
            "validation-failed": failed,
            "error-envelope": error,
            "event-outage": example_outage,
            "event-urgent": URGENT,
            "event-preview": post("/events/preview", {**common, "event": example_outage}),
        }


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples", action="store_true", help="refresh measured HTTP examples")
    args = parser.parse_args()
    _write(ROOT / "scheduler-service.openapi.json", app.openapi())
    if args.examples:
        for name, value in examples().items():
            _write(ROOT / "examples" / f"{name}.json", value)


if __name__ == "__main__":
    main()
