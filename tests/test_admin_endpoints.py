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

VALID_WORKFLOW = {
    "start": "ask_name",
    "nodes": {
        "ask_name": {
            "type": "text",
            "prompt": "Como é o seu nome?",
            "collect": "nome",
            "next": "ask_goal",
        },
        "ask_goal": {
            "type": "choice",
            "prompt": "Qual o objetivo?",
            "collect": "objetivo",
            "options": [
                {"label": "Emagrecer", "next": "done"},
                {"label": "Ganhar massa", "next": "done"},
            ],
        },
        "done": {"type": "terminal", "summary": True},
    },
}


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


_AUTH = {"X-API-Key": _TEST_API_TOKEN}


def test_admin_requires_api_key(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        response = await client.get("/admin/workflows")
        assert response.status_code == 401

    asyncio.run(run())


def test_upsert_workflow_then_tenant(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        wf = await client.put(
            "/admin/workflows/triagem_test_v1",
            headers=_AUTH,
            json={"name": "Triagem teste", "definition": VALID_WORKFLOW},
        )
        assert wf.status_code == 200
        assert wf.json()["key"] == "triagem_test_v1"

        tenant = await client.put(
            "/admin/tenants/PHONE123",
            headers=_AUTH,
            json={
                "name": "Cliente Teste",
                "workflow_key": "triagem_test_v1",
                "notify_channel": "email",
                "notify_target": "dono@cliente.com",
            },
        )
        assert tenant.status_code == 200
        body = tenant.json()
        assert body["whatsapp_phone_number_id"] == "PHONE123"
        assert body["workflow_id"] == wf.json()["id"]
        assert body["active"] is True

        listing = await client.get("/admin/tenants", headers=_AUTH)
        assert listing.status_code == 200
        assert len(listing.json()) == 1

    asyncio.run(run())


def test_upsert_workflow_rejects_invalid_definition(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        broken = {
            "start": "ask_name",
            "nodes": {
                "ask_name": {
                    "type": "text",
                    "prompt": "Nome?",
                    "next": "missing_node",
                },
                "done": {"type": "terminal"},
            },
        }
        response = await client.put(
            "/admin/workflows/broken_v1",
            headers=_AUTH,
            json={"name": "Quebrado", "definition": broken},
        )
        assert response.status_code == 422
        assert "destino inexistente" in response.json()["detail"]

    asyncio.run(run())


def test_upsert_tenant_unknown_workflow(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        response = await client.put(
            "/admin/tenants/PHONE999",
            headers=_AUTH,
            json={"name": "Sem fluxo", "workflow_key": "nao_existe"},
        )
        assert response.status_code == 404

    asyncio.run(run())


def test_workflow_upsert_is_idempotent(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        first = await client.put(
            "/admin/workflows/idem_v1",
            headers=_AUTH,
            json={"name": "Primeiro", "definition": VALID_WORKFLOW},
        )
        second = await client.put(
            "/admin/workflows/idem_v1",
            headers=_AUTH,
            json={"name": "Atualizado", "definition": VALID_WORKFLOW},
        )
        assert first.json()["id"] == second.json()["id"]
        assert second.json()["name"] == "Atualizado"

        listing = await client.get("/admin/workflows", headers=_AUTH)
        assert len([w for w in listing.json() if w["key"] == "idem_v1"]) == 1

    asyncio.run(run())


def test_tenant_upsert_updates_existing(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        await client.put(
            "/admin/workflows/wf_a",
            headers=_AUTH,
            json={"name": "A", "definition": VALID_WORKFLOW},
        )
        await client.put(
            "/admin/workflows/wf_b",
            headers=_AUTH,
            json={"name": "B", "definition": VALID_WORKFLOW},
        )

        await client.put(
            "/admin/tenants/SAMEPHONE",
            headers=_AUTH,
            json={"name": "Antes", "workflow_key": "wf_a", "active": True},
        )
        updated = await client.put(
            "/admin/tenants/SAMEPHONE",
            headers=_AUTH,
            json={"name": "Depois", "workflow_key": "wf_b", "active": False},
        )
        assert updated.json()["name"] == "Depois"
        assert updated.json()["active"] is False

        listing = await client.get("/admin/tenants", headers=_AUTH)
        assert len(listing.json()) == 1

    asyncio.run(run())
