"""Endpoints autenticados de onboarding de adopters (Fase 4).

Idempotentes por natureza (``PUT`` por chave natural) para suportar um fluxo
GitOps: o repositório de seeds versiona as definições e a pipeline aplica via
estes endpoints, ativando um cliente novo sem deploy do backend.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import require_admin_api_key
from app.core.database import get_db
from app.helpers import tenant_helper, workflow_engine, workflow_helper
from app.helpers.idle_helper import sweep_idle_conversations
from app.helpers.whatsapp_cloud_client import WhatsAppCloudClient, get_whatsapp_client
from app.core.settings import Settings, get_settings
from app.schemas.admin import (
    IdleSweepResponse,
    TenantResponse,
    TenantUpsert,
    WorkflowResponse,
    WorkflowUpsert,
)

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_api_key)],
)


@router.get("/workflows", response_model=list[WorkflowResponse])
async def list_workflows(db: Session = Depends(get_db)):
    return workflow_helper.list_workflows(db)


@router.get("/workflows/{key}", response_model=WorkflowResponse)
async def get_workflow(key: str, db: Session = Depends(get_db)):
    workflow = workflow_helper.get_by_key(db, key)
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"workflow não encontrado: {key}",
        )
    return workflow


@router.put("/workflows/{key}", response_model=WorkflowResponse)
async def upsert_workflow(
    key: str,
    payload: WorkflowUpsert,
    db: Session = Depends(get_db),
):
    try:
        return workflow_helper.upsert_workflow(
            db,
            key=key,
            name=payload.name,
            definition=payload.definition,
        )
    except workflow_engine.WorkflowError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"workflow inválido: {exc}",
        ) from exc


@router.get("/tenants", response_model=list[TenantResponse])
async def list_tenants(db: Session = Depends(get_db)):
    return tenant_helper.list_tenants(db)


@router.put("/tenants/{phone_number_id}", response_model=TenantResponse)
async def upsert_tenant(
    phone_number_id: str,
    payload: TenantUpsert,
    db: Session = Depends(get_db),
):
    workflow = workflow_helper.get_by_key(db, payload.workflow_key)
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"workflow não encontrado: {payload.workflow_key}",
        )

    return tenant_helper.upsert_tenant(
        db,
        name=payload.name,
        phone_number_id=phone_number_id,
        workflow_id=workflow.id,
        notify_channel=payload.notify_channel,
        notify_target=payload.notify_target,
        active=payload.active,
    )


@router.post("/conversations/sweep-idle", response_model=IdleSweepResponse)
async def sweep_idle_conversations_endpoint(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    whatsapp_client: WhatsAppCloudClient = Depends(get_whatsapp_client),
):
    """Varre conversas inativas: lembrete e abandono automático.

    Destinado a cron externo (ex.: a cada 5 min na VPS). Idempotente por conversa.
    """

    result = sweep_idle_conversations(
        db,
        settings=settings,
        whatsapp_client=whatsapp_client,
    )
    return IdleSweepResponse(
        nudges_sent=result.nudges_sent,
        abandoned=result.abandoned,
        skipped_outside_whatsapp_window=result.skipped_outside_whatsapp_window,
        errors=result.errors,
    )
