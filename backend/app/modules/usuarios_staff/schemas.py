"""Schemas estrictos de usuarios staff (C-11 D-6).

Invariante `rol=odontologo ⇔ profesional_id` validado en alta y sobre el
estado resultante de la edición. `email` 3–320 y `password` 8–256
(convenciones D-16); la respuesta nunca incluye `password_hash`.
"""

from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from app.models.usuario_staff import StaffRol

Forbid = ConfigDict(extra="forbid")


def validar_vinculo_rol(rol: StaffRol, profesional_id: UUID | None) -> UUID | None:
    """Invariante de identidad: solo `odontologo` lleva `profesional_id`."""
    if rol == StaffRol.odontologo:
        if profesional_id is None:
            raise ValueError("un usuario odontologo exige `profesional_id`")
    elif profesional_id is not None:
        raise ValueError("solo el rol odontologo admite `profesional_id`")
    return profesional_id


class UsuarioStaffCreate(BaseModel):
    """Body `POST /api/usuarios-staff` (admin)."""

    model_config = ConfigDict(extra="forbid", validate_default=True)

    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+$")
    password: str = Field(min_length=8, max_length=256)
    rol: StaffRol
    profesional_id: UUID | None = None

    @field_validator("profesional_id")
    @classmethod
    def _invariante(
        cls, v: UUID | None, info: ValidationInfo
    ) -> UUID | None:
        rol = info.data.get("rol")
        if rol is None:
            return v
        return validar_vinculo_rol(rol, v)


class UsuarioStaffUpdate(BaseModel):
    """Body `PUT /api/usuarios-staff/{id}`: rol/vínculo/activo, al menos uno."""

    model_config = Forbid

    rol: StaffRol | None = None
    profesional_id: UUID | None = None
    activo: bool | None = None

    @model_validator(mode="after")
    def _al_menos_uno(self) -> "UsuarioStaffUpdate":
        if not self.model_fields_set:
            raise ValueError("el body debe traer al menos un campo")
        return self


class UsuarioStaffOut(BaseModel):
    """Recurso de usuario staff (sin `password_hash`)."""

    model_config = Forbid

    id: UUID
    email: str
    rol: StaffRol
    profesional_id: UUID | None = None
    activo: bool


class UsuariosStaffQuery(BaseModel):
    """Query de `GET /api/usuarios-staff`: keyset por `id`, sin OFFSET."""

    model_config = Forbid

    limit: int = Field(default=20, ge=1, le=100)
    cursor: UUID | None = None


class ListadoUsuariosStaffOut(BaseModel):
    """Página keyset de usuarios staff (activos e inactivos, sin hash)."""

    model_config = Forbid

    items: list[UsuarioStaffOut]
    next_cursor: str | None = None
