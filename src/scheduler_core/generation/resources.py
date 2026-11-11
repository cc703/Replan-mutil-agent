"""Deterministic resource and personnel construction."""

from fractions import Fraction
from math import ceil, floor

import numpy as np
from scheduler_core.generation.params import GeneratorParams
from scheduler_core.models import Device, Person, SetupRule


def selected(n: int, fraction: float, rng: np.random.Generator) -> set[int]:
    """Select indices from range(n), rounding n*fraction to nearest, ties up.

    Expects n >= 0 and finite fraction in [0,1]; returns a set of indices.
    Advances rng, does not modify other inputs or perform IO. Invalid inputs
    may be rejected by Fraction or NumPy; this helper does not validate them."""
    count = floor(Fraction(fraction) * n + Fraction(1, 2))
    return {int(i) for i in rng.permutation(n)[:count]}


def make_devices(
    n: int, types: int, params: GeneratorParams, rng: np.random.Generator
) -> list[Device]:
    """Return n new devices with round-robin types and sampled capacities.

    Expects n > 0, 1 <= types <= n and valid GeneratorParams. Advances rng;
    does not modify params or perform IO. Preconditions are not checked here."""
    multi = selected(n, params.cap_gt1_fraction, rng)
    return [
        Device(
            id=f"d{i + 1:02d}",
            type=f"type{i % types + 1}",
            capacity=int(rng.integers(2, 5)) if i in multi else 1,
            capabilities={f"type{i % types + 1}"},
        )
        for i in range(n)
    ]


def make_persons(n_devices: int, params: GeneratorParams, rng: np.random.Generator) -> list[Person]:
    """Return new personnel with at least the configured holders per skill.

    Expects positive n_devices and params valid for the scale, including enough
    personnel for min_skill_holders. Advances rng; no other input is modified
    and no IO is performed. This helper does not validate those preconditions."""
    count = max(2, ceil(Fraction(params.persons_per_device) * n_devices))
    skills: list[set[str]] = [set() for _ in range(count)]
    for skill in range(params.skill_count):
        name = f"skill{skill + 1}"
        for i in rng.permutation(count)[: params.min_skill_holders]:
            skills[int(i)].add(name)
        for i in range(count):
            if rng.random() < 0.5:
                skills[i].add(name)
    return [Person(id=f"p{i + 1:02d}", skills=skills[i]) for i in range(count)]


def make_setups(
    devices: list[Device], types: int, params: GeneratorParams, rng: np.random.Generator
) -> list[SetupRule]:
    """Return sampled setup rules, unique per device and task type.

    Expects generated devices, positive type count and valid params; slots use
    the instance's five-minute unit. Advances rng without mutating devices or
    params; performs no IO and does not validate these preconditions."""
    result = []
    for device in devices:
        for i in range(types):
            if rng.random() < params.setup_prob:
                result.append(
                    SetupRule(
                        device_id=device.id,
                        task_type=f"type{i + 1}",
                        slots=int(rng.integers(1, params.setup_max + 1)),
                    )
                )
    return result
