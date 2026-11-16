"""Independent small-instance checks for initial scheduling."""

from datetime import datetime, timezone
from itertools import product
import random
from pathlib import Path
from typing import Any

import pytest

from scheduler_core.models import (
    Assignment,
    BlockedWindow,
    Device,
    Instance,
    Person,
    PersonBlockedWindow,
    Plan,
    Precedence,
    SetupRule,
    Task,
    TimeAxis,
)
from scheduler_core.solve_initial import solve_initial, solve_initial_detailed
from scheduler_core.validate import validate


def instance(tasks: list[Task], devices: list[Device] | None = None, **kwargs: Any) -> Instance:
    return Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=8),
        devices=devices or [Device(id="d0", type="x"), Device(id="d1", type="x")],
        tasks=tasks,
        **kwargs,
    )


def task(name: str, duration: int, **kwargs: Any) -> Task:
    return Task(
        id=name,
        experiment_id="e",
        type="x",
        duration=duration,
        compatible_devices=["d0", "d1"],
        **kwargs,
    )


def value(
    inst: Instance, assignments: dict[str, Assignment], weights: tuple[float, float]
) -> float:
    makespan = max((a.end for a in assignments.values()), default=0)
    loads = {d.id: 0 for d in inst.devices}
    by_id = {t.id: t for t in inst.tasks}
    for assignment in assignments.values():
        t = by_id[assignment.task_id]
        loads[assignment.device_id] += t.duration * t.demand
    imbalance = max(
        (
            max(loads[d.id] for d in inst.devices if d.type == kind)
            - min(loads[d.id] for d in inst.devices if d.type == kind)
            for kind in {d.type for d in inst.devices}
        ),
        default=0,
    )
    return weights[0] * makespan + weights[1] * imbalance


def oracle(inst: Instance, weights: tuple[float, float]) -> float | None:
    choices = []
    for t in inst.tasks:
        persons: list[str | None] = [p.id for p in inst.persons] if t.needs_person else [None]
        choices.append(
            [
                Assignment(
                    task_id=t.id,
                    device_id=device,
                    person_id=person,
                    start=start,
                    end=start + t.duration,
                )
                for device, person, start in product(
                    t.compatible_devices, persons, range(inst.axis.horizon_slots - t.duration + 1)
                )
            ]
        )
    best = None
    for combination in product(*choices):
        assignments = {a.task_id: a for a in combination}
        plan = Plan(id="oracle", assignments=assignments)
        if validate(inst, plan).passed:
            score = value(inst, assignments, weights)
            best = score if best is None else min(best, score)
    return best


@pytest.mark.parametrize("weights", [(1, 0), (1, 0.1), (0, 1), (0.001, 0.0001)])
def test_exhaustive_constraints_and_weights(weights: tuple[float, float]) -> None:
    inst = instance(
        [task("a", 2, required_skills={"s"}), task("b", 2, deadline=7)],
        devices=[Device(id="d0", type="x", capacity=2), Device(id="d1", type="x")],
        setups=[SetupRule(device_id="d0", task_type="x", slots=1)],
        blocked=[BlockedWindow(device_id="d1", start=0, end=1, kind="CLOSED")],
        persons=[Person(id="p", skills={"s"}, blocked=[PersonBlockedWindow(start=2, end=3)])],
        precedences=[Precedence(pred="a", succ="b", lag_min=0, lag_max=2)],
    )
    original = inst.model_dump()
    expected = oracle(inst, weights)
    result = solve_initial_detailed(
        inst, num_workers=1, objective_weights={"makespan": weights[0], "imbalance": weights[1]}
    )
    assert result.status == "OPTIMAL"
    assert result.plan is not None and validate(inst, result.plan).passed
    assert result.objective == pytest.approx(expected)
    assert value(inst, result.plan.assignments, weights) == pytest.approx(expected)
    assert inst.model_dump() == original


def test_golden_ten() -> None:
    path = Path(__file__).resolve().parents[2] / "data/fixtures/mini.json"
    inst = Instance.model_validate_json(path.read_text(encoding="utf-8"))
    result = solve_initial_detailed(inst, num_workers=1, objective_weights={"imbalance": 0})
    assert result.status == "OPTIMAL"
    assert result.objective == 10
    assert result.plan is not None and validate(inst, result.plan).passed


def test_infeasible_and_empty() -> None:
    inst = instance([task("a", 2, deadline=1)])
    result = solve_initial_detailed(inst, num_workers=1)
    assert result.status == "INFEASIBLE" and result.plan is None
    assert solve_initial(inst, num_workers=1) is None
    empty = solve_initial_detailed(instance([]), num_workers=1)
    assert empty.status == "OPTIMAL" and empty.objective == 0
    assert empty.plan is not None and validate(instance([]), empty.plan).passed


