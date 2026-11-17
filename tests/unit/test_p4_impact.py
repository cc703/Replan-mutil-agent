from datetime import datetime, timezone

import pytest

from scheduler_core.axis import TimeAxis
from scheduler_core.impact import analyze_impact, neighborhoods
from scheduler_core.models import (
    Assignment,
    BlockedWindow,
    Device,
    DeviceOutage,
    Instance,
    Plan,
    Precedence,
    Task,
)
from scheduler_core.replanning.events import prepare_post
from scheduler_core.validation_context import ExecutionSnapshot, ValidationContext


def test_outage_propagates_and_neighborhoods_are_monotone() -> None:
    tasks = [
        Task(id=x, experiment_id=e, type="x", duration=2, compatible_devices=[d])
        for x, e, d in [
            ("a", "one", "d1"),
            ("b", "two", "d2"),
            ("c", "two", "d2"),
            ("z", "three", "d1"),
        ]
    ]
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        now=2,
        tasks=tasks,
        devices=[Device(id="d1", type="x"), Device(id="d2", type="x")],
        precedences=[Precedence(pred="a", succ="b")],
        blocked=[BlockedWindow(device_id="d1", start=6, end=10, kind="FAULT")],
    )
    base = Plan(
        id="p",
        assignments={
            t.id: Assignment(task_id=t.id, device_id=t.compatible_devices[0], start=s, end=s + 2)
            for t, s in zip(tasks, [6, 14, 21, 0])
        },
    )
    context = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=2, base_as_of=0))
    event = DeviceOutage(device_id="d1", start=6, end=10)
    before = inst.model_dump_json()
    assert prepare_post(inst, base, [event], context) == inst
    assert inst.model_dump_json() == before
    impact = analyze_impact(inst, base, [event], 2, context=context)
    assert impact.frozen == {"z"}
    assert impact.affected == {"a", "b"}
    assert impact.reasons["b"] == "successor:a"
    levels = neighborhoods(inst, base, impact, 2)
    assert levels == ({"a", "b"}, {"a", "b"}, {"a", "b", "c"}, {"a", "b", "c"})
    with pytest.raises(ValueError, match="not applied"):
        prepare_post(inst.model_copy(update={"blocked": []}), base, [event], context)


def test_p4_model_outage_candidate_passes_independent_validator() -> None:
    from scheduler_core.models import ReplanParams
    from scheduler_core.replanning.model import solve_neighborhood
    from scheduler_core.validate import validate

    tasks = [
        Task(id=x, experiment_id="e", type="x", duration=2, compatible_devices=["d1", "d2"])
        for x in ["a", "b"]
    ]
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=20),
        now=2,
        tasks=tasks,
        devices=[Device(id="d1", type="x"), Device(id="d2", type="x")],
        blocked=[BlockedWindow(device_id="d2", start=6, end=10, kind="FAULT")],
    )
    base = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d1", start=0, end=2),
            "b": Assignment(task_id="b", device_id="d2", start=6, end=8),
        },
    )
    context = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=2, base_as_of=0))
    result = solve_neighborhood(inst, base, {"b"}, {"a"}, context, set(), ReplanParams(), 5)
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.assignments is not None
    candidate = Plan(id="p-new", parent_id="p", assignments=result.assignments)
    assert validate(inst, candidate, base=base, free={"b"}, context=context).passed
    assert candidate.assignments["a"] == base.assignments["a"]


def test_replan_and_full_baselines_validate() -> None:
    from scheduler_core.baselines.b2 import b2, b2s
    from scheduler_core.models import ReplanParams
    from scheduler_core.replan import replan

    task = Task(id="a", experiment_id="e", type="x", duration=2, compatible_devices=["d1", "d2"])
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=20),
        now=2,
        tasks=[task],
        devices=[Device(id="d1", type="x"), Device(id="d2", type="x")],
        blocked=[BlockedWindow(device_id="d2", start=6, end=10, kind="FAULT")],
    )
    base = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d2", start=6, end=8)})
    context = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=2, base_as_of=0))
    events = [DeviceOutage(device_id="d2", start=6, end=10)]
    params = ReplanParams(total_budget_s=5, num_workers=1, beta_switched=0)
    results = [
        replan(inst, base, events, params, context=context, post_applied=True),
        b2(inst, base, events, context, params),
        b2s(inst, base, events, context, params),
    ]
    for result in results:
        assert result.status == "OK"
        assert result.candidates[0].validation.passed
    assert results[0].level_reached == 0
    assert (
        results[0].candidates[0].plan.metrics.tardiness
        == results[1].candidates[0].plan.metrics.tardiness
    )
    assert (
        results[0].candidates[0].plan.metrics.moved <= results[1].candidates[0].plan.metrics.moved
    )


