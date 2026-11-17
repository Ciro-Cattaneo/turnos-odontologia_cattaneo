"""Operación staff de turnos (C-07; capa API/DB real y concurrencia).

# AC recepcion-turnos (R1-R9, 79 escenarios) + delta notificaciones-mail.
# Mocks solo en bordes (reloj fijo, fallo simulado de encolado); persistencia
# contra Postgres real (`db_session`/`test_engine`). Datos ficticios `.test`
# y DNI sintéticos (regla dura 12).
"""

import threading
import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
NOW = datetime(2026, 10, 19, 8, 0, tzinfo=TZ)
PASSWORD = "password-ficticia-1"

RECEPCION = "recepcion@ficticio.test"
ADMIN = "admin@ficticio.test"
ODONTO = "odonto@ficticio.test"


@pytest.fixture
def client(db_session):
    """TestClient https contra PG real con rollback + reloj fijo (D-14)."""
    from app.core import ratelimit
    from app.db.session import get_db
    from app.main import app
    from app.modules.turnos.router import get_now_provider

    ratelimit.reset()
    ratelimit.reset_public()
    original = ratelimit.LOGIN_LIMIT
    ratelimit.LOGIN_LIMIT = 1000

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    app.dependency_overrides[get_now_provider] = lambda: lambda: NOW
    with TestClient(app, base_url="https://testserver") as c:
        yield c
    app.dependency_overrides.clear()
    ratelimit.LOGIN_LIMIT = original


@pytest.fixture
def staff(db_session):
    """Profesionales y usuarios ficticios por rol (odontólogo ligado a P1)."""
    from app.models.usuario_staff import StaffRol
    from tests.conftest import mk_profesional
    from tests.test_auth_login import mk_staff

    p1 = mk_profesional(db_session)
    p2 = mk_profesional(db_session)
    _ventana(db_session, p1.id)
    recepcion = mk_staff(db_session, RECEPCION, PASSWORD)
    admin = mk_staff(db_session, ADMIN, PASSWORD, rol=StaffRol.admin)
    odonto = mk_staff(
        db_session,
        ODONTO,
        PASSWORD,
        rol=StaffRol.odontologo,
        profesional_id=p1.id,
    )
    return {
        "p1": p1,
        "p2": p2,
        "users": {"recepcion": recepcion, "admin": admin, "odonto": odonto},
    }


def _login(client, email=RECEPCION):
    response = client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200


def _delete(client, url, **kwargs):
    """`httpx.delete` no acepta `json`; el body va por `request`."""
    return client.request("DELETE", url, **kwargs)


def _prof(db_session, duracion=30, activo=True):
    from tests.conftest import mk_profesional

    return mk_profesional(db_session, duracion_default_min=duracion, activo=activo)


def _ventana(db_session, prof_id, desde=9, hasta=17, dia=0):
    from app.models.disponibilidad import Disponibilidad

    db_session.add(
        Disponibilidad(
            profesional_id=prof_id,
            dia_semana=dia,
            hora_desde=time(desde, 0),
            hora_hasta=time(hasta, 0),
            vigente_desde=date(2026, 1, 1),
            vigente_hasta=date(2026, 12, 31),
        )
    )
    db_session.flush()


def _local(hora, dia=19):
    return datetime(2026, 10, dia, hora, 0, tzinfo=TZ)


def _turno(
    db_session,
    prof,
    pac,
    *,
    hora=12,
    duracion=30,
    estado="reservado",
    dia=19,
    origen="online",
):
    from app.models.turno import TurnoEstado, TurnoOrigen
    from tests.conftest import mk_turno

    inicio = _local(hora, dia).astimezone(UTC)
    return mk_turno(
        db_session,
        prof.id,
        pac.id,
        inicio=inicio,
        fin=inicio + timedelta(minutes=duracion),
        estado=TurnoEstado(estado),
        origen=TurnoOrigen(origen),
    )


def _paciente(db_session, dni=None, **kw):
    from tests.conftest import mk_paciente

    pac = mk_paciente(db_session, **kw)
    if dni is not None:
        pac.dni = dni
        db_session.flush()
    return pac


def _escenario(db_session, *, estado="reservado", hora=12, duracion=30, dia=19):
    prof = _prof(db_session, duracion=30)
    _ventana(db_session, prof.id)
    pac = _paciente(db_session, dni=f"{uuid.uuid4().int % (9 * 10**7) + 10**7:08d}")
    turno = _turno(
        db_session,
        prof,
        pac,
        hora=hora,
        duracion=duracion,
        estado=estado,
        dia=dia,
    )
    return prof, pac, turno


def _body_staff(prof_id, inicio=None, **over):
    body = {
        "profesional_id": str(prof_id),
        "inicio": (inicio or _local(10)).isoformat(),
        "origen": "recepcion",
        "paciente": {
            "nombre": "Paciente Ficticio Staff",
            "dni": "30999123",
            "telefono": "+5491100000123",
            "obra_social": "OS Ficticia",
            "email": "paciente.staff@ficticio.test",
        },
    }
    body.update(over)
    return body


def _body_publico(prof_id, inicio=None, **over):
    body = _body_staff(prof_id, inicio=inicio, **over)
    body.pop("origen", None)
    return body


def _auditoria(db_session, turno_id):
    from app.models.auditoria import AuditoriaTurno

    return (
        db_session.query(AuditoriaTurno)
        .filter(AuditoriaTurno.turno_id == turno_id)
        .order_by(AuditoriaTurno.created_at, AuditoriaTurno.id)
        .all()
    )


def _notifs(db_session, turno_id):
    from app.models.notificacion import Notificacion

    return (
        db_session.query(Notificacion)
        .filter(Notificacion.turno_id == turno_id)
        .order_by(Notificacion.tipo)
        .all()
    )


def _estado(db_session, turno):
    from app.models.turno import Turno

    db_session.expire_all()
    return db_session.query(Turno).filter(Turno.id == turno.id).one().estado


# --- §1 Contratos y despacho por sesión ------------------------------------


def test_alta_staff_body_incompleto_400_por_campo(client, db_session, staff):
    """# AC R1 S6: paciente vacío → 400 por cada campo y sin turno."""
    from app.models.turno import Turno

    _login(client)
    body = _body_staff(staff["p1"].id, paciente={})

    resp = client.post("/api/turnos", json=body)

    assert resp.status_code == 400
    campos = {d["campo"] for d in resp.json()["detail"]}
    assert {
        "paciente.nombre",
        "paciente.dni",
        "paciente.telefono",
        "paciente.obra_social",
        "paciente.email",
    } <= campos
    assert db_session.query(Turno).count() == 0


@pytest.mark.parametrize("origen", ["ausente", "online"], ids=["ausente", "online"])
def test_alta_staff_origen_ausente_o_invalido_400(client, db_session, staff, origen):
    """# AC R1 S10: `origen` obligatorio y exactamente `recepcion`."""
    from app.models.turno import Turno

    _login(client)
    body = _body_staff(staff["p1"].id)
    if origen == "ausente":
        body.pop("origen")
    else:
        body["origen"] = origen

    resp = client.post("/api/turnos", json=body)

    assert resp.status_code == 400
    assert any(d["campo"] == "origen" for d in resp.json()["detail"])
    assert db_session.query(Turno).count() == 0


def test_alta_staff_respuesta_sin_token(client, db_session, staff):
    """# AC R1 S2: la respuesta staff no expone token ni cancel_url."""
    _login(client)

    resp = client.post(
        "/api/turnos", json=_body_staff(staff["p1"].id, inicio=_local(10))
    )

    assert resp.status_code == 201
    cuerpo = resp.json()
    assert set(cuerpo) == {
        "id",
        "estado",
        "inicio",
        "fin",
        "duracion_min",
        "notificaciones_encoladas",
    }
    assert "token_cancelacion" not in cuerpo
    assert "cancel_url" not in cuerpo


def test_alta_staff_sin_sesion_origen_400_no_regresion(client, db_session, staff):
    """# AC R1 S3: sin sesión, `origen` en el body público es 400 por campo."""
    resp = client.post(
        "/api/turnos", json=_body_staff(staff["p1"].id, inicio=_local(10))
    )

    assert resp.status_code == 400
    assert any(d["campo"] == "origen" for d in resp.json()["detail"])


def test_alta_staff_sin_sesion_body_publico_sigue_online(client, db_session, staff):
    """# AC R1 S4: sin sesión el contrato público crea `origen=online`."""
    from app.models.auditoria import AuditoriaTurno
    from app.models.turno import Turno, TurnoOrigen

    resp = client.post(
        "/api/turnos", json=_body_publico(staff["p1"].id, inicio=_local(10))
    )

    assert resp.status_code == 201
    turno = db_session.query(Turno).filter(Turno.id == resp.json()["id"]).one()
    assert turno.origen == TurnoOrigen.online
    auditoria = (
        db_session.query(AuditoriaTurno)
        .filter(AuditoriaTurno.turno_id == turno.id)
        .one()
    )
    assert auditoria.actor_id is None


