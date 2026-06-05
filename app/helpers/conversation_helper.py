from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Conversation, Message


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