@pytest.mark.parametrize("preemptible,expected", [(True, 4), (False, 6)])
def test_p3_interruption_runs_real_adapter_once(preemptible: bool, expected: int) -> None:
    from simulator.engine import Simulator
    from simulator.replan_adapter import scheduler_with_context
    from simulator.scenarios import Scenario

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[
            Task(
                id="a",
                experiment_id="e",
                type="x",
                duration=6,
                compatible_devices=["d"],
                preemptible=preemptible,
            )
        ],
    )
    base = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=6)})
    original = inst.model_dump_json(), base.model_dump_json()
    engine = Simulator(
        inst,
        base,
        Scenario(duration_sigma=0.0),
        None,
        3,
        scheduler_with_context=scheduler_with_context,
    )
    engine.inject(DeviceOutage(device_id="d", start=2, end=4), 2)
    result = engine.run(12)
    assert len(result.final_instance.blocked) == 1
    assert next(t for t in result.final_instance.tasks if t.id == "a~r1").duration == expected
    assert "a~r1" in result.final_plan.assignments
    assert (inst.model_dump_json(), base.model_dump_json()) == original


def test_unknown_never_reports_infeasible(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib
    from scheduler_core.models import ReplanParams
    from scheduler_core.replanning.model import ModelResult

    module = importlib.import_module("scheduler_core.replan")
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=20),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=2, compatible_devices=["d"])],
    )
    base = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=4, end=6)})
    context = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=0, base_as_of=0))
    statuses = iter(["INFEASIBLE", "UNKNOWN", "INFEASIBLE", "UNKNOWN"])
    monkeypatch.setattr(
        module,
        "solve_neighborhood",
        lambda *args, **kwargs: ModelResult(next(statuses), None, None, None),
    )
    result = module.replan(
        inst, base, [], ReplanParams(total_budget_s=5), context=context, post_applied=True
    )
    assert result.status == "TIMEOUT" and result.level_reached == 3
    monkeypatch.setattr(
        module,
        "solve_neighborhood",
        lambda *args, **kwargs: ModelResult("INFEASIBLE", None, None, None),
    )
    assert (
        module.replan(
            inst,
            base,
            [],
            ReplanParams(total_budget_s=5, max_level=2),
            context=context,
            post_applied=True,
        ).status
        == "TIMEOUT"
    )
    assert (
        module.replan(
            inst, base, [], ReplanParams(total_budget_s=5), context=context, post_applied=True
        ).status
        == "INFEASIBLE"
    )


def test_b3_rejects_missed_deadline_and_validator_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib
    from scheduler_core.models import ValidationReport, Violation

    module = importlib.import_module("scheduler_core.baselines.b3")
    task = Task(
        id="a",
        experiment_id="e",
        type="x",
        duration=2,
        deadline=6,
        deadline_level="HARD",
        compatible_devices=["d"],
    )
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=20),
        now=2,
        devices=[Device(id="d", type="x")],
        tasks=[task],
        blocked=[BlockedWindow(device_id="d", start=2, end=10, kind="FAULT")],
    )
    base = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=3, end=5)})
    context = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=2, base_as_of=0))
    events = [DeviceOutage(device_id="d", start=2, end=10)]
    assert module.b3(inst, base, events, context) is None
    inst.tasks[0] = task.model_copy(update={"deadline": 18})
    monkeypatch.setattr(
        module,
        "validate",
        lambda *args, **kwargs: ValidationReport(
            passed=False, violations=[Violation(code="V1", detail="forced")]
        ),
    )
    assert module.b3(inst, base, events, context) is None


def test_p3_overrun_and_not_started_real_adapter() -> None:
    from simulator.engine import Simulator
    from simulator.replan_adapter import scheduler_with_context
    from simulator.scenarios import Scenario

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[
            Task(id=x, experiment_id="e", type="x", duration=n, compatible_devices=["d"])
            for x, n in [("a", 3), ("b", 2)]
        ],
    )
    base = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=3),
            "b": Assignment(task_id="b", device_id="d", start=3, end=5),
        },
    )
    scenario = Scenario(duration_sigma=0.0, duration_factor_min=1.5, duration_factor_max=1.5)
    result = Simulator(
        inst, base, scenario, None, 1, scheduler_with_context=scheduler_with_context
    ).run(12)
    assert result.final_instance.tasks[1].status == "DONE"
    assert result.final_plan.assignments["b"].start >= result.final_plan.assignments["a"].end


