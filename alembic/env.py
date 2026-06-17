from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.database import Base
from app.core.settings import get_settings

import app.models  # noqa: F401  (registra todos os models no metadata)

config = context.config

# Quando rodado embarcado no startup da app (app.core.migrations), NÃO reconfigurar
# o logging: o fileConfig do Alembic usa disable_existing_loggers=True por padrão,
# o que silenciaria os loggers já configurados do uvicorn (inclusive o access log)
# e da aplicação. Via CLI do Alembic (attributes vazio) mantemos o comportamento padrão.
if config.config_file_name is not None and config.attributes.get(
    "configure_logger", True
):
    fileConfig(config.config_file_name)

# A URL pode ter sido injetada pelo runner (app.core.migrations); caso contrário
# (uso via CLI) vem das settings da aplicação, mantendo uma única fonte de verdade.
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
