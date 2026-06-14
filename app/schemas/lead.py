from datetime import datetime

from pydantic import BaseModel, Field


class LeadCreate(BaseModel):
    phone: str | None = Field(default=None, max_length=32)
    name: str | None = Field(default=None, max_length=255)
    business: str | None = None
    channels: str | None = None
    pain: str | None = None
    goal: str | None = None
    volume: str | None = None
    contact: str | None = None
    source: str = Field(default="manual", max_length=32)
    status: str = Field(default="new", max_length=32)


class LeadStatusUpdate(BaseModel):
    status: str = Field(min_length=1, max_length=32)


class LeadResponse(BaseModel):
    id: int
    conversation_id: int | None
    phone: str | None
    name: str | None
    business: str | None
    channels: str | None
    pain: str | None
    goal: str | None
    volume: str | None
    contact: str | None
    source: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
