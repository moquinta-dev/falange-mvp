"""Resolução de tenant a partir do roteamento do WhatsApp.

Todos os números vivem sob a mesma WABA da Falangelabs; o webhook identifica o
tenant pelo ``phone_number_id`` presente no metadata do evento da Meta.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Tenant


def resolve_by_phone_number_id(
    db: Session,
    phone_number_id: str | None,
) -> Tenant | None:
    """Retorna o tenant ativo dono do número, ou ``None`` se não houver."""

    if not phone_number_id:
        return None

    return db.scalar(
        select(Tenant).where(
            Tenant.whatsapp_phone_number_id == phone_number_id,
            Tenant.active.is_(True),
        )
    )


def list_tenants(db: Session) -> list[Tenant]:
    return list(db.scalars(select(Tenant).order_by(Tenant.name)))


def upsert_tenant(
    db: Session,
    *,
    name: str,
    phone_number_id: str,
    workflow_id: int | None,
    notify_channel: str = "email",
    notify_target: str | None = None,
    active: bool = True,
) -> Tenant:
    """Cria/atualiza um tenant por ``phone_number_id`` (idempotente)."""

    tenant = db.scalar(
        select(Tenant).where(Tenant.whatsapp_phone_number_id == phone_number_id)
    )
    if tenant is None:
        tenant = Tenant(name=name, whatsapp_phone_number_id=phone_number_id)
        db.add(tenant)

    tenant.name = name
    tenant.workflow_id = workflow_id
    tenant.notify_channel = notify_channel
    tenant.notify_target = notify_target
    tenant.active = active
    db.commit()
    db.refresh(tenant)
    return tenant
