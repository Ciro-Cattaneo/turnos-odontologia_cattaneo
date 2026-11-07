"""Configuración del servicio por variables de entorno (KB-08).

Excepción D-2 (aprobada en revisión humana): `Settings` usa
`extra='ignore'` — la regla dura 1 (`extra='forbid'`) sigue vigente
para TODOS los schemas de API. `forbid` aquí rompería el boot ante
cualquier variable ajena exportada por el host/CI.
"""

from pydantic import ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """13 vars KB-08 + `REDIS_URL` y las 4 vars del worker (PB-03/D-11)."""

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
    SMTP_TIMEOUT_S: int = 15
    NOTIF_WORKER_ENABLED: bool = True
    NOTIF_WORKER_INTERVAL_MIN: int = 5
    NOTIF_WORKER_BATCH_SIZE: int = 20

    @field_validator("NOTIF_WORKER_INTERVAL_MIN")
    @classmethod
    def _intervalo_valido(cls, value: int) -> int:
        """D-11: el loop del worker solo admite 5–10 minutos."""
        if not 5 <= value <= 10:
            raise ValueError(
                "NOTIF_WORKER_INTERVAL_MIN debe estar entre 5 y 10 "
                f"minutos (recibido: {value})"
            )
        return value


def get_settings() -> Settings:
    """Construye `Settings` con fail-fast claro (faltantes o inválidas)."""
    try:
        return Settings()
    except ValidationError as exc:
        errores = exc.errors()
        missing = sorted(
            {
                str(loc)
                for err in errores
                if err.get("type") == "missing"
                for loc in err["loc"]
                if loc
            }
        )
        if missing:
            raise RuntimeError(
                f"Missing required env var(s): {', '.join(missing)}"
            ) from exc
        detalle = "; ".join(err.get("msg", "valor inválido") for err in errores)
        raise RuntimeError(f"Invalid configuration: {detalle}") from exc
