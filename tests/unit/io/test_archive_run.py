from datetime import datetime, timezone
from pathlib import Path

import pytest

from scheduler_core.io.artifacts import ArtifactStore, Run
from scheduler_core.io.archive_publish import publish_noreplace
from scheduler_core.io.errors import ArtifactError
from scheduler_core.io.manifest import GitInfo

NOW = datetime(2026, 11, 11, tzinfo=timezone.utc)


def setup_run(tmp_path: Path) -> tuple[ArtifactStore, Run]:
    root = tmp_path / "artifacts"
    root.mkdir()
    store = ArtifactStore.open_existing(root, clock=lambda: NOW)
    run = store.new_run("sim", "sample", "test", git=GitInfo(commit="abcdef1", dirty=False))
    run.write_json("nested/output.json", {"ok": True})
    run.finish("completed", outputs=["nested/output.json"])
    return store, run


def test_archive_and_verify_without_source(tmp_path: Path) -> None:
    store, run = setup_run(tmp_path)
    maintenance = store.maintenance()
    plan = maintenance.plan_archive(run.run_id)
    assert not (store.root / "archive").exists()
    result = maintenance.archive(plan, NOW)
    assert result.status == "ARCHIVED"
    assert maintenance.verify_archive(run.run_id).valid
    with pytest.raises(ArtifactError):
        maintenance.archive(plan, NOW)


def test_changed_source_rejected(tmp_path: Path) -> None:
    store, run = setup_run(tmp_path)
    plan = store.maintenance().plan_archive(run.run_id)
    (run.dir / "new.txt").write_bytes(b"new")
    with pytest.raises(ArtifactError, match="SOURCE_CHANGED"):
        store.maintenance().archive(plan, NOW)
    assert not (store.root / "archive").exists()


def test_second_publish_failure_rolls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scheduler_core.io import archive as module

    store, run = setup_run(tmp_path)
    plan = store.maintenance().plan_archive(run.run_id)
    real = publish_noreplace
    count = 0

    def publish(source: Path, target: Path) -> None:
        nonlocal count
        count += 1
        if count == 2:
            raise OSError("injected")
        real(source, target)

    monkeypatch.setattr(module, "publish_noreplace", publish)
    with pytest.raises(ArtifactError, match="publication failed"):
        store.maintenance().archive(plan, NOW)
    assert not plan.zip_path.exists()
    assert not plan.sidecar_path.exists()
    assert not list(plan.zip_path.parent.glob("stage-*.part"))
    assert run.dir.exists()


def test_verify_after_source_renamed_and_detects_corruption(tmp_path: Path) -> None:
    store, run = setup_run(tmp_path)
    maintenance = store.maintenance()
    plan = maintenance.plan_archive(run.run_id)
    maintenance.archive(plan, NOW)
    run.dir.rename(run.dir.with_name("moved"))
    assert maintenance.verify_archive(run.run_id).valid
    plan.zip_path.chmod(0o666)
    data = plan.zip_path.read_bytes()
    plan.zip_path.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
    with pytest.raises(ArtifactError, match="verification failed"):
        maintenance.verify_archive(run.run_id)


def test_chmod_failure_is_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, run = setup_run(tmp_path)
    plan = store.maintenance().plan_archive(run.run_id)

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("injected")

    monkeypatch.setattr("scheduler_core.io.archive.os.chmod", fail)
    result = store.maintenance().archive(plan, NOW)
    assert result.warnings == ("READONLY_NOT_APPLIED",)


def test_record_strictness_and_conflicts(tmp_path: Path) -> None:
    import json
    from pydantic import ValidationError
    from scheduler_core.io.archive_record import (
        ArchiveEntry,
        ArchiveRecord,
        content_digest,
        parse_record,
    )

    store, run = setup_run(tmp_path)
    plan = store.maintenance().plan_archive(run.run_id)
    store.maintenance().archive(plan, NOW)
    raw = plan.sidecar_path.read_bytes()
    payload = json.loads(raw)
    for value in (True, 1.0):
        payload["schema"] = value
        with pytest.raises(ValidationError):
            parse_record(json.dumps(payload).encode())
        with pytest.raises(ValidationError):
            ArchiveRecord.model_validate(payload)
    payload = json.loads(raw)
    payload["empty_directories"] = ["manifest.json/ghost"]
    with pytest.raises(ValidationError):
        parse_record(json.dumps(payload).encode())
    a = ArchiveEntry(path="a", size=0, sha256="0" * 64)
    b = ArchiveEntry(path="a/b", size=0, sha256="0" * 64)
    assert content_digest([b, a]) == content_digest([a, b])
    payload["empty_directories"] = []
    payload["entries"] = [a.model_dump(), b.model_dump()]
    payload["file_count"] = 2
    payload["content_sha256"] = content_digest([a, b])
    with pytest.raises(ValidationError):
        parse_record(json.dumps(payload).encode())


