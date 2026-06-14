"""Persistência de leads do funil comercial.

Centraliza a criação/atualização de leads a partir das conversas do discovery
agent, além das transições de status usadas no follow-up comercial.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Conversation, Lead


def _phone_from_external_id(external_id: str) -> str | None:
    if not external_id:
        return None
    return external_id.split(":", 1)[1] if ":" in external_id else external_id


def _name_from_contact(contact: str | None) -> str | None:
    if not contact:
        return None
    # O passo de contato costuma vir como "Nome, melhor horário".
    name = contact.split(",", 1)[0].strip()
    return name or None


def get_lead_by_conversation(db: Session, conversation_id: int) -> Lead | None:
    return db.scalar(select(Lead).where(Lead.conversation_id == conversation_id))


def upsert_lead_for_conversation(
    db: Session,
    *,
    conversation: Conversation,
    answers_by_key: dict[str, str],
    status: str,
) -> Lead:
    """Cria ou atualiza o lead vinculado à conversa com os dados coletados."""

    lead = get_lead_by_conversation(db, conversation.id)
    contact = answers_by_key.get("contact")

    if lead is None:
        lead = Lead(
            conversation_id=conversation.id,
            source=conversation.channel or "whatsapp",
        )
        db.add(lead)

    lead.phone = _phone_from_external_id(conversation.external_id) or lead.phone
    lead.name = _name_from_contact(contact) or lead.name
    lead.business = answers_by_key.get("business") or lead.business
    lead.channels = answers_by_key.get("channels") or lead.channels
    lead.pain = answers_by_key.get("pain") or lead.pain
    lead.goal = answers_by_key.get("goal") or lead.goal
    lead.volume = answers_by_key.get("volume") or lead.volume
    lead.contact = contact or lead.contact
    lead.status = status

    db.commit()
    db.refresh(lead)
    return lead


def update_lead_status(db: Session, *, lead: Lead, status: str) -> Lead:
    lead.status = status
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead
