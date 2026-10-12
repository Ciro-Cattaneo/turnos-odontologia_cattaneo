"""Hashing argon2id + sesiones JWT + revocación in-process (C-03 D-1/D-2/D-7).

D-1: hashes nuevos argon2id (`argon2-cffi`); `verify_password` dual por
prefijo (`$argon2id$` → argon2, `pbkdf2_sha256$` → legacy stdlib solo-lectura
heredado de `seed.py` C-02). `needs_rehash` detecta legacy para la rotación
al primer login (D-5: sin migración, el prefijo ES el marcador).
D-2: JWT HS256 (`SECRET_KEY`) con claims `{sub, rol, profesional_id, jti,
exp}`; lifetime 12h (jornada + cierre, ver open question en design).
D-7 (NUEVA, para revisión humana en archive): denylist in-process de `jti`
para que `logout` invalide de verdad en topología single-process v1
(un stateless puro dejaría la cookie reutilizable hasta `exp`, violando el
AC `staff-auth/Logout-invalida`); podado perezoso por `exp`.
"""

import hashlib
import hmac
import time
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

ARGON2_PREFIX = "$argon2id$"
LEGACY_PREFIX = "pbkdf2_sha256$"
SESSION_LIFETIME_H = 12
COOKIE_NAME = "session"

_hasher = PasswordHasher()
_dummy_hash = _hasher.hash("dummy-ficticio-solo-antienumeracion")

_revoked: dict[str, float] = {}


def hash_password(password: str) -> str:
    """Hash argon2id con salt aleatorio (nunca plaintext)."""
    return _hasher.hash(password)


def _verify_legacy(password: str, guardado: str) -> bool:
    """Verify-only del formato transitorio C-02 (stdlib, tiempo constante)."""
    try:
        esquema, iteraciones, salt_hex, hash_hex = guardado.split("$")
        assert esquema == "pbkdf2_sha256"
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iteraciones)
        )
    except (ValueError, AssertionError):
        return False
    return hmac.compare_digest(digest.hex(), hash_hex)


def verify_password(password: str, guardado: str) -> bool:
    """Verifica dual por prefijo; formato desconocido/corrupto → False."""
    if guardado.startswith(ARGON2_PREFIX):
        try:
            return _hasher.verify(guardado, password)
        except (VerificationError, InvalidHashError, ValueError, AttributeError):
            return False
    if guardado.startswith(LEGACY_PREFIX):
        return _verify_legacy(password, guardado)
    return False


def needs_rehash(guardado: str) -> bool:
    """True si el hash no está en el esquema final (incluye corruptos)."""
    return not guardado.startswith(ARGON2_PREFIX)


def dummy_verify() -> bool:
    """Verify dummy argon2 para igualar tiempos en email desconocido (D-6)."""
    try:
        return _hasher.verify(_dummy_hash, "dummy-ficticio-incorrecto")
    except VerificationError:
        return False


def create_session_token(
    *,
    user_id: str,
    rol: str,
    profesional_id: str | None,
    secret: str,
    lifetime_h: int = SESSION_LIFETIME_H,
) -> str:
    """JWT HS256 con `jti` único (cada login = sesión independiente)."""
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": user_id,
            "rol": rol,
            "profesional_id": profesional_id,
            "jti": uuid.uuid4().hex,
            "iat": now,
            "exp": now + timedelta(hours=lifetime_h),
        },
        secret,
        algorithm="HS256",
    )


def decode_session_token(token: str, secret: str) -> dict:
    """Decodifica y valida firma + `exp`; cualquier fallo → ValueError."""
    try:
        data = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise ValueError("sesión inválida") from exc
    if not isinstance(data, dict) or "sub" not in data or "jti" not in data:
        raise ValueError("sesión inválida")
    return data


def revoke_session(jti: str, exp_ts: float) -> None:
    """Revoca un `jti` hasta su `exp` (logout real en single-process, D-7)."""
    _prune(time.time())
    _revoked[jti] = exp_ts


def is_session_revoked(jti: str) -> bool:
    """True si el `jti` fue revocado y aún no expiró."""
    _prune(time.time())
    return jti in _revoked


def _prune(now: float) -> None:
    """Descarta revocaciones ya expiradas (conjunto acotado)."""
    for jti in [k for k, exp in _revoked.items() if exp <= now]:
        del _revoked[jti]