@pytest.mark.parametrize("preemptible,expected", [(True, 4), (False, 6)])
def test_raw_interruption_uses_explicit_running_evidence(preemptible: bool, expected: int) -> None:
    from scheduler_core.replanning.events import prepare_raw
    from scheduler_core.validation_context import ExecutionRecord

    task = Task(
        id="a",
        experiment_id="e",
        type="x",
        duration=6,
        compatible_devices=["d"],
        status="RUNNING",
        preemptible=preemptible,
    )
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=20),
        now=2,
        devices=[Device(id="d", type="x")],
        tasks=[task],
    )
    base = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=6)})
    context = ValidationContext(
        snapshot=ExecutionSnapshot(
            plan_id="p",
            as_of=2,
            base_as_of=0,
            records=[
                ExecutionRecord(
                    task_id="a",
                    status="RUNNING",
                    device_id="d",
                    start=0,
                    planned_end=6,
                    remaining_estimate=4,
                    event_id="start",
                )
            ],
        )
    )
    before = inst.model_dump_json(), context.model_dump_json()
    post, updated = prepare_raw(inst, base, [DeviceOutage(device_id="d", start=2, end=4)], context)
    assert next(t for t in post.tasks if t.id == "a~r1").duration == expected
    assert updated.snapshot is not None and updated.snapshot.records == []
    assert (inst.model_dump_json(), context.model_dump_json()) == before


def test_level3_and_b2s_equal_on_provable_example() -> None:
    from scheduler_core.baselines.b2 import b2s
    from scheduler_core.models import ReplanParams
    from scheduler_core.replan import replan

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=12),
        now=2,
        devices=[Device(id="d", type="x")],
        tasks=[
            Task(id=x, experiment_id="e", type="x", duration=2, compatible_devices=["d"])
            for x in "ab"
        ],
        blocked=[BlockedWindow(device_id="d", start=4, end=6, kind="FAULT")],
    )
    base = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=4, end=6),
            "b": Assignment(task_id="b", device_id="d", start=6, end=8),
        },
    )
    context = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=2, base_as_of=0))
    events = [DeviceOutage(device_id="d", start=4, end=6)]
    params = ReplanParams(total_budget_s=5, num_workers=1)
    m = replan(inst, base, events, params, context=context, post_applied=True, full=True)
    b = b2s(inst, base, events, context, params)
    assert m.status == b.status == "OK"
    assert m.level_reached == b.level_reached == 3
    assert m.candidates[0].plan.assignments == b.candidates[0].plan.assignments


def test_b3_respects_person_calendar_capacity_and_rejects_lag_max() -> None:
    from scheduler_core.baselines.b3 import b3
    from scheduler_core.models import Person, PersonBlockedWindow

    tasks = [
        Task(
            id=x,
            experiment_id="e",
            type="x",
            duration=2,
            compatible_devices=["d"],
            required_skills={"s"},
        )
        for x in "ab"
    ]
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=20),
        now=2,
        devices=[Device(id="d", type="x", capacity=2)],
        tasks=tasks,
        persons=[
            Person(id="p1", skills={"s"}, blocked=[PersonBlockedWindow(start=4, end=7)]),
            Person(id="p2", skills={"s"}),
        ],
        precedences=[Precedence(pred="a", succ="b", lag_min=1, lag_max=2)],
        blocked=[BlockedWindow(device_id="d", start=4, end=6, kind="FAULT")],
    )
    base = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", person_id="p1", start=4, end=6),
            "b": Assignment(task_id="b", device_id="d", person_id="p2", start=7, end=9),
        },
    )
    context = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=2, base_as_of=0))
    events = [DeviceOutage(device_id="d", start=4, end=6)]
    candidate = b3(inst, base, events, context)
    assert candidate is not None
    from scheduler_core.validate import validate

    assert validate(inst, candidate, base=base, context=context).passed
    assert candidate.assignments["b"].start - candidate.assignments["a"].end <= 2


def test_budget_expires_before_solving(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib
    from scheduler_core.models import ReplanParams

    module = importlib.import_module("scheduler_core.replan")
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=10),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=1, compatible_devices=["d"])],
    )
    base = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=3, end=4)})
    context = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=0, base_as_of=0))
    times = iter([0.0, 2.0])
    monkeypatch.setattr(module.time, "perf_counter", lambda: next(times))

    def never(*args: object, **kwargs: object) -> None:
        raise AssertionError("solver called after budget")

    monkeypatch.setattr(module, "solve_neighborhood", never)
    assert (
        module.replan(
            inst, base, [], ReplanParams(total_budget_s=1), context=context, post_applied=True
        ).status
        == "TIMEOUT"
    )


