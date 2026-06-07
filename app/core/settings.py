from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "falange-mvp"
    app_env: str = "local"
    app_version: str = "0.1.0"
    app_debug: bool = True
    database_url: str = "sqlite:///data/falange.db"
    whatsapp_verify_token: str = ""
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    meta_app_secret: str = ""
    meta_graph_api_version: str = "v23.0"
    meta_validate_signature: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
