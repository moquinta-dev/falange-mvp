from dataclasses import dataclass
from unicodedata import normalize

from sqlalchemy.orm import Session

from app.catalog import (
    CATALOG_ITEMS,
    CatalogItem,
    CatalogMatch,
    find_catalog_item,
    find_catalog_size,
    format_catalog,
    format_order_label,
    format_size_prompt,
    is_catalog_query,
    needs_size_selection,
)
from app.helpers import conversation_helper


@dataclass(frozen=True)
class OrderAgentResult:
    conversation_id: int
    reply: str
    state: str
    intent: str
    order_summary: str | None = None


def handle_message(
    db: Session,
    *,
    external_id: str,
    message: str,
    channel: str = "simulator",
    external_message_id: str | None = None,
) -> OrderAgentResult:
    conversation = conversation_helper.get_or_create_conversation(
        db,
        external_id=external_id,
        channel=channel,
        initial_state="collecting_order",
    )
    conversation_helper.add_message(
        db,
        conversation=conversation,
        direction="inbound",
        content=message,
        external_message_id=external_message_id,
    )

    result = _respond(
        conversation.state,
        message,
        pending_size_item=_pending_size_item_from_recent_messages(db, conversation),
    )
    conversation_helper.update_conversation_state(
        db,
        conversation=conversation,
        state=result.state,
    )
    conversation_helper.add_message(
        db,
        conversation=conversation,
        direction="outbound",
        content=result.reply,
    )

    return OrderAgentResult(
        conversation_id=conversation.id,
        reply=result.reply,
        state=result.state,
        intent=result.intent,
        order_summary=result.order_summary,
    )


@dataclass(frozen=True)
class _AgentDecision:
    reply: str
    state: str
    intent: str
    order_summary: str | None = None


def _respond(
    current_state: str,
    message: str,
    *,
    pending_size_item: CatalogItem | None = None,
) -> _AgentDecision:
    normalized_message = _normalize(message)

    if _should_handoff(normalized_message):
        return _AgentDecision(
            reply="Vou encaminhar seu atendimento para uma pessoa do restaurante.",
            state="handoff",
            intent="handoff",
        )

    pending_size_item = _pending_size_item(current_state) or pending_size_item
    if pending_size_item is not None:
        return _handle_size_selection(pending_size_item, message)

    if current_state in ("new", "collecting_order"):
        return _handle_order_collection(message)

    if current_state == "collecting_address":
        return _handle_address_collection(message)

    if current_state == "confirming_order":
        return _handle_confirmation(normalized_message)

    if current_state == "completed" and _starts_new_order(message):
        return _handle_order_collection(message)

    if current_state == "completed":
        return _AgentDecision(
            reply="Seu pedido ja foi confirmado e enviado ao restaurante.",
            state="completed",
            intent="confirmation",
        )

    return _AgentDecision(
        reply="Nao consegui continuar esse atendimento. Vou chamar uma pessoa do restaurante.",
        state="handoff",
        intent="fallback",
    )


def _catalog_fallback() -> _AgentDecision:
    return _AgentDecision(
        reply=f"Posso te ajudar com o pedido. No momento temos: {format_catalog()}.",
        state="collecting_order",
        intent="fallback",
    )


def _order_from_match(match: CatalogMatch) -> _AgentDecision:
    label = format_order_label(match)
    return _AgentDecision(
        reply=f"Anotei: {label}. Informe o endereco completo de entrega.",
        state="collecting_address",
        intent="order",
        order_summary=label,
    )


def _handle_order_collection(message: str) -> _AgentDecision:
    if is_catalog_query(message) and find_catalog_item(message) is None:
        return _catalog_fallback()

    match = find_catalog_item(message)
    if match is None:
        return _catalog_fallback()

    if needs_size_selection(match):
        return _AgentDecision(
            reply=format_size_prompt(match.item),
            state=_size_selection_state(match.item),
            intent="order",
        )

    return _order_from_match(match)


def _handle_address_collection(message: str) -> _AgentDecision:
    match = find_catalog_item(message)
    if match is not None:
        if needs_size_selection(match):
            return _AgentDecision(
                reply=format_size_prompt(match.item),
                state=_size_selection_state(match.item),
                intent="order",
            )
        return _order_from_match(match)

    if is_catalog_query(message):
        return _catalog_fallback()

    if not _looks_like_address(message):
        return _AgentDecision(
            reply="Informe o endereco completo com rua e numero para entrega.",
            state="collecting_address",
            intent="address",
        )

    return _AgentDecision(
        reply=f"Confirma este endereco para entrega: {message}? Responda sim para enviar o pedido ao restaurante.",
        state="confirming_order",
        intent="address",
    )


def _handle_confirmation(normalized_message: str) -> _AgentDecision:
    if normalized_message in {"sim", "s", "confirmo", "confirmar", "ok", "pode enviar"}:
        return _AgentDecision(
            reply="Pedido confirmado e enviado ao restaurante.",
            state="completed",
            intent="confirmation",
        )

    if normalized_message in {"nao", "n", "corrigir", "errado"}:
        return _AgentDecision(
            reply="Sem problema. Informe o endereco correto para entrega.",
            state="collecting_address",
            intent="address",
        )

    return _AgentDecision(
        reply="Responda sim para confirmar o pedido ou nao para corrigir o endereco.",
        state="confirming_order",
        intent="confirmation",
    )


def _normalize(value: str) -> str:
    ascii_text = normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower().strip().strip(".!,?")


def _looks_like_address(message: str) -> bool:
    normalized_message = _normalize(message)
    has_number = any(character.isdigit() for character in normalized_message)
    has_street_hint = any(
        hint in normalized_message
        for hint in ("rua", "avenida", "av", "travessa", "alameda", "rodovia")
    )
    return has_number and has_street_hint


def _should_handoff(normalized_message: str) -> bool:
    return any(
        token in normalized_message
        for token in ("humano", "atendente", "pessoa", "reclamar", "cancelar")
    )


def _starts_new_order(message: str) -> bool:
    return find_catalog_item(message) is not None or is_catalog_query(message)


def _handle_size_selection(item: CatalogItem, message: str) -> _AgentDecision:
    size = find_catalog_size(message, item)
    if size is not None:
        return _order_from_match(CatalogMatch(item=item, size=size))

    match = find_catalog_item(message)
    if match is not None:
        if needs_size_selection(match):
            return _AgentDecision(
                reply=format_size_prompt(match.item),
                state=_size_selection_state(match.item),
                intent="order",
            )
        return _order_from_match(match)

    if is_catalog_query(message):
        return _catalog_fallback()

    return _AgentDecision(
        reply=format_size_prompt(item),
        state=_size_selection_state(item),
        intent="order",
    )


def _size_selection_state(item: CatalogItem) -> str:
    return f"collecting_size:{item.id}"


def _pending_size_item(current_state: str) -> CatalogItem | None:
    prefix = "collecting_size:"
    if not current_state.startswith(prefix):
        return None

    try:
        item_id = int(current_state.removeprefix(prefix))
    except ValueError:
        return None

    return next((item for item in CATALOG_ITEMS if item.id == item_id), None)


def _pending_size_item_from_recent_messages(db: Session, conversation) -> CatalogItem | None:
    if conversation.state not in ("collecting_order",) and _pending_size_item(conversation.state) is None:
        return None

    for message in conversation_helper.list_recent_messages(db, conversation=conversation, limit=5):
        if message.direction != "outbound":
            continue
        for item in CATALOG_ITEMS:
            if message.content == format_size_prompt(item):
                return item

    return None