def test_model_personnel_capacity_setup_calendar_and_lag() -> None:
    from scheduler_core.models import Person, PersonBlockedWindow, ReplanParams, SetupRule
    from scheduler_core.replanning.model import solve_neighborhood
    from scheduler_core.validate import validate

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=20),
        now=2,
        devices=[Device(id="d", type="x", capacity=2)],
        tasks=[
            Task(
                id=x,
                experiment_id="e",
                type="x",
                duration=2,
                demand=1,
                compatible_devices=["d"],
                required_skills={"s"},
            )
            for x in "ab"
        ],
        persons=[
            Person(id="p1", skills={"s"}, blocked=[PersonBlockedWindow(start=3, end=5)]),
            Person(id="p2", skills={"s"}),
        ],
        setups=[SetupRule(device_id="d", task_type="x", slots=1)],
        precedences=[Precedence(pred="a", succ="b", lag_min=1, lag_max=2)],
        blocked=[BlockedWindow(device_id="d", start=4, end=6, kind="FAULT")],
    )
    base = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", person_id="p1", start=4, end=6),
            "b": Assignment(task_id="b", device_id="d", person_id="p2", start=7, end=9),
        },
    )
    context = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=2, base_as_of=0))
    result = solve_neighborhood(
        inst, base, {"a", "b"}, set(), context, set(), ReplanParams(num_workers=1), 5
    )
    assert result.assignments is not None
    candidate = Plan(id="p2", parent_id="p", assignments=result.assignments)
    assert validate(inst, candidate, base=base, free={"a", "b"}, context=context).passed


def test_public_baseline_raw_api() -> None:
    from scheduler_core.baselines.b2_full import b2_full_replan
    from scheduler_core.baselines.b3_rule import b3_rule_repair
    from scheduler_core.models import ReplanParams

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=20),
        now=2,
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=2, compatible_devices=["d"])],
    )
    base = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=6, end=8)})
    events = [DeviceOutage(device_id="d", start=6, end=10)]
    assert b2_full_replan(inst, base, events, ReplanParams(total_budget_s=5)) is not None
    assert b3_rule_repair(inst, base, events) is not None
    assert inst.blocked == []


def test_raw_future_outage_does_not_interrupt_running_task() -> None:
    from scheduler_core.replanning.events import prepare_raw
    from scheduler_core.validation_context import ExecutionRecord

    task = Task(
        id="a", experiment_id="e", type="x", duration=6, compatible_devices=["d"], status="RUNNING"
    )
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=20),
        now=2,
        devices=[Device(id="d", type="x")],
        tasks=[task],
    )
    base = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=6)})
    context = ValidationContext(
        snapshot=ExecutionSnapshot(
            plan_id="p",
            as_of=2,
            base_as_of=0,
            records=[
                ExecutionRecord(
                    task_id="a",
                    status="RUNNING",
                    device_id="d",
                    start=0,
                    planned_end=6,
                    remaining_estimate=4,
                    event_id="observed",
                )
            ],
        )
    )
    before = inst.model_dump_json(), context.model_dump_json()
    post, evidence = prepare_raw(
        inst, base, [DeviceOutage(device_id="d", start=8, end=10)], context
    )
    assert len(post.tasks) == 1 and post.tasks[0].status == "RUNNING"
    assert evidence.snapshot is not None and len(evidence.snapshot.records) == 1
    assert len(post.blocked) == 1
    from scheduler_core.replan import replan

    result = replan(inst, base, [DeviceOutage(device_id="d", start=8, end=10)], context=context)
    assert (
        result.status == "OK"
        and result.candidates[0].plan.assignments["a"] == base.assignments["a"]
    )
    assert (inst.model_dump_json(), context.model_dump_json()) == before


