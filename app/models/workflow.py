from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Workflow(Base):
    """Definição (data-driven) do fluxo de triagem de um tenant.

    ``definition`` é a árvore de decisão serializada em JSON; o engine de
    workflow (Fase 1) caminha pelos nós usando ``Conversation.current_node_id`` e
    ``Conversation.answers``. Manter o fluxo em dados permite cadastrar novos
    adopters sem deploy.
    """

    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    tenants: Mapped[list["Tenant"]] = relationship(  # noqa: F821
        back_populates="workflow",
    )
