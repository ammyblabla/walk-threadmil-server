"""Shared fixtures.

DB tests need DATABASE_URL (CI sets it; locally: `docker compose up -d db` + .env).
Without it they are skipped, so `pytest` still works with no database.
"""

from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection
from sqlalchemy.orm import Session

from app.config import get_settings


def _require_db() -> None:
    if not get_settings().database_url:
        pytest.skip("DATABASE_URL not set — start Postgres to run DB tests")


@pytest.fixture(scope="session")
def migrated_db() -> None:
    """Migrate the test database to head once per test run."""
    _require_db()
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture
def db_connection(migrated_db: None) -> Iterator[Connection]:
    from app.db import get_engine

    with get_engine().connect() as conn:
        tx = conn.begin()
        yield conn
        tx.rollback()  # every test leaves the DB untouched


@pytest.fixture
def db_session(db_connection: Connection) -> Iterator[Session]:
    # App code may call commit(); savepoints keep it inside the outer rollback.
    session = Session(bind=db_connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
