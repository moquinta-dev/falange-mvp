from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# Status do funil comercial (follow-up).
LEAD_STATUSES = (
    "new",
    "contacted",
    "qualified",
    "pilot",
    "client",
    "lost",
    "handoff",
)


class Lead(Base):
    """Lead capturado pelo funil (landing -> WhatsApp -> discovery)."""

    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id"),
        nullable=True,
        unique=True,
        index=True,
    )
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business: Mapped[str | None] = mapped_column(Text, nullable=True)
    channels: Mapped[str | None] = mapped_column(Text, nullable=True)
    pain: Mapped[str | None] = mapped_column(Text, nullable=True)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    volume: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="whatsapp", index=True)
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    pilots: Mapped[list["Pilot"]] = relationship(  # noqa: F821
        back_populates="lead",
        cascade="all, delete-orphan",
    )
    clients: Mapped[list["Client"]] = relationship(  # noqa: F821
        back_populates="lead",
        cascade="all, delete-orphan",
    )
