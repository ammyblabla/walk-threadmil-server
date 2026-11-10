"""API support tables (spec 02 §3.3)."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, SmallInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._base import created_at


class IdempotencyKey(Base):
    """Offline client retries (POST /complete, /workouts/import): same key ⇒ same response.

    Purge rows older than 7 days.
    """

    __tablename__ = "idempotency_keys"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(primary_key=True)
    request_hash: Mapped[str]
    response_code: Mapped[int] = mapped_column(SmallInteger)
    response_body: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_at()
