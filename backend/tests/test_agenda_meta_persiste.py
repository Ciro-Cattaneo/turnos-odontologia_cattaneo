"""Freshness `ultima_actualizacion` vía trigger DB (capa: modelo/DB, PG real).

# AC agenda-disponibilidad/ultima_actualizacion-por-profesional (freshness/sin-datos).
"""

from datetime import UTC, date, datetime, time

from tests.conftest import mk_profesional


def _ventana(db_session, prof_id, dia=1):
    from app.models.disponibilidad import Disponibilidad

    v = Disponibilidad(
        profesional_id=prof_id,
        dia_semana=dia,
        hora_desde=time(9, 0),
        hora_hasta=time(12, 0),
        vigente_desde=date(2026, 1, 1),
        vigente_hasta=date(2026, 12, 31),
    )
    db_session.add(v)
    db_session.flush()
    return v


def test_profesional_nuevo_freshness_null(db_session):
    """# AC sin-datos: recién creado → `ultima_actualizacion` NULL."""
    prof = mk_profesional(db_session)
    db_session.refresh(prof)
    assert prof.ultima_actualizacion is None


def test_trigger_disponibilidad_actualiza_freshness(db_session):
    """# AC freshness: write en `disponibilidad` avanza `ultima_actualizacion`."""
    prof = mk_profesional(db_session)
    db_session.refresh(prof)
    assert prof.ultima_actualizacion is None
    _ventana(db_session, prof.id)
    db_session.refresh(prof)
    assert prof.ultima_actualizacion is not None
    assert prof.ultima_actualizacion.tzinfo is not None


def test_trigger_bloqueo_actualiza_freshness(db_session):
    """# AC freshness: write en `bloqueo` avanza `ultima_actualizacion`."""
    from app.models.bloqueo import Bloqueo

    prof = mk_profesional(db_session)
    db_session.refresh(prof)
    assert prof.ultima_actualizacion is None
    db_session.add(
        Bloqueo(
            profesional_id=prof.id,
            desde=datetime(2026, 10, 20, 10, 0, tzinfo=UTC),
            hasta=datetime(2026, 10, 20, 11, 0, tzinfo=UTC),
            motivo="feriado ficticio",
        )
    )
    db_session.flush()
    db_session.refresh(prof)
    assert prof.ultima_actualizacion is not None
