"""Contrato `.env.example` ↔ `Settings` (capa: static/contract).

# AC service-config/S1 — completitud contra las 13 vars KB-08.
# AC service-config/S2 — sin secretos reales en el repo.
"""

from pathlib import Path

import pytest

from app.core.config import Settings, get_settings

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

REQUIRED_KEYS = [
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
    "CANCEL_HOURS_MIN",
    "SLOT_DEFAULT_MIN",
    "FRONTEND_URL",
]


def _parse_env_example() -> dict[str, str]:
    """Parsea `.env.example` sin ejecutar nada (KEY=valor, respeta `#`)."""
    values: dict[str, str] = {}
    commented: set[str] = set()
    for line in (REPO_ROOT / ".env.example").read_text().splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            if "=" in stripped:
                key = stripped.lstrip("#").strip().split("=", 1)[0].strip()
                commented.add(key)
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    values["_commented"] = commented  # type: ignore[assignment]
    return values


def test_env_example_cubre_las_13_vars_kb08():
    """# AC service-config/S1 — toda var requerida tiene placeholder no vacío."""
    parsed = _parse_env_example()

    for key in REQUIRED_KEYS:
        assert key in parsed, f"{key} falta en .env.example"
        assert parsed[key], f"{key} sin valor placeholder en .env.example"


def test_env_example_coincide_con_campos_de_settings():
    """# AC service-config/S1 — `.env.example` y `Settings` no divergen (D-2)."""
    parsed = _parse_env_example()
    commented = parsed.pop("_commented")
    settings_fields = set(Settings.model_fields)

    assert set(REQUIRED_KEYS) <= set(parsed)
    assert set(REQUIRED_KEYS) <= settings_fields
    assert "REDIS_URL" in commented  # opcional solo comentada (PB-03)
    assert "REDIS_URL" not in parsed


def test_env_example_sin_secretos_reales():
    """# AC service-config/S2 — placeholders ficticios, nada parecido a real."""
    text = (REPO_ROOT / ".env.example").read_text().lower()

    assert "cattaneo.com" not in text
    assert "gmail" not in text
    for key in ("SECRET_KEY", "ADMIN_PASSWORD", "SMTP_PASS"):
        line = next(
            ln for ln in text.splitlines() if ln.strip().startswith(key.lower())
        )
        value = line.split("=", 1)[1]
        assert len(value) < 64 or "changeme" in value or "example" in value


def test_env_example_incluye_env_vars_worker_y_placeholders_ficticios():
    """# AC SC-R1 FELIZ — vars operativas, defaults y placeholders ficticios."""
    parsed = _parse_env_example()

    for key in (
        "ENV",
        "SMTP_TIMEOUT_S",
        "NOTIF_WORKER_ENABLED",
        "NOTIF_WORKER_INTERVAL_MIN",
        "NOTIF_WORKER_BATCH_SIZE",
        "CONSULTORIO_CONTACTO",
    ):
        assert key in parsed, f"{key} falta en .env.example"

    assert parsed["ENV"] in {"development", "staging", "prod"}
    assert parsed["TZ"] == "America/Argentina/Buenos_Aires"
    assert parsed["CANCEL_HOURS_MIN"] == "3"
    assert parsed["SLOT_DEFAULT_MIN"] == "30"
    assert "@db:5432" in parsed["DATABASE_URL"]

    for key in ("SECRET_KEY", "ADMIN_PASSWORD", "SMTP_PASS"):
        valor = parsed[key].lower()
        assert any(
            marca in valor for marca in ("changeme", "ejemplo", "ficticio", "example")
        ), f"{key} no parece un placeholder ficticio"

    texto = (REPO_ROOT / ".env.example").read_text()
    assert "PROVISORIO" in texto
    assert "MIGRABLE" in texto


def test_env_example_secret_key_placeholder_reconocible_como_no_productivo(
    monkeypatch, tmp_path
):
    """# AC SC-R1 BORDE — el placeholder de SECRET_KEY lo rechaza prod."""
    parsed = _parse_env_example()
    parsed.pop("_commented")
    secret_key = parsed["SECRET_KEY"].lower()

    assert "changeme" in secret_key or "-ejemplo" in secret_key

    monkeypatch.chdir(tmp_path)
    for key, value in parsed.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("ENV", "prod")

    with pytest.raises(RuntimeError) as exc_info:
        get_settings()

    mensaje = str(exc_info.value)
    assert "SECRET_KEY" in mensaje
    assert parsed["SECRET_KEY"] not in mensaje


def test_env_real_ignorado_por_git():
    """# AC service-config/S2 — `.env` real nunca se versiona.

    Un `.env` local ES esperado en dev (DATABASE_URL real para PG); el
    contrato es que git lo ignore, no que el archivo este ausente.
    """
    import subprocess

    gitignore = (REPO_ROOT / ".gitignore").read_text().splitlines()

    assert ".env" in gitignore
    if (REPO_ROOT / ".env").exists():
        proc = subprocess.run(
            ["git", "check-ignore", "-q", ".env"],
            cwd=REPO_ROOT,
            capture_output=True,
            timeout=30,
        )
        assert proc.returncode == 0, ".env existe pero git no lo ignora"
