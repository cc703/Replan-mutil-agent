"""P0 check entry point; use the same interpreter that contains the locked dev tools."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def main() -> int:
    """Run every P0 gate and propagate failures; list-tmp never deletes files."""
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-tmp", action="store_true", help="Dry-run listing only")
    args = parser.parse_args()
    if args.list_tmp:
        for path in sorted((root / "artifacts" / "tmp").rglob("*")):
            print(f"DRY-RUN {path.relative_to(root).as_posix()}")
        print("No files deleted. Age-based cleanup is deferred to P1.")
        return 0
    checks = [
        ["tools/check_repo_layout.py"],
        ["tools/check_import_boundaries.py"],
        ["tools/verify_source.py"],
        ["-m", "pytest", "-q", "tests"],
        ["-m", "ruff", "check", "tools", "tests", "src"],
        ["-m", "ruff", "format", "--check", "tools", "tests", "src"],
        ["-m", "mypy", "--explicit-package-bases", "tools", "tests", "src"],
    ]
    failed = False
    for command in checks:
        print("CHECK " + " ".join(command), flush=True)
        result = subprocess.run([sys.executable, *command], cwd=root, check=False)
        failed |= result.returncode != 0
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
