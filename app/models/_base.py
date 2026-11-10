"""Column helpers shared by all models (spec 02 §3.2 conventions)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from sqlalchemy import Numeric, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

# Primary key: server-generated UUID.
UuidPk = Annotated[
    uuid.UUID,
    mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
]

# Canonical units: km/h and % as numeric(4,1).
Speed = Annotated[Decimal, mapped_column(Numeric(4, 1))]
Incline = Annotated[Decimal, mapped_column(Numeric(4, 1))]


def jsonb_object() -> Mapped[dict]:
    return mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))


def created_at() -> Mapped[datetime]:
    return mapped_column(nullable=False, server_default=func.now())


def updated_at() -> Mapped[datetime]:
    return mapped_column(nullable=False, server_default=func.now(), onupdate=func.now())


def check_in(column: str, values: tuple[str, ...]) -> str:
    """SQL for `column IN ('a','b')` — text + CHECK instead of PG ENUM (easy migrations)."""
    quoted = ",".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"
