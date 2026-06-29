from app.helpers.discovery_agent_helper import (
    COMPLETED_FOLLOWUP,
    COMPLETED_REPLY,
    CONFIRM_PROMPT,
    CONFIRM_RETRY,
    DISCOVERY_STEPS,
    GREETING,
    HANDOFF_REPLY,
    RESTART_PREFIX,
    SUMMARY_HEADER,
    _respond,
)
from app.helpers import wizard_message_helper

_ANSWERS = [
    "Tenho uma loja de roupas femininas",
    "WhatsApp e Instagram",
    "Demoro muito para responder e perco vendas",
    "Quero qualificar quem chega antes de passar para mim",
    "Uns 40 atendimentos por dia",
    "João, depois das 18h",
]


def test_new_conversation_greets_and_asks_about_business() -> None:
    response = _respond("new", "Estou interessado em automatizar meu atendimento")

    assert response.state == "collecting_business"
    assert response.intent == "greeting"
    assert response.reply == GREETING + DISCOVERY_STEPS[0].question


def test_each_answer_advances_to_next_question() -> None:
    response = _respond("collecting_business", "Tenho uma loja de roupas")

    assert response.state == "collecting_channels"
    assert response.intent == "discovery"
    assert response.reply == DISCOVERY_STEPS[1].question


def test_blank_answer_reasks_same_step() -> None:
    response = _respond("collecting_pain", "   ")

    assert response.state == "collecting_pain"
    assert response.intent == "discovery"
    assert response.reply.endswith(DISCOVERY_STEPS[2].question)


def test_last_answer_builds_business_summary() -> None:
    response = _respond("collecting_contact", _ANSWERS[-1], answers=_ANSWERS)

    assert response.state == "confirming_summary"
    assert response.intent == "summary"
    assert response.summary is not None
    assert response.summary.startswith(SUMMARY_HEADER)
    for step, answer in zip(DISCOVERY_STEPS, _ANSWERS):
        assert f"- {step.label}: {answer}" in response.summary
    assert response.reply == f"{response.summary}\n\n{CONFIRM_PROMPT}"


def test_confirmation_yes_completes_and_hands_off_to_team() -> None:
    response = _respond("confirming_summary", "sim")

    assert response.state == "completed"
    assert response.intent == "confirmation"
    assert response.reply == COMPLETED_REPLY


def test_confirmation_no_restarts_discovery() -> None:
    response = _respond("confirming_summary", "não")

    assert response.state == "collecting_business"
    assert response.intent == "discovery"
    assert response.reply == RESTART_PREFIX + DISCOVERY_STEPS[0].question


def test_confirmation_unclear_message_reasks_confirmation() -> None:
    response = _respond("confirming_summary", "talvez")

    assert response.state == "confirming_summary"
    assert response.intent == "confirmation"
    assert response.reply == CONFIRM_RETRY


def test_completed_conversation_keeps_followup_for_extra_message() -> None:
    response = _respond("completed", "obrigado")

    assert response.state == "completed"
    assert response.intent == "completed"
    assert response.reply == COMPLETED_FOLLOWUP


def test_handoff_request_routes_to_human() -> None:
    response = _respond("collecting_goal", "prefiro falar com um atendente")

    assert response.state == "handoff"
    assert response.intent == "handoff"
    assert response.reply == HANDOFF_REPLY


def test_wizard_name_personalizes_contact_question() -> None:
    response = _respond(
        "collecting_volume",
        "40 atendimentos por dia",
        wizard_name="Marcos",
    )

    assert response.state == "collecting_contact"
    assert response.reply == wizard_message_helper.contact_question("Marcos")
    assert "Marcos" in response.reply
    assert "qual é o seu nome" not in response.reply


def test_wizard_contact_summary_includes_name_with_schedule() -> None:
    answers = _ANSWERS[:-1] + ["depois das 18h"]
    response = _respond(
        "collecting_contact",
        "depois das 18h",
        answers=answers,
        wizard_name="Marcos",
    )

    assert "Marcos, depois das 18h" in (response.summary or "")