def test_alta_staff_odontologo_403(client, db_session, staff):
    """# AC R1 S5: el odontólogo no puede crear turnos."""
    from app.models.paciente import Paciente
    from app.models.turno import Turno

    _login(client, ODONTO)
    resp = client.post(
        "/api/turnos", json=_body_staff(staff["p1"].id, inicio=_local(10))
    )

    assert resp.status_code == 403
    assert db_session.query(Turno).count() == 0
    assert db_session.query(Paciente).count() == 0


def test_alta_staff_recepcion_201_origen_recepcion_actor(client, db_session, staff):
    """# AC R1 S1: 201 con origen recepcion, token persistido y auditoría."""
    from app.models.auditoria import AuditoriaTurno
    from app.models.paciente import Paciente
    from app.models.turno import Turno, TurnoEstado, TurnoOrigen

    _login(client)
    resp = client.post(
        "/api/turnos", json=_body_staff(staff["p1"].id, inicio=_local(10))
    )

    assert resp.status_code == 201
    turno = db_session.query(Turno).filter(Turno.id == resp.json()["id"]).one()
    assert turno.estado == TurnoEstado.reservado
    assert turno.origen == TurnoOrigen.recepcion
    assert turno.token_cancelacion is not None
    assert db_session.query(Paciente).filter(Paciente.dni == "30999123").count() == 1
    assert resp.json()["notificaciones_encoladas"] is True
    auditoria = (
        db_session.query(AuditoriaTurno)
        .filter(AuditoriaTurno.turno_id == turno.id)
        .one()
    )
    assert auditoria.accion == "crear"
    assert auditoria.actor_id == staff["users"]["recepcion"].id
    assert auditoria.detalle["origen"] == "recepcion"
    assert auditoria.detalle["actor"]["rol"] == "recepcion"


def test_alta_staff_profesional_inexistente_o_inactivo_404(client, db_session, staff):
    """# AC R1 S8: profesional inexistente o inactivo → 404 sin crear."""
    from app.models.turno import Turno

    inactivo = _prof(db_session, activo=False)
    _login(client)

    for prof_id in (uuid.uuid4(), inactivo.id):
        resp = client.post("/api/turnos", json=_body_staff(prof_id, inicio=_local(10)))
        assert resp.status_code == 404
    assert db_session.query(Turno).count() == 0


def test_alta_staff_slot_ocupado_409_alternativos_sin_paciente(
    client, db_session, staff
):
    """# AC R1 S7: destino ocupado → 409 con alternativos, sin paciente."""
    from app.models.paciente import Paciente
    from app.models.turno import Turno

    pac = _paciente(db_session)
    _turno(db_session, staff["p1"], pac, hora=13)
    _login(client)
    dni_nuevo = "30888777"

    resp = client.post(
        "/api/turnos",
        json=_body_staff(
            staff["p1"].id,
            inicio=_local(13),
            paciente={
                "nombre": "Paciente Nuevo Staff",
                "dni": dni_nuevo,
                "telefono": "+5491100000300",
                "obra_social": "OS Ficticia",
                "email": "nuevo.staff@ficticio.test",
            },
        ),
    )

    assert resp.status_code == 409
    assert resp.json()["detail"]["codigo"] == "slot_ocupado"
    assert resp.json()["detail"]["alternativos"]
    assert db_session.query(Paciente).filter(Paciente.dni == dni_nuevo).count() == 0
    assert db_session.query(Turno).count() == 1
    assert _auditoria(db_session, db_session.query(Turno).one().id) == []


def test_alta_staff_encolado_falla_201_notificaciones_false(
    client, db_session, staff, monkeypatch
):
    """# AC R1 S9: fallo del encolado no revierte turno, paciente ni auditoría."""
    from app.models.auditoria import AuditoriaTurno
    from app.models.paciente import Paciente
    from app.models.turno import Turno
    from app.modules.turnos import service

    class _BoomNotificacion:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("fallo simulado de encolado")

    monkeypatch.setattr(service, "Notificacion", _BoomNotificacion)
    _login(client)

    resp = client.post(
        "/api/turnos", json=_body_staff(staff["p1"].id, inicio=_local(10))
    )

    assert resp.status_code == 201
    assert resp.json()["notificaciones_encoladas"] is False
    turno = db_session.query(Turno).filter(Turno.id == resp.json()["id"]).one()
    assert db_session.query(Paciente).filter(Paciente.id == turno.paciente_id).one()
    auditoria = (
        db_session.query(AuditoriaTurno)
        .filter(AuditoriaTurno.turno_id == turno.id)
        .one()
    )
    assert auditoria.detalle["notificaciones_encoladas"] is False


def test_reprogramar_body_sin_campos_400(client, db_session, staff):
    """# AC R2: body sin `inicio` ni `duracion_min` → 400 en `body`."""
    _, _, turno = _escenario(db_session)
    _login(client)

    resp = client.put(f"/api/turnos/{turno.id}", json={})

    assert resp.status_code == 400
    assert any(d["campo"] == "body" for d in resp.json()["detail"])


def test_reprogramar_campo_extra_400(client, db_session, staff):
    """# AC R2 S10: `profesional_id` no declarado → 400 por campo."""
    prof, _, turno = _escenario(db_session)
    _login(client)

    resp = client.put(
        f"/api/turnos/{turno.id}",
        json={"inicio": _local(13).isoformat(), "profesional_id": str(prof.id)},
    )

    assert resp.status_code == 400
    assert any(d["campo"] == "profesional_id" for d in resp.json()["detail"])


def test_correccion_paciente_body_sin_campos_400(client, db_session, staff):
    """# AC R4 S6: body `{}` → 400 en `body`."""
    _, _, turno = _escenario(db_session)
    _login(client)

    resp = client.put(f"/api/turnos/{turno.id}/paciente", json={})

    assert resp.status_code == 400
    assert any(d["campo"] == "body" for d in resp.json()["detail"])


@pytest.mark.parametrize("campo", ["nombre", "email"])
def test_correccion_paciente_nombre_email_400(client, db_session, staff, campo):
    """# AC R4 S7: `nombre`/`email` fuera del contrato → 400 por campo."""
    _, _, turno = _escenario(db_session)
    _login(client)

    resp = client.put(
        f"/api/turnos/{turno.id}/paciente", json={campo: "valor ficticio"}
    )

    assert resp.status_code == 400
    assert any(d["campo"] == campo for d in resp.json()["detail"])


def test_patch_estado_desconocido_400(client, db_session, staff):
    """# AC R5 S8: `estado` desconocido → 400 en `estado`."""
    _, _, turno = _escenario(db_session)
    _login(client)

    resp = client.patch(f"/api/turnos/{turno.id}/estado", json={"estado": "en_espera"})

    assert resp.status_code == 400
    assert any(d["campo"] == "estado" for d in resp.json()["detail"])


def test_ficha_query_desconocida_400(client, db_session, staff):
    """# AC R6 S7: query desconocida → 400 en ese campo."""
    _, _, turno = _escenario(db_session)
    _login(client)

    resp = client.get(f"/api/turnos/{turno.id}?orden=asc")

    assert resp.status_code == 400
    assert any(d["campo"] == "orden" for d in resp.json()["detail"])


def test_ficha_cursor_invalido_400(client, db_session, staff):
    """# AC R6 S8: cursor de historial inválido → 400 por campo."""
    _, _, turno = _escenario(db_session)
    _login(client)

    resp = client.get(
        f"/api/turnos/{turno.id}", params={"historial_cursor": "no-es-un-cursor"}
    )

    assert resp.status_code == 400
    assert any(d["campo"] == "historial_cursor" for d in resp.json()["detail"])


@pytest.mark.parametrize("limite", [0, 101])
def test_ficha_historial_limit_fuera_rango_400(client, db_session, staff, limite):
    """# AC R6 S3: `historial_limit` 1–100; fuera de rango → 400."""
    _, _, turno = _escenario(db_session)
    _login(client)

    resp = client.get(f"/api/turnos/{turno.id}", params={"historial_limit": limite})

    assert resp.status_code == 400
    assert any(d["campo"] == "historial_limit" for d in resp.json()["detail"])


def test_reprogramar_inicio_pasado_400(client, db_session, staff):
    """# AC R2 S6: `inicio` anterior al reloj → 400 en `inicio`."""
    _, _, turno = _escenario(db_session)
    _login(client)

    resp = client.put(
        f"/api/turnos/{turno.id}",
        json={"inicio": (NOW - timedelta(minutes=30)).isoformat()},
    )

    assert resp.status_code == 400
    assert any(d["campo"] == "inicio" for d in resp.json()["detail"])


def test_reprogramar_inicio_sin_zona_400(client, db_session, staff):
    """# AC R2 S6: `inicio` sin offset → 400 en `inicio`."""
    _, _, turno = _escenario(db_session)
    _login(client)

    resp = client.put(
        f"/api/turnos/{turno.id}",
        json={"inicio": "2026-10-19T13:00:00"},
    )

    assert resp.status_code == 400
    assert any(d["campo"] == "inicio" for d in resp.json()["detail"])


