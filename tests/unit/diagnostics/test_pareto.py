from itertools import permutations

import pytest

from scheduler_core.models import Assignment, Candidate, Plan, ValidationReport
from scheduler_core.pareto import select_candidates


def candidate(
    name: str,
    vector: tuple[float, float, float],
    start: int = 0,
    device: str = "d",
    person: str | None = None,
    passed: bool = True,
    level: int = 0,
) -> Candidate:
    a = Assignment(task_id="t", device_id=device, person_id=person, start=start, end=start + 1)
    return Candidate(
        plan=Plan(id=name, assignments={"t": a}),
        level=level,
        weights=(1, 1),
        f1=vector[0],
        f2=vector[1],
        f3=vector[2],
        validation=ValidationReport(passed=passed),
    )


def test_dominance_resources_and_validation() -> None:
    pool = [
        candidate("a", (1, 2, 3)),
        candidate("b", (1, 2, 3), device="e"),
        candidate("c", (2, 3, 4), device="f"),
        candidate("invalid", (0, 0, 0), passed=False),
    ]
    assert {c.plan.id for c in select_candidates(pool)} == {"a", "b"}


def test_distance_boundary_and_level_priority() -> None:
    pool = [
        candidate("a", (1, 1, 1), start=0, level=0),
        candidate("b", (1, 1, 1), start=2, level=1),
        candidate("c", (1, 1, 1), start=3, level=2),
    ]
    assert {c.plan.id for c in select_candidates(pool)} == {"a", "c"}
    assert len(select_candidates(pool, dedupe_l1=0)) == 3


def test_labels_stability_and_maximum() -> None:
    pool = [
        candidate("a", (0, 3, 1), device="a"),
        candidate("b", (3, 0, 1), device="b"),
        candidate("c", (2, 2, 1), device="c"),
    ]
    results = [
        [(c.plan.id, c.label) for c in select_candidates(list(p), max_n=2)]
        for p in permutations(pool)
    ]
    assert all(result == results[0] for result in results)
    assert results[0] == [("b", "最稳"), ("a", "最少延期")]
    assert all("最早完成紧急" not in (label or "") for _, label in results[0])


def test_multiple_labels_and_person_difference() -> None:
    pool = [candidate("a", (1, 1, 1), person="p"), candidate("b", (1, 1, 1), person="q")]
    out = select_candidates(pool)
    assert len(out) == 2
    assert out[0].label == "均衡"
    assert out[1].label is None


@pytest.mark.parametrize(
    "key,value,error",
    [
        ("max_n", True, TypeError),
        ("max_n", float("nan"), TypeError),
        ("max_n", float("inf"), TypeError),
        ("max_n", 0, ValueError),
        ("max_n", 11, ValueError),
        ("dedupe_l1", False, TypeError),
        ("dedupe_l1", float("nan"), TypeError),
        ("dedupe_l1", -1, ValueError),
    ],
)
def test_parameters(key: str, value: object, error: type[Exception]) -> None:
    with pytest.raises(error):
        select_candidates([], **{key: value})  # type: ignore[arg-type]


def test_nonfinite_objective_rejected() -> None:
    with pytest.raises(ValueError, match="finite"):
        select_candidates([candidate("bad", (float("nan"), 1, 1))])
