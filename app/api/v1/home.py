"""GET /home — aggregated home screen.

MOCK: returns static data until the planner, DB and auth exist.
"""

from datetime import UTC, date, datetime

from fastapi import APIRouter

from app.schemas.home import (
    HomeResponse,
    LastWorkout,
    PlanPreview,
    PlanStep,
    Suggestion,
    WeekSummary,
)

router = APIRouter(tags=["home"])


def _steps(spec: list[tuple[int, str, float, float, str]]) -> list[PlanStep]:
    """Build steps from (duration_s, phase, speed_kmh, incline_pct, cue); offsets are cumulative."""
    steps, offset = [], 0
    for seq, (duration_s, phase, speed, incline, cue) in enumerate(spec, start=1):
        steps.append(
            PlanStep(
                seq=seq,
                start_offset_s=offset,
                duration_s=duration_s,
                phase=phase,
                speed_kmh=speed,
                incline_pct=incline,
                cue=cue,
            )
        )
        offset += duration_s
    return steps


_MOCK_STEPS = _steps(
    [
        (300, "warmup", 4.5, 1.0, "Warm up: 4.5 at 1%"),
        (240, "work", 5.0, 6.0, "Hill: incline to 6"),
        (180, "recover", 5.0, 2.0, "Recover: incline to 2"),
        (240, "work", 5.0, 8.0, "Hill: incline to 8"),
        (180, "recover", 5.0, 2.0, "Recover: incline to 2"),
        (240, "work", 5.0, 6.0, "Hill: incline to 6"),
        (420, "cooldown", 4.2, 0.0, "Cool down: 4.2, flat"),
    ]
)


@router.get("/home", response_model=HomeResponse)
def get_home() -> HomeResponse:
    total = sum(s.duration_s for s in _MOCK_STEPS)
    return HomeResponse(
        greeting_name="Am",
        today=date.today(),
        active_session=None,
        suggestion=Suggestion(
            style="hill",
            available_min=total // 60,
            plan=PlanPreview(
                title=f"{total // 60}-min rolling hills",
                total_duration_s=total,
                est_distance_m=2900,
                steps=_MOCK_STEPS,
            ),
            reason="Mock suggestion — planner not wired yet.",
        ),
        quick_chips=["shorter", "easier", "no_incline"],
        last_workout=LastWorkout(
            id="mock-workout-1",
            started_at=datetime(2026, 11, 8, 11, 2, tzinfo=UTC),
            duration_s=2400,
            distance_m=3800,
            plan_adherence_pct=92,
        ),
        week=WeekSummary(workouts=3, duration_s=6300, distance_m=10200),
        integrations={"garmin": "disconnected"},
        needs_profile=False,
    )