def test_valid_sidecar_changes_can_verify(tmp_path: Path) -> None:
    import json

    store, run = setup_run(tmp_path)
    maintenance = store.maintenance()
    plan = maintenance.plan_archive(run.run_id)
    maintenance.archive(plan, NOW)
    plan.sidecar_path.chmod(0o666)
    payload = json.loads(plan.sidecar_path.read_bytes())
    payload["archived_at"] = "2025-01-01T00:00:00Z"
    payload["empty_directories"] = ["invented"]
    plan.sidecar_path.write_text(json.dumps(payload), encoding="utf-8")
    assert maintenance.verify_archive(run.run_id).valid


def test_target_race_preserves_other_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scheduler_core.io import archive as module

    store, run = setup_run(tmp_path)
    plan = store.maintenance().plan_archive(run.run_id)
    real = publish_noreplace

    def race(source: Path, target: Path) -> None:
        target.write_bytes(b"other writer")
        real(source, target)

    monkeypatch.setattr(module, "publish_noreplace", race)
    with pytest.raises(ArtifactError):
        store.maintenance().archive(plan, NOW)
    assert plan.zip_path.read_bytes() == b"other writer"
    assert not list(plan.zip_path.parent.glob("stage-*.part"))


def test_partial_when_rollback_identity_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scheduler_core.io import archive as module

    store, run = setup_run(tmp_path)
    plan = store.maintenance().plan_archive(run.run_id)
    real = publish_noreplace
    calls = 0

    def replace(source: Path, target: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            plan.zip_path.write_bytes(b"changed")
            raise OSError("injected")
        real(source, target)

    monkeypatch.setattr(module, "publish_noreplace", replace)
    result = store.maintenance().archive(plan, NOW)
    assert result.status == "PARTIAL_ARCHIVE"
    assert plan.zip_path.read_bytes() == b"changed"


def test_zip_stage_failure_cleans_stage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scheduler_core.io import archive as module

    store, run = setup_run(tmp_path)
    plan = store.maintenance().plan_archive(run.run_id)

    def fail(*args: object) -> None:
        raise OSError("injected")

    monkeypatch.setattr(module, "_write_zip", fail)
    with pytest.raises(ArtifactError, match="publication failed"):
        store.maintenance().archive(plan, NOW)
    assert not plan.zip_path.exists()
    assert not list(plan.zip_path.parent.glob("stage-*.part"))
    assert run.dir.exists()


def test_source_modified_mid_archive_reports_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scheduler_core.io import archive as module

    store, run = setup_run(tmp_path)
    plan = store.maintenance().plan_archive(run.run_id)

    def change(*args: object) -> None:
        (run.dir / "added.txt").write_bytes(b"external change")

    monkeypatch.setattr(module, "_check_zip", change)
    with pytest.raises(ArtifactError, match="SOURCE_CHANGED"):
        store.maintenance().archive(plan, NOW)
    assert (run.dir / "added.txt").read_bytes() == b"external change"
    assert not list(plan.zip_path.parent.glob("stage-*.part"))


@pytest.mark.parametrize("status", ["running", "failed", "partial"])
def test_noncompleted_rejected_without_artifacts(tmp_path: Path, status: str) -> None:
    from typing import cast, Literal

    root = tmp_path / "root"
    root.mkdir()
    store = ArtifactStore.open_existing(root, clock=lambda: NOW)
    run = store.new_run("sim", "sample", "test", git=GitInfo(commit="abcdef1", dirty=False))
    if status != "running":
        run.finish(cast(Literal["failed", "partial"], status))
    with pytest.raises(ArtifactError, match="not completed"):
        store.maintenance().plan_archive(run.run_id)
    assert not (root / "archive").exists()


def test_depth_limit_rejected_before_output(tmp_path: Path) -> None:
    store, run = setup_run(tmp_path)
    target = run.dir
    for _ in range(17):
        target = target / "a"
        target.mkdir()
    with pytest.raises(ArtifactError, match="limit"):
        store.maintenance().plan_archive(run.run_id)
    assert not (store.root / "archive").exists()


def test_reproducible_bytes_and_source_unchanged(tmp_path: Path) -> None:
    from scheduler_core.io.tree_snapshot import scan_tree

    first = tmp_path / "one"
    second = tmp_path / "two"
    first.mkdir()
    second.mkdir()
    s1, r1 = setup_run(first)
    s2, r2 = setup_run(second)
    before = scan_tree(r1.dir)
    p1 = s1.maintenance().plan_archive(r1.run_id)
    p2 = s2.maintenance().plan_archive(r2.run_id)
    s1.maintenance().archive(p1, NOW)
    s2.maintenance().archive(p2, NOW)
    assert scan_tree(r1.dir) == before
    assert p1.zip_path.read_bytes() == p2.zip_path.read_bytes()
    assert p1.sidecar_path.read_bytes() == p2.sidecar_path.read_bytes()


@pytest.mark.parametrize("existing", ["zip", "sidecar", "both"])
def test_existing_target_never_overwritten(tmp_path: Path, existing: str) -> None:
    store, run = setup_run(tmp_path)
    plan = store.maintenance().plan_archive(run.run_id)
    plan.zip_path.parent.mkdir(parents=True)
    paths = (
        [plan.zip_path]
        if existing == "zip"
        else [plan.sidecar_path]
        if existing == "sidecar"
        else [plan.zip_path, plan.sidecar_path]
    )
    for path in paths:
        path.write_bytes(b"existing")
    with pytest.raises(ArtifactError, match="ARCHIVE_EXISTS"):
        store.maintenance().archive(plan, NOW)
    assert all(path.read_bytes() == b"existing" for path in paths)


def test_forged_plan_cannot_redirect_output(tmp_path: Path) -> None:
    from dataclasses import replace

    store, run = setup_run(tmp_path)
    plan = store.maintenance().plan_archive(run.run_id)
    outside = tmp_path / "outside.zip"
    with pytest.raises(ArtifactError, match="SOURCE_CHANGED"):
        store.maintenance().archive(replace(plan, zip_path=outside), NOW)
    assert not outside.exists()


def test_hardlink_is_rejected(tmp_path: Path) -> None:
    import os

    store, run = setup_run(tmp_path)
    os.link(run.dir / "config.yaml", run.dir / "linked.yaml")
    with pytest.raises(ArtifactError):
        store.maintenance().plan_archive(run.run_id)
    assert not (store.root / "archive").exists()


def test_file_limit_before_creating_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scheduler_core.io import archive as module
    from scheduler_core.io.tree_snapshot import TreeSnapshot, scan_tree

    store, run = setup_run(tmp_path)
    original = scan_tree(run.dir)
    file_entry = next(entry for entry in original.entries if entry.kind == "file")
    oversized = TreeSnapshot(original.root, original.entries + (file_entry,) * 100001)
    monkeypatch.setattr(module, "scan_tree", lambda path, **kwargs: oversized)
    with pytest.raises(ArtifactError, match="limit"):
        store.maintenance().plan_archive(run.run_id)
    assert not (store.root / "archive").exists()


def test_stage_readback_failure_cleans_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scheduler_core.io import archive as module

    store, run = setup_run(tmp_path)
    plan = store.maintenance().plan_archive(run.run_id)

    def fail(*args: object) -> None:
        raise ArtifactError("stage verification failed")

    monkeypatch.setattr(module, "_check_zip", fail)
    with pytest.raises(ArtifactError, match="stage verification failed"):
        store.maintenance().archive(plan, NOW)
    assert not plan.zip_path.exists()
    assert not list(plan.zip_path.parent.glob("stage-*.part"))


def test_rollback_failure_reports_partial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scheduler_core.io import archive as module

    store, run = setup_run(tmp_path)
    plan = store.maintenance().plan_archive(run.run_id)
    real_publish = publish_noreplace
    real_unlink = Path.unlink
    calls = 0

    def fail_publish(source: Path, target: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected")
        real_publish(source, target)

    def fail_unlink(path: Path, *args: object, **kwargs: object) -> None:
        if path == plan.zip_path:
            raise OSError("injected")
        real_unlink(path, missing_ok=bool(kwargs.get("missing_ok", False)))

    monkeypatch.setattr(module, "publish_noreplace", fail_publish)
    monkeypatch.setattr(Path, "unlink", fail_unlink)
    result = store.maintenance().archive(plan, NOW)
    assert result.status == "PARTIAL_ARCHIVE"
    assert plan.zip_path.exists()
    assert not plan.sidecar_path.exists()
    assert not list(plan.zip_path.parent.glob("stage-*.part"))


def test_ambiguous_id_requires_kind(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    store = ArtifactStore.open_existing(root, clock=lambda: NOW)
    runs = [
        store.new_run(kind, "sample", "test", git=GitInfo(commit="abcdef1", dirty=False))
        for kind in ("sim", "experiment")
    ]
    for run in runs:
        run.finish("completed")
    assert runs[0].run_id == runs[1].run_id
    with pytest.raises(ArtifactError, match="ambiguous"):
        store.maintenance().plan_archive(runs[0].run_id)
    assert store.maintenance().plan_archive(runs[0].run_id, "sim", "sample").kind == "sim"
    with pytest.raises(ArtifactError, match="missing"):
        store.maintenance().plan_archive("unknown")


def test_archive_avoids_extraction_calls() -> None:
    import ast

    source = Path(__file__).resolve().parents[3] / "src" / "scheduler_core" / "io" / "archive.py"
    tree = ast.parse(source.read_text(encoding="utf-8-sig"))
    assert not any(
        isinstance(node, ast.Attribute) and node.attr in {"extract", "extractall"}
        for node in ast.walk(tree)
    )


def test_corrupt_manifest_rejected(tmp_path: Path) -> None:
    store, run = setup_run(tmp_path)
    manifest = run.dir / "manifest.json"
    manifest.chmod(0o666)
    manifest.write_bytes(b"not json")
    with pytest.raises(ArtifactError):
        store.maintenance().plan_archive(run.run_id)
    assert not (store.root / "archive").exists()


def test_unsafe_name_rejected(tmp_path: Path) -> None:
    store, run = setup_run(tmp_path)
    (run.dir / "Bad Name").write_bytes(b"x")
    with pytest.raises(ArtifactError):
        store.maintenance().plan_archive(run.run_id)
    assert not (store.root / "archive").exists()


def test_output_chain_link_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scheduler_core.io import paths

    store, run = setup_run(tmp_path)
    archive_dir = store.root / "archive"
    archive_dir.mkdir()
    real = paths._is_link

    def fake(path: Path) -> bool:
        return path == archive_dir or real(path)

    monkeypatch.setattr(paths, "_is_link", fake)
    with pytest.raises(ArtifactError):
        store.maintenance().plan_archive(run.run_id)
    assert not list(archive_dir.iterdir())


def test_archive_members_and_digests_match_source(tmp_path: Path) -> None:
    import hashlib
    import json
    import zipfile
    from scheduler_core.io.archive_record import content_digest, parse_record

    store, run = setup_run(tmp_path)
    plan = store.maintenance().plan_archive(run.run_id)
    store.maintenance().archive(plan, NOW)
    record = parse_record(plan.sidecar_path.read_bytes())
    assert record.archive_sha256 == hashlib.sha256(plan.zip_path.read_bytes()).hexdigest()
    assert (
        record.source_manifest_sha256
        == hashlib.sha256((run.dir / "manifest.json").read_bytes()).hexdigest()
    )
    assert record.content_sha256 == content_digest(record.entries)
    assert record.file_count == plan.file_count == len(record.entries)
    with zipfile.ZipFile(plan.zip_path) as archive:
        assert archive.namelist() == [f"{run.run_id}/{entry.path}" for entry in record.entries]
        for entry in record.entries:
            info = archive.getinfo(f"{run.run_id}/{entry.path}")
            data = archive.read(info)
            assert data == (run.dir / entry.path).read_bytes()
            assert len(data) == entry.size
            assert hashlib.sha256(data).hexdigest() == entry.sha256
            assert info.date_time == (1980, 1, 1, 0, 0, 0)
            assert info.external_attr >> 16 == 0o100444
            assert info.compress_type == zipfile.ZIP_DEFLATED
    assert json.loads(plan.sidecar_path.read_bytes())["schema"] == 1


def test_sidecar_race_preserves_other_and_rolls_back_zip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scheduler_core.io import archive as module

    store, run = setup_run(tmp_path)
    plan = store.maintenance().plan_archive(run.run_id)
    calls = 0

    def race(source: Path, target: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            target.write_bytes(b"other writer")
        publish_noreplace(source, target)

    monkeypatch.setattr(module, "publish_noreplace", race)
    with pytest.raises(ArtifactError, match="publication failed"):
        store.maintenance().archive(plan, NOW)
    assert not plan.zip_path.exists()
    assert plan.sidecar_path.read_bytes() == b"other writer"
    assert not list(plan.zip_path.parent.glob("stage-*.part"))


def test_sidecar_stage_readback_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scheduler_core.io import archive as module

    store, run = setup_run(tmp_path)
    plan = store.maintenance().plan_archive(run.run_id)

    def fail(data: bytes) -> object:
        raise ValueError("injected")

    monkeypatch.setattr(module, "parse_record", fail)
    with pytest.raises(ArtifactError, match="publication failed"):
        store.maintenance().archive(plan, NOW)
    assert not plan.zip_path.exists()
    assert not list(plan.zip_path.parent.glob("stage-*.part"))


def test_junction_inside_run_rejected_without_touching_target(tmp_path: Path) -> None:
    import subprocess
    import sys

    if sys.platform != "win32":
        return
    store, run = setup_run(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_bytes(b"keep")
    junction = run.dir / "junction"
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    try:
        with pytest.raises(ArtifactError):
            store.maintenance().plan_archive(run.run_id)
        assert sentinel.read_bytes() == b"keep"
        assert not (store.root / "archive").exists()
    finally:
        junction.rmdir()
