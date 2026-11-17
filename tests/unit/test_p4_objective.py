from fractions import Fraction

import pytest

from scheduler_core.replanning.objective import objective_coefficients


def test_objective_exactly_normalizes_shift_and_urgent_completion() -> None:
    coefficients, scale = objective_coefficients(1, 2, 5, 0.1, 5, 20, [1.5, 2], 2)
    tard1, tard2, moved, switched, shift, urgent = coefficients
    actual = Fraction(3 * tard1 + 2 * tard2 + moved + switched + 4 * shift + 13 * urgent, scale)
    assert actual == Fraction("1.5") * 3 + 2 * 2 + 2 + 5 + Fraction("0.1") * 4 / 20 + 5 * 13


def test_objective_rejects_unsafe_or_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        objective_coefficients(1, 2, 5, 0.1, 5, 0, [], 0)
    with pytest.raises(ValueError):
        objective_coefficients(1e100, 2, 5, 0.1, 5, 20, [1], 0)
