"""Response models for GET /api/v1/home (spec 02 §4.3).

Units are canonical: speed km/h, incline %, durations seconds, distance metres.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Phase = Literal["warmup", "work", "recover", "steady", "cooldown"]
Style = Literal["steady", "easy", "flat", "hill", "hiit", "intervals", "pyramid"]
Chip = Literal["shorter", "easier", "no_incline"]
IntegrationStatus = Literal["connected", "needs_reauth", "error", "disconnected"]


class PlanStep(BaseModel):
    seq: int = Field(ge=1)
    start_offset_s: int = Field(ge=0)
    duration_s: int = Field(gt=0)
    phase: Phase
    speed_kmh: float = Field(gt=0)
    incline_pct: float = Field(ge=0)
    target_hr_min: int | None = None
    target_hr_max: int | None = None
    cue: str | None = None


class PlanPreview(BaseModel):
    title: str
    total_duration_s: int
    est_distance_m: int | None = None
    steps: list[PlanStep]


class Suggestion(BaseModel):
    style: Style
    available_min: int
    plan: PlanPreview
    reason: str


class LastWorkout(BaseModel):
    id: str
    started_at: datetime
    duration_s: int
    distance_m: int | None = None
    plan_adherence_pct: int | None = None


class WeekSummary(BaseModel):
    workouts: int
    duration_s: int
    distance_m: int


class HomeResponse(BaseModel):
    greeting_name: str
    today: date
    active_session: dict | None = None  # typed once sessions exist
    suggestion: Suggestion | None
    quick_chips: list[Chip]
    last_workout: LastWorkout | None
    week: WeekSummary
    integrations: dict[str, IntegrationStatus]
    needs_profile: bool
