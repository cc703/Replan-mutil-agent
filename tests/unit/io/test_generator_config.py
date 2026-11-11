import hashlib
from pathlib import Path

import pytest

from scheduler_core.generation.params import GeneratorParams
from scheduler_core.io.generator_config import load_generator_config

CONFIG = Path("experiments/configs/generator/default.yaml")


def test_default_matches_model() -> None:
    data = CONFIG.read_bytes()
    loaded = load_generator_config(data)
    assert loaded.params == GeneratorParams()
    assert loaded.sha256 == hashlib.sha256(data).hexdigest()


@pytest.mark.parametrize(
    "data",
    [
        b"a: 1\na: 2\n",
        b"a: &x 1\nb: *x\n",
        b"a: !custom value\n",
        b"a: 1\n---\nb: 2\n",
        b"[1, 2]",
        b"1: value",
        b"\xef\xbb\xbf{}",
        b"\xff",
    ],
)
def test_reject_bad_documents(data: bytes) -> None:
    with pytest.raises(ValueError):
        load_generator_config(data)


@pytest.mark.parametrize(
    "old,new",
    [
        (b"lag_min_max: 2", b"lag_min_max: 2.0"),
        (b"lag_min_max: 2", b"lag_min_max: yes"),
        (b"extra_edge_prob: 0.15", b"extra_edge_prob: .nan"),
        (b"extra_edge_prob: 0.15", b"extra_edge_prob: .inf"),
        (b"extra_edge_prob: 0.15", b"extra_edge_prob: '0.15'"),
        (b"lag_min_max: 2\n", b""),
        (b"lag_min_max: 2", b"unexpected: 2"),
        (b"schema_version: 1", b"schema_version: 2"),
    ],
)
def test_reject_bad_values(old: bytes, new: bytes) -> None:
    with pytest.raises(ValueError):
        load_generator_config(CONFIG.read_bytes().replace(old, new))


def test_too_large() -> None:
    with pytest.raises(ValueError):
        load_generator_config(b"x" * 65537)


def test_integer_for_float_field_is_normalized() -> None:
    data = CONFIG.read_bytes().replace(b"release_span: 0.5", b"release_span: 1")
    assert load_generator_config(data).params.release_span == 1.0
    assert type(load_generator_config(data).params.release_span) is float


@pytest.mark.parametrize("value", [b"yes", b"no", b"on", b"off", b"true", b"'1'"])
def test_non_numeric_float_rejected(value: bytes) -> None:
    data = CONFIG.read_bytes().replace(b"release_span: 0.5", b"release_span: " + value)
    with pytest.raises(ValueError):
        load_generator_config(data)