# --- §2 Reprogramación con anti-solape -------------------------------------


def test_reprogramar_mismo_profesional_200_audita_cambios(client, db_session, staff):
    """# AC R2 S1: mueve inicio/fin conservando profesional, estado y token."""
    prof, _, turno = _escenario(db_session)
    token_previo = turno.token_cancelacion
    _login(client)

    resp = client.put(
        f"/api/turnos/{turno.id}",
        json={"inicio": _local(13).isoformat()},
    )

    assert resp.status_code == 200
    db_session.expire_all()
    actual = db_session.get(type(turno), turno.id)
    assert actual.inicio == _local(13).astimezone(UTC)
    assert actual.fin == _local(13).astimezone(UTC) + timedelta(minutes=30)
    assert actual.profesional_id == prof.id
    assert actual.estado.value == "reservado"
    assert actual.token_cancelacion == token_previo
    auditoria = _auditoria(db_session, turno.id)[-1]
    assert auditoria.accion == "reprogramar"
    assert (
        auditoria.detalle["cambios"]["inicio"]["despues"]
        == _local(13).astimezone(UTC).isoformat()
    )


def test_reprogramar_cambio_duracion_200(client, db_session, staff):
    """# AC R2 S2: `duracion_min=60` recalcula `fin` y respeta granularidad."""
    _, _, turno = _escenario(db_session, estado="confirmado", hora=9)
    _login(client)

    resp = client.put(f"/api/turnos/{turno.id}", json={"duracion_min": 60})

    assert resp.status_code == 200
    db_session.expire_all()
    actual = db_session.get(type(turno), turno.id)
    assert actual.duracion_min == 60
    assert actual.fin == actual.inicio + timedelta(minutes=60)
    auditoria = _auditoria(db_session, turno.id)[-1]
    assert auditoria.detalle["cambios"]["duracion_min"] == {
        "antes": 30,
        "despues": 60,
    }


@pytest.mark.parametrize("duracion", [0, -30, 40])
def test_reprogramar_duracion_invalida_400(client, db_session, staff, duracion):
    """# AC R2 S7: duración no positiva/múltiplo → 400 en `duracion_min`."""
    _, _, turno = _escenario(db_session)
    _login(client)

    resp = client.put(f"/api/turnos/{turno.id}", json={"duracion_min": duracion})

    assert resp.status_code == 400
    assert any(d["campo"] == "duracion_min" for d in resp.json()["detail"])


def test_reprogramar_slot_ocupado_409_sin_efectos(client, db_session, staff):
    """# AC R2 S3: destino ocupado (mismo profesional) → 409 sin efectos."""
    prof, pac, turno = _escenario(db_session, hora=12)
    _turno(db_session, prof, pac, hora=13)
    _login(client)
    antes = len(_auditoria(db_session, turno.id))

    resp = client.put(
        f"/api/turnos/{turno.id}", json={"inicio": _local(13).isoformat()}
    )

    assert resp.status_code == 409
    detalle = resp.json()["detail"]
    assert detalle["codigo"] == "slot_ocupado"
    assert detalle["alternativos"]
    assert _estado(db_session, turno).value == "reservado"
    assert len(_auditoria(db_session, turno.id)) == antes


def test_reprogramar_slot_no_disponible_409(client, db_session, staff):
    """# AC R2 S4: fuera de ventana → 409 `slot_no_disponible` sin efectos."""
    prof, _, turno = _escenario(db_session, hora=12)
    _login(client)
    antes = len(_auditoria(db_session, turno.id))

    resp = client.put(
        f"/api/turnos/{turno.id}", json={"inicio": _local(20).isoformat()}
    )

    assert resp.status_code == 409
    assert resp.json()["detail"]["codigo"] == "slot_no_disponible"
    assert _estado(db_session, turno).value == "reservado"
    assert len(_auditoria(db_session, turno.id)) == antes


@pytest.mark.parametrize("estado", ["cancelado", "atendido", "ausente"])
def test_reprogramar_turno_no_editable_422(client, db_session, staff, estado):
    """# AC R2 S5: estados cerrados no son editables."""
    _, _, turno = _escenario(db_session, estado=estado)
    _login(client)

    resp = client.put(
        f"/api/turnos/{turno.id}", json={"inicio": _local(13).isoformat()}
    )

    assert resp.status_code == 422
    assert resp.json()["detail"]["codigo"] == "turno_no_editable"


def test_reprogramar_mismos_valores_noop_200_sin_auditoria(client, db_session, staff):
    """# AC R2 S8: mismos valores → 200 no-op sin auditoría ni updated_at."""
    _, _, turno = _escenario(db_session)
    _login(client)
    antes = len(_auditoria(db_session, turno.id))
    actualizado_previo = turno.updated_at

    resp = client.put(
        f"/api/turnos/{turno.id}",
        json={
            "inicio": turno.inicio.isoformat(),
            "duracion_min": turno.duracion_min,
        },
    )

    assert resp.status_code == 200
    assert resp.json()["notificaciones_encoladas"] is False
    assert len(_auditoria(db_session, turno.id)) == antes
    db_session.expire_all()
    assert db_session.get(type(turno), turno.id).updated_at == actualizado_previo


# --- §3 Cancelación staff normal y forzada ---------------------------------


def test_cancelacion_staff_mas_3h_200_audita_cancelar(client, db_session, staff):
    """# AC R3 S1: ≥3 h → cancelado, mail y auditoría `cancelar`."""
    _, _, turno = _escenario(db_session, hora=12)  # 4 h de anticipación
    _login(client)

    resp = _delete(client, f"/api/turnos/{turno.id}", json={})

    assert resp.status_code == 200
    assert _estado(db_session, turno).value == "cancelado"
    auditoria = _auditoria(db_session, turno.id)[-1]
    assert auditoria.accion == "cancelar"
    assert auditoria.actor_id == staff["users"]["recepcion"].id
    assert auditoria.detalle["estado_nuevo"] == "cancelado"
    assert any(n.tipo.value == "cancelacion" for n in _notifs(db_session, turno.id))


def test_cancelacion_staff_mas_3h_con_motivo_audita(client, db_session, staff):
    """# AC R3 S2: motivo opcional se guarda en la auditoría."""
    _, _, turno = _escenario(db_session, hora=12)
    _login(client)

    resp = _delete(
        client,
        f"/api/turnos/{turno.id}",
        json={"motivo": "El paciente avisó por teléfono"},
    )

    assert resp.status_code == 200
    auditoria = _auditoria(db_session, turno.id)[-1]
    assert auditoria.accion == "cancelar"
    assert auditoria.detalle["motivo"] == "El paciente avisó por teléfono"


def test_cancelacion_staff_exactamente_3h_normal(client, db_session, staff):
    """# AC R3 S3: exactamente 3 h cae en la rama normal (`>=`)."""
    _, _, turno = _escenario(db_session, hora=11)  # NOW 08:00 + 3 h
    _login(client)

    resp = _delete(client, f"/api/turnos/{turno.id}", json={})

    assert resp.status_code == 200
    auditoria = _auditoria(db_session, turno.id)[-1]
    assert auditoria.accion == "cancelar"


def test_cancelacion_staff_menos_3h_con_motivo_forzar_200(client, db_session, staff):
    """# AC R3 S4: <3 h con motivo → 200 y `forzar_cancelacion`."""
    _, _, turno = _escenario(db_session, hora=10)  # 2 h
    _login(client)

    resp = _delete(
        client,
        f"/api/turnos/{turno.id}",
        json={"motivo": "El paciente no puede asistir"},
    )

    assert resp.status_code == 200
    assert _estado(db_session, turno).value == "cancelado"
    auditoria = _auditoria(db_session, turno.id)[-1]
    assert auditoria.accion == "forzar_cancelacion"
    assert auditoria.detalle["motivo"] == "El paciente no puede asistir"


def test_cancelacion_staff_menos_3h_sin_motivo_422(client, db_session, staff):
    """# AC R3 S5: <3 h sin motivo → 422 sin efectos laterales."""
    _, _, turno = _escenario(db_session, hora=10)
    _login(client)
    antes = len(_auditoria(db_session, turno.id))

    resp = _delete(client, f"/api/turnos/{turno.id}")

    assert resp.status_code == 422
    assert resp.json()["detail"]["codigo"] == "motivo_requerido"
    assert _estado(db_session, turno).value == "reservado"
    assert len(_auditoria(db_session, turno.id)) == antes
    assert not any(n.tipo.value == "cancelacion" for n in _notifs(db_session, turno.id))


@pytest.mark.parametrize("motivo", ["", "   ", "ab"])
def test_cancelacion_staff_motivo_vacio_o_corto_400(client, db_session, staff, motivo):
    """# AC R3 S6: motivo vacío o corto → 400 en `motivo`."""
    _, _, turno = _escenario(db_session, hora=10)
    _login(client)

    resp = _delete(client, f"/api/turnos/{turno.id}", json={"motivo": motivo})

    assert resp.status_code == 400
    assert any(d["campo"] == "motivo" for d in resp.json()["detail"])


