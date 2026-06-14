import asyncio
from collections.abc import Generator

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base, get_db
from app.core.settings import get_settings
from app.main import app

_TEST_API_TOKEN = "test-admin-token"


@pytest.fixture()
def client(tmp_path) -> Generator[httpx.AsyncClient, None, None]:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    settings = get_settings()
    original_token = settings.admin_api_token
    settings.admin_api_token = _TEST_API_TOKEN

    async def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    async_client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
    try:
        yield async_client
    finally:
        asyncio.run(async_client.aclose())
        app.dependency_overrides.clear()
        settings.admin_api_token = original_token
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_protected_endpoint_rejects_missing_api_key(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        response = await client.get("/leads")

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or missing API key"

    asyncio.run(run())


def test_protected_endpoint_accepts_x_api_key(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        response = await client.get("/leads", headers={"X-API-Key": _TEST_API_TOKEN})

        assert response.status_code == 200
        assert response.json() == []

    asyncio.run(run())


def test_protected_endpoint_accepts_bearer_token(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        response = await client.get(
            "/leads",
            headers={"Authorization": f"Bearer {_TEST_API_TOKEN}"},
        )

        assert response.status_code == 200
        assert response.json() == []

    asyncio.run(run())


def test_landing_events_remain_public(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        response = await client.post(
            "/funnel/landing-events",
            json={
                "event_type": "page_view",
                "session_id": "sess-auth-test",
                "path": "/",
            },
        )

        assert response.status_code == 201
        assert response.json()["event_type"] == "page_view"

    asyncio.run(run())


def test_funnel_metrics_require_api_key(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        unauthorized = await client.get("/funnel/metrics")
        authorized = await client.get(
            "/funnel/metrics",
            headers={"X-API-Key": _TEST_API_TOKEN},
        )

        assert unauthorized.status_code == 401
        assert authorized.status_code == 200

    asyncio.run(run())


def test_expose_openapi_docs_only_in_local() -> None:
    settings = get_settings()

    original_env = settings.app_env
    try:
        settings.app_env = "local"
        assert settings.expose_openapi_docs is True

        settings.app_env = "staging"
        assert settings.expose_openapi_docs is False

        settings.app_env = "production"
        assert settings.expose_openapi_docs is False
    finally:
        settings.app_env = original_env
