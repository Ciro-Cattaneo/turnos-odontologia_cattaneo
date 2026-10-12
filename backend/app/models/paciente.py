"""Paciente (KB-04 + D-9a: contacto nulable en DB, obligatorio en app/C-05)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Paciente(Base):
    """Paciente sin login en v1; soft-delete via `activo` (PB-04)."""

    __tablename__ = "paciente"
    __table_args__ = (
        # §2 review: nombre estable bloqueado (handoff C-01 lo dejaba abierto).
        UniqueConstraint("dni", name="ux_paciente_dni"),
        # D-5: formato laxo solo a nivel DB; el 400 por campo llega en C-05.
        CheckConstraint(
            "(email IS NULL OR position('@' IN email) > 1)",
            name="ck_paciente_email_formato",
        ),
        Index("ix_paciente_telefono", "telefono"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # D-9a: nulables a nivel DB para permitir anonimizacion a NULL (Ley 25.326);
    # la obligatoriedad RN-TU-01 se exige a nivel app/Pydantic en C-05.
    nombre: Mapped[str | None] = mapped_column(String(120))
    dni: Mapped[str | None] = mapped_column(String(20))
    telefono: Mapped[str | None] = mapped_column(String(30))
    obra_social: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(160))
    activo: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
