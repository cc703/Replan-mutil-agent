"""Archive sidecar structure and consistency tests."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from scheduler_core.io.archive_record import (
    ArchiveEntry,
    ArchiveRecord,
    content_digest,
    parse_record,
)
from scheduler_core.io.artifacts import ArtifactStore
from scheduler_core.io.manifest import GitInfo


def record_bytes(tmp_path: Path) -> bytes:
    now = datetime(2026, 11, 11, tzinfo=timezone.utc)
    root = tmp_path / "root"
    root.mkdir()
    store = ArtifactStore.open_existing(root, clock=lambda: now)
    run = store.new_run("sim", "sample", "test", git=GitInfo(commit="abcdef1", dirty=False))
    run.finish("completed")
    plan = store.maintenance().plan_archive(run.run_id)
    store.maintenance().archive(plan, now)
    return plan.sidecar_path.read_bytes()


def test_strict_schema_and_duplicates(tmp_path: Path) -> None:
    raw = record_bytes(tmp_path)
    payload = json.loads(raw)
    for value in (True, 1.0):
        payload["schema"] = value
        with pytest.raises(ValidationError):
            parse_record(json.dumps(payload).encode())
        with pytest.raises(ValidationError):
            ArchiveRecord.model_validate(payload)
    with pytest.raises(ValueError, match="duplicate"):
        parse_record(raw.replace(b'"schema": 1', b'"schema": 1, "schema": 1'))
    payload = json.loads(raw)
    payload["extra"] = 1
    with pytest.raises(ValidationError):
        parse_record(json.dumps(payload).encode())


def test_path_conflicts_and_sorted_digest(tmp_path: Path) -> None:
    payload = json.loads(record_bytes(tmp_path))
    payload["empty_directories"] = ["manifest.json/ghost"]
    with pytest.raises(ValidationError):
        parse_record(json.dumps(payload).encode())
    a = ArchiveEntry(path="a", size=0, sha256="0" * 64)
    b = ArchiveEntry(path="a/b", size=0, sha256="0" * 64)
    assert content_digest([b, a]) == content_digest([a, b])
    payload.update(
        empty_directories=[],
        entries=[a.model_dump(), b.model_dump()],
        file_count=2,
        content_sha256=content_digest([a, b]),
    )
    with pytest.raises(ValidationError):
        parse_record(json.dumps(payload).encode())
