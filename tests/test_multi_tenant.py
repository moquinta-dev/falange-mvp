import asyncio
from collections.abc import Generator

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app import seed as seed_module
from app.core.database import Base, get_db
from app.core.settings import get_settings
from app.helpers import tenant_helper
from app.helpers.email_client import get_email_client
from app.helpers.whatsapp_cloud_client import get_whatsapp_client
from app.main import app
from app.models import Conversation, Tenant, Workflow

_FALANGE_PHONE_ID = "111000111"
_NATALIA_PHONE_ID = "222000222"


class FakeWhatsAppClient:
    def __init__(self) -> None:
        self.sent: list[dict[str, str | None]] = []

    async def send_text(
        self,
        *,
        to: str,
        text: str,
        phone_number_id: str | None = None,
    ) -> dict[str, object]:
        self.sent.append({"to": to, "text": text, "phone_number_id": phone_number_id})
        return {"messages": [{"id": "wamid.outbound-test"}]}


@pytest.fixture()
def session_factory(tmp_path) -> Generator[sessionmaker, None, None]:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def webhook_client(
    session_factory, monkeypatch
) -> Generator[tuple[httpx.AsyncClient, FakeWhatsAppClient, sessionmaker], None, None]:
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "test-verify-token")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "test-access-token")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "fallback-phone-id")
    monkeypatch.setenv("META_APP_SECRET", "test-app-secret")
    monkeypatch.setenv("META_VALIDATE_SIGNATURE", "false")
    monkeypatch.setenv("REQUIRE_KNOWN_TENANT", "false")
    get_settings.cache_clear()

    fake_client = FakeWhatsAppClient()

    async def override_get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_whatsapp_client] = lambda: fake_client
    transport = httpx.ASGITransport(app=app)
    async_client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
    try:
        yield async_client, fake_client, session_factory
    finally:
        asyncio.run(async_client.aclose())
        app.dependency_overrides.clear()
        get_settings.cache_clear()


_MINIMAL_WORKFLOW = {
    "start": "ask_name",
    "nodes": {
        "ask_name": {
            "type": "text",
            "prompt": "Como é o seu nome?",
            "collect": "nome",
            "next": "done",
        },
        "done": {"type": "terminal", "summary": True},
    },
}


