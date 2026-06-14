from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Conversation, Message


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_or_create_conversation(
    db: Session,
    *,
    external_id: str,
    channel: str = "whatsapp",
    initial_state: str = "new",
) -> Conversation:
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.channel == channel,
            Conversation.external_id == external_id,
        )
    )
    if conversation is not None:
        return conversation

    conversation = Conversation(
        channel=channel,
        external_id=external_id,
        state=initial_state,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_conversation(db: Session, conversation_id: int) -> Conversation | None:
    return db.get(Conversation, conversation_id)


def add_message(
    db: Session,
    *,
    conversation: Conversation,
    direction: str,
    content: str,
    external_message_id: str | None = None,
) -> Message:
    message = Message(
        conversation_id=conversation.id,
        direction=direction,
        content=content,
        external_message_id=external_message_id,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def get_message_by_external_id(
    db: Session,
    *,
    conversation: Conversation,
    external_message_id: str,
) -> Message | None:
    return db.scalar(
        select(Message).where(
            Message.conversation_id == conversation.id,
            Message.external_message_id == external_message_id,
        )
    )


def update_conversation_state(
    db: Session,
    *,
    conversation: Conversation,
    state: str,
) -> Conversation:
    conversation.state = state
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def mark_completed(db: Session, *, conversation: Conversation) -> Conversation:
    if conversation.completed_at is None:
        conversation.completed_at = _utc_now()
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    return conversation


def mark_handed_off(db: Session, *, conversation: Conversation) -> Conversation:
    if conversation.handed_off_at is None:
        conversation.handed_off_at = _utc_now()
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    return conversation


def list_recent_messages(
    db: Session,
    *,
    conversation: Conversation,
    limit: int = 20,
) -> list[Message]:
    return list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
    )
