"""Regression locks frozen by root after independent G3; not correctness evidence.

Generator version c2-1 and NumPy 2.4.6 produced these independently reviewed
hashes under PYTHONHASHSEED 0, 1 and 2024. Algorithm/version changes require
reviewing this lock and the separate structural oracle, not copying new hashes.
"""

import hashlib
from importlib.metadata import version

import pytest

from scheduler_core.generate import generate_instance
from scheduler_core.generation.canonical import instance_to_bytes


@pytest.mark.parametrize(
    "scale,utilization,tightness,seed,expected",
    [
        ("S", 0.8, 0.5, 0, "d0e16c15f5b841ec6b0b1d00219d25b70164d0c58fccb8579f5845bf7b09869d"),
        ("M", 0.6, 0.25, 1, "712e9aebfca29641f62a63d9152d67af1f7562bdcc19dbe4be919d80dbbbf5e5"),
        ("L", 0.95, 0.75, 2, "a494cad109ae890732063c2631da2c7aca015862a656f1e11ec6bc7d808d1f77"),
    ],
)
def test_generated_canonical_regression(
    scale: str, utilization: float, tightness: float, seed: int, expected: str
) -> None:
    assert version("numpy") == "2.4.6"
    data = instance_to_bytes(generate_instance(scale, utilization, tightness, seed))
    assert hashlib.sha256(data).hexdigest() == expected
