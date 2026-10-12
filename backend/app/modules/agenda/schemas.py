"""Schemas estrictos de agenda/disponibilidad (C-04 D-6, regla dura 1).

Todos con `extra='forbid'` — campo desconocido → 400 con detalle por campo
(el mapeo HTTP ValidationError→400 vive en `app.main`; aquí el contrato
Pydantic que los tests de capa schemas verifican).
"""

from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Forbid = ConfigDict(extra="forbid")

# Tope de rango público (D-6/D-2: evita cómputo degradado en rangos amplios).
MAX_RANGO_DIAS = 31


class ProfesionalPublico(BaseModel):
    """Fila pública de `GET /api/profesionales` (sin datos staff internos)."""

    model_config = Forbid

    id: UUID
    nombre: str
    especialidad: str | None = None
    matricula: str | None = None
    duracion_default_min: int
    ultima_actualizacion: datetime | None = None


class ProfesionalesQuery(BaseModel):
    """Query keyset de `GET /api/profesionales` (sin OFFSET)."""

    model_config = Forbid

    limit: int = Field(default=20, ge=1, le=100)
    cursor: UUID | None = None


class DisponibilidadQuery(BaseModel):
    """Query de `GET /api/disponibilidad` (tope 31 días, 400 por campo)."""

    model_config = Forbid

    profesional_id: UUID
    desde: datetime
    hasta: datetime

    @model_validator(mode="after")
    def _rango_valido(self) -> "DisponibilidadQuery":
        if self.desde >= self.hasta:
            raise ValueError("`desde` debe ser anterior a `hasta`")
        if (self.hasta - self.desde).days > MAX_RANGO_DIAS:
            raise ValueError("rango máximo 31 días")
        return self


class AgendaQuery(BaseModel):
    """Query de `GET /api/profesionales/{id}/agenda` (`vista=dia|semana`)."""

    model_config = Forbid

    vista: Literal["dia", "semana"] = "dia"
    fecha: date

    @field_validator("fecha", mode="before")
    @classmethod
    def _fecha_valida(cls, v: object) -> object:
        if isinstance(v, str):
            try:
                return date.fromisoformat(v)
            except ValueError:
                raise ValueError("`fecha` debe ser ISO YYYY-MM-DD") from None
        return v


class DisponibilidadCreate(BaseModel):
    """Body `POST /api/disponibilidades` (staff; validación sin solape en servicio)."""

    model_config = Forbid

    profesional_id: UUID
    dia_semana: int = Field(ge=0, le=6)
    hora_desde: time
    hora_hasta: time
    vigente_desde: date | None = None
    vigente_hasta: date | None = None

    @model_validator(mode="after")
    def _horario_valido(self) -> "DisponibilidadCreate":
        if self.hora_desde >= self.hora_hasta:
            raise ValueError("`hora_desde` debe ser anterior a `hora_hasta`")
        if (
            self.vigente_desde is not None
            and self.vigente_hasta is not None
            and self.vigente_desde > self.vigente_hasta
        ):
            raise ValueError("`vigente_desde` debe ser anterior a `vigente_hasta`")
        return self


class BloqueoCreate(BaseModel):
    """Body `POST /api/bloqueos` (`motivo` obligatorio non-empty)."""

    model_config = Forbid

    profesional_id: UUID
    desde: datetime
    hasta: datetime
    motivo: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _valido(self) -> "BloqueoCreate":
        if self.desde >= self.hasta:
            raise ValueError("`desde` debe ser anterior a `hasta`")
        if not self.motivo.strip():
            raise ValueError("`motivo` no puede ser vacío")
        return self
