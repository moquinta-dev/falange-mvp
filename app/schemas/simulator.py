from pydantic import BaseModel, Field


class SimulatorMessageRequest(BaseModel):
    external_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1)


class SimulatorMessageResponse(BaseModel):
    conversation_id: int
    reply: str
    state: str
    intent: str
    order_summary: str | None = None
