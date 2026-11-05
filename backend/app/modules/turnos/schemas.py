"""Schemas estrictos de reserva online (C-05 D-1/D-4/D-11, regla dura 1).

`extra='forbid'` en raíz y anidados; `email` con patrón propio (no `EmailStr`,
que rechaza el TLD reservado `.test` de la regla dura 12); `inicio` debe ser
aware y `parse_body_or_400` normaliza el `loc` de Pydantic a `campo`.
"""

from datetime import datetime
from uuid import UUID

from fastapi.exceptions import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from pydantic_core import PydanticCustomError

Forbid = ConfigDict(extra="forbid")


class PacienteIn(BaseModel):
    """Los cinco datos obligatorios del paciente (RN-TU-01/PB-02)."""

    model_config = Forbid

    nombre: str = Field(min_length=1, max_length=120)
    dni: str = Field(min_length=1, max_length=20)
    telefono: str = Field(min_length=1, max_length=30)
    obra_social: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=320, pattern=r".+@.+\..+")

    @field_validator("nombre", "dni", "telefono", "obra_social", "email", mode="before")
    @classmethod
    def _trim(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v


class TurnoCreate(BaseModel):
    """Body de `POST /api/turnos` (público, sin login)."""

    model_config = Forbid

    profesional_id: UUID
    inicio: datetime
    duracion_min: int | None = None
    paciente: PacienteIn

    @field_validator("inicio")
    @classmethod
    def _inicio_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise PydanticCustomError(
                "inicio_sin_zona", "`inicio` debe incluir zona horaria"
            )
        return v


class ProfesionalResumen(BaseModel):
    """Resumen público del profesional en la respuesta de reserva."""

    model_config = Forbid

    id: UUID
    nombre: str


class PacienteResumen(BaseModel):
    """Datos de contacto devueltos al paciente que reservó."""

    model_config = Forbid

    nombre: str
    dni: str
    email: str


class TurnoOut(BaseModel):
    """Respuesta `201` de reserva (D-11)."""

    model_config = Forbid

    id: UUID
    estado: str
    inicio: str
    fin: str
    duracion_min: int
    profesional: ProfesionalResumen
    paciente: PacienteResumen
    token_cancelacion: UUID
    cancel_url: str
    notificaciones_encoladas: bool


class AlternativoOut(BaseModel):
    """Slot alternativo del mismo día local."""

    model_config = Forbid

    inicio: str
    fin: str
    duracion_min: int


class AlternativosOut(BaseModel):
    """Detalle del `409` de disponibilidad (D-6/D-11)."""

    model_config = Forbid

    codigo: str
    alternativos: list[AlternativoOut]


def _formato_error(e: dict) -> dict:
    loc = [p for p in e.get("loc", ()) if p != "body"]
    return {
        "campo": ".".join(str(p) for p in loc) if loc else "body",
        "error": e.get("msg", "valor inválido"),
        "tipo": e.get("type", "value_error"),
    }


def parse_body_or_400[T: BaseModel](model: type[T], raw: dict) -> T:
    """Valida el body contra `model`; `ValidationError` → `400` por campo."""
    try:
        return model(**raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400, detail=[_formato_error(e) for e in exc.errors()]
        ) from None
