"""Behavioral coverage of artifact cleanup and its safety boundaries."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import pytest

from scheduler_core.io.artifacts import ArtifactStore
from scheduler_core.io.manifest import GitInfo
from scheduler_core.io.retention import parse_age
from scheduler_core.io.tree_snapshot import scan_tree

NOW = datetime(2026, 11, 11, tzinfo=timezone.utc)


def store_at(tmp_path: Path) -> ArtifactStore:
    root = tmp_path / "artifacts"
    root.mkdir()
    return ArtifactStore.open_existing(root, clock=lambda: NOW)


def old(path: Path, seconds: int = 800000) -> None:
    timestamp = NOW.timestamp() - seconds
    os.utime(path, (timestamp, timestamp))


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


@pytest.mark.parametrize("age", ["", "0d", "-1d", "7", "7x", "1.5d", "3651d", "７d", " 7d"])
def test_invalid_age(age: str) -> None:
    with pytest.raises(ValueError):
        parse_age(age, "tmp")


def test_failed_age_limit() -> None:
    with pytest.raises(ValueError):
        parse_age("13d", "failed-runs")
    assert parse_age("14d", "failed-runs") == 14 * 86400 * 10**9


def test_tmp_nested_age_and_change(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    directory = store.root / "tmp" / "old"
    directory.mkdir(parents=True)
    child = directory / "a.txt"
    child.write_text("hello")
    old(child, 86400)
    old(directory)
    maintenance = store.maintenance()
    plan = maintenance.plan_cleanup("tmp", "7d", tmp_path / "missing", NOW)
    assert plan.items[0].reason == "TOO_YOUNG"
    old(child)
    plan = maintenance.plan_cleanup("tmp", "7d", tmp_path / "missing", NOW)
    assert plan.items[0].reason == "ELIGIBLE"
    (directory / "new.txt").write_text("changed")
    result = maintenance.apply_cleanup(plan, tmp_path / "missing", NOW)
    assert result.skipped[0].reason == "CHANGED_SINCE_PLAN"
    assert child.exists()


def test_boundary_future_and_empty_tmp(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    maint = store.maintenance()
    index = tmp_path / "missing"
    assert maint.plan_cleanup("tmp", "7d", index, NOW).items == ()
    tmp = store.root / "tmp"
    tmp.mkdir()
    boundary = tmp / "boundary"
    boundary.write_text("x")
    at = int(NOW.timestamp()) * 10**9 - 7 * 86400 * 10**9
    os.utime(boundary, ns=(at, at))
    assert maint.plan_cleanup("tmp", "7d", index, NOW).items[0].reason == "TOO_YOUNG"
    os.utime(boundary, ns=(at - 100, at - 100))
    assert maint.plan_cleanup("tmp", "7d", index, NOW).items[0].reason == "ELIGIBLE"
    future = int(NOW.timestamp()) * 10**9 + 10**9
    os.utime(boundary, ns=(future, future))
    assert maint.plan_cleanup("tmp", "7d", index, NOW).items[0].reason == "FUTURE_TIME"


def test_invalid_manifest_is_not_deleted(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    run = make_run(store, "failed")
    manifest = run / "manifest.json"
    os.chmod(manifest, 0o666)
    manifest.write_text("invalid")
    plan = store.maintenance().plan_cleanup("failed-runs", "14d", tmp_path / "index", NOW)
    assert plan.items[0].reason == "MANIFEST_INVALID"
    assert run.exists()


def test_nanosecond_boundary_via_snapshot_injection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dataclasses import replace
    import scheduler_core.io.maintenance as module

    store = store_at(tmp_path)
    target = store.root / "tmp" / "entry"
    target.parent.mkdir()
    target.write_text("x")
    snapshot = scan_tree(target)
    boundary = int(NOW.timestamp()) * 10**9 - 7 * 86400 * 10**9
    monkeypatch.setattr(
        module,
        "scan_tree",
        lambda path: replace(snapshot, entries=(replace(snapshot.entries[0], mtime_ns=boundary),)),
    )
    maintenance = store.maintenance()
    assert (
        maintenance.plan_cleanup("tmp", "7d", tmp_path / "index", NOW).items[0].reason
        == "TOO_YOUNG"
    )
    monkeypatch.setattr(
        module,
        "scan_tree",
        lambda path: replace(
            snapshot, entries=(replace(snapshot.entries[0], mtime_ns=boundary - 1),)
        ),
    )
    assert (
        maintenance.plan_cleanup("tmp", "7d", tmp_path / "index", NOW).items[0].reason == "ELIGIBLE"
    )


@pytest.mark.parametrize("status", ["failed", "partial"])
@pytest.mark.parametrize(
    "offset,expected",
    [
        (timedelta(days=14), "TOO_YOUNG"),
        (timedelta(days=14, microseconds=1), "ELIGIBLE"),
        (timedelta(seconds=-1), "FUTURE_TIME"),
    ],
)
def test_terminal_ended_at_boundaries(
    tmp_path: Path, status: Literal["failed", "partial"], offset: timedelta, expected: str
) -> None:
    store = store_at(tmp_path)
    end = NOW - offset
    creator = ArtifactStore.open_existing(store.root, clock=lambda: end - timedelta(days=1))
    run = creator.new_run("sim", "case", "test", git=GitInfo(commit="abcdef1", dirty=False))
    run.finish(status, ended_at=end)
    plan = store.maintenance().plan_cleanup("failed-runs", "14d", tmp_path / "index", NOW)
    assert plan.items[0].path == run.dir
    assert plan.items[0].reason == expected
    assert plan.items[0].age_ns == int(offset.total_seconds() * 1_000_000_000)
