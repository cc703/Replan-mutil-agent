"""Statically check package import boundaries, including relative imports."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import sys

CORE_ALLOWED = {"ortools", "numpy", "pydantic", "scheduler_core"}
SIM_ALLOWED = CORE_ALLOWED | {"simulator"}


def check(root: Path) -> list[dict[str, str]]:
    """Inspect protected Python packages; absent packages are valid during P0."""
    errors: list[dict[str, str]] = []
    for package, allowed in (("scheduler_core", CORE_ALLOWED), ("simulator", SIM_ALLOWED)):
        folder = root / "src" / package
        for path in sorted(folder.rglob("*.py")):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                errors.append({"rule": "R-import", "path": relative, "reason": "Symlink forbidden"})
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
            except (OSError, SyntaxError) as exc:
                errors.append({"rule": "R-import", "path": relative, "reason": str(exc)})
                continue
            for node in ast.walk(tree):
                modules: list[str] = []
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        parents = list(path.relative_to(root / "src").parts[:-1])
                        if node.level > len(parents):
                            modules = ["INVALID_RELATIVE_IMPORT"]
                        else:
                            base = parents[: len(parents) - node.level + 1]
                            if node.module:
                                base.extend(node.module.split("."))
                            modules = [".".join([*base, alias.name]) for alias in node.names]
                    else:
                        modules = [node.module or ""]
                for module in modules:
                    top = module.split(".")[0]
                    if top not in allowed | sys.stdlib_module_names:
                        errors.append(
                            {
                                "rule": "R-import",
                                "path": relative,
                                "reason": f"line {getattr(node, 'lineno', '?')}: forbidden import {module}",
                            }
                        )
    return errors


def main() -> int:
    """Return zero only if every protected import respects package boundaries."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    errors = check(args.root)
    print(
        json.dumps(errors, ensure_ascii=False)
        if args.format == "json"
        else "\n".join(f"{e['rule']} {e['path']}: {e['reason']}" for e in errors) or "Imports: PASS"
    )
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
