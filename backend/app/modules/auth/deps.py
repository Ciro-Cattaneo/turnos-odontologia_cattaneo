"""Dependencias de autenticación/autorización staff (C-03 D-2/D-3).

Contrato estable para C-04/C-07 (opción A aprobada — importar, no duplicar):
- `from app.modules.auth.deps import get_current_staff, require_role,`
  `require_own_profesional`
- `get_current_staff`: sesión válida desde DB (autoridad) o 401 genérico.
- `require_role(*roles)`: 401 sin sesión; 403 con sesión pero rol ajeno.
  Jerarquía: `admin` pasa todo; `recepcion`/`odontologo` solo su cadena.
- `require_own_profesional(profesional_id, staff)`: 401 sin sesión; `admin`
  pasa; resto exige link propio igual (mismatch o NULL → 403 sin datos).

Semántica 401-vs-403 (D-6): 401 = sin sesión válida (ausente/inválida/
expirada/revocada/inactiva); 403 = sesión válida sin permiso. Mensajes
genéricos, sin revelar existencia del recurso ni del usuario.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Cookie, Depends
from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decode_session_token, is_session_revoked
from app.db.session import get_db
from app.models.usuario_staff import UsuarioStaff

UNAUTHORIZED = HTTPException(status_code=401, detail="No autenticado")
FORBIDDEN = HTTPException(status_code=403, detail="Sin permiso")

DbSession = Annotated[Session, Depends(get_db)]


def get_current_staff(
    session: Annotated[str | None, Cookie(alias="session")] = None,
    db: DbSession = None,  # type: ignore[assignment]
) -> UsuarioStaff:
    """Carga el staff desde la cookie; DB manda sobre los claims (D-2)."""
    if not session:
        raise UNAUTHORIZED
    try:
        claims = decode_session_token(session, get_settings().SECRET_KEY)
    except ValueError:
        raise UNAUTHORIZED from None
    if is_session_revoked(claims["jti"]):
        raise UNAUTHORIZED from None
    try:
        user_id = UUID(str(claims["sub"]))
    except ValueError:
        raise UNAUTHORIZED from None
    usuario = (
        db.query(UsuarioStaff).filter(UsuarioStaff.id == user_id).one_or_none()
    )
    if usuario is None or not usuario.activo:
        raise UNAUTHORIZED from None
    return usuario


# Alias tras la definición (C-04/C-07 lo usan en firmas de ruta).
CurrentStaff = Annotated[UsuarioStaff, Depends(get_current_staff)]


def require_role(*roles: str):
    """Fábrica de dependencia: exige sesión + uno de `roles` (o `admin`)."""

    def _check(staff: CurrentStaff) -> UsuarioStaff:
        if staff.rol == "admin" or staff.rol.value in roles:
            return staff
        raise FORBIDDEN from None

    return _check


def require_own_profesional(
    profesional_id: UUID | None,
    staff: CurrentStaff,
) -> UsuarioStaff:
    """Scoping odontólogo: `admin` pasa; resto exige `profesional_id` propio."""
    if staff.rol == "admin":
        return staff
    if staff.profesional_id is None or profesional_id is None:
        raise FORBIDDEN from None
    if UUID(str(staff.profesional_id)) != UUID(str(profesional_id)):
        raise FORBIDDEN from None
    return staff
