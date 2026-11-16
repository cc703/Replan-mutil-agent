"""Pure PCG64 samples derived from stable entity keys."""

import hashlib
import math
import numpy as np
from numpy.random import Generator, PCG64, SeedSequence
from scheduler_core.models import Instance, Precedence, UrgentInsert
from .scenarios import Scenario


def _rng(seed: int, stream: int, *keys: int) -> Generator:
    return Generator(PCG64(SeedSequence(seed, spawn_key=(stream, *keys))))


def actual_duration(seed: int, task_id: str, attempt: int, planned: int, scenario: Scenario) -> int:
    """Sample a clipped lognormal multiplier and round half up."""
    key = int.from_bytes(hashlib.sha256(task_id.encode()).digest()[:8], "big")
    factor = _rng(seed, 0, key, attempt).lognormal(0, scenario.duration_sigma)
    return max(
        1,
        math.floor(
            planned
            * float(np.clip(factor, scenario.duration_factor_min, scenario.duration_factor_max))
            + 0.5
        ),
    )


def next_fault_gap(seed: int, device_index: int, occurrence: int, scenario: Scenario) -> int | None:
    """Return a fault interarrival in slots, or None when disabled."""
    if not scenario.fault_enabled:
        return None
    return max(
        1,
        math.floor(_rng(seed, 1, device_index, occurrence).exponential(scenario.mtbf_slots) + 0.5),
    )


def repair_duration(seed: int, device_index: int, occurrence: int, scenario: Scenario) -> int:
    """Return a lognormal repair duration in slots."""
    x = _rng(seed, 2, device_index, occurrence).lognormal(
        math.log(scenario.repair_median_slots), scenario.repair_sigma
    )
    return max(1, math.floor(x + 0.5))


def urgent_gap(seed: int, occurrence: int, scenario: Scenario, slot_minutes: int = 5) -> int | None:
    """Return exponential interarrival in slots using arrivals per 24-hour day."""
    if not scenario.urgent_enabled:
        return None
    if slot_minutes <= 0:
        raise ValueError("slot_minutes must be positive")
    mean = 1440 / slot_minutes / scenario.urgent_rate_per_day
    return max(1, math.floor(_rng(seed, 3, occurrence).exponential(mean) + 0.5))


def urgent_content(
    seed: int, occurrence: int, release: int, instance: Instance, scenario: Scenario
) -> UrgentInsert:
    """Sample prototypes without modifying the instance; avoid all existing IDs."""
    if not instance.tasks:
        raise ValueError("urgent content requires task prototypes")
    rng = _rng(seed, 4, occurrence)
    count = int(rng.integers(scenario.urgent_task_range[0], scenario.urgent_task_range[1] + 1))
    existing = {t.id for t in instance.tasks}
    experiments = {t.experiment_id for t in instance.tasks}
    prefix = f"u{occurrence}"
    while prefix in experiments or any(f"{prefix}-t{j}" in existing for j in range(count)):
        prefix += "~"
    prototypes = [instance.tasks[int(rng.integers(len(instance.tasks)))] for _ in range(count)]
    cp = (
        sum(t.duration for t in prototypes)
        if scenario.urgent_chain
        else max(t.duration for t in prototypes)
    )
    deadline = release + math.ceil(scenario.urgent_slack * cp)
    tasks = [
        t.model_copy(
            deep=True,
            update={
                "id": f"{prefix}-t{j}",
                "experiment_id": prefix,
                "release": release,
                "deadline": deadline,
                "weight": scenario.urgent_weight,
                "status": "PENDING",
            },
        )
        for j, t in enumerate(prototypes)
    ]
    edges = (
        [Precedence(pred=tasks[j].id, succ=tasks[j + 1].id) for j in range(count - 1)]
        if scenario.urgent_chain
        else []
    )
    return UrgentInsert(tasks=tasks, precedences=edges)
