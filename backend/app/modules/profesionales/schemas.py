"""Schemas estrictos del CRUD admin de profesionales (C-11 D-3).

`extra='forbid'` + 400 por campo (regla dura 1). `duracion_default_min`
5–240 múltiplo de 5 (convención D-16); `matricula`/`especialidad` opcionales.
`ProfesionalAdminOut` nunca incluye turnos ni conteos.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Forbid = ConfigDict(extra="forbid")


def _trim_nombre(v: object) -> object:
    return v.strip() if isinstance(v, str) else v


class ProfesionalCreate(BaseModel):
    """Body `POST /api/profesionales` (admin)."""

    model_config = Forbid

    nombre: str = Field(min_length=1, max_length=120)
    matricula: str | None = Field(default=None, min_length=1, max_length=50)
    especialidad: str | None = Field(default=None, min_length=1, max_length=100)
    duracion_default_min: int = Field(default=30, ge=5, le=240, multiple_of=5)

    @field_validator("nombre", mode="before")
    @classmethod
    def _nombre_no_vacio(cls, v: object) -> object:
        return _trim_nombre(v)


class ProfesionalUpdate(BaseModel):
    """Body `PUT /api/profesionales/{id}`: todos opcionales, al menos uno."""

    model_config = Forbid

    nombre: str = Field(default=None, min_length=1, max_length=120)  # type: ignore[assignment]
    matricula: str | None = Field(default=None, min_length=1, max_length=50)
    especialidad: str | None = Field(default=None, min_length=1, max_length=100)
    duracion_default_min: int = Field(  # type: ignore[assignment]
        default=None, ge=5, le=240, multiple_of=5
    )
    activo: bool | None = None

    @field_validator("nombre", mode="before")
    @classmethod
    def _nombre_no_vacio(cls, v: object) -> object:
        return _trim_nombre(v)

    @model_validator(mode="after")
    def _al_menos_uno(self) -> "ProfesionalUpdate":
        if not self.model_fields_set:
            raise ValueError("el body debe traer al menos un campo")
        return self


class ProfesionalAdminOut(BaseModel):
    """Recurso admin de profesional (sin turnos, D-3)."""

    model_config = Forbid

    id: UUID
    nombre: str
    matricula: str | None = None
    especialidad: str | None = None
    duracion_default_min: int
    activo: bool
    ultima_actualizacion: datetime | None = None


class EliminarProfesionalQuery(BaseModel):
    """Query de `DELETE /api/profesionales/{id}`: sin parámetros (no `?fisico`)."""

    model_config = Forbid
