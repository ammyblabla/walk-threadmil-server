"""GET/PUT /me/profile — body + treadmill limits; HR zones computed on read."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter

from app.auth import CurrentUser, DbSession
from app.models import Profile
from app.planner.hr_zones import compute_zones, resolve_max_hr
from app.schemas.profile import HrZoneOut, ProfileIn, ProfileOut

router = APIRouter(prefix="/me", tags=["me"])

_NUMERIC_FIELDS = {
    "weight_kg",
    "treadmill_min_speed_kmh",
    "treadmill_max_speed_kmh",
    "treadmill_max_incline_pct",
    "treadmill_speed_step",
    "treadmill_incline_step",
}


def _to_out(profile: Profile) -> ProfileOut:
    out = ProfileOut.model_validate(profile)
    max_hr = resolve_max_hr(profile.max_hr, profile.birth_year, date.today().year)
    if max_hr is not None:
        out.effective_max_hr = max_hr
        out.hr_zones = [
            HrZoneOut(zone=z.zone, min_bpm=z.min_bpm, max_bpm=z.max_bpm)
            for z in compute_zones(max_hr, profile.resting_hr, profile.hr_ceiling)
        ]
    return out


def _get_or_create(db: DbSession, user: CurrentUser) -> Profile:
    profile = db.get(Profile, user.id)
    if profile is None:
        profile = Profile(user_id=user.id, **_db_values(ProfileIn()))
        db.add(profile)
        db.flush()
    return profile


def _db_values(body: ProfileIn) -> dict:
    # Floats in the API, numeric(…) in the DB: go through str to avoid binary-float noise.
    return {
        k: Decimal(str(v)) if k in _NUMERIC_FIELDS and v is not None else v
        for k, v in body.model_dump().items()
    }


@router.get("/profile", response_model=ProfileOut)
def get_profile(db: DbSession, user: CurrentUser) -> ProfileOut:
    return _to_out(_get_or_create(db, user))


@router.put("/profile", response_model=ProfileOut)
def put_profile(body: ProfileIn, db: DbSession, user: CurrentUser) -> ProfileOut:
    profile = _get_or_create(db, user)
    for key, value in _db_values(body).items():
        setattr(profile, key, value)
    db.flush()
    return _to_out(profile)
