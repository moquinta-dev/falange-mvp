import asyncio
from collections.abc import Generator

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base, get_db
from app.helpers.discovery_agent_helper import (
    COMPLETED_REPLY,
    DISCOVERY_STEPS,
    GREETING,
    SUMMARY_HEADER,
)
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


def test_simulator_first_message_greets_and_starts_discovery(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        response = await _send(client, "simulator-user-1", "Quero automatizar meu atendimento")

        assert response.status_code == 200
        assert response.json()["state"] == "collecting_business"
        assert response.json()["intent"] == "greeting"
        assert response.json()["reply"] == GREETING + DISCOVERY_STEPS[0].question

    asyncio.run(run())


def test_simulator_runs_guided_discovery_until_completed(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        external_id = "simulator-user-flow"

        first = await _send(client, external_id, "Quero automatizar meu atendimento")
        conversation_id = first.json()["conversation_id"]

        for answer in _BUSINESS_ANSWERS:
            step_response = await _send(client, external_id, answer)

        summary_payload = step_response.json()
        assert summary_payload["state"] == "confirming_summary"
        assert summary_payload["intent"] == "summary"
        assert summary_payload["summary"].startswith(SUMMARY_HEADER)
        for step, answer in zip(DISCOVERY_STEPS, _BUSINESS_ANSWERS):
            assert f"- {step.label}: {answer}" in summary_payload["summary"]

        confirmation = await _send(client, external_id, "sim")

        assert confirmation.status_code == 200
        assert confirmation.json()["state"] == "completed"
        assert confirmation.json()["intent"] == "confirmation"
        assert confirmation.json()["reply"] == COMPLETED_REPLY
        assert confirmation.json()["conversation_id"] == conversation_id

    asyncio.run(run())


def test_simulator_persists_inbound_and_outbound_messages(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        response = await _send(client, "simulator-user-2", "Quero automatizar meu atendimento")
        conversation_id = response.json()["conversation_id"]

        messages_response = await client.get(f"/conversations/{conversation_id}/messages")
        messages = messages_response.json()

        assert messages_response.status_code == 200
        assert len(messages) == 2
        assert {message["direction"] for message in messages} == {"inbound", "outbound"}

    asyncio.run(run())


def test_simulator_handoff_request_updates_state(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        response = await _send(client, "simulator-user-3", "quero falar com um atendente")

        assert response.status_code == 200
        assert response.json()["state"] == "handoff"
        assert response.json()["intent"] == "handoff"

    asyncio.run(run())
