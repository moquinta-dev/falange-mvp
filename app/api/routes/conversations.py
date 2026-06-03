from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.helpers import conversation_helper
from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    ConversationStateUpdate,
    MessageCreate,
    MessageResponse,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_or_get_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
):
    return conversation_helper.get_or_create_conversation(
        db,
        external_id=payload.external_id,
        channel=payload.channel,
        initial_state=payload.initial_state,
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    conversation = conversation_helper.get_conversation(db, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


@router.patch("/{conversation_id}/state", response_model=ConversationResponse)
def update_conversation_state(
    conversation_id: int,
    payload: ConversationStateUpdate,
    db: Session = Depends(get_db),
):
    conversation = conversation_helper.get_conversation(db, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    return conversation_helper.update_conversation_state(
        db,
        conversation=conversation,
        state=payload.state,
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_message(
    conversation_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
):
    conversation = conversation_helper.get_conversation(db, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    return conversation_helper.add_message(
        db,
        conversation=conversation,
        direction=payload.direction,
        content=payload.content,
        external_message_id=payload.external_message_id,
    )


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
def list_messages(
    conversation_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    conversation = conversation_helper.get_conversation(db, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    return conversation_helper.list_recent_messages(
        db,
        conversation=conversation,
        limit=limit,
    )
