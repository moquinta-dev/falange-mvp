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
