"""Configuración por variables de entorno (capa: unit).

# AC service-config/S3 — falta SECRET_KEY → error que la nombra.
# AC service-config/S4 — defaults CANCEL_HOURS_MIN=3, SLOT_DEFAULT_MIN=30.
"""

import os

import pytest

from app.core.config import Settings, get_settings

REQUIRED_ENV = {
    "DATABASE_URL": "postgresql+psycopg://user:pass@db:5432/turnos",
    "SECRET_KEY": "clave-ficticia-solo-tests-0123456789abcdef",
    "ADMIN_EMAIL": "admin-ficticio@cattaneo.test",
    "ADMIN_PASSWORD": "password-ficticia-solo-tests",
    "SMTP_HOST": "smtp.ficticio.test",
    "SMTP_PORT": "587",
    "SMTP_USER": "usuario-ficticio",
    "SMTP_PASS": "pass-ficticia-solo-tests",
    "SMTP_FROM": "turnos@ficticio.test",
    "TZ": "America/Argentina/Buenos_Aires",
    "FRONTEND_URL": "https://turnos.ficticio.test",
}

MANAGED_KEYS = list(REQUIRED_ENV) + [
    "CANCEL_HOURS_MIN",
    "SLOT_DEFAULT_MIN",
    "REDIS_URL",
]


@pytest.fixture
def clean_env(monkeypatch):
    for key in MANAGED_KEYS:
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


def _load_full_env(monkeypatch):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)


def test_falta_secret_key_falla_nombrando_la_variable(clean_env):
    """# AC service-config/S3 — sin SECRET_KEY el boot falla nombrándola."""
    _load_full_env(clean_env)
    os.environ.pop("SECRET_KEY")

    with pytest.raises(Exception) as exc_info:
        Settings()

    assert "SECRET_KEY" in str(exc_info.value)


@pytest.mark.parametrize(
    "missing",
    [
        "DATABASE_URL",
        "SECRET_KEY",
        "ADMIN_EMAIL",
        "ADMIN_PASSWORD",
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USER",
        "SMTP_PASS",
        "SMTP_FROM",
        "TZ",
        "FRONTEND_URL",
    ],
)
def test_falta_cada_requerida_falla_nombrandola(clean_env, missing):
    """# AC service-config/S3 — cada faltante se reporta por su nombre."""
    _load_full_env(clean_env)
    os.environ.pop(missing)

    with pytest.raises(Exception) as exc_info:
        get_settings()

    assert missing in str(exc_info.value)


def test_defaults_operativos_aplican_sin_configurarlos(clean_env):
    """# AC service-config/S4 — CANCEL_HOURS_MIN=3 y SLOT_DEFAULT_MIN=30 por defecto."""
    _load_full_env(clean_env)

    settings = get_settings()

    assert settings.CANCEL_HOURS_MIN == 3
    assert settings.SLOT_DEFAULT_MIN == 30


def test_config_completa_bootea_y_reporta_timezone(clean_env):
    """# AC service-config/S4 — con todo seteado bootea y expone TZ operativa."""
    _load_full_env(clean_env)
    clean_env.setenv("CANCEL_HOURS_MIN", "5")
    clean_env.setenv("SLOT_DEFAULT_MIN", "45")

    settings = get_settings()

    assert settings.TZ == "America/Argentina/Buenos_Aires"
    assert settings.CANCEL_HOURS_MIN == 5
    assert settings.SLOT_DEFAULT_MIN == 45
    assert settings.SMTP_PORT == 587


def test_redis_url_opcional_default_none(clean_env):
    """REDIS_URL es opcional (PB-03): ausente → None; presente → se expone."""
    _load_full_env(clean_env)

    assert get_settings().REDIS_URL is None

    clean_env.setenv("REDIS_URL", "redis://redis:6379/0")
    assert get_settings().REDIS_URL == "redis://redis:6379/0"