def test_cancelacion_staff_token_publico_precedencia(client, db_session, staff):
    """# AC R3 S10: `?token=` ejecuta C-06 con `actor_id=NULL`."""
    _, _, turno = _escenario(db_session, hora=12)
    _login(client)

    resp = _delete(
        client,
        f"/api/turnos/{turno.id}",
        params={"token": str(turno.token_cancelacion)},
    )

    assert resp.status_code == 200
    auditoria = _auditoria(db_session, turno.id)[-1]
    assert auditoria.actor_id is None


def test_cancelacion_staff_sin_sesion_401_odontologo_403(client, db_session, staff):
    """# AC R3 S11: sin sesión 401; odontólogo 403; el turno no cambia."""
    _, _, turno = _escenario(db_session, hora=12)

    sin_sesion = _delete(
        client, f"/api/turnos/{turno.id}", json={"motivo": "motivo ficticio"}
    )
    assert sin_sesion.status_code == 401

    _login(client, ODONTO)
    ajeno = _delete(
        client, f"/api/turnos/{turno.id}", json={"motivo": "motivo ficticio"}
    )
    assert ajeno.status_code == 403
    assert _estado(db_session, turno).value == "reservado"


def test_cancelacion_staff_ya_cancelado_422(client, db_session, staff):
    """# AC R3 S7: ya cancelado → 422 `turno_ya_cancelado` sin efectos."""
    _, _, turno = _escenario(db_session, estado="cancelado")
    _login(client)
    antes = len(_auditoria(db_session, turno.id))

    resp = _delete(client, f"/api/turnos/{turno.id}", json={})

    assert resp.status_code == 422
    assert resp.json()["detail"]["codigo"] == "turno_ya_cancelado"
    assert len(_auditoria(db_session, turno.id)) == antes


@pytest.mark.parametrize("estado", ["atendido", "ausente"])
def test_cancelacion_staff_atendido_ausente_422(client, db_session, staff, estado):
    """# AC R3 S8: atendido/ausente → 422 `turno_no_cancelable`."""
    _, _, turno = _escenario(db_session, estado=estado)
    _login(client)

    resp = _delete(client, f"/api/turnos/{turno.id}", json={})

    assert resp.status_code == 422
    assert resp.json()["detail"]["codigo"] == "turno_no_cancelable"


def test_cancelacion_staff_no_borra_fila(client, db_session, staff):
    """# AC R3 S9 / duro 3: la fila sigue existiendo como `cancelado`."""
    from app.models.turno import Turno, TurnoEstado

    _, _, turno = _escenario(db_session, hora=12)
    _login(client)

    resp = _delete(client, f"/api/turnos/{turno.id}", json={})

    assert resp.status_code == 200
    fila = db_session.query(Turno).filter(Turno.id == turno.id).one()
    assert fila.estado == TurnoEstado.cancelado


def test_cancelacion_staff_body_extra_400(client, db_session, staff):
    """# AC R3 S12: clave extra (`forzar`) → 400 por campo."""
    _, _, turno = _escenario(db_session, hora=12)
    _login(client)

    resp = _delete(
        client, f"/api/turnos/{turno.id}", json={"motivo": "válido", "forzar": True}
    )

    assert resp.status_code == 400
    assert any(d["campo"] == "forzar" for d in resp.json()["detail"])


# --- §4 Corrección de datos del paciente -----------------------------------


def test_correccion_paciente_telefono_os_200_audita(client, db_session, staff):
    """# AC R4 S1: teléfono/OS nuevos persisten y auditan antes→después."""
    _, pac, turno = _escenario(db_session)
    telefono_previo = pac.telefono
    _login(client)

    resp = client.put(
        f"/api/turnos/{turno.id}/paciente",
        json={"telefono": "+5491100009999", "obra_social": "OS Nueva"},
    )

    assert resp.status_code == 200
    db_session.expire_all()
    actual = db_session.get(type(pac), pac.id)
    assert actual.telefono == "+5491100009999"
    assert actual.obra_social == "OS Nueva"
    auditoria = _auditoria(db_session, turno.id)[-1]
    assert auditoria.accion == "editar_paciente"
    assert auditoria.detalle["cambios"]["telefono"]["antes"] == telefono_previo
    assert auditoria.detalle["cambios"]["telefono"]["despues"] == ("+5491100009999")


def test_correccion_paciente_dni_duplicado_409_sin_fusion(client, db_session, staff):
    """# AC R4 S3: DNI de otro paciente → 409 sin fusionar ni auditar."""
    _, pac_a, turno = _escenario(db_session)
    pac_b = _paciente(db_session, dni="30111222")
    _login(client)
    antes = len(_auditoria(db_session, turno.id))

    resp = client.put(f"/api/turnos/{turno.id}/paciente", json={"dni": pac_b.dni})

    assert resp.status_code == 409
    assert resp.json()["detail"]["codigo"] == "dni_duplicado"
    assert len(_auditoria(db_session, turno.id)) == antes
    db_session.expire_all()
    assert db_session.get(type(pac_a), pac_a.id).dni == pac_a.dni
    assert db_session.get(type(pac_b), pac_b.id).dni == pac_b.dni


def test_correccion_paciente_mismo_dni_noop_200(client, db_session, staff):
    """# AC R4 S4: mismo DNI → 200 no-op sin auditoría ni updated_at."""
    _, pac, turno = _escenario(db_session)
    _login(client)
    antes = len(_auditoria(db_session, turno.id))
    actualizado_previo = pac.updated_at

    resp = client.put(f"/api/turnos/{turno.id}/paciente", json={"dni": pac.dni})

    assert resp.status_code == 200
    assert len(_auditoria(db_session, turno.id)) == antes
    db_session.expire_all()
    assert db_session.get(type(pac), pac.id).updated_at == actualizado_previo


@pytest.mark.parametrize("telefono", ["", "   "])
def test_correccion_paciente_campo_vacio_400(client, db_session, staff, telefono):
    """# AC R4 S5: vacío o solo espacios → 400 en `telefono`."""
    _, _, turno = _escenario(db_session)
    _login(client)

    resp = client.put(f"/api/turnos/{turno.id}/paciente", json={"telefono": telefono})

    assert resp.status_code == 400
    assert any(d["campo"] == "telefono" for d in resp.json()["detail"])


@pytest.mark.parametrize("dni", ["30ABC001", "123"])
def test_correccion_paciente_dni_formato_invalido_400(client, db_session, staff, dni):
    """# AC R4 S2: DNI con formato inválido → 400 en `dni`."""
    _, _, turno = _escenario(db_session)
    _login(client)

    resp = client.put(f"/api/turnos/{turno.id}/paciente", json={"dni": dni})

    assert resp.status_code == 400
    assert any(d["campo"] == "dni" for d in resp.json()["detail"])


def test_correccion_paciente_odontologo_403(client, db_session, staff):
    """# AC R4 S8: odontólogo no corrige datos del paciente."""
    _, pac, turno = _escenario(db_session)
    telefono_previo = pac.telefono
    _login(client, ODONTO)

    resp = client.put(
        f"/api/turnos/{turno.id}/paciente",
        json={"telefono": "+5491100007777"},
    )

    assert resp.status_code == 403
    db_session.expire_all()
    assert db_session.get(type(pac), pac.id).telefono == telefono_previo


def test_correccion_paciente_visible_en_otros_turnos(client, db_session, staff):
    """# AC R4 S9: la fila compartida refleja el cambio en todo el paciente."""
    prof, pac, turno = _escenario(db_session, hora=12)
    otro = _turno(db_session, prof, pac, hora=14)
    _login(client)

    resp = client.put(
        f"/api/turnos/{turno.id}/paciente", json={"telefono": "+5491100006666"}
    )

    assert resp.status_code == 200
    db_session.expire_all()
    primero = db_session.get(type(turno), turno.id)
    segundo = db_session.get(type(otro), otro.id)
    assert primero.paciente_id == segundo.paciente_id
    assert db_session.get(type(pac), pac.id).telefono == "+5491100006666"


def test_correccion_paciente_turno_cancelado_permitida(client, db_session, staff):
    """# AC R4 S10: corregir un turno cancelado está permitido y audita."""
    _, pac, turno = _escenario(db_session, estado="cancelado")
    _login(client)

    resp = client.put(
        f"/api/turnos/{turno.id}/paciente", json={"telefono": "+5491100005555"}
    )

    assert resp.status_code == 200
    assert _auditoria(db_session, turno.id)[-1].accion == "editar_paciente"
    db_session.expire_all()
    assert db_session.get(type(pac), pac.id).telefono == "+5491100005555"


# --- �5 Cambio de estado (RN-TU-07) ----------------------------------------


