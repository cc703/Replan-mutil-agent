"""Independent checks of layered DAG structure."""

from fractions import Fraction
from math import ceil

import numpy as np
import pytest

from scheduler_core.generate import generate_instance
from scheduler_core.generation.dag import layered_edges
from scheduler_core.generation.workflow import task_groups


@pytest.mark.parametrize("count,experiments", [(20, 6), (60, 15), (150, 35)])
@pytest.mark.parametrize("ratio", [0.01, 0.6, 1.0])
def test_dag_structure(count: int, experiments: int, ratio: float) -> None:
    rng = np.random.Generator(np.random.PCG64(123))
    groups = task_groups(count, experiments, rng)
    assert sum(map(len, groups)) == count
    assert max(map(len, groups)) - min(map(len, groups)) <= 1
    for ids in groups:
        edges = layered_edges(ids, ratio, 0.15, rng)
        lengths = {task: 1 for task in ids}
        neighbors: dict[str, set[str]] = {task: set() for task in ids}
        for a, b in edges:
            assert a < b
            lengths[b] = max(lengths[b], lengths[a] + 1)
            neighbors[a].add(b)
            neighbors[b].add(a)
        assert max(lengths.values()) == max(2, ceil(Fraction(ratio) * len(ids)))
        seen, pending = set(), [ids[0]]
        while pending:
            node = pending.pop()
            if node not in seen:
                seen.add(node)
                pending.extend(neighbors[node] - seen)
        assert seen == set(ids)


@pytest.mark.parametrize("ratio", [0.01, 0.2, 0.4, 0.6, 0.8, 1.0])
@pytest.mark.parametrize("seed", range(10))
def test_ratio_matrix(ratio: float, seed: int) -> None:
    from scheduler_core.generation.params import GeneratorParams

    for scale in ("S", "M", "L"):
        instance = generate_instance(
            scale, 0.8, 0.5, seed, params=GeneratorParams(dag_depth_ratio=ratio)
        )
        depth: dict[str, int] = {}
        for task in instance.tasks:
            depth[task.id] = 1 + max(
                (depth[p.pred] for p in instance.precedences if p.succ == task.id), default=0
            )
        for experiment in {task.experiment_id for task in instance.tasks}:
            group = [task for task in instance.tasks if task.experiment_id == experiment]
            assert max(depth[task.id] for task in group) == max(
                2, ceil(Fraction(ratio) * len(group))
            )
