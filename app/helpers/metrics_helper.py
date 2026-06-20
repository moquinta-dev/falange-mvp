"""Cálculo das métricas do funil de atendimento.

Implementado em Python (ORM) para funcionar tanto em SQLite (testes/local)
quanto em PostgreSQL (produção). O Grafana lê as mesmas métricas diretamente
das views SQL (ver app/core/analytics.py)."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Conversation, Message

_TERMINAL_STATES = ("completed", "handoff", "abandoned")


def _is_handed_off(conversation: Conversation) -> bool:
    return conversation.handed_off_at is not None or conversation.state == "handoff"


def _is_completed_without_human(conversation: Conversation) -> bool:
    return conversation.state == "completed"


def _is_terminal(conversation: Conversation) -> bool:
    return (
        conversation.state in _TERMINAL_STATES
        or conversation.handed_off_at is not None
        or conversation.completed_at is not None
        or conversation.abandoned_at is not None
    )


def compute_funnel_metrics(db: Session) -> dict[str, float | int | None]:
    conversations = list(db.scalars(select(Conversation)))

    message_bounds = {
        row.conversation_id: (row.first_at, row.last_at)
        for row in db.execute(
            select(
                Message.conversation_id.label("conversation_id"),
                func.min(Message.created_at).label("first_at"),
                func.max(Message.created_at).label("last_at"),
            ).group_by(Message.conversation_id)
        )
    }

    total = len(conversations)
    terminal = 0
    completed = 0
    handed_off = 0
    durations: list[float] = []

    for conversation in conversations:
        is_terminal = _is_terminal(conversation)
        if is_terminal:
            terminal += 1
        if _is_completed_without_human(conversation):
            completed += 1
        if _is_handed_off(conversation):
            handed_off += 1

        if is_terminal:
            bounds = message_bounds.get(conversation.id)
            if bounds and bounds[0] is not None and bounds[1] is not None:
                durations.append((bounds[1] - bounds[0]).total_seconds())

    def _pct(value: int) -> float | None:
        if terminal == 0:
            return None
        return round(100.0 * value / terminal, 2)

    avg_handle_time = round(sum(durations) / len(durations), 2) if durations else None

    return {
        "total_conversations": total,
        "terminal_conversations": terminal,
        "completed_without_human": completed,
        "handed_off": handed_off,
        "pct_completed_without_human": _pct(completed),
        "pct_handoff": _pct(handed_off),
        "avg_handle_time_seconds": avg_handle_time,
    }
