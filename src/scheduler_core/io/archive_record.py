"""Strict sidecar schema and canonical archive content digest."""

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from .manifest import _reject_constant, _unique_pairs
from .paths import relative_path


class ArchiveEntry(BaseModel):
    """Digest and size of one file in the source run."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    path: StrictStr
    size: StrictInt
    sha256: StrictStr

    @model_validator(mode="after")
    def validate_entry(self) -> "ArchiveEntry":
        relative_path(self.path, reserved=False)
        if self.size < 0 or not re.fullmatch(r"[a-f0-9]{64}", self.sha256):
            raise ValueError("invalid entry")
        return self


def content_digest(entries: list[ArchiveEntry]) -> str:
    """Return the digest of sorted path, size and SHA-256 records."""
    payload = "".join(
        f"{e.path}\0{e.size}\0{e.sha256}\n" for e in sorted(entries, key=lambda entry: entry.path)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ArchiveRecord(BaseModel):
    """Strict archive metadata; integrity is internal, not authentication."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schema_version: Literal[1] = Field(alias="schema")
    tool_version: Literal["c3-1"]
    run_id: StrictStr
    kind: Literal["experiment", "sim", "agent_eval"]
    name: StrictStr
    source_relpath: StrictStr
    status: Literal["completed"]
    source_manifest_sha256: StrictStr
    git_commit: StrictStr
    git_dirty: StrictBool
    archived_at: datetime
    archive_filename: StrictStr
    archive_sha256: StrictStr
    archive_bytes: StrictInt
    file_count: StrictInt
    content_sha256: StrictStr
    entries: list[ArchiveEntry]
    empty_directories: list[StrictStr]

    @field_validator("schema_version", mode="before")
    @classmethod
    def strict_schema(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("schema must be integer 1")
        return value

    @field_validator("archived_at")
    @classmethod
    def utc_time(cls, value: datetime) -> datetime:
        offset = value.utcoffset()
        if value.tzinfo is None or offset is None or offset.total_seconds() != 0:
            raise ValueError("archived_at must be UTC")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_record(self) -> "ArchiveRecord":
        for value in (self.run_id, self.name):
            relative_path(value, reserved=False)
            if "/" in value:
                raise ValueError("identity must be a single component")
        if self.source_relpath != f"runs/{self.kind}/{self.name}/{self.run_id}":
            raise ValueError("source identity mismatch")
        if self.archive_filename != f"{self.run_id}.zip":
            raise ValueError("archive identity mismatch")
        if not re.fullmatch(r"[a-f0-9]{7,40}", self.git_commit):
            raise ValueError("invalid git commit")
        for digest in (self.source_manifest_sha256, self.archive_sha256, self.content_sha256):
            if not re.fullmatch(r"[a-f0-9]{64}", digest):
                raise ValueError("invalid digest")
        paths = [entry.path for entry in self.entries]
        if paths != sorted(set(paths)) or self.file_count != len(paths):
            raise ValueError("invalid entry order or count")
        files = set(paths)
        for path in paths:
            parts = path.split("/")
            if any("/".join(parts[:i]) in files for i in range(1, len(parts))):
                raise ValueError("file ancestor conflict")
        if self.archive_bytes < 0 or self.content_sha256 != content_digest(self.entries):
            raise ValueError("invalid archive size or content digest")
        if self.empty_directories != sorted(set(self.empty_directories)):
            raise ValueError("invalid empty directory order")
        parents: set[str] = set()
        for path in paths:
            parts = path.split("/")
            parents.update("/".join(parts[:i]) for i in range(1, len(parts)))
        empty = set(self.empty_directories)
        for directory in self.empty_directories:
            relative_path(directory, reserved=False)
            parts = directory.split("/")
            ancestors = {"/".join(parts[:i]) for i in range(1, len(parts))}
            if directory in files or directory in parents or ancestors & (files | empty):
                raise ValueError("empty directory conflicts with entries")
        return self


def parse_record(data: bytes) -> ArchiveRecord:
    """Parse strict JSON with duplicate keys and non-finite numbers rejected."""
    json.loads(
        data.decode("utf-8"), object_pairs_hook=_unique_pairs, parse_constant=_reject_constant
    )
    return ArchiveRecord.model_validate_json(data)


def serialize_record(record: ArchiveRecord) -> bytes:
    """Serialize a record in stable UTF-8 JSON with a final newline."""
    return (
        json.dumps(
            record.model_dump(mode="json", by_alias=True),
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")
