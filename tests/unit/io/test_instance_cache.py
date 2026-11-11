from pathlib import Path
import hashlib
import json
import os
import struct

import pytest

from scheduler_core.generation.params import GeneratorParams
from scheduler_core.io.artifacts import ArtifactStore
from scheduler_core.instance_cache import CacheConflictError, InstanceCache, _float_token


def test_tokens_cover_binary64() -> None:
    values = [0.8, 1.0, 0.05, 1e-9, 1e-21, 5e-324, 0.30000000000000004]
    tokens = [_float_token(x) for x in values]
    assert len(set(tokens)) == len(values)
    assert [struct.unpack(">d", bytes.fromhex(x))[0] for x in tokens] == values
    assert _float_token(-0.0) == _float_token(0.0)


def test_cache_create_reuse_and_regeneration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = InstanceCache(ArtifactStore(tmp_path))
    first = cache.get_or_generate("S", 0.8, 0.5, 0)
    assert not first.reused and not first.regeneration_verified
    original = (first.directory / "instance.json").read_bytes()
    import importlib

    module = importlib.import_module("scheduler_core.instance_cache")
    generator = module.generate_instance

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("unexpected generation")

    monkeypatch.setattr(module, "generate_instance", fail)
    second = cache.get_or_generate("S", 0.8, 0.5, 0)
    assert second.reused and not second.regeneration_verified
    monkeypatch.setattr(module, "generate_instance", generator)
    verified = cache.get_or_generate("S", 0.8, 0.5, 0, verify_regeneration=True)
    assert verified.reused and verified.regeneration_verified
    assert (first.directory / "instance.json").read_bytes() == original
    changed = cache.get_or_generate("S", 0.8, 0.5, 0, params=GeneratorParams(extra_edge_prob=0.2))
    assert changed.key != first.key and len(changed.key) <= 116


def test_corruption_and_metadata_tampering(tmp_path: Path) -> None:
    cache = InstanceCache(ArtifactStore(tmp_path))
    result = cache.get_or_generate("S", 0.8, 0.5, 0)
    path = result.directory / "meta.json"
    os.chmod(path, 0o666)
    meta = json.loads(path.read_bytes())
    meta["schema"] = True
    path.write_text(json.dumps(meta), encoding="utf8")
    with pytest.raises(CacheConflictError):
        cache.get_or_generate("S", 0.8, 0.5, 0)


def test_invalid_inputs_do_not_create_namespace(tmp_path: Path) -> None:
    cache = InstanceCache(ArtifactStore(tmp_path))
    with pytest.raises(ValueError):
        cache.get_or_generate("S", 0.01, 0.5, 0)
    assert not cache.area.parent.exists()


def test_self_consistent_modification_requires_regeneration(tmp_path: Path) -> None:
    from scheduler_core.generation.canonical import instance_from_bytes, instance_to_bytes

    cache = InstanceCache(ArtifactStore(tmp_path))
    result = cache.get_or_generate("S", 0.8, 0.5, 0)
    instance_file = result.directory / "instance.json"
    meta_file = result.directory / "meta.json"
    instance = instance_from_bytes(instance_file.read_bytes())
    instance.tasks[0].weight += 1.0
    data = instance_to_bytes(instance)
    meta = json.loads(meta_file.read_bytes())
    meta["instance_sha256"] = hashlib.sha256(data).hexdigest()
    meta["instance_bytes"] = len(data)
    os.chmod(instance_file, 0o666)
    os.chmod(meta_file, 0o666)
    instance_file.write_bytes(data)
    meta_file.write_text(json.dumps(meta), encoding="utf8")
    assert cache.get_or_generate("S", 0.8, 0.5, 0).reused
    with pytest.raises(CacheConflictError, match="regeneration mismatch"):
        cache.get_or_generate("S", 0.8, 0.5, 0, verify_regeneration=True)


@pytest.mark.parametrize(
    "field,value",
    [
        ("seed", "0"),
        ("seed", 0.0),
        ("seed", True),
        ("schema", 1.0),
        ("canonical_version", True),
        ("generator_version", "c1-1"),
        ("instance_sha256", "A" * 64),
    ],
)
def test_metadata_fields_strict(tmp_path: Path, field: str, value: object) -> None:
    cache = InstanceCache(ArtifactStore(tmp_path))
    entry = cache.get_or_generate("S", 0.8, 0.5, 0)
    path = entry.directory / "meta.json"
    os.chmod(path, 0o666)
    metadata = json.loads(path.read_bytes())
    metadata[field] = value
    path.write_text(json.dumps(metadata), encoding="utf8")
    with pytest.raises(CacheConflictError):
        cache.get_or_generate("S", 0.8, 0.5, 0)


def test_metadata_duplicate_and_unexpected_file(tmp_path: Path) -> None:
    cache = InstanceCache(ArtifactStore(tmp_path))
    result = cache.get_or_generate("S", 0.8, 0.5, 0)
    meta = result.directory / "meta.json"
    os.chmod(meta, 0o666)
    data = meta.read_bytes()
    meta.write_bytes(data.replace(b'"schema":1', b'"schema":1,"schema":1'))
    with pytest.raises(CacheConflictError):
        cache.get_or_generate("S", 0.8, 0.5, 0)


def test_key_parameter_binding_and_maximum_length(tmp_path: Path) -> None:
    cache = InstanceCache(ArtifactStore(tmp_path))
    first = cache.get_or_generate(
        "L", 0.8, 5e-324, 2**63 - 1, params=GeneratorParams(extra_edge_prob=0.2)
    )
    second = cache.get_or_generate(
        "L", 0.8, 5e-324, 2**63 - 1, params=GeneratorParams(extra_edge_prob=0.3)
    )
    assert len(first.key) == 116
    assert first.key != second.key


def test_extra_file_rejected(tmp_path: Path) -> None:
    cache = InstanceCache(ArtifactStore(tmp_path))
    result = cache.get_or_generate("S", 0.8, 0.5, 0)
    (result.directory / "extra").write_bytes(b"x")
    with pytest.raises(CacheConflictError):
        cache.get_or_generate("S", 0.8, 0.5, 0)


def test_negative_zero_parameters_have_same_semantic_hash() -> None:
    from scheduler_core.instance_cache import _params_hash

    positive = GeneratorParams(extra_edge_prob=0.0)
    negative = GeneratorParams(extra_edge_prob=-0.0)
    assert _params_hash(positive) == _params_hash(negative)


@pytest.mark.parametrize("value", ["false", 0, 1, None])
def test_regeneration_flag_requires_bool_before_storage(tmp_path: Path, value: object) -> None:
    from typing import cast

    cache = InstanceCache(ArtifactStore(tmp_path))
    with pytest.raises(TypeError, match="verify_regeneration must be a bool"):
        cache.get_or_generate("S", 0.8, 0.5, 0, verify_regeneration=cast(bool, value))
    assert not cache.area.parent.exists()


def test_regeneration_flag_bool_results(tmp_path: Path) -> None:
    cache = InstanceCache(ArtifactStore(tmp_path))
    assert (
        cache.get_or_generate("S", 0.8, 0.5, 0, verify_regeneration=False).regeneration_verified
        is False
    )
    assert (
        cache.get_or_generate("S", 0.8, 0.5, 0, verify_regeneration=True).regeneration_verified
        is True
    )
