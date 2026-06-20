import json
import logging

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.settings import Settings, get_settings
from app.helpers import (
    conversation_helper,
    discovery_agent_helper,
    idle_helper,
    notification_helper,
    tenant_helper,
    workflow_engine,
    workflow_helper,
)
from app.helpers.email_client import EmailClient, get_email_client
from app.helpers.whatsapp_cloud_client import WhatsAppCloudClient, get_whatsapp_client
from app.helpers.whatsapp_webhook_helper import (
    extract_whatsapp_message,
    verify_meta_signature,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook/whatsapp", tags=["whatsapp"])


@router.get("")
async def verify_whatsapp_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    settings: Settings = Depends(get_settings),
) -> PlainTextResponse:
    if (
        hub_mode == "subscribe"
        and hub_verify_token == settings.whatsapp_verify_token
        and hub_challenge is not None
    ):
        return PlainTextResponse(hub_challenge)

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid verify token",
    )


@router.post("")
async def receive_whatsapp_message(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    whatsapp_client: WhatsAppCloudClient = Depends(get_whatsapp_client),
    email_client: EmailClient = Depends(get_email_client),
) -> dict[str, str | int]:
    body = await request.body()
    if settings.meta_validate_signature:
        signature = request.headers.get("X-Hub-Signature-256")
        if not verify_meta_signature(body, signature, settings.meta_app_secret):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid webhook signature",
            )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        ) from exc

    message = extract_whatsapp_message(payload)
    if message is None:
        return {"status": "ignored"}

    # Roteamento multi-tenant: o phone_number_id do evento identifica o tenant.
    phone_number_id = message.get("phone_number_id") or None
    tenant = tenant_helper.resolve_by_phone_number_id(db, phone_number_id)
    if tenant is None and settings.require_known_tenant:
        logger.warning(
            "WhatsApp event for unknown tenant phone_number_id=%s",
            phone_number_id,
        )
        return {"status": "unknown_tenant"}

    # Número usado para responder: o do tenant quando resolvido, senão o fallback.
    sender_phone_number_id = (
        tenant.whatsapp_phone_number_id if tenant is not None else phone_number_id
    )

    # Conversa escopada por tenant: o mesmo telefone pode falar com adopters
    # diferentes (ex.: Falangelabs e Natália) sem que os estados de triagem
    # colidam entre si. Sem tenant resolvido, mantemos o escopo só pelo remetente.
    external_id = (
        f"whatsapp:{tenant.id}:{message['from']}"
        if tenant is not None
        else f"whatsapp:{message['from']}"
    )
    conversation = conversation_helper.get_or_create_conversation(
        db,
        external_id=external_id,
        channel="whatsapp",
        initial_state=discovery_agent_helper.INITIAL_STATE,
        tenant_id=tenant.id if tenant is not None else None,
    )

    message_id = message.get("message_id", "")
    if message_id and conversation_helper.get_message_by_external_id(
        db,
        conversation=conversation,
        external_message_id=message_id,
    ):
        logger.info("Duplicate WhatsApp message ignored conversation_id=%s", conversation.id)
        return {"status": "duplicate", "conversation_id": conversation.id}

    # Tenant com workflow cadastrado roda no engine data-driven; sem workflow
    # (fallback/sem tenant) seguimos no discovery agent legado.
    workflow = (
        workflow_helper.get_definition_for_tenant(db, tenant)
        if tenant is not None
        else None
    )
    if workflow is not None:
        if conversation.idle_nudge_sent_at is not None:
            if idle_helper.is_continue_token(message["text"]):
                conversation_helper.clear_idle_nudge(db, conversation=conversation)
                result = workflow_engine.reprompt_current(
                    db,
                    conversation=conversation,
                    workflow=workflow,
                    message=message["text"],
                    external_message_id=message_id or None,
                )
            else:
                conversation_helper.clear_idle_nudge(db, conversation=conversation)
                result = workflow_engine.handle_message(
                    db,
                    conversation=conversation,
                    workflow=workflow,
                    message=message["text"],
                    external_message_id=message_id or None,
                )
        else:
            result = workflow_engine.handle_message(
                db,
                conversation=conversation,
                workflow=workflow,
                message=message["text"],
                external_message_id=message_id or None,
            )
    else:
        result = discovery_agent_helper.handle_message(
            db,
            external_id=external_id,
            channel="whatsapp",
            message=message["text"],
            external_message_id=message_id or None,
        )
    logger.info("WhatsApp message handled conversation_id=%s", result.conversation_id)

    # Triagem concluída (engine data-driven) → notifica o dono do tenant fora do
    # caminho da resposta ao Meta. SMTP é I/O lento; a BackgroundTask roda após o
    # response e nunca quebra o fluxo (já concluído e persistido).
    if (
        settings.notifications_enabled
        and tenant is not None
        and workflow is not None
        and getattr(result, "completed", False)
    ):
        background_tasks.add_task(
            notification_helper.notify_tenant_of_completion,
            email_client,
            tenant_name=tenant.name,
            notify_channel=tenant.notify_channel,
            notify_target=tenant.notify_target,
            lead_phone=message["from"],
            summary=result.summary,
            answers=dict(conversation.answers or {}),
        )

    try:
        await whatsapp_client.send_text(
            to=message["from"],
            text=result.reply,
            phone_number_id=sender_phone_number_id,
        )
    except httpx.HTTPStatusError as exc:
        logger.exception(
            "WhatsApp Cloud API send failed conversation_id=%s status_code=%s response=%s",
            result.conversation_id,
            exc.response.status_code,
            _response_body_for_log(exc.response),
        )
        return {"status": "reply_failed", "conversation_id": result.conversation_id}
    except httpx.HTTPError:
        logger.exception(
            "WhatsApp Cloud API send failed conversation_id=%s",
            result.conversation_id,
        )
        return {"status": "reply_failed", "conversation_id": result.conversation_id}

    return {"status": "ok", "conversation_id": result.conversation_id}


def _response_body_for_log(response: httpx.Response) -> str:
    body = response.text.strip()
    if not body:
        return "<empty>"
    return body[:2000]
