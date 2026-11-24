"""Verify the P7 HTTP workflow and independently recheck its PostgreSQL evidence."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, cast
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx

from agent.miniature import miniature
from scheduler_core.generate import generate_instance
from scheduler_core.io.artifacts import ArtifactStore
from scheduler_core.models import BlockedWindow, Device, Instance, Plan
from scheduler_core.validate import validate
from scheduler_core.validation_context import ValidationContext


ROOT = Path(__file__).resolve().parents[1]
ACTOR = "p7-local-e2e"
SEED = 2

# Only identifiers validated as UUID and integer parameters reach these statements.
DB_PROOF = """
SELECT json_build_object(
    'server_version', current_setting('server_version'),
    'evidence', p.evidence,
    'versions', (SELECT count(*) FROM plan_version WHERE lab_id=p.lab_id),
    'active_count', (SELECT count(*) FROM plan_version WHERE lab_id=p.lab_id AND status='ACTIVE'),
    'job_status', (SELECT status FROM job WHERE lab_id=p.lab_id AND id=:'job_id'),
    'event_status', (SELECT status FROM event WHERE lab_id=p.lab_id AND id=:'event_id'),
    'confirmation_status',
        (SELECT status FROM confirmation WHERE lab_id=p.lab_id AND id=:'approval_id'),
    'decisions', (SELECT count(*) FROM decision_log WHERE lab_id=p.lab_id)
)
FROM plan_version p
WHERE p.lab_id=:'lab_id' AND p.version_no=2 AND p.status='ACTIVE';
"""


class FlowError(RuntimeError):
    """A workflow condition was not observed."""


def expect(condition: object, message: str) -> None:
    if not condition:
        raise FlowError(message)


class Client:
    """Request the real browser-facing API with a trace and idempotency per operation."""

    def __init__(self, url: str) -> None:
        self.http = httpx.Client(base_url=url.rstrip("/") + "/api/v1", timeout=35, trust_env=False)
        self.steps: list[dict[str, object]] = []
        self.trace = str(uuid4())
        self.lab = ""

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
        *,
        status: int = 200,
        code: str | None = None,
        key: str | None = None,
        replay: bool = False,
        lab: bool = True,
    ) -> dict[str, Any]:
        route = f"/labs/{self.lab}{path}" if lab else path
        headers = {"X-Trace-Id": self.trace}
        if method == "POST":
            headers["Idempotency-Key"] = key or str(uuid4())
        response = self.http.request(method, route, headers=headers, json=payload)
        body = response.json()
        error = body.get("error") if isinstance(body, dict) else None
        actual = error.get("code") if isinstance(error, dict) else None
        self.steps.append(
            {"method": method, "path": path, "status": response.status_code, "code": actual}
        )
        expect(
            response.status_code == status,
            f"{method} {path}: expected {status}/{code}, got {response.status_code}/{actual}",
        )
        expect(not code or actual == code, f"{method} {path}: expected code {code}, got {actual}")
        expect(response.headers.get("X-Trace-Id") == self.trace, f"{path}: trace ID missing")
        expect(
            not replay or response.headers.get("Idempotent-Replay") == "true",
            "Replay header missing",
        )
        expect(isinstance(body, dict), f"{path}: object response required")
        return cast(dict[str, Any], body)

    def create_lab(self, instance: Instance, name: str) -> None:
        result = self.request(
            "POST",
            "/labs",
            {"name": name, "instance": instance.model_dump(mode="json")},
            status=201,
            lab=False,
        )
        self.lab = str(UUID(result["lab_id"]))

    def wait_job(self, job_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + 130
        while time.monotonic() < deadline:
            job = self.request("GET", f"/jobs/{job_id}")
            if job["status"] not in {"QUEUED", "RUNNING"}:
                return job
            time.sleep(0.25)
        raise FlowError("Job did not finish within 130 seconds")

    def next_job(self) -> str:
        state = self.request("GET", "")
        job_id = state.get("undecided_job_id") or state.get("running_job_id")
        deadline = time.monotonic() + 45
        while job_id is None and time.monotonic() < deadline:
            time.sleep(0.2)
            state = self.request("GET", "")
            job_id = state.get("undecided_job_id") or state.get("running_job_id")
        if job_id is None:
            raise FlowError("No asynchronous replan was claimed")
        return str(UUID(job_id))

    def approval(self, action: str, level: str, payload: dict[str, object]) -> dict[str, Any]:
        return self.request(
            "POST",
            "/confirmations",
            {"action": action, "level": level, "payload": payload, "actor": ACTOR},
            status=201,
        )

    def confirm(self, approval: dict[str, Any]) -> None:
        route = f"/confirmations/{approval['confirmation_id']}/confirm"
        body = {"actor": ACTOR, "payload_hash": approval["payload_hash"]}
        key = str(uuid4())
        reply = self.request("POST", route, body, key=key)
        expect(reply["status"] == "CONFIRMED", "Approval did not reach CONFIRMED")
        self.request("POST", route, body, key=key, replay=True)


def _choose(job: dict[str, Any], base: int) -> dict[str, object]:
    expect(job["status"] == "SUCCEEDED" and job["result_status"] == "OK", "Expected solved job")
    candidates = job["candidates"]
    expect(bool(candidates), "No usable CP-SAT candidates returned")
    expect(
        all(c["validation"]["passed"] is True for c in candidates), "Unvalidated candidate exposed"
    )
    chosen = candidates[0]
    return {
        "job_id": job["job_id"],
        "candidate_id": chosen["candidate_id"],
        "plan_sha256": chosen["plan_sha256"],
        "base_version_no": base,
    }


def _commit(client: Client, selection: dict[str, object], *, negative: bool = False) -> str:
    approval = client.approval("PLAN_COMMIT", "L2", selection)
    action = {key: value for key, value in selection.items() if key != "plan_sha256"}
    action["actor"] = ACTOR
    if negative:
        client.request("POST", "/plans/commit", action, status=428, code="CONFIRMATION_REQUIRED")
    action["confirmation_id"] = approval["confirmation_id"]
    if negative:
        client.request(
            "POST", "/plans/commit", action, status=409, code="CONFIRMATION_NOT_CONFIRMED"
        )
    client.confirm(approval)
    key = str(uuid4())
    result = client.request("POST", "/plans/commit", action, status=201, key=key)
    expect(
        result["version_no"] == int(cast(int, selection["base_version_no"])) + 1,
        "Wrong new version",
    )
    client.request("POST", "/plans/commit", action, status=201, key=key, replay=True)
    if negative:
        client.request("POST", "/plans/commit", action, status=409, code="STALE_BASE_VERSION")
    return str(UUID(approval["confirmation_id"]))


def _inject(client: Client, event: dict[str, object]) -> str:
    action: dict[str, object] = {"client_event_id": str(uuid4()), "event": event, "actor": ACTOR}
    client.request("POST", "/events", action, status=428, code="CONFIRMATION_REQUIRED")
    approval = client.approval("EVENT_INJECT", "L1", event)
    action["confirmation_id"] = approval["confirmation_id"]
    client.request("POST", "/events", action, status=409, code="CONFIRMATION_NOT_CONFIRMED")
    client.confirm(approval)
    key = str(uuid4())
    accepted = client.request("POST", "/events", action, status=202, key=key)
    duplicate = client.request("POST", "/events", action, status=202, key=key, replay=True)
    expect(duplicate["event_id"] == accepted["event_id"], "Replay duplicated event")
    client.request(
        "POST",
        "/events",
        {**action, "client_event_id": str(uuid4())},
        status=409,
        code="IDEMPOTENCY_KEY_REUSED",
        key=key,
    )
    return str(UUID(accepted["event_id"]))


def _database(args: argparse.Namespace, ids: dict[str, str]) -> dict[str, Any]:
    settings = dict(os.environ)
    if args.db_mode == "compose":
        db = [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            settings.get("P7_DB_USER", "p7_local"),
            "-d",
            "p7_demo",
        ]
    else:
        db = [settings.get("P7_PSQL", "psql"), "-d", args.database]
    db += ["-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1"]
    for name, value in ids.items():
        db += ["-v", f"{name}={UUID(value)}"]
    settings["PGCLIENTENCODING"] = "UTF8"
    proc = subprocess.run(
        db,
        cwd=ROOT,
        env=settings,
        input=DB_PROOF,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=15,
        check=False,
    )
    expect(proc.returncode == 0, "Could not query the PostgreSQL audit proof")
    expect(bool(proc.stdout.strip()), "Formal version missing from PostgreSQL")
    data = cast(dict[str, Any], json.loads(proc.stdout))
    evidence = data.pop("evidence")
    plan = Plan.model_validate(evidence["plan"])
    base = Plan.model_validate(evidence["base_plan"])
    free = set(evidence["free"])
    world = Instance.model_validate(evidence["instance"])
    context = ValidationContext.model_validate(evidence["context"])
    report = validate(world, plan, base=base, free=free, context=context)
    expect(report.passed, "Independent revalidation of stored post-world failed")
    expect(
        data["versions"] == 2
        and data["active_count"] == 1
        and data["job_status"] == "COMMITTED"
        and data["event_status"] == "APPLIED"
        and data["confirmation_status"] == "CONSUMED"
        and data["decisions"] > 0,
        "Persisted lifecycle or audit differs from the API",
    )
    return {
        **data,
        "independent_validation": "passed",
        "assignment": plan.assignments["t1"].model_dump(),
    }


def _agent_flow(client: Client, world: Instance) -> None:
    """Confirm that a scripted model can propose actions but cannot apply them."""
    start, end = (world.axis.to_dt(slot).isoformat() for slot in (35, 36))
    unclear = client.request("POST", "/agent/turn", {"text": "设备停用", "actor": ACTOR})
    expect(unclear["clarifications"] and not unclear["pending_items"], "Missing clarification")
    draft = client.request(
        "POST",
        "/agent/turn",
        {"session_id": unclear["session_id"], "actor": ACTOR, "text": f"outage d1 {start} {end}"},
    )
    item = draft["pending_items"][0]
    expect(item["action"] == "EVENT_INJECT" and item["back_translation"], "Missing draft preview")
    expect(client.request("GET", "")["pending_event_count"] == 0, "Agent draft wrote a fact")
    _inject(client, item["event"])


def _unresolved_batch(client: Client) -> dict[str, object]:
    """An infeasible result gates the next batch, preserving each confirmed event."""
    world = miniature()
    world.devices.append(Device(id="d2", type="generic"))
    client.create_lab(world, f"P7 blocked batch {client.trace[:8]}")
    initial = client.request("POST", "/plans/initial", {}, status=202)
    _commit(client, _choose(client.wait_job(initial["job_id"]), 0))

    def outage(device: str, start: int, end: int) -> str:
        return _inject(
            client,
            {
                "type": "DEVICE_OUTAGE",
                "device_id": device,
                "start": world.axis.to_dt(start).isoformat(),
                "end": world.axis.to_dt(end).isoformat(),
            },
        )

    first = outage("d1", 0, world.axis.horizon_slots)
    current = client.next_job()
    result = client.wait_job(current)
    expect(
        result["result_status"] == "INFEASIBLE" and not result["candidates"],
        "Expected proven infeasibility",
    )
    expect(
        all(r["hypothetical"] is True for r in result["relaxations"]),
        "A relaxation appeared authorized",
    )
    with ThreadPoolExecutor(max_workers=4) as workers:
        subsequent = list(workers.map(lambda slot: outage("d2", slot, slot + 1), range(8)))
    state = client.request("GET", "")
    expect(
        state["undecided_job_id"] == current
        and state["running_job_id"] is None
        and state["pending_event_count"] >= 8,
        "Unresolved infeasibility failed to gate confirmed events",
    )
    client.request("POST", f"/jobs/{current}/discard", {"reason": "e2e-next-batch", "actor": ACTOR})
    following = client.next_job()
    expect(following != current, "Discard did not allow a new batch")
    result = client.wait_job(following)
    expect(
        set(result["event_ids"]) == {first, *subsequent}, "A confirmed fact was lost or replayed"
    )
    client.request("POST", f"/jobs/{following}/discard", {"reason": "e2e-complete", "actor": ACTOR})
    return {"result": "INFEASIBLE", "next_batch_facts": len(subsequent) + 1}


def _workflow(client: Client, args: argparse.Namespace) -> dict[str, Any]:
    generated = generate_instance("S", 0.08, 0.05, SEED)
    client.create_lab(generated, f"P7 generated {client.trace[:8]}")
    initial = client.request("POST", "/plans/initial", {}, status=202)
    _choose(client.wait_job(initial["job_id"]), 0)

    world = miniature()
    world.blocked.append(BlockedWindow(device_id="d1", start=40, end=44, kind="MAINT"))
    client.create_lab(world, f"P7 local E2E {client.trace[:8]}")
    initial = client.request("POST", "/plans/initial", {}, status=202)
    _commit(client, _choose(client.wait_job(initial["job_id"]), 0))
    baseline = Plan.model_validate(client.request("GET", "/plans/1")["plan"])
    t1 = baseline.assignments["t1"]
    event: dict[str, object] = {
        "type": "DEVICE_OUTAGE",
        "device_id": t1.device_id,
        "start": world.axis.to_dt(t1.start).isoformat(),
        "end": world.axis.to_dt(t1.end + 1).isoformat(),
    }
    event_id = _inject(client, event)
    outdated = client.request("GET", "/plans/1")
    expect(
        outdated["status"] == "NEEDS_REPLAN" and not outdated.get("view"),
        "The previous plan was still shown as active despite conflicting facts",
    )
    job_id = client.next_job()
    job = client.wait_job(job_id)
    selection = _choose(job, 1)
    expect(bool(job["candidates"][0]["diff"]), "The outage did not yield a candidate difference")
    approval_id = _commit(client, selection, negative=True)
    latest = client.request("GET", "/plans/2")
    view = latest["view"]
    blocked = {row["kind"] for row in view["blocked"]}
    expect(
        {"MAINT", "FAULT"} <= blocked, "The device timeline lacks a maintenance or outage window"
    )
    expect(client.request("GET", "")["active_version_no"] == 2, "Active version did not update")
    expect(bool(client.request("GET", "/plans/2/diff?base=1")["changes"]), "Committed diff missing")
    proof = _database(
        args,
        {"lab_id": client.lab, "job_id": job_id, "event_id": event_id, "approval_id": approval_id},
    )
    expect(proof["assignment"]["start"] >= t1.end + 1, "Task still intersects the injected outage")
    client.request(
        "POST",
        "/confirmations",
        {
            "action": "PLAN_ROLLBACK",
            "level": "L2",
            "actor": ACTOR,
            "payload": {"target_version_no": 1, "base_version_no": 2},
        },
        status=422,
        code="ROLLBACK_INFEASIBLE",
    )
    _agent_flow(client, world)
    batches = _unresolved_batch(client)
    return {
        "ok": True,
        "trace_id": client.trace,
        "postgres": proof,
        "batches": batches,
        "steps": client.steps,
    }


def main() -> int:
    """Run real local HTTP/DB checks and record observed outcomes through ArtifactStore."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:5173")
    parser.add_argument("--db-mode", choices=("local", "compose"), default="local")
    parser.add_argument("--database", default="p7_demo")
    args = parser.parse_args()
    url = urlsplit(args.url)
    if url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost"} or url.username:
        parser.error("P7 E2E requires a loopback HTTP URL without credentials")
    out = ArtifactStore(ROOT / "artifacts").new_run(
        "experiment",
        "p7_local_demo",
        "http-db",
        config=f"generator_seed: {SEED}\nscale: S\nutilization: 0.08\ndeadline_tightness: 0.05\n",
        seeds=[SEED],
        metadata={"profile": "local", "db_mode": args.db_mode},
    )
    client = Client(args.url)
    success = False
    try:
        out.write_json("summary.json", _workflow(client, args))
        success = True
    except (
        FlowError,
        OSError,
        ValueError,
        httpx.HTTPError,
        KeyError,
        TypeError,
        AttributeError,
    ) as exc:
        message = str(exc) if isinstance(exc, FlowError) else type(exc).__name__
        out.write_json("summary.json", {"ok": False, "error": message, "steps": client.steps})
        print(f"P7 E2E failed: {message}")
    finally:
        client.http.close()
        manifest = out.finish("completed" if success else "failed", outputs=["summary.json"])
        print(f"{manifest.status}: {out.dir}")
    return int(not success)


if __name__ == "__main__":
    raise SystemExit(main())
