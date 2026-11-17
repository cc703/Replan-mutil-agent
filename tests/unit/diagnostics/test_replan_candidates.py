from datetime import datetime, timezone

import pytest

from scheduler_core.axis import TimeAxis
from scheduler_core.models import (
    Assignment,
    Device,
    DeviceOutage,
    Instance,
    Plan,
    ReplanParams,
    Task,
)
from scheduler_core.replanning.model import ModelResult
from scheduler_core.replanning.pool import replan_candidates
from scheduler_core.validation_context import (
    DeadlineAuthorization,
    ExecutionSnapshot,
    ValidationContext,
)


def fixture() -> tuple[Instance, Plan, DeviceOutage]:
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=20),
        tasks=[
            Task(
                id="t",
                experiment_id="e",
                type="x",
                duration=2,
                compatible_devices=["d", "e"],
                deadline=15,
            )
        ],
        devices=[Device(id="d", type="x"), Device(id="e", type="x")],
    )
    base = Plan(id="p", assignments={"t": Assignment(task_id="t", device_id="d", start=4, end=6)})
    return inst, base, DeviceOutage(device_id="d", start=4, end=7)


def test_candidates_validate_and_event_applied_once() -> None:
    inst, base, event = fixture()
    before = inst.model_dump_json()
    result = replan_candidates(inst, base, [event], ReplanParams(total_budget_s=5))
    assert result.status == "OK" and result.candidates
    assert all(c.validation.passed for c in result.candidates)
    assert all(c.plan.id.startswith("p.replan.l") for c in result.candidates)
    assert len({c.plan.id for c in result.candidates}) == len(result.candidates)
    assert inst.model_dump_json() == before


def test_existing_candidate_survives_later_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    inst, base, event = fixture()
    from scheduler_core.replanning.model import solve_neighborhood

    real = solve_neighborhood
    calls = 0

    def solve(*args: object, **kwargs: object) -> ModelResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return real(*args, **kwargs)  # type: ignore[arg-type]
        return ModelResult("UNKNOWN", None, None, None)

    monkeypatch.setattr("scheduler_core.replanning.pool.solve_neighborhood", solve)
    result = replan_candidates(inst, base, [event], ReplanParams(total_budget_s=5))
    assert calls > 1 and result.status == "OK" and result.candidates


def test_restricted_infeasibility_is_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    inst, base, event = fixture()
    monkeypatch.setattr(
        "scheduler_core.replanning.pool.solve_neighborhood",
        lambda *args, **kwargs: ModelResult("INFEASIBLE", None, None, None),
    )
    result = replan_candidates(
        inst, base, [event], ReplanParams(max_level=2), diagnose_on_infeasible=False
    )
    assert result.status == "TIMEOUT" and result.conflict is None


def test_authorization_is_not_rebound() -> None:
    from scheduler_core.replanning.pool import _candidate_context

    inst, base, _ = fixture()
    auth = DeadlineAuthorization(
        task_id="t",
        plan_id="p.replan.l0.w0",
        original_deadline=15,
        relaxed_deadline=18,
        confirmation_id="real",
        acted_at=0,
    )
    ctx = ValidationContext(
        snapshot=ExecutionSnapshot(plan_id="p", as_of=0), deadline_authorizations=[auth]
    )
    matched = _candidate_context(ctx, "p.replan.l0.w0", base, inst, [])
    other = _candidate_context(ctx, "p.replan.l0.w1", base, inst, [])
    assert matched.deadline_authorizations == [auth]
    assert other.deadline_authorizations == []
    assert ctx.deadline_authorizations == [auth]


@pytest.mark.parametrize(
    "grid", [[], [(0, 0)], [(float("nan"), 1)], [(1, float("inf"))], [(1, 1)] * 5]
)
def test_invalid_grid(grid: list[tuple[float, float]]) -> None:
    inst, base, event = fixture()
    with pytest.raises(ValueError):
        replan_candidates(inst, base, [event], ReplanParams(weight_grid=grid))


