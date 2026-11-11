"""Creation and lifecycle of immutable-on-completion artifact runs."""

import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from .errors import ArtifactError, RunClosedError, UnsafePathError
from .manifest import GitInfo, Manifest, read_manifest
from .paths import _is_link, atomic_write, check_chain, inside, mkdir_chain, relative_path
from .provenance import config_bytes, git_info

if TYPE_CHECKING:
    from .cache_area import CacheArea


Scalar = str | int | float | bool | None


def _clock() -> datetime:
    return datetime.now(timezone.utc)


def _time(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("time must be aware")
    return value.astimezone(timezone.utc)


def _serialize(manifest: Manifest) -> bytes:
    return (manifest.model_dump_json(indent=2) + "\n").encode("utf-8")


def _files(directory: Path) -> list[Path]:
    result: list[Path] = []
    for entry in os.scandir(directory):
        path = Path(entry.path)
        if _is_link(path):
            raise UnsafePathError(f"link in run: {path}")
        if entry.is_dir(follow_symlinks=False):
            result.extend(_files(path))
        elif entry.is_file(follow_symlinks=False):
            result.append(path)
        else:
            raise UnsafePathError(f"non-regular file: {path}")
    return result


class ArtifactStore:
    """Create runs beneath root; clock must return aware datetimes.

    Creates root when absent and rejects linked path components with UnsafePathError.
    """

    def __init__(
        self, root: str | Path = "artifacts", *, clock: Callable[[], datetime] | None = None
    ) -> None:
        check_chain(Path(root))
        self.root = Path(os.path.abspath(root))
        check_chain(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        check_chain(self.root)
        self.clock = clock or _clock

    def cache(self, namespace: Literal["instances"]) -> "CacheArea":
        """Bind the ``instances`` namespace beneath this store without creating it.

        Returns a CacheArea; other namespaces raise ValueError. Its get and put
        methods check paths when used, and put publishes read-only files without
        replacing an existing entry. This method does not modify the store root.
        """
        from .cache_area import CacheArea

        return CacheArea(self.root, namespace)

    def new_run(
        self,
        kind: str,
        name: str,
        tag: str,
        *,
        command: str | None = None,
        config: bytes | str | Path | None = None,
        seeds: Sequence[int] = (),
        versions: Mapping[str, str] | None = None,
        inputs: Sequence[str] = (),
        metadata: Mapping[str, Scalar] | None = None,
        git: GitInfo | None = None,
    ) -> "Run":
        """Create and return a running run without overwriting an existing run.

        Kind, name and tag must satisfy the run naming rules. Config preserves its
        bytes; sequences and mappings are copied, not modified. The caller owns
        redaction and supplied Git evidence. Invalid inputs raise ValueError or a
        Pydantic validation error; unavailable Git raises ArtifactError.
        """
        if kind not in {"experiment", "sim", "agent_eval"}:
            raise ValueError("invalid kind")
        if not re.fullmatch(r"[a-z0-9]+(?:[_-][a-z0-9]+)*", name) or len(name) > 64:
            raise ValueError("invalid name")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", tag) or len(tag) > 40:
            raise ValueError("invalid tag")
        stamp = _time(self.clock())
        evidence = (
            GitInfo.model_validate({"commit": git.commit, "dirty": git.dirty})
            if git is not None
            else git_info(self.root)
        )
        data = config_bytes(config)
        versions_copy = dict(versions or {})
        if "python" in versions_copy and versions_copy["python"] != platform.python_version():
            raise ValueError("python version conflicts with runtime")
        versions_copy["python"] = platform.python_version()
        parent = self.root / "runs" / kind / name
        mkdir_chain(self.root, parent)
        prefix = f"{stamp:%Y%m%d-%H%M%S}_{evidence.commit[:7]}_{tag}"
        for number in range(1, 100):
            run_id = prefix if number == 1 else f"{prefix}-{number}"
            directory = parent / run_id
            try:
                directory.mkdir()
                break
            except FileExistsError:
                continue
        else:
            raise ArtifactError("run identifiers exhausted")
        try:
            manifest = Manifest(
                run_id=run_id,
                kind=cast(Literal["experiment", "sim", "agent_eval"], kind),
                name=name,
                status="running",
                started_at=stamp,
                ended_at=None,
                command=command if command is not None else shlex.join(sys.argv),
                git=evidence,
                config_sha256=hashlib.sha256(data).hexdigest(),
                seeds=list(seeds),
                versions=versions_copy,
                inputs=list(inputs),
                outputs=[],
                metadata=dict(metadata or {}),
            )
            inside(self.root, directory)
            (directory / "config.yaml").write_bytes(data)
            atomic_write(directory / "manifest.json", _serialize(manifest))
        except BaseException:
            try:
                inside(self.root, directory)
                if directory.is_dir() and not _is_link(directory):
                    shutil.rmtree(directory)
            except (OSError, ArtifactError):
                pass
            raise
        return Run(self.root, directory, clock=self.clock)


class Run:
    """Access run_dir under root; clock returns aware times for finish.

    The directory must match the configured runs layout. Every mutation checks
    the on-disk manifest, rejecting links and terminal states.
    """

    def __init__(
        self, root: Path, run_dir: Path, *, clock: Callable[[], datetime] | None = None
    ) -> None:
        check_chain(root)
        check_chain(run_dir)
        self.root = Path(os.path.abspath(root))
        self.dir = Path(os.path.abspath(run_dir))
        self.clock = clock or _clock

    @property
    def run_id(self) -> str:
        """Return the run directory identifier without reading the manifest."""
        return self.dir.name

    @property
    def manifest(self) -> Manifest:
        """Return a fresh disk-validated manifest or raise ArtifactError."""
        inside(self.root, self.dir)
        manifest = read_manifest(self.dir)
        if self.dir != self.root / "runs" / manifest.kind / manifest.name / manifest.run_id:
            raise ArtifactError("run is outside the configured runs layout")
        return manifest

    def _running(self) -> Manifest:
        manifest = self.manifest
        if manifest.status != "running":
            raise RunClosedError("run is closed")
        for path in self.dir.iterdir():
            if path.name.startswith((".manifest-", ".part-")):
                if _is_link(path) or not path.is_file():
                    raise UnsafePathError("unsafe temporary file")
                try:
                    os.chmod(path, 0o666)
                    path.unlink()
                except OSError as exc:
                    raise ArtifactError("cannot remove temporary file") from exc
        return manifest

    def path(self, rel: str) -> Path:
        """Return rel under the run, creating only its parent directories.

        Reject unsafe paths and links with UnsafePathError, or closed runs with
        RunClosedError. This does not create the target file.
        """
        self._running()
        target = self.dir / relative_path(rel)
        mkdir_chain(self.root, target.parent)
        inside(self.root, target)
        return target

    def write_json(self, rel: str, obj: object) -> Path:
        """Write obj as UTF-8 JSON at rel and return its path without mutating obj.

        Reject closed runs, unsafe paths, non-JSON values and non-finite numbers;
        failed serialization or atomic replacement preserves any existing file.
        """
        self._running()
        data = (json.dumps(obj, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode(
            "utf-8"
        )
        target = self.path(rel)
        atomic_write(target, data)
        return target

    def finish(
        self,
        status: Literal["completed", "failed", "partial"],
        *,
        outputs: Sequence[str] = (),
        ended_at: datetime | None = None,
    ) -> Manifest:
        """Publish and return a completed, failed or partial manifest.

        Outputs must be distinct existing safe ordinary files. ended_at, or clock
        when omitted, must be aware and no earlier than started_at. Inputs are not
        modified. Invalid state, paths and values raise the corresponding exception;
        a failed publication leaves the manifest running and files may be readonly.
        """
        current = self._running()
        if status not in {"completed", "failed", "partial"}:
            raise ValueError("invalid final status")
        end = _time(ended_at if ended_at is not None else self.clock())
        paths = list(outputs)
        if len(set(paths)) != len(paths):
            raise ValueError("duplicate output")
        for rel in paths:
            path = self.dir / relative_path(rel)
            inside(self.root, path)
            if not path.is_file() or _is_link(path):
                raise ArtifactError("output is not a regular file")
        inside(self.root, self.dir)
        files = _files(self.dir)
        payload = current.model_dump()
        payload.update(status=status, ended_at=end, outputs=paths)
        terminal = Manifest.model_validate(payload)
        data = _serialize(terminal)
        for path in files:
            if path != self.dir / "manifest.json":
                os.chmod(path, 0o444)
        atomic_write(self.dir / "manifest.json", data, readonly=True)
        return terminal
