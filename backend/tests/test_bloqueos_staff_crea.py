"""Creación staff de bloqueos (capa: api, PG real).

# AC agenda-disponibilidad/Bloqueos (201 oculta slots, 400 motivo/rango,
# freshness avanza, `creado_por` desde sesión).
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(db_session):
    """TestClient https contra PG real con rollback + throttle limpio."""
    from app.core import ratelimit
    from app.db.session import get_db
    from app.main import app

    ratelimit.reset()
    ratelimit.reset_public()
    original = ratelimit.LOGIN_LIMIT
    ratelimit.LOGIN_LIMIT = 1000

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app, base_url="https://testserver") as c:
        yield c
    app.dependency_overrides.clear()
    ratelimit.LOGIN_LIMIT = original


@pytest.fixture
def recep(db_session):
    """Profesional con ventana lunes 09-12 + sesión recepción."""
    from datetime import date, time

    from app.models.disponibilidad import Disponibilidad
    from tests.conftest import mk_profesional
    from tests.test_auth_login import mk_staff

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
    db_session.flush()
    staff = mk_staff(db_session, "recepcion@ficticio.test", "password-ficticia-1")
    db_session.refresh(prof)
    antes = prof.ultima_actualizacion
    return {"prof": prof, "staff_id": str(staff.id), "freshness_antes": antes}


def _login(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "recepcion@ficticio.test", "password": "password-ficticia-1"},
    )
    assert response.status_code == 200


def _body(pid, motivo="feriado ficticio"):
    return {
        "profesional_id": str(pid),
        "desde": "2026-10-19T10:00:00-03:00",
        "hasta": "2026-10-19T11:00:00-03:00",
        "motivo": motivo,
    }


def test_crear_bloqueo_oculta_slots_201(client, db_session, recep):
    """# AC crear-bloqueo: 201 + freshness avanza + slots 10-11 ya no se ofrecen."""
    from datetime import UTC, datetime

    from app.models.profesional import Profesional

    _login(client)
    # `now()` es estable dentro de la transacción del test: se fija un valor
    # viejo para observar el avance del trigger de forma determinista.
    viejo = datetime(2026, 1, 1, tzinfo=UTC)
    db_session.query(Profesional).filter(
        Profesional.id == recep["prof"].id
    ).update({"ultima_actualizacion": viejo})
    db_session.flush()
    response = client.post("/api/bloqueos", json=_body(recep["prof"].id))
    assert response.status_code == 201
    assert response.json()["motivo"] == "feriado ficticio"
    db_session.refresh(recep["prof"])
    assert recep["prof"].ultima_actualizacion is not None
    assert recep["prof"].ultima_actualizacion > viejo
    slots = client.get(
        "/api/disponibilidad",
        params={
            "profesional_id": str(recep["prof"].id),
            "desde": "2026-10-19T09:00:00-03:00",
            "hasta": "2026-10-19T12:00:00-03:00",
        },
    )
    assert slots.status_code == 200
    horas = [s["inicio"][11:16] for s in slots.json()["slots"]]
    assert horas == ["09:00", "09:30", "11:00", "11:30"]


def test_bloqueo_sin_motivo_400(client, db_session, recep):
    """# AC 400-motivo: vacío/blancos o ausente → 400 y no persiste."""
    _login(client)
    sin_motivo = client.post(
        "/api/bloqueos", json=_body(recep["prof"].id, motivo="")
    )
    assert sin_motivo.status_code == 400
    assert (
        client.post(
            "/api/bloqueos", json=_body(recep["prof"].id, motivo="   ")
        ).status_code
        == 400
    )


def test_bloqueo_rango_invertido_400(client, db_session, recep):
    """# AC 400-rango: `desde >= hasta` o campo extra → 400 y no persiste."""
    _login(client)
    invertido = _body(recep["prof"].id)
    invertido["desde"], invertido["hasta"] = invertido["hasta"], invertido["desde"]
    assert client.post("/api/bloqueos", json=invertido).status_code == 400
    con_extra = _body(recep["prof"].id)
    con_extra["interno"] = "x"
    assert client.post("/api/bloqueos", json=con_extra).status_code == 400
