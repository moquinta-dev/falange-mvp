"""Notificação ao tenant quando uma triagem é concluída (Fase 2).

Despacha pelo canal configurado no tenant (``notify_channel`` + ``notify_target``).
Hoje só ``email`` está implementado; ``whatsapp`` (mensagem no número pessoal do
dono) depende de template utility aprovado pela Meta e é evolução futura.

A função é desenhada para rodar dentro de uma BackgroundTask: recebe apenas
valores primitivos (não objetos ligados à sessão do banco, que já estará fechada)
e nunca propaga exceção — falha de notificação não pode quebrar a triagem, que já
foi concluída e persistida.
"""

import logging

from app.helpers.email_client import EmailClient

logger = logging.getLogger(__name__)

EMAIL_CHANNEL = "email"
WHATSAPP_CHANNEL = "whatsapp"


def _humanize(key: str) -> str:
    return key.replace("_", " ").strip().capitalize()


def _is_triagem_lead(answers: dict | None) -> bool:
    return bool(answers and answers.get("nome"))


def _formato_foco(answers: dict) -> str:
    return str(answers.get("modalidade") or answers.get("objetivo") or "—")


def build_email_subject(
    *,
    tenant_name: str,
    answers: dict | None,
) -> str:
    if _is_triagem_lead(answers):
        nome = answers["nome"]
        interesse = answers.get("interesse") or "Triagem"
        return f"[Novo Lead Triagem] - {nome} - {interesse}"
    return f"Nova triagem concluída — {tenant_name}"


def build_triagem_email_body(*, lead_phone: str, answers: dict) -> str:
    idade = answers.get("idade") or answers.get("faixa_etaria") or "—"
    return "\n".join(
        [
            "Ficha de Triagem - Assistente Virtual",
            "",
            f"* Nome: {answers.get('nome', '—')}",
            f"* Idade: {idade}",
            f"* Interesse: {answers.get('interesse', '—')}",
            f"* Formato/Foco: {_formato_foco(answers)}",
            f"* WhatsApp do Cliente: {lead_phone}",
        ]
    )


def build_email_body(
    *,
    tenant_name: str,
    lead_phone: str,
    summary: str | None,
    answers: dict | None,
) -> str:
    if _is_triagem_lead(answers):
        return build_triagem_email_body(lead_phone=lead_phone, answers=answers)

    lines = [
        f"Uma nova triagem foi concluída para {tenant_name}.",
        "",
        f"Contato (WhatsApp): {lead_phone}",
        "",
    ]
    if summary:
        lines.append(summary)
    elif answers:
        lines.append("Respostas:")
        lines.extend(f"- {_humanize(key)}: {value}" for key, value in answers.items())
    else:
        lines.append("Triagem concluída (sem respostas registradas).")
    lines.extend(["", "— Falangelabs"])
    return "\n".join(lines)


def notify_tenant_of_completion(
    email_client: EmailClient,
    *,
    tenant_name: str,
    notify_channel: str | None,
    notify_target: str | None,
    lead_phone: str,
    summary: str | None,
    answers: dict | None = None,
) -> bool:
    """Envia a notificação de triagem concluída. Retorna True se enviou.

    Nunca levanta exceção: erros são logados para não interromper nada.
    """

    if not notify_target:
        logger.info("Tenant %s sem notify_target; notificação ignorada", tenant_name)
        return False

    channel = (notify_channel or EMAIL_CHANNEL).lower()
    if channel != EMAIL_CHANNEL:
        logger.info(
            "notify_channel %r ainda não implementado (tenant=%s); notificação ignorada",
            channel,
            tenant_name,
        )
        return False

    subject = build_email_subject(tenant_name=tenant_name, answers=answers)
    body = build_email_body(
        tenant_name=tenant_name,
        lead_phone=lead_phone,
        summary=summary,
        answers=answers,
    )
    try:
        email_client.send(to=notify_target, subject=subject, body=body)
    except Exception:  # noqa: BLE001 - notificação não pode quebrar a triagem
        logger.exception(
            "Falha ao enviar notificação de triagem (tenant=%s, to=%s)",
            tenant_name,
            notify_target,
        )
        return False

    logger.info("Notificação de triagem enviada (tenant=%s, to=%s)", tenant_name, notify_target)
    return True
