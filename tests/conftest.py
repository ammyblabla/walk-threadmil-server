"""Shared fixtures.

DB tests need DATABASE_URL (CI sets it; locally: `docker compose up -d db` + .env).
Without it they are skipped, so `pytest` still works with no database.
"""

import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import Settings, get_settings


def _use_isolated_test_database() -> None:
    """Point the app at `<db>_test` so tests never touch dev data; create it if missing."""
    url = Settings().database_url
    if not url:
        return
    base = make_url(url)
    test_name = base.database if base.database.endswith("_test") else f"{base.database}_test"
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(text("select 1 from pg_database where datname = :n"), {"n": test_name})
        if not exists:
            conn.execute(text(f'create database "{test_name}"'))
    admin.dispose()
    os.environ["DATABASE_URL"] = base.set(database=test_name).render_as_string(hide_password=False)
    get_settings.cache_clear()


_use_isolated_test_database()


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
