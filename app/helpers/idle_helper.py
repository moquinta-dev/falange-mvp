"""Encerramento automático de conversas inativas (workflow data-driven).

Fluxo:
1. Após ``idle_nudge_after_minutes`` sem mensagem inbound → lembrete WhatsApp.
2. Após ``idle_abandon_after_nudge_minutes`` sem resposta ao lembrete → ``abandoned``
   (``answers`` congelados) + mensagem de despedida.
3. Nova mensagem do usuário após abandono → triagem reinicia do zero (engine).

Projetado para ser chamado por cron externo via ``POST /admin/conversations/sweep-idle``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.settings import Settings
from app.helpers import conversation_helper
from app.helpers.whatsapp_cloud_client import WhatsAppCloudClient
from app.models import Conversation, Message, Tenant

logger = logging.getLogger(__name__)

ABANDONED_STATE = "abandoned"

_TERMINAL_STATES = ("completed", "handoff", ABANDONED_STATE)

IDLE_NUDGE_MESSAGE = (
    "Ainda está no atendimento? Digite *1* para continuar."
)
IDLE_FAREWELL_MESSAGE = (
    "Encerramos seu atendimento por inatividade. "
    "Quando quiser retomar, é só enviar uma nova mensagem por aqui. Até breve!"
)

_CONTINUE_TOKENS = frozenset({"1", "sim", "continuar"})


def is_continue_token(message: str) -> bool:
    normalized = message.strip().lower().strip(".!,?")
    return normalized in _CONTINUE_TOKENS


@dataclass(frozen=True)
class IdleSweepResult:
    nudges_sent: int = 0
    abandoned: int = 0
    skipped_outside_whatsapp_window: int = 0
    errors: int = 0


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def sweep_idle_conversations(
    db: Session,
    *,
    settings: Settings,
    whatsapp_client: WhatsAppCloudClient,
) -> IdleSweepResult:
    if not settings.idle_sweep_enabled:
        logger.info("Idle sweep disabled; skipping")
        return IdleSweepResult()

    now = _utc_now()
    nudge_cutoff = now - timedelta(minutes=settings.idle_nudge_after_minutes)
    abandon_cutoff = now - timedelta(minutes=settings.idle_abandon_after_nudge_minutes)
    whatsapp_window_cutoff = now - timedelta(hours=settings.idle_whatsapp_window_hours)

    result = IdleSweepResult()
    last_inbound = _last_inbound_subquery()

    nudge_rows = db.execute(
        select(Conversation, Tenant, last_inbound.c.last_inbound_at)
        .join(Tenant, Tenant.id == Conversation.tenant_id)
        .join(last_inbound, last_inbound.c.conversation_id == Conversation.id)
        .where(
            Tenant.active.is_(True),
            Tenant.workflow_id.is_not(None),
            Conversation.state.notin_(_TERMINAL_STATES),
            Conversation.idle_nudge_sent_at.is_(None),
            last_inbound.c.last_inbound_at < nudge_cutoff,
        )
        .order_by(last_inbound.c.last_inbound_at)
        .limit(settings.idle_sweep_batch_size)
    ).all()

    for conversation, tenant, last_inbound_at in nudge_rows:
        last_inbound_at = _as_utc(last_inbound_at)
        if last_inbound_at < whatsapp_window_cutoff:
            _mark_abandoned_silent(db, conversation)
            result = IdleSweepResult(
                nudges_sent=result.nudges_sent,
                abandoned=result.abandoned + 1,
                skipped_outside_whatsapp_window=result.skipped_outside_whatsapp_window + 1,
                errors=result.errors,
            )
            continue

        phone = _phone_from_external_id(conversation.external_id)
        if phone is None:
            logger.warning(
                "Idle nudge skipped: invalid external_id conversation_id=%s",
                conversation.id,
            )
            result = IdleSweepResult(
                nudges_sent=result.nudges_sent,
                abandoned=result.abandoned,
                skipped_outside_whatsapp_window=result.skipped_outside_whatsapp_window,
                errors=result.errors + 1,
            )
            continue

        try:
            whatsapp_client.send_text_sync(
                to=phone,
                text=IDLE_NUDGE_MESSAGE,
                phone_number_id=tenant.whatsapp_phone_number_id,
            )
            conversation_helper.mark_idle_nudge_sent(
                db,
                conversation=conversation,
                content=IDLE_NUDGE_MESSAGE,
            )
            result = IdleSweepResult(
                nudges_sent=result.nudges_sent + 1,
                abandoned=result.abandoned,
                skipped_outside_whatsapp_window=result.skipped_outside_whatsapp_window,
                errors=result.errors,
            )
        except httpx.HTTPError:
            logger.exception(
                "Failed to send idle nudge conversation_id=%s tenant=%s",
                conversation.id,
                tenant.name,
            )
            result = IdleSweepResult(
                nudges_sent=result.nudges_sent,
                abandoned=result.abandoned,
                skipped_outside_whatsapp_window=result.skipped_outside_whatsapp_window,
                errors=result.errors + 1,
            )

    abandon_rows = db.execute(
        select(Conversation, Tenant, last_inbound.c.last_inbound_at)
        .join(Tenant, Tenant.id == Conversation.tenant_id)
        .join(last_inbound, last_inbound.c.conversation_id == Conversation.id)
        .where(
            Tenant.active.is_(True),
            Tenant.workflow_id.is_not(None),
            Conversation.state.notin_(_TERMINAL_STATES),
            Conversation.idle_nudge_sent_at.is_not(None),
            Conversation.idle_nudge_sent_at < abandon_cutoff,
            last_inbound.c.last_inbound_at < Conversation.idle_nudge_sent_at,
        )
        .order_by(Conversation.idle_nudge_sent_at)
        .limit(settings.idle_sweep_batch_size)
    ).all()

    for conversation, tenant, last_inbound_at in abandon_rows:
        last_inbound_at = _as_utc(last_inbound_at)
        phone = _phone_from_external_id(conversation.external_id)
        farewell_sent = False

        if last_inbound_at >= whatsapp_window_cutoff and phone is not None:
            try:
                whatsapp_client.send_text_sync(
                    to=phone,
                    text=IDLE_FAREWELL_MESSAGE,
                    phone_number_id=tenant.whatsapp_phone_number_id,
                )
                farewell_sent = True
            except httpx.HTTPError:
                logger.exception(
                    "Failed to send idle farewell conversation_id=%s tenant=%s",
                    conversation.id,
                    tenant.name,
                )
                result = IdleSweepResult(
                    nudges_sent=result.nudges_sent,
                    abandoned=result.abandoned,
                    skipped_outside_whatsapp_window=result.skipped_outside_whatsapp_window,
                    errors=result.errors + 1,
                )
                continue

        conversation_helper.mark_abandoned(
            db,
            conversation=conversation,
            farewell_content=IDLE_FAREWELL_MESSAGE if farewell_sent else None,
        )
        result = IdleSweepResult(
            nudges_sent=result.nudges_sent,
            abandoned=result.abandoned + 1,
            skipped_outside_whatsapp_window=result.skipped_outside_whatsapp_window,
            errors=result.errors,
        )

    return result


def _mark_abandoned_silent(db: Session, conversation: Conversation) -> None:
    conversation_helper.mark_abandoned(db, conversation=conversation, farewell_content=None)


def _last_inbound_subquery():
    return (
        select(
            Message.conversation_id.label("conversation_id"),
            func.max(Message.created_at).label("last_inbound_at"),
        )
        .where(Message.direction == "inbound")
        .group_by(Message.conversation_id)
        .subquery("last_inbound")
    )


def _phone_from_external_id(external_id: str) -> str | None:
    if not external_id.startswith("whatsapp:"):
        return None
    parts = external_id.split(":", 2)
    if len(parts) == 3:
        return parts[2] or None
    if len(parts) == 2:
        return parts[1] or None
    return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
