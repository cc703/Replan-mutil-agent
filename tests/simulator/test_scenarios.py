import pytest
from pydantic import ValidationError
from simulator.scenarios import Scenario


def test_ranges_and_strictness() -> None:
    for values in (
        {"cooldown_slots": 0},
        {"duration_sigma": -0.1},
        {"urgent_task_range": (3, 1)},
        {"fault_enabled": 1},
        {"urgent_rate_per_day": 0.0},
    ):
        with pytest.raises(ValidationError):
            Scenario(**values)


@pytest.mark.parametrize(
    "field,valid,invalid",
    [
        ("delta_slots", 0, -1),
        ("cooldown_slots", 1, 0),
        ("max_consecutive_failures", 1, 0),
        ("periodic_slots", 1, 0),
        ("duration_sigma", 0.0, -0.1),
        ("duration_factor_min", 0.1, 0.0),
        ("duration_factor_max", 1.0, 0.0),
        ("mtbf_slots", 1.0, 0.0),
        ("repair_median_slots", 1.0, 0.0),
        ("repair_sigma", 0.0, -0.1),
        ("urgent_rate_per_day", 1.0, 0.0),
        ("urgent_slack", 1.0, 0.0),
        ("urgent_weight", 0.0, -0.1),
        ("urgent_task_range", (1, 1), (0, 1)),
        ("fault_enabled", True, 1),
        ("urgent_enabled", False, 0),
        ("urgent_chain", True, 1),
    ],
)
def test_each_field_boundary(field: str, valid: object, invalid: object) -> None:
    Scenario.model_validate({field: valid})
    with pytest.raises(ValidationError):
        Scenario.model_validate({field: invalid})
