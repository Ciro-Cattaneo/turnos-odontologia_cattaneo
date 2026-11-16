"""Configuración del servicio por variables de entorno (KB-08).

Excepción D-2 (aprobada en revisión humana): `Settings` usa
`extra='ignore'` — la regla dura 1 (`extra='forbid'`) sigue vigente
para TODOS los schemas de API. `forbid` aquí rompería el boot ante
cualquier variable ajena exportada por el host/CI.
"""

from typing import Literal

from pydantic import ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_MARKERS = ("changeme", "ejemplo", "ficticio")
_SECRET_KEY_MIN_LEN = 32


class Settings(BaseSettings):
    """13 vars KB-08 + `REDIS_URL` y las 4 vars del worker (PB-03/D-11)."""

    model_config = SettingsConfigDict(extra="ignore", env_file=".env")

    ENV: Literal["development", "staging", "prod"] = "development"
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
    STATIC_DIR: str = "static"
    CONSULTORIO_CONTACTO: str = (
        "Comunicate con el consultorio para coordinar la cancelación"
    )
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


def _es_placeholder(valor: str) -> bool:
    """Marcadores conocidos de valor ficticio (`changeme-*`, `*-ejemplo`)."""
    normalizado = valor.lower()
    return any(marca in normalizado for marca in _PLACEHOLDER_MARKERS)


def _validar_produccion(settings: Settings) -> None:
    """SC-R2/D-4: en `prod` se rechazan placeholders y `SECRET_KEY` débil.

    Solo se nombran los campos inválidos; nunca se imprime su valor.
    """
    if settings.ENV != "prod":
        return
    invalidos = []
    if len(settings.SECRET_KEY) < _SECRET_KEY_MIN_LEN or _es_placeholder(
        settings.SECRET_KEY
    ):
        invalidos.append("SECRET_KEY")
    if _es_placeholder(settings.ADMIN_PASSWORD):
        invalidos.append("ADMIN_PASSWORD")
    if _es_placeholder(settings.SMTP_PASS):
        invalidos.append("SMTP_PASS")
    if invalidos:
        raise RuntimeError(
            "Unsafe production configuration (placeholder or weak secret): "
            f"{', '.join(sorted(invalidos))}"
        )


def get_settings() -> Settings:
    """Construye `Settings` con fail-fast claro (faltantes o inválidas)."""
    try:
        settings = Settings()
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
        detalle = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or 'config'}: "
            f"{err.get('msg', 'valor inválido')}"
            for err in errores
        )
        raise RuntimeError(f"Invalid configuration: {detalle}") from exc
    _validar_produccion(settings)
    return settings