def test_patch_estado_reservado_confirmado_200(client, db_session, staff):
    """# AC R5 S1: reservado ? confirmado, 200 y auditor�a."""
    _, _, turno = _escenario(db_session)
    _login(client)

    resp = client.patch(f"/api/turnos/{turno.id}/estado", json={"estado": "confirmado"})

    assert resp.status_code == 200
    assert resp.json()["estado_previo"] == "reservado"
    assert resp.json()["estado"] == "confirmado"
    assert _estado(db_session, turno).value == "confirmado"
    auditoria = _auditoria(db_session, turno.id)[-1]
    assert auditoria.accion == "cambiar_estado"
    assert auditoria.detalle["estado_previo"] == "reservado"
    assert auditoria.detalle["estado_nuevo"] == "confirmado"


def test_patch_estado_confirmado_atendido_200(client, db_session, staff):
    """# AC R5 S2: confirmado → atendido, 200."""
    _, _, turno = _escenario(db_session, estado="confirmado")
    _login(client)

    resp = client.patch(f"/api/turnos/{turno.id}/estado", json={"estado": "atendido"})

    assert resp.status_code == 200
    assert _estado(db_session, turno).value == "atendido"


def test_patch_estado_confirmado_ausente_200(client, db_session, staff):
    """# AC R5 S3: confirmado → ausente, 200."""
    _, _, turno = _escenario(db_session, estado="confirmado")
    _login(client)

    resp = client.patch(f"/api/turnos/{turno.id}/estado", json={"estado": "ausente"})

    assert resp.status_code == 200
    assert _estado(db_session, turno).value == "ausente"


@pytest.mark.parametrize("destino", ["atendido", "ausente"])
def test_patch_estado_reservado_terminal_422(client, db_session, staff, destino):
    """# AC R5 S3: reservado ? terminal ? 422 `transicion_invalida`."""
    _, _, turno = _escenario(db_session)
    _login(client)
    antes = len(_auditoria(db_session, turno.id))

    resp = client.patch(f"/api/turnos/{turno.id}/estado", json={"estado": destino})

    assert resp.status_code == 422
    assert resp.json()["detail"]["codigo"] == "transicion_invalida"
    assert len(_auditoria(db_session, turno.id)) == antes


@pytest.mark.parametrize(
    ("estado_actual", "destino"),
    [("reservado", "reservado"), ("confirmado", "confirmado")],
)
def test_patch_estado_reservado_target_422(
    client, db_session, staff, estado_actual, destino
):
    """# AC R5 S6: volver a reservado o repetir confirmado → 422."""
    _, _, turno = _escenario(db_session, estado=estado_actual)
    _login(client)

    resp = client.patch(f"/api/turnos/{turno.id}/estado", json={"estado": destino})

    assert resp.status_code == 422
    assert resp.json()["detail"]["codigo"] == "transicion_invalida"


def test_patch_estado_cancelado_target_422(client, db_session, staff):
    """# AC R5 S5: cancelar por PATCH estado → 422."""
    _, _, turno = _escenario(db_session)
    _login(client)

    resp = client.patch(f"/api/turnos/{turno.id}/estado", json={"estado": "cancelado"})

    assert resp.status_code == 422
    assert resp.json()["detail"]["codigo"] == "transicion_invalida"


@pytest.mark.parametrize("previo", ["cancelado", "atendido", "ausente"])
def test_patch_estado_terminal_sin_transiciones_422(client, db_session, staff, previo):
    """# AC R5 S5: estados terminales no tienen transiciones salientes."""
    _, _, turno = _escenario(db_session, estado=previo)
    _login(client)
    antes = len(_auditoria(db_session, turno.id))

    resp = client.patch(f"/api/turnos/{turno.id}/estado", json={"estado": "confirmado"})

    assert resp.status_code == 422
    assert len(_auditoria(db_session, turno.id)) == antes


def test_patch_estado_odontologo_propio_200(client, db_session, staff):
    """# AC R5 S6: odont�logo propio ? reservado a confirmado permitido."""
    pac = _paciente(db_session)

    turno = _turno(db_session, staff["p1"], pac, hora=14)

    _login(client, ODONTO)

    resp = client.patch(f"/api/turnos/{turno.id}/estado", json={"estado": "confirmado"})

    assert resp.status_code == 200
    assert _estado(db_session, turno).value == "confirmado"


def test_patch_estado_odontologo_ajeno_403(client, db_session, staff):
    """# AC R5 S7: turno de otro profesional ? 403 sin auditar."""
    prof_ajeno, pac, turno = _escenario(db_session)
    _login(client, ODONTO)
    antes = len(_auditoria(db_session, turno.id))

    resp = client.patch(f"/api/turnos/{turno.id}/estado", json={"estado": "confirmado"})

    assert resp.status_code == 403
    assert len(_auditoria(db_session, turno.id)) == antes


def test_patch_estado_odontologo_ausente_403(client, db_session, staff):
    """# AC R5 S9: el odont�logo no puede marcar ausente (solo recepci�n)."""
    prof, pac, _ = _escenario(db_session)
    turno = _turno(db_session, prof, pac, hora=14, estado="confirmado")
    _login(client, ODONTO)

    resp = client.patch(f"/api/turnos/{turno.id}/estado", json={"estado": "ausente"})

    assert resp.status_code == 403
    assert _estado(db_session, turno).value == "confirmado"


def test_patch_estado_admin_hereda(client, db_session, staff):
    """# AC R5 S10: admin puede aplicar cualquier transici�n v�lida."""
    _, _, turno = _escenario(db_session)
    _login(client, ADMIN)

    resp = client.patch(f"/api/turnos/{turno.id}/estado", json={"estado": "confirmado"})

    assert resp.status_code == 200


# --- �6 Ficha staff con historial keyset -----------------------------------


def _auditoria_manual(
    db_session, turno_id, *, accion, created_at, actor_id=None, detalle=None
):
    from app.models.auditoria import AuditoriaTurno

    fila = AuditoriaTurno(
        turno_id=turno_id,
        actor_id=actor_id,
        accion=accion,
        created_at=created_at,
        detalle=detalle or {"origen": "staff"},
    )
    db_session.add(fila)
    db_session.flush()
    return fila


def test_ficha_recepcion_datos_e_historial_ascendente(client, db_session, staff):
    """# AC R6 S1/S2: ficha completa y auditor�a ascendente."""
    prof, pac, turno = _escenario(db_session)
    for hora, accion in ((9, "crear"), (10, "reprogramar"), (11, "cancelar")):
        _auditoria_manual(
            db_session,
            turno.id,
            accion=accion,
            created_at=datetime(2026, 10, 19, hora, tzinfo=UTC),
            actor_id=staff["users"]["recepcion"].id,
        )
    _login(client)

    resp = client.get(f"/api/turnos/{turno.id}")

    assert resp.status_code == 200
    cuerpo = resp.json()
    assert cuerpo["id"] == str(turno.id)
    assert cuerpo["profesional"]["id"] == str(prof.id)
    assert cuerpo["paciente"]["id"] == str(pac.id)
    assert cuerpo["paciente"]["telefono"] == pac.telefono
    acciones = [item["accion"] for item in cuerpo["auditoria"]["items"]]
    assert acciones == ["crear", "reprogramar", "cancelar"]
    assert cuerpo["auditoria"]["next_cursor"] is None


def test_ficha_historial_keyset_sin_offset(client, db_session, staff):
    """# AC R6 S3/S4: `historial_limit` + cursor opaco sin OFFSET."""
    _, _, turno = _escenario(db_session)
    for minuto in range(5):
        _auditoria_manual(
            db_session,
            turno.id,
            accion=f"accion_{minuto}",
            created_at=datetime(2026, 10, 19, 9, minuto, tzinfo=UTC),
        )
    _login(client)

    primera = client.get(f"/api/turnos/{turno.id}", params={"historial_limit": 2})
    assert primera.status_code == 200
    pagina = primera.json()["auditoria"]
    assert [i["accion"] for i in pagina["items"]] == ["accion_0", "accion_1"]
    assert pagina["next_cursor"]

    segunda = client.get(
        f"/api/turnos/{turno.id}",
        params={
            "historial_limit": 2,
            "historial_cursor": pagina["next_cursor"],
        },
    )
    assert segunda.status_code == 200
    pagina2 = segunda.json()["auditoria"]
    assert [i["accion"] for i in pagina2["items"]] == ["accion_2", "accion_3"]
    assert pagina2["next_cursor"]


def test_ficha_no_expone_token(client, db_session, staff):
    """# AC R6 S6: la ficha nunca devuelve `token_cancelacion`/`cancel_url`."""
    _, _, turno = _escenario(db_session)
    _auditoria_manual(
        db_session,
        turno.id,
        accion="crear",
        created_at=datetime(2026, 10, 19, 9, tzinfo=UTC),
    )
    _login(client)

    resp = client.get(f"/api/turnos/{turno.id}")

    assert resp.status_code == 200
    crudo = resp.text
    assert str(turno.token_cancelacion) not in crudo
    assert "token_cancelacion" not in crudo
    assert "cancel_url" not in crudo


def test_ficha_odontologo_ajeno_403(client, db_session, staff):
    """# AC R6 S5: odont�logo ajeno ? 403."""
    _, _, turno = _escenario(db_session)
    _login(client, ODONTO)

    resp = client.get(f"/api/turnos/{turno.id}")

    assert resp.status_code == 403


