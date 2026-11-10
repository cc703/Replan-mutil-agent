"""Lifecycle acceptance examples for artifact storage."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from scheduler_core.io import (
    ArtifactError,
    ArtifactStore,
    GitInfo,
    Run,
    RunClosedError,
    read_manifest,
)


NOW = datetime(2026, 11, 10, tzinfo=timezone.utc)


def test_running_to_completed_and_new_handle_is_closed(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path, clock=lambda: NOW)
    run = store.new_run(
        "experiment", "e2_replan_micro", "small-light", git=GitInfo(commit="abcdef0", dirty=False)
    )
    run.path("raw.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    run.write_json("plans/inst1_m.json", {"k": 1})
    result = run.finish("completed", outputs=["raw.csv", "plans/inst1_m.json"])
    assert result == read_manifest(run.dir)
    assert result.outputs == ["raw.csv", "plans/inst1_m.json"]
    with pytest.raises(RunClosedError):
        Run(tmp_path, run.dir).path("new.csv")


def test_invalid_output_then_retry_and_unique_run(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path, clock=lambda: NOW)
    git = GitInfo(commit="abcdef0", dirty=False)
    run = store.new_run("sim", "sample", "tag", git=git)
    prior = (run.dir / "manifest.json").read_bytes()
    with pytest.raises(ArtifactError):
        run.finish("failed", outputs=["missing.csv"])
    assert (run.dir / "manifest.json").read_bytes() == prior
    assert run.finish("partial").status == "partial"
    assert store.new_run("sim", "sample", "tag", git=git).run_id.endswith("-2")


def test_failed_replace_preserves_manifest_and_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    store = ArtifactStore(tmp_path, clock=lambda: NOW)
    run = store.new_run("sim", "sample", "tag", git=GitInfo(commit="abcdef0", dirty=False))
    run.write_json("output.json", {"value": 1})
    before = (run.dir / "manifest.json").read_bytes()
    replace = os.replace

    def fail_replace(source: object, destination: object) -> None:
        raise PermissionError("injected")

    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", fail_replace)
        with pytest.raises(PermissionError):
            run.finish("completed", outputs=["output.json"])
    assert os.replace is replace
    assert (run.dir / "manifest.json").read_bytes() == before
    assert not list(run.dir.glob(".manifest-*"))
    assert run.finish("completed", outputs=["output.json"]).status == "completed"


@pytest.mark.parametrize("failure", ["fsync", "file_chmod", "temp_chmod", "replace"])
def test_finish_failure_is_retryable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    import os

    run = ArtifactStore(tmp_path, clock=lambda: NOW).new_run(
        "sim", "sample", "tag", git=GitInfo(commit="abcdef0", dirty=False)
    )
    run.write_json("output.json", {"value": 1})
    old = (run.dir / "manifest.json").read_bytes()
    chmod = os.chmod
    count = 0

    def failing_chmod(path: str | Path, mode: int) -> None:
        nonlocal count
        count += 1
        if failure == "file_chmod" and count == 2:
            raise PermissionError("injected file chmod")
        if (
            failure == "temp_chmod"
            and Path(str(path)).name.startswith(".manifest-")
            and mode == 0o444
        ):
            raise PermissionError("injected temp chmod")
        chmod(path, mode)

    def fail(*args: object, **kwargs: object) -> None:
        raise PermissionError("injected failure")

    with monkeypatch.context() as patch:
        if failure in {"file_chmod", "temp_chmod"}:
            patch.setattr(os, "chmod", failing_chmod)
        else:
            patch.setattr(os, failure, fail)
        with pytest.raises(PermissionError):
            run.finish("completed", outputs=["output.json"])
    assert (run.dir / "manifest.json").read_bytes() == old
    assert run.manifest.status == "running"
    assert not list(run.dir.glob(".manifest-*"))
    assert run.finish("completed", outputs=["output.json"]).status == "completed"


def test_closed_run_checks_state_before_json_serialization(tmp_path: Path) -> None:
    run = ArtifactStore(tmp_path, clock=lambda: NOW).new_run(
        "sim", "sample", "tag", git=GitInfo(commit="abcdef0", dirty=False)
    )
    run.finish("completed")
    before = (run.dir / "manifest.json").read_bytes()
    with pytest.raises(RunClosedError):
        run.write_json("output.json", object())
    assert (run.dir / "manifest.json").read_bytes() == before


@pytest.mark.parametrize("status", ["completed", "failed", "partial"])
def test_all_terminal_states_close_run(tmp_path: Path, status: str) -> None:
    from typing import Literal, cast

    run = ArtifactStore(tmp_path, clock=lambda: NOW).new_run(
        "sim", "sample", "tag", git=GitInfo(commit="abcdef0", dirty=False)
    )
    final = cast(Literal["completed", "failed", "partial"], status)
    assert run.finish(final).status == status
    for action in (
        lambda: run.path("x.json"),
        lambda: run.write_json("x.json", {}),
        lambda: run.finish(final),
    ):
        with pytest.raises(RunClosedError):
            action()


def test_auto_git_evidence_in_real_repository(tmp_path: Path) -> None:
    import subprocess

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=tmp_path, capture_output=True, text=True, check=True
        ).stdout.strip()

    git("init")
    (tmp_path / "tracked.txt").write_text("content", encoding="utf-8")
    git("add", "tracked.txt")
    git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "initial")
    commit = git("rev-parse", "HEAD")
    run = ArtifactStore(tmp_path / "artifacts").new_run("sim", "sample", "tag")
    assert run.manifest.git.commit == commit
    assert run.manifest.git.dirty is False
    (tmp_path / "untracked.txt").write_text("dirty", encoding="utf-8")
    second = ArtifactStore(tmp_path / "artifacts").new_run("sim", "sample", "tag")
    assert second.manifest.git.dirty is True


def test_publish_is_last_io_and_temp_is_readonly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os
    import stat

    run = ArtifactStore(tmp_path, clock=lambda: NOW).new_run(
        "sim", "sample", "tag", git=GitInfo(commit="abcdef0", dirty=False)
    )
    replace = os.replace

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("I/O after publish")

    def publish(source: str | Path, destination: str | Path) -> None:
        assert os.stat(destination).st_mode & stat.S_IWRITE
        assert not os.stat(source).st_mode & stat.S_IWRITE
        replace(source, destination)
        monkeypatch.setattr(os, "chmod", forbidden)
        monkeypatch.setattr(Path, "read_bytes", forbidden)

    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", publish)
        result = run.finish("completed")
    assert result.status == "completed"


def test_clock_and_end_time_require_aware_order(tmp_path: Path) -> None:
    from datetime import timedelta

    git = GitInfo(commit="abcdef0", dirty=False)
    with pytest.raises(ValueError):
        ArtifactStore(tmp_path, clock=lambda: datetime(2026, 1, 1)).new_run(
            "sim", "sample", "tag", git=git
        )
    run = ArtifactStore(tmp_path, clock=lambda: NOW).new_run("sim", "sample", "tag", git=git)
    for end in (datetime(2026, 1, 1), NOW - timedelta(seconds=1)):
        with pytest.raises(ValueError):
            run.finish("completed", ended_at=end)
    assert run.manifest.status == "running"


@pytest.mark.parametrize("outputs", [["missing"], ["folder"], ["a.json", "a.json"], ["../outside"]])
def test_invalid_outputs_preserve_manifest(tmp_path: Path, outputs: list[str]) -> None:
    from scheduler_core.io import ArtifactError

    run = ArtifactStore(tmp_path, clock=lambda: NOW).new_run(
        "sim", "sample", "tag", git=GitInfo(commit="abcdef0", dirty=False)
    )
    run.write_json("a.json", {})
    (run.dir / "folder").mkdir()
    before = (run.dir / "manifest.json").read_bytes()
    with pytest.raises((ArtifactError, ValueError)):
        run.finish("completed", outputs=outputs)
    assert (run.dir / "manifest.json").read_bytes() == before
    assert run.finish("completed", outputs=["a.json"]).status == "completed"


def test_json_serialization_failure_preserves_existing_file(tmp_path: Path) -> None:
    run = ArtifactStore(tmp_path).new_run(
        "sim", "sample", "tag", git=GitInfo(commit="abcdef0", dirty=False)
    )
    path = run.write_json("out.json", {"text": "中文"})
    before = path.read_bytes()
    for value in (float("nan"), object()):
        with pytest.raises((TypeError, ValueError)):
            run.write_json("out.json", value)
        assert path.read_bytes() == before


def test_stale_temp_cleanup_requires_running_state(tmp_path: Path) -> None:
    run = ArtifactStore(tmp_path, clock=lambda: NOW).new_run(
        "sim", "sample", "tag", git=GitInfo(commit="abcdef0", dirty=False)
    )
    stale = run.dir / ".manifest-stale"
    stale.write_text("temporary", encoding="utf-8")
    run.path("out.json")
    assert not stale.exists()
    run.finish("completed")
    stale.write_text("do not change", encoding="utf-8")
    with pytest.raises(RunClosedError):
        run.path("out.json")
    assert stale.read_text(encoding="utf-8") == "do not change"


def test_creation_failure_removes_only_new_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    store = ArtifactStore(tmp_path, clock=lambda: NOW)
    git = GitInfo(commit="abcdef0", dirty=False)
    prior = store.new_run("sim", "sample", "tag", git=git)
    before = (prior.dir / "manifest.json").read_bytes()

    def fail(*args: object, **kwargs: object) -> None:
        raise PermissionError("injected")

    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", fail)
        with pytest.raises(PermissionError):
            store.new_run("sim", "sample", "tag", git=git)
    assert (prior.dir / "manifest.json").read_bytes() == before
    assert sorted(p.name for p in prior.dir.parent.iterdir()) == [prior.run_id]


def test_readme_example_line_by_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "file.txt").write_text("example", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-m",
            "initial",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    monkeypatch.chdir(tmp_path)
    # README ArtifactStore 用法, executing the example exactly.
    store = ArtifactStore(root="artifacts")
    run = store.new_run(kind="experiment", name="e2_replan_micro", tag="small-light")
    raw_path = run.path("raw.csv")
    raw_path.write_text("a,b\n1,2\n", encoding="utf-8")
    run.write_json("plans/inst1_m.json", {"k": 1})
    run.finish(status="completed", outputs=["raw.csv", "plans/inst1_m.json"])
    assert run.manifest.status == "completed"


def test_terminal_files_are_readonly_and_inputs_not_mutated(tmp_path: Path) -> None:
    import copy

    seeds = [1, 2]
    data = {"nested": ["中文", 1]}
    expected = copy.deepcopy(data)
    outputs = ["out.json"]
    run = ArtifactStore(tmp_path, clock=lambda: NOW).new_run(
        "sim", "sample", "tag", seeds=seeds, git=GitInfo(commit="abcdef0", dirty=False)
    )
    run.write_json("out.json", data)
    run.finish("completed", outputs=outputs)
    assert seeds == [1, 2]
    assert data == expected
    assert outputs == ["out.json"]
    for name in ("out.json", "config.yaml", "manifest.json"):
        with pytest.raises(PermissionError):
            (run.dir / name).write_text("changed", encoding="utf-8")


def test_path_recheck_failure_preserves_running_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scheduler_core.io.artifacts as artifacts
    from scheduler_core.io import UnsafePathError
    from scheduler_core.io.paths import inside

    run = ArtifactStore(tmp_path, clock=lambda: NOW).new_run(
        "sim", "sample", "tag", git=GitInfo(commit="abcdef0", dirty=False)
    )
    before = (run.dir / "manifest.json").read_bytes()
    original = inside
    calls = 0

    def fail_second(root: Path, path: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise UnsafePathError("injected recheck")
        original(root, path)

    with monkeypatch.context() as patch:
        patch.setattr(artifacts, "inside", fail_second)
        with pytest.raises(UnsafePathError):
            run.finish("completed")
    assert (run.dir / "manifest.json").read_bytes() == before
    assert run.finish("completed").status == "completed"


def test_unavailable_git_raises_artifact_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    def unavailable(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("git unavailable")

    monkeypatch.setattr(subprocess, "run", unavailable)
    with pytest.raises(ArtifactError):
        ArtifactStore(tmp_path).new_run("sim", "sample", "tag")
    assert not (tmp_path / "runs").exists()


def test_failed_finish_leaves_readonly_output_and_can_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    run = ArtifactStore(tmp_path, clock=lambda: NOW).new_run(
        "sim", "sample", "tag", git=GitInfo(commit="abcdef0", dirty=False)
    )
    output = run.write_json("out.json", {})

    def fail(*args: object, **kwargs: object) -> None:
        raise PermissionError("injected")

    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", fail)
        with pytest.raises(PermissionError):
            run.finish("completed", outputs=["out.json"])
    with pytest.raises(PermissionError):
        output.write_text("changed", encoding="utf-8")
    with pytest.raises(PermissionError):
        run.write_json("out.json", {"changed": True})
    assert run.finish("completed", outputs=["out.json"]).status == "completed"
