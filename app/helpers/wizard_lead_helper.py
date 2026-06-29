"""Notificação interna quando um lead conclui o wizard da landing page."""

import logging

from app.helpers.email_client import EmailClient

logger = logging.getLogger(__name__)


def build_wizard_lead_email_subject(*, segment: str, name: str | None) -> str:
    label = name.strip() if name and name.strip() else segment
    return f"[Novo lead wizard] {label} — {segment}"


def build_wizard_lead_email_body(
    *,
    lead_id: int,
    segment: str,
    question: str,
    answer: str,
    phone: str,
    name: str | None,
    email: str | None,
) -> str:
    lines = [
        "Novo lead capturado pelo wizard /criar-agente",
        "",
        f"ID do lead: {lead_id}",
        f"Segmento: {segment}",
        f"Pergunta frequente: {question}",
        f"Resposta configurada: {answer}",
        f"WhatsApp: {phone}",
    ]
    if name:
        lines.append(f"Nome: {name}")
    if email:
        lines.append(f"E-mail: {email}")
    lines.extend(["", "— Falange Labs"])
    return "\n".join(lines)


def notify_team_of_wizard_lead(
    email_client: EmailClient,
    *,
    notify_target: str,
    lead_id: int,
    segment: str,
    question: str,
    answer: str,
    phone: str,
    name: str | None,
    email: str | None,
) -> bool:
    """Envia alerta interno. Retorna True se enviou; nunca propaga exceção."""

    if not notify_target:
        logger.info("wizard_lead_notify_email ausente; notificação ignorada")
        return False

    if not email_client.is_configured:
        logger.warning(
            "SMTP não configurado; notificação de wizard lead ignorada "
            "(lead_id=%s, destino=%s)",
            lead_id,
            notify_target,
        )
        return False

    subject = build_wizard_lead_email_subject(segment=segment, name=name)
    body = build_wizard_lead_email_body(
        lead_id=lead_id,
        segment=segment,
        question=question,
        answer=answer,
        phone=phone,
        name=name,
        email=email,
    )
    try:
        email_client.send(to=notify_target, subject=subject, body=body)
    except Exception:  # noqa: BLE001 - notificação não pode quebrar o wizard
        logger.exception(
            "Falha ao enviar notificação de wizard lead (lead_id=%s, to=%s)",
            lead_id,
            notify_target,
        )
        return False

    logger.info("Notificação de wizard lead enviada (lead_id=%s, to=%s)", lead_id, notify_target)
    return True
