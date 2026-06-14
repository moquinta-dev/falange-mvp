from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "falange-mvp"
    app_env: str = "local"
    app_version: str = "0.2.0"
    app_debug: bool = True
    database_url: str = "sqlite:///data/falange.db"
    # Tentativas de conexão ao banco no startup (útil quando o Postgres ainda
    # está subindo em outro container da rede privada).
    database_connect_retries: int = 10
    database_connect_retry_delay: float = 3.0
    # Papel somente leitura usado pelo Grafana; recebe SELECT nas views de
    # métricas quando o backend roda sobre PostgreSQL.
    grafana_db_role: str = "grafana_ro"
    # Origens permitidas para CORS (ex.: a landing page que envia o beacon de
    # clique no WhatsApp). Lista separada por vírgula.
    cors_allow_origins: str = "https://www.falangelabs.io,https://falangelabs.io"
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

    @property
    def cors_allow_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
