import asyncio
import hashlib
import hmac
import json
from collections.abc import Generator

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base, get_db
from app.core.settings import get_settings
from app.helpers.whatsapp_cloud_client import get_whatsapp_client
from app.main import app


class FakeWhatsAppClient:
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []
        self.error: httpx.HTTPError | None = None

    async def send_text(self, *, to: str, text: str) -> dict[str, object]:
        if self.error is not None:
            raise self.error
        self.sent.append({"to": to, "text": text})
        return {"messages": [{"id": "wamid.outbound-test"}]}


@pytest.fixture()
def whatsapp_client(tmp_path, monkeypatch) -> Generator[tuple[httpx.AsyncClient, FakeWhatsAppClient], None, None]:
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "test-verify-token")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "test-access-token")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "123456789")
    monkeypatch.setenv("META_APP_SECRET", "test-app-secret")
    monkeypatch.setenv("META_VALIDATE_SIGNATURE", "false")
    get_settings.cache_clear()

    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    fake_client = FakeWhatsAppClient()

    async def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_whatsapp_client] = lambda: fake_client
    transport = httpx.ASGITransport(app=app)
    async_client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
    try:
        yield async_client, fake_client
    finally:
        asyncio.run(async_client.aclose())
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        get_settings.cache_clear()


def _message_payload(message_id: str = "wamid.test001") -> dict[str, object]:
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "5571999999999",
                                    "id": message_id,
                                    "type": "text",
                                    "text": {"body": "quero uma pizza grande de calabresa"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }


def test_whatsapp_webhook_verification(whatsapp_client) -> None:
    async def run() -> None:
        client, _ = whatsapp_client

        response = await client.get(
            "/webhook/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "test-verify-token",
                "hub.challenge": "123",
            },
        )

        assert response.status_code == 200
        assert response.text == "123"

    asyncio.run(run())


def test_whatsapp_webhook_rejects_invalid_verify_token(whatsapp_client) -> None:
    async def run() -> None:
        client, _ = whatsapp_client

        response = await client.get(
            "/webhook/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-token",
                "hub.challenge": "123",
            },
        )

        assert response.status_code == 403

    asyncio.run(run())


def test_whatsapp_webhook_receives_message_and_sends_reply(whatsapp_client) -> None:
    async def run() -> None:
        client, fake_client = whatsapp_client

        response = await client.post("/webhook/whatsapp", json=_message_payload())

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["conversation_id"] > 0
        assert fake_client.sent == [
            {
                "to": "5571999999999",
                "text": "Anotei: Pizza grande de calabresa. Informe o endereco completo de entrega.",
            }
        ]

        messages_response = await client.get(
            f"/conversations/{response.json()['conversation_id']}/messages"
        )
        messages = messages_response.json()

        assert messages_response.status_code == 200
        assert len(messages) == 2
        assert messages[1]["external_message_id"] == "wamid.test001"
        assert {message["direction"] for message in messages} == {"inbound", "outbound"}

    asyncio.run(run())


def test_whatsapp_webhook_ignores_event_without_message(whatsapp_client) -> None:
    async def run() -> None:
        client, fake_client = whatsapp_client
        payload = {"entry": [{"changes": [{"value": {"statuses": [{"id": "wamid.status"}]}}]}]}

        response = await client.post("/webhook/whatsapp", json=payload)

        assert response.status_code == 200
        assert response.json() == {"status": "ignored"}
        assert fake_client.sent == []

    asyncio.run(run())


def test_whatsapp_webhook_is_idempotent_by_message_id(whatsapp_client) -> None:
    async def run() -> None:
        client, fake_client = whatsapp_client
        payload = _message_payload("wamid.duplicate")

        first_response = await client.post("/webhook/whatsapp", json=payload)
        second_response = await client.post("/webhook/whatsapp", json=payload)

        assert first_response.status_code == 200
        assert first_response.json()["status"] == "ok"
        assert second_response.status_code == 200
        assert second_response.json()["status"] == "duplicate"
        assert len(fake_client.sent) == 1

    asyncio.run(run())


def test_whatsapp_webhook_acks_when_reply_send_fails(whatsapp_client) -> None:
    async def run() -> None:
        client, fake_client = whatsapp_client
        request = httpx.Request("POST", "https://graph.facebook.com/v23.0/123456789/messages")
        response = httpx.Response(
            400,
            request=request,
            json={
                "error": {
                    "message": "(#100) Invalid parameter",
                    "type": "OAuthException",
                    "code": 100,
                    "fbtrace_id": "test-trace",
                }
            },
        )
        fake_client.error = httpx.HTTPStatusError(
            "Client error '400 Bad Request'",
            request=request,
            response=response,
        )

        webhook_response = await client.post("/webhook/whatsapp", json=_message_payload())

        assert webhook_response.status_code == 200
        assert webhook_response.json()["status"] == "reply_failed"
        assert webhook_response.json()["conversation_id"] > 0

    asyncio.run(run())


def test_whatsapp_webhook_validates_signature_when_enabled(
    whatsapp_client,
    monkeypatch,
) -> None:
    async def run() -> None:
        client, _ = whatsapp_client
        monkeypatch.setenv("META_VALIDATE_SIGNATURE", "true")
        get_settings.cache_clear()
        body = json.dumps(_message_payload()).encode("utf-8")
        signature = hmac.new(b"test-app-secret", body, hashlib.sha256).hexdigest()

        invalid_response = await client.post(
            "/webhook/whatsapp",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        valid_response = await client.post(
            "/webhook/whatsapp",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": f"sha256={signature}",
            },
        )

        assert invalid_response.status_code == 403
        assert valid_response.status_code == 200

    asyncio.run(run())
