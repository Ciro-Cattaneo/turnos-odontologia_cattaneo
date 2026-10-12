"""Rama pública de la agenda (capa: api, PG real).

# AC agenda-disponibilidad/Agenda-pública (solo libres, sin paciente/motivo,
# 404 inexistente/inactivo).
"""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

TZ = ZoneInfo("America/Argentina/Buenos_Aires")


@pytest.fixture
def client(db_session):
    """TestClient https contra PG real con rollback + throttle limpio."""
    from app.core import ratelimit
    from app.db.session import get_db
    from app.main import app

    ratelimit.reset()
    ratelimit.reset_public()

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app, base_url="https://testserver") as c:
        yield c
    app.dependency_overrides.clear()


def _escenario(db_session):
    """Ventana lunes 09-12 + reservado 09:00 + bloqueo 10:00-10:30."""
    from datetime import UTC

    from app.models.bloqueo import Bloqueo
    from app.models.disponibilidad import Disponibilidad
    from tests.conftest import mk_paciente, mk_profesional, mk_turno

    prof = mk_profesional(db_session)
    db_session.add(
        Disponibilidad(
            profesional_id=prof.id,
            dia_semana=0,
            hora_desde=time(9, 0),
            hora_hasta=time(12, 0),
            vigente_desde=date(2026, 1, 1),
            vigente_hasta=date(2026, 12, 31),
        )
    )
    pac = mk_paciente(db_session)
    mk_turno(
        db_session,
        prof.id,
        pac.id,
        inicio=datetime(2026, 10, 19, 12, 0, tzinfo=UTC),
        fin=datetime(2026, 10, 19, 12, 30, tzinfo=UTC),
    )
    db_session.add(
        Bloqueo(
            profesional_id=prof.id,
            desde=datetime(2026, 10, 19, 10, 0, tzinfo=TZ),
            hasta=datetime(2026, 10, 19, 10, 30, tzinfo=TZ),
            motivo="motivo interno ficticio",
        )
    )
    db_session.flush()
    return prof


def test_agenda_publica_oculta_paciente(client, db_session):
    """# AC agenda-pública: sin auth solo `libre`, sin nombre/DNI/teléfono."""
    prof = _escenario(db_session)
    response = client.get(
        f"/api/profesionales/{prof.id}/agenda",
        params={"vista": "dia", "fecha": "2026-10-19"},
    )
    assert response.status_code == 200
    franjas = response.json()["dias"][0]["franjas"]
    assert franjas
    assert {f["tipo"] for f in franjas} == {"libre"}
    cuerpo = str(response.json())
    assert "Paciente Ficticio" not in cuerpo
    assert "ocupado" not in cuerpo


def test_agenda_publica_oculta_bloqueados(client, db_session):
    """# AC agenda-pública: bloqueados no listados y motivo interno oculto."""
    prof = _escenario(db_session)
    response = client.get(
        f"/api/profesionales/{prof.id}/agenda",
        params={"vista": "dia", "fecha": "2026-10-19"},
    )
    assert response.status_code == 200
    cuerpo = str(response.json())
    assert "bloqueado" not in cuerpo
    assert "motivo interno ficticio" not in cuerpo
    # 09:00 ocupado + 10:00 bloqueado → 4 de 6 libres.
    assert len(response.json()["dias"][0]["franjas"]) == 4


def test_agenda_profesional_inexistente_404(client, db_session):
    """# AC 404: id inexistente o inactivo sin auth → 404 sin datos staff."""
    from uuid import uuid4

    from tests.conftest import mk_profesional

    assert (
        client.get(
            f"/api/profesionales/{uuid4()}/agenda",
            params={"vista": "dia", "fecha": "2026-10-19"},
        ).status_code
        == 404
    )
    inactivo = mk_profesional(db_session, activo=False)
    respuesta = client.get(
        f"/api/profesionales/{inactivo.id}/agenda",
        params={"vista": "dia", "fecha": "2026-10-19"},
    )
    assert respuesta.status_code == 404
    assert "password_hash" not in respuesta.text
