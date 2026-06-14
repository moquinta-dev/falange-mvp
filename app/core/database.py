import logging
import time
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.settings import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


def _connect_args(database_url: str) -> dict[str, bool]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    url = make_url(database_url)
    if url.drivername != "sqlite":
        return

    database = url.database
    if database in (None, "", ":memory:"):
        return

    Path(database).parent.mkdir(parents=True, exist_ok=True)


settings = get_settings()
_ensure_sqlite_parent_dir(settings.database_url)
engine = create_engine(
    settings.database_url,
    connect_args=_connect_args(settings.database_url),
    pool_pre_ping=not settings.database_url.startswith("sqlite"),
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _wait_for_database() -> None:
    """Aguarda o banco aceitar conexões (Postgres pode estar subindo)."""

    if settings.database_url.startswith("sqlite"):
        return

    last_error: Exception | None = None
    for attempt in range(1, settings.database_connect_retries + 1):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except OperationalError as exc:
            last_error = exc
            logger.warning(
                "Database not ready (attempt %s/%s): %s",
                attempt,
                settings.database_connect_retries,
                exc,
            )
            time.sleep(settings.database_connect_retry_delay)

    if last_error is not None:
        raise last_error


def init_database() -> None:
    import app.models  # noqa: F401

    _wait_for_database()
    Base.metadata.create_all(bind=engine)

    if engine.dialect.name == "postgresql":
        from app.core.analytics import apply_analytics_objects

        apply_analytics_objects(engine)


async def get_db() -> AsyncGenerator[Session, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
