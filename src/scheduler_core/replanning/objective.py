"""Exact integer scaling for the P4 objective."""

from fractions import Fraction
from functools import reduce
from math import gcd, isfinite, lcm

from scheduler_core.solving.weights import LIMIT


def objective_coefficients(
    alpha: float,
    beta_moved: float,
    beta_switched: float,
    beta_shift: float,
    gamma: float,
    horizon: int,
    weights: list[float],
    urgent_count: int,
) -> tuple[list[int], int]:
    """Return coefficients for tardiness per task, moved, switched, shift and urgent.

    The final coefficient applies to each urgent end. Shift is in raw slots;
    its coefficient includes the horizon normalization. The returned scale
    converts the integer objective back to the original units.
    """
    if horizon <= 0 or horizon > LIMIT or urgent_count < 0:
        raise ValueError("invalid objective bounds")
    values = [alpha, beta_moved, beta_switched, beta_shift, gamma, *weights]
    if any(
        isinstance(v, bool)
        or not isinstance(v, (int, float))
        or (isinstance(v, float) and not isfinite(v))
        or v < 0
        for v in values
    ):
        raise ValueError("objective weights must be finite and nonnegative")
    a, moved, switched, shift, urgent = (Fraction(str(v)) for v in values[:5])
    terms = [a * Fraction(str(w)) for w in weights]
    terms += [moved, switched, shift / horizon, urgent]
    if any(x.numerator > LIMIT or x.denominator > LIMIT for x in terms):
        raise ValueError("objective precision exceeds safe bounds")
    scale = lcm(*(x.denominator for x in terms))
    if scale > LIMIT:
        raise ValueError("objective scale exceeds safe bounds")
    coefficients = [x.numerator * (scale // x.denominator) for x in terms]
    divisor = reduce(gcd, [scale, *coefficients])
    scale //= divisor
    coefficients = [c // divisor for c in coefficients]
    n = len(weights)
    bound = horizon * sum(coefficients[:n])
    bound += n * (coefficients[n] + coefficients[n + 1] + horizon * coefficients[n + 2])
    bound += urgent_count * horizon * coefficients[n + 3]
    if max(coefficients, default=0) > LIMIT or bound > LIMIT:
        raise ValueError("objective exceeds safe bounds")
    return coefficients, scale