def test_ficha_sin_sesion_401(client, db_session, staff):
    """# AC R6 S9: sin sesi�n ni token ? 401."""
    _, _, turno = _escenario(db_session)

    resp = client.get(f"/api/turnos/{turno.id}")

    assert resp.status_code == 401


def test_ficha_turno_inexistente_404(client, db_session, staff):
    """# AC R6 S10: id v�lido inexistente ? 404."""
    _login(client)

    resp = client.get(f"/api/turnos/{uuid.uuid4()}")

    assert resp.status_code == 404


def test_ficha_id_malformado_404(client, db_session, staff):
    """# AC R6 S11: id no UUID ? 404 sin 500."""
    _login(client)

    resp = client.get("/api/turnos/no-es-uuid")

    assert resp.status_code == 404


# --- �7 Auth, RBAC y contratos p�blicos ------------------------------------


@pytest.mark.parametrize("metodo", ["get", "put", "patch"])
def test_staff_endpoints_token_paciente_401(client, db_session, staff, metodo):
    """# AC R7 S1: `?token=` no autentica staff (salvo DELETE p�blico)."""
    _, _, turno = _escenario(db_session)
    params = {"token": str(turno.token_cancelacion)}
    if metodo == "get":
        resp = client.get(f"/api/turnos/{turno.id}", params=params)
    elif metodo == "put":
        resp = client.put(
            f"/api/turnos/{turno.id}", params=params, json={"duracion_min": 30}
        )
    else:
        resp = client.patch(
            f"/api/turnos/{turno.id}/estado",
            params=params,
            json={"estado": "confirmado"},
        )

    assert resp.status_code == 401


def test_cookie_invalida_401_no_degrada_publico(client, db_session, staff):
    """# AC R7 S2: cookie inv�lida no cae al flujo p�blico."""
    client.cookies.set("session", "token-invalido")

    resp = client.post(
        "/api/turnos", json=_body_publico(staff["p1"].id, inicio=_local(10))
    )

    assert resp.status_code == 401


def test_recepcion_todas_las_operaciones_staff(client, db_session, staff):
    """# AC R7 S3: recepci�n puede alta, reprogramar, corregir, estado y ficha."""
    _login(client)
    alta = client.post(
        "/api/turnos", json=_body_staff(staff["p1"].id, inicio=_local(10))
    )
    assert alta.status_code == 201
    turno_id = alta.json()["id"]

    reprogramar = client.put(
        f"/api/turnos/{turno_id}", json={"inicio": _local(13).isoformat()}
    )
    corregir = client.put(
        f"/api/turnos/{turno_id}/paciente",
        json={"telefono": "+5491100004444"},
    )
    estado = client.patch(
        f"/api/turnos/{turno_id}/estado", json={"estado": "confirmado"}
    )
    ficha = client.get(f"/api/turnos/{turno_id}")
    cancelar = _delete(client, f"/api/turnos/{turno_id}", json={})

    assert reprogramar.status_code == 200
    assert corregir.status_code == 200
    assert estado.status_code == 200
    assert ficha.status_code == 200
    assert cancelar.status_code == 200


def test_odontologo_escrituras_recepcion_403(client, db_session, staff):
    """# AC R7 S4: odont�logo no ejecuta altas ni correcciones."""
    prof, pac, turno = _escenario(db_session)
    _login(client, ODONTO)

    alta = client.post(
        "/api/turnos", json=_body_staff(staff["p1"].id, inicio=_local(10))
    )
    reprogramar = client.put(f"/api/turnos/{turno.id}", json={"duracion_min": 30})
    corregir = client.put(
        f"/api/turnos/{turno.id}/paciente", json={"telefono": "+5491100003333"}
    )

    assert alta.status_code == 403
    assert reprogramar.status_code == 403
    assert corregir.status_code == 403


def test_admin_hereda_operaciones_recepcion(client, db_session, staff):
    """# AC R7 S5: admin hereda las operaciones de recepci�n."""
    _login(client, ADMIN)
    alta = client.post(
        "/api/turnos", json=_body_staff(staff["p1"].id, inicio=_local(10))
    )
    assert alta.status_code == 201
    turno_id = alta.json()["id"]

    reprogramar = client.put(
        f"/api/turnos/{turno_id}", json={"inicio": _local(13).isoformat()}
    )
    corregir = client.put(
        f"/api/turnos/{turno_id}/paciente",
        json={"telefono": "+5491100002222"},
    )
    cancelar = _delete(client, f"/api/turnos/{turno_id}", json={})

    assert reprogramar.status_code == 200
    assert corregir.status_code == 200
    assert cancelar.status_code == 200


def test_contratos_publicos_intactos(client, db_session, staff):
    """# AC R7 S6: POST p�blico y DELETE por token conservan C-05/C-06."""
    publica = client.post(
        "/api/turnos", json=_body_publico(staff["p1"].id, inicio=_local(12))
    )

    assert publica.status_code == 201
    token = publica.json()["token_cancelacion"]

    cancelar = _delete(
        client, f"/api/turnos/{publica.json()['id']}", params={"token": token}
    )
    assert cancelar.status_code == 200


# --- �8 Notificaciones (delta C-07) ----------------------------------------


def test_alta_staff_encola_confirmacion_y_recordatorios(client, db_session, staff):
    """# AC R8 S1: alta staff encola la misma cascada que C-05."""
    from app.models.notificacion import NotifEstado, NotifTipo

    prof = _prof(db_session)
    _ventana(db_session, prof.id, dia=1)
    _login(client)

    resp = client.post(
        "/api/turnos", json=_body_staff(prof.id, inicio=_local(10, dia=20))
    )

    assert resp.status_code == 201
    notifs = _notifs(db_session, uuid.UUID(resp.json()["id"]))
    assert {n.tipo for n in notifs} == {
        NotifTipo.confirmacion,
        NotifTipo.recordatorio_24h,
        NotifTipo.recordatorio_2h,
    }
    assert all(n.estado == NotifEstado.pendiente for n in notifs)


def test_cancelacion_staff_encola_cancelacion(client, db_session, staff):
    """# AC R8 S2: cancelaci�n staff encola `cancelacion` sin SMTP."""
    from app.models.notificacion import NotifEstado, NotifTipo

    _, _, turno = _escenario(db_session, hora=12)
    _login(client)

    resp = _delete(client, f"/api/turnos/{turno.id}", json={})

    assert resp.status_code == 200
    notifs = _notifs(db_session, turno.id)
    assert [n for n in notifs if n.tipo == NotifTipo.cancelacion]
    assert all(n.estado == NotifEstado.pendiente for n in notifs)
    assert all(n.enviada_at is None for n in notifs)


def test_c07_no_envia_smtp(client, db_session, staff, monkeypatch):
    """# AC R9 S5: ninguna request staff invoca el sender SMTP."""
    from app.models.notificacion import NotifEstado
    from app.modules.notificaciones.sender import SMTPSender

    llamadas: list[dict] = []

    def _send(self, **kwargs):
        llamadas.append(kwargs)
        raise RuntimeError("no debería enviarse SMTP en la request")

    monkeypatch.setattr(SMTPSender, "send", _send)
    _login(client)
    alta = client.post(
        "/api/turnos", json=_body_staff(staff["p1"].id, inicio=_local(10))
    )
    cancelar = _delete(
        client,
        f"/api/turnos/{alta.json()['id']}",
        json={"motivo": "motivo ficticio"},
    )

    assert alta.status_code == 201
    assert cancelar.status_code == 200
    assert llamadas == []
    assert all(
        n.estado == NotifEstado.pendiente
        for n in _notifs(db_session, uuid.UUID(alta.json()["id"]))
    )


def test_reprogramacion_descarta_obsoletas_y_encola_nuevas(client, db_session, staff):
    """# AC R8 S3: pendientes obsoletas ? fallida con prefijo; nuevas pendientes."""
    from app.models.notificacion import NotifEstado, Notificacion, NotifTipo

    prof, _, turno = _escenario(db_session, hora=12)
    for tipo in (
        NotifTipo.confirmacion,
        NotifTipo.recordatorio_24h,
        NotifTipo.cancelacion,
    ):
        db_session.add(
            Notificacion(
                turno_id=turno.id,
                tipo=tipo,
                estado=NotifEstado.pendiente,
                intentos=0,
                payload={},
            )
        )
    db_session.flush()
    _login(client)

    resp = client.put(
        f"/api/turnos/{turno.id}", json={"inicio": _local(14).isoformat()}
    )

    assert resp.status_code == 200
    db_session.expire_all()
    notifs = _notifs(db_session, turno.id)
    obsoletas = {
        n.tipo: n
        for n in notifs
        if n.error and n.error.startswith("turno_reprogramado:")
    }
    assert set(obsoletas) == {
        NotifTipo.confirmacion,
        NotifTipo.recordatorio_24h,
    }
    assert all(n.estado == NotifEstado.fallida for n in obsoletas.values())
    cancelacion = [n for n in notifs if n.tipo == NotifTipo.cancelacion]
    assert len(cancelacion) == 1
    assert cancelacion[0].estado == NotifEstado.pendiente
    nuevas = [
        n
        for n in notifs
        if n.estado == NotifEstado.pendiente
        and n.tipo in (NotifTipo.confirmacion, NotifTipo.recordatorio_24h)
    ]
    assert nuevas
    for notif in nuevas:
        assert notif.payload["cancel_url"].endswith(
            f"/cancelar?token={turno.token_cancelacion}&id={turno.id}"
        )


