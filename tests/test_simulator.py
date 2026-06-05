import asyncio
from collections.abc import Generator

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.catalog import format_catalog
from app.core.database import Base, get_db
from app.main import app

_CATALOG_REPLY = (
    f"Posso te ajudar com o pedido. No momento temos: {format_catalog()}."
)


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


def test_simulator_completes_basic_order_flow(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        external_id = "simulator-user-1"

        order_response = await client.post(
            "/simulator/messages",
            json={
                "external_id": external_id,
                "message": "Quero uma pizza grande de calabresa",
            },
        )
        conversation_id = order_response.json()["conversation_id"]

        address_response = await client.post(
            "/simulator/messages",
            json={
                "external_id": external_id,
                "message": "Rua das Flores 120",
            },
        )
        confirmation_response = await client.post(
            "/simulator/messages",
            json={
                "external_id": external_id,
                "message": "sim",
            },
        )

        assert order_response.status_code == 200
        assert order_response.json()["state"] == "collecting_address"
        assert order_response.json()["intent"] == "order"
        assert address_response.status_code == 200
        assert address_response.json()["state"] == "confirming_order"
        assert confirmation_response.status_code == 200
        assert confirmation_response.json()["state"] == "completed"
        assert confirmation_response.json()["conversation_id"] == conversation_id

    asyncio.run(run())


def test_simulator_persists_inbound_and_outbound_messages(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        response = await client.post(
            "/simulator/messages",
            json={
                "external_id": "simulator-user-2",
                "message": "Quero uma pizza grande de calabresa",
            },
        )
        conversation_id = response.json()["conversation_id"]

        messages_response = await client.get(f"/conversations/{conversation_id}/messages")
        messages = messages_response.json()

        assert messages_response.status_code == 200
        assert len(messages) == 2
        assert {message["direction"] for message in messages} == {"inbound", "outbound"}

    asyncio.run(run())


def test_simulator_shows_catalog_for_generic_pizza_request(
    client: httpx.AsyncClient,
) -> None:
    async def run() -> None:
        response = await client.post(
            "/simulator/messages",
            json={
                "external_id": "simulator-user-generic-pizza",
                "message": "Quero pizza",
            },
        )

        assert response.status_code == 200
        assert response.json()["state"] == "collecting_order"
        assert response.json()["intent"] == "fallback"
        assert response.json()["reply"] == _CATALOG_REPLY

    asyncio.run(run())


def test_simulator_shows_catalog_for_generic_pizza_request_while_collecting_address(
    client: httpx.AsyncClient,
) -> None:
    async def run() -> None:
        external_id = "simulator-user-address-then-generic-pizza"
        await client.post(
            "/simulator/messages",
            json={
                "external_id": external_id,
                "message": "Quero uma pizza grande de calabresa",
            },
        )

        response = await client.post(
            "/simulator/messages",
            json={
                "external_id": external_id,
                "message": "Quero pizza",
            },
        )

        assert response.status_code == 200
        assert response.json()["state"] == "collecting_order"
        assert response.json()["intent"] == "fallback"
        assert response.json()["reply"] == _CATALOG_REPLY

    asyncio.run(run())


def test_simulator_handoff_request_updates_state(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        response = await client.post(
            "/simulator/messages",
            json={
                "external_id": "simulator-user-3",
                "message": "quero falar com um atendente",
            },
        )

        assert response.status_code == 200
        assert response.json()["state"] == "handoff"
        assert response.json()["intent"] == "handoff"

    asyncio.run(run())
