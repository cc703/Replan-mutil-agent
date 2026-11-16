"""P2-2 search equivalence and fallback regression tests."""

from datetime import datetime, timezone
from itertools import product
from typing import Any

import pytest

from scheduler_core.models import (
    Assignment,
    BlockedWindow,
    Device,
    Instance,
    Person,
    Plan,
    Precedence,
    SetupRule,
    Task,
    TimeAxis,
)
from scheduler_core.solving import run, search
from scheduler_core.validate import validate


def make_instance(index: int) -> Instance:
    n = 2 + index % 2
    ids = [f"d{i}" for i in range(n)]
    duration_a = 1 + (index // 2) % 2
    duration_b = 1 + (index // 4) % 2
    person = bool((index // 8) % 2)
    setup = (index // 16) % 2
    window = bool((index // 32) % 2)
    lag = bool((index // 64) % 2)
    deadline = 3 + (index // 128) % 2
    return Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=4),
        devices=[Device(id=d, type="x") for d in ids],
        tasks=[
            Task(
                id="a",
                experiment_id="e",
                type="x",
                duration=duration_a,
                compatible_devices=ids,
                requires_person=person,
            ),
            Task(
                id="b",
                experiment_id="e",
                type="x",
                duration=duration_b,
                compatible_devices=ids,
                deadline=deadline,
                requires_person=person,
            ),
        ],
        persons=[Person(id="p")] if person else [],
        setups=[SetupRule(device_id=d, task_type="x", slots=setup) for d in ids],
        blocked=[BlockedWindow(device_id=d, start=0, end=1, kind="CLOSED") for d in ids]
        if window
        else [],
        precedences=[Precedence(pred="a", succ="b", lag_min=0, lag_max=1)] if lag else [],
    )


def oracle(inst: Instance) -> float | None:
    choices = []
    for task in inst.tasks:
        people: list[str | None] = [p.id for p in inst.persons] if task.needs_person else [None]
        choices.append(
            [
                Assignment(
                    task_id=task.id, device_id=d, person_id=p, start=s, end=s + task.duration
                )
                for d, p, s in product(
                    task.compatible_devices,
                    people,
                    range(inst.axis.horizon_slots - task.duration + 1),
                )
            ]
        )
    scores = []
    for combination in product(*choices):
        assignments = {a.task_id: a for a in combination}
        if not validate(inst, Plan(id="oracle", assignments=assignments)).passed:
            continue
        loads = {d.id: 0 for d in inst.devices}
        for task in inst.tasks:
            loads[assignments[task.id].device_id] += task.duration * task.demand
        scores.append(
            max(a.end for a in combination) + 0.1 * (max(loads.values()) - min(loads.values()))
        )
    return min(scores) if scores else None


def assert_result(inst: Instance, result: Any, expected: float | None) -> None:
    if expected is None:
        assert result.status == "INFEASIBLE"
        return
    assert result.status == "OPTIMAL"
    assert result.objective == pytest.approx(expected)
    assert result.assignments is not None
    assert validate(inst, Plan(id="result", assignments=result.assignments)).passed


def test_exhaustive_equivalent_devices() -> None:
    for index in range(160):
        inst = make_instance(index)
        expected = oracle(inst)
        for enabled in (False, True):
            result = run.run_model(inst, 5, 1, 0, None, use_search=enabled, use_strategy=False)
            assert_result(inst, result, expected)


@pytest.mark.parametrize(
    "difference", ["capacity", "window", "setup", "capabilities", "compatibility"]
)
def test_near_equivalent_devices(difference: str) -> None:
    inst = make_instance(0)
    if difference == "capacity":
        inst.devices[1].capacity = 2
    elif difference == "window":
        inst.blocked.append(BlockedWindow(device_id="d1", start=0, end=1, kind="CLOSED"))
    elif difference == "setup":
        inst.setups[1].slots = 1
    elif difference == "capabilities":
        inst.devices[1].capabilities = {"special"}
    else:
        inst.tasks[0].compatible_devices = ["d1"]
    assert not any({"d0", "d1"} <= set(group) for group in search.equivalent_device_classes(inst))
    expected = oracle(inst)
    assert_result(inst, run.run_model(inst, 5, 1, 0, None, use_search=True), expected)


def test_forced_false_equivalence_changes_optimum(monkeypatch: pytest.MonkeyPatch) -> None:
    inst = make_instance(0)
    inst.tasks[1].compatible_devices = ["d1"]
    expected = oracle(inst)
    assert expected is not None
    monkeypatch.setattr(search, "equivalent_device_classes", lambda _: [["d0", "d1"]])
    result = run.run_model(inst, 5, 1, 0, None, use_search=True, use_strategy=False)
    assert result.status == "INFEASIBLE" or (
        result.objective is not None and result.objective > expected
    )


@pytest.mark.parametrize("failure", ["exception", "timeout", "partial", "invalid", "validation"])
def test_hint_faults_leave_no_hint(monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    from scheduler_core.solving import hint

    inst = make_instance(0)
    model, starts, _, selected, people, _, _ = run._build_model(inst, 4, 2, 10, 1)
    ordered = search.ordered_task_ids(inst)
    valid = hint.build_hint(inst, ordered, float("inf"))
    assert valid is not None
    if failure == "exception":

        def broken(*args: Any) -> Any:
            raise RuntimeError("injected")

        monkeypatch.setattr(hint, "build_hint", broken)
    elif failure == "timeout":
        monkeypatch.setattr(
            search,
            "time",
            type("Clock", (), {"perf_counter": staticmethod(iter([0.0, 2.0]).__next__)})(),
        )
        monkeypatch.setattr(hint, "build_hint", lambda *args: valid)
    elif failure == "partial":
        monkeypatch.setattr(hint, "build_hint", lambda *args: Plan(id="partial", assignments={}))
    elif failure == "invalid":
        invalid = valid.model_copy(deep=True)
        invalid.assignments["a"].end += 1
        monkeypatch.setattr(hint, "build_hint", lambda *args: invalid)
    else:
        monkeypatch.setattr(hint, "build_hint", lambda *args: valid)
        monkeypatch.setattr(
            search, "validate", lambda *args: type("Report", (), {"passed": False})()
        )
    search.add_hint(model, inst, ordered, starts, selected, people, 10)
    assert len(model.proto.solution_hint.vars) == 0


@pytest.mark.parametrize("failure", ["exception", "partial", "invalid"])
def test_hint_failure_solve_matches_disabled(monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    from scheduler_core.solving import hint

    inst = make_instance(0)
    baseline = run.run_model(inst, 5, 1, 0, None, use_search=False)
    if failure == "exception":

        def broken(*args: Any) -> Any:
            raise RuntimeError("injected")

        monkeypatch.setattr(hint, "build_hint", broken)
    elif failure == "partial":
        monkeypatch.setattr(hint, "build_hint", lambda *args: Plan(id="partial", assignments={}))
    else:
        plan = hint.build_hint(inst, search.ordered_task_ids(inst), float("inf"))
        assert plan is not None
        plan.assignments["a"].end += 1
        monkeypatch.setattr(hint, "build_hint", lambda *args: plan)
    result = run.run_model(inst, 5, 1, 0, None, use_search=True, use_strategy=False)
    assert_result(inst, result, baseline.objective)


def test_sub_tick_hint_budget_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    from scheduler_core.solving import hint

    inst = make_instance(0)
    ordered = search.ordered_task_ids(inst)
    valid = hint.build_hint(inst, ordered, float("inf"))
    assert valid is not None
    model, starts, _, selected, people, _, _ = run._build_model(inst, 4, 2, 10, 1)
    # 5% of 0.1 s is 5 ms; elapsed 6 ms, both within one old 15.625 ms tick.
    clock = iter([10.0, 10.006])
    monkeypatch.setattr(
        search, "time", type("Clock", (), {"perf_counter": staticmethod(clock.__next__)})()
    )
    monkeypatch.setattr(hint, "build_hint", lambda *args: valid)
    search.add_hint(model, inst, ordered, starts, selected, people, 0.1)
    assert not model.proto.solution_hint.vars


def test_solver_receives_remaining_high_resolution_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    from ortools.sat.python import cp_model

    clock = iter([10.0, 10.006])
    monkeypatch.setattr(
        run, "time", type("Clock", (), {"perf_counter": staticmethod(clock.__next__)})()
    )
    monkeypatch.setattr(search, "add_hint", lambda *args: None)
    limits: list[float] = []

    class RecordingSolver(cp_model.CpSolver):
        def solve(self, *args: Any, **kwargs: Any) -> Any:
            limits.append(self.parameters.max_time_in_seconds)
            return super().solve(*args, **kwargs)

    monkeypatch.setattr(cp_model, "CpSolver", RecordingSolver)
    run.run_model(make_instance(0), 0.01, 1, 0, None)
    assert limits == pytest.approx([0.004])
