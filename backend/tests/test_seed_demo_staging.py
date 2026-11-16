"""`seed_demo.py` fail-closed: sólo `ENV=staging` escribe (DO-R6; capa proceso).

Datos ficticios (regla dura 12). Las corridas de staging escriben sobre
`turnos_test` y se limpian en el mismo test.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "backend" / "scripts" / "seed_demo.py"


def _run_seed(env_extra: dict[str, str], timeout: int = 180):
    env = dict(os.environ)
    env.pop("ENV", None)
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def _conteos(engine) -> tuple[int, int]:
    session = Session(bind=engine)
    try:
        profesionales = session.execute(
            sqlalchemy.text(
                "SELECT count(*) FROM profesional WHERE nombre LIKE 'Demo Seed%'"
            )
        ).scalar()
        turnos = session.execute(
            sqlalchemy.text(
                "SELECT count(*) FROM turno t "
                "JOIN profesional p ON p.id = t.profesional_id "
                "WHERE p.nombre LIKE 'Demo Seed%'"
            )
        ).scalar()
        return int(profesionales), int(turnos)
    finally:
        session.close()


def _limpiar_demo(engine) -> None:
    session = Session(bind=engine)
    try:
        session.execute(
            sqlalchemy.text(
                "DELETE FROM turno WHERE profesional_id IN "
                "(SELECT id FROM profesional WHERE nombre LIKE 'Demo Seed%')"
            )
        )
        session.execute(
            sqlalchemy.text("DELETE FROM paciente WHERE nombre LIKE 'Demo Seed%'")
        )
        session.execute(
            sqlalchemy.text("DELETE FROM profesional WHERE nombre LIKE 'Demo Seed%'")
        )
        session.commit()
    finally:
        session.close()


def test_seed_demo_env_ausente_exit_2_sin_escribir(test_engine):
    """# AC DO-R6 BORDE — sin `ENV` falla cerrado y no escribe."""
    from tests.conftest import test_db_url

    antes = _conteos(test_engine)
    result = _run_seed({"DATABASE_URL": test_db_url()})

    assert result.returncode == 2
    assert "staging" in (result.stdout + result.stderr).lower()
    assert _conteos(test_engine) == antes


@pytest.mark.parametrize("entorno", ["production", "PROD", "demo"])
def test_seed_demo_env_desconocido_exit_2(test_engine, entorno):
    """# AC DO-R6 BORDE — cualquier valor distinto de `staging` falla cerrado."""
    from tests.conftest import test_db_url

    antes = _conteos(test_engine)
    result = _run_seed({"ENV": entorno, "DATABASE_URL": test_db_url()})

    assert result.returncode == 2
    assert _conteos(test_engine) == antes


def test_seed_demo_env_prod_exit_2_sin_escribir(test_engine):
    """# AC DO-R6 ERROR — en producción rechaza sin insertar ni modificar."""
    from tests.conftest import test_db_url

    antes = _conteos(test_engine)
    result = _run_seed({"ENV": "prod", "DATABASE_URL": test_db_url()})

    assert result.returncode == 2
    assert (result.stdout + result.stderr).strip()
    assert _conteos(test_engine) == antes


def test_seed_demo_env_staging_exit_0_datos_ficticios(test_engine):
    """# AC DO-R6 FELIZ — en staging siembra 2 profesionales y 20 turnos."""
    from tests.conftest import test_db_url

    _limpiar_demo(test_engine)
    try:
        result = _run_seed({"ENV": "staging", "DATABASE_URL": test_db_url()})

        assert result.returncode == 0, result.stderr
        assert _conteos(test_engine) == (2, 20)

        session = Session(bind=test_engine)
        try:
            contactos = session.execute(
                sqlalchemy.text(
                    "SELECT email, dni, telefono FROM paciente "
                    "WHERE nombre LIKE 'Demo Seed%'"
                )
            ).all()
        finally:
            session.close()
        assert contactos
        for contacto in contactos:
            assert contacto.email.endswith("@ficticio.test"), contacto.email
            assert contacto.dni.startswith("33999"), contacto.dni
            assert "gmail" not in (contacto.email + contacto.telefono).lower()
    finally:
        _limpiar_demo(test_engine)


def test_seed_demo_guarda_corre_antes_de_conectar():
    """# AC DO-R6 BORDE — con DB inalcanzable y ENV inválido igual devuelve 2."""
    result = _run_seed(
        {
            "ENV": "prod",
            "DATABASE_URL": (
                "postgresql+psycopg://turnos:clave-ficticia@127.0.0.1:1/turnos"
            ),
        },
        timeout=60,
    )

    assert result.returncode == 2
    assert "staging" in (result.stdout + result.stderr).lower()
