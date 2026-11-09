"""Exact integer-slot time conversion."""

from datetime import datetime, timedelta, timezone
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Slot = Annotated[int, Field(strict=True, ge=0)]


class TimeAxis(BaseModel):
    """A UTC-normalized axis with inclusive horizon endpoint."""

    model_config = ConfigDict(extra="forbid")
    t0: datetime
    slot_minutes: Annotated[int, Field(strict=True, gt=0)] = 5
    horizon_slots: Annotated[int, Field(strict=True, gt=0)]

    @field_validator("t0")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("t0 must be timezone-aware")
        try:
            return value.astimezone(timezone.utc)
        except OverflowError as exc:
            raise ValueError("t0 cannot be represented in UTC") from exc

    @model_validator(mode="after")
    def representable_horizon(self) -> "TimeAxis":
        """Ensure every slot, including the endpoint, has a UTC datetime."""
        try:
            self.t0 + timedelta(minutes=self.slot_minutes * self.horizon_slots)
        except OverflowError as exc:
            raise ValueError("horizon cannot be represented in UTC") from exc
        return self

    def to_slot(self, dt: datetime) -> Slot:
        """Convert aware, aligned datetime to a slot; reject outside horizon."""
        if not isinstance(dt, datetime):
            raise TypeError("dt must be datetime")
        if dt.utcoffset() is None:
            raise ValueError("dt must be timezone-aware")
        try:
            delta = dt.astimezone(timezone.utc) - self.t0
        except OverflowError as exc:
            raise ValueError("datetime cannot be represented in UTC") from exc
        unit = timedelta(minutes=self.slot_minutes)
        slot, remainder = divmod(delta, unit)
        if remainder or not 0 <= slot <= self.horizon_slots:
            raise ValueError("datetime is unaligned or outside horizon")
        return slot

    def to_dt(self, slot: Slot) -> datetime:
        """Convert an integer slot in [0, horizon] to UTC datetime."""
        if isinstance(slot, bool) or not isinstance(slot, int):
            raise TypeError("slot must be an integer")
        if not 0 <= slot <= self.horizon_slots:
            raise ValueError("slot outside horizon")
        return self.t0 + timedelta(minutes=slot * self.slot_minutes)
