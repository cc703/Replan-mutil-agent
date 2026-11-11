from pathlib import Path

import pytest

from scheduler_core.io.cache_publish import publish_noreplace


def test_no_replace_directories_and_file(tmp_path: Path) -> None:
    for kind in ("empty", "nonempty", "file"):
        source = tmp_path / f"src-{kind}"
        target = tmp_path / f"dst-{kind}"
        source.mkdir()
        (source / "marker").write_bytes(b"source")
        if kind == "file":
            target.write_bytes(b"target")
        else:
            target.mkdir()
            if kind == "nonempty":
                (target / "marker").write_bytes(b"target")
        with pytest.raises(FileExistsError):
            publish_noreplace(source, target)
        assert (source / "marker").read_bytes() == b"source"
        if kind != "empty":
            assert (target if kind == "file" else target / "marker").read_bytes() == b"target"


def test_publish_success_and_missing_source(tmp_path: Path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    publish_noreplace(source, target)
    assert target.is_dir() and not source.exists()
    with pytest.raises(FileNotFoundError):
        publish_noreplace(source, tmp_path / "missing")


def test_unknown_platform_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib

    module = importlib.import_module("scheduler_core.io.cache_publish")

    monkeypatch.setattr(module.sys, "platform", "unknown")
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(OSError):
        module.publish_noreplace(source, tmp_path / "target")
    assert source.is_dir() and not (tmp_path / "target").exists()
