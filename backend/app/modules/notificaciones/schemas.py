"""Schemas estrictos del panel de fallidas (C-08 D-9, regla dura 1)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Forbid = ConfigDict(extra="forbid")


class FallidasQuery(BaseModel):
    """Query de `GET /api/notificaciones/fallidas` (keyset, sin OFFSET)."""

    model_config = Forbid

    limit: int = Field(default=50, ge=1, le=200)
    cursor: str | None = None


class FallidaItem(BaseModel):
    """Fila mínima del panel: sin payload ni PII innecesaria (D-9)."""

    model_config = Forbid

    id: UUID
    turno_id: UUID
    tipo: str
    intentos: int
    error: str | None
    enviar_en: str | None
    paciente_nombre: str | None
    paciente_email: str | None
    inicio: datetime
    fin: datetime


class FallidasPage(BaseModel):
    """Respuesta paginada del panel de fallidas."""

    model_config = Forbid

    items: list[FallidaItem]
    next_cursor: str | None
