"""Admin de profesionales: schemas y API (capa: unit/schemas + api/DB real).

# AC admin-profesionales R1-R5 (alta/edición/baja/listado/reactivación/RBAC).
"""

import threading
from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4

import pytest
from fastapi.exceptions import HTTPException
from fastapi.testclient import TestClient

from app.models.usuario_staff import StaffRol

# --- §1 schemas ---------------------------------------------------------


def _detalle_body(model, body):
    """Valida body y devuelve el `detail` 400 del contrato."""
    from app.modules.turnos.schemas import parse_body_or_400

    with pytest.raises(HTTPException) as exc:
        parse_body_or_400(model, body)
    assert exc.value.status_code == 400
    return exc.value.detail


def _campos(detalle):
    return {d["campo"] for d in detalle}


@pytest.mark.parametrize("nombre", ["", "   "])
def test_alta_profesional_nombre_vacio_400(nombre):
    """# AC AP-R1: nombre vacío/solo espacios → 400 en `nombre`."""
    from app.modules.profesionales.schemas import ProfesionalCreate

    detalle = _detalle_body(ProfesionalCreate, {"nombre": nombre})
    assert "nombre" in _campos(detalle)


def test_alta_profesional_campo_extra_400():
    """# AC AP-R1: clave no declarada → 400 en ese campo."""
    from app.modules.profesionales.schemas import ProfesionalCreate

    detalle = _detalle_body(
        ProfesionalCreate,
        {"nombre": "Dra. Ficticia", "email": "extra@cattaneo.test"},
    )
    assert "email" in _campos(detalle)


@pytest.mark.parametrize("duracion", [0, -30, 32, 250, "treinta"])
def test_alta_profesional_duracion_invalida_400(duracion):
    """# AC AP-R1: 0/-30/32/250/"treinta" → 400 en `duracion_default_min`."""
    from app.modules.profesionales.schemas import ProfesionalCreate

    detalle = _detalle_body(
        ProfesionalCreate,
        {"nombre": "Dra. Ficticia", "duracion_default_min": duracion},
    )
    assert "duracion_default_min" in _campos(detalle)


def test_alta_profesional_duracion_default_30():
    """# AC AP-R1: sin duración explícita el default es 30."""
    from app.modules.profesionales.schemas import ProfesionalCreate

    data = ProfesionalCreate(nombre="Dra. Ficticia Uno")
    assert data.duracion_default_min == 30


def test_alta_profesional_matricula_especialidad_null_201():
    """# AC AP-R1 borde: matrícula/especialidad opcionales; out sin turnos."""
    from app.modules.profesionales.schemas import (
        ProfesionalAdminOut,
        ProfesionalCreate,
    )

    data = ProfesionalCreate(nombre="Dra. Ficticia Uno")
    assert data.matricula is None
    assert data.especialidad is None
    assert set(ProfesionalAdminOut.model_fields) == {
        "id",
        "nombre",
        "matricula",
        "especialidad",
        "duracion_default_min",
        "activo",
        "ultima_actualizacion",
    }
    assert "turnos" not in ProfesionalAdminOut.model_fields


def test_edicion_profesional_body_vacio_400():
    """# AC AP-R2: body `{}` → 400 en `body`."""
    from app.modules.profesionales.schemas import ProfesionalUpdate

    detalle = _detalle_body(ProfesionalUpdate, {})
    assert "body" in _campos(detalle)


def test_edicion_profesional_campo_extra_400():
    """# AC AP-R2: clave desconocida → 400 en esa clave."""
    from app.modules.profesionales.schemas import ProfesionalUpdate

    detalle = _detalle_body(ProfesionalUpdate, {"turnos": []})
    assert "turnos" in _campos(detalle)


def test_edicion_profesional_activo_tipo_invalido_400():
    """# AC AP-R2: `activo` no booleano → 400 en `activo`."""
    from app.modules.profesionales.schemas import ProfesionalUpdate

    detalle = _detalle_body(ProfesionalUpdate, {"activo": "si"})
    assert "activo" in _campos(detalle)


