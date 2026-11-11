"""Read-only validation of an archive and its internal provenance."""

import hashlib
import json
import re
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from .archive_record import ArchiveRecord, content_digest, parse_record
from .artifacts import ArtifactStore
from .errors import ArtifactError
from .manifest import Manifest, _reject_constant, _unique_pairs
from .paths import check_chain, relative_path


def _stream_digest(stream: IO[bytes]) -> str:
    digest = hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class VerifyResult:
    """Identity and validation result for one archive."""

    run_id: str
    kind: str
    name: str
    valid: bool
    reason: str


def locate(
    root: Path, namespace: str, run_id: str, kind: str | None, name: str | None, suffix: str = ""
) -> Path:
    """Locate exactly one safe identity under a storage namespace."""
    for value in (run_id, kind, name):
        if value is not None:
            relative_path(value, reserved=False)
            if "/" in value:
                raise ValueError("identity must be one component")
    if kind is not None and kind not in {"experiment", "sim", "agent_eval"}:
        raise ValueError("invalid kind")
    base = root / namespace
    check_chain(base)
    matches = []
    if base.is_dir():
        for k in sorted(base.iterdir()):
            check_chain(k)
            if (
                not k.is_dir()
                or k.name not in {"experiment", "sim", "agent_eval"}
                or (kind and k.name != kind)
            ):
                continue
            for n in sorted(k.iterdir()):
                check_chain(n)
                if not n.is_dir() or (name and n.name != name):
                    continue
                candidate = n / (run_id + suffix)
                check_chain(candidate)
                if candidate.exists():
                    matches.append(candidate)
    if len(matches) != 1:
        raise ArtifactError("run identity missing or ambiguous")
    return matches[0]


def _verify_members(archive: zipfile.ZipFile, record: ArchiveRecord, run_id: str) -> None:
    names = archive.namelist()
    expected = [f"{run_id}/{entry.path}" for entry in record.entries]
    if names != expected or len(set(names)) != len(names):
        raise ValueError("archive members mismatch")
    for info in archive.infolist():
        if info.compress_type != zipfile.ZIP_DEFLATED or info.flag_bits & (1 | 32 | 64):
            raise ValueError("unsupported archive member format")
    if archive.testzip() is not None:
        raise ValueError("archive members mismatch")
    for entry, member in zip(record.entries, names, strict=True):
        with archive.open(member) as stream:
            digest = _stream_digest(stream)
        if archive.getinfo(member).file_size != entry.size or digest != entry.sha256:
            raise ValueError("member digest mismatch")
    manifest_bytes = archive.read(f"{run_id}/manifest.json")
    if hashlib.sha256(manifest_bytes).hexdigest() != record.source_manifest_sha256:
        raise ValueError("manifest digest mismatch")
    json.loads(
        manifest_bytes.decode("utf-8"),
        object_pairs_hook=_unique_pairs,
        parse_constant=_reject_constant,
    )
    manifest = Manifest.model_validate_json(manifest_bytes)
    pattern = (
        manifest.started_at.strftime("%Y%m%d-%H%M%S_")
        + manifest.git.commit[:7]
        + r"_[a-z0-9]+(?:-[a-z0-9]+)*"
    )
    if (
        manifest.run_id,
        manifest.kind,
        manifest.name,
        manifest.status,
        manifest.git.commit,
        manifest.git.dirty,
    ) != (
        record.run_id,
        record.kind,
        record.name,
        record.status,
        record.git_commit,
        record.git_dirty,
    ) or not re.fullmatch(pattern, run_id):
        raise ValueError("manifest identity mismatch")
    if hashlib.sha256(archive.read(f"{run_id}/config.yaml")).hexdigest() != manifest.config_sha256:
        raise ValueError("config mismatch")
    if any(f"{run_id}/{output}" not in names for output in manifest.outputs):
        raise ValueError("output missing")
    if content_digest(record.entries) != record.content_sha256:
        raise ValueError("content digest mismatch")


def verify_archive(
    store: ArtifactStore, run_id: str, kind: str | None = None, name: str | None = None
) -> VerifyResult:
    """Verify archive identity and contents without source access or extraction.

    Invalid or ambiguous paths and inconsistent content raise ArtifactError;
    success returns an immutable result. This does not authenticate the archive.
    """
    root = ArtifactStore.open_existing(store.root, clock=store.clock).root
    sidecar = locate(root, "archive", run_id, kind, name, ".archive.json")
    zip_path = sidecar.with_name(run_id + ".zip")
    check_chain(zip_path)
    try:
        record = parse_record(sidecar.read_bytes())
        if (record.run_id, record.kind, record.name) != (
            run_id,
            sidecar.parent.parent.name,
            sidecar.parent.name,
        ):
            raise ValueError("sidecar identity mismatch")
        with zip_path.open("rb") as stream:
            digest = _stream_digest(stream)
        if zip_path.stat().st_size != record.archive_bytes or digest != record.archive_sha256:
            raise ValueError("archive digest mismatch")
        with zipfile.ZipFile(zip_path) as archive:
            _verify_members(archive, record, run_id)
    except (
        OSError,
        ValueError,
        KeyError,
        EOFError,
        NotImplementedError,
        zlib.error,
        zipfile.BadZipFile,
    ) as exc:
        raise ArtifactError("archive verification failed") from exc
    return VerifyResult(run_id, record.kind, record.name, True, "OK")
