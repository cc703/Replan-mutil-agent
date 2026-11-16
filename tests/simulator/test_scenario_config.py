from pathlib import Path
import pytest
from pydantic import ValidationError
from simulator.config import load_scenario
from simulator.scenarios import Scenario


def test_default_and_rejections() -> None:
    assert load_scenario(Path("experiments/configs/scenarios/default.yaml")) == Scenario()
    for text in (
        "fault_enabled: yes",
        "x: 1\nx: 2",
        "x: &a 1\ny: *a",
        "---\na: 1\n---\nb: 2",
        "duration_sigma: .nan",
        "delta_slots: true",
        "x: !tag value",
        "[]",
    ):
        with pytest.raises(ValueError):
            load_scenario(text)
    with pytest.raises(ValidationError):
        Scenario(duration_factor_min=2.0, duration_factor_max=1.0)


def test_yaml_boundary_is_local(tmp_path: Path) -> None:
    import json
    import subprocess
    import sys

    folder = tmp_path / "src" / "simulator"
    folder.mkdir(parents=True)
    (folder / "config.py").write_text("import yaml\n", encoding="utf-8")
    (folder / "other.py").write_text("import yaml\n", encoding="utf-8")
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
    errors = json.loads(result.stdout)
    assert len(errors) == 1 and errors[0]["path"] == "src/simulator/other.py"


@pytest.mark.parametrize(
    "text",
    [
        "duration_sigma: yes",
        "duration_sigma: .inf",
        "fault_enabled: NO",
        "urgent_task_range: [1, true]",
        "unknown: 1",
        "null",
        "- 1",
        "duration_sigma: &x 1.0",
        "duration_sigma: !!python/object:foo {}",
        "duration_sigma: 1.0\nduration_sigma: 2.0",
        "---\n{}\n---\n{}",
    ],
)
def test_invalid_yaml_forms(text: str) -> None:
    with pytest.raises(ValueError):
        load_scenario(text)
