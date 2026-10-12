"""Schemas estrictos agenda (capa: schemas/unit, sin DB).

# AC agenda-disponibilidad/400-por-campo (`extra='forbid'`, tope 31 días,
# rango no invertido, vista cerrada). El mapeo HTTP 400 se verifica en los
# tests de endpoints 2.2/2.3/2.4/3.4 (handler ValidationError→400 en main).
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError


def test_query_extra_rechazado_400():
    """# AC 400-por-campo: query con campo desconocido → error en ese campo."""
    from app.modules.agenda.schemas import AgendaQuery

    with pytest.raises(ValidationError) as exc:
        AgendaQuery(vista="dia", fecha="2026-10-19", inventado="x")  # type: ignore[call-arg]
    assert "inventado" in str(exc.value)


def test_rango_invertido_400():
    """# AC 400-por-campo: `desde > hasta` y `hora_desde >= hora_hasta` → 400."""
    from app.modules.agenda.schemas import DisponibilidadCreate, DisponibilidadQuery

    pid = uuid4()
    with pytest.raises(ValidationError) as exc:
        DisponibilidadQuery(
            profesional_id=pid,
            desde=datetime(2026, 10, 20, 9, tzinfo=UTC),
            hasta=datetime(2026, 10, 19, 9, tzinfo=UTC),
        )
    assert "desde" in str(exc.value)
    with pytest.raises(ValidationError) as exc2:
        DisponibilidadCreate(
            profesional_id=pid,
            dia_semana=1,
            hora_desde="12:00",  # type: ignore[arg-type]
            hora_hasta="09:00",  # type: ignore[arg-type]
        )
    assert "hora_desde" in str(exc2.value)


def test_vista_invalida_400():
    """# AC 400-por-campo: `vista=mes` y `fecha` malformada → error por campo."""
    from app.modules.agenda.schemas import AgendaQuery

    with pytest.raises(ValidationError) as exc:
        AgendaQuery(vista="mes", fecha="2026-10-19")  # type: ignore[arg-type]
    assert "vista" in str(exc.value)
    with pytest.raises(ValidationError) as exc2:
        AgendaQuery(vista="dia", fecha="19/10/2026")
    assert "fecha" in str(exc2.value)


def test_rango_mayor_31_dias_400():
    """# AC tope-31-días: rango amplio → 400 sin computar."""
    from app.modules.agenda.schemas import DisponibilidadQuery

    with pytest.raises(ValidationError) as exc:
        DisponibilidadQuery(
            profesional_id=uuid4(),
            desde=datetime(2026, 1, 1, 9, tzinfo=UTC),
            hasta=datetime(2026, 3, 1, 9, tzinfo=UTC),
        )
    assert "31" in str(exc.value)


def test_bloqueo_sin_motivo_o_extra_400():
    """# AC bloqueos-400: motivo vacío y campo extra → error por campo."""
    from app.modules.agenda.schemas import BloqueoCreate

    with pytest.raises(ValidationError) as exc:
        BloqueoCreate(
            profesional_id=uuid4(),
            desde=datetime(2026, 10, 20, 10, tzinfo=UTC),
            hasta=datetime(2026, 10, 20, 11, tzinfo=UTC),
            motivo="   ",
        )
    assert "motivo" in str(exc.value)
    with pytest.raises(ValidationError) as exc2:
        BloqueoCreate(
            profesional_id=uuid4(),
            desde=datetime(2026, 10, 20, 10, tzinfo=UTC),
            hasta=datetime(2026, 10, 20, 11, tzinfo=UTC),
            motivo="feriado ficticio",
            interno="x",  # type: ignore[call-arg]
        )
    assert "interno" in str(exc2.value)
