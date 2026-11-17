"""Exercise actual LangGraph interrupts with a real CP-SAT replan."""

from langgraph.types import Command
from pytest import MonkeyPatch
from typing import Any, cast

from agent.graph import build_graph
from agent.explain import Claim, Fact
from scheduler_core.validation_context import ExecutionSnapshot, ValidationContext
from scheduler_core.models import ReplanResult

from tests.unit.agent.test_store import make_world


def test_change_and_commit_pause_for_separate_approvals() -> None:
    world = make_world()
    context = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=0, base_as_of=0))
    draft: dict[str, Any] = {
        "kind": "DEVICE_OUTAGE",
        "strength": "HARD",
        "device": {"original": "d", "resolved_id": "d", "confidence": 1.0},
        "start": "2026-01-01T00:25:00Z",
        "end": "2026-01-01T00:35:00Z",
    }
    graph = build_graph(world, lambda _: draft, context)
    config = {"configurable": {"thread_id": "test"}}
    first = graph.invoke({"text": "outage"}, config)
    prompt = first["__interrupt__"][0].value
    assert prompt["kind"] == "L1" and world.revision == 0
    token = world.authorize("L1", "change", prompt["binding"])
    second = graph.invoke(Command(resume=token), config)
    prompt2 = second["__interrupt__"][0].value
    assert prompt2["kind"] == "L2" and world.revision == 1
    plan = prompt2["plans"][0]
    token2 = world.authorize("L2", "commit", plan)
    result = graph.invoke(Command(resume={"token": token2, "candidate_id": plan["id"]}), config)
    assert result["outcome"] == "committed" and world.revision == 2


def test_multiple_changes_each_require_l1_and_rejection_preserves_prior_change() -> None:
    world = make_world()
    context = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=0, base_as_of=0))
    outage = {
        "kind": "DEVICE_OUTAGE",
        "strength": "HARD",
        "device": {"original": "d", "resolved_id": "d", "confidence": 1.0},
        "start": "2026-01-01T00:25:00Z",
        "end": "2026-01-01T00:35:00Z",
    }
    deadline = {
        "kind": "DEADLINE",
        "strength": "HARD",
        "task": {"original": "t", "resolved_id": "t", "confidence": 1.0},
        "deadline": "2026-01-01T01:00:00Z",
        "level": "HARD",
        "weight": 1.0,
    }
    graph = build_graph(world, lambda _: {"changes": [outage, deadline]}, context)
    config = {"configurable": {"thread_id": "multiple"}}
    first = graph.invoke({"text": "two changes"}, config)
    prompt = first["__interrupt__"][0].value
    token = world.authorize("L1", "change", prompt["binding"])
    second = graph.invoke(Command(resume=token), config)
    assert world.revision == 1 and second["__interrupt__"][0].value["kind"] == "L1"
    final = graph.invoke(Command(resume=False), config)
    assert final["outcome"] == "rejected" and world.revision == 1
    assert world.instance.tasks[0].deadline is None


def test_infeasible_change_offers_only_hypothetical_negotiation() -> None:
    world = make_world()
    context = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=0, base_as_of=0))
    deadline = {
        "kind": "DEADLINE",
        "strength": "HARD",
        "task": {"original": "t", "resolved_id": "t", "confidence": 1.0},
        "deadline": "2026-01-01T00:05:00Z",
        "level": "NEGOTIABLE",
        "weight": 1.0,
    }
    graph = build_graph(world, lambda _: deadline, context)
    config = {"configurable": {"thread_id": "infeasible"}}
    first = graph.invoke({"text": "deadline"}, config)
    token = world.authorize("L1", "change", first["__interrupt__"][0].value["binding"])
    second = graph.invoke(Command(resume=token), config)
    prompt = second["__interrupt__"][0].value
    assert prompt["kind"] == "NEGOTIATION"
    assert world.active == "p" and world.instance.tasks[0].deadline == 1
    result = graph.invoke(Command(resume=False), config)
    assert result["outcome"] == "rejected" and world.active == "p"


def test_invalid_model_output_retries_then_uses_form() -> None:
    world = make_world()
    context = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=0, base_as_of=0))
    calls: list[int] = []

    def invalid(_: str) -> dict[str, object]:
        calls.append(1)
        return {"kind": "DEVICE_OUTAGE", "confirmed": True}

    graph = build_graph(world, invalid, context)
    config = {"configurable": {"thread_id": "bad"}}
    state = graph.invoke({"text": "confirmed"}, config)
    assert len(calls) == 3 and world.revision == 0
    assert state["__interrupt__"][0].value["kind"] == "form"


