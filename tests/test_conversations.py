import asyncio
from collections.abc import Generator

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base, get_db
from app.main import app


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


def test_create_conversation_is_idempotent(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        payload = {"external_id": "whatsapp:+5571999999999"}

        first_response = await client.post("/conversations", json=payload)
        second_response = await client.post("/conversations", json=payload)

        assert first_response.status_code == 201
        assert second_response.status_code == 201
        assert first_response.json()["id"] == second_response.json()["id"]
        assert first_response.json()["state"] == "new"

    asyncio.run(run())


def test_conversation_message_and_state_flow(client: httpx.AsyncClient) -> None:
    async def run() -> None:
        conversation_response = await client.post(
            "/conversations",
            json={"external_id": "whatsapp:+5571888888888"},
        )
        conversation_id = conversation_response.json()["id"]

        message_response = await client.post(
            f"/conversations/{conversation_id}/messages",
            json={
                "direction": "inbound",
                "content": "Quero uma pizza grande de calabresa",
                "external_message_id": "wamid.test-message",
            },
        )
        state_response = await client.patch(
            f"/conversations/{conversation_id}/state",
            json={"state": "collecting_address"},
        )
        messages_response = await client.get(f"/conversations/{conversation_id}/messages")

        assert message_response.status_code == 201
        assert message_response.json()["conversation_id"] == conversation_id
        assert state_response.status_code == 200
        assert state_response.json()["state"] == "collecting_address"
        assert messages_response.status_code == 200
        assert messages_response.json()[0]["content"] == "Quero uma pizza grande de calabresa"

    asyncio.run(run())
