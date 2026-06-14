from datetime import datetime

from pydantic import BaseModel, Field


class LandingEventCreate(BaseModel):
    event_type: str = Field(min_length=1, max_length=32)
    session_id: str | None = Field(default=None, max_length=64)
    path: str | None = Field(default=None, max_length=255)
    referrer: str | None = None
    utm_source: str | None = Field(default=None, max_length=128)
    utm_medium: str | None = Field(default=None, max_length=128)
    utm_campaign: str | None = Field(default=None, max_length=128)


class LandingEventResponse(BaseModel):
    id: int
    event_type: str
    session_id: str | None
    path: str | None
    referrer: str | None
    utm_source: str | None
    utm_medium: str | None
    utm_campaign: str | None
    user_agent: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
