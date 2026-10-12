"""Cableado DB + Alembic (capa: wiring/integration, sin conectar).

Verifica que el engine se construye con `DATABASE_URL` dummy (sin abrir
conexión), que `get_db` es importable y cierra la sesión, y que
`alembic/env.py` importa `Base` como `target_metadata`.
"""

import sqlalchemy
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import engine, get_db


def test_engine_se_construye_con_database_url_dummy(monkeypatch):
    """El engine usa la URL de Settings sin conectar (triangulación: 2 URLs)."""
    from app.db import session as session_module

    for dummy_url in (
        "postgresql+psycopg://user:pass@db:5432/turnos",
        "postgresql+psycopg://otro:pass@db:5433/otra",
    ):
        monkeypatch.setenv("DATABASE_URL", dummy_url)
        rebuilt = session_module.build_engine()

        assert rebuilt.url.render_as_string(hide_password=False) == dummy_url
        rebuilt.dispose()


def test_engine_pool_chico_para_single_instance():
    """D-3 — pool_size=5 (disciplina de conexión, PG16 single-instance)."""
    assert engine.pool.size() == 5


def test_get_db_cierra_la_sesion(monkeypatch):
    """`get_db` hace yield y cierra (try/finally) aunque el request falle."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@db:5432/turnos")
    from app.db import session as session_module

    rebuilt = session_module.build_engine()
    factory = session_module.build_factory(rebuilt)
    monkeypatch.setattr(session_module, "SessionLocal", factory)

    gen = get_db()
    db = next(gen)
    assert isinstance(db, Session)
    gen.close()
    rebuilt.dispose()


def test_alembic_env_cablea_base_y_url_de_settings():
    """D-4 — `env.py` importa `Base`, fija `target_metadata` y URL de Settings."""
    import ast
    from pathlib import Path

    source = (Path(__file__).resolve().parent.parent / "alembic" / "env.py").read_text()
    tree = ast.parse(source)

    imports_base = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "app.db.base"
        and any(alias.name == "Base" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert imports_base

    assert "target_metadata = Base.metadata" in source
    assert 'set_main_option("sqlalchemy.url"' in source
    assert "get_settings().DATABASE_URL" in source


def test_alembic_offline_corre_sin_conectar_db():
    """D-4 — `upgrade head --sql` ejecuta `env.py` real sin conexión (exit 0)."""
    import subprocess
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent.parent
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
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert proc.returncode == 0, proc.stderr


def test_base_no_declara_tablas_dominio():
    """D-1 — `app/db/base.py` no declara tablas: el dominio vive en `app.models`.

    Reemplaza al assert C-01 `Base.metadata` vacio (su docstring preveia que
    C-02 lo llena): con `app.models` importado en la sesion, metadata ya no
    esta vacio; lo invariante es que `base.py` solo define `Base`.
    """
    import ast
    from pathlib import Path

    base_py = Path(__file__).resolve().parent.parent / "app" / "db" / "base.py"
    tree = ast.parse(base_py.read_text())

    clases = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    assert clases == ["Base"]
    assert issubclass(Base, sqlalchemy.orm.DeclarativeBase)
