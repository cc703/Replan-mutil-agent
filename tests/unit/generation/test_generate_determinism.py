from typing import Any, cast
import os
import pytest
import subprocess
import sys
from scheduler_core.generate import generate_instance
from scheduler_core.generation.canonical import instance_to_bytes


def test_repeated_and_hashseed() -> None:
    expected = instance_to_bytes(generate_instance("S", 0.8, 0.5, 0))
    assert expected == instance_to_bytes(generate_instance("S", 0.8, 0.5, 0))
    code = "from scheduler_core.generate import generate_instance; from scheduler_core.generation.canonical import instance_to_bytes; import sys; sys.stdout.buffer.write(instance_to_bytes(generate_instance('S',.8,.5,0)))"
    for seed in ("0", "1", "2024"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH="src")
        assert subprocess.check_output([sys.executable, "-c", code], env=env) == expected


def test_substream_isolation() -> None:
    from scheduler_core.generation.rng import STREAMS, streams

    first = streams(101)
    second = streams(101)
    values = [int(first[name].integers(0, 2**63)) for name in STREAMS]
    assert len(set(values)) == len(values)
    assert values == [int(second[name].integers(0, 2**63)) for name in STREAMS]


@pytest.mark.parametrize(
    "scale,u,t,seed", [("S", 0.8, 0.5, 0), ("M", 0.6, 0.25, 1), ("L", 0.95, 0.75, 2)]
)
def test_hashseed_all_scales(scale: str, u: float, t: float, seed: int) -> None:
    import hashlib

    code = (
        "from scheduler_core.generate import generate_instance; from scheduler_core.generation.canonical import instance_to_bytes; import hashlib; print(hashlib.sha256(instance_to_bytes(generate_instance(%r,%r,%r,%r))).hexdigest())"
        % (scale, u, t, seed)
    )
    hashes = []
    for hashseed in ("0", "1", "2024"):
        env = dict(os.environ, PYTHONHASHSEED=hashseed, PYTHONPATH="src")
        hashes.append(subprocess.check_output([sys.executable, "-c", code], env=env).strip())
    assert len(set(hashes)) == 1
    assert (
        hashes[0].decode()
        == hashlib.sha256(instance_to_bytes(generate_instance(scale, u, t, seed))).hexdigest()
    )


def test_no_forbidden_imports_and_global_rng_unchanged() -> None:
    import ast
    from pathlib import Path
    import numpy as np

    paths = [
        Path("src/scheduler_core/generate.py"),
        *Path("src/scheduler_core/generation").glob("*.py"),
    ]
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf8"))):
            if isinstance(node, ast.Import):
                assert all(
                    alias.name.split(".")[0] not in {"random", "ortools"} for alias in node.names
                )
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in {"random", "ortools"}
    before = cast(tuple[Any, ...], np.random.get_state())
    generate_instance("S", 0.8, 0.5, 0)
    after = cast(tuple[Any, ...], np.random.get_state())
    assert before[0] == after[0] and np.array_equal(before[1], after[1]) and before[2:] == after[2:]