@pytest.mark.parametrize(
    "weights",
    [
        {"preference": 1},
        {"makespan": -1},
        {"imbalance": float("nan")},
        {"makespan": float("inf")},
        {"other": 1},
        {"makespan": 1e-30},
    ],
)
def test_invalid_weights_rejected(weights: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        solve_initial_detailed(instance([task("a", 1)]), objective_weights=weights)


def test_non_pending_rejected() -> None:
    with pytest.raises(ValueError):
        solve_initial_detailed(instance([task("a", 1, status="SCHEDULED")]))


def test_random_small_instances_against_oracle() -> None:
    rng = random.Random(20261111)
    for index in range(8):
        tasks = [task(str(i), rng.randint(1, 3), release=rng.randint(0, 2)) for i in range(2)]
        inst = instance(tasks)
        expected = oracle(inst, (1, 0.1))
        result = solve_initial_detailed(inst, num_workers=1)
        assert result.status == "OPTIMAL", index
        assert result.plan is not None and validate(inst, result.plan).passed
        assert result.objective == pytest.approx(expected)


@pytest.mark.parametrize("workers", [8, 1])
def test_mini_repeated_solutions(workers: int) -> None:
    path = Path(__file__).resolve().parents[2] / "data/fixtures/mini.json"
    inst = Instance.model_validate_json(path.read_text(encoding="utf-8"))
    results = [
        solve_initial_detailed(
            inst, num_workers=workers, seed=0, objective_weights={"imbalance": 0}
        )
        for _ in range(5)
    ]
    assignments = []
    for result in results:
        assert result.status == "OPTIMAL"
        assert result.objective == 10
        assert result.plan is not None and validate(inst, result.plan).passed
        assignments.append(
            tuple(
                sorted(
                    (a.task_id, a.device_id, a.person_id, a.start, a.end)
                    for a in result.plan.assignments.values()
                )
            )
        )
    if workers == 1:
        assert len(set(assignments)) == 1, assignments


def test_status_mapping_and_validation_barrier(monkeypatch: pytest.MonkeyPatch) -> None:
    from importlib import import_module
    from types import SimpleNamespace

    module = import_module("scheduler_core.solve_initial")
    inst = instance([task("a", 1)])
    raw = SimpleNamespace(
        status="UNKNOWN",
        assignments=None,
        makespan=0,
        objective=None,
        best_bound=None,
        gap=None,
        wall_seconds=0.0,
        reasons=("test",),
    )
    monkeypatch.setattr(module, "run_model", lambda *args: raw)
    assert module.solve_initial_detailed(inst).status == "UNKNOWN"
    assert module.solve_initial(inst) is None
    raw.status = "MODEL_INVALID"
    assert module.solve_initial_detailed(inst).status == "MODEL_INVALID"
    with pytest.raises(RuntimeError):
        module.solve_initial(inst)
    raw.status = "FEASIBLE"
    raw.assignments = {"a": Assignment(task_id="a", device_id="d0", start=0, end=1)}
    actual_validate = module.validate
    calls = 0

    def reject_final(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            return SimpleNamespace(passed=False, violations=["injected failure"])
        return actual_validate(*args, **kwargs)

    monkeypatch.setattr(module, "validate", reject_final)
    with pytest.raises(RuntimeError, match="invalid plan"):
        module.solve_initial_detailed(inst)


def test_capacity_two_and_adjacent_blocks() -> None:
    inst = instance(
        [task("a", 2, deadline=4), task("b", 2, deadline=4)],
        devices=[Device(id="d0", type="x", capacity=2)],
        blocked=[
            BlockedWindow(device_id="d0", start=0, end=1, kind="CLOSED"),
            BlockedWindow(device_id="d0", start=1, end=2, kind="MAINT"),
        ],
    )
    for t in inst.tasks:
        t.compatible_devices = ["d0"]
    result = solve_initial_detailed(inst, num_workers=1)
    assert result.status == "OPTIMAL"
    assert result.plan is not None and validate(inst, result.plan).passed
    assert {(a.start, a.end) for a in result.plan.assignments.values()} == {(2, 4)}
    inst.devices[0].capacity = 1
    assert solve_initial_detailed(inst, num_workers=1).status == "INFEASIBLE"


def test_setup_can_cross_now_and_person_skill_selection() -> None:
    inst = instance(
        [task("a", 2, required_skills={"s"}, deadline=5)],
        now=3,
        setups=[SetupRule(device_id="d0", task_type="x", slots=2)],
        persons=[Person(id="wrong"), Person(id="qualified", skills={"s"})],
    )
    inst.tasks[0].compatible_devices = ["d0"]
    result = solve_initial_detailed(inst, num_workers=1)
    assert result.status == "OPTIMAL"
    assert result.plan is not None and validate(inst, result.plan).passed
    assignment = result.plan.assignments["a"]
    assert (assignment.start, assignment.end, assignment.person_id) == (3, 5, "qualified")
