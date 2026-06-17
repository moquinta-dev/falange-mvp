"""Execução de migrações Alembic no startup (PostgreSQL).

Em produção o schema é gerido por Alembic. Em SQLite (local/testes) seguimos
usando ``Base.metadata.create_all`` por simplicidade.

Adoção de banco legado: bancos criados pela versão antiga (que usava apenas
``create_all``) têm as tabelas, mas não têm ``alembic_version``. Nesse caso
carimbamos (stamp) a baseline antes de aplicar as migrações novas, para não
tentar recriar tabelas já existentes.
"""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_BASELINE_REVISION = "0001_baseline"
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _alembic_config(engine: Engine) -> Config:
    config = Config(str(_PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_PROJECT_ROOT / "alembic"))
    # Usa exatamente a mesma URL do engine da aplicação (com senha), para que o
    # Alembic (que gerencia sua própria conexão e commit) opere sobre o mesmo DB.
    config.set_main_option(
        "sqlalchemy.url",
        engine.url.render_as_string(hide_password=False),
    )
    # Embarcado no startup: o env.py NÃO deve chamar fileConfig (que desativaria os
    # loggers já configurados do uvicorn/app). Logging fica a cargo da aplicação.
    config.attributes["configure_logger"] = False
    return config


def run_migrations(engine: Engine) -> None:
    inspector = inspect(engine)
    has_existing_schema = inspector.has_table("conversations")
    has_alembic_version = inspector.has_table("alembic_version")

    config = _alembic_config(engine)

    if has_existing_schema and not has_alembic_version:
        logger.info(
            "Schema legado detectado sem alembic_version; carimbando baseline %s",
            _BASELINE_REVISION,
        )
        command.stamp(config, _BASELINE_REVISION)

    command.upgrade(config, "head")
    logger.info("Migrações Alembic aplicadas (head)")
