"""Integer scaling for the initial objective."""

from fractions import Fraction
from functools import reduce
from math import gcd, isfinite, lcm

LIMIT = (1 << 62) - 1


def scale_weights(
    weights: dict[str, float] | None, horizon: int, load_bound: int
) -> tuple[int, int, int]:
    """Return makespan and imbalance coefficients and their common scale."""
    values = {"tardiness": 1.0, "makespan": 1.0, "imbalance": 0.1, "preference": 0.0}
    if weights is not None:
        if set(weights) - values.keys():
            raise ValueError("unknown objective weight")
        values.update(weights)
    fractions = []
    for name, value in values.items():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or (isinstance(value, float) and not isfinite(value))
            or value < 0
        ):
            raise ValueError(f"invalid objective weight: {name}")
        if isinstance(value, int) and value > LIMIT:
            raise ValueError("objective weight exceeds safe bounds")
        f = Fraction(str(value))
        if f.numerator > LIMIT or f.denominator > LIMIT:
            raise ValueError("objective weight precision exceeds safe bounds")
        fractions.append(f)
    if fractions[3]:
        raise ValueError("preference input is unavailable")
    denominator = lcm(*(f.denominator for f in fractions))
    if denominator > LIMIT:
        raise ValueError("objective scale exceeds safe bounds")
    ints = [f.numerator * (denominator // f.denominator) for f in fractions]
    divisor = reduce(gcd, ints + [denominator])
    ints = [n // divisor for n in ints]
    denominator //= divisor
    if max(ints) > LIMIT or ints[1] * horizon + ints[2] * load_bound > LIMIT:
        raise ValueError("objective exceeds safe bounds")
    return ints[1], ints[2], denominator
