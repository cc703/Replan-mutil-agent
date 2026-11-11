import json
import subprocess
import sys
from pathlib import Path


def test_yaml_allowlist_is_one_module(tmp_path: Path) -> None:
    core = tmp_path / "src" / "scheduler_core"
    for relative in ("io/generator_config.py", "io/other.py", "generation/other.py"):
        path = core / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("import yaml\n", encoding="utf8")
    sim = tmp_path / "src" / "simulator" / "module.py"
    sim.parent.mkdir(parents=True, exist_ok=True)
    sim.write_text("import yaml\n", encoding="utf8")
    result = subprocess.run(
        [
            sys.executable,
            "tools/check_import_boundaries.py",
            "--root",
            str(tmp_path),
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert {item["path"] for item in json.loads(result.stdout)} == {
        "src/scheduler_core/io/other.py",
        "src/scheduler_core/generation/other.py",
        "src/simulator/module.py",
    }
