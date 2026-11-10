from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, text


def test_database_reachable(db_connection: Connection) -> None:
    assert db_connection.execute(text("select 1")).scalar_one() == 1


def test_database_at_latest_migration(db_connection: Connection) -> None:
    head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    current = MigrationContext.configure(db_connection).get_current_revision()

    assert current == head