def test_reference_metrics_ignore_grid_and_ids_stable() -> None:
    from scheduler_core.replanning.pool import _make_candidate

    inst, base, _ = fixture()
    assignments = {"t": Assignment(task_id="t", device_id="e", start=7, end=9)}
    ctx = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=0))
    params = ReplanParams(beta_moved=2, beta_switched=5, beta_shift=1)
    a = _make_candidate(
        inst, base, assignments, 0, (1, 0.5), params, set(), "p.replan.l0.w0", 0, {"t"}, ctx
    )
    b = _make_candidate(
        inst, base, assignments, 1, (4, 2), params, set(), "p.replan.l1.w1", 0, {"t"}, ctx
    )
    assert (a.f1, a.f2, a.f3) == (b.f1, b.f2, b.f3) == (0, 7.15, 0)
    assert a.weights != b.weights


def test_unknown_in_final_grid_does_not_claim_infeasible(monkeypatch: pytest.MonkeyPatch) -> None:
    inst, base, event = fixture()
    statuses = iter(["INFEASIBLE", "UNKNOWN"])
    monkeypatch.setattr(
        "scheduler_core.replanning.pool.solve_neighborhood",
        lambda *args, **kwargs: ModelResult(next(statuses), None, None, None),
    )
    p = ReplanParams(weight_grid=[(1, 1), (2, 1)], total_budget_s=5)
    result = replan_candidates(inst, base, [event], p, full=True, diagnose_on_infeasible=False)
    assert result.status == "TIMEOUT" and result.conflict is None


def test_complete_final_level_proves_infeasible(monkeypatch: pytest.MonkeyPatch) -> None:
    inst, base, event = fixture()
    monkeypatch.setattr(
        "scheduler_core.replanning.pool.solve_neighborhood",
        lambda *args, **kwargs: ModelResult("INFEASIBLE", None, None, None),
    )
    p = ReplanParams(weight_grid=[(1, 1), (2, 1)], total_budget_s=5)
    result = replan_candidates(inst, base, [event], p, full=True, diagnose_on_infeasible=False)
    assert result.status == "INFEASIBLE" and result.conflict is None


def test_grid_produces_distinct_valid_tradeoffs() -> None:
    from scheduler_core.models import UrgentInsert

    axis = TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=20)
    task = Task(id="t", experiment_id="e", type="x", duration=4, compatible_devices=["d"])
    urgent = Task(id="u", experiment_id="e", type="x", duration=1, compatible_devices=["d"])
    inst = Instance(axis=axis, devices=[Device(id="d", type="x")], tasks=[task])
    base = Plan(id="p", assignments={"t": Assignment(task_id="t", device_id="d", start=0, end=4)})
    p = ReplanParams(weight_grid=[(1, 0.01), (1, 10)], gamma=5, total_budget_s=5, max_level=0)
    result = replan_candidates(inst, base, [UrgentInsert(tasks=[urgent])], p)
    assert result.status == "OK"
    assert len(result.candidates) == 2
    assert all(c.validation.passed for c in result.candidates)
    assert {c.plan.assignments["u"].start for c in result.candidates} == {0, 4}


def test_post_applied_same_result_as_raw() -> None:
    from scheduler_core.replanning.events import prepare_raw

    inst, base, event = fixture()
    ctx = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=0, base_as_of=0))
    post, post_ctx = prepare_raw(inst, base, [event], ctx)
    params = ReplanParams(weight_grid=[(1, 1)], max_level=0, total_budget_s=5)
    raw = replan_candidates(inst, base, [event], params, context=ctx)
    applied = replan_candidates(post, base, [event], params, context=post_ctx, post_applied=True)
    assert raw.status == applied.status == "OK"
    assert raw.candidates[0].plan.assignments == applied.candidates[0].plan.assignments
    assert len(post.blocked) == 1 and not inst.blocked


def test_timeout_before_validation_discards_unverified(monkeypatch: pytest.MonkeyPatch) -> None:
    inst, base, event = fixture()
    ticks = iter([0.0, 0.0, 0.0, 1.1])
    monkeypatch.setattr("scheduler_core.replanning.pool.time.perf_counter", lambda: next(ticks))
    assignments = {"t": Assignment(task_id="t", device_id="e", start=4, end=6)}
    monkeypatch.setattr(
        "scheduler_core.replanning.pool.solve_neighborhood",
        lambda *args, **kwargs: ModelResult("OPTIMAL", assignments, 0, 0),
    )
    result = replan_candidates(inst, base, [event], ReplanParams(total_budget_s=1))
    assert result.status == "TIMEOUT" and not result.candidates


