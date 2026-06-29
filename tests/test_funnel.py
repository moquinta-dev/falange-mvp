import asyncio
from collections.abc import Generator

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base, get_db
from app.main import app

_BUSINESS_ANSWERS = [
    "Tenho uma loja de roupas femininas",
    "WhatsApp e Instagram",
    "Demoro muito para responder e perco vendas",
    "Quero qualificar quem chega antes de passar para mim",
    "Uns 40 atendimentos por dia",
    "João, depois das 18h",
]


@pytest.fixture()
def client(tmp_path) -> Generator[httpx.AsyncClient, None, None]:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

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
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


async def _send(client: httpx.AsyncClient, external_id: str, message: str) -> httpx.Response:
    return await client.post(
        "/simulator/messages",
        json={"external_id": external_id, "message": message},
    )


async def _run_full_discovery(client: httpx.AsyncClient, external_id: str) -> None:
    await _send(client, external_id, "Quero automatizar meu atendimento")
    for answer in _BUSINESS_ANSWERS:
        await _send(client, external_id, answer)
    await _send(client, external_id, "sim")


def test_completed_discovery_creates_qualified_lead(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        await _run_full_discovery(client, "whatsapp:+5571999999999")

        leads_response = await client.get("/leads")
        leads = leads_response.json()

        assert leads_response.status_code == 200
        assert len(leads) == 1
        lead = leads[0]
        assert lead["status"] == "qualified"
        assert lead["phone"] == "+5571999999999"
        assert lead["business"] == _BUSINESS_ANSWERS[0]
        assert lead["goal"] == _BUSINESS_ANSWERS[3]
        assert lead["name"] == "João"

    asyncio.run(run())


def test_handoff_creates_handoff_lead(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        external_id = "whatsapp:+5571888888888"
        await _send(client, external_id, "Quero automatizar meu atendimento")
        await _send(client, external_id, "Prefiro falar com um atendente humano")

        leads = (await client.get("/leads", params={"status": "handoff"})).json()

        assert len(leads) == 1
        assert leads[0]["status"] == "handoff"
        assert leads[0]["phone"] == "+5571888888888"

    asyncio.run(run())


def test_funnel_metrics_reflect_completed_and_handoff(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        await _run_full_discovery(client, "whatsapp:+5571111111111")

        handoff_id = "whatsapp:+5571222222222"
        await _send(client, handoff_id, "Quero automatizar meu atendimento")
        await _send(client, handoff_id, "Quero falar com um atendente")

        metrics = (await client.get("/funnel/metrics")).json()

        assert metrics["total_conversations"] == 2
        assert metrics["terminal_conversations"] == 2
        assert metrics["completed_without_human"] == 1
        assert metrics["handed_off"] == 1
        assert metrics["pct_completed_without_human"] == 50.0
        assert metrics["pct_handoff"] == 50.0
        assert metrics["avg_handle_time_seconds"] is not None

    asyncio.run(run())


def test_landing_event_is_recorded(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        response = await client.post(
            "/funnel/landing-events",
            json={
                "event_type": "whatsapp_click",
                "session_id": "sess-123",
                "path": "/",
                "utm_source": "instagram",
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["event_type"] == "whatsapp_click"
        assert body["utm_source"] == "instagram"
        assert body["id"] > 0

    asyncio.run(run())


def test_wizard_lead_is_recorded(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        response = await client.post(
            "/funnel/wizard-leads",
            json={
                "session_id": "sess-wizard-1",
                "segment": "Clínica",
                "question": "Quanto custa a consulta?",
                "answer": "As consultas custam R$250. Atendemos de segunda a sexta.",
                "phone": "(71) 99999-0000",
                "name": "Ana",
                "email": "ana@example.com",
                "consent": True,
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["source"] == "wizard"
        assert body["business"] == "Clínica"
        assert body["pain"] == "Quanto custa a consulta?"
        assert body["phone"] == "+5571999990000"
        assert body["name"] == "Ana"
        assert body["contact"] == "ana@example.com"

        leads = (await client.get("/leads", params={"status": "new"})).json()
        assert any(lead["id"] == body["id"] for lead in leads)

    asyncio.run(run())


def test_wizard_lead_rejects_missing_consent(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        response = await client.post(
            "/funnel/wizard-leads",
            json={
                "segment": "Clínica",
                "question": "Quanto custa a consulta?",
                "answer": "R$250",
                "phone": "71999990000",
                "consent": False,
            },
        )

        assert response.status_code == 422

    asyncio.run(run())


def test_lead_status_update_supports_followup(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        created = await client.post(
            "/leads",
            json={"name": "Maria", "phone": "+5571000000000", "source": "manual"},
        )
        lead_id = created.json()["id"]

        updated = await client.patch(f"/leads/{lead_id}/status", json={"status": "contacted"})

        assert created.status_code == 201
        assert updated.status_code == 200
        assert updated.json()["status"] == "contacted"

    asyncio.run(run())
