"""Schemas estrictos de reserva online (C-05 D-1/D-4/D-11, regla dura 1).

`extra='forbid'` en raíz y anidados; `email` con patrón propio (no `EmailStr`,
que rechaza el TLD reservado `.test` de la regla dura 12); `inicio` debe ser
aware y `parse_body_or_400` normaliza el `loc` de Pydantic a `campo`.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi.exceptions import HTTPException
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

from app.models.turno import TurnoEstado

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


class CancelacionOut(BaseModel):
    """Respuesta `200` de cancelación: solo campos públicos (C-06 D-11)."""

    model_config = Forbid

    id: UUID
    estado: str
    inicio: str
    fin: str
    duracion_min: int
    notificaciones_encoladas: bool
    mensaje: str


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


class TurnoCreateStaff(TurnoCreate):
    """Body staff de `POST /api/turnos` (D-1): exige `origen=recepcion`."""

    origen: Literal["recepcion"]


class TurnoStaffOut(BaseModel):
    """Respuesta `201` staff sin la credencial del paciente (D-3)."""

    model_config = Forbid

    id: UUID
    estado: str
    inicio: str
    fin: str
    duracion_min: int
    notificaciones_encoladas: bool


class TurnoReprogramar(BaseModel):
    """Body de `PUT /api/turnos/{id}` (D-4): al menos un campo."""

    model_config = Forbid

    inicio: datetime | None = None
    duracion_min: int | None = None

    @field_validator("inicio")
    @classmethod
    def _inicio_aware(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return v
        if v.tzinfo is None or v.utcoffset() is None:
            raise PydanticCustomError(
                "inicio_sin_zona", "`inicio` debe incluir zona horaria"
            )
        return v

    @model_validator(mode="after")
    def _al_menos_uno(self) -> "TurnoReprogramar":
        if self.inicio is None and self.duracion_min is None:
            raise ValueError("se requiere `inicio` o `duracion_min`")
        return self


class ReprogramacionOut(BaseModel):
    """Respuesta `200` de reprogramación."""

    model_config = Forbid

    id: UUID
    estado: str
    inicio: str
    fin: str
    duracion_min: int
    notificaciones_encoladas: bool


class CorreccionPacienteIn(BaseModel):
    """Body de `PUT /api/turnos/{id}/paciente` (D-7): DNI/teléfono/OS."""

    model_config = Forbid

    dni: str | None = None
    telefono: str | None = None
    obra_social: str | None = None

    @field_validator("dni")
    @classmethod
    def _dni_valido(cls, v: str | None) -> str | None:
        if v is None:
            return v
        valor = v.strip()
        if not valor.isdigit() or not 7 <= len(valor) <= 8:
            raise PydanticCustomError(
                "dni_formato", "`dni` debe tener 7 u 8 dígitos"
            )
        return valor

    @field_validator("telefono")
    @classmethod
    def _telefono_valido(cls, v: str | None) -> str | None:
        if v is None:
            return v
        valor = v.strip()
        if len(valor) < 3:
            raise PydanticCustomError(
                "telefono_invalido", "`telefono` no puede estar vacío"
            )
        return valor

    @field_validator("obra_social")
    @classmethod
    def _obra_social_valida(cls, v: str | None) -> str | None:
        if v is None:
            return v
        valor = v.strip()
        if not valor:
            raise PydanticCustomError(
                "obra_social_invalida", "`obra_social` no puede estar vacía"
            )
        return valor

    @model_validator(mode="after")
    def _al_menos_uno(self) -> "CorreccionPacienteIn":
        if self.dni is None and self.telefono is None and self.obra_social is None:
            raise ValueError("se requiere `dni`, `telefono` u `obra_social`")
        return self


class PacienteCorregidoOut(BaseModel):
    """Datos vigentes del paciente tras la corrección."""

    model_config = Forbid

    id: UUID
    nombre: str | None
    dni: str | None
    telefono: str | None
    obra_social: str | None
    email: str | None
    activo: bool


class CorreccionPacienteOut(BaseModel):
    """Respuesta `200` de corrección de paciente."""

    model_config = Forbid

    id: UUID
    paciente: PacienteCorregidoOut
    notificaciones_encoladas: bool


class EstadoUpdate(BaseModel):
    """Body de `PATCH /api/turnos/{id}/estado` (D-5)."""

    model_config = Forbid

    estado: TurnoEstado


class EstadoOut(BaseModel):
    """Respuesta `200` de transición de estado."""

    model_config = Forbid

    id: UUID
    estado: str
    estado_previo: str
    notificaciones_encoladas: bool


class MotivoCancelacionIn(BaseModel):
    """Body opcional de `DELETE /api/turnos/{id}` staff (D-6)."""

    model_config = Forbid

    motivo: str | None = None

    @field_validator("motivo")
    @classmethod
    def _motivo_valido(cls, v: str | None) -> str | None:
        if v is None:
            return v
        valor = v.strip()
        if len(valor) < 3:
            raise PydanticCustomError(
                "motivo_invalido", "`motivo` debe tener al menos 3 caracteres"
            )
        return valor


class FichaQuery(BaseModel):
    """Query estricta de `GET /api/turnos/{id}` (D-9)."""

    model_config = Forbid

    historial_limit: int = Field(default=50, ge=1, le=100)
    historial_cursor: str | None = None


class ProfesionalFichaOut(BaseModel):
    """Datos mínimos del profesional en la ficha."""

    model_config = Forbid

    id: UUID
    nombre: str
    especialidad: str | None


class PacienteFichaOut(BaseModel):
    """Datos del paciente en la ficha (sin token de cancelación)."""

    model_config = Forbid

    id: UUID
    nombre: str | None
    dni: str | None
    telefono: str | None
    obra_social: str | None
    email: str | None
    activo: bool


class AuditoriaItemOut(BaseModel):
    """Fila del historial de auditoría."""

    model_config = Forbid

    id: UUID
    accion: str
    actor: dict
    created_at: datetime
    detalle: dict


class AuditoriaPageOut(BaseModel):
    """Página keyset del historial."""

    model_config = Forbid

    items: list[AuditoriaItemOut]
    next_cursor: str | None


class TurnoFichaOut(BaseModel):
    """Ficha `200` con turno, profesional, paciente e historial."""

    model_config = Forbid

    id: UUID
    estado: str
    origen: str
    inicio: datetime
    fin: datetime
    duracion_min: int
    profesional: ProfesionalFichaOut
    paciente: PacienteFichaOut
    auditoria: AuditoriaPageOut


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
