"""Detecta e extrai dados da mensagem pré-preenchida do wizard da landing page.

Leads que concluem o passo 5 abrem o WhatsApp com um texto estruturado
(``buildWizardWhatsAppMessage`` na landing). O CTA secundário usa outra
mensagem genérica e não deve acionar esta lógica.
"""

from typing import Any

WIZARD_MARKER = "Acabei de criar meu agente na Falange Labs"

CONTACT_QUESTION_DEFAULT = (
    "Perfeito. Por último, qual é o seu nome e o melhor horário para a "
    "nossa equipe falar com você?"
)

CONTACT_QUESTION_WITH_NAME = (
    "Perfeito, {name}. Por último, qual é o melhor horário para a nossa "
    "equipe falar com você?"
)

_FIELD_LABELS = {
    "wizard_segment": "Segmento",
    "wizard_question": "Pergunta do cliente",
    "wizard_answer": "Resposta do meu agente",
    "wizard_phone": "Meu WhatsApp",
    "wizard_name": "Nome",
}


def is_wizard_whatsapp_message(message: str) -> bool:
    return WIZARD_MARKER in message


def parse_wizard_whatsapp_message(message: str) -> dict[str, str] | None:
    """Retorna metadados do wizard ou ``None`` se não for mensagem do wizard."""

    if not is_wizard_whatsapp_message(message):
        return None

    parsed: dict[str, str] = {}
    for line in message.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        for key, label in _FIELD_LABELS.items():
            prefix = f"{label}:"
            if stripped.startswith(prefix):
                value = stripped[len(prefix) :].strip()
                if value:
                    parsed[key] = value
                break

    return parsed or {}


def contact_question(wizard_name: str | None) -> str:
    name = (wizard_name or "").strip()
    if name:
        return CONTACT_QUESTION_WITH_NAME.format(name=name)
    return CONTACT_QUESTION_DEFAULT


def normalize_contact_answer(message: str, wizard_name: str | None) -> str:
    text = message.strip()
    name = (wizard_name or "").strip()
    if name and text and "," not in text:
        return f"{name}, {text}"
    return text


def merge_wizard_metadata(
    answers: dict[str, Any],
    message: str,
) -> dict[str, Any]:
    """Injeta metadados do wizard em ``answers`` na primeira mensagem."""

    wizard_data = parse_wizard_whatsapp_message(message)
    if not wizard_data:
        return answers

    merged = dict(answers)
    merged.update(wizard_data)
    return merged