def test_overrun_evidence_uses_candidate_id_and_does_not_mutate() -> None:
    from scheduler_core.models import TaskOverrun
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
    ctx = ValidationContext(
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
                    event_id="observed",
                )
            ],
        )
    )
    before = ctx.model_dump_json()
    result = replan_candidates(
        inst,
        base,
        [TaskOverrun(task_id="a", new_end=8)],
        ReplanParams(total_budget_s=5),
        context=ctx,
    )
    assert result.status == "OK" and result.candidates[0].plan.assignments["a"].end == 8
    assert ctx.model_dump_json() == before
    with pytest.raises(ValueError, match="overrun"):
        replan_candidates(inst, base, [TaskOverrun(task_id="a", new_end=9)], context=ctx)


def test_infeasible_integration_fills_diagnosis_and_relaxation() -> None:
    task = Task(
        id="t",
        experiment_id="e",
        type="x",
        duration=2,
        compatible_devices=["d"],
        deadline=1,
        deadline_level="NEGOTIABLE",
    )
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=10),
        devices=[Device(id="d", type="x")],
        tasks=[task],
    )
    base = Plan(id="p", assignments={"t": Assignment(task_id="t", device_id="d", start=0, end=2)})
    result = replan_candidates(
        inst, base, [], ReplanParams(total_budget_s=5, weight_grid=[(1, 1)]), full=True
    )
    assert result.status == "INFEASIBLE"
    assert result.conflict is not None and result.conflict.group_ids == ["deadline:t"]
    assert result.relaxations and result.relaxations[0].relaxed_groups == ["deadline:t"]


def test_unknown_diagnosis_does_not_invent_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    from scheduler_core.diagnose import DiagnoseResult

    inst, base, event = fixture()
    monkeypatch.setattr(
        "scheduler_core.replanning.pool.solve_neighborhood",
        lambda *args, **kwargs: ModelResult("INFEASIBLE", None, None, None),
    )
    monkeypatch.setattr(
        "scheduler_core.diagnose.diagnose_detailed",
        lambda *args, **kwargs: DiagnoseResult("UNKNOWN", None, False, (), 0, 0, 0),
    )
    result = replan_candidates(inst, base, [event], ReplanParams(weight_grid=[(1, 1)]), full=True)
    assert result.status == "INFEASIBLE" and result.conflict is None and not result.relaxations


def test_authorized_candidate_domains_do_not_get_base_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inst, base, event = fixture()
    auth = DeadlineAuthorization(
        task_id="t",
        plan_id="p.replan.l3.w0",
        original_deadline=15,
        relaxed_deadline=18,
        confirmation_id="real",
        acted_at=0,
    )
    ctx = ValidationContext(
        snapshot=ExecutionSnapshot(plan_id="p", as_of=0), deadline_authorizations=[auth]
    )
    monkeypatch.setattr(
        "scheduler_core.replanning.pool.solve_neighborhood",
        lambda *args, **kwargs: ModelResult("INFEASIBLE", None, None, None),
    )

    def bad(*args: object, **kwargs: object) -> None:
        raise AssertionError("cannot diagnose using base authorization domain")

    monkeypatch.setattr("scheduler_core.diagnose.diagnose_detailed", bad)
    result = replan_candidates(
        inst, base, [event], ReplanParams(weight_grid=[(1, 1)]), full=True, context=ctx
    )
    assert result.status == "INFEASIBLE" and result.conflict is None


def test_candidate_solve_preserves_caller_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    inst, base, event = fixture()
    seen: list[int] = []

    def solve(*args: object, **kwargs: object) -> ModelResult:
        params = args[6]
        assert isinstance(params, ReplanParams)
        seen.append(params.num_workers)
        return ModelResult("UNKNOWN", None, None, None)

    monkeypatch.setattr("scheduler_core.replanning.pool.solve_neighborhood", solve)
    replan_candidates(
        inst,
        base,
        [event],
        ReplanParams(num_workers=4, weight_grid=[(1, 1)]),
        full=True,
        diagnose_on_infeasible=False,
    )
    assert seen == [4]
