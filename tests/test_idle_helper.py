from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.core.settings import Settings
from app.helpers import conversation_helper, workflow_engine
from app.helpers.idle_helper import (
    ABANDONED_STATE,
    IDLE_FAREWELL_MESSAGE,
    IDLE_NUDGE_MESSAGE,
    is_continue_token,
    sweep_idle_conversations,
)
from app.models import Conversation, Message, Tenant, Workflow

_MINIMAL_WORKFLOW = {
    "start": "ask_name",
    "nodes": {
        "ask_name": {
            "type": "text",
            "prompt": "Nome?",
            "collect": "nome",
            "next": "done",
        },
        "done": {"type": "terminal"},
    },
}


class _FakeWhatsApp:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send_text_sync(self, *, to, text, phone_number_id=None) -> dict:
        self.sent.append({"to": to, "text": text, "phone_number_id": phone_number_id})
        return {"messages": [{"id": "wamid.fake"}]}


@pytest.fixture()
def db(tmp_path) -> Generator[Session, None, None]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'idle.db'}", connect_args={"check_same_thread": False}
    )
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _settings(**overrides) -> Settings:
    base = Settings(
        idle_sweep_enabled=True,
        idle_nudge_after_minutes=20,
        idle_abandon_after_nudge_minutes=15,
        whatsapp_access_token="token",
        whatsapp_phone_number_id="phone",
    )
    for key, value in overrides.items():
        object.__setattr__(base, key, value)
    return base


def _seed_tenant_conversation(db: Session) -> tuple[Tenant, Conversation]:
    workflow = Workflow(key="wf_v1", name="Test", definition=_MINIMAL_WORKFLOW)
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    tenant = Tenant(
        name="Natália",
        whatsapp_phone_number_id="1125270987344850",
        workflow_id=workflow.id,
        active=True,
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    conversation = conversation_helper.get_or_create_conversation(
        db,
        external_id=f"whatsapp:{tenant.id}:5571999999999",
        tenant_id=tenant.id,
    )
    conversation_helper.update_workflow_state(
        db,
        conversation=conversation,
        current_node_id="ask_name",
        answers={},
        state="ask_name",
    )
    return tenant, conversation


def _add_inbound(db: Session, conversation: Conversation, text: str, *, minutes_ago: int) -> None:
    created_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    message = Message(
        conversation_id=conversation.id,
        direction="inbound",
        content=text,
        created_at=created_at,
    )
    db.add(message)
    db.commit()


def test_is_continue_token() -> None:
    assert is_continue_token("1")
    assert is_continue_token(" 1 ")
    assert is_continue_token("continuar")
    assert not is_continue_token("2")
    assert not is_continue_token("Marina")


def test_sweep_sends_nudge_after_idle(db: Session) -> None:
    _tenant, conversation = _seed_tenant_conversation(db)
    _add_inbound(db, conversation, "oi", minutes_ago=25)
    client = _FakeWhatsApp()

    result = sweep_idle_conversations(
        db, settings=_settings(), whatsapp_client=client  # type: ignore[arg-type]
    )

    assert result.nudges_sent == 1
    assert result.abandoned == 0
    assert len(client.sent) == 1
    assert client.sent[0]["text"] == IDLE_NUDGE_MESSAGE
    db.refresh(conversation)
    assert conversation.idle_nudge_sent_at is not None


def test_sweep_abandons_after_nudge_without_reply(db: Session) -> None:
    _tenant, conversation = _seed_tenant_conversation(db)
    _add_inbound(db, conversation, "oi", minutes_ago=40)
    conversation.answers = {"nome": "Marina"}
    conversation.idle_nudge_sent_at = datetime.now(timezone.utc) - timedelta(minutes=20)
    db.add(conversation)
    db.commit()
    client = _FakeWhatsApp()

    result = sweep_idle_conversations(
        db, settings=_settings(), whatsapp_client=client  # type: ignore[arg-type]
    )

    assert result.abandoned == 1
    assert client.sent[-1]["text"] == IDLE_FAREWELL_MESSAGE
    db.refresh(conversation)
    assert conversation.state == ABANDONED_STATE
    assert conversation.abandoned_at is not None
    assert conversation.answers == {"nome": "Marina"}


def test_sweep_disabled_is_noop(db: Session) -> None:
    _seed_tenant_conversation(db)
    client = _FakeWhatsApp()
    result = sweep_idle_conversations(
        db,
        settings=_settings(idle_sweep_enabled=False),
        whatsapp_client=client,  # type: ignore[arg-type]
    )
    assert result.nudges_sent == 0
    assert result.abandoned == 0
    assert client.sent == []


def test_message_after_abandon_restarts_triagem(db: Session) -> None:
    _tenant, conversation = _seed_tenant_conversation(db)
    conversation.state = ABANDONED_STATE
    conversation.abandoned_at = datetime.now(timezone.utc)
    conversation.current_node_id = "ask_name"
    conversation.answers = {"nome": "Marina"}
    db.add(conversation)
    db.commit()

    result = workflow_engine.handle_message(
        db,
        conversation=conversation,
        workflow=_MINIMAL_WORKFLOW,
        message="oi de novo",
    )

    assert result.reply == "Nome?"
    assert result.current_node_id == "ask_name"
    assert conversation.answers == {}
    assert conversation.abandoned_at is None


def test_reprompt_current_does_not_advance(db: Session) -> None:
    _tenant, conversation = _seed_tenant_conversation(db)
    conversation.answers = {"nome": "Ana"}
    conversation.current_node_id = "ask_name"
    db.add(conversation)
    db.commit()

    result = workflow_engine.reprompt_current(
        db,
        conversation=conversation,
        workflow=_MINIMAL_WORKFLOW,
        message="1",
    )

    assert result.reply == "Nome?"
    assert conversation.answers == {"nome": "Ana"}
    inbound_count = db.scalar(
        select(Message).where(
            Message.conversation_id == conversation.id,
            Message.direction == "inbound",
        )
    )
    assert inbound_count is not None
