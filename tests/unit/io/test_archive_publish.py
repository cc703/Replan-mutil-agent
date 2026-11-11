from pathlib import Path

import pytest

from scheduler_core.io.archive_publish import publish_noreplace


def test_existing_destination_is_not_replaced(tmp_path: Path) -> None:
    source = tmp_path / "stage"
    target = tmp_path / "target"
    source.write_bytes(b"new")
    target.write_bytes(b"original")
    with pytest.raises(FileExistsError):
        publish_noreplace(source, target)
    assert target.read_bytes() == b"original"
    assert source.read_bytes() == b"new"


def test_publish_moves_file(tmp_path: Path) -> None:
    source = tmp_path / "stage"
    target = tmp_path / "target"
    source.write_bytes(b"new")
    publish_noreplace(source, target)
    assert not source.exists()
    assert target.read_bytes() == b"new"


def test_unsupported_platform_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.write_bytes(b"data")
    monkeypatch.setattr("scheduler_core.io.archive_publish.sys.platform", "unverified")
    with pytest.raises(OSError):
        publish_noreplace(source, target)
    assert source.read_bytes() == b"data"
    assert not target.exists()