def test_reprogramacion_encolado_falla_no_bloquea_200(
    client, db_session, staff, monkeypatch
):
    """# AC R8 S4: fallo del re-encolado no bloquea la reprogramaci�n."""
    from app.models.notificacion import NotifEstado, Notificacion, NotifTipo
    from app.modules.turnos import service

    _, _, turno = _escenario(db_session, hora=12)
    db_session.add(
        Notificacion(
            turno_id=turno.id,
            tipo=NotifTipo.confirmacion,
            estado=NotifEstado.pendiente,
            intentos=0,
            payload={},
        )
    )
    db_session.flush()

    class _BoomNotificacion:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("fallo simulado de encolado")

    monkeypatch.setattr(service, "Notificacion", _BoomNotificacion)
    _login(client)

    resp = client.put(
        f"/api/turnos/{turno.id}", json={"inicio": _local(14).isoformat()}
    )

    assert resp.status_code == 200
    assert resp.json()["notificaciones_encoladas"] is False
    auditoria = _auditoria(db_session, turno.id)[-1]
    assert auditoria.detalle["notificaciones_encoladas"] is False
    assert _estado(db_session, turno).value == "reservado"


def test_notif_descarte_solo_afecta_su_turno(client, db_session, staff):
    """# AC R8 S7: el descarte es por `turno_id`, no global."""
    from app.models.notificacion import NotifEstado, Notificacion, NotifTipo
    from app.modules.turnos import service

    prof, pac, turno = _escenario(db_session, hora=12)
    otro = _turno(db_session, prof, pac, hora=15)
    for turno_id in (turno.id, otro.id):
        db_session.add(
            Notificacion(
                turno_id=turno_id,
                tipo=NotifTipo.confirmacion,
                estado=NotifEstado.pendiente,
                intentos=0,
                payload={},
            )
        )
    db_session.flush()

    assert service._descartar_pendientes(
        db_session, turno_id=turno.id, detalle="prueba"
    )
    db_session.expire_all()
    propias = _notifs(db_session, turno.id)
    ajenas = _notifs(db_session, otro.id)
    assert all(n.estado == NotifEstado.fallida for n in propias)
    assert all(n.estado == NotifEstado.pendiente for n in ajenas)


def test_notif_descarte_no_altera_intentos_ni_toca_enviadas(client, db_session, staff):
    """# AC R8 S5: descarte no cambia `intentos` ni pisotea enviadas."""
    from app.models.notificacion import NotifEstado, Notificacion, NotifTipo
    from app.modules.turnos import service

    _, _, turno = _escenario(db_session)
    pendiente = Notificacion(
        turno_id=turno.id,
        tipo=NotifTipo.confirmacion,
        estado=NotifEstado.pendiente,
        intentos=2,
        payload={},
    )
    enviada = Notificacion(
        turno_id=turno.id,
        tipo=NotifTipo.recordatorio_2h,
        estado=NotifEstado.enviada,
        intentos=1,
        payload={},
    )
    db_session.add_all([pendiente, enviada])
    db_session.flush()

    service._descartar_pendientes(db_session, turno_id=turno.id, detalle="x")
    db_session.expire_all()
    pendiente = db_session.get(Notificacion, pendiente.id)
    enviada = db_session.get(Notificacion, enviada.id)
    assert pendiente.estado == NotifEstado.fallida
    assert pendiente.intentos == 2
    assert enviada.estado == NotifEstado.enviada
    assert enviada.intentos == 1
    assert enviada.error is None


def test_worker_no_reenvia_descartadas(client, db_session, staff):
    """# AC R8 S7: el worker solo toma `pendiente`, nunca `fallida`."""
    from app.models.notificacion import NotifEstado, Notificacion, NotifTipo
    from app.modules.notificaciones.worker import run_once

    _, _, turno = _escenario(db_session)
    descartada = Notificacion(
        turno_id=turno.id,
        tipo=NotifTipo.confirmacion,
        estado=NotifEstado.fallida,
        intentos=0,
        error="turno_reprogramado: inicio 2026-10-19T12:00:00+00:00 -> ...",
        payload={},
    )
    db_session.add(descartada)
    db_session.flush()

    class _Sender:
        def __init__(self):
            self.llamadas = []

        def send(self, **kwargs):
            self.llamadas.append(kwargs)

    sender = _Sender()
    resumen = run_once(db_session, sender, now=NOW.astimezone(UTC), batch_size=10)

    assert sender.llamadas == []
    assert resumen.enviadas == 0
    db_session.expire_all()
    assert db_session.get(Notificacion, descartada.id).estado == NotifEstado.fallida


# --- �9 Auditor�a append-only ----------------------------------------------


@pytest.mark.parametrize(
    "accion",
    [
        "crear",
        "reprogramar",
        "editar_paciente",
        "cancelar",
        "forzar_cancelacion",
    ],
)
def test_auditoria_una_fila_por_mutacion_staff(client, db_session, staff, accion):
    """# AC R9 S1/S4: cada mutaci�n staff produce exactamente una fila."""
    if accion == "crear":
        _login(client)
        resp = client.post(
            "/api/turnos",
            json=_body_staff(staff["p1"].id, inicio=_local(10)),
        )
        turno_id = uuid.UUID(resp.json()["id"])
        esperada = "crear"
    elif accion == "reprogramar":
        _, _, turno = _escenario(db_session)
        turno_id = turno.id
        _login(client)
        resp = client.put(
            f"/api/turnos/{turno.id}", json={"inicio": _local(13).isoformat()}
        )
        esperada = "reprogramar"
    elif accion == "editar_paciente":
        _, _, turno = _escenario(db_session)
        turno_id = turno.id
        _login(client)
        resp = client.put(
            f"/api/turnos/{turno.id}/paciente",
            json={"telefono": "+5491100001111"},
        )
        esperada = "editar_paciente"
    else:
        _, _, turno = _escenario(
            db_session, hora=10 if accion == "forzar_cancelacion" else 12
        )
        turno_id = turno.id
        _login(client)
        body = {"motivo": "motivo ficticio"} if accion == "forzar_cancelacion" else {}
        resp = _delete(client, f"/api/turnos/{turno.id}", json=body)
        esperada = accion

    assert resp.status_code in (200, 201)
    filas = _auditoria(db_session, turno_id)
    assert [f.accion for f in filas] == [esperada]
    assert filas[0].actor_id == staff["users"]["recepcion"].id


@pytest.mark.parametrize("caso", ["400", "401", "403", "409", "422"])
def test_auditoria_solicitud_rechazada_no_escribe(client, db_session, staff, caso):
    """# AC R9 S2: 400/401/403/409/422 no agregan filas."""
    prof, pac, turno = _escenario(db_session, hora=12)
    turno_id = turno.id
    antes = len(_auditoria(db_session, turno_id))

    if caso == "400":
        _login(client)
        resp = client.put(
            f"/api/turnos/{turno.id}",
            json={"inicio": _local(13).isoformat(), "extra": True},
        )
    elif caso == "401":
        resp = client.put(f"/api/turnos/{turno.id}", json={"duracion_min": 30})
    elif caso == "403":
        _login(client, ODONTO)
        resp = client.put(f"/api/turnos/{turno.id}", json={"duracion_min": 30})
    elif caso == "409":
        _turno(db_session, prof, pac, hora=13)
        _login(client)
        resp = client.put(
            f"/api/turnos/{turno.id}", json={"inicio": _local(13).isoformat()}
        )
    else:
        _, _, cerrado = _escenario(db_session, estado="cancelado", hora=14)
        turno_id = cerrado.id
        antes = len(_auditoria(db_session, turno_id))
        _login(client)
        resp = client.put(
            f"/api/turnos/{cerrado.id}",
            json={"inicio": _local(15).isoformat()},
        )

    assert resp.status_code == int(caso)
    assert len(_auditoria(db_session, turno_id)) == antes


def test_auditoria_detalle_antes_despues_y_actor(client, db_session, staff):
    """# AC R9 S3: `detalle` guarda antes/despu�s y actor con rol."""
    _, _, turno = _escenario(db_session)
    _login(client)

    resp = client.put(
        f"/api/turnos/{turno.id}", json={"inicio": _local(14).isoformat()}
    )

    assert resp.status_code == 200
    fila = _auditoria(db_session, turno.id)[-1]
    assert fila.detalle["actor"]["id"] == str(staff["users"]["recepcion"].id)
    assert fila.detalle["actor"]["rol"] == "recepcion"
    assert fila.detalle["estado_previo"] == "reservado"
    assert fila.detalle["estado_nuevo"] == "reservado"
    cambio = fila.detalle["cambios"]["inicio"]
    assert set(cambio) == {"antes", "despues"}
    assert cambio["antes"] != cambio["despues"]


