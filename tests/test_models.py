from decimal import Decimal

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.db import Base
from app.models import Plan, PlanStep, Profile, User, WorkoutSession


def _user(db: Session, uid: str = "firebase-test-1") -> User:
    user = User(firebase_uid=uid, email="t@example.com")
    db.add(user)
    db.flush()
    return user


def test_models_match_migrations(db_connection: Connection) -> None:
    """Fails if a model changed without `alembic revision --autogenerate`."""
    ctx = MigrationContext.configure(db_connection, opts={"compare_type": True})
    assert compare_metadata(ctx, Base.metadata) == []


def test_profile_server_defaults(db_session: Session) -> None:
    user = _user(db_session)
    db_session.add(Profile(user_id=user.id))
    db_session.flush()

    profile = db_session.get(Profile, user.id)
    db_session.refresh(profile)
    assert profile.treadmill_max_speed_kmh == Decimal("12.0")
    assert profile.treadmill_speed_step == Decimal("0.1")
    assert profile.treadmill_incline_step == Decimal("1.0")
    assert user.timezone == "Asia/Bangkok"


def test_check_constraint_rejects_unknown_style(db_session: Session) -> None:
    user = _user(db_session)
    db_session.add(WorkoutSession(user_id=user.id, available_min=30, style="sprint"))

    with pytest.raises(IntegrityError, match="ck_sessions_style"):
        db_session.flush()


def test_session_plan_versions_and_circular_fk(db_session: Session) -> None:
    user = _user(db_session)
    session = WorkoutSession(user_id=user.id, available_min=30, style="hill")
    db_session.add(session)
    db_session.flush()

    v1 = Plan(
        user_id=user.id,
        session_id=session.id,
        title="30-min hills",
        total_duration_s=1800,
        generator="rules@test",
        steps=[
            PlanStep(
                seq=1,
                start_offset_s=0,
                duration_s=1800,
                phase="steady",
                speed_kmh=Decimal("5.0"),
                incline_pct=Decimal("4.0"),
            )
        ],
    )
    db_session.add(v1)
    db_session.flush()
    session.current_plan_id = v1.id
    db_session.flush()

    # Deleting the current plan nulls the pointer (ON DELETE SET NULL), not the session.
    db_session.delete(v1)
    db_session.flush()
    db_session.refresh(session)
    assert session.current_plan_id is None


def test_deleting_user_cascades(db_session: Session) -> None:
    user = _user(db_session)
    db_session.add(WorkoutSession(user_id=user.id, available_min=20, style="easy"))
    db_session.flush()

    db_session.delete(user)
    db_session.flush()
    db_session.expire_all()

    assert db_session.scalars(select(WorkoutSession)).all() == []
