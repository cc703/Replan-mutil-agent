"""Real Git evidence and configuration bytes."""

import subprocess
from pathlib import Path

from .errors import ArtifactError
from .manifest import GitInfo


def git_info(root: Path) -> GitInfo:
    """Read Git commit and dirty state in the repository containing root."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=root, check=True, capture_output=True, text=True
        ).stdout
        return GitInfo(commit=commit, dirty=bool(status))
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        raise ArtifactError("Git evidence unavailable") from exc


def config_bytes(config: bytes | str | Path | None) -> bytes:
    """Return the exact supplied configuration bytes; None denotes empty bytes."""
    if config is None:
        return b""
    if isinstance(config, Path):
        return config.read_bytes()
    if isinstance(config, str):
        return config.encode("utf-8")
    if isinstance(config, bytes):
        return config
    raise TypeError("invalid configuration")
