"""Experiment identifiers and allocation."""

import numpy as np

from scheduler_core.generation.dag import experiment_sizes
from scheduler_core.generation.params import GeneratorParams
from scheduler_core.models import Device, Person, Task


def task_groups(tasks: int, experiments: int, rng: np.random.Generator) -> list[list[str]]:
    """Return stable task IDs divided as evenly as possible among experiments.

    Expects nonnegative tasks and positive experiments. Advances rng to choose
    remainder recipients; performs no IO. Zero experiments raises
    ZeroDivisionError; other preconditions are not validated."""
    sizes = experiment_sizes(tasks, experiments, rng)
    return [[f"e{i:03d}-t{j:02d}" for j in range(1, size + 1)] for i, size in enumerate(sizes, 1)]


def make_tasks(
    groups: list[list[str]],
    types: int,
    devices: list[Device],
    persons: list[Person],
    params: GeneratorParams,
    random: dict[str, np.random.Generator],
) -> list[Task]:
    """Return new tasks for generated groups, devices and personnel.

    Expects nonempty valid groups, positive types, a device of each type,
    personnel covering configured skills, valid params and named RNG streams.
    Advances the supplied generators but does not mutate other inputs or do IO.
    Preconditions are not independently validated by this helper."""
    tasks = []
    for group in groups:
        for task_id in group:
            r = random["attributes"]
            primary = int(r.integers(types)) + 1
            choices = {primary}
            if r.random() < params.multi_type_prob and types > 1:
                others = [i for i in range(1, types + 1) if i != primary]
                choices.add(others[int(r.integers(len(others)))])
            demand = 2 if r.random() < params.demand2_prob else 1
            compatible = [
                d.id for d in devices if int(d.type[4:]) in choices and d.capacity >= demand
            ]
            if not compatible:
                demand = 1
                compatible = [d.id for d in devices if int(d.type[4:]) in choices]
            skills: set[str] = set()
            skill_rng = random["skills"]
            if skill_rng.random() < params.skill_task_prob:
                singles = sorted({skill for person in persons for skill in person.skills})
                pairs = sorted(
                    {
                        (a, b)
                        for person in persons
                        for a in person.skills
                        for b in person.skills
                        if a < b
                    }
                )
                choose_pair = skill_rng.random() < params.two_skill_prob
                if choose_pair and pairs:
                    skills.update(pairs[int(skill_rng.integers(len(pairs)))])
                else:
                    skills.add(singles[int(skill_rng.integers(len(singles)))])
            tasks.append(
                Task(
                    id=task_id,
                    experiment_id=task_id.split("-")[0],
                    type=f"type{primary}",
                    duration=int(r.integers(params.duration_min, params.duration_max + 1)),
                    compatible_devices=compatible,
                    demand=demand,
                    required_skills=skills,
                    requires_person=bool(random["persons"].random() < params.person_no_skill_prob),
                    weight=float(random["weights"].random()),
                )
            )
    return tasks
