"""Contrato del compose final single-host (DO-R2; capa contrato/YAML)."""

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"
ENV_EXAMPLE_PATH = REPO_ROOT / ".env.example"

_CLAVES_SECRETAS = ("SECRET_KEY", "SMTP_PASS", "ADMIN_PASSWORD", "POSTGRES_PASSWORD")
_PATRON_CLAVE_VALOR = re.compile(
    r"(?i)\b(" + "|".join(_CLAVES_SECRETAS) + r")\s*[=:]\s*(\S+)"
)
_MARCADORES_FICTICIOS = ("changeme", "ejemplo", "ficticio", "example", "local", "${")


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def compose_texto() -> str:
    return COMPOSE_PATH.read_text(encoding="utf-8")


def _env_example() -> dict[str, str]:
    valores: dict[str, str] = {}
    for linea in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines():
        limpia = linea.strip()
        if not limpia or limpia.startswith("#") or "=" not in limpia:
            continue
        clave, _, valor = limpia.partition("=")
        valores[clave.strip()] = valor.strip()
    return valores


def test_compose_solo_web_y_db_activos(compose):
    """# AC DO-R2 FELIZ / ERROR — exactamente `web` y `db`, sin worker/redis."""
    assert set(compose["services"]) == {"web", "db"}


def test_compose_restart_unless_stopped_y_volumen_pgdata(compose):
    """# AC DO-R2 FELIZ — reinicio automático y datos en volumen nombrado."""
    for servicio in ("web", "db"):
        assert compose["services"][servicio]["restart"] == "unless-stopped"

    assert "pgdata" in compose["volumes"]
    montajes_db = compose["services"]["db"]["volumes"]
    assert any(str(montaje).startswith("pgdata:") for montaje in montajes_db)


def test_compose_db_sin_puertos_publicados(compose):
    """# AC DO-R2 BORDE — la DB no se expone fuera de la red interna."""
    assert "ports" not in compose["services"]["db"]

    url = _env_example()["DATABASE_URL"]
    assert "@db:5432/" in url
    assert set(compose["services"]["web"]["networks"]) == {"turnos-internal"}
    assert set(compose["services"]["db"]["networks"]) == {"turnos-internal"}


def test_compose_publica_solo_puerto_web(compose):
    """# AC DO-R2 FELIZ — único puerto publicado, parametrizable."""
    puertos_web = compose["services"]["web"]["ports"]

    assert len(puertos_web) == 1
    assert puertos_web[0] == "${WEB_PORT:-8000}:8000"


def test_compose_web_depends_on_db_service_healthy(compose):
    """# AC DO-R2 ERROR — `web` no arranca antes de la DB sana."""
    depends = compose["services"]["web"]["depends_on"]

    assert depends["db"]["condition"] == "service_healthy"


def test_compose_healthchecks_web_y_db(compose):
    """# AC DO-R2 ERROR — healthchecks reales en ambos servicios."""
    web_hc = " ".join(compose["services"]["web"]["healthcheck"]["test"])
    db_hc = " ".join(compose["services"]["db"]["healthcheck"]["test"])

    assert "/api/health" in web_hc
    assert "pg_isready" in db_hc


def test_compose_worker_comentado_cita_modulo_real(compose, compose_texto):
    """# AC DO-R2 ERROR — worker en-proceso, comentado con módulo real."""
    assert set(compose["services"]) == {"web", "db"}
    assert "app.modules.notificaciones.scheduler" in compose_texto
    assert "app.worker.scheduler" not in compose_texto

    lineas = [
        linea
        for linea in compose_texto.splitlines()
        if "app.modules.notificaciones.scheduler" in linea
    ]
    assert lineas
    assert all(linea.lstrip().startswith("#") for linea in lineas)


def test_compose_redis_comentado_y_redis_url_documentada_sin_servicio(
    compose, compose_texto
):
    """# AC DO-R2 ERROR / regla dura 6 — Redis solo documentado (PB-03)."""
    assert "redis" not in compose["services"]
    assert any(
        linea.lstrip().startswith("#") and "REDIS_URL" in linea
        for linea in compose_texto.splitlines()
    )


def test_compose_no_contiene_secretos_literales(compose, compose_texto):
    """# AC SC-R1 / DO-R2 — credenciales solo por env, nunca literales."""
    for linea in compose_texto.splitlines():
        if linea.lstrip().startswith("#"):
            continue
        for match in _PATRON_CLAVE_VALOR.finditer(linea):
            valor = match.group(2).lower()
            assert any(marca in valor for marca in _MARCADORES_FICTICIOS), (
                f"credencial literal en compose: {match.group(1)}"
            )

    # Credenciales solo por env: `.env` y, si existe, `.env.docker` (overrides
    # de docker, gitignored). Nunca valores literales en el compose.
    env_files = compose["services"]["web"]["env_file"]
    assert env_files[0] == {"path": ".env", "required": True}
    assert all(entrada["path"] in {".env", ".env.docker"} for entrada in env_files)
    assert all(isinstance(entrada.get("required"), bool) for entrada in env_files)


def test_compose_db_toma_password_de_env_file(compose):
    """# AC SC-R1 / DO-R2 BORDE — la password de `db` no está literal ni con
    fallback por defecto en el compose: llega por `env_file` (`.env` +
    `.env.docker`), la misma que usa `DATABASE_URL`.
    """
    db = compose["services"]["db"]

    assert "POSTGRES_PASSWORD" not in (db.get("environment") or {})
    rutas = {entrada["path"] for entrada in db["env_file"]}
    assert rutas == {".env", ".env.docker"}
