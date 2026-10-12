"""Modelos core registrados en `Base.metadata` (capa: unit, sin DB).

# AC core-models/Entidades-persisten (estructura: 8 tablas, PK UUID, timestamptz).
"""

import pytest
from sqlalchemy import DateTime, Uuid

import app.models  # noqa: F401  (el import registra las 8 tablas en metadata)
from app.db.base import Base

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


def test_ocho_tablas_registradas_en_metadata():
    """# AC core-models/Entidades-persisten: las 8 entidades viven en metadata."""
    assert frozenset(Base.metadata.tables) == EXPECTED_TABLES


@pytest.mark.parametrize("table_name", sorted(EXPECTED_TABLES))
def test_pk_es_uuid_unica_por_tabla(table_name):
    """# AC core-models/Entidades-persisten: PK simple tipo UUID en cada tabla."""
    table = Base.metadata.tables[table_name]
    pk_cols = list(table.primary_key.columns)
    assert len(pk_cols) == 1
    assert isinstance(pk_cols[0].type, Uuid)
    assert callable(pk_cols[0].default.arg)


@pytest.mark.parametrize("column", ["inicio", "fin"])
def test_turno_rango_es_timestamptz(column):
    """# AC core-models/Entidades-persisten: `inicio`/`fin` con zona horaria."""
    col = Base.metadata.tables["turno"].c[column]
    assert isinstance(col.type, DateTime)
    assert col.type.timezone is True
    assert col.nullable is False


@pytest.mark.parametrize("column", ["profesional_id", "paciente_id"])
def test_turno_fk_es_restrict(column):
    """PB-04/D-9: el DELETE con turnos falla tambien a nivel DB (RESTRICT)."""
    fks = Base.metadata.tables["turno"].foreign_keys
    fk = next(fk for fk in fks if fk.parent.name == column)
    assert fk.ondelete == "RESTRICT"


@pytest.mark.parametrize(
    ("table_name", "column", "constraint"),
    [
        ("turno", "token_cancelacion", "ux_turno_token"),
        ("paciente", "dni", "ux_paciente_dni"),
    ],
)
def test_unicos_declarados(table_name, column, constraint):
    """Lifecycle/privacidad: token y dni unicos con nombre de constraint estable.

    §2 lock (handoff §1 lo dejaba abierto): UNIQUE a nivel tabla con nombre
    explícito — una sola restricción por columna, sin duplicado auto-nombrado.
    """
    from sqlalchemy import UniqueConstraint

    table = Base.metadata.tables[table_name]
    sobre_columna = [
        c
        for c in table.constraints
        if isinstance(c, UniqueConstraint) and column in {col.name for col in c.columns}
    ]
    assert len(sobre_columna) == 1, f"UNIQUE duplicado/ausente sobre {column}"
    assert sobre_columna[0].name == constraint


def test_turno_token_no_nulo():
    """# AC turno-lifecycle/Token-duplicado-o-nulo: token obligatorio."""
    assert Base.metadata.tables["turno"].c.token_cancelacion.nullable is False


def test_created_at_con_server_default_utc():
    """Regla dura 10: `created_at` persiste en DB con default servidor."""
    for table_name in ("paciente", "turno", "auditoria_turno"):
        col = Base.metadata.tables[table_name].c.created_at
        assert isinstance(col.type, DateTime)
        assert col.type.timezone is True
        assert col.server_default is not None
