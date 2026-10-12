"""AuditoriaTurno append-only (KB-04, D-8: trigger anti UPDATE/DELETE en §2)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditoriaTurno(Base):
    """Trail no reescribible; `actor_id` NULL = accion del paciente."""

    __tablename__ = "auditoria_turno"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    turno_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("turno.id"), nullable=False, index=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario_staff.id"))
    accion: Mapped[str] = mapped_column(String(40), nullable=False)
    detalle: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
