"""Fixtures compartidas: expone `backend/` en `sys.path` (imports `app.*`).

DB real (D-10): los tests de persistencia corren contra Postgres real en la
base `turnos_test` (derivada de `DATABASE_URL`, NUNCA la `turnos` de dev),
creada una vez por sesión con migraciones aplicadas; cada test recibe una
`db_session` con rollback (aislamiento por transacción).
"""

import itertools
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import sqlalchemy
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Env mínimo ficticio para que `app.main` importe en tests (datos ficticios,
# nunca credenciales reales — regla dura 12). Los tests de config usan
# `monkeypatch` para aislar/alterar estas vars por caso.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://user:pass@db:5432/turnos")
os.environ.setdefault("SECRET_KEY", "clave-ficticia-solo-tests-0123456789abcdef")
os.environ.setdefault("ADMIN_EMAIL", "admin-ficticio@cattaneo.test")
os.environ.setdefault("ADMIN_PASSWORD", "password-ficticia-solo-tests")
os.environ.setdefault("SMTP_HOST", "smtp.ficticio.test")
os.environ.setdefault("SMTP_PORT", "587")
os.environ.setdefault("SMTP_USER", "usuario-ficticio")
os.environ.setdefault("SMTP_PASS", "pass-ficticia-solo-tests")
os.environ.setdefault("SMTP_FROM", "turnos@ficticio.test")
os.environ.setdefault("TZ", "America/Argentina/Buenos_Aires")
os.environ.setdefault("FRONTEND_URL", "https://turnos.ficticio.test")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEST_DB_NAME = "turnos_test"

_counter = itertools.count(1)


def _real_database_url() -> str:
    """URL real desde el `.env` de repo-root.

    `os.environ["DATABASE_URL"]` es el dummy de este conftest (para que
    `app.main` importe sin PG) y `Settings` prioriza env sobre `.env`;
    por eso se lee el archivo directo, sin ejecutar nada.
    """
    env_file = REPO_ROOT / ".env"
    assert env_file.exists(), ".env ausente en repo-root (requisito 0.1)"
    for line in env_file.read_text().splitlines():
        if line.startswith("DATABASE_URL="):
            url = line.partition("=")[2].strip()
            assert url, "DATABASE_URL vacía en .env"
            return url
    raise RuntimeError("DATABASE_URL falta en .env (requisito 0.1)")


def test_db_url() -> str:
    """URL de la base de tests: misma conexión que `DATABASE_URL`, otro DB.

    OJO: `str(URL)` enmascara el password como `***`; para re-conectar hay
    que usar `render_as_string(hide_password=False)`.
    """
    from sqlalchemy.engine import make_url

    url = make_url(_real_database_url())
    return url.set(database=TEST_DB_NAME).render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def pg_test_url() -> str:
    """Crea `turnos_test` si falta y aplica `alembic upgrade head` una vez."""
    url = test_db_url()
    from sqlalchemy.engine import make_url

    maint = make_url(url).set(database="turnos").render_as_string(hide_password=False)
    engine = sqlalchemy.create_engine(maint, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            existe = conn.execute(
                sqlalchemy.text(
                    "SELECT count(*) FROM pg_database WHERE datname = 'turnos_test'"
                )
            ).scalar()
            if not existe:
                conn.execute(sqlalchemy.text("CREATE DATABASE turnos_test"))
    finally:
        engine.dispose()
    env = dict(os.environ, DATABASE_URL=url)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "backend/alembic.ini",
            "upgrade",
            "head",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    return url


@pytest.fixture(scope="session")
def test_engine(pg_test_url):
    """Engine compartido contra `turnos_test` (los tests aíslan por txn)."""
    engine = sqlalchemy.create_engine(pg_test_url, pool_size=5, max_overflow=5)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    """Sesión PG real con rollback: lo que el test commitea se descarta."""
    conn = test_engine.connect()
    txn = conn.begin()
    session = Session(bind=conn)
    yield session
    session.close()
    txn.rollback()
    conn.close()


@pytest.fixture
def alembic_on_testdb(pg_test_url):
    """Corre `alembic ...` contra `turnos_test` (para tests de migración)."""

    def run(*args: str) -> None:
        env = dict(os.environ, DATABASE_URL=pg_test_url)
        proc = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
        assert proc.returncode == 0, proc.stderr

    return run


# --- Factorías ficticias (regla dura 12: dominio `.test`, DNI sintéticos) ---


def mk_profesional(db_session, nombre="Odontologa Ficticia", **kw):
    """Profesional activo mínimo."""
    from app.models.profesional import Profesional

    n = next(_counter)
    prof = Profesional(nombre=f"{nombre} {n}", **kw)
    db_session.add(prof)
    db_session.flush()
    return prof


def mk_paciente(db_session, **kw):
    """Paciente mínimo con contacto ficticio único por test."""
    from app.models.paciente import Paciente

    n = next(_counter)
    pac = Paciente(
        nombre=f"Paciente Ficticio {n}",
        dni=f"309990{n:04d}",
        telefono=f"+549110000{n:04d}",
        email=f"paciente{n}@ficticio.test",
        obra_social="OS Ficticia",
        **kw,
    )
    db_session.add(pac)
    db_session.flush()
    return pac


def mk_turno(
    db_session,
    profesional_id,
    paciente_id,
    inicio=None,
    fin=None,
    estado=None,
    **kw,
):
    """Turno de 30 min; `duracion_min` consistente salvo override explícito."""
    import uuid as _uuid

    from app.models.turno import Turno, TurnoEstado, TurnoOrigen

    base = datetime(2026, 10, 20, 13, 0, tzinfo=UTC)
    inicio = inicio or base
    fin = fin or (base + timedelta(minutes=30))
    kw.setdefault("duracion_min", round((fin - inicio).total_seconds() / 60))
    kw.setdefault("origen", TurnoOrigen.online)
    kw.setdefault("token_cancelacion", _uuid.uuid4())
    turno = Turno(
        profesional_id=profesional_id,
        paciente_id=paciente_id,
        inicio=inicio,
        fin=fin,
        estado=estado or TurnoEstado.reservado,
        **kw,
    )
    db_session.add(turno)
    db_session.flush()
    return turno


def unique_token() -> uuid.UUID:
    """Token de cancelación nuevo (los tests nunca reutilizan tokens)."""
    return uuid.uuid4()


# Env mínimo ficticio para que `app.main` importe en tests (datos ficticios,
# nunca credenciales reales — regla dura 12). Los tests de config usan
# `monkeypatch` para aislar/alterar estas vars por caso.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://user:pass@db:5432/turnos")
os.environ.setdefault("SECRET_KEY", "clave-ficticia-solo-tests-0123456789abcdef")
os.environ.setdefault("ADMIN_EMAIL", "admin-ficticio@cattaneo.test")
os.environ.setdefault("ADMIN_PASSWORD", "password-ficticia-solo-tests")
os.environ.setdefault("SMTP_HOST", "smtp.ficticio.test")
os.environ.setdefault("SMTP_PORT", "587")
os.environ.setdefault("SMTP_USER", "usuario-ficticio")
os.environ.setdefault("SMTP_PASS", "pass-ficticia-solo-tests")
os.environ.setdefault("SMTP_FROM", "turnos@ficticio.test")
os.environ.setdefault("TZ", "America/Argentina/Buenos_Aires")
os.environ.setdefault("FRONTEND_URL", "https://turnos.ficticio.test")
