"""Regression tests against independent malformed repositories and run artifacts."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


layout = load("check_repo_layout")
imports = load("check_import_boundaries")


def write(root: Path, path: str, data: str | bytes = "content\n") -> Path:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data.encode() if isinstance(data, str) else data)
    return target


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    write(tmp_path, ".gitignore", (ROOT / ".gitignore").read_text(encoding="utf-8"))
    return tmp_path


def codes(repo: Path) -> set[str]:
    return {error["rule"] for error in layout.check(repo)}


def test_ignored_local_files_and_conventional_names(repo: Path) -> None:
    for name in (".venv/x", ".env", "AGENTS.md", "README.md", "CHANGELOG.md"):
        write(repo, name)
    assert not layout.check(repo)


def test_unknown_root_and_generated_source(repo: Path) -> None:
    write(repo, "notes.txt")
    write(repo, "src/core/results.csv")
    assert {"R-root", "R-generated"} <= codes(repo)


def test_scoped_framework_names(repo: Path) -> None:
    write(repo, "apps/backend/src/main/resources/db/migration/V001__init.sql")
    write(repo, "apps/backend/src/main/java/Scheduler.java")
    write(repo, "apps/frontend/src/TaskView.vue")
    assert not layout.check(repo)
    write(repo, "data/Foo.csv")
    assert "R-naming" in codes(repo)


def test_image_content_not_extension(repo: Path) -> None:
    write(repo, "docs/results/fake.svg", b"\x89PNG\r\n\x1a\nnot-svg")
    assert "R-magic" in codes(repo)
    write(repo, "docs/results/fake.svg", '<?xml version="1.0"?><not_svg/>')
    assert "R-magic" in codes(repo)
    write(repo, "docs/results/fake.svg", '<svg xmlns="http://www.w3.org/2000/svg"/>')
    assert not layout.check(repo)


def test_forced_artifact_tracking(repo: Path) -> None:
    write(repo, "artifacts/raw.csv")
    subprocess.run(["git", "-C", str(repo), "add", "-f", "artifacts/raw.csv"], check=True)
    assert "R-artifacts" in codes(repo)


def test_ignored_run_still_requires_manifest(repo: Path) -> None:
    write(repo, "artifacts/runs/experiment/e2/run1/raw.csv")
    assert "R-manifest" in codes(repo)


def test_manifest_identity_and_completion(repo: Path) -> None:
    run_id = "20261109-120000_abc1234_test"
    name = f"artifacts/runs/experiment/e2/{run_id}/manifest.json"
    manifest = dict(
        run_id=run_id,
        kind="experiment",
        name="e2",
        status="completed",
        started_at="2026-11-09T00:00:00Z",
        ended_at=None,
        command="demo",
        git={"commit": "abc123", "dirty": False},
        config_sha256="0" * 64,
        seeds=[1],
        versions={"python": "3.11"},
    )
    write(repo, name, json.dumps(manifest))
    assert "R-manifest" in codes(repo)
    manifest["ended_at"] = "2026-11-09T00:01:00Z"
    write(repo, name, json.dumps(manifest))
    assert not layout.check(repo)
    for invalid in ("raw.csv", {"raw.csv": True}, [123]):
        manifest["outputs"] = invalid
        write(repo, name, json.dumps(manifest))
        assert "R-manifest" in codes(repo)
    manifest.pop("outputs")
    manifest["command"] = ""
    write(repo, name, json.dumps(manifest))
    assert "R-manifest" in codes(repo)
    manifest["command"] = "demo"
    manifest["git"]["commit"] = ""
    write(repo, name, json.dumps(manifest))
    assert "R-manifest" in codes(repo)
    manifest["git"]["commit"] = "abc123"
    manifest["name"] = "wrong"
    write(repo, name, json.dumps(manifest))
    assert "R-manifest" in codes(repo)


def test_large_files_and_exact_lock_exception(repo: Path) -> None:
    write(repo, "docs/large.md", "x" * 1048577)
    write(repo, "uv.lock", "x" * 1048577)
    failures = layout.check(repo)
    assert [e["path"] for e in failures if e["rule"] == "R-size"] == ["docs/large.md"]


def test_ignore_contract(repo: Path) -> None:
    write(repo, ".gitignore", "artifacts/*\n")
    assert "R-ignore" in codes(repo)


def test_forced_cache_and_ignored_source_log(repo: Path) -> None:
    write(repo, "apps/frontend/node_modules/pkg/index.js")
    subprocess.run(["git", "-C", str(repo), "add", "-f", "apps/frontend/node_modules"], check=True)
    write(repo, "src/core/debug.log")
    assert {"R-ignore", "R-generated"} <= codes(repo)


@pytest.mark.parametrize(
    "path,content",
    [
        ("src/scheduler_core/models.py", "import agent\n"),
        ("src/simulator/engine.py", "from agent import tools\n"),
        ("src/scheduler_core/solver.py", "import fastapi\n"),
        ("src/scheduler_core/solver.py", "from ..agent import tools\n"),
    ],
)
def test_import_rejection(repo: Path, path: str, content: str) -> None:
    write(repo, path, content)
    assert imports.check(repo)


def test_legal_imports_and_absent_src(repo: Path) -> None:
    assert not imports.check(repo)
    write(repo, "src/scheduler_core/models.py", "import pydantic\nfrom . import axis\n")
    write(repo, "src/simulator/engine.py", "from scheduler_core import models\n")
    write(repo, "experiments/run.py", "import agent\n")
    write(repo, "src/scheduler_core/solver.py", "from .baselines import b1_llm\n")
    assert not imports.check(repo)


def test_cli_json_nonzero(repo: Path) -> None:
    write(repo, "notes.txt")
    result = subprocess.run(
        [
            __import__("sys").executable,
            str(ROOT / "tools/check_repo_layout.py"),
            "--root",
            str(repo),
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert any(e["rule"] == "R-root" for e in json.loads(result.stdout))


def test_registered_exact_naming_exception(repo: Path) -> None:
    write(repo, "data/Foo.csv")
    assert "R-naming" in codes(repo)
    rules = layout.load_rules()
    rules["exceptions"].append(
        dict(
            rule="R-naming",
            scope="data/",
            target="path",
            pattern=r"^data/Foo\.csv$",
            reason="Legacy input fixture",
        )
    )
    assert not layout.check(repo, rules)
    write(repo, "data/Other.csv")
    assert any(e["path"] == "data/Other.csv" for e in layout.check(repo, rules))


@pytest.mark.parametrize(
    "change",
    [
        {"reason": " "},
        {"scope": ""},
        {"scope": "**/"},
        {"scope": "../"},
        {"rule": "*"},
        {"pattern": ".*"},
    ],
)
def test_invalid_exception_registration(repo: Path, change: dict[str, str]) -> None:
    entry = dict(
        rule="R-naming",
        scope="data/",
        target="path",
        pattern=r"^data/Foo\.csv$",
        reason="Legacy input fixture",
    )
    entry.update(change)
    rules = layout.load_rules()
    rules["exceptions"].append(entry)
    with pytest.raises(ValueError):
        layout.check(repo, rules)
