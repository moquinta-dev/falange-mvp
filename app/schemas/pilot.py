from datetime import datetime

from pydantic import BaseModel, Field


class PilotCreate(BaseModel):
    lead_id: int
    status: str = Field(default="planned", max_length=32)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    notes: str | None = None


class PilotUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=32)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    notes: str | None = None


class PilotResponse(BaseModel):
    id: int
    lead_id: int
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
