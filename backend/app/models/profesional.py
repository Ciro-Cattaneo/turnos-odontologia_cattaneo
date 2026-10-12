"""Profesional (KB-04)."""

import uuid

from sqlalchemy import Boolean, Index, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Profesional(Base):
    """Odontologo/profesional del consultorio."""

    __tablename__ = "profesional"
    __table_args__ = (
        # D-5: parcial de activos (listados futuros filtran activo=true).
        Index("ix_profesional_activo", "activo", postgresql_where=text("activo")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    matricula: Mapped[str | None] = mapped_column(String(50))
    especialidad: Mapped[str | None] = mapped_column(String(100))
    duracion_default_min: Mapped[int] = mapped_column(
        Integer, default=30, server_default="30", nullable=False
    )
    activo: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
