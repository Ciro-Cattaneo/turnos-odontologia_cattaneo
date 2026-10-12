"""Endpoints de sesión staff (C-03 D-2/D-4/D-6)."""

from fastapi import APIRouter, Cookie, Request, Response
from fastapi.exceptions import HTTPException

from app.core.config import get_settings
from app.core.ratelimit import check_rate_limit
from app.core.security import (
    COOKIE_NAME,
    SESSION_LIFETIME_H,
    create_session_token,
    decode_session_token,
    revoke_session,
)
from app.modules.auth import service
from app.modules.auth.deps import CurrentStaff, DbSession
from app.modules.auth.schemas import LoginIn, LoginOut, MeOut

router = APIRouter(prefix="/api/auth", tags=["auth"])

_CREDENCIALES = HTTPException(status_code=401, detail="Credenciales inválidas")
_LIMITE = HTTPException(status_code=429, detail="Demasiados intentos")


def _cookie_secure() -> bool:
    """`Secure` según entorno sin nueva env var: https del front (D-2)."""
    return get_settings().FRONTEND_URL.startswith("https")


@router.post("/login", response_model=LoginOut)
def login(
    body: LoginIn,
    request: Request,
    response: Response,
    db: DbSession,
) -> LoginOut:
    """Autentica staff y emite JWT HS256 en cookie httpOnly (D-2)."""
    ip = request.client.host if request.client else "desconocida"
    if not check_rate_limit(ip):
        raise _LIMITE from None
    usuario = service.authenticate(db, body.email, body.password)
    if usuario is None:
        raise _CREDENCIALES from None
    token = create_session_token(
        user_id=str(usuario.id),
        rol=usuario.rol.value,
        profesional_id=str(usuario.profesional_id) if usuario.profesional_id else None,
        secret=get_settings().SECRET_KEY,
    )
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=SESSION_LIFETIME_H * 3600,
        path="/",
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(),
    )
    return LoginOut(email=usuario.email, rol=usuario.rol)


@router.post("/logout")
def logout(
    response: Response,
    session: str | None = Cookie(default=None, alias="session"),
) -> dict[str, bool]:
    """Revoca la sesión (D-7) y limpia la cookie; sin sesión es no-op 200."""
    if session:
        try:
            claims = decode_session_token(session, get_settings().SECRET_KEY)
            revoke_session(claims["jti"], float(claims["exp"]))
        except ValueError:
            pass
    response.delete_cookie(COOKIE_NAME, path="/", samesite="lax")
    return {"ok": True}


@router.get("/me", response_model=MeOut)
def me(staff: CurrentStaff) -> MeOut:
    """Identidad mínima de la sesión para la UI staff (C-10 consume)."""
    return MeOut(email=staff.email, rol=staff.rol, profesional_id=staff.profesional_id)
