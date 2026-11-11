"""Behavioral coverage of artifact cleanup and its safety boundaries."""

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scheduler_core.io.artifacts import ArtifactStore
from scheduler_core.io.errors import UnsafePathError

NOW = datetime(2026, 11, 11, tzinfo=timezone.utc)


def test_open_existing_rejects_project_marker(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "pyproject.toml").write_text("marker")
    with pytest.raises(UnsafePathError):
        ArtifactStore.open_existing(root)


def test_open_existing_rejects_missing_file_and_filesystem_root(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    with pytest.raises(UnsafePathError):
        ArtifactStore.open_existing(missing)
    assert not missing.exists()
    file = tmp_path / "file"
    file.write_text("not a directory")
    with pytest.raises(UnsafePathError):
        ArtifactStore.open_existing(file)
    with pytest.raises(UnsafePathError):
        ArtifactStore.open_existing(Path(tmp_path.anchor))


def test_removal_does_not_use_rmtree() -> None:
    import ast

    source = Path(__file__).resolve().parents[3] / "src" / "scheduler_core" / "io" / "removal.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, ast.Attribute) and node.attr == "rmtree" for node in ast.walk(tree)
    )


@pytest.mark.parametrize("marker", [".git", "pyproject.toml"])
def test_marker_entry_even_if_dangling_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, marker: str
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    original = os.path.lexists
    monkeypatch.setattr(
        os.path, "lexists", lambda path: Path(path) == root / marker or original(path)
    )
    with pytest.raises(UnsafePathError):
        ArtifactStore.open_existing(root)


def test_open_existing_checks_original_junction_dotdot(tmp_path: Path) -> None:
    import subprocess
    import sys

    if sys.platform != "win32":
        return
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    junction = root / "junction"
    proc = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)], capture_output=True, check=False
    )
    assert proc.returncode == 0, proc.stderr
    with pytest.raises(UnsafePathError):
        ArtifactStore.open_existing(junction / "..")