def _seed_tenant(
    session_factory: sessionmaker,
    *,
    name: str,
    phone_number_id: str,
    workflow_key: str = "triagem_personal_v1",
) -> int:
    db = session_factory()
    try:
        workflow = Workflow(
            key=workflow_key, name=name, definition=_MINIMAL_WORKFLOW
        )
        db.add(workflow)
        db.commit()
        db.refresh(workflow)
        tenant = Tenant(
            name=name,
            whatsapp_phone_number_id=phone_number_id,
            workflow_id=workflow.id,
            notify_channel="email",
            notify_target="dona@example.com",
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        return tenant.id
    finally:
        db.close()


def _payload(phone_number_id: str, *, message_id: str = "wamid.mt-1") -> dict[str, object]:
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": phone_number_id},
                            "messages": [
                                {
                                    "from": "5571999999999",
                                    "id": message_id,
                                    "type": "text",
                                    "text": {"body": "Oi"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }


def test_resolve_by_phone_number_id(session_factory: sessionmaker) -> None:
    _seed_tenant(session_factory, name="Natália", phone_number_id=_NATALIA_PHONE_ID)
    db = session_factory()
    try:
        found = tenant_helper.resolve_by_phone_number_id(db, _NATALIA_PHONE_ID)
        assert found is not None
        assert found.name == "Natália"
        assert tenant_helper.resolve_by_phone_number_id(db, "nope") is None
        assert tenant_helper.resolve_by_phone_number_id(db, None) is None
    finally:
        db.close()


def test_resolve_ignores_inactive_tenant(session_factory: sessionmaker) -> None:
    tenant_id = _seed_tenant(session_factory, name="Natália", phone_number_id=_NATALIA_PHONE_ID)
    db = session_factory()
    try:
        tenant = db.get(Tenant, tenant_id)
        tenant.active = False
        db.commit()
        assert tenant_helper.resolve_by_phone_number_id(db, _NATALIA_PHONE_ID) is None
    finally:
        db.close()


def test_webhook_routes_to_tenant_and_sends_from_tenant_number(webhook_client) -> None:
    async def run() -> None:
        client, fake_client, factory = webhook_client
        tenant_id = _seed_tenant(factory, name="Natália", phone_number_id=_NATALIA_PHONE_ID)

        response = await client.post("/webhook/whatsapp", json=_payload(_NATALIA_PHONE_ID))

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert fake_client.sent[-1]["phone_number_id"] == _NATALIA_PHONE_ID

        db = factory()
        try:
            conversation = db.scalar(select(Conversation))
            assert conversation is not None
            assert conversation.tenant_id == tenant_id
        finally:
            db.close()

    asyncio.run(run())


def test_same_sender_across_tenants_gets_distinct_conversations(webhook_client) -> None:
    """O mesmo telefone falando com dois adopters não pode compartilhar conversa.

    Regressão do loop: antes, a conversa era chaveada só pelo remetente, então o
    estado de triagem de um tenant vazava para o outro (ex.: Falangelabs concluía
    e a Natália herdava o nó terminal, respondendo sempre o follow-up).
    """

    async def run() -> None:
        client, _fake_client, factory = webhook_client
        falange_id = _seed_tenant(
            factory,
            name="Falangelabs",
            phone_number_id=_FALANGE_PHONE_ID,
            workflow_key="discovery_v1",
        )
        natalia_id = _seed_tenant(
            factory,
            name="Natália",
            phone_number_id=_NATALIA_PHONE_ID,
            workflow_key="triagem_personal_v1",
        )

        await client.post(
            "/webhook/whatsapp", json=_payload(_FALANGE_PHONE_ID, message_id="wamid.f-1")
        )
        await client.post(
            "/webhook/whatsapp", json=_payload(_NATALIA_PHONE_ID, message_id="wamid.n-1")
        )

        db = factory()
        try:
            conversations = list(db.scalars(select(Conversation)))
            assert len(conversations) == 2
            assert {c.tenant_id for c in conversations} == {falange_id, natalia_id}
            assert {c.external_id for c in conversations} == {
                f"whatsapp:{falange_id}:5571999999999",
                f"whatsapp:{natalia_id}:5571999999999",
            }
        finally:
            db.close()

    asyncio.run(run())


def test_webhook_falls_back_when_tenant_unknown(webhook_client) -> None:
    async def run() -> None:
        client, fake_client, factory = webhook_client

        response = await client.post("/webhook/whatsapp", json=_payload("unregistered-id"))

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        # Sem tenant e sem require_known_tenant: envia pelo phone_number_id do evento.
        assert fake_client.sent[-1]["phone_number_id"] == "unregistered-id"

        db = factory()
        try:
            conversation = db.scalar(select(Conversation))
            assert conversation is not None
            assert conversation.tenant_id is None
        finally:
            db.close()

    asyncio.run(run())


def test_webhook_rejects_unknown_tenant_when_required(webhook_client, monkeypatch) -> None:
    async def run() -> None:
        client, fake_client, _ = webhook_client
        monkeypatch.setenv("REQUIRE_KNOWN_TENANT", "true")
        get_settings.cache_clear()

        response = await client.post("/webhook/whatsapp", json=_payload("unregistered-id"))

        assert response.status_code == 200
        assert response.json()["status"] == "unknown_tenant"
        assert fake_client.sent == []

    asyncio.run(run())


def test_webhook_drives_engine_to_completion(webhook_client) -> None:
    async def run() -> None:
        client, fake_client, factory = webhook_client
        _seed_tenant(factory, name="Natália", phone_number_id=_NATALIA_PHONE_ID)

        # 1ª mensagem: apresenta o nó inicial (sem consumir o texto).
        first = await client.post(
            "/webhook/whatsapp", json=_payload(_NATALIA_PHONE_ID, message_id="wamid.e-1")
        )
        # 2ª mensagem: responde o nome -> alcança o terminal (workflow mínimo).
        second = await client.post(
            "/webhook/whatsapp", json=_payload(_NATALIA_PHONE_ID, message_id="wamid.e-2")
        )

        assert first.json()["status"] == "ok"
        assert fake_client.sent[0]["text"] == "Como é o seu nome?"
        assert second.json()["status"] == "ok"
        assert "Nome: Oi" in fake_client.sent[-1]["text"]

        db = factory()
        try:
            conversation = db.scalar(select(Conversation))
            assert conversation.state == "completed"
            assert conversation.current_node_id == "done"
            assert conversation.completed_at is not None
        finally:
            db.close()

    asyncio.run(run())


class _FakeEmailClient:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, *, to, subject, body) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body})


