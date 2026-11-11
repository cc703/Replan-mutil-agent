"""Behavioral coverage of artifact cleanup and its safety boundaries."""

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import pytest

from scheduler_core.io.artifacts import ArtifactStore
from scheduler_core.io.errors import UnsafePathError
from scheduler_core.io.manifest import GitInfo
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


def test_apply_readonly_and_other_target(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    directory = store.root / "tmp" / "old"
    directory.mkdir(parents=True)
    file = directory / "file"
    file.write_text("data")
    old(file)
    old(directory)
    os.chmod(file, 0o444)
    sentinel = tmp_path / "sentinel"
    sentinel.write_text("keep")
    maintenance = store.maintenance()
    plan = maintenance.plan_cleanup("tmp", "7d", tmp_path / "index", NOW)
    result = maintenance.apply_cleanup(plan, tmp_path / "index", NOW)
    assert result.deleted == (directory,)
    assert sentinel.read_text() == "keep"


def test_failure_continues_and_lists_remaining(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = store_at(tmp_path)
    tmp = store.root / "tmp"
    tmp.mkdir()
    for name in ("a", "b"):
        directory = tmp / name
        directory.mkdir()
        for filename in ("one", "two"):
            file = directory / filename
            file.write_text(filename)
            old(file)
        old(directory)
    original = os.unlink

    def fail_one(path: Path) -> None:
        if Path(path) == tmp / "a" / "two":
            raise PermissionError("injected")
        original(path)

    monkeypatch.setattr(os, "unlink", fail_one)
    maintenance = store.maintenance()
    plan = maintenance.plan_cleanup("tmp", "7d", tmp_path / "index", NOW)
    result = maintenance.apply_cleanup(plan, tmp_path / "index", NOW)
    assert result.failed == (tmp / "a",)
    assert result.partial == (tmp / "a",)
    assert tmp / "a" / "two" in result.remaining
    assert result.deleted == (tmp / "b",)
    assert not (tmp / "a" / "one").exists()


def test_real_junction_never_followed(tmp_path: Path) -> None:
    if sys.platform != "win32":
        return
    store = store_at(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_text("preserve")
    target = store.root / "tmp" / "entry"
    target.mkdir(parents=True)
    old(target)
    maintenance = store.maintenance()
    plan = maintenance.plan_cleanup("tmp", "7d", tmp_path / "index", NOW)
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(target / "junction"), str(outside)],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    with pytest.raises(UnsafePathError):
        scan_tree(target / "junction" / "..")
    outcome = maintenance.apply_cleanup(plan, tmp_path / "index", NOW)
    assert outcome.skipped[0].reason == "CHANGED_SINCE_PLAN"
    assert sentinel.read_text() == "preserve"
    next_plan = maintenance.plan_cleanup("tmp", "7d", tmp_path / "index", NOW)
    assert next_plan.items[0].reason == "UNSAFE_ENTRY"


def test_forged_target_outside_store_cannot_be_removed(tmp_path: Path) -> None:
    from dataclasses import replace

    store = store_at(tmp_path)
    candidate = store.root / "tmp" / "candidate"
    candidate.parent.mkdir()
    candidate.write_text("x")
    old(candidate)
    outside = tmp_path / "outside"
    outside.write_text("safe")
    maintenance = store.maintenance()
    plan = maintenance.plan_cleanup("tmp", "7d", tmp_path / "index", NOW)
    forged = replace(plan, items=(replace(plan.items[0], path=outside),))
    result = maintenance.apply_cleanup(forged, tmp_path / "index", NOW)
    assert result.skipped[0].reason == "CHANGED_SINCE_PLAN"
    assert outside.read_text() == "safe"


def test_rechecks_each_candidate_after_first_deletion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = store_at(tmp_path)
    tmp = store.root / "tmp"
    tmp.mkdir()
    for name in ("a", "b"):
        target = tmp / name
        target.write_text(name)
        old(target)
    maint = store.maintenance()
    plan = maint.plan_cleanup("tmp", "7d", tmp_path / "index", NOW)
    original = os.unlink

    def mutate_second(path: Path) -> None:
        if Path(path) == tmp / "a":
            (tmp / "b").write_text("changed")
        original(path)

    monkeypatch.setattr(os, "unlink", mutate_second)
    result = maint.apply_cleanup(plan, tmp_path / "index", NOW)
    assert result.deleted == (tmp / "a",)
    assert result.skipped[0].reason == "CHANGED_SINCE_PLAN"
    assert (tmp / "b").read_text() == "changed"


def test_status_change_after_plan_is_skipped(tmp_path: Path) -> None:
    import json

    store = store_at(tmp_path)
    run = make_run(store, "failed")
    index = tmp_path / "index"
    maint = store.maintenance()
    plan = maint.plan_cleanup("failed-runs", "14d", index, NOW)
    manifest = run / "manifest.json"
    os.chmod(manifest, 0o666)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["status"] = "running"
    data["ended_at"] = None
    manifest.write_text(json.dumps(data), encoding="utf-8")
    result = maint.apply_cleanup(plan, index, NOW)
    assert result.skipped[0].reason == "CHANGED_SINCE_PLAN"
    assert run.exists()
