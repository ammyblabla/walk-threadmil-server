"""Execution & history: workouts, segments, samples, feedback (spec 02 §3.3)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    REAL,
    CheckConstraint,
    ForeignKey,
    Index,
    SmallInteger,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._base import Incline, Speed, UuidPk, check_in, created_at, updated_at

WORKOUT_SOURCES = ("app", "garmin", "screenshot", "link", "manual")
SEGMENT_EVENTS = ("step", "pause", "skip", "extend")
FEEDBACK_AUTHORS = ("user", "assistant")


class Workout(Base):
    __tablename__ = "workouts"
    __table_args__ = (
        CheckConstraint(check_in("source", WORKOUT_SOURCES), name="source"),
        UniqueConstraint("user_id", "source", "external_id"),  # idempotent Garmin sync
        Index("ix_workouts_user_started", "user_id", text("started_at DESC")),
    )

    id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL"), unique=True
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(  # the version actually run
        ForeignKey("plans.id", ondelete="SET NULL")
    )
    source: Mapped[str]
    external_id: Mapped[str | None]  # Garmin activityId
    started_at: Mapped[datetime]
    duration_s: Mapped[int]
    distance_m: Mapped[int | None]
    avg_hr: Mapped[int | None] = mapped_column(SmallInteger)
    max_hr: Mapped[int | None] = mapped_column(SmallInteger)
    kcal: Mapped[int | None]
    elevation_gain_m: Mapped[int | None]
    source_meta: Mapped[dict | None] = mapped_column(JSONB)  # whitelisted provider fields only
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    segments: Mapped[list["WorkoutSegment"]] = relationship(
        order_by="WorkoutSegment.seq", cascade="all, delete-orphan", passive_deletes=True
    )


class WorkoutSegment(Base):
    """What was actually dialled in (run mode or Garmin laps). Drives planned-vs-actual."""

    __tablename__ = "workout_segments"
    __table_args__ = (CheckConstraint(check_in("event", SEGMENT_EVENTS), name="event"),)

    workout_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workouts.id", ondelete="CASCADE"), primary_key=True
    )
    seq: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    plan_step_seq: Mapped[int | None] = mapped_column(SmallInteger)  # NULL = unplanned
    start_offset_s: Mapped[int]
    duration_s: Mapped[int]
    speed_kmh: Mapped[Speed | None]
    incline_pct: Mapped[Incline | None]
    avg_hr: Mapped[int | None] = mapped_column(SmallInteger)
    event: Mapped[str | None]


class WorkoutSample(Base):
    """LATER (HR guidance): ~1 Hz traces as arrays, one row per workout. Index = t / interval_s."""

    __tablename__ = "workout_samples"

    workout_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workouts.id", ondelete="CASCADE"), primary_key=True
    )
    interval_s: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"))
    hr: Mapped[list[int] | None] = mapped_column(ARRAY(SmallInteger))
    speed_kmh: Mapped[list[float] | None] = mapped_column(ARRAY(REAL))
    incline_pct: Mapped[list[float] | None] = mapped_column(ARRAY(REAL))


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint(check_in("author", FEEDBACK_AUTHORS), name="author"),
        CheckConstraint("perceived_exertion BETWEEN 1 AND 10", name="perceived_exertion"),
        Index("ix_feedback_workout", "workout_id"),
    )

    id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    workout_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workouts.id", ondelete="CASCADE"))
    author: Mapped[str]
    # RPE: Rate of Perceived Exertion, 1 = very easy, 10 = max effort
    perceived_exertion: Mapped[int | None] = mapped_column(SmallInteger)
    notes: Mapped[str | None]
    analysis: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_at()
