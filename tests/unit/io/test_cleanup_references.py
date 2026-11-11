"""Behavioral coverage of artifact cleanup and its safety boundaries."""

import subprocess
import sys

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import pytest

from scheduler_core.io.artifacts import ArtifactStore
from scheduler_core.io.errors import ArtifactError
from scheduler_core.io.manifest import GitInfo

NOW = datetime(2026, 11, 11, tzinfo=timezone.utc)


def store_at(tmp_path: Path) -> ArtifactStore:
    root = tmp_path / "artifacts"
    root.mkdir()
    return ArtifactStore.open_existing(root, clock=lambda: NOW)


def make_run(
    store: ArtifactStore,
    status: Literal["running", "completed", "failed", "partial"],
    tag: str = "case",
) -> Path:
    then = NOW - timedelta(days=20)
    creator = ArtifactStore.open_existing(store.root, clock=lambda: then)
    run = creator.new_run("sim", "small-light", tag, git=GitInfo(commit="abcdef1", dirty=False))
    if status != "running":
        run.finish(status, ended_at=then)
    return run.dir


def test_failed_running_completed_and_reference(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    failed = make_run(store, "failed", "failed")
    partial = make_run(store, "partial", "partial")
    running = make_run(store, "running", "running")
    completed = make_run(store, "completed", "completed")
    index = tmp_path / "INDEX.md"
    index.write_text(f"See {failed.name}", encoding="utf-8")
    maintenance = store.maintenance()
    plan = maintenance.plan_cleanup("failed-runs", "14d", index, NOW)
    reasons = {item.path: item.reason for item in plan.items}
    assert reasons == {
        failed: "PROTECTED",
        partial: "ELIGIBLE",
        running: "STALE_RUNNING",
        completed: "COMPLETED",
    }
    result = maintenance.apply_cleanup(plan, index, NOW)
    assert result.deleted == (partial,)
    assert failed.exists() and running.exists() and completed.exists()


def test_index_bad_rejects_apply(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    failed = make_run(store, "failed")
    index = tmp_path / "index"
    maintenance = store.maintenance()
    plan = maintenance.plan_cleanup("failed-runs", "14d", index, NOW)
    index.write_text("artifacts/runs/sim/small-light/truncated", encoding="utf-8")
    with pytest.raises(ArtifactError, match="INDEX_UNREADABLE"):
        maintenance.apply_cleanup(plan, index, NOW)
    assert failed.exists()


@pytest.mark.parametrize(
    "content",
    [
        b"\xff",
        b"x\0y",
        b"x" * 1048577,
        b"artifacts/runs/sim",
        b"artifacts/runs/no/name",
        b"artifacts/runs/sim/name?x",
        b"artifacts/runs/sim/name#x",
        b"artifacts/runs/sim/name%20x",
    ],
    ids=["utf8", "nul", "large", "short", "kind", "query", "fragment", "percent"],
)
def test_invalid_index_rejected(tmp_path: Path, content: bytes) -> None:
    store = store_at(tmp_path)
    index = tmp_path / "index"
    index.write_bytes(content)
    with pytest.raises(ArtifactError, match="INDEX_UNREADABLE"):
        store.maintenance().plan_cleanup("tmp", None, index, NOW)


def test_appearing_reference_prevents_removal(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    run = make_run(store, "failed")
    index = tmp_path / "index"
    maintenance = store.maintenance()
    plan = maintenance.plan_cleanup("failed-runs", "14d", index, NOW)
    index.write_text(run.name, encoding="utf-8")
    result = maintenance.apply_cleanup(plan, index, NOW)
    assert result.skipped[0].reason == "CHANGED_SINCE_PLAN"
    assert run.exists()


def test_index_paths_protect_name_and_overprotect_prefix(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    first = make_run(store, "failed", "one")
    second = make_run(store, "partial", "two")
    index = tmp_path / "index"
    index.write_text(r"[result](artifacts\runs\sim\small-light-2)", encoding="utf-8")
    plan = store.maintenance().plan_cleanup("failed-runs", "14d", index, NOW)
    assert {item.path: item.reason for item in plan.items} == {
        first: "PROTECTED",
        second: "PROTECTED",
    }


def test_index_directory_rejected(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    index = tmp_path / "index"
    index.mkdir()
    with pytest.raises(ArtifactError, match="INDEX_UNREADABLE"):
        store.maintenance().plan_cleanup("tmp", None, index, NOW)


def test_absent_index_and_name_reference(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    run = make_run(store, "failed")
    index = tmp_path / "index"
    maint = store.maintenance()
    plan = maint.plan_cleanup("failed-runs", "14d", index, NOW)
    assert plan.index_status == "INDEX_ABSENT"
    assert plan.items[0].reason == "ELIGIBLE"
    index.write_text(r"`artifacts\runs\sim\small-light`", encoding="utf-8")
    plan = maint.plan_cleanup("failed-runs", "14d", index, NOW)
    assert plan.index_status == "INDEX_OK"
    assert plan.protected[0].path == run


def test_multiline_index_path_is_ambiguous(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    index = tmp_path / "index"
    index.write_text("`artifacts/runs/sim/name\ncontinued`", encoding="utf-8")
    with pytest.raises(ArtifactError, match="INDEX_UNREADABLE"):
        store.maintenance().plan_cleanup("tmp", None, index, NOW)


def test_index_read_error_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = store_at(tmp_path)
    run = make_run(store, "failed")
    index = tmp_path / "index"
    index.write_text("anything")
    maint = store.maintenance()
    plan = maint.plan_cleanup("failed-runs", "14d", index, NOW)
    original = Path.read_bytes

    def broken(path: Path) -> bytes:
        if path == index:
            raise PermissionError("injected")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", broken)
    with pytest.raises(ArtifactError, match="INDEX_UNREADABLE"):
        maint.apply_cleanup(plan, index, NOW)
    assert run.exists()


def test_junction_index_is_rejected(tmp_path: Path) -> None:
    if sys.platform != "win32":
        return
    store = store_at(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    index = tmp_path / "index"
    proc = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(index), str(outside)], capture_output=True, check=False
    )
    assert proc.returncode == 0
    with pytest.raises(ArtifactError):
        store.maintenance().plan_cleanup("tmp", None, index, NOW)


@pytest.mark.parametrize(
    "template",
    [
        "| result | {id} |\n",
        "`{id}`\n",
        "[result](artifacts/runs/sim/small-light/{id}/manifest.json)\n",
        "\ufeffheader\r\n{id}\r\n",
    ],
)
def test_index_valid_reference_forms(tmp_path: Path, template: str) -> None:
    store = store_at(tmp_path)
    run = make_run(store, "failed")
    index = tmp_path / "index"
    index.write_bytes(template.format(id=run.name).encode("utf-8"))
    plan = store.maintenance().plan_cleanup("failed-runs", "14d", index, NOW)
    assert plan.items[0].reason == "PROTECTED"
    assert plan.items[0].referenced is True


def test_reference_to_sibling_id_only_protects_that_sibling(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    first = make_run(store, "failed", "first")
    second = make_run(store, "partial", "second")
    index = tmp_path / "index"
    index.write_text(f"| {first.name} |", encoding="utf-8")
    plan = store.maintenance().plan_cleanup("failed-runs", "14d", index, NOW)
    assert {item.path: item.reason for item in plan.items} == {
        first: "PROTECTED",
        second: "ELIGIBLE",
    }
