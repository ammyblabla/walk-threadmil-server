"""GET/PUT /api/v1/me/profile (spec 02 §4.2). Bounds mirror the DB CHECK constraints."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProfileIn(BaseModel):
    """PUT body = full replacement; omitted fields reset to their defaults."""

    model_config = ConfigDict(extra="forbid")

    weight_kg: float | None = Field(default=None, ge=20, le=300)
    birth_year: int | None = Field(default=None, ge=1900, le=2100)
    max_hr: int | None = Field(default=None, ge=100, le=230)
    resting_hr: int | None = Field(default=None, ge=30, le=120)
    hr_ceiling: int | None = Field(default=None, ge=60, le=230)
    treadmill_min_speed_kmh: float = Field(default=1.0, gt=0, le=30)
    treadmill_max_speed_kmh: float = Field(default=12.0, gt=0, le=30)
    treadmill_max_incline_pct: float = Field(default=12.0, ge=0, le=40)
    treadmill_speed_step: float = Field(default=0.1, gt=0, le=5)
    treadmill_incline_step: float = Field(default=1.0, gt=0, le=5)

    @model_validator(mode="after")
    def _ranges(self) -> Self:
        if self.treadmill_min_speed_kmh >= self.treadmill_max_speed_kmh:
            raise ValueError("treadmill_min_speed_kmh must be below treadmill_max_speed_kmh")
        if (
            self.resting_hr is not None
            and self.max_hr is not None
            and self.resting_hr >= self.max_hr
        ):
            raise ValueError("resting_hr must be below max_hr")
        return self


class HrZoneOut(BaseModel):
    zone: int
    min_bpm: int
    max_bpm: int


class ProfileOut(ProfileIn):
    model_config = ConfigDict(extra="ignore", from_attributes=True)

    # Read-only, computed from max_hr / birth_year / resting_hr (D2). None until enough data.
    effective_max_hr: int | None = None
    hr_zones: list[HrZoneOut] | None = None
