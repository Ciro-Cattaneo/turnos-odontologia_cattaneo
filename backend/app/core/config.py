"""Configuración del servicio por variables de entorno (KB-08).

Excepción D-2 (aprobada en revisión humana): `Settings` usa
`extra='ignore'` — la regla dura 1 (`extra='forbid'`) sigue vigente
para TODOS los schemas de API. `forbid` aquí rompería el boot ante
cualquier variable ajena exportada por el host/CI.
"""

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """13 vars KB-08 + `REDIS_URL` opcional (PB-03, solo documentada)."""

    model_config = SettingsConfigDict(extra="ignore", env_file=".env")

    DATABASE_URL: str
    SECRET_KEY: str
    ADMIN_EMAIL: str
    ADMIN_PASSWORD: str
    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USER: str
    SMTP_PASS: str
    SMTP_FROM: str
    TZ: str
    FRONTEND_URL: str
    CANCEL_HOURS_MIN: int = 3
    SLOT_DEFAULT_MIN: int = 30
    REDIS_URL: str | None = None


def get_settings() -> Settings:
    """Construye `Settings` con fail-fast que nombra la(s) faltante(s)."""
    try:
        return Settings()
    except ValidationError as exc:
        missing = sorted(
            {str(loc) for err in exc.errors() for loc in err["loc"] if loc}
        )
        names = ", ".join(missing) if missing else exc.title
        raise RuntimeError(f"Missing required env var(s): {names}") from exc
