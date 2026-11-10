from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "local"
    # Set by CI at deploy time so /health shows which commit is running.
    git_sha: str = "dev"
    # SQLAlchemy URL, e.g. postgresql+psycopg://walk:walk@localhost:5432/walk
    # Unset in prod until Neon is wired; DB-backed endpoints then return 503.
    database_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
