from functools import lru_cache
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "local"
    # Set by CI at deploy time so /health shows which commit is running.
    git_sha: str = "dev"
    # SQLAlchemy URL, e.g. postgresql+psycopg://walk:walk@localhost:5432/walk
    # Unset ⇒ DB-backed endpoints return 503.
    database_url: str | None = None

    # "firebase": verify Firebase ID tokens. "dev": every request is one local owner (never prod).
    auth_mode: Literal["firebase", "dev"] = "firebase"
    firebase_project_id: str = "walk-treadmil"

    @model_validator(mode="after")
    def _no_dev_auth_in_prod(self) -> Self:
        if self.env == "prod" and self.auth_mode == "dev":
            raise ValueError("AUTH_MODE=dev is not allowed when ENV=prod")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