def test_listado_profesionales_incluir_inactivos_invalido_400():
    """# AC AP-R4: flag no booleano → 400 en `incluir_inactivos`."""
    from app.modules.agenda.public import parse_query_or_400
    from app.modules.agenda.schemas import ProfesionalesQuery

    with pytest.raises(HTTPException) as exc:
        parse_query_or_400(ProfesionalesQuery, {"incluir_inactivos": "maybe"})
    assert exc.value.status_code == 400
    assert "incluir_inactivos" in _campos(exc.value.detail)


def test_profesionales_query_extra_sigue_prohibido():
    """# AC AP-R4: agregar el flag no afloja `extra='forbid'`."""
    from app.modules.agenda.public import parse_query_or_400
    from app.modules.agenda.schemas import ProfesionalesQuery

    with pytest.raises(HTTPException) as exc:
        parse_query_or_400(ProfesionalesQuery, {"inventado": "x"})
    assert "inventado" in _campos(exc.value.detail)


# --- helpers API (PG real, rollback por test) ---------------------------

PASSWORD = "password-ficticia-1"
ADMIN_EMAIL = "admin.ficticio@cattaneo.test"


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


def _staff(db_session, rol=StaffRol.recepcion, email=None, profesional_id=None):
    from tests.test_auth_login import mk_staff

    return mk_staff(
        db_session,
        email or f"staff.{uuid4().hex[:8]}@cattaneo.test",
        PASSWORD,
        rol=rol,
        profesional_id=profesional_id,
    )


def _login(client, email=ADMIN_EMAIL):
    resp = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text


def _admin(client, db_session):
    _staff(db_session, StaffRol.admin, ADMIN_EMAIL)
    _login(client)


def _prof(db_session, **kw):
    from tests.conftest import mk_profesional

    return mk_profesional(db_session, **kw)


def _turno(db_session, prof, estado=None, inicio=None, duracion=30):
    from tests.conftest import mk_paciente, mk_turno

    pac = mk_paciente(db_session)
    inicio = inicio or datetime(2026, 12, 7, 13, 0, tzinfo=UTC)
    return mk_turno(
        db_session,
        prof.id,
        pac.id,
        inicio=inicio,
        fin=inicio + timedelta(minutes=duracion),
        estado=estado,
    )


def _agregar_agenda_dependientes(db_session, prof_id):
    from app.models.bloqueo import Bloqueo
    from app.models.disponibilidad import Disponibilidad

    db_session.add(
        Disponibilidad(
            profesional_id=prof_id,
            dia_semana=0,
            hora_desde=time(9, 0),
            hora_hasta=time(13, 0),
            vigente_desde=date(2026, 1, 1),
            vigente_hasta=date(2026, 12, 31),
        )
    )
    db_session.add(
        Bloqueo(
            profesional_id=prof_id,
            desde=datetime(2026, 12, 7, 13, 0, tzinfo=UTC),
            hasta=datetime(2026, 12, 7, 13, 30, tzinfo=UTC),
            motivo="bloqueo ficticio",
        )
    )
    db_session.flush()


def _count(db_session, model, prof_id):
    return db_session.query(model).filter(model.profesional_id == prof_id).count()


# --- §2 alta y edición --------------------------------------------------


def test_alta_profesional_201_activo_default(client, db_session):
    """# AC AP-R1: 201 + `activo=true` + duración 30 persistidos."""
    from app.models.profesional import Profesional

    _admin(client, db_session)
    resp = client.post("/api/profesionales", json={"nombre": "Dra. Ficticia Uno"})

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["activo"] is True
    assert body["duracion_default_min"] == 30
    assert "turnos" not in body
    fila = db_session.get(Profesional, body["id"])
    assert fila.activo is True
    assert fila.duracion_default_min == 30


