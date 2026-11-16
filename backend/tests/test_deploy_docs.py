"""Contrato de la guía de deploy (DO-R4/DO-R5; capa contrato/documento).

Los tests leen el archivo versionado real y verifican contenido observable:
secciones, criterios de rollback, declaración Ley 25.326, marcas
PROVISORIO/MIGRABLE y ausencia de datos reales de pacientes (regla dura 12).
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOC = REPO_ROOT / "docs" / "deploy-single-host.md"

_DOMINIOS_FICTICIOS = ("@ficticio.test", "@ejemplo.test", ".test", ".example")
_PATRON_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PATRON_DNI = re.compile(r"\bDNI[:\s]+([0-9][0-9.]*)", re.IGNORECASE)


def _texto() -> str:
    assert DOC.exists(), f"falta {DOC}"
    return DOC.read_text(encoding="utf-8")


def test_docs_deploy_cubre_compose_paas_tls_migraciones_rollback():
    """# AC DO-R4 FELIZ — Compose, PaaS single instance, TLS, migración, rollback."""
    texto = _texto().lower()

    for token in (
        "docker compose",
        "railway",
        "render",
        "fly",
        "tls",
        "alembic upgrade head",
        "rollback",
        "single instance",
    ):
        assert token in texto, f"falta '{token}' en la guía"


def test_docs_deploy_tls_fuera_de_la_app_y_proxy_headers():
    """# AC DO-R4 BORDE — TLS en el borde y app HTTP con headers de proxy."""
    texto = _texto().lower()

    assert "tls lo termina" in texto
    assert "la app escucha http" in texto
    assert "forwarded_allow_ips" in texto
    assert "proxy" in texto


def test_docs_deploy_rollback_criterio_observable():
    """# AC DO-R4 ERROR — rollback con criterio `/api/health` + `alembic current`."""
    texto = _texto().lower()

    assert "rollback" in texto
    assert "/api/health" in texto
    assert "alembic current" in texto
    assert "imagen" in texto
    assert "revisión" in texto or "revision" in texto


def test_docs_privacidad_finalidad_conservacion_no_cesion():
    """# AC DO-R5 FELIZ — declaración mínima Ley 25.326."""
    texto = _texto().lower()

    assert "ley 25.326" in texto
    assert "finalidad" in texto
    assert "conservación" in texto
    assert "no se ceden a terceros" in texto


def test_docs_provisorio_migrable_smtp_y_backups():
    """# AC DO-R5 BORDE — SMTP y backups marcados con su ruta de reemplazo."""
    texto = _texto().lower()

    marcas = texto.count("provisorio/migrable")
    assert marcas >= 2, f"esperaba SMTP y backups marcados, hay {marcas}"
    assert "proveedor transaccional" in texto
    assert "fuera del host" in texto or "storage externo" in texto


def test_docs_sin_datos_reales_de_pacientes():
    """# AC DO-R5 ERROR — sólo datos ficticios (regla dura 12)."""
    texto = _texto()
    emails = _PATRON_EMAIL.findall(texto)

    assert emails, "la guía debe traer ejemplos con datos ficticios"
    for email in emails:
        assert email.lower().endswith(_DOMINIOS_FICTICIOS), email
    assert "@ficticio.test" in texto.lower()
    for dominio_real in ("gmail.com", "hotmail.com", "outlook.com", "yahoo.com"):
        assert dominio_real not in texto.lower()

    dnis = _PATRON_DNI.findall(texto)
    assert dnis, "la guía debe traer un DNI sintético de ejemplo"
    for dni in dnis:
        assert dni.replace(".", "").startswith("33999"), dni


def test_docs_backup_cron_y_restore_documentados():
    """# AC DO-R3 FELIZ (operación) — cron diario y comando de restore."""
    texto = _texto()

    assert "17 3 * * *" in texto
    assert "backup_postgres.sh" in texto
    assert "restore_postgres.sh" in texto
    assert "7 días" in texto
