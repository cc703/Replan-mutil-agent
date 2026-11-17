"""Independent validation and revision-bound commits."""

from datetime import datetime, timezone

import pytest

from agent.store import Evidence, WorldStore
from scheduler_core.axis import TimeAxis
from scheduler_core.models import Assignment, Device, Instance, Plan, Task
from scheduler_core.validation_context import ExecutionRecord, ExecutionSnapshot, ValidationContext


def make_world() -> WorldStore:
    instance = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=20),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="t", experiment_id="e", type="x", duration=2, compatible_devices=["d"])],
    )
    plan = Plan(id="p", assignments={"t": Assignment(task_id="t", device_id="d", start=1, end=3)})
    return WorldStore("session", instance, Evidence(instance, plan, None, None, None, 0))


def test_candidate_is_checked_and_approval_is_single_use() -> None:
    world = make_world()
    plan = world.versions["p"].plan.model_copy(deep=True, update={"id": "next"})
    evidence = Evidence(world.instance, plan, None, None, None, 0)
    world._add_candidate(evidence)
    token = world.authorize("L2", "commit", plan.model_dump(mode="json"))
    world.commit(token, "next", "person")
    assert world.active == "1:next" and world.revision == 1
    with pytest.raises(KeyError):
        world.commit(token, "next", "person")


def test_invalid_or_stale_candidate_rejected() -> None:
    world = make_world()
    plan = world.versions["p"].plan.model_copy(deep=True, update={"id": "candidate"})
    plan.assignments["t"].end = 19
    with pytest.raises(ValueError, match="validation"):
        world._add_candidate(Evidence(world.instance, plan, None, None, None, 0))
    plan.assignments["t"].end = 3
    with pytest.raises(ValueError, match="stale"):
        world._add_candidate(Evidence(world.instance, plan, None, None, None, 1))


def test_returned_state_is_copy_and_rollback_requires_l2() -> None:
    world = make_world()
    snapshot = world.instance
    snapshot.tasks[0].deadline = 1
    assert world.instance.tasks[0].deadline is None
    version = world.versions["p"]
    version.plan.assignments["t"].end = 19
    assert world.versions["p"].plan.assignments["t"].end == 3
    context = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=0, base_as_of=0))
    payload = world.rollback_payload("p", context)
    with pytest.raises(PermissionError):
        world.rollback("forged", "p", "person", context)
    token = world.authorize("L2", "rollback", payload)
    world.rollback(token, "p", "person", context)
    assert world.revision == 1
    with pytest.raises(PermissionError):
        world.rollback(token, "p", "person", context)


def test_rollback_rejects_missing_and_running_evidence_conflict() -> None:
    world = make_world()
    with pytest.raises(ValueError, match="snapshot"):
        world.rollback_payload("p", ValidationContext())
    plan = world.versions["p"].plan.model_copy(deep=True, update={"id": "q"})
    plan.assignments["t"].start = 0
    plan.assignments["t"].end = 2
    world._add_candidate(Evidence(world.instance, plan, None, None, None, 0))
    token = world.authorize("L2", "commit", plan.model_dump(mode="json"))
    world.commit(token, "q", "person")
    # Simulate a trusted execution update: q has started at the current business now.
    world._instance.tasks[0].status = "RUNNING"
    context = ValidationContext(
        snapshot=ExecutionSnapshot(
            plan_id="q",
            as_of=0,
            base_as_of=0,
            records=[
                ExecutionRecord(
                    task_id="t",
                    status="RUNNING",
                    device_id="d",
                    start=0,
                    planned_end=2,
                    remaining_estimate=2,
                    event_id="observed",
                )
            ],
        )
    )
    payload = world.rollback_payload("p", context)
    approval = world.authorize("L2", "rollback", payload)
    with pytest.raises(ValueError, match="validation"):
        world.rollback(approval, "p", "person", context)
    assert world.active == "1:q"


def test_future_rollback_uses_current_parent_and_context() -> None:
    world = make_world()
    base = world.versions["p"].plan
    plan = base.model_copy(deep=True, update={"id": "q", "parent_id": "p"})
    plan.assignments["t"].start, plan.assignments["t"].end = 2, 4
    old_context = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=0, base_as_of=0))
    world._add_candidate(Evidence(world.instance, plan, base, frozenset({"t"}), old_context, 0))
    token = world.authorize("L2", "commit", plan.model_dump(mode="json"))
    world.commit(token, "q", "person")
    context = ValidationContext(snapshot=ExecutionSnapshot(plan_id="q", as_of=0, base_as_of=0))
    binding = world.rollback_payload("p", context)
    token = world.authorize("L2", "rollback", binding)
    with pytest.raises(ValueError, match="snapshot"):
        world.rollback(token, "p", "person", ValidationContext())
    world.rollback(token, "p", "person", context)
    assert world.versions[world.active].plan.assignments["t"].start == 1
