"""Real process coverage for archive CLI."""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from scheduler_core.io.artifacts import ArtifactStore
from scheduler_core.io.manifest import GitInfo

SCRIPT = Path(__file__).resolve().parents[3] / "tools" / "archive_run.py"


def test_cli_dry_run_apply_verify_and_conflict(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    now = datetime(2026, 11, 11, tzinfo=timezone.utc)
    store = ArtifactStore.open_existing(root, clock=lambda: now)
    run = store.new_run("sim", "sample", "test", git=GitInfo(commit="abcdef1", dirty=False))
    run.finish("completed")
    command = [
        sys.executable,
        str(SCRIPT),
        "--root",
        str(root),
        "--run",
        run.run_id,
        "--format",
        "json",
    ]

    def invoke(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([*command, *args], capture_output=True, text=True, check=False)

    first = invoke()
    assert first.returncode == 0
    assert json.loads(first.stdout)["run_id"] == run.run_id
    assert invoke().stdout == first.stdout
    assert not (root / "archive").exists()
    assert invoke("--apply").returncode == 0
    assert json.loads(invoke("--verify").stdout)["valid"] is True
    assert invoke("--apply").returncode == 3
    assert invoke("--apply", "--verify").returncode == 2


def test_cli_missing_root(tmp_path: Path) -> None:
    root = tmp_path / "missing"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), "--run", "x"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 3
    assert not root.exists()


def test_apply_failure_exit_four(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    now = datetime(2026, 11, 11, tzinfo=timezone.utc)
    store = ArtifactStore.open_existing(root, clock=lambda: now)
    run = store.new_run("sim", "sample", "test", git=GitInfo(commit="abcdef1", dirty=False))
    run.finish("completed")
    injected = """import runpy, sys
sys.path.insert(0, sys.argv[1])
from scheduler_core.io import archive
from scheduler_core.io.errors import ArtifactError
def fail(*args): raise ArtifactError('stage verification failed')
archive._check_zip = fail
sys.argv = [sys.argv[2], '--root', sys.argv[3], '--run', sys.argv[4], '--apply', '--format', 'json']
runpy.run_path(sys.argv[0], run_name='__main__')
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            injected,
            str(SCRIPT.parents[1] / "src"),
            str(SCRIPT),
            str(root),
            run.run_id,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 4
    assert json.loads(result.stderr)["error"] == "stage verification failed"
