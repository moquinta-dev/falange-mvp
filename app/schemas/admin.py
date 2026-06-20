"""Schemas dos endpoints de onboarding/administração (Fase 4).

Permitem cadastrar workflows e tenants via API autenticada — base do fluxo
GitOps em que ativar um novo cliente é aplicar definições versionadas, sem
deploy do backend.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class WorkflowUpsert(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    definition: dict[str, Any]


class WorkflowResponse(BaseModel):
    id: int
    key: str
    name: str | None
    definition: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TenantUpsert(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    workflow_key: str = Field(min_length=1, max_length=64)
    notify_channel: Literal["email", "whatsapp"] = "email"
    notify_target: str | None = Field(default=None, max_length=255)
    active: bool = True


class TenantResponse(BaseModel):
    id: int
    name: str
    whatsapp_phone_number_id: str
    workflow_id: int | None
    notify_channel: str
    notify_target: str | None
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IdleSweepResponse(BaseModel):
    nudges_sent: int
    abandoned: int
    skipped_outside_whatsapp_window: int
    errors: int
