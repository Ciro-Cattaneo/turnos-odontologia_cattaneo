"""Ayudas públicas de agenda (C-04 D-5/D-6): throttle + query estricta + staff opcional.

Routers delgados (D-1): la lógica vive en `slot_service`; aquí solo el borde
HTTP (parseo `extra='forbid'` → 400, rate-limit 30/min/IP → 429, sesión
opcional para la rama pública/staff de la agenda).
"""

from fastapi import Request
from fastapi.exceptions import HTTPException
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.core import ratelimit
from app.core.config import get_settings
from app.core.security import decode_session_token, is_session_revoked
from app.models.usuario_staff import UsuarioStaff


def parse_query_or_400[T: BaseModel](model: type[T], raw: dict[str, str]) -> T:
    """Valida query contra `model` (`extra='forbid'`); error → 400 por campo."""
    try:
        return model(**raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400, detail=[_formato_error(e) for e in exc.errors()]
        ) from None


def _formato_error(e: dict) -> dict:
    loc = e.get("loc", ())
    return {
        "campo": ".".join(str(p) for p in loc) if loc else "query",
        "error": e.get("msg", "valor inválido"),
        "tipo": e.get("type", "value_error"),
    }


def public_throttle(request: Request) -> None:
    """Dependencia: 30 req/min/IP ventana fija; excedido → 429 + `Retry-After`."""
    ip = request.client.host if request.client else "desconocida"
    pasa, retry = ratelimit.check_public_rate_limit(f"agenda-publica:{ip}")
    if not pasa:
        raise HTTPException(
            status_code=429,
            detail="Demasiadas consultas",
            headers={"Retry-After": str(max(1, int(retry) + 1))},
        )


def staff_opcional(request: Request, db: Session) -> UsuarioStaff | None:
    """Sesión staff si hay cookie; `None` si no hay (rama pública).

    Cookie presente pero inválida/expirada/revocada/inactiva → 401 genérico
    (no se degrada a público: una sesión rota no es anonimato).
    """
    from uuid import UUID

    token = request.cookies.get("session")
    if not token:
        return None
    try:
        claims = decode_session_token(token, get_settings().SECRET_KEY)
    except ValueError:
        raise HTTPException(status_code=401, detail="No autenticado") from None
    if is_session_revoked(claims["jti"]):
        raise HTTPException(status_code=401, detail="No autenticado") from None
    try:
        user_id = UUID(str(claims["sub"]))
    except ValueError:
        raise HTTPException(status_code=401, detail="No autenticado") from None
    usuario = (
        db.query(UsuarioStaff).filter(UsuarioStaff.id == user_id).one_or_none()
    )
    if usuario is None or not usuario.activo:
        raise HTTPException(status_code=401, detail="No autenticado") from None
    return usuario
