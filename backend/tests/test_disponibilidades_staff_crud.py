"""CRUD staff de disponibilidades (capa: api, PG real).

# AC agenda-disponibilidad/CRUD-staff + LOCK D-3 (201/409-borde/distinto,
# 400-por-campo, freshness avanza vía trigger).
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(db_session):
    """TestClient https contra PG real con rollback + throttle holgado."""
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
    """Profesional + sesión recepción (datos ficticios)."""
    from tests.conftest import mk_profesional
    from tests.test_auth_login import mk_staff

    prof = mk_profesional(db_session)
    mk_staff(db_session, "recepcion@ficticio.test", "password-ficticia-1")
    return prof


def _login(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "recepcion@ficticio.test", "password": "password-ficticia-1"},
    )
    assert response.status_code == 200


def _body(pid, dia=1, h0="09:00:00", h1="12:00:00"):
    return {
        "profesional_id": str(pid),
        "dia_semana": dia,
        "hora_desde": h0,
        "hora_hasta": h1,
    }


def test_crear_ventana_avanza_freshness_201(client, db_session, recep):
    """# AC crear-válida: 201 + persiste + `ultima_actualizacion` avanza."""
    _login(client)
    db_session.refresh(recep)
    assert recep.ultima_actualizacion is None
    response = client.post("/api/disponibilidades", json=_body(recep.id))
    assert response.status_code == 201
    assert response.json()["dia_semana"] == 1
    db_session.refresh(recep)
    assert recep.ultima_actualizacion is not None


def test_solapada_mismo_dia_rechazada_409(client, db_session, recep):
    """# AC 409-solape: martes 11-13 sobre 09-12 → 409 con conflicto, no persiste."""
    _login(client)
    assert client.post("/api/disponibilidades", json=_body(recep.id)).status_code == 201
    conflicto = client.post(
        "/api/disponibilidades", json=_body(recep.id, h0="11:00:00", h1="13:00:00")
    )
    assert conflicto.status_code == 409
    assert "11:00" in str(conflicto.json()) or "conflicto" in str(conflicto.json())


def test_adyacente_borde_permitida_201(client, db_session, recep):
    """# AC borde `[)`: 12:00-14:00 sobre 09-12 → 201 (no es solape)."""
    _login(client)
    assert client.post("/api/disponibilidades", json=_body(recep.id)).status_code == 201
    response = client.post(
        "/api/disponibilidades", json=_body(recep.id, h0="12:00:00", h1="14:00:00")
    )
    assert response.status_code == 201


def test_distinto_profesional_o_dia_permitida_201(client, db_session, recep):
    """# AC scope-validación: mismo horario otro profesional u otro día → 201."""
    from tests.conftest import mk_profesional

    otro = mk_profesional(db_session)
    _login(client)
    assert client.post("/api/disponibilidades", json=_body(recep.id)).status_code == 201
    assert client.post("/api/disponibilidades", json=_body(otro.id)).status_code == 201
    assert (
        client.post("/api/disponibilidades", json=_body(recep.id, dia=2)).status_code
        == 201
    )


def test_schema_extra_400(client, db_session, recep):
    """# AC 400-por-campo: campo extra / día 9 / horario invertido → 400."""
    _login(client)
    assert (
        client.post(
            "/api/disponibilidades", json={**_body(recep.id), "interno": "x"}
        ).status_code
        == 400
    )
    assert (
        client.post("/api/disponibilidades", json=_body(recep.id, dia=9)).status_code
        == 400
    )
    assert (
        client.post(
            "/api/disponibilidades", json=_body(recep.id, h0="12:00:00", h1="09:00:00")
        ).status_code
        == 400
    )