def test_raw_overrun_binds_running_evidence_to_candidate() -> None:
    from scheduler_core.models import ReplanParams, TaskOverrun
    from scheduler_core.replan import replan
    from scheduler_core.validation_context import ExecutionRecord, FrozenEndChange
    from scheduler_core.validate import validate

    task = Task(
        id="a", experiment_id="e", type="x", duration=6, compatible_devices=["d"], status="RUNNING"
    )
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=20),
        now=2,
        devices=[Device(id="d", type="x")],
        tasks=[task],
    )
    base = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=6)})
    context = ValidationContext(
        snapshot=ExecutionSnapshot(
            plan_id="p",
            as_of=2,
            base_as_of=0,
            records=[
                ExecutionRecord(
                    task_id="a",
                    status="RUNNING",
                    device_id="d",
                    start=0,
                    planned_end=6,
                    remaining_estimate=6,
                    event_id="execution-observation",
                )
            ],
        )
    )
    before = context.model_dump_json()
    result = replan(
        inst,
        base,
        [TaskOverrun(task_id="a", new_end=8)],
        ReplanParams(total_budget_s=5),
        context=context,
    )
    assert result.status == "OK"
    candidate = result.candidates[0].plan
    assert candidate.assignments["a"].end == 8
    evidence = context.model_copy(deep=True)
    evidence.end_changes.append(
        FrozenEndChange(
            task_id="a",
            plan_id=candidate.id,
            base_plan_id=base.id,
            old_end=6,
            new_end=8,
            event_id="execution-observation",
            acted_at=2,
        )
    )
    assert validate(inst, candidate, base=base, free=set(), context=evidence).passed
    assert context.model_dump_json() == before
    with pytest.raises(ValueError, match="overrun"):
        replan(inst, base, [TaskOverrun(task_id="a", new_end=9)], context=context)
    invalid = context.model_copy(deep=True)
    assert invalid.snapshot is not None
    invalid.snapshot.records[0].device_id = "other"
    with pytest.raises(ValueError, match="overrun"):
        replan(inst, base, [TaskOverrun(task_id="a", new_end=8)], context=invalid)


def test_overrun_propagates_frozen_source_to_cross_device_successor() -> None:
    from scheduler_core.models import ReplanParams, TaskOverrun
    from scheduler_core.replan import replan
    from scheduler_core.validation_context import ExecutionRecord

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=20),
        now=2,
        devices=[Device(id="d1", type="x"), Device(id="d2", type="x")],
        tasks=[
            Task(
                id="a",
                experiment_id="e",
                type="x",
                duration=6,
                compatible_devices=["d1"],
                status="RUNNING",
            ),
            Task(id="b", experiment_id="e", type="x", duration=2, compatible_devices=["d2"]),
        ],
        precedences=[Precedence(pred="a", succ="b")],
    )
    base = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d1", start=0, end=6),
            "b": Assignment(task_id="b", device_id="d2", start=6, end=8),
        },
    )
    context = ValidationContext(
        snapshot=ExecutionSnapshot(
            plan_id="p",
            as_of=2,
            base_as_of=0,
            records=[
                ExecutionRecord(
                    task_id="a",
                    status="RUNNING",
                    device_id="d1",
                    start=0,
                    planned_end=6,
                    remaining_estimate=6,
                    event_id="observed",
                )
            ],
        )
    )
    result = replan(
        inst,
        base,
        [TaskOverrun(task_id="a", new_end=8)],
        ReplanParams(total_budget_s=5),
        context=context,
    )
    assert result.status == "OK" and result.level_reached == 0
    assert (
        result.impact is not None
        and result.impact.frozen == {"a"}
        and result.impact.affected == {"b"}
    )
    assert result.impact.reasons["b"] == "successor:a"
    assert result.candidates[0].plan.assignments["b"].start >= 8


@pytest.mark.parametrize(
    "field,value",
    [
        ("total_budget_s", float("nan")),
        ("total_budget_s", float("inf")),
        ("total_budget_s", 0),
        ("num_workers", 0),
        ("num_workers", 2147483648),
        ("seed", -1),
        ("seed", 2147483648),
        ("window_slots", -1),
        ("max_level", 4),
    ],
)
def test_public_replan_and_b3_reject_invalid_search_parameters(field: str, value: float) -> None:
    from scheduler_core.baselines.b2_full import b2_full_replan
    from scheduler_core.baselines.b3_rule import b3_rule_repair
    from scheduler_core.models import ReplanParams
    from scheduler_core.replan import replan

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=10),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=1, compatible_devices=["d"])],
    )
    base = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=3, end=4)})
    params = ReplanParams().model_copy(update={field: value})
    for call in (
        lambda: replan(inst, base, [], params),
        lambda: b2_full_replan(inst, base, [], params),
        lambda: b3_rule_repair(inst, base, [], params=params),
    ):
        with pytest.raises(ValueError, match=field):
            call()
