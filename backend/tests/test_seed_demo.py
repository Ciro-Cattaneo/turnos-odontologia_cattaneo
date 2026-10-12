"""`seed_demo.py` staging-only con datos ficticios (capa: db/staging).

# AC core-models/seed_demo-ficticio (2 profesionales + 20 turnos ficticios,
# ningún dato real, NUNCA en producción).
"""

import subprocess
import sys
from pathlib import Path

import sqlalchemy
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "backend" / "scripts" / "seed_demo.py"


def test_seed_demo_crea_dos_profesionales_y_veinte_turnos(db_session):
    """En staging: 2+20 ficticios, contados por marcador propio `Demo Seed`."""
    from app.db.seed import seed_demo

    seed_demo(db_session)
    n_profs = db_session.execute(
        sqlalchemy.text(
            "SELECT count(*) FROM profesional WHERE nombre LIKE 'Demo Seed%'"
        )
    ).scalar()
    assert n_profs == 2
    n_turnos = db_session.execute(
        sqlalchemy.text(
            "SELECT count(*) FROM turno t "
            "JOIN profesional p ON p.id = t.profesional_id "
            "WHERE p.nombre LIKE 'Demo Seed%'"
        )
    ).scalar()
    assert n_turnos == 20
    # Ningún dato real: emails del dominio ficticio y DNI del rango demo.
    contactos = db_session.execute(
        sqlalchemy.text(
            "SELECT email, dni, telefono FROM paciente WHERE nombre LIKE 'Demo Seed%'"
        )
    ).all()
    assert len(contactos) > 0
    for c in contactos:
        assert c.email.endswith("@ficticio.test"), c.email
        assert c.dni.startswith("33999"), c.dni
        assert "gmail" not in (c.email + c.telefono).lower()


def test_seed_demo_rehusa_en_produccion():
    """Con `ENV=prod` el script rehúsa sin tocar la DB (exit != 0)."""
    import os

    assert SCRIPT.exists(), "falta backend/scripts/seed_demo.py"
    env = dict(os.environ, ENV="prod")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert proc.returncode != 0
    assert "prod" in (proc.stdout + proc.stderr).lower()


def test_seed_demo_no_corre_sin_rehusar_fuera_de_prod(test_engine):
    """Fuera de prod el CLI corre (smoke contra `turnos_test`, con limpieza)."""
    import os

    from tests.conftest import test_db_url

    env = dict(os.environ, ENV="staging", DATABASE_URL=test_db_url())
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    sesion = Session(bind=test_engine)
    try:
        n = sesion.execute(
            sqlalchemy.text(
                "SELECT count(*) FROM profesional WHERE nombre LIKE 'Demo Seed%'"
            )
        ).scalar()
        assert n >= 2
        # Limpieza: demo no escribe auditoría (C-07 la genera), se borra todo.
        sesion.execute(
            sqlalchemy.text(
                "DELETE FROM turno WHERE profesional_id IN "
                "(SELECT id FROM profesional WHERE nombre LIKE 'Demo Seed%')"
            )
        )
        sesion.execute(
            sqlalchemy.text("DELETE FROM paciente WHERE nombre LIKE 'Demo Seed%'")
        )
        sesion.execute(
            sqlalchemy.text("DELETE FROM profesional WHERE nombre LIKE 'Demo Seed%'")
        )
        sesion.commit()
    finally:
        sesion.close()
