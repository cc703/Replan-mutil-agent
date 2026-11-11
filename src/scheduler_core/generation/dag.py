"""Experiment allocation and connected layered directed acyclic graphs."""

from fractions import Fraction
from math import ceil

import numpy as np

from scheduler_core.models import Precedence


def experiment_sizes(tasks: int, experiments: int, rng: np.random.Generator) -> list[int]:
    """Return experiment task counts differing by at most one.

    Expects nonnegative tasks and positive experiments; advances rng to select
    remainder recipients. Zero experiments raises ZeroDivisionError. No IO or
    input mutation other than RNG state; other preconditions are not checked."""
    base, remainder = divmod(tasks, experiments)
    result = [base] * experiments
    for i in rng.permutation(experiments)[:remainder]:
        result[int(i)] += 1
    return result


def layered_edges(
    ids: list[str], ratio: float, probability: float, rng: np.random.Generator
) -> list[tuple[str, str]]:
    """Return sorted directed edges for a layered weakly connected DAG.

    Expects at least two unique ordered IDs, ratio in (0,1], probability in
    [0,1], and a Generator. Longest depth is max(2, ceil(ratio*len(ids)))
    capped at len(ids), with ratio interpreted as an exact binary float.
    Advances rng; does not modify IDs or do IO. Preconditions are not checked."""
    count = len(ids)
    depth = max(2, min(count, ceil(Fraction(ratio) * count)))
    cuts = sorted(int(x) for x in rng.choice(range(1, count), depth - 1, replace=False))
    bounds = [0, *cuts, count]
    layers = [ids[bounds[i] : bounds[i + 1]] for i in range(depth)]
    edges: set[tuple[str, str]] = set()
    for i in range(1, depth):
        for task in layers[i]:
            edges.add((layers[i - 1][int(rng.integers(len(layers[i - 1])))], task))
    for i, layer in enumerate(layers):
        for source in layer:
            for later in layers[i + 1 :]:
                for target in later:
                    if (source, target) not in edges and rng.random() < probability:
                        edges.add((source, target))
    parent = {task: task for task in ids}

    def find(task: str) -> str:
        while parent[task] != task:
            task = parent[task]
        return task

    for source, target in sorted(edges):
        parent[find(source)] = find(target)
    anchor = min(layers[1])
    components: dict[str, list[str]] = {}
    for task in ids:
        components.setdefault(find(task), []).append(task)
    others = sorted(
        (members for root, members in components.items() if root != find(anchor)), key=min
    )
    for members in others:
        source = min(task for task in members if task in layers[0])
        edges.add((source, anchor))
    return sorted(edges)


def build_precedences(
    ids: list[str],
    ratio: float,
    probability: float,
    lag_max: int,
    workflow: np.random.Generator,
    lags: np.random.Generator,
) -> list[Precedence]:
    """Return sorted DAG precedences with independently drawn integer-slot lags.

    Expects the same ID, ratio and probability preconditions as layered_edges
    and nonnegative integer lag_max. Advances workflow and lags RNGs; does not
    modify IDs or do IO. Invalid helper inputs may raise NumPy errors."""
    return [
        Precedence(pred=a, succ=b, lag_min=int(lags.integers(0, lag_max + 1)))
        for a, b in layered_edges(ids, ratio, probability, workflow)
    ]
