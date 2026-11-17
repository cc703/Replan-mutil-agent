"""Deterministic Pareto selection for independently validated candidates."""

from math import isfinite, sqrt

from scheduler_core.models import Candidate


def _canonical(c: Candidate) -> tuple[tuple[str, str, str, int, int], ...]:
    return tuple(
        sorted(
            (a.task_id, a.device_id, a.person_id or "", a.start, a.end)
            for a in c.plan.assignments.values()
        )
    )


def _vector(c: Candidate) -> tuple[float, float, float]:
    return c.f1, c.f2, c.f3


def _key(c: Candidate) -> tuple[object, ...]:
    return c.level, _vector(c), _canonical(c), c.plan.id


def _duplicate(a: Candidate, b: Candidate, threshold: int) -> bool:
    aa, bb = a.plan.assignments, b.plan.assignments
    if aa.keys() != bb.keys():
        return False
    if any((aa[t].device_id, aa[t].person_id) != (bb[t].device_id, bb[t].person_id) for t in aa):
        return False
    return sum(abs(aa[t].start - bb[t].start) for t in aa) < max(threshold, 1)


def select_candidates(
    pool: list[Candidate], *, max_n: int = 5, dedupe_l1: int = 3
) -> list[Candidate]:
    """Select nondominated validated plans with stable deduplication and labels."""
    if isinstance(max_n, bool) or not isinstance(max_n, int):
        raise TypeError("max_n must be an integer")
    if not 1 <= max_n <= 10:
        raise ValueError("max_n must be between 1 and 10")
    if isinstance(dedupe_l1, bool) or not isinstance(dedupe_l1, int):
        raise TypeError("dedupe_l1 must be an integer")
    if dedupe_l1 < 0:
        raise ValueError("dedupe_l1 must be nonnegative")
    valid = [c for c in pool if c.validation.passed]
    if any(not isfinite(v) for c in valid for v in _vector(c)):
        raise ValueError("candidate objectives must be finite")
    front = [
        c
        for c in valid
        if not any(
            all(x <= y for x, y in zip(_vector(other), _vector(c), strict=True))
            and _vector(other) != _vector(c)
            for other in valid
        )
    ]
    unique: list[Candidate] = []
    for c in sorted(front, key=_key):
        if not any(_duplicate(c, previous, dedupe_l1) for previous in unique):
            unique.append(c)
    if not unique:
        return []
    vectors = [_vector(c) for c in unique]
    lows = tuple(min(v[i] for v in vectors) for i in range(3))
    highs = tuple(max(v[i] for v in vectors) for i in range(3))

    def distance(c: Candidate) -> float:
        return sqrt(
            sum(
                ((v - lo) / (hi - lo)) ** 2 if hi != lo else 0
                for v, lo, hi in zip(_vector(c), lows, highs, strict=True)
            )
        )

    identities: list[tuple[str, Candidate]] = []
    for i, name in ((1, "最稳"), (0, "最少延期"), (2, "最早完成紧急")):
        if lows[i] != highs[i]:
            winner = min(
                unique,
                key=lambda c: (
                    _vector(c)[i],
                    tuple(v for j, v in enumerate(_vector(c)) if j != i),
                    _canonical(c),
                    c.plan.id,
                ),
            )
            identities.append((name, winner))
    identities.append(("均衡", min(unique, key=lambda c: (distance(c), _canonical(c), c.plan.id))))
    chosen: list[Candidate] = []
    for _, candidate in identities:
        if candidate not in chosen and len(chosen) < max_n:
            chosen.append(candidate)
    for candidate in sorted(unique, key=lambda c: (distance(c), _canonical(c), c.plan.id)):
        if len(chosen) >= max_n:
            break
        if candidate not in chosen:
            chosen.append(candidate)
    return [
        c.model_copy(
            update={"label": "·".join(name for name, winner in identities if winner is c) or None},
            deep=True,
        )
        for c in chosen
    ]