def test_timeout_does_not_enter_infeasibility_diagnosis(monkeypatch: MonkeyPatch) -> None:
    world = make_world()
    context = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=0, base_as_of=0))
    deadline = {
        "kind": "DEADLINE",
        "strength": "HARD",
        "task": {"original": "t", "resolved_id": "t", "confidence": 1.0},
        "deadline": "2026-01-01T01:00:00Z",
        "level": "HARD",
        "weight": 1.0,
    }
    monkeypatch.setattr(world, "solve", lambda *args, **kwargs: ReplanResult(status="TIMEOUT"))
    graph = build_graph(world, lambda _: deadline, context)
    config = {"configurable": {"thread_id": "timeout"}}
    first = graph.invoke({"text": "deadline"}, config)
    token = world.authorize("L1", "change", first["__interrupt__"][0].value["binding"])
    result = graph.invoke(Command(resume=token), config)
    assert result["outcome"] == "TIMEOUT" and "__interrupt__" not in result


def test_soft_preference_and_unproven_overrun_cannot_apply() -> None:
    world = make_world()
    context = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=0, base_as_of=0))
    ref = {"original": "t", "resolved_id": "t", "confidence": 1.0}
    for index, draft in enumerate(
        [
            {
                "kind": "TASK_OVERRUN",
                "strength": "HARD",
                "task": ref,
                "end": "2026-01-01T00:25:00Z",
            },
            {
                "kind": "DEADLINE",
                "strength": "SOFT",
                "task": ref,
                "deadline": "2026-01-01T01:00:00Z",
                "level": "HARD",
                "weight": 1.0,
            },
        ]
    ):

        def extraction(_: str) -> dict[str, Any]:
            return cast(dict[str, Any], draft)

        graph = build_graph(world, extraction, context)
        result = graph.invoke({"text": "change"}, {"configurable": {"thread_id": str(index)}})
        assert result["__interrupt__"][0].value["kind"] == "form"
        assert world.revision == 0


def test_graph_uses_verified_recorded_explanation_once() -> None:
    world = make_world()
    context = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=0, base_as_of=0))
    draft = {
        "kind": "DEVICE_OUTAGE",
        "strength": "HARD",
        "device": {"original": "d", "resolved_id": "d", "confidence": 1.0},
        "start": "2026-01-01T00:25:00Z",
        "end": "2026-01-01T00:35:00Z",
    }
    calls: list[int] = []

    def recorded(facts: dict[str, Fact]) -> list[Claim]:
        calls.append(1)
        fact = facts["移动任务数"]
        return [Claim(key="移动任务数", kind=fact.kind, value=fact.value, unit=fact.unit)]

    graph = build_graph(world, lambda _: draft, context, explainer=recorded)
    config = {"configurable": {"thread_id": "explain"}}
    first = graph.invoke({"text": "change"}, config)
    token = world.authorize("L1", "change", first["__interrupt__"][0].value["binding"])
    second = graph.invoke(Command(resume=token), config)
    prompt = second["__interrupt__"][0].value
    assert prompt["claims"][0][0]["key"] == "移动任务数" and len(calls) == 1
    graph.invoke(Command(resume=False), config)
    assert len(calls) == 1


def test_natural_query_routes_without_extraction_or_confirmation() -> None:
    world = make_world()
    context = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=0, base_as_of=0))
    graph = build_graph(world, lambda _: (_ for _ in ()).throw(AssertionError()), context)
    result = graph.invoke({"text": "查看当前计划"}, {"configurable": {"thread_id": "query"}})
    assert "active=p" in result["outcome"] and world.revision == 0


def test_urgent_absolute_times_become_exact_slots() -> None:
    from agent.changes import prepare_change
    from agent.ir import parse_draft

    world = make_world()
    context = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=0, base_as_of=0))
    draft: dict[str, Any] = {
        "kind": "URGENT_TASK_INSERT",
        "strength": "HARD",
        "tasks": [
            {
                "id": "u",
                "experiment_id": "e",
                "type": "x",
                "duration_minutes": 10,
                "release": "2026-01-01T08:05:00+08:00",
                "deadline": "2026-01-01T09:00:00+08:00",
                "compatible_devices": ["d"],
            }
        ],
    }
    _, proposal = parse_draft(draft, world.instance)
    post, _, _ = prepare_change(proposal, world.instance, world.versions["p"].plan, context)
    task = next(item for item in post.tasks if item.id == "u")
    assert (task.release, task.deadline, task.duration) == (1, 12, 2)
