"""Exact open-capacity calculations and horizon search."""

from fractions import Fraction
from math import ceil, floor
from typing import NamedTuple

import numpy as np

from scheduler_core.generation.params import GeneratorParams
from scheduler_core.generation.resources import selected
from scheduler_core.models import (
    BlockedWindow,
    Device,
    Person,
    PersonBlockedWindow,
    Precedence,
    Task,
)

H_MAX_SLOTS = 1_000_000


def closed_slots(horizon: int) -> int:
    """Return closed slots in [0,horizon) for a nonnegative integer horizon.

    Units are five-minute slots from 2026-01-05 00:00 UTC (Shanghai 08:00);
    local 20:00–08:00 is closed. This pure arithmetic helper does no IO and
    does not validate the typed input."""
    days, rest = divmod(horizon, 288)
    return days * 144 + max(0, rest - 144)


def capacity(horizon: int, devices: list[Device], closed: set[str]) -> int:
    """Return total capacity-slots open over [0,horizon).

    Expects a nonnegative integer horizon, valid devices and a set of IDs
    using the periodic local closure; unlisted devices are always open.
    Does not mutate inputs or do IO; preconditions are not validated."""
    return sum(
        d.capacity * (horizon - closed_slots(horizon) if d.id in closed else horizon)
        for d in devices
    )


def horizon_for_load(
    work: int, utilization: float, devices: list[Device], closed: set[str], limit: int = H_MAX_SLOTS
) -> int:
    """Return the minimum positive horizon whose open capacity meets the bound.

    Expects nonnegative integer work, finite positive utilization, valid
    devices and closure IDs, and positive limit. Uses exact Fraction(float)
    comparison; zero capacity cannot satisfy the bound. Raises ValueError if
    no horizon through limit satisfies it. Inputs are not mutated; no IO."""

    def satisfied(h: int) -> bool:
        c = capacity(h, devices, closed)
        return c > 0 and Fraction(work, c) <= Fraction(utilization)

    lo, hi = 0, 1
    while not satisfied(hi):
        lo = hi
        if hi == limit:
            raise ValueError("horizon exceeds limit")
        hi = min(hi * 2, limit)
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if satisfied(mid):
            hi = mid
        else:
            lo = mid
    return hi


def closed_windows(horizon: int, devices: list[Device], closed: set[str]) -> list[BlockedWindow]:
    """Return periodic CLOSED windows clipped to a nonnegative horizon.

    Expects valid devices and a set of closed device IDs; integer slots are
    five minutes from 2026-01-05 00:00 UTC (Shanghai 08:00), so the first
    closure is [144,288). Does not modify inputs or do IO."""
    result = []
    for device in devices:
        if device.id in closed:
            for start in range(144, horizon, 288):
                result.append(
                    BlockedWindow(
                        device_id=device.id,
                        kind="CLOSED",
                        start=start,
                        end=min(start + 144, horizon),
                    )
                )
    return result


class TimingResult(NamedTuple):
    """Horizon, device windows, and independently copied tasks and persons."""

    horizon: int
    blocked: list[BlockedWindow]
    tasks: list[Task]
    persons: list[Person]


def assign_times(
    tasks: list[Task],
    groups: list[list[str]],
    edges: list[Precedence],
    devices: list[Device],
    persons: list[Person],
    utilization: float,
    deadline_tightness: float,
    params: GeneratorParams,
    random: dict[str, np.random.Generator],
) -> TimingResult:
    """Return the horizon, device windows, and new timed tasks and persons.

    Expects generated topologically ordered tasks, groups, precedences,
    devices, personnel, valid params and all named RNG streams. Slots are
    five minutes from the fixed Shanghai 08:00/UTC 00:00 anchor. Inputs are
    not modified; random streams are consumed in their existing draw order.
    Does no IO. Raises ValueError if the required horizon exceeds the limit. This
    internal construction helper does not validate all preconditions."""
    tasks = [task.model_copy(deep=True) for task in tasks]
    persons = [person.model_copy(deep=True) for person in persons]
    n_devices = len(devices)
    closed_indices = selected(n_devices, params.closed_calendar_fraction, random["calendars"])
    closed = {devices[i].id for i in closed_indices}
    early: dict[str, int] = {}
    for task in tasks:
        incoming = [early[e.pred] + e.lag_min for e in edges if e.succ == task.id]
        early[task.id] = task.duration + max(incoming, default=0)
    cp = {group[0].split("-")[0]: max(early[t] for t in group) for group in groups}
    h = max(
        horizon_for_load(sum(t.duration * t.demand for t in tasks), utilization, devices, closed),
        max(cp.values()),
    )
    releases = {
        e: floor(
            Fraction(float(random["releases"].random()))
            * Fraction(params.release_span)
            * (h - path)
        )
        for e, path in cp.items()
    }
    multiplier = 1 + (1 - Fraction(deadline_tightness)) * Fraction(params.deadline_slack_span)
    for task in tasks:
        task.release = releases[task.experiment_id]
        task.deadline = min(h, task.release + ceil(multiplier * early[task.id]))
        if (
            params.hard_deadline_fraction > 0
            and random["deadlines"].random() < params.hard_deadline_fraction
        ):
            task.deadline_level = "HARD"
    blocked = closed_windows(h, devices, closed)
    for i in selected(n_devices, params.maint_fraction, random["maintenance"]):
        hi = min(params.maint_max, h // 4)
        if hi >= params.maint_min:
            length = int(random["maintenance"].integers(params.maint_min, hi + 1))
            start = int(random["maintenance"].integers(0, h - length + 1))
            blocked.append(
                BlockedWindow(
                    device_id=devices[i].id, kind="MAINT", start=start, end=start + length
                )
            )
    for person in persons:
        hi = min(params.absence_max, h // 2)
        if random["persons"].random() < params.person_absence_prob and hi >= params.absence_min:
            length = int(random["persons"].integers(params.absence_min, hi + 1))
            start = int(random["persons"].integers(0, h - length + 1))
            person.blocked.append(PersonBlockedWindow(start=start, end=start + length))
    return TimingResult(h, blocked, tasks, persons)
