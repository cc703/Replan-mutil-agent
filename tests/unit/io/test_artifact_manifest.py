"""Manifest tamper and configuration checks."""

import hashlib
from pathlib import Path
from typing import cast

import pytest

from scheduler_core.io import ArtifactError, ArtifactStore, GitInfo, read_manifest


def test_empty_config_hash_and_tamper(tmp_path: Path) -> None:
    run = ArtifactStore(tmp_path).new_run(
        "sim", "sample", "tag", git=GitInfo(commit="abcdef0", dirty=False)
    )
    assert (run.dir / "config.yaml").read_bytes() == b""
    assert run.manifest.config_sha256 == hashlib.sha256(b"").hexdigest()
    (run.dir / "config.yaml").write_bytes(b"changed")
    with pytest.raises(ArtifactError):
        read_manifest(run.dir)


@pytest.mark.parametrize("dirty", ["false", 0, 1])
def test_git_dirty_is_strict(dirty: object) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        GitInfo.model_validate({"commit": "abcdef0", "dirty": dirty})


def test_duplicate_json_keys_are_rejected(tmp_path: Path) -> None:
    run = ArtifactStore(tmp_path).new_run(
        "sim", "sample", "tag", git=GitInfo(commit="abcdef0", dirty=False)
    )
    manifest = run.dir / "manifest.json"
    raw = manifest.read_text(encoding="utf-8")
    manifest.write_text(
        raw.replace('"status": "running"', '"status": "running", "status": "running"'),
        encoding="utf-8",
    )
    with pytest.raises(ArtifactError):
        read_manifest(run.dir)


@pytest.mark.parametrize("configuration", [b"\xff\xfe\r\n", "\ufeffa: 1\r\n", None])
def test_config_bytes_preserved(tmp_path: Path, configuration: bytes | str | None) -> None:
    expected = (
        configuration.encode("utf-8") if isinstance(configuration, str) else configuration or b""
    )
    run = ArtifactStore(tmp_path).new_run(
        "sim", "sample", "tag", config=configuration, git=GitInfo(commit="abcdef0", dirty=False)
    )
    assert (run.dir / "config.yaml").read_bytes() == expected
    assert run.manifest.config_sha256 == hashlib.sha256(expected).hexdigest()


def test_config_path_preserves_bytes(tmp_path: Path) -> None:
    source = tmp_path / "source.yaml"
    source.write_bytes(b"\xef\xbb\xbfhello\r\n")
    run = ArtifactStore(tmp_path / "root").new_run(
        "sim", "sample", "tag", config=source, git=GitInfo(commit="abcdef0", dirty=False)
    )
    assert (run.dir / "config.yaml").read_bytes() == source.read_bytes()


def test_input_may_name_external_config_and_timestamp_is_bound(tmp_path: Path) -> None:
    run = ArtifactStore(tmp_path).new_run(
        "sim",
        "sample",
        "tag",
        inputs=["data/config.yaml"],
        git=GitInfo(commit="abcdef0", dirty=False),
    )
    assert run.manifest.inputs == ["data/config.yaml"]
    manifest = run.dir / "manifest.json"
    raw = manifest.read_text(encoding="utf-8")
    started = run.manifest.started_at.isoformat().replace("+00:00", "Z")
    assert started in raw
    manifest.write_text(raw.replace(started, "2025-01-01T00:00:00Z"), encoding="utf-8")
    with pytest.raises(ArtifactError):
        read_manifest(run.dir)


@pytest.mark.parametrize("seed", [True, 1.0, "1", -1])
def test_invalid_seeds_are_rejected(tmp_path: Path, seed: object) -> None:
    from pydantic import ValidationError

    store = ArtifactStore(tmp_path)
    with pytest.raises(ValidationError):
        store.new_run(
            "sim",
            "sample",
            "tag",
            seeds=[cast(int, seed)],
            git=GitInfo(commit="abcdef0", dirty=False),
        )
    assert not list((tmp_path / "runs" / "sim" / "sample").iterdir())


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), [], {}])
def test_invalid_metadata_is_rejected(tmp_path: Path, value: object) -> None:
    from pydantic import ValidationError

    store = ArtifactStore(tmp_path)
    with pytest.raises(ValidationError):
        store.new_run(
            "sim",
            "sample",
            "tag",
            metadata={"key": cast(str | int | float | bool | None, value)},
            git=GitInfo(commit="abcdef0", dirty=False),
        )


