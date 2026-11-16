"""Alcance por rol del reporte de ocupación (capa: api/DB real).

# AC RE-R5: admin/recepción leen todo; odontólogo solo su fila (403 con
# otro `profesional_id`, 403 sin vínculo); sin sesión 401.
"""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.models.usuario_staff import StaffRol

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
LUNES = date(2026, 10, 19)


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


def _staff(db_session, email, rol, profesional_id=None):
    from tests.test_auth_login import mk_staff

    return mk_staff(
        db_session,
        email,
        "password-ficticia-1",
        rol=rol,
        profesional_id=profesional_id,
    )


def _prof_con_turno(db_session):
    from app.models.disponibilidad import Disponibilidad
    from app.models.turno import TurnoEstado
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
    inicio = datetime(2026, 10, 19, 9, 0, tzinfo=TZ)
    mk_turno(
        db_session,
        prof.id,
        pac.id,
        inicio=inicio,
        fin=datetime(2026, 10, 19, 9, 30, tzinfo=TZ),
        estado=TurnoEstado.atendido,
    )
    db_session.flush()
    return prof


@pytest.fixture
def escenario(db_session):
    """Dos profesionales con un turno en el rango (LUNES 09:00 local)."""
    p1 = _prof_con_turno(db_session)
    p2 = _prof_con_turno(db_session)
    db_session.flush()
    _staff(db_session, "admin@cattaneo.test", StaffRol.admin)
    _staff(db_session, "recepcion@cattaneo.test", StaffRol.recepcion)
    _staff(
        db_session,
        "odonto@cattaneo.test",
        StaffRol.odontologo,
        profesional_id=p1.id,
    )
    _staff(db_session, "sin-link@cattaneo.test", StaffRol.odontologo)
    return {"p1": p1, "p2": p2}


def _login(client, email):
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "password-ficticia-1"},
    )
    assert response.status_code == 200


def _params(**extra):
    return {"desde": LUNES.isoformat(), "hasta": LUNES.isoformat(), **extra}


@pytest.mark.parametrize("email", ["admin@cattaneo.test", "recepcion@cattaneo.test"])
def test_reporte_rbac_admin_y_recepcion_todos(client, escenario, email):
    """# AC RE-R5: admin y recepción ven las filas de todos los profesionales."""
    _login(client, email)
    response = client.get("/api/reportes/ocupacion", params=_params())
    assert response.status_code == 200
    ids = {item["profesional"]["id"] for item in response.json()["items"]}
    assert {str(escenario["p1"].id), str(escenario["p2"].id)} <= ids


def test_reporte_odontologo_solo_propio(client, escenario):
    """# AC RE-R5: el odontólogo obtiene una única fila, la propia."""
    _login(client, "odonto@cattaneo.test")
    response = client.get("/api/reportes/ocupacion", params=_params())
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["profesional"]["id"] == str(escenario["p1"].id)


def test_reporte_odontologo_otro_profesional_403(client, escenario):
    """# AC RE-R5: pedir un `profesional_id` ajeno responde 403 genérico."""
    _login(client, "odonto@cattaneo.test")
    response = client.get(
        "/api/reportes/ocupacion",
        params=_params(profesional_id=str(escenario["p2"].id)),
    )
    assert response.status_code == 403
    assert str(escenario["p2"].id) not in response.text


def test_reporte_odontologo_sin_vinculo_403(client, db_session):
    """# AC RE-R5: odontólogo sin `profesional_id` no resuelve alcance → 403."""
    _staff(db_session, "sin-link@cattaneo.test", StaffRol.odontologo)
    _login(client, "sin-link@cattaneo.test")
    response = client.get("/api/reportes/ocupacion", params=_params())
    assert response.status_code == 403


def test_reporte_sin_sesion_401(client):
    """# AC RE-R5: sin cookie de sesión → 401 genérico."""
    response = client.get("/api/reportes/ocupacion", params=_params())
    assert response.status_code == 401
