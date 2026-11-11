"""Behavioral coverage of artifact cleanup and its safety boundaries."""

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scheduler_core.io.artifacts import ArtifactStore

NOW = datetime(2026, 11, 11, tzinfo=timezone.utc)


def store_at(tmp_path: Path) -> ArtifactStore:
    root = tmp_path / "artifacts"
    root.mkdir()
    return ArtifactStore.open_existing(root, clock=lambda: NOW)


def old(path: Path, seconds: int = 800000) -> None:
    timestamp = NOW.timestamp() - seconds
    os.utime(path, (timestamp, timestamp))


def independent_tree(root: Path) -> tuple[tuple[str, str, int, int, bytes], ...]:
    """Capture bytes and metadata independently of the production scanner."""
    import stat

    result = []
    for path in [root, *sorted(root.rglob("*"))]:
        info = path.lstat()
        kind = "directory" if stat.S_ISDIR(info.st_mode) else "file"
        data = path.read_bytes() if kind == "file" else b""
        result.append(
            (path.relative_to(root).as_posix(), kind, info.st_mode, info.st_mtime_ns, data)
        )
    return tuple(result)


def test_cli_missing_root_is_read_only(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[3] / "tools" / "clean_artifacts.py"
    root = tmp_path / "absent"
    proc = subprocess.run(
        [sys.executable, str(script), "--kind", "tmp", "--root", str(root)],
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 3
    assert not root.exists()


def test_cli_json_dry_run_preserves_tree(tmp_path: Path) -> None:
    import json

    store = store_at(tmp_path)
    target = store.root / "tmp" / "entry"
    target.parent.mkdir()
    target.write_text("keep")
    old(target)
    before = independent_tree(store.root)
    script = Path(__file__).resolve().parents[3] / "tools" / "clean_artifacts.py"
    args = [
        sys.executable,
        str(script),
        "--kind",
        "tmp",
        "--root",
        str(store.root),
        "--index",
        str(tmp_path / "missing"),
        "--format",
        "json",
    ]
    proc = subprocess.run(args, capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["plan"]["items"][0]["path"] == str(target)
    assert payload["result"] is None
    assert independent_tree(store.root) == before
    bad = subprocess.run([*args, "--older-than", "0d"], capture_output=True, check=False)
    assert bad.returncode == 2
    assert independent_tree(store.root) == before


def test_explicit_empty_age_rejected_by_api_and_cli(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    with pytest.raises(ValueError):
        store.maintenance().plan_cleanup("tmp", "", tmp_path / "index", NOW)
    script = Path(__file__).resolve().parents[3] / "tools" / "clean_artifacts.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--kind",
            "tmp",
            "--root",
            str(store.root),
            "--older-than",
            "",
        ],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2


def test_cli_reports_apply_failure(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    target = store.root / "tmp" / "entry"
    target.parent.mkdir()
    target.write_text("keep")
    os.utime(target, (1, 1))
    script = Path(__file__).resolve().parents[3] / "tools" / "clean_artifacts.py"
    code = (
        "import os,runpy,sys; "
        "os.unlink=lambda path: (_ for _ in ()).throw(PermissionError('injected')); "
        "sys.argv=[sys.argv[1], '--kind', 'tmp', '--root', sys.argv[2], "
        "'--index', sys.argv[3], '--apply', '--format', 'json']; "
        "runpy.run_path(sys.argv[0], run_name='__main__')"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code, str(script), str(store.root), str(tmp_path / "index")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 4
    assert target.read_text() == "keep"
