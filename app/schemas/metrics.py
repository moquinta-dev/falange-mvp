from pydantic import BaseModel


class FunnelMetricsResponse(BaseModel):
    total_conversations: int
    terminal_conversations: int
    completed_without_human: int
    handed_off: int
    pct_completed_without_human: float | None
    pct_handoff: float | None
    avg_handle_time_seconds: float | None
