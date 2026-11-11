import pytest
from scheduler_core.generate import generate_instance
from scheduler_core.generation.params import GeneratorParams, validate_inputs


@pytest.mark.parametrize(
    "args",
    [
        (None, 0.8, 0.5, 0),
        ("XL", 0.8, 0.5, 0),
        ("S", True, 0.5, 0),
        ("S", float("nan"), 0.5, 0),
        ("S", 0.8, float("inf"), 0),
        ("S", 0.8, 0.5, True),
        ("S", 0.8, 0.5, -1),
    ],
)
def test_invalid(args: tuple[object, object, object, object]) -> None:
    with pytest.raises((ValueError, TypeError)):
        validate_inputs(*args)


def test_nested_frozen() -> None:
    source = {"S": 3, "M": 4, "L": 5}
    params = GeneratorParams.model_validate({"device_type_count": source})
    source["S"] = 1
    assert params.device_type_count.S == 3
    with pytest.raises(ValueError):
        params.device_type_count.S = 2


def test_horizon_search_zero_and_limit() -> None:
    from scheduler_core.generation.timing import horizon_for_load
    from scheduler_core.models import Device

    devices = [Device(id="d", type="t")]
    assert horizon_for_load(144, 1.0, devices, {"d"}, limit=144) == 144
    with pytest.raises(ValueError):
        horizon_for_load(145, 1.0, devices, {"d"}, limit=288)
    assert horizon_for_load(145, 1.0, devices, {"d"}, limit=289) == 289


@pytest.mark.parametrize("value", [0.0, -0.0, 1e-21, 5e-324, 1.0])
def test_tightness_domain(value: float) -> None:
    assert generate_instance("S", 1.0, value, 0).tasks


def test_zero_capacity_search() -> None:
    from scheduler_core.generation.timing import horizon_for_load

    with pytest.raises(ValueError):
        horizon_for_load(1, 1.0, [], set(), limit=10)


@pytest.mark.parametrize(
    "field",
    [
        "dag_depth_ratio",
        "extra_edge_prob",
        "cap_gt1_fraction",
        "demand2_prob",
        "multi_type_prob",
        "setup_prob",
        "closed_calendar_fraction",
        "maint_fraction",
        "release_span",
        "hard_deadline_fraction",
        "skill_task_prob",
        "two_skill_prob",
        "person_no_skill_prob",
        "person_absence_prob",
    ],
)
@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -0.1, 1.1])
def test_probability_domains(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        GeneratorParams.model_validate({field: value})


@pytest.mark.parametrize(
    "field",
    [
        "lag_min_max",
        "duration_min",
        "duration_max",
        "setup_max",
        "maint_min",
        "maint_max",
        "skill_count",
        "min_skill_holders",
        "absence_min",
        "absence_max",
    ],
)
@pytest.mark.parametrize("value", [True, 1.5, "1", -1, 999])
def test_integer_domains(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        GeneratorParams.model_validate({field: value})


def test_copy_update_must_revalidate() -> None:
    invalid = GeneratorParams().model_copy(update={"duration_min": 999})
    with pytest.raises(ValueError):
        validate_inputs("S", 0.8, 0.5, 0, invalid)


@pytest.mark.parametrize(
    "low,high",
    [("duration_min", "duration_max"), ("maint_min", "maint_max"), ("absence_min", "absence_max")],
)
def test_inverted_bounds(low: str, high: str) -> None:
    with pytest.raises(ValueError):
        GeneratorParams.model_validate({low: 3, high: 2})


@pytest.mark.parametrize(
    "mapping", [{"S": 1, "M": 1}, {"S": 6, "M": 1, "L": 1}, {"S": 1, "M": 0, "L": 1}]
)
def test_invalid_counts(mapping: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        GeneratorParams.model_validate({"device_type_count": mapping})


def test_extreme_legal_configuration() -> None:
    params = GeneratorParams.model_validate(
        {
            "device_type_count": {"S": 1, "M": 1, "L": 1},
            "dag_depth_ratio": 5e-324,
            "skill_count": 1,
            "min_skill_holders": 2,
            "persons_per_device": 0.01,
            "skill_task_prob": 1,
            "two_skill_prob": 1,
            "maint_min": 288,
            "maint_max": 288,
            "absence_min": 288,
            "absence_max": 288,
        }
    )
    instance = generate_instance("S", 1, 1, 0, params=params)
    assert all(len(t.required_skills) == 1 for t in instance.tasks)
    assert len(instance.persons) == 2
    assert all("skill1" in p.skills for p in instance.persons)
    assert not any(w.kind == "MAINT" for w in instance.blocked)
    assert all(not p.blocked for p in instance.persons)
    with pytest.raises(ValueError):
        validate_inputs("S", 0.8, 0.5, 0, params.model_copy(update={"min_skill_holders": 3}))


@pytest.mark.parametrize(
    "field,low,high",
    [
        ("lag_min_max", 0, 12),
        ("duration_min", 1, 144),
        ("duration_max", 1, 144),
        ("setup_max", 1, 12),
        ("maint_min", 1, 288),
        ("maint_max", 1, 288),
        ("skill_count", 1, 8),
        ("min_skill_holders", 1, 8),
        ("absence_min", 1, 288),
        ("absence_max", 1, 288),
    ],
)
def test_integer_valid_limits(field: str, low: int, high: int) -> None:
    for value in (low, high):
        data = {field: value}
        if field.endswith("_min"):
            data[field[:-4] + "_max"] = value
        if field.endswith("_max") and field not in {"lag_min_max", "setup_max"}:
            data[field[:-4] + "_min"] = value
        assert getattr(GeneratorParams.model_validate(data), field) == value


@pytest.mark.parametrize(
    "field,valid,invalid", [("deadline_slack_span", 20.0, 20.1), ("persons_per_device", 5.0, 5.1)]
)
def test_other_floats(field: str, valid: float, invalid: float) -> None:
    assert getattr(GeneratorParams.model_validate({field: valid}), field) == valid
    for value in (invalid, True, float("nan"), float("inf"), -1):
        with pytest.raises(ValueError):
            GeneratorParams.model_validate({field: value})


@pytest.mark.parametrize(
    "field",
    [
        "extra_edge_prob",
        "cap_gt1_fraction",
        "demand2_prob",
        "multi_type_prob",
        "setup_prob",
        "closed_calendar_fraction",
        "maint_fraction",
        "release_span",
        "hard_deadline_fraction",
        "skill_task_prob",
        "two_skill_prob",
        "person_no_skill_prob",
        "person_absence_prob",
    ],
)
def test_probability_endpoints(field: str) -> None:
    for value in (0, 1):
        assert getattr(GeneratorParams.model_validate({field: value}), field) == float(value)


def test_ratio_and_float_endpoints() -> None:
    for value in (5e-324, 1):
        assert GeneratorParams.model_validate({"dag_depth_ratio": value}).dag_depth_ratio == value
    for value in (0, 20):
        assert (
            GeneratorParams.model_validate({"deadline_slack_span": value}).deadline_slack_span
            == value
        )
    for value in (5e-324, 5):
        assert (
            GeneratorParams.model_validate({"persons_per_device": value}).persons_per_device
            == value
        )
    for field in ("dag_depth_ratio", "persons_per_device"):
        with pytest.raises(ValueError):
            GeneratorParams.model_validate({field: 0})
