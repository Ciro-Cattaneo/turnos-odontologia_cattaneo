"""Rama staff de la agenda día/semana (capa: api, PG real).

# AC agenda-disponibilidad/Agenda-staff (tipifica libre/ocupado/bloqueado,
# semana 7 días keyset, fecha inválida 400).
"""

from datetime import date, datetime, time, timedelta
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
def staff_escenario(db_session):
    """Ventana lun-vie 09-12 + reservado lunes 09:00 + bloqueo lunes 10:00."""
    from datetime import UTC

    from app.models.bloqueo import Bloqueo
    from app.models.disponibilidad import Disponibilidad
    from tests.conftest import mk_paciente, mk_profesional, mk_turno
    from tests.test_auth_login import mk_staff

    prof = mk_profesional(db_session)
    for dia in range(5):
        db_session.add(
            Disponibilidad(
                profesional_id=prof.id,
                dia_semana=dia,
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
            motivo="feriado ficticio",
        )
    )
    db_session.flush()
    mk_staff(db_session, "recepcion@ficticio.test", "password-ficticia-1")
    return prof


def _login(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "recepcion@ficticio.test", "password": "password-ficticia-1"},
    )
    assert response.status_code == 200


def test_vista_dia_tipifica_franjas(client, db_session, staff_escenario):
    """# AC vista-día-staff: ocupado (estado+paciente) + bloqueado (motivo) + libres."""
    _login(client)
    response = client.get(
        f"/api/profesionales/{staff_escenario.id}/agenda",
        params={"vista": "dia", "fecha": "2026-10-19"},
    )
    assert response.status_code == 200
    franjas = response.json()["dias"][0]["franjas"]
    tipos = [f["tipo"] for f in franjas]
    assert "ocupado" in tipos and "bloqueado" in tipos and "libre" in tipos
    ocupado = next(f for f in franjas if f["tipo"] == "ocupado")
    assert ocupado["estado"] == "reservado"
    assert ocupado["paciente"]["nombre"].startswith("Paciente Ficticio")
    assert "dni" not in str(ocupado).lower()
    bloqueado = next(f for f in franjas if f["tipo"] == "bloqueado")
    assert bloqueado["motivo"] == "feriado ficticio"


def test_vista_semana_siete_dias_keyset(client, db_session, staff_escenario):
    """# AC vista-semana: 7 días + `next_cursor` (+7) sin OFFSET."""
    _login(client)
    response = client.get(
        f"/api/profesionales/{staff_escenario.id}/agenda",
        params={"vista": "semana", "fecha": "2026-10-19"},
    )
    assert response.status_code == 200
    cuerpo = response.json()
    assert len(cuerpo["dias"]) == 7
    assert cuerpo["dias"][0]["fecha"] == "2026-10-19"
    assert cuerpo["dias"][-1]["fecha"] == "2026-10-25"
    assert cuerpo["next_cursor"] == "2026-10-26"
    assert cuerpo["vista"] == "semana"


def test_fecha_invalida_400(client, db_session, staff_escenario):
    """# AC 400-fecha: `fecha` malformada o `vista` ajena → 400 por campo."""
    _login(client)
    assert (
        client.get(
            f"/api/profesionales/{staff_escenario.id}/agenda",
            params={"vista": "dia", "fecha": "19/10/2026"},
        ).status_code
        == 400
    )
    assert (
        client.get(
            f"/api/profesionales/{staff_escenario.id}/agenda",
            params={"vista": "mes", "fecha": "2026-10-19"},
        ).status_code
        == 400
    )


@pytest.fixture
def agenda_lunes(db_session):
    """Lunes 09:00–12:00 local con turno activo de `duracion_min` configurable."""
    from datetime import UTC

    from app.models.disponibilidad import Disponibilidad
    from app.models.turno import TurnoEstado
    from tests.conftest import mk_paciente, mk_profesional, mk_turno
    from tests.test_auth_login import mk_staff

    def _crear(duracion_min: int, estado=TurnoEstado.reservado):
        prof = mk_profesional(db_session, duracion_default_min=duracion_min)
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
        inicio = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
        turno = mk_turno(
            db_session,
            prof.id,
            pac.id,
            inicio=inicio,
            fin=inicio + timedelta(minutes=duracion_min),
            estado=estado,
        )
        db_session.flush()
        mk_staff(db_session, "recepcion@ficticio.test", "password-ficticia-1")
        return prof, turno, pac

    return _crear


