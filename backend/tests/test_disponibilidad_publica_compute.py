"""Cómputo público de disponibilidad (capa: api, PG real).

# AC agenda-disponibilidad/Cómputo-público (feliz, 45', sin-ventana, borde,
# liberan-slot). Sin auth y con token staff (sin fuga de datos).
"""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

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

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app, base_url="https://testserver") as c:
        yield c
    app.dependency_overrides.clear()


def _ventana(db_session, prof_id, dia=0, desde=9, hasta=11):
    from app.models.disponibilidad import Disponibilidad

    v = Disponibilidad(
        profesional_id=prof_id,
        dia_semana=dia,
        hora_desde=time(desde, 0),
        hora_hasta=time(hasta, 0),
        vigente_desde=date(2026, 1, 1),
        vigente_hasta=date(2026, 12, 31),
    )
    db_session.add(v)
    db_session.flush()
    return v


def _bloqueo(db_session, prof_id, h0=9, m0=30, h1=10, m1=0):
    from app.models.bloqueo import Bloqueo

    b = Bloqueo(
        profesional_id=prof_id,
        desde=datetime(2026, 10, 19, h0, m0, tzinfo=TZ),
        hasta=datetime(2026, 10, 19, h1, m1, tzinfo=TZ),
        motivo="feriado ficticio",
    )
    db_session.add(b)
    db_session.flush()
    return b


def _params(pid, h0=9, h1=11, dia=19):
    return {
        "profesional_id": str(pid),
        "desde": f"2026-10-{dia:02d}T{h0:02d}:00:00-03:00",
        "hasta": f"2026-10-{dia:02d}T{h1:02d}:00:00-03:00",
    }


def test_ventanas_menos_bloqueos_ocupados_libres(client, db_session):
    """# AC feliz: ventana − bloqueo − reservado → libres [09:00, 10:30]."""
    from tests.conftest import mk_paciente, mk_profesional, mk_turno

    prof = mk_profesional(db_session)
    _ventana(db_session, prof.id)
    _bloqueo(db_session, prof.id)
    pac = mk_paciente(db_session)
    mk_turno(
        db_session,
        prof.id,
        pac.id,
        inicio=datetime(2026, 10, 19, 13, 0, tzinfo=datetime_utc()),
        fin=datetime(2026, 10, 19, 13, 30, tzinfo=datetime_utc()),
    )
    response = client.get("/api/disponibilidad", params=_params(prof.id))
    assert response.status_code == 200
    horas = [(s["inicio"][11:16]) for s in response.json()["slots"]]
    assert horas == ["09:00", "10:30"]
    assert all(s["duracion_min"] == 30 for s in response.json()["slots"])


def datetime_utc():
    from datetime import UTC

    return UTC


def test_granularidad_45_responde_45(client, db_session):
    """# AC granularidad-45: duracion 45' → slots de 45, ninguno de 30."""
    from tests.conftest import mk_profesional

    prof = mk_profesional(db_session, duracion_default_min=45)
    _ventana(db_session, prof.id, hasta=12)
    response = client.get("/api/disponibilidad", params=_params(prof.id, h1=12))
    assert response.status_code == 200
    horas = [s["inicio"][11:16] for s in response.json()["slots"]]
    assert horas == ["09:00", "09:45", "10:30", "11:15"]
    assert all(s["duracion_min"] == 45 for s in response.json()["slots"])


def test_sin_ventana_lista_vacia(client, db_session):
    """# AC sin-ventana: sin ventanas → 200 lista vacía (no inventa horarios)."""
    from tests.conftest import mk_profesional

    prof = mk_profesional(db_session)
    response = client.get("/api/disponibilidad", params=_params(prof.id))
    assert response.status_code == 200
    assert response.json()["slots"] == []


def test_borde_ventana_incluye_slot(client, db_session):
    """# AC borde `[)`: ventana 09-10 → [09:00, 09:30], nada excede 10:00."""
    from tests.conftest import mk_profesional

    prof = mk_profesional(db_session)
    _ventana(db_session, prof.id, hasta=10)
    response = client.get("/api/disponibilidad", params=_params(prof.id, h1=10))
    assert response.status_code == 200
    horas = [s["inicio"][11:16] for s in response.json()["slots"]]
    assert horas == ["09:00", "09:30"]


def test_cancelado_libera_slot(client, db_session):
    """# AC liberan-slot: cancelado/atendido no ocupan → ambos libres."""
    from datetime import UTC

    from app.models.turno import TurnoEstado
    from tests.conftest import mk_paciente, mk_profesional, mk_turno

    prof = mk_profesional(db_session)
    _ventana(db_session, prof.id, hasta=10)
    pac = mk_paciente(db_session)
    mk_turno(
        db_session,
        prof.id,
        pac.id,
        inicio=datetime(2026, 10, 19, 12, 0, tzinfo=UTC),
        fin=datetime(2026, 10, 19, 12, 30, tzinfo=UTC),
        estado=TurnoEstado.cancelado,
    )
    pac2 = mk_paciente(db_session)
    mk_turno(
        db_session,
        prof.id,
        pac2.id,
        inicio=datetime(2026, 10, 19, 12, 30, tzinfo=UTC),
        fin=datetime(2026, 10, 19, 13, 0, tzinfo=UTC),
        estado=TurnoEstado.atendido,
    )
    response = client.get("/api/disponibilidad", params=_params(prof.id, h1=10))
    assert response.status_code == 200
    assert len(response.json()["slots"]) == 2


def test_con_staff_token_no_hay_fuga(client, db_session):
    """# AC sin-fuga: con sesión staff el público no expone pacientes/motivos."""
    from tests.conftest import mk_profesional
    from tests.test_auth_login import mk_staff

    prof = mk_profesional(db_session)
    _ventana(db_session, prof.id)
    mk_staff(db_session, "recepcion@ficticio.test", "password-ficticia-1")
    login = client.post(
        "/api/auth/login",
        json={"email": "recepcion@ficticio.test", "password": "password-ficticia-1"},
    )
    assert login.status_code == 200
    response = client.get("/api/disponibilidad", params=_params(prof.id))
    assert response.status_code == 200
    cuerpo = str(response.json())
    assert "paciente" not in cuerpo.lower()
    assert "motivo" not in cuerpo.lower()
    assert "password_hash" not in cuerpo
