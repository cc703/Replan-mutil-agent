import pytest
from scheduler_core.generate import generate_instance
from scheduler_core.generation.integrity import check_generated_profile
from fractions import Fraction
from math import ceil
from scheduler_core.models import Task

from tests.unit.generation.generation_oracle import capacity, critical_paths, load, utilization


@pytest.mark.parametrize("scale", ["S", "M", "L"])
@pytest.mark.parametrize("u", [0.6, 0.8, 0.95])
@pytest.mark.parametrize("t", [0.25, 0.5, 0.75])
@pytest.mark.parametrize("seed", range(5))
def test_structure(scale: str, u: float, t: float, seed: int) -> None:
    instance = generate_instance(scale, u, t, seed)
    check_generated_profile(instance, scale)
    assert utilization(instance) <= u
    assert all(
        d.capacity >= task.demand
        for task in instance.tasks
        for d in instance.devices
        if d.id in task.compatible_devices
    )

    horizon = instance.axis.horizon_slots
    cp = max(critical_paths(instance).values())
    previous = capacity(instance, horizon - 1)
    if horizon > cp and previous:
        assert Fraction(load(instance), previous) > Fraction(u)
    else:
        assert horizon == cp or previous == 0

    early: dict[str, int] = {}
    by_experiment: dict[str, list[Task]] = {}
    for task in instance.tasks:
        early[task.id] = task.duration + max(
            (early[p.pred] + p.lag_min for p in instance.precedences if p.succ == task.id),
            default=0,
        )
        by_experiment.setdefault(task.experiment_id, []).append(task)
        assert task.deadline == min(
            horizon, task.release + ceil((1 + (1 - Fraction(t)) * 3) * early[task.id])
        )
        assert task.required_skills <= set.union(*(person.skills for person in instance.persons))
        if task.needs_person:
            assert any(task.required_skills <= person.skills for person in instance.persons)
    assert all(len({task.release for task in group}) == 1 for group in by_experiment.values())
    assert len({(rule.device_id, rule.task_type) for rule in instance.setups}) == len(
        instance.setups
    )
    assert all(0 <= w.start < w.end <= horizon for w in instance.blocked)
    for skill in range(1, 4):
        assert sum(f"skill{skill}" in person.skills for person in instance.persons) >= 2
