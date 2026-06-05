from datetime import datetime

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    external_id: str = Field(min_length=1, max_length=128)
    channel: str = Field(default="whatsapp", min_length=1, max_length=32)
    initial_state: str = Field(default="new", min_length=1, max_length=64)


class ConversationStateUpdate(BaseModel):
    state: str = Field(min_length=1, max_length=64)


class MessageCreate(BaseModel):
    direction: str = Field(min_length=1, max_length=16)
    content: str = Field(min_length=1)
    external_message_id: str | None = Field(default=None, max_length=128)


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    direction: str
    content: str
    external_message_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: int
    channel: str
    external_id: str
    state: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
