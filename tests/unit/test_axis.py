from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError
from scheduler_core.axis import TimeAxis
from scheduler_core import models


def test_exact_utc_conversion_and_boundaries() -> None:
    axis = TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=8))), horizon_slots=2)
    assert axis.to_dt(0) == datetime(2025, 12, 31, 16, tzinfo=timezone.utc)
    assert axis.to_slot(axis.to_dt(2)) == 2
    for value in (-1, 3):
        with pytest.raises(ValueError):
            axis.to_dt(value)
    for invalid in (True, 1.0):
        with pytest.raises(TypeError):
            axis.to_dt(invalid)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        axis.to_slot(axis.t0 + timedelta(seconds=1))
    with pytest.raises(ValueError):
        axis.to_slot(datetime(2026, 1, 1))
    with pytest.raises(ValidationError):
        TimeAxis(t0=datetime(2026, 1, 1), horizon_slots=1)
    assert models.TimeAxis is TimeAxis


def test_import_orders() -> None:
    import os
    import subprocess
    import sys

    env = {**os.environ, "PYTHONPATH": "src"}
    for first, second in (("axis", "models"), ("models", "axis")):
        code = (
            f"import scheduler_core.{first}; import scheduler_core.{second}; "
            "from scheduler_core import axis, models; "
            "assert models.TimeAxis is axis.TimeAxis and models.Slot is axis.Slot"
        )
        subprocess.run([sys.executable, "-c", code], env=env, check=True)


@pytest.mark.parametrize(
    "field,value",
    [
        ("horizon_slots", 0),
        ("horizon_slots", -1),
        ("horizon_slots", True),
        ("slot_minutes", 0),
        ("slot_minutes", -1),
        ("slot_minutes", 1.5),
    ],
)
def test_invalid_axis_configuration(field: str, value: object) -> None:
    values = {"t0": datetime(2026, 1, 1, tzinfo=timezone.utc), "horizon_slots": 2, field: value}
    with pytest.raises(ValidationError):
        TimeAxis.model_validate(values)


def test_datetime_range_and_zone() -> None:
    axis = TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=2)
    assert axis.to_slot(datetime(2026, 1, 1, 8, tzinfo=timezone(timedelta(hours=8)))) == 0
    for dt in (
        axis.t0 - timedelta(minutes=5),
        axis.t0 + timedelta(minutes=15),
        axis.t0 + timedelta(milliseconds=1),
    ):
        with pytest.raises(ValueError):
            axis.to_slot(dt)
    with pytest.raises(TypeError):
        axis.to_slot("2026-01-01")  # type: ignore[arg-type]


def test_representable_datetime_limits() -> None:
    end = datetime.max.replace(tzinfo=timezone.utc)
    axis = TimeAxis(t0=end - timedelta(minutes=5), horizon_slots=1)
    assert axis.to_dt(1) == end
    assert axis.to_slot(end) == 1
    with pytest.raises(ValidationError, match="horizon cannot be represented"):
        TimeAxis(t0=end - timedelta(minutes=1), horizon_slots=1)
    with pytest.raises(ValidationError, match="horizon cannot be represented"):
        TimeAxis(
            t0=datetime(2026, 1, 1, tzinfo=timezone.utc),
            slot_minutes=10**100,
            horizon_slots=10**100,
        )
    with pytest.raises(ValidationError, match="t0 cannot be represented"):
        TimeAxis(t0=datetime.min.replace(tzinfo=timezone(timedelta(hours=1))), horizon_slots=1)
    with pytest.raises(ValidationError, match="t0 cannot be represented"):
        TimeAxis(t0=datetime.max.replace(tzinfo=timezone(-timedelta(hours=1))), horizon_slots=1)
    with pytest.raises(ValueError, match="datetime cannot be represented"):
        axis.to_slot(datetime.min.replace(tzinfo=timezone(timedelta(hours=1))))
