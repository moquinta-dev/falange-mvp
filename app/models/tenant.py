from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# Canais possíveis para notificar o dono do tenant ao concluir uma triagem.
NOTIFY_CHANNELS = ("email", "whatsapp")


class Tenant(Base):
    """Adopter atendido pela plataforma (ex.: a Natália, ou a própria Falange).

    O roteamento das mensagens é feito por ``whatsapp_phone_number_id``: todos os
    números vivem sob a mesma WABA da Falangelabs, então um único webhook/token
    serve todos os tenants. Cadastrar um novo adopter é inserir uma linha aqui —
    sem deploy.
    """

    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    whatsapp_phone_number_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
    )
    workflow_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflows.id"),
        nullable=True,
        index=True,
    )
    # Destino da notificação de triagem concluída (Fase 2).
    notify_channel: Mapped[str] = mapped_column(String(16), default="email")
    notify_target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    workflow: Mapped["Workflow | None"] = relationship(  # noqa: F821
        back_populates="tenants",
    )
