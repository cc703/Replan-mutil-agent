"""Manifest layout contract and dependency boundaries."""

import ast
import tomllib
from pathlib import Path

from scheduler_core.io import Manifest


def test_manifest_covers_machine_required_fields() -> None:
    rules = tomllib.loads(Path("tools/layout_rules.toml").read_text(encoding="utf-8"))
    assert set(rules["manifest"]["required"]) <= set(Manifest.model_fields)


def test_storage_has_no_forbidden_imports() -> None:
    forbidden = ("random", "numpy", "ortools", "scheduler_core.models", "scheduler_core.validate")
    for path in Path("src/scheduler_core/io").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(not alias.name.startswith(forbidden) for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith(forbidden)
