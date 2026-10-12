"""Schemas del módulo auth (C-03 D-6: estrictos, `extra='forbid'`).

Regla dura 1: TODO schema de API usa `extra='forbid'` + 400 con detalle por
campo (la única excepción aprobada es `Settings`, no esto).
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.usuario_staff import StaffRol


class LoginIn(BaseModel):
    """Body de `POST /api/auth/login`: solo email + password."""

    model_config = ConfigDict(extra="forbid")

    # `str` + patrón (no `EmailStr`): el validador RFC rechaza el TLD
    # reservado `.test` que la regla dura 12 exige en fixtures; el login
    # nunca verifica deliverability (D-6: la existencia no se revela).
    email: str = Field(min_length=3, max_length=320, pattern=r".+@.+\..+")
    password: str = Field(min_length=1, max_length=256)


class LoginOut(BaseModel):
    """Respuesta de login: conveniencia sin hash ni token (D-6)."""

    model_config = ConfigDict(extra="forbid")

    email: str
    rol: StaffRol


class MeOut(BaseModel):
    """Respuesta de `GET /api/auth/me` para la UI staff (C-10 consume)."""

    model_config = ConfigDict(extra="forbid")

    email: str
    rol: StaffRol
    profesional_id: UUID | None
