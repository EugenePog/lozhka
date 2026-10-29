"""Settings read from environment variables (prefix LOZHKA_) and an optional .env file."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="LOZHKA_", extra="ignore")

    env: str = "local"  # local | staging | production
    # Each process gets the URL of its own database role (see ecosystem.config.js).
    database_url: str = "postgresql://localhost:5432/lozhka"
    object_storage_endpoint: str = ""
    object_storage_bucket: str = "lozhka-local"
    timezone: str = "Europe/Amsterdam"


@lru_cache
def get_settings() -> Settings:
    return Settings()
