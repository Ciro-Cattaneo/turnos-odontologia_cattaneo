"""Notificacion de mail encolada/enviada (KB-04; worker en C-08)."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, SmallInteger, Text, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.turno import CanalRecordatorio


class NotifTipo(enum.StrEnum):
    """Tipos de mail del dominio."""

    confirmacion = "confirmacion"
    recordatorio_24h = "recordatorio_24h"
    recordatorio_2h = "recordatorio_2h"
    cancelacion = "cancelacion"


class NotifEstado(enum.StrEnum):
    """Estado de envio en la cola."""

    pendiente = "pendiente"
    enviada = "enviada"
    fallida = "fallida"


class Notificacion(Base):
    """Mail vinculado a un turno; el worker C-08 consume `pendiente`."""

    __tablename__ = "notificacion"
    __table_args__ = (
        # D-5: el worker C-08 solo mira pendientes.
        Index(
            "ix_notif_estado",
            "estado",
            postgresql_where=text("estado = 'pendiente'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    turno_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("turno.id"), nullable=False, index=True
    )
    canal: Mapped[CanalRecordatorio] = mapped_column(
        Enum(CanalRecordatorio, native_enum=True, name="canal"),
        default=CanalRecordatorio.mail,
        server_default=CanalRecordatorio.mail.value,
        nullable=False,
    )
    tipo: Mapped[NotifTipo] = mapped_column(
        Enum(NotifTipo, native_enum=True, name="notif_tipo"), nullable=False
    )
    estado: Mapped[NotifEstado] = mapped_column(
        Enum(NotifEstado, native_enum=True, name="notif_estado"),
        default=NotifEstado.pendiente,
        server_default=NotifEstado.pendiente.value,
        nullable=False,
    )
    intentos: Mapped[int] = mapped_column(
        SmallInteger, default=0, server_default="0", nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    enviada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
