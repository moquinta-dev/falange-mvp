from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class WizardLeadCreate(BaseModel):
    session_id: str | None = Field(default=None, max_length=64)
    segment: str = Field(min_length=1, max_length=128)
    question: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1, max_length=2000)
    phone: str = Field(min_length=8, max_length=32)
    name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    consent: bool
    website: str | None = Field(default=None, max_length=255)

    @field_validator("consent")
    @classmethod
    def consent_must_be_true(cls, value: bool) -> bool:
        if not value:
            raise ValueError("consent is required")
        return value


class WizardLeadResponse(BaseModel):
    id: int
    phone: str | None
    name: str | None
    business: str | None
    pain: str | None
    goal: str | None
    contact: str | None
    source: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
