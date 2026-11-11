"""Behavioral coverage of artifact cleanup and its safety boundaries."""

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scheduler_core.io.artifacts import ArtifactStore
from scheduler_core.io.errors import UnsafePathError
from scheduler_core.io.tree_snapshot import scan_tree

NOW = datetime(2026, 11, 11, tzinfo=timezone.utc)


def store_at(tmp_path: Path) -> ArtifactStore:
    root = tmp_path / "artifacts"
    root.mkdir()
    return ArtifactStore.open_existing(root, clock=lambda: NOW)


def test_hardlink_and_bad_name_rejected(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    tmp = store.root / "tmp"
    tmp.mkdir()
    item = tmp / "item"
    item.mkdir()
    source = item / "file"
    source.write_text("safe")
    os.link(source, item / "other")
    (tmp / "BAD").write_text("bad")
    plan = store.maintenance().plan_cleanup("tmp", "7d", tmp_path / "index", NOW)
    assert {item.path.name: item.reason for item in plan.items} == {
        "BAD": "BAD_NAME",
        "item": "UNSAFE_ENTRY",
    }
    with pytest.raises(UnsafePathError):
        scan_tree(item)


def test_link_detection_refuses_tree_even_without_symlink_privilege(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scheduler_core.io.tree_snapshot as snapshot_module
    from scheduler_core.io.paths import _is_link

    root = tmp_path / "root"
    root.mkdir()
    link = root / "link"
    link.write_text("placeholder")
    original = _is_link
    monkeypatch.setattr(snapshot_module, "_is_link", lambda path: path == link or original(path))
    with pytest.raises(UnsafePathError):
        snapshot_module.scan_tree(root)


def test_scan_tree_limits_and_default(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    nested = root / "dir"
    nested.mkdir(parents=True)
    (nested / "file").write_bytes(b"payload")
    assert scan_tree(root).file_count == 1
    assert scan_tree(root, max_depth=2, max_files=1).file_count == 1
    with pytest.raises(UnsafePathError, match="depth"):
        scan_tree(root, max_depth=1)
    with pytest.raises(UnsafePathError, match="count"):
        scan_tree(root, max_files=0)
    empty = tmp_path / "empty"
    empty.mkdir()
    assert scan_tree(empty, max_depth=0, max_files=0).file_count == 0


@pytest.mark.parametrize("value", [-1, True, 1.5, "1"])
def test_scan_tree_rejects_invalid_limits(tmp_path: Path, value: object) -> None:
    from typing import Any, cast

    for field in ("max_depth", "max_files"):
        with pytest.raises(ValueError):
            scan_tree(tmp_path, **{field: cast(Any, value)})
