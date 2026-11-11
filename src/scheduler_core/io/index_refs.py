"""Fail-closed parsing of result index references."""

import re
import stat
from dataclasses import dataclass
from pathlib import Path

from .errors import ArtifactError
from .paths import _is_link, check_chain, relative_path


@dataclass(frozen=True)
class IndexReferences:
    """Literal index content and whether the index was absent."""

    text: str
    absent: bool

    def protects(self, kind: str, name: str, run_id: str) -> bool:
        """Conservatively match complete identifiers and name-level paths."""
        return run_id in self.text or f"artifacts/runs/{kind}/{name}" in self.text


def read_index(path: Path, run_ids: set[str]) -> IndexReferences:
    """Read and validate every literal artifact run path or reject deletion."""
    try:
        check_chain(path)
        try:
            info = path.lstat()
        except FileNotFoundError:
            return IndexReferences("", True)
        if _is_link(path) or not stat.S_ISREG(info.st_mode) or info.st_size > 1048576:
            raise ValueError("unsafe index")
        raw = path.read_bytes()
        if len(raw) > 1048576 or b"\0" in raw:
            raise ValueError("invalid index bytes")
        text = raw.decode("utf-8-sig").replace("\\", "/")
        if re.search(r"`[^`]*artifacts/runs/[^`]*\n[^`]*`", text):
            raise ValueError("multiline quoted index path")
        for match in re.finditer(r"artifacts/runs/([^\s<>()\[\]\"'`]*)", text):
            token = match.group(1)
            parts = token.split("/")
            if len(parts) < 2 or parts[0] not in {"experiment", "sim", "agent_eval"}:
                raise ValueError("invalid index path")
            if not re.fullmatch(r"[a-z0-9]+(?:[_-][a-z0-9]+)*", parts[1]) or len(parts[1]) > 64:
                raise ValueError("invalid index name")
            if len(parts) > 2:
                if parts[2] not in run_ids:
                    raise ValueError("unknown or truncated run id")
                for part in parts[3:]:
                    relative_path(part, reserved=False)
        return IndexReferences(text, False)
    except (OSError, UnicodeError, ValueError, ArtifactError) as exc:
        raise ArtifactError("INDEX_UNREADABLE") from exc
