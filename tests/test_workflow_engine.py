from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.helpers import conversation_helper, workflow_engine
from app.models import Conversation

# Árvore com ramificação (espelha a triagem da Natália, reduzida).
TRIAGEM = {
    "start": "ask_name",
    "nodes": {
        "ask_name": {
            "type": "text",
            "prompt": "Como é o seu nome?",
            "collect": "nome",
            "next": "ask_interest",
        },
        "ask_interest": {
            "type": "choice",
            "prompt": "Você está interessada em:",
            "collect": "interesse",
            "options": [
                {"label": "Aulas de Personal", "next": "personal_mod"},
                {"label": "Aulas de Yoga", "next": "yoga_mod"},
            ],
        },
        "personal_mod": {
            "type": "choice",
            "prompt": "Personal: online ou presencial?",
            "collect": "modalidade",
            "options": [
                {"label": "Online", "next": "done"},
                {"label": "Presencial", "next": "done"},
            ],
        },
        "yoga_mod": {
            "type": "choice",
            "prompt": "Yoga: particular ou em grupo?",
            "collect": "modalidade",
            "options": [
                {"label": "Particular", "next": "done"},
                {"label": "Em grupo", "next": "done"},
            ],
        },
        "done": {"type": "terminal", "summary": True},
    },
}


@pytest.fixture()
def db(tmp_path) -> Generator[Session, None, None]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
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


def _conversation(db: Session, external_id: str = "whatsapp:5571") -> Conversation:
    return conversation_helper.get_or_create_conversation(db, external_id=external_id)


def _send(db: Session, conversation: Conversation, text: str):
    return workflow_engine.handle_message(
        db, conversation=conversation, workflow=TRIAGEM, message=text
    )


def test_first_contact_presents_start_node_without_consuming(db: Session) -> None:
    conversation = _conversation(db)
    result = _send(db, conversation, "oi")

    assert result.reply == "Como é o seu nome?"
    assert result.current_node_id == "ask_name"
    assert result.completed is False
    assert (conversation.answers or {}) == {}


def test_text_then_choice_renders_numbered_options(db: Session) -> None:
    conversation = _conversation(db)
    _send(db, conversation, "oi")
    result = _send(db, conversation, "Marina")

    assert conversation.answers["nome"] == "Marina"
    assert result.current_node_id == "ask_interest"
    assert result.reply == "Você está interessada em:\n1. Aulas de Personal\n2. Aulas de Yoga"


def test_choice_by_number_branches_and_completes(db: Session) -> None:
    conversation = _conversation(db)
    _send(db, conversation, "oi")
    _send(db, conversation, "Marina")
    _send(db, conversation, "1")  # Aulas de Personal
    result = _send(db, conversation, "1")  # Online -> done

    assert conversation.answers["interesse"] == "Aulas de Personal"
    assert conversation.answers["modalidade"] == "Online"
    assert result.completed is True
    assert result.state == workflow_engine.COMPLETED_STATE
    assert "Nome: Marina" in result.reply
    assert result.summary is not None


def test_choice_by_label_is_accepted(db: Session) -> None:
    conversation = _conversation(db)
    _send(db, conversation, "oi")
    _send(db, conversation, "Marina")
    result = _send(db, conversation, "Aulas de Yoga")

    assert conversation.answers["interesse"] == "Aulas de Yoga"
    assert result.current_node_id == "yoga_mod"


def test_invalid_choice_reprompts_without_advancing(db: Session) -> None:
    conversation = _conversation(db)
    _send(db, conversation, "oi")
    _send(db, conversation, "Marina")
    result = _send(db, conversation, "talvez")

    assert result.current_node_id == "ask_interest"
    assert result.reply.startswith("Você está interessada em:")
    assert "interesse" not in (conversation.answers or {})


def test_empty_text_reasks(db: Session) -> None:
    conversation = _conversation(db)
    _send(db, conversation, "oi")
    result = _send(db, conversation, "   ")

    assert result.current_node_id == "ask_name"
    assert result.reply.startswith(workflow_engine.REASK_PREFIX)


def test_handoff_short_circuits(db: Session) -> None:
    conversation = _conversation(db)
    _send(db, conversation, "oi")
    result = _send(db, conversation, "quero falar com um humano")

    assert result.state == workflow_engine.HANDOFF_STATE
    assert result.reply == workflow_engine.HANDOFF_REPLY
    assert conversation.handed_off_at is not None


def test_message_after_completion_returns_followup(db: Session) -> None:
    conversation = _conversation(db)
    _send(db, conversation, "oi")
    _send(db, conversation, "Marina")
    _send(db, conversation, "1")
    _send(db, conversation, "1")  # completa
    result = _send(db, conversation, "obrigada")

    assert result.reply == workflow_engine.COMPLETED_FOLLOWUP
    assert result.completed is False
