"""Checked immutable cache entries stored beneath an artifact root."""

import os
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path

from .cache_publish import publish_noreplace
from .errors import ArtifactError, UnsafePathError
from .paths import _is_link, atomic_write, inside, mkdir_chain, relative_path


class CacheArea:
    """Read and publish small immutable entries under a fixed namespace."""

    def __init__(self, root: Path, namespace: str) -> None:
        """Bind root and the sole supported namespace, ``instances``.

        Does not create or inspect directories; an unsupported namespace raises
        ValueError. The caller supplies a root managed by ArtifactStore.
        """
        if namespace != "instances":
            raise ValueError("unsupported cache namespace")
        self.root = root
        self.parent = root / namespace

    def _entry(self, key: str) -> Path:
        if len(key) > 120 or "/" in key:
            raise UnsafePathError("invalid cache key")
        return self.parent / relative_path(key, reserved=False)

    def get(self, key: str) -> dict[str, bytes] | None:
        """Return filename-to-bytes contents, or None if the entry is absent.

        Key is a safe single path component of at most 120 characters. No
        directories are created. Unsafe paths or links raise UnsafePathError;
        a non-directory entry, more than eight files, or over 64 MiB raises
        ArtifactError. Filesystem read errors can propagate as OSError.
        """
        target = self._entry(key)
        inside(self.root, target)
        if not target.exists():
            return None
        if not target.is_dir():
            raise ArtifactError("cache entry is not a directory")
        result: dict[str, bytes] = {}
        total = 0
        for item in target.iterdir():
            inside(self.root, item)
            relative_path(item.name, reserved=False)
            if _is_link(item) or not item.is_file():
                raise UnsafePathError("unsafe cache entry member")
            if len(result) >= 8:
                raise ArtifactError("too many cache files")
            size = item.stat().st_size
            total += size
            if total > 64 * 1024 * 1024:
                raise ArtifactError("cache entry too large")
            result[item.name] = item.read_bytes()
        return result

    def put(self, key: str, files: Mapping[str, bytes]) -> Path:
        """Publish named byte files and return the entry path, without replacement.

        Key and filenames must be safe single components; key is at most 120
        characters. At most eight files and 64 MiB are accepted. This creates
        the namespace and a temporary stage, writes files read-only, and attempts
        to remove its stage on failure. It does not modify the input mapping.

        Invalid size or contents raise ValueError, unsafe paths UnsafePathError,
        an existing target FileExistsError, and other publication or filesystem
        failures OSError. Platform and race limitations are those of
        ``publish_noreplace``; read-only attributes are not an access-control ACL.
        """
        target = self._entry(key)
        if len(files) > 8 or sum(len(data) for data in files.values()) > 64 * 1024 * 1024:
            raise ValueError("cache files exceed limits")
        for name, data in files.items():
            if "/" in name or not isinstance(data, bytes):
                raise ValueError("invalid cache member")
            relative_path(name, reserved=False)
        mkdir_chain(self.root, self.parent)
        inside(self.root, target)
        stage = Path(tempfile.mkdtemp(prefix="stage-", dir=self.parent))
        try:
            for name, data in files.items():
                atomic_write(stage / name, data, readonly=True)
            inside(self.root, target)
            publish_noreplace(stage, target)
        finally:
            if stage.exists():
                for item in stage.iterdir():
                    os.chmod(item, 0o666)
                shutil.rmtree(stage)
        return target
