from app.helpers import wizard_message_helper
from app.seed import DISCOVERY_V1

_WIZARD_MESSAGE = """Olá! Acabei de criar meu agente na Falange Labs.

Segmento: Clínica
Pergunta do cliente: Qual o horário de funcionamento?
Resposta do meu agente: Atendemos de segunda a sexta, das 8h às 18h.

Meu WhatsApp: 71999998888
Nome: Marcos

Quero receber esse fluxo e saber mais sobre o piloto."""

_SECONDARY_CTA_MESSAGE = (
    "Olá! Quero falar com o assistente virtual da Falange Labs."
)


def test_is_wizard_message() -> None:
    assert wizard_message_helper.is_wizard_whatsapp_message(_WIZARD_MESSAGE)
    assert not wizard_message_helper.is_wizard_whatsapp_message(_SECONDARY_CTA_MESSAGE)


def test_parse_wizard_message_extracts_name_and_fields() -> None:
    parsed = wizard_message_helper.parse_wizard_whatsapp_message(_WIZARD_MESSAGE)

    assert parsed is not None
    assert parsed["wizard_name"] == "Marcos"
    assert parsed["wizard_segment"] == "Clínica"
    assert parsed["wizard_phone"] == "71999998888"
    assert "horário de funcionamento" in parsed["wizard_question"]


def test_parse_secondary_cta_returns_none() -> None:
    assert wizard_message_helper.parse_wizard_whatsapp_message(_SECONDARY_CTA_MESSAGE) is None


def test_contact_question_uses_name_when_known() -> None:
    assert "Marcos" in wizard_message_helper.contact_question("Marcos")
    assert "qual é o seu nome" not in wizard_message_helper.contact_question("Marcos")
    assert "qual é o seu nome" in wizard_message_helper.contact_question(None)


def test_normalize_contact_answer_prepends_wizard_name() -> None:
    assert (
        wizard_message_helper.normalize_contact_answer("18h", "Marcos")
        == "Marcos, 18h"
    )
    assert (
        wizard_message_helper.normalize_contact_answer("Marcos, 18h", "Marcos")
        == "Marcos, 18h"
    )


def test_merge_wizard_metadata_on_first_message() -> None:
    merged = wizard_message_helper.merge_wizard_metadata({}, _WIZARD_MESSAGE)

    assert merged["wizard_name"] == "Marcos"
    assert wizard_message_helper.merge_wizard_metadata({}, _SECONDARY_CTA_MESSAGE) == {}
