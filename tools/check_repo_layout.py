"""Check tracked and non-ignored files, plus local run manifests, without dependencies."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import tomllib
from typing import Any
import xml.etree.ElementTree as ET

DEFAULT_RULES = Path(__file__).with_name("layout_rules.toml")


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a read-only Git command in the selected repository."""
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def load_rules(path: Path = DEFAULT_RULES) -> dict[str, Any]:
    """Load the authoritative TOML rules."""
    with path.open("rb") as stream:
        return tomllib.load(stream)


def check(root: Path, rules: dict[str, Any] | None = None) -> list[dict[str, str]]:
    """Return violations; generated runs are inspected even when Git ignores them."""
    root = root.resolve()
    rules = load_rules() if rules is None else rules
    exceptions = rules.get("exceptions", [])
    if not isinstance(exceptions, list):
        raise ValueError("exceptions must be an array of scoped rule registrations")
    for exception in exceptions:
        if not isinstance(exception, dict):
            raise ValueError("Each exception must be an object")
        scope = exception.get("scope")
        pattern = exception.get("pattern")
        reason = exception.get("reason")
        if (
            not isinstance(scope, str)
            or not scope.endswith("/")
            or scope.startswith("/")
            or any(part in {"", ".", ".."} for part in scope[:-1].split("/"))
            or any(char in scope for char in "*?[]\\:")
        ):
            raise ValueError("Exception scope must be a non-global fixed relative directory prefix")
        if exception.get("rule") != "R-naming" or exception.get("target") not in {
            "path",
            "filename",
        }:
            raise ValueError("Exception must target R-naming and path or filename")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Exception requires a non-empty reason")
        if not isinstance(pattern, str) or not pattern.startswith("^") or not pattern.endswith("$"):
            raise ValueError("Exception pattern must be an anchored regex")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"Invalid exception regex: {exc}") from exc
    errors: list[dict[str, str]] = []

    def error(rule: str, path: str, reason: str) -> None:
        errors.append({"rule": rule, "path": path, "reason": reason})

    listing = git(root, "ls-files", "-co", "--exclude-standard", "-z")
    if listing.returncode:
        raise ValueError(f"Git enumeration failed: {listing.stderr.strip()}")
    tracked_result = git(root, "ls-files", "-z")
    tracked = set(tracked_result.stdout.split("\0"))
    files = sorted(set(listing.stdout.split("\0")) - {""})
    local_only = {probe.removesuffix("/probe") for probe in rules["ignore"]["probes"]}
    for name in tracked - {""}:
        if any(part in local_only for part in Path(name).parts):
            error("R-ignore", name, "Local environment, secret, or cache must not be tracked")
    # Source directories must stay free of generated data even when *.log is ignored.
    for source_root in rules["generated"]["source_roots"]:
        for directory, children, filenames in os.walk(root / source_root, followlinks=False):
            children[:] = [child for child in children if child not in local_only]
            for filename in filenames:
                path = Path(directory) / filename
                name = path.relative_to(root).as_posix()
                if (
                    name not in files
                    and not any(
                        name.startswith(prefix) for prefix in rules["generated"]["config_prefixes"]
                    )
                    and path.suffix.lower() in rules["generated"]["forbidden_extensions"]
                ):
                    error("R-generated", name, "Ignored generated data left in source directory")
    for name in files:
        path = root / name
        parts = Path(name).parts
        if parts[0] not in rules["root"]["allowed"]:
            error("R-root", name, "Root entry is not allowed")
        if not path.exists():  # A staged or unstaged deletion has no current content.
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            error("R-naming", name, "Symlink or path outside repository is forbidden")
            continue
        if not path.is_file():
            continue
        if name.startswith("artifacts/"):
            if name in tracked and name not in rules["artifacts"]["tracked_allowed"]:
                error("R-artifacts", name, "Generated artifact must not be tracked")
            if name not in rules["artifacts"]["tracked_allowed"]:
                error("R-artifacts", name, "Generated artifact must be ignored")
        for i, part in enumerate(parts):
            conventional = part in rules["naming"]["conventional"]
            root_file = len(parts) == 1 and part in rules["root"]["allowed"]
            registered = any(
                name.startswith(entry["scope"])
                and (
                    (entry["target"] == "path" and re.fullmatch(entry["pattern"], name))
                    or (
                        entry["target"] == "filename"
                        and i == len(parts) - 1
                        and re.fullmatch(entry["pattern"], part)
                    )
                )
                for entry in exceptions
            )
            if not (
                conventional
                or root_file
                or registered
                or re.fullmatch(rules["naming"]["pattern"], part)
            ):
                error("R-naming", name, f"Invalid filename component: {part}")
                break
        if (
            path.stat().st_size > rules["size"]["max_bytes"]
            and name not in rules["size"]["exceptions"]
        ):
            error("R-size", name, "File exceeds maximum tracked size")
        source = parts[0] in rules["generated"]["source_roots"]
        config = any(name.startswith(prefix) for prefix in rules["generated"]["config_prefixes"])
        suffix = path.suffix.lower()
        if source and not config and suffix in rules["generated"]["forbidden_extensions"]:
            error("R-generated", name, "Generated data in source directory")
        if (
            source
            and suffix in rules["generated"]["image_extensions"]
            and not any(name.startswith(prefix) for prefix in rules["generated"]["asset_prefixes"])
        ):
            error("R-generated", name, "Image outside approved static asset directories")
        if suffix in rules["magic"]["extensions"]:
            raw = path.read_bytes()
            valid = True
            if suffix == ".png":
                valid = raw.startswith(b"\x89PNG\r\n\x1a\n")
            elif suffix == ".pdf":
                valid = raw.startswith(b"%PDF-")
            else:
                try:
                    valid = ET.fromstring(raw).tag in {"svg", "{http://www.w3.org/2000/svg}svg"}
                except ET.ParseError:
                    valid = False
            if not valid:
                error("R-magic", name, "Content does not match declared image format")
    for probe in rules["ignore"]["probes"]:
        if git(root, "check-ignore", "--no-index", "-q", "--", probe).returncode != 0:
            error("R-ignore", probe, "Required local path is not ignored")
    runs = root / "artifacts" / "runs"
    if runs.exists():
        for run in sorted(runs.glob("*/*/*")):
            relative = run.relative_to(root).as_posix()
            if run.is_symlink() or not run.resolve().is_relative_to(root):
                error("R-manifest", relative, "Run path must stay inside repository")
                continue
            if not run.is_dir():
                error("R-manifest", relative, "Run entry must be a directory")
                continue
            try:
                manifest_path = run / "manifest.json"
                if manifest_path.is_symlink():
                    raise ValueError("Manifest cannot be a symlink")
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if not isinstance(manifest, dict):
                    raise ValueError("Manifest must be an object")
                missing = set(rules["manifest"]["required"]) - manifest.keys()
                if missing:
                    raise ValueError(f"Missing manifest fields: {sorted(missing)}")
                if manifest["status"] not in rules["manifest"]["statuses"]:
                    raise ValueError("Invalid run status")
                if manifest["kind"] not in rules["manifest"]["kinds"]:
                    raise ValueError("Invalid run kind")
                if (manifest["kind"], manifest["name"], manifest["run_id"]) != tuple(
                    run.parts[-3:]
                ):
                    raise ValueError("Manifest identity differs from directory")
                if not isinstance(manifest["run_id"], str) or not re.fullmatch(
                    rules["manifest"]["run_id_pattern"], manifest["run_id"]
                ):
                    raise ValueError("Invalid run_id format")
                if (
                    not isinstance(manifest["git"], dict)
                    or not {"commit", "dirty"} <= manifest["git"].keys()
                ):
                    raise ValueError("Manifest git must contain commit and dirty")
                if manifest["status"] == "completed" and not manifest["ended_at"]:
                    raise ValueError("Completed run requires ended_at")
                for field in ("started_at", "ended_at"):
                    value = manifest[field]
                    if field == "ended_at" and value is None:
                        continue
                    if (
                        not isinstance(value, str)
                        or datetime.fromisoformat(value.replace("Z", "+00:00")).utcoffset() is None
                    ):
                        raise ValueError(f"{field} requires an ISO 8601 timestamp with timezone")
                if not isinstance(manifest["git"]["dirty"], bool):
                    raise ValueError("git.dirty requires a boolean")
                for label, value in (
                    ("git.commit", manifest["git"]["commit"]),
                    ("command", manifest["command"]),
                ):
                    if not isinstance(value, str) or not value.strip():
                        raise ValueError(f"{label} requires a non-empty string")
                if not isinstance(manifest["seeds"], list) or any(
                    not isinstance(seed, int) or isinstance(seed, bool)
                    for seed in manifest["seeds"]
                ):
                    raise ValueError("seeds requires an integer array")
                if not isinstance(manifest["versions"], dict):
                    raise ValueError("versions requires an object")
                if not isinstance(manifest["config_sha256"], str) or not re.fullmatch(
                    r"[a-f0-9]{64}", manifest["config_sha256"]
                ):
                    raise ValueError("config_sha256 requires 64 lowercase hex digits")
                outputs = manifest.get("outputs", [])
                if not isinstance(outputs, list) or any(
                    not isinstance(item, str) for item in outputs
                ):
                    raise ValueError("outputs requires an array of strings")
                for output in outputs:
                    if (
                        not isinstance(output, str)
                        or "\\" in output
                        or not (run / output).resolve().is_relative_to(run.resolve())
                    ):
                        raise ValueError("Output paths must stay inside the run directory")
            except (OSError, ValueError, TypeError, KeyError) as exc:
                error("R-manifest", relative, str(exc))
    return errors


def main() -> int:
    """Expose a human-readable or JSON CLI with nonzero failure status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        errors = check(args.root)
    except (OSError, ValueError, KeyError) as exc:
        errors = [{"rule": "R-config", "path": str(args.root), "reason": str(exc)}]
    print(
        json.dumps(errors, ensure_ascii=False)
        if args.format == "json"
        else "\n".join(f"{e['rule']} {e['path']}: {e['reason']}" for e in errors) or "Layout: PASS"
    )
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
