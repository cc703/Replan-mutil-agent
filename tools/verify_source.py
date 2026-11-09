from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast

CANONICAL = {
    "docs/source/design_v2.original.md",
    "docs/source/codex_spec_v1.1.original.md",
    "docs/source/p0_claude_plan_v001.original.md",
}


def positive(value: Any) -> bool:
    return type(value) is int and value > 0


def digest(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def validate_entries(manifest: Any) -> list[dict[str, Any]]:
    """Validate source metadata and return entries; reject malformed or incomplete manifests."""
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
        raise ValueError("files must be a list")
    entries = manifest["files"]
    if len(entries) != len(CANONICAL) or any(not isinstance(e, dict) for e in entries):
        raise ValueError("expected exactly three source entries")
    names = [e.get("path") for e in entries]
    if any(not isinstance(n, str) for n in names) or set(names) != CANONICAL:
        raise ValueError("source paths must be the three distinct canonical paths")
    for entry in entries:
        for key in ("original_name", "encoding", "newline", "source", "verified_at"):
            if not isinstance(entry.get(key), str) or not entry[key]:
                raise ValueError(f"invalid {key}")
        if not positive(entry.get("bytes")) or not positive(entry.get("lines")):
            raise ValueError("invalid source size or line count")
        if not digest(entry.get("sha256")):
            raise ValueError("invalid source sha256")
        batches = entry.get("batches")
        if not isinstance(batches, list) or not batches:
            raise ValueError("batches must be a nonempty list")
        next_line = 1
        total_bytes = 0
        for batch in batches:
            if not isinstance(batch, dict):
                raise ValueError("invalid batch")
            start, end, size = batch.get("start"), batch.get("end"), batch.get("bytes")
            if not all(positive(x) for x in (start, end, size)):
                raise ValueError("invalid batch numbers")
            start, end, size = cast(int, start), cast(int, end), cast(int, size)
            if start != next_line or end < start or end > entry["lines"]:
                raise ValueError("batches must cover lines in order without gaps or overlap")
            if size < end - start + 1 or size > entry["bytes"] or not digest(batch.get("sha256")):
                raise ValueError("invalid batch size or sha256")
            next_line = end + 1
            total_bytes += size
        if next_line != entry["lines"] + 1 or total_bytes != entry["bytes"]:
            raise ValueError("batches must cover all lines and bytes")
    return cast(list[dict[str, Any]], entries)


def verify(root: Path) -> bool:
    """Verify manifest structure and source bytes under root; return overall success."""
    try:
        root = root.resolve()
        source = (root / "docs/source").resolve()
        if not source.is_relative_to(root):
            raise ValueError("source directory escapes root")
        manifest_path = (source / "manifest.json").resolve()
        if not manifest_path.is_relative_to(source):
            raise ValueError("manifest escapes source directory")
        entries = validate_entries(json.loads(manifest_path.read_text(encoding="utf-8")))
        good = True
        for entry in entries:
            name = entry["path"]
            try:
                path = (root / name).resolve()
                if not path.is_relative_to(source) or not path.is_relative_to(root):
                    raise ValueError("source path escapes source directory")
                data = path.read_bytes()
                lines = data.splitlines(keepends=True)
                checks = {
                    "bytes": len(data) == entry["bytes"],
                    "lines": len(lines) == entry["lines"],
                    "sha256": hashlib.sha256(data).hexdigest() == entry["sha256"],
                    "encoding": not data.startswith(b"\xef\xbb\xbf")
                    and bool(data.decode("utf-8") or not data),
                    "LF": b"\r" not in data and data.endswith(b"\n"),
                }
                for batch in entry["batches"]:
                    part = b"".join(lines[batch["start"] - 1 : batch["end"]])
                    checks[f"batch {batch['start']}-{batch['end']}"] = (
                        len(part) == batch["bytes"]
                        and hashlib.sha256(part).hexdigest() == batch["sha256"]
                    )
                for label, ok in checks.items():
                    print(f"{name}: {label}: {'PASS' if ok else 'FAIL'}")
                    good = good and ok
            except (OSError, UnicodeError, ValueError) as exc:
                print(f"{name}: FAIL: {exc}")
                good = False
        return good
    except (OSError, ValueError, TypeError) as exc:
        print(f"manifest: FAIL: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    return 0 if verify(parser.parse_args().root) else 1


if __name__ == "__main__":
    raise SystemExit(main())
