"""Planning: sessions, immutable plan versions, plan steps, chat (spec 02 §3.3)."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, SmallInteger, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._base import Incline, Speed, UuidPk, check_in, created_at, jsonb_object, updated_at

SESSION_STATUSES = ("planning", "ready", "in_progress", "completed", "abandoned")
STYLES = ("steady", "easy", "flat", "hill", "hiit", "intervals", "pyramid")
PHASES = ("warmup", "work", "recover", "steady", "cooldown")
VISIBILITIES = ("private", "link", "public")
CHAT_ROLES = ("user", "assistant", "system")


class WorkoutSession(Base):
    """A Session = one intended treadmill workout ("today, 30 min, slept badly").

    Named WorkoutSession in Python to avoid clashing with sqlalchemy.orm.Session.
    """

    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(check_in("status", SESSION_STATUSES), name="status"),
        CheckConstraint(check_in("style", STYLES), name="style"),
        CheckConstraint("available_min BETWEEN 5 AND 240", name="available_min"),
        Index("ix_sessions_user_created", "user_id", text("created_at DESC")),
    )

    id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(server_default=text("'planning'"))
    available_min: Mapped[int] = mapped_column(SmallInteger)
    style: Mapped[str]
    goal: Mapped[str | None]
    conditions: Mapped[dict] = jsonb_object()  # SessionConditions: sleep_hours, is_period, injury…
    overrides: Mapped[dict] = jsonb_object()  # PreferenceSet keys for this session only
    # Circular with plans.session_id → FK created after both tables (use_alter).
    current_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("plans.id", ondelete="SET NULL", use_alter=True)
    )
    started_at: Mapped[datetime | None]
    ended_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    current_plan: Mapped["Plan | None"] = relationship(foreign_keys=[current_plan_id])


class Plan(Base):
    """Immutable plan version. Every adjustment inserts a new row (parent_plan_id = source)."""

    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint(check_in("visibility", VISIBILITIES), name="visibility"),
        UniqueConstraint("session_id", "version"),
        Index("ix_plans_session_version", "session_id", text("version DESC")),
    )

    id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    session_id: Mapped[uuid.UUID | None] = mapped_column(  # NULL = saved template
        ForeignKey("sessions.id", ondelete="CASCADE")
    )
    parent_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("plans.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"))
    title: Mapped[str]
    rationale: Mapped[str | None]
    total_duration_s: Mapped[int]
    est_distance_m: Mapped[int | None]
    est_kcal: Mapped[int | None]
    generator: Mapped[str]  # e.g. 'rules@1.0.0'
    adjustment: Mapped[dict | None] = mapped_column(JSONB)  # PlanAdjustment that made this version
    visibility: Mapped[str] = mapped_column(server_default=text("'private'"))
    created_at: Mapped[datetime] = created_at()

    steps: Mapped[list["PlanStep"]] = relationship(
        order_by="PlanStep.seq", cascade="all, delete-orphan", passive_deletes=True
    )


class PlanStep(Base):
    __tablename__ = "plan_steps"
    __table_args__ = (
        CheckConstraint(check_in("phase", PHASES), name="phase"),
        CheckConstraint("duration_s > 0", name="duration_s"),
        CheckConstraint("speed_kmh > 0", name="speed_kmh"),
        CheckConstraint("incline_pct >= 0", name="incline_pct"),
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), primary_key=True
    )
    seq: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    start_offset_s: Mapped[int]  # denormalized: O(1) "what now?" in run mode
    duration_s: Mapped[int]
    phase: Mapped[str]
    speed_kmh: Mapped[Speed]
    incline_pct: Mapped[Incline]
    target_hr_min: Mapped[int | None] = mapped_column(SmallInteger)
    target_hr_max: Mapped[int | None] = mapped_column(SmallInteger)
    cue: Mapped[str | None]  # Phase 2 audio


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint(check_in("role", CHAT_ROLES), name="role"),
        Index("ix_chat_messages_session_created", "session_id", "created_at"),
    )

    id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    role: Mapped[str]
    content: Mapped[str]
    adjustment: Mapped[dict | None] = mapped_column(JSONB)
    produced_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("plans.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at()
