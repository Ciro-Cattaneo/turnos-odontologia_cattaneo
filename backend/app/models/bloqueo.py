"""Bloqueo de agenda: feriado, vacaciones, sobreturno negativo (KB-04)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Bloqueo(Base):
    """Excepcion sobre ventanas recurrentes; `creado_por` nullable (seed/sistema)."""

    __tablename__ = "bloqueo"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    profesional_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profesional.id"), nullable=False, index=True
    )
    desde: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    hasta: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    motivo: Mapped[str] = mapped_column(Text, nullable=False)
    creado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario_staff.id"))
