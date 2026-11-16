"""Fail-fast de configuración de producción (SC-R2; capa unit/config)."""

import pytest

from app.core.config import get_settings

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
    "ENV",
    "CANCEL_HOURS_MIN",
    "SLOT_DEFAULT_MIN",
    "REDIS_URL",
    "SMTP_TIMEOUT_S",
    "NOTIF_WORKER_ENABLED",
    "NOTIF_WORKER_INTERVAL_MIN",
    "NOTIF_WORKER_BATCH_SIZE",
]


@pytest.fixture
def env_limpio(monkeypatch, tmp_path):
    """Aísla el `.env` real de repo-root: solo cuenta el entorno del test."""
    monkeypatch.chdir(tmp_path)
    for key in MANAGED_KEYS:
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


def _completo(monkeypatch) -> None:
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)


def test_config_lista_todas_las_faltantes_ordenadas(env_limpio):
    """# AC SC-R2 ERROR — todas las faltantes, en orden alfabético."""
    _completo(env_limpio)
    env_limpio.delenv("SECRET_KEY")
    env_limpio.delenv("SMTP_PASS")

    with pytest.raises(RuntimeError) as exc_info:
        get_settings()

    mensaje = str(exc_info.value)
    assert "Missing required env var(s): SECRET_KEY, SMTP_PASS" in mensaje
    assert mensaje.index("SECRET_KEY") < mensaje.index("SMTP_PASS")


def test_config_mensaje_no_imprime_valores(env_limpio):
    """# AC SC-R2 ERROR — el error nombra variables, nunca valores (regla 10)."""
    _completo(env_limpio)
    valor_secreto = "valor-clave-que-no-debe-filtrarse-0123456789"
    env_limpio.setenv("SECRET_KEY", valor_secreto)
    env_limpio.delenv("SMTP_PASS")

    with pytest.raises(RuntimeError) as exc_faltante:
        get_settings()
    assert valor_secreto not in str(exc_faltante.value)

    env_limpio.setenv("SMTP_PASS", "changeme-ejemplo-solo-local")
    env_limpio.setenv("ENV", "prod")
    with pytest.raises(RuntimeError) as exc_produccion:
        get_settings()
    assert valor_secreto not in str(exc_produccion.value)


@pytest.mark.parametrize(
    "clave",
    [
        "changeme-" + "a" * 40,
        "clave-ejemplo-" + "b" * 40,
        "a" * 31,
    ],
    ids=["changeme", "ejemplo", "corta"],
)
def test_config_prod_rechaza_secret_key_placeholder(env_limpio, clave):
    """# AC SC-R2 ERROR — placeholder o SECRET_KEY débil bloquea prod."""
    _completo(env_limpio)
    env_limpio.setenv("ENV", "prod")
    env_limpio.setenv("SECRET_KEY", clave)

    with pytest.raises(RuntimeError) as exc_info:
        get_settings()

    mensaje = str(exc_info.value)
    assert "SECRET_KEY" in mensaje
    assert clave not in mensaje


def test_config_prod_rechaza_admin_password_y_smtp_pass_placeholder(env_limpio):
    """# AC SC-R2 ERROR — credenciales de admin/SMTP placeholder también."""
    _completo(env_limpio)
    env_limpio.setenv("ENV", "prod")
    env_limpio.setenv("SECRET_KEY", "9f" * 32)
    env_limpio.setenv("ADMIN_PASSWORD", "changeme-admin-solo-local")
    env_limpio.setenv("SMTP_PASS", "clave-ejemplo-smtp")

    with pytest.raises(RuntimeError) as exc_info:
        get_settings()

    mensaje = str(exc_info.value)
    assert "ADMIN_PASSWORD" in mensaje
    assert "SMTP_PASS" in mensaje
    assert "changeme-admin-solo-local" not in mensaje
    assert "clave-ejemplo-smtp" not in mensaje


@pytest.mark.parametrize(
    "entorno",
    [None, "development", "staging"],
    ids=["ausente", "development", "staging"],
)
def test_config_dev_y_staging_permiten_placeholders(env_limpio, entorno):
    """# AC SC-R2 BORDE — fuera de prod los placeholders locales son válidos."""
    _completo(env_limpio)
    env_limpio.setenv("SECRET_KEY", "changeme-local")
    env_limpio.setenv("ADMIN_PASSWORD", "changeme-local")
    env_limpio.setenv("SMTP_PASS", "changeme-local")
    if entorno is not None:
        env_limpio.setenv("ENV", entorno)

    settings = get_settings()

    assert settings.ENV == (entorno or "development")
    assert settings.SECRET_KEY == "changeme-local"


@pytest.mark.parametrize("valor", ["production", "PROD", ""])
def test_config_env_invalido_falla_nombrando_env(env_limpio, valor):
    """# AC SC-R2 — `ENV` fuera del enum falla nombrando el campo."""
    _completo(env_limpio)
    env_limpio.setenv("ENV", valor)

    with pytest.raises(RuntimeError) as exc_info:
        get_settings()

    assert "ENV" in str(exc_info.value)
