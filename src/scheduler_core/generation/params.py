"""Generation parameters and immutable scale-specific defaults."""

from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Probability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class TypeCounts(BaseModel):
    """Frozen type counts, defaulting to S=3, M=4 and L=5.

    Construct with strict integer fields S in [1,5], M in [1,10], L in
    [1,20]; omitted constructor fields use defaults. Invalid fields or extra
    keys raise Pydantic ValidationError (a ValueError). Indexing by S/M/L
    returns the count; an unknown key raises KeyError."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    S: Annotated[int, Field(ge=1, le=5)] = 3
    M: Annotated[int, Field(ge=1, le=10)] = 4
    L: Annotated[int, Field(ge=1, le=20)] = 5

    def __getitem__(self, scale: str) -> int:
        return {"S": self.S, "M": self.M, "L": self.L}[scale]


class GeneratorParams(BaseModel):
    """Frozen generation settings; scale and seed are supplied separately.

    Construct with named fields or model_validate; field annotations provide
    defaults and bounds, also reflected in generator/default.yaml. A mapping
    for device_type_count must contain exactly S, M and L; it is copied into
    frozen TypeCounts. Integer fields reject bool; floats must be finite.
    Minimum/maximum pairs must be ordered. Invalid fields raise Pydantic
    ValidationError (ValueError); scale-specific holder constraints are checked
    by validate_inputs. Time-valued settings use five-minute integer slots."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    dag_depth_ratio: Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)] = 0.6
    extra_edge_prob: Probability = 0.15
    lag_min_max: Annotated[int, Field(ge=0, le=12)] = 2
    duration_min: Annotated[int, Field(ge=1, le=144)] = 3
    duration_max: Annotated[int, Field(ge=1, le=144)] = 18
    device_type_count: TypeCounts = Field(default_factory=TypeCounts)
    cap_gt1_fraction: Probability = 0.2
    demand2_prob: Probability = 0.15
    multi_type_prob: Probability = 0.2
    setup_prob: Probability = 0.3
    setup_max: Annotated[int, Field(ge=1, le=12)] = 3
    closed_calendar_fraction: Probability = 0.4
    maint_fraction: Probability = 0.3
    maint_min: Annotated[int, Field(ge=1, le=288)] = 6
    maint_max: Annotated[int, Field(ge=1, le=288)] = 24
    release_span: Probability = 0.5
    deadline_slack_span: Annotated[float, Field(ge=0, le=20, allow_inf_nan=False)] = 3.0
    hard_deadline_fraction: Probability = 0.0
    persons_per_device: Annotated[float, Field(gt=0, le=5, allow_inf_nan=False)] = 0.6
    skill_count: Annotated[int, Field(ge=1, le=8)] = 3
    min_skill_holders: Annotated[int, Field(ge=1, le=8)] = 2
    skill_task_prob: Probability = 0.4
    two_skill_prob: Probability = 0.2
    person_no_skill_prob: Probability = 0.1
    person_absence_prob: Probability = 0.3
    absence_min: Annotated[int, Field(ge=1, le=288)] = 24
    absence_max: Annotated[int, Field(ge=1, le=288)] = 144

    @field_validator("device_type_count", mode="before")
    @classmethod
    def counts(cls, value: object) -> object:
        if isinstance(value, dict):
            if set(value) != {"S", "M", "L"}:
                raise ValueError("device_type_count requires S, M, L")
            return TypeCounts.model_validate(value)
        return value

    @model_validator(mode="after")
    def ranges(self) -> "GeneratorParams":
        for low, high in (
            (self.duration_min, self.duration_max),
            (self.maint_min, self.maint_max),
            (self.absence_min, self.absence_max),
        ):
            if low > high:
                raise ValueError("minimum exceeds maximum")
        return self


SCALES: dict[str, tuple[int, int, int]] = {"S": (20, 5, 6), "M": (60, 10, 15), "L": (150, 20, 35)}
Scale = Literal["S", "M", "L"]


def validate_inputs(
    scale: object,
    utilization: object,
    deadline_tightness: object,
    seed: object,
    params: object = None,
) -> tuple[str, float, float, int, GeneratorParams]:
    """Validate generation inputs and return normalized scale, floats, seed and params.

    Accept S/M/L, finite utilization [0.05,1], tightness [0,1], an integer
    seed [0,2**63-1], and None or GeneratorParams. Reject bool as a number.
    TypeError indicates wrong types; ValueError indicates invalid ranges,
    parameter validation or insufficient personnel for the selected scale.
    Negative zero becomes positive zero. Does no IO or mutation."""
    import math
    from fractions import Fraction

    if not isinstance(scale, str):
        raise TypeError("scale must be a string")
    if scale not in SCALES:
        raise ValueError("unknown scale")
    values = []
    for name, value, minimum in (
        ("utilization", utilization, 0.05),
        ("deadline_tightness", deadline_tightness, 0.0),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a number")
        try:
            number = float(value)
        except OverflowError as exc:
            raise ValueError(f"invalid {name}") from exc
        if not math.isfinite(number) or not minimum <= number <= 1:
            raise ValueError(f"invalid {name}")
        values.append(0.0 if number == 0 else number)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")
    if not 0 <= seed <= 2**63 - 1:
        raise ValueError("invalid seed")
    if params is None:
        params = GeneratorParams()
    if not isinstance(params, GeneratorParams):
        raise TypeError("params must be GeneratorParams")
    # model_copy(update=...) bypasses Pydantic validation; revalidate its fields.
    params = GeneratorParams.model_validate(
        {name: getattr(params, name) for name in GeneratorParams.model_fields}
    )
    n_devices = SCALES[scale][1]
    n_persons = max(2, math.ceil(Fraction(params.persons_per_device) * n_devices))
    if params.min_skill_holders > n_persons:
        raise ValueError("min_skill_holders exceeds personnel count")
    if params.device_type_count[scale] > n_devices:
        raise ValueError("device_type_count exceeds device count")
    return scale, values[0], values[1], seed, params
