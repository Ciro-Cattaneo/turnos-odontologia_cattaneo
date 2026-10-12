"""Anti-solape EXCLUDE + half-open `[)` + colisión concurrente (capa: db).

# AC core-models/Solape-rechazado (dos activos solapados → exclusión).
# AC core-models/EDGE-borde-permitido (fin==inicio aceptado, rango `[)`).
# AC core-models/Cancelado-no-bloquea (predicado solo reservado/confirmado).
# AC core-models/Distinto-profesional (igualdad por profesional_id).
# AC core-models/Colision-concurrente (dos tx simultáneas → un ganador).

Objetivo de mutación (§5): el borde `<` vs `<=` — los tests de borde aceptan
`fin==inicio` exacto y rechazan cualquier solape de 1 minuto, de modo que un
mutante `[ ]`/`<=` (o predicado sin estado) falla al menos un caso.
"""

import threading
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy
from sqlalchemy.orm import Session

from tests.conftest import mk_paciente, mk_profesional, mk_turno, unique_token

BASE = datetime(2026, 10, 22, 13, 0, tzinfo=UTC)  # 10:00 America/Argentina


def _rango(desde_min: int, hasta_min: int):
    return (
        BASE + timedelta(minutes=desde_min),
        BASE + timedelta(minutes=hasta_min),
    )


@pytest.mark.parametrize("estado", ["reservado", "confirmado"])
def test_solape_activo_rechazado(db_session, estado):
    """# AC core-models/Solape-rechazado: 10:00–10:30 vs 10:15–10:45 choca."""
    from app.models.turno import TurnoEstado

    prof = mk_profesional(db_session)
    pac = mk_paciente(db_session)
    i1, f1 = _rango(0, 30)
    mk_turno(
        db_session,
        prof.id,
        pac.id,
        inicio=i1,
        fin=f1,
        estado=TurnoEstado(estado),
    )
    i2, f2 = _rango(15, 45)
    with pytest.raises(sqlalchemy.exc.IntegrityError, match="no_solape_prof"):
        mk_turno(db_session, prof.id, pac.id, inicio=i2, fin=f2)


def test_borde_exacto_fin_igual_inicio_permitido(db_session):
    """# AC core-models/EDGE-borde-permitido: `[10:00,10:30)` + `[10:30,11:00)`."""
    from app.models.turno import TurnoEstado

    prof = mk_profesional(db_session)
    pac = mk_paciente(db_session)
    i1, f1 = _rango(0, 30)
    mk_turno(
        db_session,
        prof.id,
        pac.id,
        inicio=i1,
        fin=f1,
        estado=TurnoEstado.confirmado,
    )
    i2, f2 = _rango(30, 60)
    segundo = mk_turno(db_session, prof.id, pac.id, inicio=i2, fin=f2)
    assert segundo.id is not None


def test_solape_de_un_minuto_en_borde_rechazado(db_session):
    """Triangulación del EDGE: 10:29–11:00 SÍ intersecta `[10:00,10:30)`."""
    prof = mk_profesional(db_session)
    pac = mk_paciente(db_session)
    i1, f1 = _rango(0, 30)
    mk_turno(db_session, prof.id, pac.id, inicio=i1, fin=f1)
    i2, f2 = _rango(29, 60)
    with pytest.raises(sqlalchemy.exc.IntegrityError, match="no_solape_prof"):
        mk_turno(db_session, prof.id, pac.id, inicio=i2, fin=f2)


@pytest.mark.parametrize("estado", ["cancelado", "atendido", "ausente"])
def test_solape_con_inactivo_permitido(db_session, estado):
    """# AC core-models/Cancelado-no-bloquea: fuera del predicado no bloquea."""
    from app.models.turno import TurnoEstado

    prof = mk_profesional(db_session)
    pac = mk_paciente(db_session)
    i1, f1 = _rango(0, 30)
    mk_turno(
        db_session,
        prof.id,
        pac.id,
        inicio=i1,
        fin=f1,
        estado=TurnoEstado(estado),
    )
    i2, f2 = _rango(15, 45)
    nuevo = mk_turno(db_session, prof.id, pac.id, inicio=i2, fin=f2)
    assert nuevo.id is not None


def test_mismo_horario_distinto_profesional_permitido(db_session):
    """# AC core-models/Distinto-profesional: la igualdad es por profesional."""
    p1 = mk_profesional(db_session)
    p2 = mk_profesional(db_session)
    pac = mk_paciente(db_session)
    i, f = _rango(0, 30)
    mk_turno(db_session, p1.id, pac.id, inicio=i, fin=f)
    otro = mk_turno(db_session, p2.id, pac.id, inicio=i, fin=f)
    assert otro.id is not None


def test_colision_concurrente_deja_un_ganador(test_engine):
    """# AC core-models/Colision-concurrente: 2 tx mismo slot → 1 fila."""
    from app.models.turno import TurnoEstado

    setup = Session(bind=test_engine)
    prof = mk_profesional(setup)
    pac = mk_paciente(setup)
    setup.commit()
    prof_id, pac_id = prof.id, pac.id
    setup.close()

    i, f = _rango(0, 30)
    barrera = threading.Barrier(2, timeout=30)
    resultados = []

    def reservar():
        sesion = Session(bind=test_engine)
        try:
            barrera.wait(timeout=30)
            turno = mk_turno(
                sesion,
                prof_id,
                pac_id,
                inicio=i,
                fin=f,
                estado=TurnoEstado.reservado,
                token_cancelacion=unique_token(),
            )
            sesion.commit()
            resultados.append(("ok", str(turno.id)))
        except sqlalchemy.exc.IntegrityError as exc:
            sesion.rollback()
            resultados.append(("rechazado", str(exc.orig)))
        finally:
            sesion.close()

    hilos = [threading.Thread(target=reservar) for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=60)

    try:
        estados = sorted(r[0] for r in resultados)
        assert estados == ["ok", "rechazado"], resultados
        assert "no_solape_prof" in resultados[1][1] or "exclusion" in (
            resultados[1][1].lower()
        )
        sesion = Session(bind=test_engine)
        try:
            n = sesion.execute(
                sqlalchemy.text(
                    "SELECT count(*) FROM turno "
                    "WHERE profesional_id = :prof AND inicio = :inicio"
                ),
                {"prof": str(prof_id), "inicio": i},
            ).scalar()
            assert n == 1
        finally:
            sesion.close()
    finally:
        limpieza = Session(bind=test_engine)
        try:
            limpieza.execute(
                sqlalchemy.text("DELETE FROM turno WHERE profesional_id = :prof"),
                {"prof": str(prof_id)},
            )
            limpieza.execute(
                sqlalchemy.text("DELETE FROM paciente WHERE id = :id"),
                {"id": str(pac_id)},
            )
            limpieza.execute(
                sqlalchemy.text("DELETE FROM profesional WHERE id = :id"),
                {"id": str(prof_id)},
            )
            limpieza.commit()
        finally:
            limpieza.close()
