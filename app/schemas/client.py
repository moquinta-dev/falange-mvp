from datetime import datetime

from pydantic import BaseModel, Field


class ClientCreate(BaseModel):
    lead_id: int
    company_name: str = Field(min_length=1, max_length=255)
    plan: str | None = Field(default=None, max_length=64)
    mrr_cents: int | None = Field(default=None, ge=0)
    status: str = Field(default="active", max_length=32)
    started_at: datetime | None = None
    notes: str | None = None


class ClientResponse(BaseModel):
    id: int
    lead_id: int
    company_name: str
    plan: str | None
    mrr_cents: int | None
    status: str
    started_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
