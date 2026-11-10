from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "local"
    # Set by CI at deploy time so /healthz shows which commit is running.
    git_sha: str = "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()
