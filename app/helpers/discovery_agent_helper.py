"""Deterministic discovery agent for the Falangelabs PoC.

This helper replaces the previous pizza-order agent. Instead of taking orders
from a static catalog, it runs a guided conversation that leads a lead (who
arrived from the landing page WhatsApp button) to tell us the essence of their
business. The collected answers are summarized and handed off to the human
team. The state machine and output contract are documented in
``docs/prompts/discovery_agent_v1.md`` and are intentionally shaped so a future
AI agent can take over the same flow.
"""

from dataclasses import dataclass
from unicodedata import normalize

from sqlalchemy.orm import Session

from app.helpers import conversation_helper, lead_helper


@dataclass(frozen=True)
class DiscoveryStep:
    key: str
    state: str
    label: str
    question: str


INITIAL_STATE = "new"
CONFIRMATION_STATE = "confirming_summary"
COMPLETED_STATE = "completed"
HANDOFF_STATE = "handoff"

GREETING = (
    "Oi! Eu sou o assistente virtual da Falangelabs e vou te ajudar a entender "
    "como automatizar o seu atendimento no WhatsApp. "
)

DISCOVERY_STEPS: tuple[DiscoveryStep, ...] = (
    DiscoveryStep(
        key="business",
        state="collecting_business",
        label="Negócio",
        question=(
            "Para começar, me conta um pouco sobre o seu negócio: o que a sua "
            "empresa faz e quais produtos ou serviços você oferece?"
        ),
    ),
    DiscoveryStep(
        key="channels",
        state="collecting_channels",
        label="Canais de atendimento",
        question=(
            "Mostra que faz sentido! E hoje, por onde os seus clientes costumam "
            "falar com você? (WhatsApp, telefone, Instagram, site...)"
        ),
    ),
    DiscoveryStep(
        key="pain",
        state="collecting_pain",
        label="Maior dor hoje",
        question=(
            "Entendi. Pensando no atendimento de hoje, qual é a maior "
            "dificuldade ou o que mais consome o seu tempo no dia a dia?"
        ),
    ),
    DiscoveryStep(
        key="goal",
        state="collecting_goal",
        label="O que automatizar primeiro",
        question=(
            "Faz sentido. Se você pudesse automatizar uma coisa primeiro, o que "
            "seria? (ex.: tirar dúvidas, agendar horários, registrar pedidos, "
            "qualificar clientes)"
        ),
    ),
    DiscoveryStep(
        key="volume",
        state="collecting_volume",
        label="Volume de atendimentos",
        question=(
            "Ótimo. Para eu dimensionar melhor: qual é o volume aproximado de "
            "atendimentos que você recebe por dia ou por semana?"
        ),
    ),
    DiscoveryStep(
        key="contact",
        state="collecting_contact",
        label="Contato e melhor horário",
        question=(
            "Perfeito. Por último, qual é o seu nome e o melhor horário para a "
            "nossa equipe falar com você?"
        ),
    ),
)

SUMMARY_HEADER = "Show! Deixa eu confirmar o que entendi sobre o seu negócio:"
CONFIRM_PROMPT = (
    "Está tudo certo? Responda *sim* para eu encaminhar para o nosso time, ou "
    "*não* para ajustarmos."
)
CONFIRM_RETRY = (
    "Só para confirmar: responda *sim* para encaminharmos ao time ou *não* "
    "para ajustarmos as informações."
)
RESTART_PREFIX = "Sem problema, vamos ajustar rapidinho. "
REASK_PREFIX = "Pode me contar com as suas palavras? "
COMPLETED_REPLY = (
    "Maravilha! Registrei tudo e o time da Falangelabs vai te chamar em breve "
    "para mostrar como automatizar o seu atendimento. Obrigado pelas "
    "informações!"
)
COMPLETED_FOLLOWUP = (
    "Já registramos o seu interesse e o time da Falangelabs vai falar com você "
    "em breve. Se precisar de algo agora, é só pedir para falar com uma pessoa."
)
HANDOFF_REPLY = (
    "Claro! Vou encaminhar você para uma pessoa do nosso time. Em breve alguém "
    "entra em contato por aqui."
)

