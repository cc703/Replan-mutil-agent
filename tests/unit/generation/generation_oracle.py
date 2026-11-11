"""Checks which do not depend on generator implementation."""

from __future__ import annotations

from fractions import Fraction
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scheduler_core.models import Instance


def capacity(instance: Instance, h: int) -> int:
    return sum(
        d.capacity
        * (
            h
            - sum(
                max(0, min(h, w.end) - w.start)
                for w in instance.blocked
                if w.device_id == d.id and w.kind == "CLOSED" and w.start < h
            )
        )
        for d in instance.devices
    )


def load(instance: Instance) -> int:
    return sum(t.duration * t.demand for t in instance.tasks)


def utilization(instance: Instance) -> Fraction:
    return Fraction(load(instance), capacity(instance, instance.axis.horizon_slots))


def critical_paths(instance: Instance) -> dict[str, int]:
    early: dict[str, int] = {}
    for task in instance.tasks:
        previous = [early[p.pred] + p.lag_min for p in instance.precedences if p.succ == task.id]
        early[task.id] = task.duration + max(previous, default=0)
    result: dict[str, int] = {}
    for task in instance.tasks:
        result[task.experiment_id] = max(result.get(task.experiment_id, 0), early[task.id])
    return result
