from app.catalog import format_catalog
from app.helpers.order_agent_helper import _respond

_CATALOG_REPLY = (
    f"Posso te ajudar com o pedido. No momento temos: {format_catalog()}."
)


def test_generic_pizza_request_shows_catalog_before_collecting_address() -> None:
    response = _respond("collecting_order", "Quero pizza")

    assert response.state == "collecting_order"
    assert response.intent == "fallback"
    assert response.reply == _CATALOG_REPLY


def test_generic_pizza_request_during_address_collection_shows_catalog() -> None:
    response = _respond("collecting_address", "Quero pizza")

    assert response.state == "collecting_order"
    assert response.intent == "fallback"
    assert response.reply == _CATALOG_REPLY


def test_specific_catalog_item_request_collects_address() -> None:
    response = _respond("collecting_order", "Quero uma pizza grande de calabresa")

    assert response.state == "collecting_address"
    assert response.intent == "order"
    assert response.reply == (
        "Anotei: Pizza grande de calabresa. Informe o endereco completo de entrega."
    )


def test_catalog_item_without_size_asks_for_size() -> None:
    response = _respond("collecting_order", "Quero calabresa")

    assert response.state == "collecting_size:101"
    assert response.intent == "order"
    assert response.reply == "Qual tamanho da pizza de calabresa? Temos grande ou média."


def test_size_selection_uses_pending_catalog_item() -> None:
    size_prompt = _respond("collecting_order", "Quero muçarela")

    response = _respond(size_prompt.state, "grande")

    assert size_prompt.state == "collecting_size:102"
    assert response.state == "collecting_address"
    assert response.intent == "order"
    assert response.reply == (
        "Anotei: Pizza grande de muçarela. Informe o endereco completo de entrega."
    )


def test_completed_conversation_restarts_on_new_generic_order_request() -> None:
    response = _respond("completed", "Quero uma pizza")

    assert response.state == "collecting_order"
    assert response.intent == "fallback"
    assert response.reply == _CATALOG_REPLY


def test_completed_conversation_keeps_status_for_non_order_message() -> None:
    response = _respond("completed", "obrigado")

    assert response.state == "completed"
    assert response.intent == "confirmation"
    assert response.reply == "Seu pedido ja foi confirmado e enviado ao restaurante."
