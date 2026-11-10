"""Identity: users, profiles, preferences, integrations (spec 02 §3.3)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    LargeBinary,
    Numeric,
    SmallInteger,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._base import Incline, Speed, UuidPk, check_in, created_at, jsonb_object, updated_at

INTEGRATION_PROVIDERS = ("garmin",)
INTEGRATION_STATUSES = ("connected", "needs_reauth", "error", "disconnected")


class User(Base):
    __tablename__ = "users"

    id: Mapped[UuidPk]
    firebase_uid: Mapped[str] = mapped_column(unique=True)
    email: Mapped[str | None]
    display_name: Mapped[str | None]
    timezone: Mapped[str] = mapped_column(server_default=text("'Asia/Bangkok'"))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    profile: Mapped["Profile | None"] = relationship(back_populates="user", passive_deletes=True)
    preferences: Mapped["Preference | None"] = relationship(passive_deletes=True)


class Profile(Base):
    """Body + treadmill facts; hard limits for the planner. HR zones are computed (D2)."""

    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint("weight_kg BETWEEN 20 AND 300", name="weight_kg"),
        CheckConstraint("max_hr BETWEEN 100 AND 230", name="max_hr"),
        CheckConstraint("resting_hr BETWEEN 30 AND 120", name="resting_hr"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    birth_year: Mapped[int | None] = mapped_column(SmallInteger)
    max_hr: Mapped[int | None] = mapped_column(SmallInteger)  # NULL ⇒ estimate from birth_year
    resting_hr: Mapped[int | None] = mapped_column(SmallInteger)  # set ⇒ Karvonen
    hr_ceiling: Mapped[int | None] = mapped_column(SmallInteger)
    treadmill_max_speed_kmh: Mapped[Speed] = mapped_column(server_default=text("12.0"))
    treadmill_min_speed_kmh: Mapped[Speed] = mapped_column(server_default=text("1.0"))
    treadmill_max_incline_pct: Mapped[Incline] = mapped_column(server_default=text("12.0"))
    treadmill_speed_step: Mapped[Decimal] = mapped_column(Numeric(3, 1), server_default=text("0.1"))
    treadmill_incline_step: Mapped[Decimal] = mapped_column(Numeric(3, 1), server_default=text("1"))
    updated_at: Mapped[datetime] = updated_at()

    user: Mapped[User] = relationship(back_populates="profile")


class Preference(Base):
    """Per-user defaults. `data` shape = Pydantic PreferenceSet at `schema_version`."""

    __tablename__ = "preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    schema_version: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"))
    data: Mapped[dict] = jsonb_object()
    updated_at: Mapped[datetime] = updated_at()


class Integration(Base):
    """Third-party connection. `credentials_enc` is Fernet-encrypted in the app, never plaintext."""

    __tablename__ = "integrations"
    __table_args__ = (
        CheckConstraint(check_in("provider", INTEGRATION_PROVIDERS), name="provider"),
        CheckConstraint(check_in("status", INTEGRATION_STATUSES), name="status"),
        UniqueConstraint("user_id", "provider"),  # one connection per provider per user
    )

    id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str]
    status: Mapped[str] = mapped_column(server_default=text("'connected'"))
    credentials_enc: Mapped[bytes] = mapped_column(LargeBinary)
    key_version: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"))
    last_sync_at: Mapped[datetime | None]
    last_error: Mapped[str | None]
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()