def test_webhook_notifies_tenant_on_completion(webhook_client, monkeypatch) -> None:
    async def run() -> None:
        client, _fake_whatsapp, factory = webhook_client
        monkeypatch.setenv("NOTIFICATIONS_ENABLED", "true")
        get_settings.cache_clear()
        fake_email = _FakeEmailClient()
        app.dependency_overrides[get_email_client] = lambda: fake_email
        _seed_tenant(factory, name="Natália", phone_number_id=_NATALIA_PHONE_ID)

        # 1ª msg apresenta o nó inicial (sem completar) → nenhuma notificação.
        await client.post(
            "/webhook/whatsapp", json=_payload(_NATALIA_PHONE_ID, message_id="wamid.c-1")
        )
        assert fake_email.sent == []

        # 2ª msg conclui a triagem → exatamente uma notificação ao dono.
        await client.post(
            "/webhook/whatsapp", json=_payload(_NATALIA_PHONE_ID, message_id="wamid.c-2")
        )

        assert len(fake_email.sent) == 1
        notification = fake_email.sent[0]
        assert notification["to"] == "dona@example.com"
        assert notification["subject"].startswith("[Novo Lead Triagem]")
        assert "5571999999999" in notification["body"]
        assert "Ficha de Triagem - Assistente Virtual" in notification["body"]

    asyncio.run(run())


def test_webhook_does_not_notify_when_disabled(webhook_client) -> None:
    async def run() -> None:
        client, _fake_whatsapp, factory = webhook_client
        # notifications_enabled fica False (padrão da fixture).
        fake_email = _FakeEmailClient()
        app.dependency_overrides[get_email_client] = lambda: fake_email
        _seed_tenant(factory, name="Natália", phone_number_id=_NATALIA_PHONE_ID)

        await client.post(
            "/webhook/whatsapp", json=_payload(_NATALIA_PHONE_ID, message_id="wamid.d-1")
        )
        await client.post(
            "/webhook/whatsapp", json=_payload(_NATALIA_PHONE_ID, message_id="wamid.d-2")
        )

        assert fake_email.sent == []

    asyncio.run(run())


def test_seed_is_idempotent(session_factory: sessionmaker, monkeypatch) -> None:
    monkeypatch.setenv("FALANGE_WHATSAPP_PHONE_NUMBER_ID", _FALANGE_PHONE_ID)
    monkeypatch.setenv("NATALIA_WHATSAPP_PHONE_NUMBER_ID", _NATALIA_PHONE_ID)

    db = session_factory()
    try:
        seed_module.seed(db)
        seed_module.seed(db)

        tenants = list(db.scalars(select(Tenant)))
        workflows = list(db.scalars(select(Workflow)))
        assert len(tenants) == 2
        assert {t.whatsapp_phone_number_id for t in tenants} == {
            _FALANGE_PHONE_ID,
            _NATALIA_PHONE_ID,
        }
        assert {w.key for w in workflows} == {
            "discovery_v1",
            "triagem_personal_v1",
            "triagem_personal_v2",
        }
    finally:
        db.close()
