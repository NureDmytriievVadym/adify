from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ADIFY_", extra="ignore")

    app_name: str = "Adify API"
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