@pytest.mark.parametrize("replacement", ["null", '"' + "A" * 64 + '"', '"' + "a" * 63 + '"'])
def test_bad_config_hash_is_rejected(tmp_path: Path, replacement: str) -> None:
    run = ArtifactStore(tmp_path).new_run(
        "sim", "sample", "tag", git=GitInfo(commit="abcdef0", dirty=False)
    )
    manifest = run.dir / "manifest.json"
    text = manifest.read_text(encoding="utf-8")
    text = text.replace('"' + run.manifest.config_sha256 + '"', replacement)
    manifest.write_text(text, encoding="utf-8")
    with pytest.raises(ArtifactError):
        read_manifest(run.dir)


@pytest.mark.parametrize("mutation", ["extra", "nan", "utf8", "naive", "status"])
def test_malformed_json_is_rejected(tmp_path: Path, mutation: str) -> None:
    run = ArtifactStore(tmp_path).new_run(
        "sim", "sample", "tag", git=GitInfo(commit="abcdef0", dirty=False)
    )
    path = run.dir / "manifest.json"
    raw = path.read_bytes()
    if mutation == "extra":
        raw = raw.replace(b'"status":', b'"extra": 1, "status":')
    elif mutation == "nan":
        raw = raw.replace(b'"metadata": {}', b'"metadata": {"x": NaN}')
    elif mutation == "utf8":
        raw += b"\xff"
    elif mutation == "naive":
        raw = raw.replace(b'Z"', b'"', 1)
    else:
        raw = raw.replace(b'"status": "running"', b'"status": 1')
    path.write_bytes(raw)
    with pytest.raises(ArtifactError):
        read_manifest(run.dir)


def test_python_version_conflict_and_metadata_float(tmp_path: Path) -> None:
    import platform

    store = ArtifactStore(tmp_path)
    git = GitInfo(commit="abcdef0", dirty=False)
    with pytest.raises(ValueError):
        store.new_run("sim", "sample", "bad", versions={"python": "wrong"}, git=git)
    run = store.new_run("sim", "sample", "good", metadata={"ratio": 0.5}, git=git)
    assert run.manifest.versions["python"] == platform.python_version()
    assert run.manifest.metadata["ratio"] == 0.5


def test_invalid_version_type(tmp_path: Path) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ArtifactStore(tmp_path).new_run(
            "sim",
            "sample",
            "tag",
            versions={"other": cast(str, 1)},
            git=GitInfo(commit="abcdef0", dirty=False),
        )


@pytest.mark.parametrize("action", ["delete", "directory"])
def test_missing_or_nonfile_configuration_rejected(tmp_path: Path, action: str) -> None:
    run = ArtifactStore(tmp_path).new_run(
        "sim", "sample", "tag", git=GitInfo(commit="abcdef0", dirty=False)
    )
    config = run.dir / "config.yaml"
    config.unlink()
    if action == "directory":
        config.mkdir()
    with pytest.raises(ArtifactError):
        read_manifest(run.dir)


@pytest.mark.parametrize("constructed", [False, True])
def test_invalid_git_instance_revalidated_before_creation(
    tmp_path: Path, constructed: bool
) -> None:
    from pydantic import ValidationError

    if constructed:
        evidence = GitInfo.model_construct(commit="abcdef0", dirty=0)
    else:
        evidence = GitInfo(commit="abcdef0", dirty=False)
        evidence.dirty = cast(bool, 0)
    store = ArtifactStore(tmp_path)
    with pytest.raises(ValidationError):
        store.new_run("sim", "sample", "tag", git=evidence)
    assert not (tmp_path / "runs").exists()


def test_manifest_requires_python_version(tmp_path: Path) -> None:
    run = ArtifactStore(tmp_path).new_run(
        "sim", "sample", "tag", git=GitInfo(commit="abcdef0", dirty=False)
    )
    path = run.dir / "manifest.json"
    text = path.read_text(encoding="utf-8")
    import platform

    text = text.replace('"python": "' + platform.python_version() + '"', '"python": ""')
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ArtifactError):
        read_manifest(run.dir)


def test_config_file_link_guard_without_symlink_privilege(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scheduler_core.io.paths as paths
    from scheduler_core.io import UnsafePathError

    run = ArtifactStore(tmp_path).new_run(
        "sim", "sample", "tag", git=GitInfo(commit="abcdef0", dirty=False)
    )
    config = run.dir / "config.yaml"
    original = paths._is_link
    monkeypatch.setattr(paths, "_is_link", lambda path: path == config or original(path))
    with pytest.raises(UnsafePathError):
        read_manifest(run.dir)
