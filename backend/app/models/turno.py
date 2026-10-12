"""Turno + enums de lifecycle (KB-04, D-3; EXCLUDE anti-solape llega en §2/D-4)."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TurnoEstado(enum.StrEnum):
    """RN-TU-07: vocabulario cerrado de estados."""

    reservado = "reservado"
    confirmado = "confirmado"
    cancelado = "cancelado"
    atendido = "atendido"
    ausente = "ausente"


class TurnoOrigen(enum.StrEnum):
    """Origen de la reserva."""

    online = "online"
    recepcion = "recepcion"


class CanalRecordatorio(enum.StrEnum):
    """RN-NO-03: `mail` en v1; `whatsapp` requiere migracion post-v1."""

    mail = "mail"


class Turno(Base):
    """Reserva; columnas post-v1 `pago_estado`/`lista_espera_pos` sin logica."""

    __tablename__ = "turno"
    __table_args__ = (
        CheckConstraint("fin > inicio", name="ck_turno_fin_gt_inicio"),
        # NUEVA decisión §2 (revisa D-4): consistencia exacta minuto a minuto
        # en DB — el AC turno-lifecycle exige rechazo en scope modelo y C-02
        # no tiene capa app; C-05 suma pre-validación Pydantic + 400 amable.
        # `EXTRACT(EPOCH)` sobre `timestamptz` es tiempo real transcurrido
        # (exacto para TZ America/Argentina/Buenos_Aires, sin DST futuro).
        CheckConstraint(
            "(EXTRACT(EPOCH FROM (fin - inicio)) = duracion_min * 60)",
            name="ck_turno_duracion_min",
        ),
        # §2 review: nombre estable bloqueado (handoff C-01 lo dejaba abierto).
        UniqueConstraint("token_cancelacion", name="ux_turno_token"),
        Index("ix_turno_prof_inicio", "profesional_id", "inicio"),
        # D-5: parcial de activos en orden de filtro (agenda/slots/worker).
        Index(
            "ix_turno_estado_inicio",
            "estado",
            "inicio",
            postgresql_where=text("estado IN ('reservado', 'confirmado')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    profesional_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profesional.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    paciente_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("paciente.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duracion_min: Mapped[int] = mapped_column(
        Integer, default=30, server_default="30", nullable=False
    )
    estado: Mapped[TurnoEstado] = mapped_column(
        Enum(TurnoEstado, native_enum=True, name="turno_estado"),
        default=TurnoEstado.reservado,
        server_default=TurnoEstado.reservado.value,
        nullable=False,
    )
    origen: Mapped[TurnoOrigen] = mapped_column(
        Enum(TurnoOrigen, native_enum=True, name="turno_origen"), nullable=False
    )
    token_cancelacion: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    notas: Mapped[str | None] = mapped_column(Text)
    canal_recordatorio: Mapped[CanalRecordatorio] = mapped_column(
        Enum(CanalRecordatorio, native_enum=True, name="canal"),
        default=CanalRecordatorio.mail,
        server_default=CanalRecordatorio.mail.value,
        nullable=False,
    )
    pago_estado: Mapped[str | None] = mapped_column(String(20))
    lista_espera_pos: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