def test_alta_profesional_duracion_45_201(client, db_session):
    """# AC AP-R1: alta con todos los campos opcionales + duración 45."""
    from app.models.profesional import Profesional

    _admin(client, db_session)
    resp = client.post(
        "/api/profesionales",
        json={
            "nombre": "Dr. Ficticio Dos",
            "matricula": "MP-1234",
            "especialidad": "Ortodoncia",
            "duracion_default_min": 45,
        },
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["matricula"] == "MP-1234"
    assert body["especialidad"] == "Ortodoncia"
    fila = db_session.get(Profesional, body["id"])
    assert fila.duracion_default_min == 45


@pytest.mark.parametrize("duracion", [5, 240])
def test_alta_profesional_duracion_limite_5_240_201(client, db_session, duracion):
    """# AC AP-R1 borde: 5 y 240 se aceptan y persisten."""
    from app.models.profesional import Profesional

    _admin(client, db_session)
    resp = client.post(
        "/api/profesionales",
        json={"nombre": "Dra. Ficticia Limite", "duracion_default_min": duracion},
    )

    assert resp.status_code == 201, resp.text
    fila = db_session.get(Profesional, resp.json()["id"])
    assert fila.duracion_default_min == duracion


def test_edicion_profesional_duracion_no_altera_turnos(client, db_session):
    """# AC AP-R2: cambiar duración default no reescribe turnos existentes."""
    from app.models.turno import Turno

    prof = _prof(db_session, duracion_default_min=30)
    turno = _turno(db_session, prof)
    antes = (turno.estado, turno.inicio, turno.fin, turno.duracion_min)
    _admin(client, db_session)

    resp = client.put(
        f"/api/profesionales/{prof.id}", json={"duracion_default_min": 45}
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["duracion_default_min"] == 45
    db_session.expire_all()
    fila = db_session.get(Turno, turno.id)
    assert (fila.estado, fila.inicio, fila.fin, fila.duracion_min) == antes


def test_edicion_profesional_noop_200_sin_tocar_ultima_actualizacion(
    client, db_session
):
    """# AC AP-R2: PUT con los mismos valores → 200 sin UPDATE (freshness)."""
    from app.models.profesional import Profesional

    marca = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
    prof = _prof(db_session, ultima_actualizacion=marca)
    _admin(client, db_session)

    resp = client.put(
        f"/api/profesionales/{prof.id}",
        json={
            "nombre": prof.nombre,
            "duracion_default_min": prof.duracion_default_min,
        },
    )

    assert resp.status_code == 200, resp.text
    db_session.expire_all()
    fila = db_session.get(Profesional, prof.id)
    assert fila.ultima_actualizacion == marca


def test_edicion_profesional_datos_200(client, db_session):
    """# AC AP-R2: PUT de nombre/matrícula/especialidad → 200 y persiste."""
    from app.models.profesional import Profesional

    prof = _prof(db_session)
    _admin(client, db_session)

    resp = client.put(
        f"/api/profesionales/{prof.id}",
        json={
            "nombre": "Dra. Ficticia Editada",
            "matricula": "MP-9999",
            "especialidad": "Endodoncia",
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["nombre"] == "Dra. Ficticia Editada"
    assert body["matricula"] == "MP-9999"
    assert body["especialidad"] == "Endodoncia"
    db_session.expire_all()
    fila = db_session.get(Profesional, prof.id)
    assert (fila.nombre, fila.matricula, fila.especialidad) == (
        "Dra. Ficticia Editada",
        "MP-9999",
        "Endodoncia",
    )


def _request_inexistente(client, metodo, prof_id):
    if metodo == "put":
        return client.put(f"/api/profesionales/{prof_id}", json={"nombre": "X"})
    if metodo == "delete":
        return client.delete(f"/api/profesionales/{prof_id}")
    return client.put(f"/api/profesionales/{prof_id}", json={"activo": True})


@pytest.mark.parametrize("metodo", ["put", "delete", "put_activo"])
def test_edicion_profesional_inexistente_404(client, db_session, metodo):
    """# AC AP-R2/R3: id inexistente → 404 en edición, baja y reactivación."""
    _admin(client, db_session)
    resp = _request_inexistente(client, metodo, uuid4())
    assert resp.status_code == 404


@pytest.mark.parametrize("metodo", ["put", "delete", "put_activo"])
def test_baja_profesional_inexistente_404(client, db_session, metodo):
    """# AC AP-R3: baja/reactivación de id inexistente → 404."""
    _admin(client, db_session)
    resp = _request_inexistente(client, metodo, uuid4())
    assert resp.status_code == 404
    assert "No encontrado" in resp.text


# --- §3 baja lógica e idempotencia --------------------------------------


def test_baja_profesional_activo_false_conserva_historial(client, db_session):
    """# AC AP-R3: DELETE → `activo=false` y estados/inicio/duración intactos."""
    from app.models.profesional import Profesional
    from app.models.turno import Turno, TurnoEstado

    prof = _prof(db_session)
    turnos = []
    for i, estado in enumerate(
        [TurnoEstado.atendido, TurnoEstado.ausente, TurnoEstado.cancelado]
    ):
        turnos.append(
            _turno(
                db_session,
                prof,
                estado=estado,
                inicio=datetime(2026, 9, 7, 13 + i, 0, tzinfo=UTC),
            )
        )
    antes = {t.id: (t.estado, t.inicio, t.fin, t.duracion_min) for t in turnos}
    _admin(client, db_session)

    resp = client.delete(f"/api/profesionales/{prof.id}")

    assert resp.status_code == 200, resp.text
    assert resp.json()["activo"] is False
    db_session.expire_all()
    fila = db_session.get(Profesional, prof.id)
    assert fila is not None
    assert fila.activo is False
    for turno_id, esperado in antes.items():
        t = db_session.get(Turno, turno_id)
        assert (t.estado, t.inicio, t.fin, t.duracion_min) == esperado


@pytest.mark.parametrize("estado", ["reservado", "confirmado"])
def test_baja_profesional_turno_futuro_200_turno_intacto(
    client, db_session, estado
):
    """# AC AP-R3: turno futuro no bloquea la baja (sin 409) y queda intacto."""
    from app.models.notificacion import Notificacion
    from app.models.turno import Turno, TurnoEstado

    prof = _prof(db_session)
    turno = _turno(db_session, prof, estado=TurnoEstado(estado))
    antes = (turno.estado, turno.inicio, turno.fin, turno.duracion_min)
    _admin(client, db_session)

    resp = client.delete(f"/api/profesionales/{prof.id}")

    assert resp.status_code == 200, resp.text
    assert resp.json()["activo"] is False
    db_session.expire_all()
    fila = db_session.get(Turno, turno.id)
    assert (fila.estado, fila.inicio, fila.fin, fila.duracion_min) == antes
    assert (
        db_session.query(Notificacion)
        .filter(Notificacion.turno_id == turno.id)
        .count()
        == 0
    )


def test_baja_profesional_turnos_futuros_gestionables_por_staff(
    client, db_session
):
    """# AC AP-R3: la agenda staff sigue mostrando y cancelando turnos futuros."""
    from app.models.turno import Turno, TurnoEstado

    prof = _prof(db_session)
    turno = _turno(db_session, prof, estado=TurnoEstado.reservado)
    _admin(client, db_session)
    assert client.delete(f"/api/profesionales/{prof.id}").status_code == 200
    client.cookies.clear()

    staff_email = "recepcion.ficticia@cattaneo.test"
    _staff(db_session, StaffRol.recepcion, staff_email)
    _login(client, staff_email)

    agenda = client.get(
        f"/api/profesionales/{prof.id}/agenda",
        params={"vista": "dia", "fecha": "2026-12-07"},
    )
    assert agenda.status_code == 200, agenda.text
    franjas = agenda.json()["dias"][0]["franjas"]
    assert any(f.get("turno_id") == str(turno.id) for f in franjas)

    cancel = client.request("DELETE", f"/api/turnos/{turno.id}", json={})
    assert cancel.status_code == 200, cancel.text
    db_session.expire_all()
    assert db_session.get(Turno, turno.id).estado == TurnoEstado.cancelado


def test_baja_profesional_sale_catalogo_publico_y_alta_reserva(
    client, db_session
):
    """# AC AP-R3/R4: baja lo saca del catálogo; reservar da 404 (C-05)."""
    from app.models.turno import Turno, TurnoEstado

    prof = _prof(db_session)
    turno = _turno(db_session, prof, estado=TurnoEstado.reservado)
    _admin(client, db_session)
    assert client.delete(f"/api/profesionales/{prof.id}").status_code == 200
    client.cookies.clear()

    items = client.get("/api/profesionales").json()["items"]
    assert str(prof.id) not in {p["id"] for p in items}

    resp = client.post(
        "/api/turnos",
        json={
            "profesional_id": str(prof.id),
            "inicio": "2026-12-07T15:00:00-03:00",
            "paciente": {
                "nombre": "Paciente Baja Ficticio",
                "dni": "30999077",
                "telefono": "+5491100000077",
                "obra_social": "OS Ficticia",
                "email": "baja@cattaneo.test",
            },
        },
    )
    assert resp.status_code == 404, resp.text
    db_session.expire_all()
    assert db_session.get(Turno, turno.id).estado == TurnoEstado.reservado


def test_put_profesional_activo_false_misma_semantica_que_delete(
    client, db_session
):
    """# AC AP-R3: `PUT activo=false` no borra filas dependientes."""
    from app.models.bloqueo import Bloqueo
    from app.models.disponibilidad import Disponibilidad
    from app.models.profesional import Profesional
    from app.models.turno import Turno

    prof = _prof(db_session)
    _turno(db_session, prof)
    _agregar_agenda_dependientes(db_session, prof.id)
    _admin(client, db_session)

    resp = client.put(f"/api/profesionales/{prof.id}", json={"activo": False})

    assert resp.status_code == 200, resp.text
    assert resp.json()["activo"] is False
    db_session.expire_all()
    assert db_session.get(Profesional, prof.id).activo is False
    assert _count(db_session, Turno, prof.id) == 1
    assert _count(db_session, Disponibilidad, prof.id) == 1
    assert _count(db_session, Bloqueo, prof.id) == 1


def test_baja_profesional_repetida_200_idempotente(client, db_session):
    """# AC AP-R3: DELETE y `PUT activo=false` repetidos → 200 idempotente."""
    from app.models.bloqueo import Bloqueo
    from app.models.disponibilidad import Disponibilidad
    from app.models.profesional import Profesional
    from app.models.turno import Turno

    prof = _prof(db_session, activo=False)
    turno = _turno(db_session, prof)
    antes = (turno.estado, turno.inicio, turno.duracion_min)
    _agregar_agenda_dependientes(db_session, prof.id)
    _admin(client, db_session)

    una = client.delete(f"/api/profesionales/{prof.id}")
    dos = client.put(f"/api/profesionales/{prof.id}", json={"activo": False})

    assert una.status_code == 200, una.text
    assert dos.status_code == 200, dos.text
    assert una.json()["activo"] is False
    assert dos.json()["activo"] is False
    db_session.expire_all()
    assert db_session.get(Profesional, prof.id).activo is False
    fila = db_session.get(Turno, turno.id)
    assert (fila.estado, fila.inicio, fila.duracion_min) == antes
    assert _count(db_session, Disponibilidad, prof.id) == 1
    assert _count(db_session, Bloqueo, prof.id) == 1


def test_baja_profesional_no_borra_filas_dependientes(client, db_session):
    """# AC AP-R3: DELETE lógico conserva turnos, disponibilidad y bloqueos."""
    from app.models.bloqueo import Bloqueo
    from app.models.disponibilidad import Disponibilidad
    from app.models.profesional import Profesional
    from app.models.turno import Turno

    prof = _prof(db_session)
    _turno(db_session, prof)
    _agregar_agenda_dependientes(db_session, prof.id)
    _admin(client, db_session)

    assert client.delete(f"/api/profesionales/{prof.id}").status_code == 200

    db_session.expire_all()
    assert db_session.get(Profesional, prof.id) is not None
    assert _count(db_session, Turno, prof.id) == 1
    assert _count(db_session, Disponibilidad, prof.id) == 1
    assert _count(db_session, Bloqueo, prof.id) == 1


def test_baja_profesional_parametro_fisico_400(client, db_session):
    """# AC AP-R3: `?fisico=true` → 400 en `fisico`, sin baja."""
    from app.models.profesional import Profesional

    prof = _prof(db_session)
    _admin(client, db_session)

    resp = client.delete(
        f"/api/profesionales/{prof.id}", params={"fisico": "true"}
    )

    assert resp.status_code == 400, resp.text
    assert "fisico" in _campos(resp.json()["detail"])
    db_session.expire_all()
    assert db_session.get(Profesional, prof.id).activo is True


# --- §3.8 concurrencia baja vs reserva (PG real, sin 500) ---------------

NOW_CONC = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


def _turno_create(prof_id):
    from app.modules.turnos.schemas import PacienteIn, TurnoCreate

    return TurnoCreate(
        profesional_id=prof_id,
        inicio=datetime(2026, 10, 19, 15, 0, tzinfo=UTC),
        paciente=PacienteIn(
            nombre="Paciente Concurrente Ficticio",
            dni="30999099",
            telefono="+5491100000099",
            obra_social="OS Ficticia",
            email="concurrente@cattaneo.test",
        ),
    )


def _setup_conc(test_engine):
    from sqlalchemy.orm import Session

    from tests.conftest import mk_profesional

    sesion = Session(bind=test_engine)
    try:
        prof = mk_profesional(sesion, duracion_default_min=30)
        _agregar_agenda_dependientes(sesion, prof.id)
        prof_id = prof.id
        sesion.commit()
        return prof_id
    finally:
        sesion.close()


def _limpiar_conc(test_engine, prof_id):
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    sesion = Session(bind=test_engine)
    try:
        sesion.execute(
            text("DELETE FROM bloqueo WHERE profesional_id = :p"), {"p": prof_id}
        )
        sesion.execute(
            text("DELETE FROM disponibilidad WHERE profesional_id = :p"),
            {"p": prof_id},
        )
        sesion.execute(
            text("DELETE FROM profesional WHERE id = :p"), {"p": prof_id}
        )
        sesion.commit()
    finally:
        sesion.close()


@pytest.mark.parametrize("orden", ["baja_primero", "reserva_primero"])
def test_baja_profesional_concurrente_con_reserva_sin_500(test_engine, orden):
    """# AC AP-R3 R6: baja vs reserva serializan por `profesional` sin 500."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    from app.modules.profesionales import service as prof_service
    from app.modules.turnos import service as turno_service

    prof_id = _setup_conc(test_engine)
    resultado: dict = {}
    try:
        conn = test_engine.connect()
        txn = conn.begin()
        sesion = Session(bind=conn)
        try:
            if orden == "baja_primero":
                prof_service._lock(sesion, prof_id)
                arrancada = threading.Event()

                def reservar():
                    from sqlalchemy.orm import Session as SessionB

                    conn_b = test_engine.connect()
                    txn_b = conn_b.begin()
                    sesion_b = SessionB(bind=conn_b)
                    try:
                        arrancada.set()
                        turno_service.reservar(
                            sesion_b,
                            _turno_create(prof_id),
                            now_provider=lambda: NOW_CONC,
                        )
                        resultado["reserva"] = 201
                    except HTTPException as exc:
                        resultado["reserva"] = exc.status_code
                    except Exception as exc:  # pragma: no cover - diagnóstico
                        resultado["reserva"] = type(exc).__name__
                    finally:
                        if txn_b.is_active:
                            txn_b.rollback()
                        sesion_b.close()
                        conn_b.close()

                hilo = threading.Thread(target=reservar)
                hilo.start()
                assert arrancada.wait(timeout=5)
                threading.Event().wait(0.5)
                assert hilo.is_alive(), "la reserva no esperó el lock de baja"
                baja = prof_service.dar_de_baja(sesion, prof_id)
                txn.commit()
                hilo.join(timeout=15)
                assert not hilo.is_alive()
                assert baja["activo"] is False
                assert resultado["reserva"] == 404, resultado
            else:
                arrancada = threading.Event()
                liberar = threading.Event()

                def reservar_y_soltar():
                    from sqlalchemy.orm import Session as SessionB

                    conn_b = test_engine.connect()
                    txn_b = conn_b.begin()
                    sesion_b = SessionB(bind=conn_b)
                    try:
                        turno_service.reservar(
                            sesion_b,
                            _turno_create(prof_id),
                            now_provider=lambda: NOW_CONC,
                        )
                        resultado["reserva"] = 201
                    except HTTPException as exc:
                        resultado["reserva"] = exc.status_code
                    except Exception as exc:  # pragma: no cover - diagnóstico
                        resultado["reserva"] = type(exc).__name__
                    finally:
                        arrancada.set()
                        liberar.wait(timeout=15)
                        if txn_b.is_active:
                            txn_b.rollback()
                        sesion_b.close()
                        conn_b.close()

                def baja_luego():
                    try:
                        prof_service.dar_de_baja(sesion, prof_id)
                        resultado["baja"] = 200
                    except Exception as exc:  # pragma: no cover - diagnóstico
                        resultado["baja"] = type(exc).__name__

                hilo_reserva = threading.Thread(target=reservar_y_soltar)
                hilo_reserva.start()
                assert arrancada.wait(timeout=10)
                hilo_baja = threading.Thread(target=baja_luego)
                hilo_baja.start()
                threading.Event().wait(0.5)
                assert hilo_baja.is_alive(), "la baja no esperó el lock de reserva"
                liberar.set()
                hilo_baja.join(timeout=15)
                hilo_reserva.join(timeout=15)
                assert not hilo_baja.is_alive()
                assert not hilo_reserva.is_alive()
                txn.commit()
                assert resultado["reserva"] == 201, resultado
                assert resultado["baja"] == 200, resultado
        finally:
            if txn.is_active:
                txn.rollback()
            sesion.close()
            conn.close()

        verificacion = Session(bind=test_engine)
        try:
            turnos = verificacion.execute(
                text("SELECT count(*) FROM turno WHERE profesional_id = :p"),
                {"p": prof_id},
            ).scalar_one()
            activo = verificacion.execute(
                text("SELECT activo FROM profesional WHERE id = :p"),
                {"p": prof_id},
            ).scalar_one()
        finally:
            verificacion.close()
        assert turnos == 0, "sin turnos huérfanos de la rama perdedora"
        assert activo is False
        assert 500 not in resultado.values()
    finally:
        _limpiar_conc(test_engine, prof_id)


# --- §4 listado admin, reactivación y RBAC ------------------------------


def test_listado_admin_incluye_inactivos(client, db_session):
    """# AC AP-R4: `incluir_inactivos=true` (admin) devuelve activos e inactivos."""
    activo = _prof(db_session)
    inactivo = _prof(db_session, activo=False)
    _admin(client, db_session)

    resp = client.get(
        "/api/profesionales", params={"incluir_inactivos": "true"}
    )

    assert resp.status_code == 200, resp.text
    items = {p["id"]: p for p in resp.json()["items"]}
    assert {str(activo.id), str(inactivo.id)} <= set(items)
    assert items[str(activo.id)]["activo"] is True
    assert items[str(inactivo.id)]["activo"] is False


def test_listado_publico_solo_activos_no_regresion(client, db_session):
    """# AC AP-R4/agenda: sin sesión ni flag, keyset solo activos con limit/cursor."""
    activo1 = _prof(db_session)
    activo2 = _prof(db_session)
    inactivo = _prof(db_session, activo=False)

    vistos: list[str] = []
    cursor = None
    for _ in range(5):
        params: dict = {"limit": 1}
        if cursor is not None:
            params["cursor"] = cursor
        resp = client.get("/api/profesionales", params=params)
        assert resp.status_code == 200, resp.text
        cuerpo = resp.json()
        vistos.extend(p["id"] for p in cuerpo["items"])
        cursor = cuerpo["next_cursor"]
        if cursor is None:
            break

    assert {str(activo1.id), str(activo2.id)} <= set(vistos)
    assert str(inactivo.id) not in set(vistos)


@pytest.mark.parametrize("caso", ["sin_cookie", "vencida", "corrupta"])
def test_listado_publico_cookie_invalida_200(client, db_session, caso):
    """# AC AP-R4 H-03: sin cookie / vencida / corrupta el listado público es 200."""
    from app.core.config import get_settings
    from app.core.security import create_session_token

    _prof(db_session)

    if caso == "sin_cookie":
        resp = client.get("/api/profesionales")
    elif caso == "vencida":
        token = create_session_token(
            user_id=str(uuid4()),
            rol="admin",
            profesional_id=None,
            secret=get_settings().SECRET_KEY,
            lifetime_h=-1,
        )
        client.cookies.set("session", token)
        resp = client.get("/api/profesionales")
    else:
        resp = client.get(
            "/api/profesionales", headers={"Cookie": "session=no-es-un-jwt"}
        )

    assert resp.status_code == 200, resp.text


def test_listado_publico_columnas_sin_activo(client, db_session):
    """# AC AP-R4: la rama pública trae exactamente las columnas sin `activo`."""
    _prof(db_session)

    items = client.get("/api/profesionales").json()["items"]

    assert items
    columnas = {
        "id",
        "nombre",
        "especialidad",
        "matricula",
        "duracion_default_min",
        "ultima_actualizacion",
    }
    assert all(set(p) == columnas for p in items)


@pytest.mark.parametrize("rol", [StaffRol.recepcion, StaffRol.odontologo])
def test_listado_incluir_inactivos_recepcion_odontologo_403(
    client, db_session, rol
):
    """# AC AP-R4/R5: flag con sesión no admin → 403 genérico."""
    link = _prof(db_session) if rol is StaffRol.odontologo else None
    email = f"{rol.value}.listado@cattaneo.test"
    _staff(db_session, rol, email, profesional_id=link.id if link else None)
    _login(client, email)

    resp = client.get(
        "/api/profesionales", params={"incluir_inactivos": "true"}
    )

    assert resp.status_code == 403
    assert "activo" not in resp.text


def test_listado_incluir_inactivos_sin_sesion_401(client, db_session):
    """# AC AP-R4/R5: flag sin sesión → 401 (no degrada a público)."""
    _prof(db_session)

    resp = client.get(
        "/api/profesionales", params={"incluir_inactivos": "true"}
    )

    assert resp.status_code == 401


def test_reactivacion_profesional_200_aparece_publico(client, db_session):
    """# AC AP-R5: `PUT activo=true` reactiva y vuelve al catálogo público."""
    from app.models.profesional import Profesional

    prof = _prof(db_session, activo=False)
    _admin(client, db_session)

    resp = client.put(f"/api/profesionales/{prof.id}", json={"activo": True})

    assert resp.status_code == 200, resp.text
    assert resp.json()["activo"] is True
    db_session.expire_all()
    assert db_session.get(Profesional, prof.id).activo is True
    client.cookies.clear()
    ids = {p["id"] for p in client.get("/api/profesionales").json()["items"]}
    assert str(prof.id) in ids


def test_reactivacion_profesional_ya_activo_200(client, db_session):
    """# AC AP-R5: reactivar uno ya activo → 200 idempotente."""
    prof = _prof(db_session)
    _admin(client, db_session)

    resp = client.put(f"/api/profesionales/{prof.id}", json={"activo": True})

    assert resp.status_code == 200, resp.text
    assert resp.json()["activo"] is True


@pytest.mark.parametrize("rol", [StaffRol.recepcion, StaffRol.odontologo])
def test_profesionales_escrituras_recepcion_odontologo_403(
    client, db_session, rol
):
    """# AC AP-R5: POST/PUT/DELETE/GET-admin con sesión no admin → 403."""
    from app.models.profesional import Profesional

    link = _prof(db_session) if rol is StaffRol.odontologo else None
    objetivo = _prof(db_session)
    email = f"{rol.value}.escrituras@cattaneo.test"
    _staff(db_session, rol, email, profesional_id=link.id if link else None)
    _login(client, email)

    alta = client.post("/api/profesionales", json={"nombre": "Dra. No Permitida"})
    edicion = client.put(
        f"/api/profesionales/{objetivo.id}", json={"nombre": "Nombre Alterado"}
    )
    baja = client.delete(f"/api/profesionales/{objetivo.id}")
    listado = client.get(
        "/api/profesionales", params={"incluir_inactivos": "true"}
    )

    for resp in (alta, edicion, baja, listado):
        assert resp.status_code == 403, resp.text
    db_session.expire_all()
    assert db_session.get(Profesional, objetivo.id).activo is True
    assert db_session.get(Profesional, objetivo.id).nombre == objetivo.nombre


def test_profesionales_escrituras_sin_sesion_401(client, db_session):
    """# AC AP-R5: POST/PUT/DELETE sin sesión → 401 sin cambios."""
    from app.models.profesional import Profesional

    prof = _prof(db_session)

    alta = client.post("/api/profesionales", json={"nombre": "Dra. Anónima"})
    edicion = client.put(
        f"/api/profesionales/{prof.id}", json={"nombre": "Nombre Anónimo"}
    )
    baja = client.delete(f"/api/profesionales/{prof.id}")

    for resp in (alta, edicion, baja):
        assert resp.status_code == 401, resp.text
    db_session.expire_all()
    fila = db_session.get(Profesional, prof.id)
    assert fila.activo is True
    assert fila.nombre == prof.nombre


