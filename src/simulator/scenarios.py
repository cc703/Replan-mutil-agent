"""Validated synthetic simulator parameters; not estimates of real systems."""

from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, model_validator

PosInt = Annotated[int, Field(strict=True, gt=0)]
NonnegInt = Annotated[int, Field(strict=True, ge=0)]
Nonneg = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
Positive = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]


class Scenario(BaseModel):
    """Parameters for independently keyed synthetic perturbations."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    delta_slots: NonnegInt = 1
    cooldown_slots: PosInt = 6
    max_consecutive_failures: PosInt = 3
    periodic_slots: PosInt | None = None
    duration_sigma: Nonneg = 0.2
    duration_factor_min: Positive = 0.8
    duration_factor_max: Positive = 1.6
    fault_enabled: bool = False
    mtbf_slots: Positive = 1000.0
    repair_median_slots: Positive = 12.0
    repair_sigma: Nonneg = 0.4
    urgent_enabled: bool = False
    urgent_rate_per_day: Positive = 1.0
    urgent_task_range: tuple[PosInt, PosInt] = (1, 3)
    urgent_slack: Positive = 2.0
    urgent_weight: Nonneg = 2.0
    urgent_chain: bool = True

    @model_validator(mode="after")
    def ranges(self) -> "Scenario":
        if self.duration_factor_min > self.duration_factor_max:
            raise ValueError("duration factor bounds reversed")
        if self.urgent_task_range[0] > self.urgent_task_range[1]:
            raise ValueError("urgent task range reversed")
        return self