_STEP_BY_STATE = {step.state: step for step in DISCOVERY_STEPS}
_NOT_INFORMED = "(não informado)"
_YES_ANSWERS = {
    "sim",
    "s",
    "isso",
    "isso mesmo",
    "correto",
    "confirmo",
    "confirmar",
    "ok",
    "pode",
    "pode sim",
    "ta certo",
    "esta certo",
    "tudo certo",
    "perfeito",
}
_NO_ANSWERS = {"nao", "n", "errado", "corrigir", "ajustar", "mudar", "refazer"}
_HANDOFF_TOKENS = ("humano", "atendente", "reclamar", "reclamacao", "cancelar")


@dataclass(frozen=True)
class DiscoveryAgentResult:
    conversation_id: int
    reply: str
    state: str
    intent: str
    summary: str | None = None


@dataclass(frozen=True)
class _AgentDecision:
    reply: str
    state: str
    intent: str
    summary: str | None = None


def handle_message(
    db: Session,
    *,
    external_id: str,
    message: str,
    channel: str = "simulator",
    external_message_id: str | None = None,
) -> DiscoveryAgentResult:
    conversation = conversation_helper.get_or_create_conversation(
        db,
        external_id=external_id,
        channel=channel,
        initial_state=INITIAL_STATE,
    )
    previous_state = conversation.state
    conversation_helper.add_message(
        db,
        conversation=conversation,
        direction="inbound",
        content=message,
        external_message_id=external_message_id,
    )

    decision = _respond(
        conversation.state,
        message,
        answers=_recent_answers(db, conversation),
    )
    conversation_helper.update_conversation_state(
        db,
        conversation=conversation,
        state=decision.state,
    )
    conversation_helper.add_message(
        db,
        conversation=conversation,
        direction="outbound",
        content=decision.reply,
    )

    _persist_funnel(db, conversation, decision, previous_state)

    return DiscoveryAgentResult(
        conversation_id=conversation.id,
        reply=decision.reply,
        state=decision.state,
        intent=decision.intent,
        summary=decision.summary,
    )


def _respond(
    current_state: str,
    message: str,
    *,
    answers: list[str] | None = None,
) -> _AgentDecision:
    answers = answers or []
    normalized_message = _normalize(message)

    if _should_handoff(normalized_message):
        return _AgentDecision(
            reply=HANDOFF_REPLY,
            state=HANDOFF_STATE,
            intent="handoff",
        )

    if current_state == INITIAL_STATE:
        first_step = DISCOVERY_STEPS[0]
        return _AgentDecision(
            reply=GREETING + first_step.question,
            state=first_step.state,
            intent="greeting",
        )

    step = _STEP_BY_STATE.get(current_state)
    if step is not None:
        return _advance_from_step(step, message, answers)

    if current_state == CONFIRMATION_STATE:
        return _handle_confirmation(normalized_message)

    if current_state == COMPLETED_STATE:
        return _AgentDecision(
            reply=COMPLETED_FOLLOWUP,
            state=COMPLETED_STATE,
            intent="completed",
        )

    first_step = DISCOVERY_STEPS[0]
    return _AgentDecision(
        reply=GREETING + first_step.question,
        state=first_step.state,
        intent="greeting",
    )


def _advance_from_step(
    step: DiscoveryStep,
    message: str,
    answers: list[str],
) -> _AgentDecision:
    if not message.strip():
        return _AgentDecision(
            reply=REASK_PREFIX + step.question,
            state=step.state,
            intent="discovery",
        )

    index = DISCOVERY_STEPS.index(step)
    if index + 1 < len(DISCOVERY_STEPS):
        next_step = DISCOVERY_STEPS[index + 1]
        return _AgentDecision(
            reply=next_step.question,
            state=next_step.state,
            intent="discovery",
        )

    summary = _format_summary(answers)
    return _AgentDecision(
        reply=f"{summary}\n\n{CONFIRM_PROMPT}",
        state=CONFIRMATION_STATE,
        intent="summary",
        summary=summary,
    )


