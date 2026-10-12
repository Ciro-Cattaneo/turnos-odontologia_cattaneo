"""Disponibilidad semanal recurrente por profesional (KB-04)."""

import uuid
from datetime import date, time

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    SmallInteger,
    Time,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Disponibilidad(Base):
    """Ventana semanal; sin solape mismo profesional+dia (validacion app, C-04)."""

    __tablename__ = "disponibilidad"
    __table_args__ = (
        CheckConstraint("hora_desde < hora_hasta", name="ck_disponibilidad_horario"),
        # D-5: orden = filtro de agenda (profesional + día).
        Index("ix_disponibilidad_prof_dia", "profesional_id", "dia_semana"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    profesional_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profesional.id"), nullable=False, index=True
    )
    dia_semana: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    hora_desde: Mapped[time] = mapped_column(Time, nullable=False)
    hora_hasta: Mapped[time] = mapped_column(Time, nullable=False)
    vigente_desde: Mapped[date | None] = mapped_column(Date)
    vigente_hasta: Mapped[date | None] = mapped_column(Date)
