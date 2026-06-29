from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.database import init_database
from app.core.settings import get_settings
from app.helpers.email_client import get_email_client

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_database()
    if settings.app_env != "local" and settings.wizard_lead_notify_email:
        if not get_email_client(settings).is_configured:
            logger.warning(
                "Alertas de wizard lead desativados: SMTP incompleto "
                "(SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM). "
                "Destino configurado: %s",
                settings.wizard_lead_notify_email,
            )
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.expose_openapi_docs else None,
    redoc_url="/redoc" if settings.expose_openapi_docs else None,
    openapi_url="/openapi.json" if settings.expose_openapi_docs else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
    }
