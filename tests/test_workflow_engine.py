from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.helpers import conversation_helper, workflow_engine
from app.models import Conversation
from app.seed import DISCOVERY_V1, TRIAGEM_PERSONAL_V2

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


def test_message_after_completion_restarts_flow(db: Session) -> None:
    conversation = _conversation(db)
    _send(db, conversation, "oi")
    _send(db, conversation, "Marina")
    _send(db, conversation, "1")
    _send(db, conversation, "1")  # completa
    result = _send(db, conversation, "oi de novo")

    # Nova mensagem numa conversa concluída inicia uma nova triagem, sem loop.
    assert result.reply == "Como é o seu nome?"
    assert result.current_node_id == "ask_name"
    assert result.completed is False
    assert (conversation.answers or {}) == {}


def test_stale_node_id_restarts_flow(db: Session) -> None:
    conversation = _conversation(db)
    _send(db, conversation, "oi")
    # Simula uma conversa apontando para um nó que não existe mais na definição
    # (workflow alterado após o cadastro do adopter).
    conversation.current_node_id = "no_longer_exists"
    result = _send(db, conversation, "oi")

    assert result.reply == "Como é o seu nome?"
    assert result.current_node_id == "ask_name"
    assert result.completed is False


def test_show_options_false_does_not_append_numbered_list(db: Session) -> None:
    workflow = {
        "start": "pick",
        "nodes": {
            "pick": {
                "type": "choice",
                "prompt": "Escolha:\n1️⃣ Opção A\n2️⃣ Opção B",
                "collect": "x",
                "show_options": False,
                "options": [
                    {"label": "Opção A", "next": "done"},
                    {"label": "Opção B", "next": "done"},
                ],
            },
            "done": {"type": "terminal"},
        },
    }
    conversation = _conversation(db)
    result = workflow_engine.handle_message(
        db, conversation=conversation, workflow=workflow, message="oi"
    )
    assert result.reply == "Escolha:\n1️⃣ Opção A\n2️⃣ Opção B"
    assert "\n1. Opção A" not in result.reply


def test_prompt_interpolates_collected_answers(db: Session) -> None:
    workflow = {
        "start": "ask_name",
        "nodes": {
            "ask_name": {
                "type": "text",
                "prompt": "Nome?",
                "collect": "nome",
                "next": "confirm",
            },
            "confirm": {
                "type": "choice",
                "prompt": "Olá, {nome}! Confirma?",
                "show_options": False,
                "options": [{"label": "Sim", "next": "done"}],
            },
            "done": {"type": "terminal", "reply": "Até, {nome}!"},
        },
    }
    conversation = _conversation(db)
    workflow_engine.handle_message(
        db, conversation=conversation, workflow=workflow, message="oi"
    )
    workflow_engine.handle_message(
        db, conversation=conversation, workflow=workflow, message="Ana"
    )
    result = workflow_engine.handle_message(
        db, conversation=conversation, workflow=workflow, message="1"
    )
    assert result.reply == "Até, Ana!"
    assert result.completed is True


def test_triagem_v2_personal_flow_with_confirmation(db: Session) -> None:
    conversation = _conversation(db)
    workflow_engine.handle_message(
        db, conversation=conversation, workflow=TRIAGEM_PERSONAL_V2, message="oi"
    )
    workflow_engine.handle_message(
        db, conversation=conversation, workflow=TRIAGEM_PERSONAL_V2, message="Marina"
    )
    workflow_engine.handle_message(
        db, conversation=conversation, workflow=TRIAGEM_PERSONAL_V2, message="32"
    )
    workflow_engine.handle_message(
        db, conversation=conversation, workflow=TRIAGEM_PERSONAL_V2, message="1"
    )
    confirm = workflow_engine.handle_message(
        db, conversation=conversation, workflow=TRIAGEM_PERSONAL_V2, message="2"
    )
    assert "Nome:* Marina" in confirm.reply
    assert "Presencial" in confirm.reply
    assert confirm.current_node_id == "confirm_personal"

    result = workflow_engine.handle_message(
        db, conversation=conversation, workflow=TRIAGEM_PERSONAL_V2, message="1"
    )
    assert result.completed is True
    assert "Prontinho!" in result.reply
    assert conversation.answers["nome"] == "Marina"
    assert conversation.answers["idade"] == "32"
    assert conversation.answers["interesse"] == "Aulas de Personal"
    assert conversation.answers["modalidade"] == "Presencial"

_WIZARD_MESSAGE = """Olá! Acabei de criar meu agente na Falange Labs.

Segmento: Clínica
Pergunta do cliente: Qual o horário?
Resposta do meu agente: Das 8h às 18h.

Meu WhatsApp: 71999998888
Nome: Marcos

Quero receber esse fluxo e saber mais sobre o piloto."""


def _send_discovery(db: Session, conversation: Conversation, text: str):
    return workflow_engine.handle_message(
        db, conversation=conversation, workflow=DISCOVERY_V1, message=text
    )


def test_wizard_lead_gets_personalized_contact_question(db: Session) -> None:
    conversation = _conversation(db)
    _send_discovery(db, conversation, _WIZARD_MESSAGE)
    _send_discovery(db, conversation, "Tenho uma clínica de estética")
    _send_discovery(db, conversation, "WhatsApp")
    _send_discovery(db, conversation, "Demoro para responder")
    _send_discovery(db, conversation, "Agendar consultas")
    result = _send_discovery(db, conversation, "20 por dia")

    assert conversation.answers.get("wizard_name") == "Marcos"
    assert "Marcos" in result.reply
    assert "qual é o seu nome" not in result.reply
    assert "melhor horário" in result.reply


def test_wizard_contact_answer_combines_name_and_schedule(db: Session) -> None:
    conversation = _conversation(db)
    _send_discovery(db, conversation, _WIZARD_MESSAGE)
    _send_discovery(db, conversation, "Tenho uma clínica")
    _send_discovery(db, conversation, "WhatsApp")
    _send_discovery(db, conversation, "Demoro para responder")
    _send_discovery(db, conversation, "Agendar consultas")
    _send_discovery(db, conversation, "20 por dia")
    result = _send_discovery(db, conversation, "depois das 18h")

    assert conversation.answers["contact"] == "Marcos, depois das 18h"
    assert result.completed is True
    assert "Marcos, depois das 18h" in result.reply


def test_secondary_cta_keeps_default_contact_question(db: Session) -> None:
    conversation = _conversation(db)
    _send_discovery(
        db,
        conversation,
        "Olá! Quero falar com o assistente virtual da Falange Labs.",
    )
    _send_discovery(db, conversation, "Tenho uma loja")
    _send_discovery(db, conversation, "WhatsApp")
    _send_discovery(db, conversation, "Demoro para responder")
    _send_discovery(db, conversation, "Qualificar clientes")
    result = _send_discovery(db, conversation, "30 por dia")

    assert "qual é o seu nome" in result.reply
    assert "Marcos" not in result.reply
