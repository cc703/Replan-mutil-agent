from datetime import datetime, timezone

import pytest

from scheduler_core.axis import TimeAxis
from scheduler_core.diagnose import DiagnosisUnknownError, diagnose, diagnose_detailed
from scheduler_core.models import Device, Instance, Task


def instance(duration: int = 4, deadline: int = 3, horizon: int = 10) -> Instance:
    return Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=horizon),
        devices=[Device(id="D", type="d")],
        tasks=[
            Task(
                id="X",
                experiment_id="e",
                type="t",
                duration=duration,
                deadline=deadline,
                deadline_level="HARD",
                compatible_devices=["D"],
            )
        ],
    )


def test_deadline_core() -> None:
    result = diagnose_detailed(instance(), None, None)
    assert result.status == "CORE"
    assert result.core is not None and result.core.group_ids == ["deadline:X"]
    assert result.minimal


def test_feasible() -> None:
    assert diagnose(instance(deadline=5), None, None) is None


def test_background() -> None:
    result = diagnose_detailed(instance(duration=11, deadline=3), None, None)
    assert result.status == "BACKGROUND"
    assert result.core is not None and result.core.group_ids == []


def test_unknown() -> None:
    with pytest.raises(DiagnosisUnknownError):
        diagnose(instance(), None, None, time_limit_s=1e-12)


def test_unrelated_deadline_does_not_enter_core() -> None:
    from scheduler_core.models import Device, Task

    inst = instance()
    inst.devices.append(Device(id="E", type="d"))
    inst.tasks.append(
        Task(id="Y", experiment_id="e", type="t", duration=1, deadline=8, compatible_devices=["E"])
    )
    result = diagnose_detailed(inst, None, None)
    assert result.core is not None and result.core.group_ids == ["deadline:X"]
    assert result.minimal


def test_guard_rejects_conflicting_proofs(monkeypatch: pytest.MonkeyPatch) -> None:
    from scheduler_core.diagnose import DiagnosisInconsistent
    from scheduler_core.models import Assignment, Plan
    from scheduler_core.replanning.model import ModelResult
    from scheduler_core.validation_context import ExecutionSnapshot, ValidationContext

    inst = instance(deadline=5)
    base = Plan(id="p", assignments={"X": Assignment(task_id="X", device_id="D", start=0, end=4)})
    ctx = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=0, base_as_of=0))
    answers = iter(["OPTIMAL", "INFEASIBLE"])
    monkeypatch.setattr(
        "scheduler_core.diagnose.solve_neighborhood",
        lambda *args, **kwargs: ModelResult(next(answers), None, None, None),
    )
    with pytest.raises(DiagnosisInconsistent):
        diagnose_detailed(inst, base, None, context=ctx)


def test_replanning_does_not_start_solver_after_build_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ortools.sat.python import cp_model
    from scheduler_core.models import Assignment, Plan, ReplanParams
    from scheduler_core.replanning.model import solve_neighborhood
    from scheduler_core.validation_context import ExecutionSnapshot, ValidationContext

    inst = instance(deadline=5)
    base = Plan(id="p", assignments={"X": Assignment(task_id="X", device_id="D", start=0, end=4)})
    ctx = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=0, base_as_of=0))
    ticks = iter([0.0, 1.0])
    monkeypatch.setattr("scheduler_core.replanning.model.time.perf_counter", lambda: next(ticks))
    calls: list[object] = []

    def spy(self: cp_model.CpSolver, model: cp_model.CpModel) -> cp_model.CpSolverStatus:
        calls.append(model)
        return cp_model.UNKNOWN

    monkeypatch.setattr(cp_model.CpSolver, "solve", spy)
    result = solve_neighborhood(inst, base, {"X"}, set(), ctx, set(), ReplanParams(), 1.0)
    assert result.status == "UNKNOWN"
    assert result.assignments is None and result.objective is None and result.bound is None
    assert result.deltas is None and result.assumption_core is None
    assert calls == []