def test_franja_ocupada_expone_turno_id_y_duracion(client, db_session, agenda_lunes):
    """# AC franjas-staff: `ocupado` con `turno_id` + `duracion_min` del turno."""
    prof, turno, _ = agenda_lunes(45)
    _login(client)
    response = client.get(
        f"/api/profesionales/{prof.id}/agenda",
        params={"vista": "dia", "fecha": "2026-10-19"},
    )
    assert response.status_code == 200
    franjas = response.json()["dias"][0]["franjas"]
    ocupado = next(f for f in franjas if f["tipo"] == "ocupado")
    assert ocupado["turno_id"] == str(turno.id)
    assert ocupado["duracion_min"] == 45


def test_franja_libre_expone_granularidad(client, db_session, agenda_lunes):
    """# AC franjas-staff: cada `libre` incluye la granularidad del profesional."""
    prof, _, _ = agenda_lunes(30)
    _login(client)
    response = client.get(
        f"/api/profesionales/{prof.id}/agenda",
        params={"vista": "dia", "fecha": "2026-10-19"},
    )
    assert response.status_code == 200
    libres = [f for f in response.json()["dias"][0]["franjas"] if f["tipo"] == "libre"]
    assert libres
    assert all(f["duracion_min"] == 30 for f in libres)


def test_turno_cancelado_sigue_libre_y_aparece_cerrado(
    client, db_session, agenda_lunes
):
    """# AC cerrados: un cancelado no ocupa y aparece una sola vez como cerrado."""
    from app.models.turno import TurnoEstado

    prof, turno, _ = agenda_lunes(30, estado=TurnoEstado.cancelado)
    _login(client)
    response = client.get(
        f"/api/profesionales/{prof.id}/agenda",
        params={"vista": "dia", "fecha": "2026-10-19"},
    )
    assert response.status_code == 200
    franjas = response.json()["dias"][0]["franjas"]
    libres = [f for f in franjas if f["tipo"] == "libre"]
    assert any(f["inicio"].startswith("2026-10-19T09:00") for f in libres)
    cerrados = [f for f in franjas if f["tipo"] == "cerrado"]
    assert len(cerrados) == 1
    cerrado = cerrados[0]
    assert cerrado["turno_id"] == str(turno.id)
    assert cerrado["estado"] == "cancelado"
    assert cerrado["duracion_min"] == 30
    assert cerrado["paciente"]["nombre"].startswith("Paciente Ficticio")
    assert not any(f["tipo"] == "ocupado" for f in franjas)


def test_turnos_terminales_se_listan_todos_como_cerrados(
    client, db_session, agenda_lunes
):
    """# AC cerrados: atendido, ausente y cancelado aparecen una vez cada uno."""
    from app.models.turno import TurnoEstado
    from tests.conftest import mk_turno

    prof, _, paciente = agenda_lunes(30, estado=TurnoEstado.cancelado)
    for hora, estado in ((10, TurnoEstado.atendido), (11, TurnoEstado.ausente)):
        inicio = datetime(2026, 10, 19, hora, 0, tzinfo=TZ)
        mk_turno(
            db_session,
            prof.id,
            paciente.id,
            inicio=inicio,
            fin=inicio + timedelta(minutes=30),
            estado=estado,
        )
    db_session.flush()
    _login(client)
    response = client.get(
        f"/api/profesionales/{prof.id}/agenda",
        params={"vista": "dia", "fecha": "2026-10-19"},
    )
    assert response.status_code == 200
    franjas = response.json()["dias"][0]["franjas"]
    cerrados = [f for f in franjas if f["tipo"] == "cerrado"]
    assert {f["estado"] for f in cerrados} == {"cancelado", "atendido", "ausente"}
    assert len(cerrados) == 3
    assert not any(f["tipo"] == "ocupado" for f in franjas)
