"""Independent archive verification and provenance mismatch tests."""

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scheduler_core.io.archive import ArchivePlan
from scheduler_core.io.archive_record import ArchiveEntry, content_digest
from scheduler_core.io.artifacts import ArtifactStore
from scheduler_core.io.errors import ArtifactError
from scheduler_core.io.manifest import GitInfo


def make_archive(tmp_path: Path) -> tuple[ArtifactStore, ArchivePlan]:
    root = tmp_path / "root"
    root.mkdir()
    now = datetime(2026, 11, 11, tzinfo=timezone.utc)
    store = ArtifactStore.open_existing(root, clock=lambda: now)
    run = store.new_run("sim", "sample", "test", git=GitInfo(commit="abcdef1", dirty=False))
    run.write_json("output.json", {"ok": True})
    run.finish("completed", outputs=["output.json"])
    plan = store.maintenance().plan_archive(run.run_id)
    store.maintenance().archive(plan, now)
    return store, plan


def rewrite(plan: ArchivePlan, mutation: str) -> None:
    zip_path = plan.zip_path
    sidecar = plan.sidecar_path
    zip_path.chmod(0o666)
    sidecar.chmod(0o666)
    record = json.loads(sidecar.read_bytes())
    with zipfile.ZipFile(zip_path) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    manifest_name = f"{record['run_id']}/manifest.json"
    manifest = json.loads(members[manifest_name])
    if mutation == "git":
        manifest["git"]["dirty"] = not manifest["git"]["dirty"]
    elif mutation == "identity":
        manifest["name"] = "other"
    elif mutation == "config":
        manifest["config_sha256"] = "0" * 64
    else:
        manifest["outputs"] = ["missing.json"]
    members[manifest_name] = json.dumps(manifest).encode()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(members.items()):
            archive.writestr(name, data)
    entries = [
        ArchiveEntry(
            path=name.split("/", 1)[1], size=len(data), sha256=hashlib.sha256(data).hexdigest()
        )
        for name, data in sorted(members.items())
    ]
    record["entries"] = [entry.model_dump() for entry in entries]
    record["content_sha256"] = content_digest(entries)
    record["source_manifest_sha256"] = hashlib.sha256(members[manifest_name]).hexdigest()
    zipped = zip_path.read_bytes()
    record["archive_sha256"] = hashlib.sha256(zipped).hexdigest()
    record["archive_bytes"] = len(zipped)
    sidecar.write_text(json.dumps(record), encoding="utf-8")


@pytest.mark.parametrize("mutation", ["git", "identity", "config", "outputs"])
def test_manifest_mismatch_rejected(tmp_path: Path, mutation: str) -> None:
    store, plan = make_archive(tmp_path)
    rewrite(plan, mutation)
    with pytest.raises(ArtifactError, match="verification failed"):
        store.maintenance().verify_archive(plan.run_id)


@pytest.mark.parametrize("change", ["missing", "extra", "duplicate", "truncated"])
def test_zip_member_changes_rejected(tmp_path: Path, change: str) -> None:
    store, plan = make_archive(tmp_path)
    zip_path = plan.zip_path
    sidecar = plan.sidecar_path
    zip_path.chmod(0o666)
    sidecar.chmod(0o666)
    record = json.loads(sidecar.read_bytes())
    if change == "truncated":
        zip_path.write_bytes(zip_path.read_bytes()[:-15])
    else:
        with zipfile.ZipFile(zip_path) as archive:
            members = [(name, archive.read(name)) for name in archive.namelist()]
        if change == "missing":
            members.pop()
        elif change == "extra":
            members.append((f"{plan.run_id}/extra.txt", b"extra"))
        else:
            members.append(members[0])
        with zipfile.ZipFile(zip_path, "w") as archive:
            for index, (name, data) in enumerate(members):
                if change == "duplicate" and index == len(members) - 1:
                    with pytest.warns(UserWarning, match="Duplicate name"):
                        archive.writestr(name, data)
                else:
                    archive.writestr(name, data)
    data = zip_path.read_bytes()
    record["archive_sha256"] = hashlib.sha256(data).hexdigest()
    record["archive_bytes"] = len(data)
    sidecar.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ArtifactError, match="verification failed"):
        store.maintenance().verify_archive(plan.run_id)