def _handle_confirmation(normalized_message: str) -> _AgentDecision:
    if normalized_message in _YES_ANSWERS:
        return _AgentDecision(
            reply=COMPLETED_REPLY,
            state=COMPLETED_STATE,
            intent="confirmation",
        )

    if normalized_message in _NO_ANSWERS:
        first_step = DISCOVERY_STEPS[0]
        return _AgentDecision(
            reply=RESTART_PREFIX + first_step.question,
            state=first_step.state,
            intent="discovery",
        )

    return _AgentDecision(
        reply=CONFIRM_RETRY,
        state=CONFIRMATION_STATE,
        intent="confirmation",
    )


def _format_summary(answers: list[str]) -> str:
    tail = list(answers)[-len(DISCOVERY_STEPS):]
    lines = [SUMMARY_HEADER, ""]
    for offset, step in enumerate(DISCOVERY_STEPS):
        value = tail[offset].strip() if offset < len(tail) and tail[offset].strip() else _NOT_INFORMED
        lines.append(f"- {step.label}: {value}")
    return "\n".join(lines)


def _answers_by_key(answers: list[str]) -> dict[str, str]:
    keys = [step.key for step in DISCOVERY_STEPS]
    mapping: dict[str, str] = {}
    for index in range(min(len(answers), len(keys))):
        value = answers[index].strip()
        if value:
            mapping[keys[index]] = value
    return mapping


def _persist_funnel(
    db: Session,
    conversation,
    decision: _AgentDecision,
    previous_state: str,
) -> None:
    """Persiste o lead e os marcos do funil conforme as transições de estado."""

    state = decision.state

    if state == CONFIRMATION_STATE and previous_state != CONFIRMATION_STATE:
        answers = _answers_by_key(_recent_answers(db, conversation))
        lead_helper.upsert_lead_for_conversation(
            db,
            conversation=conversation,
            answers_by_key=answers,
            status="new",
        )
        return

    if state == COMPLETED_STATE and previous_state != COMPLETED_STATE:
        conversation_helper.mark_completed(db, conversation=conversation)
        lead = lead_helper.get_lead_by_conversation(db, conversation.id)
        if lead is None:
            answers = _answers_by_key(_recent_answers(db, conversation))
            lead_helper.upsert_lead_for_conversation(
                db,
                conversation=conversation,
                answers_by_key=answers,
                status="qualified",
            )
        else:
            lead_helper.update_lead_status(db, lead=lead, status="qualified")
        return

    if state == HANDOFF_STATE and previous_state != HANDOFF_STATE:
        conversation_helper.mark_handed_off(db, conversation=conversation)
        lead = lead_helper.get_lead_by_conversation(db, conversation.id)
        if lead is None:
            answers = _answers_by_key(_recent_answers(db, conversation))
            lead_helper.upsert_lead_for_conversation(
                db,
                conversation=conversation,
                answers_by_key=answers,
                status="handoff",
            )
        else:
            lead_helper.update_lead_status(db, lead=lead, status="handoff")


def _recent_answers(db: Session, conversation) -> list[str]:
    count = len(DISCOVERY_STEPS)
    messages = conversation_helper.list_recent_messages(
        db,
        conversation=conversation,
        limit=(count + 1) * 4,
    )
    inbound = [message.content for message in reversed(messages) if message.direction == "inbound"]
    return inbound[-count:]


def _normalize(value: str) -> str:
    ascii_text = normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower().strip().strip(".!,?")


def _should_handoff(normalized_message: str) -> bool:
    return any(token in normalized_message for token in _HANDOFF_TOKENS)