def test_auditoria_append_only_trigger(client, db_session, staff):
    """# AC R9 S5: UPDATE/DELETE de `auditoria_turno` lo bloquea el trigger."""
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    _, _, turno = _escenario(db_session)
    fila = _auditoria_manual(
        db_session,
        turno.id,
        accion="crear",
        created_at=datetime(2026, 10, 19, 9, tzinfo=UTC),
    )

    with pytest.raises(DBAPIError):
        with db_session.begin_nested():
            db_session.execute(
                text("UPDATE auditoria_turno SET accion = 'x' WHERE id = :id"),
                {"id": fila.id},
            )

    with pytest.raises(DBAPIError):
        with db_session.begin_nested():
            db_session.execute(
                text("DELETE FROM auditoria_turno WHERE id = :id"),
                {"id": fila.id},
            )

    assert db_session.get(type(fila), fila.id).accion == "crear"


# --- §10 Concurrencia (autoridad final DB) ---------------------------------


def _setup_c07_concurrencia(test_engine, *, cantidad=2):
    """Profesional + ventana + staff + N turnos activos commiteados."""
    from sqlalchemy.orm import Session

    from app.core.security import hash_password
    from app.models.disponibilidad import Disponibilidad
    from app.models.paciente import Paciente
    from app.models.profesional import Profesional
    from app.models.turno import Turno, TurnoEstado, TurnoOrigen
    from app.models.usuario_staff import StaffRol, UsuarioStaff

    sesion = Session(bind=test_engine)
    try:
        prof = Profesional(
            nombre="Odontologo Concurrencia",
            especialidad="General",
            duracion_default_min=30,
        )
        sesion.add(prof)
        sesion.flush()
        sesion.add(
            Disponibilidad(
                profesional_id=prof.id,
                dia_semana=0,
                hora_desde=time(9),
                hora_hasta=time(17),
                vigente_desde=date(2026, 1, 1),
                vigente_hasta=date(2026, 12, 31),
            )
        )
        staff = UsuarioStaff(
            email=f"conc-{uuid.uuid4().hex}@ficticio.test",
            password_hash=hash_password(PASSWORD),
            rol=StaffRol.recepcion,
            activo=True,
        )
        sesion.add(staff)
        turnos: list[uuid.UUID] = []
        dnis: list[str] = []
        for indice in range(cantidad):
            dni = f"{uuid.uuid4().int % (9 * 10**7) + 10**7:08d}"
            dni_previo = dni
            while dni_previo in dnis:
                dni = f"{uuid.uuid4().int % (9 * 10**7) + 10**7:08d}"
            dnis.append(dni)
            pac = Paciente(
                nombre=f"Paciente Conc {indice}",
                dni=dni,
                telefono="+5491100000200",
                obra_social="OS Ficticia",
                email=f"conc{indice}@ficticio.test",
            )
            sesion.add(pac)
            sesion.flush()
            inicio = _local(9 + indice).astimezone(UTC)
            turno = Turno(
                profesional_id=prof.id,
                paciente_id=pac.id,
                inicio=inicio,
                fin=inicio + timedelta(minutes=30),
                duracion_min=30,
                estado=TurnoEstado.reservado,
                origen=TurnoOrigen.recepcion,
                token_cancelacion=uuid.uuid4(),
            )
            sesion.add(turno)
            sesion.flush()
            turnos.append(turno.id)
        sesion.commit()
        return {
            "prof_id": prof.id,
            "staff_id": staff.id,
            "turnos": turnos,
            "dnis": dnis,
        }
    finally:
        sesion.close()


def _limpiar_c07_concurrencia(test_engine, datos):
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    turnos = [str(t) for t in datos["turnos"]]
    sesion = Session(bind=test_engine)
    try:
        sesion.execute(
            text(
                "ALTER TABLE auditoria_turno DISABLE TRIGGER auditoria_no_update_delete"
            )
        )
        for turno in turnos:
            sesion.execute(
                text("DELETE FROM auditoria_turno WHERE turno_id = :t"),
                {"t": turno},
            )
            sesion.execute(
                text("DELETE FROM notificacion WHERE turno_id = :t"),
                {"t": turno},
            )
            sesion.execute(text("DELETE FROM turno WHERE id = :t"), {"t": turno})
        for dni in datos["dnis"]:
            sesion.execute(text("DELETE FROM paciente WHERE dni = :dni"), {"dni": dni})
        sesion.execute(
            text("DELETE FROM disponibilidad WHERE profesional_id = :prof"),
            {"prof": str(datos["prof_id"])},
        )
        sesion.execute(
            text("DELETE FROM usuario_staff WHERE id = :staff"),
            {"staff": str(datos["staff_id"])},
        )
        sesion.execute(
            text("DELETE FROM profesional WHERE id = :prof"),
            {"prof": str(datos["prof_id"])},
        )
        sesion.execute(
            text(
                "ALTER TABLE auditoria_turno ENABLE TRIGGER auditoria_no_update_delete"
            )
        )
        sesion.commit()
    finally:
        sesion.close()


def test_reprogramar_dos_concurrentes_un_ganador(test_engine):
    """# AC R2 S9: dos reprogramaciones al mismo destino ? un 200 y un 409."""
    from sqlalchemy.orm import Session

    from app.modules.turnos import service
    from app.modules.turnos.schemas import TurnoReprogramar

    datos = _setup_c07_concurrencia(test_engine, cantidad=2)
    barrera = threading.Barrier(3)
    resultados: list[tuple[int, dict | None]] = []
    actor = {
        "tipo": "staff",
        "id": str(datos["staff_id"]),
        "rol": "recepcion",
    }

    def mover(turno_id):
        sesion = Session(bind=test_engine)
        try:
            barrera.wait(timeout=5)
            service.reprogramar(
                sesion,
                turno_id,
                TurnoReprogramar(inicio=_local(13)),
                actor=actor,
                now_provider=lambda: NOW,
            )
            resultados.append((200, None))
        except Exception as exc:  # HTTPException esperada
            resultados.append(
                (getattr(exc, "status_code", 500), getattr(exc, "detail", None))
            )
        finally:
            sesion.close()

    hilos = [
        threading.Thread(target=mover, args=(turno_id,)) for turno_id in datos["turnos"]
    ]
    for hilo in hilos:
        hilo.start()
    barrera.wait(timeout=5)
    for hilo in hilos:
        hilo.join(timeout=20)
    try:
        codigos = sorted(codigo for codigo, _ in resultados)
        assert codigos == [200, 409], resultados
        perdedor = next(d for c, d in resultados if c == 409)
        assert perdedor["codigo"] == "slot_ocupado"
        verificacion = Session(bind=test_engine)
        try:
            from app.models.turno import Turno

            destino = Turno.inicio == _local(13).astimezone(UTC)
            activos = (
                verificacion.query(Turno)
                .filter(Turno.profesional_id == datos["prof_id"], destino)
                .count()
            )
            assert activos == 1
        finally:
            verificacion.close()
    finally:
        _limpiar_c07_concurrencia(test_engine, datos)


def test_patch_estado_dos_concurrentes_una_transicion(test_engine):
    """# AC R5 S11: dos PATCH simultáneos ? uno aplica y el otro 422."""
    from sqlalchemy.orm import Session

    from app.models.turno import TurnoEstado
    from app.modules.turnos import service

    datos = _setup_c07_concurrencia(test_engine, cantidad=1)
    turno_id = datos["turnos"][0]
    barrera = threading.Barrier(3)
    resultados: list[int] = []
    actor = {
        "tipo": "staff",
        "id": str(datos["staff_id"]),
        "rol": "recepcion",
    }

    def transicionar():
        sesion = Session(bind=test_engine)
        try:
            barrera.wait(timeout=5)
            service.cambiar_estado(
                sesion,
                turno_id,
                TurnoEstado.confirmado,
                actor=actor,
                now_provider=lambda: NOW,
            )
            resultados.append(200)
        except Exception as exc:
            resultados.append(getattr(exc, "status_code", 500))
        finally:
            sesion.close()

    hilos = [threading.Thread(target=transicionar) for _ in range(2)]
    for hilo in hilos:
        hilo.start()
    barrera.wait(timeout=5)
    for hilo in hilos:
        hilo.join(timeout=20)
    try:
        assert sorted(resultados) == [200, 422], resultados
        verificacion = Session(bind=test_engine)
        try:
            from app.models.auditoria import AuditoriaTurno
            from app.models.turno import Turno

            turno = verificacion.get(Turno, turno_id)
            assert turno.estado == TurnoEstado.confirmado
            filas = (
                verificacion.query(AuditoriaTurno)
                .filter(AuditoriaTurno.turno_id == turno_id)
                .count()
            )
            assert filas == 1
        finally:
            verificacion.close()
    finally:
        _limpiar_c07_concurrencia(test_engine, datos)