def test_self_consistent_rewrite_can_pass(tmp_path: Path) -> None:
    store, plan = make_archive(tmp_path)
    zip_path, sidecar = plan.zip_path, plan.sidecar_path
    zip_path.chmod(0o666)
    sidecar.chmod(0o666)
    record = json.loads(sidecar.read_bytes())
    with zipfile.ZipFile(zip_path) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    members[f"{plan.run_id}/extra.txt"] = b"rewritten"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(members.items()):
            archive.writestr(name, data)
    entries = [
        ArchiveEntry(
            path=name.split("/", 1)[1], size=len(data), sha256=hashlib.sha256(data).hexdigest()
        )
        for name, data in sorted(members.items())
    ]
    zipped = zip_path.read_bytes()
    record.update(
        entries=[entry.model_dump() for entry in entries],
        file_count=len(entries),
        content_sha256=content_digest(entries),
        archive_sha256=hashlib.sha256(zipped).hexdigest(),
        archive_bytes=len(zipped),
    )
    sidecar.write_text(json.dumps(record), encoding="utf-8")
    assert store.maintenance().verify_archive(plan.run_id).valid


@pytest.mark.parametrize("mutation", ["method", "encrypted", "corrupt", "version"])
def test_invalid_zip_encoding_cli_rejects_without_traceback(tmp_path: Path, mutation: str) -> None:
    import struct
    import subprocess
    import sys
    import zlib

    store, plan = make_archive(tmp_path)
    assert store.maintenance().verify_archive(plan.run_id).valid
    plan.zip_path.chmod(0o666)
    plan.sidecar_path.chmod(0o666)
    with zipfile.ZipFile(plan.zip_path) as archive:
        info = archive.infolist()[0]
        central = archive.start_dir
        local = info.header_offset
    payload = bytearray(plan.zip_path.read_bytes())
    assert payload[local : local + 4] == b"PK\x03\x04"
    assert payload[central : central + 4] == b"PK\x01\x02"
    if mutation == "method":
        struct.pack_into("<H", payload, local + 8, 99)
        struct.pack_into("<H", payload, central + 10, 99)
    elif mutation == "encrypted":
        struct.pack_into("<H", payload, local + 6, info.flag_bits | 1)
        struct.pack_into("<H", payload, central + 8, info.flag_bits | 1)
    elif mutation == "version":
        struct.pack_into("<H", payload, central + 6, 99)
    else:
        filename_length, extra_length = struct.unpack_from("<HH", payload, local + 26)
        data_start = local + 30 + filename_length + extra_length
        payload[data_start] = 0xFF
    plan.zip_path.write_bytes(payload)
    exception_type = {
        "method": NotImplementedError,
        "encrypted": RuntimeError,
        "corrupt": zlib.error,
        "version": NotImplementedError,
    }[mutation]
    with pytest.raises(exception_type):
        with zipfile.ZipFile(plan.zip_path) as malformed:
            malformed.read(malformed.namelist()[0])
    record = json.loads(plan.sidecar_path.read_bytes())
    record["archive_sha256"] = hashlib.sha256(payload).hexdigest()
    record["archive_bytes"] = len(payload)
    plan.sidecar_path.write_text(json.dumps(record), encoding="utf-8")
    script = Path(__file__).resolve().parents[3] / "tools" / "archive_run.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--root",
            str(store.root),
            "--run",
            plan.run_id,
            "--verify",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 3
    assert json.loads(result.stderr)["error"] == "archive verification failed"
    assert "Traceback" not in result.stderr
