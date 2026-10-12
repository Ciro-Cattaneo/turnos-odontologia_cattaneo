"""Migración `001_core_models` (capas: migration/offline + db).

# AC core-models/Migracion-upgrade-downgrade (upgrade crea 8 tablas + EXCLUDE,
# downgrade las elimina, re-upgrade idempotente).
# AC core-models/Solape-rechazado (EXCLUDE textual D-4 exacto en el SQL).
"""

import ast
import subprocess
import sys
from pathlib import Path

import sqlalchemy

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VERSIONS = REPO_ROOT / "backend" / "alembic" / "versions" / "001_core_models.py"

EXPECTED_TABLES = frozenset(
    {
        "paciente",
        "profesional",
        "disponibilidad",
        "bloqueo",
        "turno",
        "notificacion",
        "usuario_staff",
        "auditoria_turno",
    }
)


def _alembic_sql_offline() -> str:
    """`upgrade head --sql` offline: no conecta, solo renderiza DDL."""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "backend/alembic.ini",
            "upgrade",
            "head",
            "--sql",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def test_env_py_importa_app_models():
    """D-1/D-6 — `env.py` registra `app.models` para el autogenerate."""
    source = (REPO_ROOT / "backend" / "alembic" / "env.py").read_text()
    tree = ast.parse(source)
    importa = any(
        isinstance(node, (ast.Import, ast.ImportFrom))
        and any(
            a.name == "app.models" or a.name.startswith("app.models.")
            for a in node.names
        )
        for node in ast.walk(tree)
    )
    assert importa, "env.py debe importar app.models (una línea, D-1)"


def test_revision_001_existe_y_es_cabeza_unica():
    """D-6 — una sola head y el archivo se llama `001_core_models.py`."""
    assert VERSIONS.exists(), "falta backend/alembic/versions/001_core_models.py"
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "heads"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    heads = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    assert len(heads) == 1, f"se esperaba una head, hay: {heads}"


def test_sql_offline_contiene_exclude_d4_exacto():
    """# AC core-models/Solape-rechazado — EXCLUDE gist textual D-4 exacto."""
    sql = _alembic_sql_offline()
    assert "EXCLUDE USING gist" in sql
    assert "tstzrange(inicio, fin" in sql
    assert "WHERE (estado IN ('reservado', 'confirmado'))" in sql
    assert "no_solape_prof" in sql


def test_sql_offline_contiene_extensiones_y_tipos():
    """D-4/D-5 — `btree_gist`+`citext` y enums nativos en el DDL."""
    sql = _alembic_sql_offline()
    assert "btree_gist" in sql
    assert "citext" in sql
    for enum in (
        "turno_estado",
        "turno_origen",
        "canal",
        "notif_tipo",
        "notif_estado",
        "staff_rol",
    ):
        assert enum in sql, f"falta el tipo enum {enum}"


def test_sql_offline_contiene_trigger_append_only():
    """D-8 — trigger `auditoria_no_update_delete` en el DDL."""
    sql = _alembic_sql_offline()
    assert "auditoria_no_update_delete" in sql


def test_sql_offline_contiene_indices_parciales():
    """D-5 — parciales de estado/activo en el DDL."""
    sql = _alembic_sql_offline()
    assert "ix_turno_estado_inicio" in sql
    assert "ix_notif_estado" in sql


def test_upgrade_head_crea_ocho_tablas_y_exclude(pg_test_url, alembic_on_testdb):
    """# AC core-models/Migracion-upgrade-downgrade — upgrade crea todo."""
    alembic_on_testdb("upgrade", "head")
    engine = sqlalchemy.create_engine(pg_test_url)
    try:
        with engine.connect() as conn:
            tablas = {
                row[0]
                for row in conn.execute(
                    sqlalchemy.text(
                        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                    )
                )
            }
            assert EXPECTED_TABLES <= tablas
            n_exclude = conn.execute(
                sqlalchemy.text(
                    "SELECT count(*) FROM pg_constraint "
                    "WHERE conname = 'no_solape_prof' AND contype = 'x'"
                )
            ).scalar()
            assert n_exclude == 1, "falta el EXCLUDE no_solape_prof"
    finally:
        engine.dispose()


def test_downgrade_elimina_y_reupgrade_es_idempotente(pg_test_url, alembic_on_testdb):
    """# AC core-models/Migracion-upgrade-downgrade — baja y vuelve a subir."""
    alembic_on_testdb("upgrade", "head")
    alembic_on_testdb("downgrade", "-1")
    engine = sqlalchemy.create_engine(pg_test_url)
    try:
        with engine.connect() as conn:
            tablas = {
                row[0]
                for row in conn.execute(
                    sqlalchemy.text(
                        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                    )
                )
            }
            assert EXPECTED_TABLES.isdisjoint(tablas), f"quedaron: {tablas}"
        alembic_on_testdb("upgrade", "head")
        alembic_on_testdb("upgrade", "head")
        with engine.connect() as conn:
            tablas = {
                row[0]
                for row in conn.execute(
                    sqlalchemy.text(
                        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                    )
                )
            }
            assert EXPECTED_TABLES <= tablas
    finally:
        engine.dispose()
