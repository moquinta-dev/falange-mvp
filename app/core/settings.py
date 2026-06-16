from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "falange-mvp"
    app_env: str = "local"
    app_version: str = "0.4.0"
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
    # Token system-user da Falangelabs: envia em nome de qualquer número da WABA.
    # O número de envio é escolhido por tenant (phone_number_id) em tempo de
    # execução; este token é compartilhado por todos.
    whatsapp_access_token: str = ""
    # Número de fallback usado quando nenhum tenant é resolvido pelo
    # phone_number_id do evento (retrocompatível com o setup single-tenant).
    whatsapp_phone_number_id: str = ""
    # Quando True, eventos de números sem tenant cadastrado são ignorados
    # (status "unknown_tenant"). Quando False, usa o número de fallback acima.
    require_known_tenant: bool = False
    meta_app_secret: str = ""
    meta_graph_api_version: str = "v23.0"
    meta_validate_signature: bool = False
    # Token para endpoints internos (leads, conversas, simulador, etc.).
    # Obrigatório quando APP_ENV != local.
    admin_api_token: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_allow_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    @property
    def expose_openapi_docs(self) -> bool:
        return self.app_env == "local"

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        if self.app_env != "local" and not self.admin_api_token:
            raise ValueError("ADMIN_API_TOKEN is required when APP_ENV is not 'local'")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
