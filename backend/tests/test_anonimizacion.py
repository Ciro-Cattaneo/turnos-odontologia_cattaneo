"""Anonimización Ley 25.326: script admin + doc, sin UI (capa: db).

# AC paciente-privacidad/Anonimizacion-conserva-estadisticas (datos NULL,
# turnos intactos como estadística).
# AC paciente-privacidad/Anonimizacion-no-toca-otros (B intacto, FK sanas).
# AC paciente-privacidad/Sin-UI-v1 (ninguna ruta UI anonimiza).
"""

import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import sqlalchemy
from sqlalchemy.orm import Session

from tests.conftest import mk_paciente, mk_profesional, mk_turno

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "backend" / "scripts" / "anonimizar_paciente.py"

BASE = datetime(2026, 10, 25, 13, 0, tzinfo=UTC)


def _con_turnos(db_session, n=2):
    prof = mk_profesional(db_session)
    pac = mk_paciente(db_session)
    for k in range(n):
        mk_turno(
            db_session,
            prof.id,
            pac.id,
            inicio=BASE + timedelta(hours=k),
            fin=BASE + timedelta(hours=k, minutes=30),
        )
    return prof, pac


def test_anonimizar_conserva_turnos_como_estadistica(db_session):
    """# AC paciente-privacidad/Anonimizacion-conserva-estadisticas."""
    from app.db.anonimizacion import anonimizar_paciente

    _, pac = _con_turnos(db_session)
    pac_id = pac.id
    anonimizar_paciente(db_session, pac_id)
    db_session.flush()

    fila = db_session.execute(
        sqlalchemy.text(
            "SELECT nombre, dni, telefono, email, obra_social "
            "FROM paciente WHERE id = :id"
        ),
        {"id": str(pac_id)},
    ).one()
    assert fila.nombre == f"Eliminado #{pac_id}"
    assert fila.dni is None
    assert fila.telefono is None
    assert fila.email is None
    assert fila.obra_social == "(eliminado)"
    n_turnos = db_session.execute(
        sqlalchemy.text("SELECT count(*) FROM turno WHERE paciente_id = :id"),
        {"id": str(pac_id)},
    ).scalar()
    assert n_turnos == 2
    n_audit = db_session.execute(
        sqlalchemy.text(
            "SELECT count(*) FROM auditoria_turno WHERE accion = 'anonimizar' "
            "AND turno_id IN (SELECT id FROM turno WHERE paciente_id = :id)"
        ),
        {"id": str(pac_id)},
    ).scalar()
    assert n_audit == 2


def test_anonimizar_no_toca_otro_paciente_ni_fk(db_session):
    """# AC paciente-privacidad/Anonimizacion-no-toca-otros: B intacto."""
    from app.db.anonimizacion import anonimizar_paciente

    _, pac_a = _con_turnos(db_session, n=1)
    _, pac_b = _con_turnos(db_session, n=1)
    datos_b = (pac_b.nombre, pac_b.dni, pac_b.telefono, pac_b.email)
    anonimizar_paciente(db_session, pac_a.id)
    db_session.flush()

    fila_b = db_session.execute(
        sqlalchemy.text(
            "SELECT nombre, dni, telefono, email FROM paciente WHERE id = :id"
        ),
        {"id": str(pac_b.id)},
    ).one()
    assert tuple(fila_b) == datos_b
    # Ninguna FK huérfana: todo turno y auditoría resuelven a filas vivas.
    huerfanos = db_session.execute(
        sqlalchemy.text(
            "SELECT count(*) FROM turno t "
            "LEFT JOIN paciente p ON p.id = t.paciente_id "
            "WHERE p.id IS NULL"
        )
    ).scalar()
    assert huerfanos == 0


def test_anonimizar_paciente_inexistente_falla(db_session):
    """El procedimiento con id desconocido falla sin tocar nada."""
    from app.db.anonimizacion import anonimizar_paciente

    with pytest.raises(ValueError, match="no existe"):
        anonimizar_paciente(db_session, uuid.uuid4())


def test_script_cli_anonimiza_sobre_pg_real(test_engine):
    """El script `anonimizar_paciente.py --paciente-id` corre de verdad.

    Nota D-8: las filas de auditoría son permanentes (el trigger impide su
    DELETE y referencian a los turnos), así que este test DEJA sus filas
    commiteadas en `turnos_test`; los demás tests aíslan por transacción o
    filtran por fixture propio y no dependen de tablas vacías.
    """
    from tests.conftest import test_db_url

    assert SCRIPT.exists(), "falta backend/scripts/anonimizar_paciente.py"
    setup = Session(bind=test_engine)
    _, pac = _con_turnos(setup)
    setup.commit()
    pac_id = pac.id
    setup.close()
    import os

    env = dict(os.environ, DATABASE_URL=test_db_url())
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--paciente-id", str(pac_id)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Eliminado" in proc.stdout
    sesion = Session(bind=test_engine)
    try:
        nombre = sesion.execute(
            sqlalchemy.text("SELECT nombre FROM paciente WHERE id = :id"),
            {"id": str(pac_id)},
        ).scalar()
        assert nombre == f"Eliminado #{pac_id}"
    finally:
        sesion.close()


def test_sin_ui_v1_para_anonimizar():
    """# AC paciente-privacidad/Sin-UI-v1: ningún router/UI nombra anonimizar."""
    modulos = REPO_ROOT / "backend" / "app" / "modules"
    hits = [
        p
        for p in modulos.rglob("*.py")
        if "anonimiz" in p.read_text(encoding="utf-8").lower()
    ]
    assert hits == [], f"la UI/API no debe exponer anonimización: {hits}"
    frontend_src = REPO_ROOT / "frontend" / "src"
    if frontend_src.exists():
        hits_fe = [
            p
            for p in frontend_src.rglob("*")
            if p.is_file()
            and "anonimiz" in p.read_text(encoding="utf-8", errors="ignore").lower()
        ]
        assert hits_fe == []
    assert (REPO_ROOT / "docs" / "anonimizacion-ley-25326.md").exists()
