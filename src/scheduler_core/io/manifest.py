"""Strict, disk-bound run manifest."""

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from .errors import ArtifactError
from .paths import _is_link, check_chain, relative_path


class GitInfo(BaseModel):
    """Commit and working tree evidence, supplied by caller or Git."""

    model_config = ConfigDict(extra="forbid", strict=True)
    commit: StrictStr
    dirty: StrictBool

    @field_validator("commit")
    @classmethod
    def commit_format(cls, value: str) -> str:
        if not re.fullmatch(r"[a-f0-9]{7,40}", value):
            raise ValueError("invalid commit")
        return value


class Manifest(BaseModel):
    """Validated provenance and lifecycle state for one run."""

    model_config = ConfigDict(extra="forbid", strict=True)
    run_id: StrictStr
    kind: Literal["experiment", "sim", "agent_eval"]
    name: StrictStr
    status: Literal["running", "completed", "failed", "partial"]
    started_at: datetime
    ended_at: datetime | None
    command: StrictStr
    git: GitInfo
    config_sha256: StrictStr
    seeds: list[StrictInt]
    versions: dict[StrictStr, StrictStr]
    inputs: list[StrictStr]
    outputs: list[StrictStr]
    metadata: dict[StrictStr, StrictStr | StrictInt | float | StrictBool | None]

    @field_validator("started_at", "ended_at")
    @classmethod
    def utc_time(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("time must be aware")
            return value.astimezone(timezone.utc)
        return None

    @model_validator(mode="after")
    def consistency(self) -> "Manifest":
        if not re.fullmatch(r"[a-f0-9]{64}", self.config_sha256):
            raise ValueError("invalid config hash")
        if not re.fullmatch(r"[a-z0-9]+(?:[_-][a-z0-9]+)*", self.name) or len(self.name) > 64:
            raise ValueError("invalid name")
        if len(self.command) > 2000 or any(ord(c) < 32 or ord(c) == 127 for c in self.command):
            raise ValueError("invalid command")
        if any(seed < 0 for seed in self.seeds):
            raise ValueError("negative seed")
        if not self.versions.get("python"):
            raise ValueError("python version is required")
        if any(not re.fullmatch(r"[a-z0-9_]+", key) for key in self.metadata):
            raise ValueError("invalid metadata key")
        if any(
            isinstance(value, float) and not math.isfinite(value)
            for value in self.metadata.values()
        ):
            raise ValueError("non-finite metadata")
        for path in self.inputs:
            relative_path(path, reserved=False)
        for path in self.outputs:
            relative_path(path)
        if len(set(self.outputs)) != len(self.outputs):
            raise ValueError("duplicate outputs")
        if self.status == "running":
            if self.ended_at is not None or self.outputs:
                raise ValueError("running state inconsistent")
        elif self.ended_at is None or self.ended_at < self.started_at:
            raise ValueError("terminal state inconsistent")
        return self


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant {value}")


def read_manifest(run_dir: Path) -> Manifest:
    """Return a validated manifest for run_dir without modifying any files.

    Verify strict JSON, directory identity, configuration bytes and output files.
    Invalid content or missing files raise ArtifactError; links raise UnsafePathError.
    """
    try:
        check_chain(run_dir)
        file = run_dir / "manifest.json"
        check_chain(file)
        raw = file.read_bytes()
        decoded = raw.decode("utf-8")
        json.loads(decoded, object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
        manifest = Manifest.model_validate_json(raw)
        pattern = (
            manifest.started_at.strftime("%Y%m%d-%H%M%S_")
            + manifest.git.commit[:7]
            + r"_[a-z0-9]+(?:-[a-z0-9]+)*"
        )
        if (
            run_dir.name != manifest.run_id
            or run_dir.parent.name != manifest.name
            or run_dir.parent.parent.name != manifest.kind
            or not re.fullmatch(pattern, manifest.run_id)
        ):
            raise ValueError("run identity mismatch")
        config = run_dir / "config.yaml"
        check_chain(config)
        if not config.is_file() or _is_link(config):
            raise ValueError("config is not a regular file")
        if hashlib.sha256(config.read_bytes()).hexdigest() != manifest.config_sha256:
            raise ValueError("config hash mismatch")
        for value in manifest.outputs:
            path = run_dir / relative_path(value)
            check_chain(path)
            if not path.is_file() or _is_link(path):
                raise ValueError("invalid output")
        return manifest
    except (OSError, ValueError) as exc:
        raise ArtifactError("invalid run manifest") from exc
