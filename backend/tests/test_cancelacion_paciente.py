"""Cancelación pública por token (C-06; PG real, reloj inyectable).

# AC cancelacion-paciente (R1-R8, 32 escenarios). Los mocks se limitan al
# reloj y a un fallo simulado del encolado (borde); la persistencia corre
# contra Postgres real (`db_session`/`test_engine`). Datos ficticios `.test`,
# DNI sintéticos y tokens UUID aleatorios (regla dura 12).
"""

import logging
import threading
import time as time_module
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
NOW = datetime(2026, 10, 19, 8, 0, tzinfo=TZ)


@pytest.fixture
def client(db_session):
    """TestClient https contra PG real con rollback + reloj fijo (D-10/D-13)."""
    from app.core import ratelimit
    from app.db.session import get_db
    from app.main import app
    from app.modules.turnos.router import get_now_provider

    ratelimit.reset()
    ratelimit.reset_public()

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    app.dependency_overrides[get_now_provider] = lambda: (lambda: NOW)
    with TestClient(app, base_url="https://testserver") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def client_rate_limit(db_session, monkeypatch):
    """TestClient con reloj fake y IP inyectable (R8, sin sleeps)."""
    from app.core import ratelimit
    from app.db.session import get_db
    from app.main import app
    from app.modules.turnos.router import get_client_ip, get_now_provider

    ratelimit.reset()
    ratelimit.reset_public()
    ahora = [1_000.0]
    ip = {"valor": "10.0.0.1"}
    monkeypatch.setattr(time_module, "monotonic", lambda: ahora[0])

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    app.dependency_overrides[get_now_provider] = lambda: (lambda: NOW)
    app.dependency_overrides[get_client_ip] = lambda: ip["valor"]
    with TestClient(app, base_url="https://testserver") as c:
        yield c, ahora, ip
    app.dependency_overrides.clear()


def _prof(db_session, duracion=30, **kw):
    from tests.conftest import mk_profesional

    return mk_profesional(db_session, duracion_default_min=duracion, **kw)


def _ventana(db_session, prof_id, dia=0, desde=9, hasta=17):
    from datetime import time

    from app.models.disponibilidad import Disponibilidad

    db_session.add(
        Disponibilidad(
            profesional_id=prof_id,
            dia_semana=dia,
            hora_desde=time(desde, 0),
            hora_hasta=time(hasta, 0),
            vigente_desde=datetime(2026, 1, 1).date(),
            vigente_hasta=datetime(2026, 12, 31).date(),
        )
    )
    db_session.flush()


def _turno(
    db_session,
    *,
    estado="reservado",
    offset=timedelta(hours=6),
    duracion=30,
    prof=None,
    paciente=None,
):
    """Turno de 30 min con `inicio = NOW + offset` (UTC) y token único."""
    from app.models.turno import TurnoEstado
    from tests.conftest import mk_paciente, mk_turno

    prof = prof or _prof(db_session)
    pac = paciente or mk_paciente(db_session)
    inicio = (NOW + offset).astimezone(UTC)
    turno = mk_turno(
        db_session,
        prof.id,
        pac.id,
        inicio=inicio,
        fin=inicio + timedelta(minutes=duracion),
        estado=TurnoEstado(estado),
    )
    return prof, pac, turno


def _url(turno) -> str:
    return f"/api/turnos/{turno.id}"


def _params(turno) -> dict:
    return {"token": str(turno.token_cancelacion)}


def _estado(db_session, turno):
    from app.models.turno import Turno

    return db_session.query(Turno).filter(Turno.id == turno.id).one().estado


# --- §1 Contrato, query estricta y configuración ----------------------------


def test_cancelacion_query_token_repetido_400(client, db_session):
    """# AC R3 S4: `token` repetido → 400 en `campo="token"`, sin cancelar."""
    from app.models.turno import TurnoEstado

    _, _, turno = _turno(db_session)
    resp = client.delete(
        _url(turno),
        params=[
            ("token", str(turno.token_cancelacion)),
            ("token", str(uuid.uuid4())),
        ],
    )

    assert resp.status_code == 400
    assert any(d["campo"] == "token" for d in resp.json()["detail"])
    assert _estado(db_session, turno) == TurnoEstado.reservado


@pytest.mark.parametrize("con_token", [False, True], ids=["sin-token", "con-token"])
def test_cancelacion_query_dni_telefono_400(client, db_session, con_token):
    """# AC R3 S2: `dni`/`telefono` en query → 400 por campo y sin cancelar."""
    from app.models.turno import TurnoEstado

    _, _, turno = _turno(db_session)
    params = {"dni": "30999001", "telefono": "+5491100000001"}
    if con_token:
        params["token"] = str(turno.token_cancelacion)

    resp = client.delete(_url(turno), params=params)

    assert resp.status_code == 400
    campos = {d["campo"] for d in resp.json()["detail"]}
    assert {"dni", "telefono"} <= campos
    assert _estado(db_session, turno) == TurnoEstado.reservado


def test_cancelacion_respuesta_solo_campos_declarados():
    """# AC R7 S1: `CancelacionOut` declara solo los campos públicos."""
    from app.modules.turnos.schemas import CancelacionOut

    declarados = {
        "id",
        "estado",
        "inicio",
        "fin",
        "duracion_min",
        "notificaciones_encoladas",
        "mensaje",
    }
    assert set(CancelacionOut.model_fields) == declarados

    out = CancelacionOut(
        id=uuid.uuid4(),
        estado="cancelado",
        inicio="2026-10-19T17:00:00+00:00",
        fin="2026-10-19T17:30:00+00:00",
        duracion_min=30,
        notificaciones_encoladas=True,
        mensaje="Turno cancelado",
    )
    data = out.model_dump(mode="json")
    assert set(data) == declarados
    for prohibido in (
        "nombre",
        "dni",
        "telefono",
        "email",
        "obra_social",
        "token_cancelacion",
        "cancel_url",
    ):
        assert prohibido not in data


def test_cancelacion_out_extra_forbid():
    """# AC R7 S3: un campo desconocido en la respuesta es imposible."""
    from pydantic import ValidationError

    from app.modules.turnos.schemas import CancelacionOut

    with pytest.raises(ValidationError):
        CancelacionOut(
            id=uuid.uuid4(),
            estado="cancelado",
            inicio="2026-10-19T17:00:00+00:00",
            fin="2026-10-19T17:30:00+00:00",
            duracion_min=30,
            notificaciones_encoladas=True,
            mensaje="Turno cancelado",
            dni="30999001",
        )


def test_cancelacion_contacto_default_y_env(monkeypatch, tmp_path):
    """D-11: `CONSULTORIO_CONTACTO` tiene default no secreto y override por env."""
    from app.core.config import get_settings

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CONSULTORIO_CONTACTO", raising=False)
    default = get_settings().CONSULTORIO_CONTACTO
    assert default == "Comunicate con el consultorio para coordinar la cancelación"

    monkeypatch.setenv("CONSULTORIO_CONTACTO", "WhatsApp 11-0000-0000")
    assert get_settings().CONSULTORIO_CONTACTO == "WhatsApp 11-0000-0000"


def test_cancelacion_inicio_iso_utc_en_respuesta(client, db_session):
    """# AC R7 S1: `inicio`/`fin` del 200 son strings ISO-8601 UTC."""
    _, _, turno = _turno(db_session)
    inicio_esperado = turno.inicio.astimezone(UTC)

    resp = client.delete(_url(turno), params=_params(turno))

    assert resp.status_code == 200
    cuerpo = resp.json()
    for clave in ("inicio", "fin"):
        assert isinstance(cuerpo[clave], str)
        assert datetime.fromisoformat(cuerpo[clave]).utcoffset() == timedelta(0)
    assert datetime.fromisoformat(cuerpo["inicio"]) == inicio_esperado


# --- §2 Servicio de cancelación y transacción -------------------------------


def _reserva_body(prof_id, inicio, *, dni="30999001"):
    return {
        "profesional_id": str(prof_id),
        "inicio": inicio.isoformat(),
        "paciente": {
            "nombre": "Paciente Ficticio",
            "dni": dni,
            "telefono": "+5491100000001",
            "obra_social": "OS Ficticia",
            "email": f"paciente-{dni}@ficticio.test",
        },
    }


def test_cancelacion_mas_de_3h_cancela_y_libera_slot(client, db_session):
    """# AC R1 S1: >3h → 200, `cancelado` y el slot se puede volver a reservar."""
    from app.models.turno import Turno, TurnoEstado

    offset = timedelta(hours=6)
    prof, _, turno = _turno(db_session, offset=offset)
    _ventana(db_session, prof.id, desde=9, hasta=17)

    resp = client.delete(_url(turno), params=_params(turno))

    assert resp.status_code == 200
    assert resp.json()["estado"] == "cancelado"
    assert _estado(db_session, turno) == TurnoEstado.cancelado
    assert db_session.query(Turno).filter(Turno.id == turno.id).count() == 1

    nueva = client.post(
        "/api/turnos", json=_reserva_body(prof.id, NOW + offset)
    )
    assert nueva.status_code == 201, nueva.text


def test_cancelacion_turno_confirmado_cancela_200(client, db_session):
    """# AC R1 S2: `confirmado → cancelado` procede igual que `reservado`."""
    from app.models.turno import TurnoEstado

    _, _, turno = _turno(db_session, estado="confirmado")

    resp = client.delete(_url(turno), params=_params(turno))

    assert resp.status_code == 200
    assert resp.json()["estado"] == "cancelado"
    assert _estado(db_session, turno) == TurnoEstado.cancelado


def test_cancelacion_exactamente_3h_acepta_200(client, db_session):
    """# AC R1 S3: borde `>=`: exactamente `CANCEL_HOURS_MIN` se acepta."""
    from app.models.turno import TurnoEstado

    _, _, turno = _turno(db_session, offset=timedelta(hours=3))

    resp = client.delete(_url(turno), params=_params(turno))

    assert resp.status_code == 200
    assert _estado(db_session, turno) == TurnoEstado.cancelado


def test_cancelacion_menos_de_3h_422_con_contacto(client, db_session):
    """# AC R1 S4: 2h59 → 422 fuera de plazo, contacto, sin efectos."""
    from app.models.auditoria import AuditoriaTurno
    from app.models.notificacion import Notificacion
    from app.models.turno import TurnoEstado

    _, _, turno = _turno(db_session, offset=timedelta(hours=2, minutes=59))

    resp = client.delete(_url(turno), params=_params(turno))

    assert resp.status_code == 422
    detalle = resp.json()["detail"]
    assert detalle["codigo"] == "cancelacion_fuera_de_plazo"
    assert detalle["mensaje"]
    assert detalle["contacto"].strip()
    assert _estado(db_session, turno) == TurnoEstado.reservado
    assert (
        db_session.query(Notificacion)
        .filter(Notificacion.turno_id == turno.id)
        .count()
        == 0
    )
    assert (
        db_session.query(AuditoriaTurno)
        .filter(AuditoriaTurno.turno_id == turno.id)
        .count()
        == 0
    )


def test_cancelacion_ventana_expirada_422_no_403(client, db_session):
    """# AC R1 S5: `inicio < now` con token válido → 422, nunca 403."""
    from app.models.turno import TurnoEstado

    _, _, turno = _turno(db_session, offset=timedelta(hours=-1))

    resp = client.delete(_url(turno), params=_params(turno))

    assert resp.status_code == 422
    assert resp.json()["detail"]["codigo"] == "cancelacion_fuera_de_plazo"
    assert _estado(db_session, turno) == TurnoEstado.reservado


def test_cancelacion_umbral_configurable_5h_422(
    client, db_session, monkeypatch
):
    """# AC R1 S6: con `CANCEL_HOURS_MIN=5`, 4 h de anticipación no alcanza."""
    monkeypatch.setenv("CANCEL_HOURS_MIN", "5")
    _, _, turno = _turno(db_session, offset=timedelta(hours=4))

    resp = client.delete(_url(turno), params=_params(turno))

    assert resp.status_code == 422
    assert resp.json()["detail"]["codigo"] == "cancelacion_fuera_de_plazo"


def test_cancelacion_no_elimina_fila_turno(client, db_session):
    """# AC R1 S7 / regla dura 3: soft cancel, la fila sigue existiendo."""
    from app.models.turno import Turno, TurnoEstado

    _, _, turno = _turno(db_session)

    resp = client.delete(_url(turno), params=_params(turno))

    assert resp.status_code == 200
    fila = db_session.query(Turno).filter(Turno.id == turno.id).one()
    assert fila.estado == TurnoEstado.cancelado
    assert db_session.query(Turno).filter(Turno.id == turno.id).count() == 1


def test_cancelacion_dos_concurrentes_un_solo_efecto(test_engine):
    """# AC R4 S4: la 2.ª tx espera el `FOR UPDATE` y da 422, no 500."""
    from sqlalchemy.orm import Session

    from app.models.auditoria import AuditoriaTurno
    from app.models.notificacion import Notificacion
    from app.models.turno import Turno, TurnoEstado
    from app.modules.turnos import cancellation_service

    datos = _setup_commit(test_engine)
    conn_a = test_engine.connect()
    txn_a = conn_a.begin()
    sesion_a = Session(bind=conn_a)
    resultado: dict = {}
    try:
        bloqueado = (
            sesion_a.query(Turno)
            .filter(Turno.id == datos["turno_id"])
            .with_for_update()
            .one()
        )
        bloqueado.estado = TurnoEstado.cancelado
        sesion_a.flush()
        sesion_a.add(
            Notificacion(
                turno_id=datos["turno_id"],
                tipo="cancelacion",
                estado="pendiente",
                intentos=0,
                payload={"tipo": "cancelacion"},
            )
        )
        sesion_a.add(
            AuditoriaTurno(
                turno_id=datos["turno_id"],
                actor_id=None,
                accion="cancelar",
                detalle={"actor": "paciente"},
            )
        )
        sesion_a.flush()

        arrancada = threading.Event()

        def segunda():
            from sqlalchemy.orm import Session as SessionB

            conn_b = test_engine.connect()
            txn_b = conn_b.begin()
            sesion_b = SessionB(bind=conn_b)
            try:
                arrancada.set()
                cancellation_service.cancelar(
                    sesion_b,
                    turno_id=datos["turno_id"],
                    token=datos["token"],
                    now_provider=lambda: NOW,
                )
                resultado["status"] = 200
            except cancellation_service.TurnoYaCancelado:
                resultado["status"] = 422
                resultado["codigo"] = "turno_ya_cancelado"
            except Exception as exc:  # pragma: no cover - diagnóstico
                resultado["status"] = type(exc).__name__
                resultado["detalle"] = str(exc)
            finally:
                if txn_b.is_active:
                    txn_b.rollback()
                sesion_b.close()
                conn_b.close()

        hilo = threading.Thread(target=segunda)
        hilo.start()
        assert arrancada.wait(timeout=5)
        threading.Event().wait(0.5)
        assert hilo.is_alive(), "la segunda cancelación no esperó el lock"
        txn_a.commit()
        hilo.join(timeout=15)
        assert not hilo.is_alive()

        assert resultado["status"] == 422, resultado
        assert resultado["codigo"] == "turno_ya_cancelado"

        verificacion = Session(bind=test_engine)
        try:
            final = (
                verificacion.query(Turno)
                .filter(Turno.id == datos["turno_id"])
                .one()
            )
            assert final.estado == TurnoEstado.cancelado
            assert (
                verificacion.query(Notificacion)
                .filter(Notificacion.turno_id == datos["turno_id"])
                .count()
                == 1
            )
            assert (
                verificacion.query(AuditoriaTurno)
                .filter(AuditoriaTurno.turno_id == datos["turno_id"])
                .count()
                == 1
            )
        finally:
            verificacion.close()
    finally:
        if txn_a.is_active:
            txn_a.rollback()
        sesion_a.close()
        conn_a.close()
        _limpiar_commit(test_engine, datos)


def _setup_commit(test_engine, *, offset=timedelta(hours=6)):
    """Setup commiteado (fuera de `db_session`) para la prueba de concurrencia."""
    from sqlalchemy.orm import Session

    from app.models.paciente import Paciente
    from app.models.turno import Turno, TurnoEstado, TurnoOrigen
    from tests.conftest import mk_profesional

    sesion = Session(bind=test_engine)
    try:
        prof = mk_profesional(sesion)
        pac = Paciente(
            nombre="Paciente Concurrencia",
            dni=f"7{uuid.uuid4().int % 10**9:09d}",
            telefono="+5491100000200",
            obra_social="OS Ficticia",
            email="concurrencia@ficticio.test",
        )
        sesion.add(pac)
        sesion.flush()
        token = uuid.uuid4()
        inicio = (NOW + offset).astimezone(UTC)
        turno = Turno(
            profesional_id=prof.id,
            paciente_id=pac.id,
            inicio=inicio,
            fin=inicio + timedelta(minutes=30),
            duracion_min=30,
            estado=TurnoEstado.reservado,
            origen=TurnoOrigen.online,
            token_cancelacion=token,
        )
        sesion.add(turno)
        sesion.commit()
        return {
            "prof_id": prof.id,
            "pac_id": pac.id,
            "turno_id": turno.id,
            "token": token,
        }
    finally:
        sesion.close()


def _limpiar_commit(test_engine, datos):
    """Limpia filas commiteadas; el trigger append-only exige desactivarlo."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    sesion = Session(bind=test_engine)
    try:
        sesion.execute(
            text(
                "ALTER TABLE auditoria_turno "
                "DISABLE TRIGGER auditoria_no_update_delete"
            )
        )
        sesion.execute(
            text("DELETE FROM auditoria_turno WHERE turno_id = :turno"),
            {"turno": str(datos["turno_id"])},
        )
        sesion.execute(
            text(
                "ALTER TABLE auditoria_turno "
                "ENABLE TRIGGER auditoria_no_update_delete"
            )
        )
        sesion.execute(
            text("DELETE FROM notificacion WHERE turno_id = :turno"),
            {"turno": str(datos["turno_id"])},
        )
        sesion.execute(
            text("DELETE FROM turno WHERE id = :turno"),
            {"turno": str(datos["turno_id"])},
        )
        sesion.execute(
            text("DELETE FROM paciente WHERE id = :pac"),
            {"pac": str(datos["pac_id"])},
        )
        sesion.execute(
            text("DELETE FROM profesional WHERE id = :prof"),
            {"prof": str(datos["prof_id"])},
        )
        sesion.commit()
    finally:
        sesion.close()

# --- §3 Endpoint, credencial única y 403 genérico ---------------------------


def test_cancelacion_token_invalido_403(client, db_session):
    """# AC R2 S2: token bien formado que no corresponde → 403 sin efectos."""
    from app.models.auditoria import AuditoriaTurno
    from app.models.notificacion import Notificacion
    from app.models.turno import TurnoEstado

    _, _, turno = _turno(db_session)

    resp = client.delete(_url(turno), params={"token": str(uuid.uuid4())})

    assert resp.status_code == 403
    assert resp.json() == {"detail": "No autorizado"}
    assert _estado(db_session, turno) == TurnoEstado.reservado
    assert (
        db_session.query(Notificacion)
        .filter(Notificacion.turno_id == turno.id)
        .count()
        == 0
    )
    assert (
        db_session.query(AuditoriaTurno)
        .filter(AuditoriaTurno.turno_id == turno.id)
        .count()
        == 0
    )


@pytest.mark.parametrize(
    "params",
    [{}, {"token": ""}, {"token": "no-es-uuid"}],
    ids=["sin-token", "token-vacio", "token-malformado"],
)
def test_cancelacion_token_ausente_vacio_malformado_403(
    client, db_session, params
):
    """# AC R2 S3: token ausente/vacío/mal formado → mismo 403 genérico."""
    from app.models.turno import TurnoEstado

    _, _, turno = _turno(db_session)

    resp = client.delete(_url(turno), params=params)

    assert resp.status_code == 403
    assert resp.json() == {"detail": "No autorizado"}
    assert _estado(db_session, turno) == TurnoEstado.reservado


def test_cancelacion_token_de_otro_turno_403(client, db_session):
    """# AC R2 S4: el token del turno A no cancela el turno B."""
    from app.models.turno import TurnoEstado

    prof, _, turno_a = _turno(db_session)
    _, _, turno_b = _turno(db_session, prof=prof, offset=timedelta(hours=7))

    resp = client.delete(_url(turno_b), params=_params(turno_a))

    assert resp.status_code == 403
    assert resp.json() == {"detail": "No autorizado"}
    assert _estado(db_session, turno_a) == TurnoEstado.reservado
    assert _estado(db_session, turno_b) == TurnoEstado.reservado


def test_cancelacion_id_inexistente_403(client, db_session):
    """# AC R2 S5: UUID inexistente con token bien formado → 403 genérico."""
    resp = client.delete(
        f"/api/turnos/{uuid.uuid4()}", params={"token": str(uuid.uuid4())}
    )

    assert resp.status_code == 403
    assert resp.json() == {"detail": "No autorizado"}


def test_cancelacion_id_malformado_403(client, db_session):
    """# AC R2 S5: `id` que no parsea como UUID → 403 genérico, no 400/422."""
    _, _, turno = _turno(db_session)

    resp = client.delete(
        "/api/turnos/no-es-uuid", params=_params(turno)
    )

    assert resp.status_code == 403
    assert resp.json() == {"detail": "No autorizado"}


def test_cancelacion_token_en_body_no_autentica_403(client, db_session):
    """# AC R3 S3: un token en el body sin `?token=` no autentica."""
    from app.models.turno import TurnoEstado

    _, _, turno = _turno(db_session)

    resp = client.request(
        "DELETE",
        _url(turno),
        json={"token": str(turno.token_cancelacion)},
    )

    assert resp.status_code == 403
    assert resp.json() == {"detail": "No autorizado"}
    assert _estado(db_session, turno) == TurnoEstado.reservado


def test_cancelacion_turno_cancelado_422_sin_efectos(client, db_session):
    """# AC R4 S2 / D-5: segunda llamada → 422 sin cambiar nada."""
    from app.models.auditoria import AuditoriaTurno
    from app.models.notificacion import Notificacion
    from app.models.turno import Turno

    _, _, turno = _turno(db_session, estado="cancelado")
    db_session.add(
        Notificacion(
            turno_id=turno.id,
            tipo="cancelacion",
            estado="pendiente",
            intentos=0,
            payload={"tipo": "cancelacion"},
        )
    )
    db_session.add(
        AuditoriaTurno(
            turno_id=turno.id,
            actor_id=None,
            accion="cancelar",
            detalle={"actor": "paciente"},
        )
    )
    db_session.flush()
    db_session.refresh(turno)
    updated_previo = turno.updated_at

    resp = client.delete(_url(turno), params=_params(turno))

    assert resp.status_code == 422
    assert resp.json()["detail"]["codigo"] == "turno_ya_cancelado"
    fila = db_session.query(Turno).filter(Turno.id == turno.id).one()
    assert fila.updated_at == updated_previo
    assert (
        db_session.query(Notificacion)
        .filter(Notificacion.turno_id == turno.id)
        .count()
        == 1
    )
    assert (
        db_session.query(AuditoriaTurno)
        .filter(AuditoriaTurno.turno_id == turno.id)
        .count()
        == 1
    )


@pytest.mark.parametrize("estado", ["atendido", "ausente"])
def test_cancelacion_turno_atendido_o_ausente_422(client, db_session, estado):
    """# AC R4 S3: `atendido`/`ausente` → 422 `turno_no_cancelable`."""
    from app.models.turno import TurnoEstado

    _, _, turno = _turno(db_session, estado=estado)

    resp = client.delete(_url(turno), params=_params(turno))

    assert resp.status_code == 422
    assert resp.json()["detail"]["codigo"] == "turno_no_cancelable"
    assert _estado(db_session, turno) == TurnoEstado(estado)


def test_cancelacion_403_no_revela_datos_ni_existencia(client, db_session):
    """# AC R7 S2: el 403 es idéntico para turno existente e inexistente."""
    _, _, turno = _turno(db_session)

    existente = client.delete(_url(turno), params={"token": str(uuid.uuid4())})
    inexistente = client.delete(
        f"/api/turnos/{uuid.uuid4()}", params={"token": str(uuid.uuid4())}
    )

    assert existente.status_code == inexistente.status_code == 403
    assert existente.json() == inexistente.json() == {"detail": "No autorizado"}
    assert set(existente.json()) == {"detail"}

# --- §4 Notificación de cancelación ----------------------------------------


def test_cancelacion_encola_mail_cancelacion_pendiente(client, db_session):
    """# AC R5 S1: exactamente una `Notificacion cancelacion` pendiente."""
    from app.models.notificacion import NotifEstado, Notificacion, NotifTipo
    from app.modules.notificaciones.payload import REQUIRED_KEYS

    _, _, turno = _turno(db_session)

    resp = client.delete(_url(turno), params=_params(turno))

    assert resp.status_code == 200
    assert resp.json()["notificaciones_encoladas"] is True
    notifs = (
        db_session.query(Notificacion)
        .filter(Notificacion.turno_id == turno.id)
        .all()
    )
    assert len(notifs) == 1
    notif = notifs[0]
    assert notif.tipo == NotifTipo.cancelacion
    assert notif.canal.value == "mail"
    assert notif.estado == NotifEstado.pendiente
    assert notif.intentos == 0
    assert notif.enviada_at is None

    payload = notif.payload
    assert set(payload) == set(REQUIRED_KEYS)
    assert len(payload) == 11
    assert payload["tipo"] == "cancelacion"
    assert payload["turno_id"] == str(turno.id)
    assert payload["token_cancelacion"] == str(turno.token_cancelacion)
    assert payload["duracion_min"] == 30
    assert payload["cancel_url"].endswith(
        f"/cancelar?token={turno.token_cancelacion}"
    )
    enviar_en = payload["enviar_en"]
    assert isinstance(enviar_en, str)
    assert datetime.fromisoformat(enviar_en).utcoffset() == timedelta(0)
    assert datetime.fromisoformat(enviar_en) == NOW.astimezone(UTC)
    for prohibido in ("dni", "telefono", "obra_social"):
        assert prohibido not in payload


def test_cancelacion_encolado_falla_no_bloquea_200(
    client, db_session, monkeypatch
):
    """# AC R5 S2 / regla dura 5: fallo del encolado no deshace la cancelación."""
    from app.models.auditoria import AuditoriaTurno
    from app.models.notificacion import Notificacion
    from app.models.turno import TurnoEstado
    from app.modules.turnos import cancellation_service

    class _BoomNotificacion:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("fallo simulado de encolado")

    monkeypatch.setattr(
        cancellation_service, "Notificacion", _BoomNotificacion
    )
    _, _, turno = _turno(db_session)

    resp = client.delete(_url(turno), params=_params(turno))

    assert resp.status_code == 200
    assert resp.json()["notificaciones_encoladas"] is False
    assert _estado(db_session, turno) == TurnoEstado.cancelado
    auditoria = (
        db_session.query(AuditoriaTurno)
        .filter(AuditoriaTurno.turno_id == turno.id)
        .one()
    )
    assert auditoria.detalle["notificaciones_encoladas"] is False
    assert (
        db_session.query(Notificacion)
        .filter(Notificacion.turno_id == turno.id)
        .count()
        == 0
    )


def test_cancelacion_no_envia_smtp_ni_crea_otra_cola(
    client, db_session, monkeypatch
):
    """# AC R5 S3: C-06 solo encola; no invoca SMTP ni otra cola."""
    from app.models.notificacion import NotifEstado, Notificacion
    from app.modules.notificaciones import sender as sender_module

    def _prohibido(*args, **kwargs):
        raise AssertionError("C-06 no debe enviar SMTP")

    monkeypatch.setattr(sender_module.MailSender, "send", _prohibido)
    _, _, turno = _turno(db_session)

    resp = client.delete(_url(turno), params=_params(turno))

    assert resp.status_code == 200
    notifs = (
        db_session.query(Notificacion)
        .filter(Notificacion.turno_id == turno.id)
        .all()
    )
    assert len(notifs) == 1
    assert notifs[0].estado == NotifEstado.pendiente
    assert notifs[0].enviada_at is None
    assert notifs[0].error is None

# --- §5 Auditoría append-only ----------------------------------------------


def test_cancelacion_escribe_auditoria_actor_paciente(client, db_session):
    """# AC R6 S1: auditoría `cancelar`, actor NULL, detalle paciente/token."""
    from app.models.auditoria import AuditoriaTurno

    _, _, turno = _turno(db_session)

    resp = client.delete(_url(turno), params=_params(turno))

    assert resp.status_code == 200
    auditorias = (
        db_session.query(AuditoriaTurno)
        .filter(AuditoriaTurno.turno_id == turno.id)
        .all()
    )
    assert len(auditorias) == 1
    auditoria = auditorias[0]
    assert auditoria.accion == "cancelar"
    assert auditoria.actor_id is None
    detalle = auditoria.detalle
    assert detalle["actor"] == "paciente"
    assert detalle["credencial"] == "token_cancelacion"
    assert detalle["estado_previo"] == "reservado"
    assert detalle["duracion_min"] == 30
    assert detalle["notificaciones_encoladas"] is True
    for clave in ("inicio", "fin"):
        assert isinstance(detalle[clave], str)
        assert datetime.fromisoformat(detalle[clave]).utcoffset() == timedelta(0)
    assert datetime.fromisoformat(detalle["inicio"]) == turno.inicio.astimezone(
        UTC
    )


@pytest.mark.parametrize(
    "caso",
    ["token-invalido", "fuera-de-plazo", "no-cancelable"],
    ids=["403-token", "422-plazo", "422-estado"],
)
def test_cancelacion_400_422_no_escriben_auditoria(
    client, db_session, caso
):
    """# AC R6 S2: una solicitud rechazada no agrega filas de auditoría."""
    from app.models.auditoria import AuditoriaTurno

    if caso == "token-invalido":
        _, _, turno = _turno(db_session)
        resp = client.delete(_url(turno), params={"token": str(uuid.uuid4())})
        assert resp.status_code == 403
    elif caso == "fuera-de-plazo":
        _, _, turno = _turno(db_session, offset=timedelta(hours=1))
        resp = client.delete(_url(turno), params=_params(turno))
        assert resp.status_code == 422
    else:
        _, _, turno = _turno(db_session, estado="atendido")
        resp = client.delete(_url(turno), params=_params(turno))
        assert resp.status_code == 422

    assert (
        db_session.query(AuditoriaTurno)
        .filter(AuditoriaTurno.turno_id == turno.id)
        .count()
        == 0
    )


def test_cancelacion_auditoria_no_guarda_token(
    client, db_session, caplog
):
    """# AC R6 S3: el token no aparece en `detalle` ni en logs."""
    from app.models.auditoria import AuditoriaTurno

    caplog.set_level(logging.DEBUG)
    _, _, turno = _turno(db_session)
    token = str(turno.token_cancelacion)

    resp = client.delete(_url(turno), params=_params(turno))

    assert resp.status_code == 200
    auditoria = (
        db_session.query(AuditoriaTurno)
        .filter(AuditoriaTurno.turno_id == turno.id)
        .one()
    )
    assert token not in str(auditoria.detalle)
    logs_app = "\n".join(
        registro.getMessage()
        for registro in caplog.records
        if registro.name.startswith("app")
    )
    assert token not in logs_app

# --- §6 Rate limit del endpoint público ------------------------------------


def _consumir_cupo_cancelacion(ip: str, veces: int) -> None:
    """Consume `veces` intentos del cupo de esa IP (reloj fake del fixture)."""
    from app.core import ratelimit

    clave = f"turnos-cancelacion:{ip}"
    for _ in range(veces):
        pasa, _ = ratelimit.check_public_rate_limit(clave, limit=10, window_s=60)
        assert pasa, "el cupo se agotó antes de lo esperado"


def test_cancelacion_rate_limit_dentro_limite_200(
    client_rate_limit, db_session
):
    """# AC R8 S1: dentro del límite responde 200 y consume cupo."""
    from app.core import ratelimit

    cliente, _, ip = client_rate_limit
    _, _, turno = _turno(db_session)

    resp = cliente.delete(_url(turno), params=_params(turno))

    assert resp.status_code == 200
    _consumir_cupo_cancelacion(ip["valor"], 9)
    pasa, _ = ratelimit.check_public_rate_limit(
        f"turnos-cancelacion:{ip['valor']}", limit=10, window_s=60
    )
    assert pasa is False


def test_cancelacion_rate_limit_exceso_429_sin_cancelar(
    client_rate_limit, db_session
):
    """# AC R8 S2: IP agotada → 429 con `Retry-After`, turno sin cambios."""
    from app.models.notificacion import Notificacion

    cliente, _, ip = client_rate_limit
    _, _, turno = _turno(db_session)
    _consumir_cupo_cancelacion(ip["valor"], 10)

    resp = cliente.delete(_url(turno), params=_params(turno))

    assert resp.status_code == 429
    assert int(resp.headers["Retry-After"]) >= 1
    assert _estado(db_session, turno).value == "reservado"
    assert (
        db_session.query(Notificacion)
        .filter(Notificacion.turno_id == turno.id)
        .count()
        == 0
    )


def test_cancelacion_rate_limit_decimo_pasa_undecimo_429(
    client_rate_limit, db_session
):
    """# AC R8 S3: el intento 10 se evalúa; el 11 → 429 antes de la credencial."""
    cliente, _, ip = client_rate_limit
    _, _, turno = _turno(db_session)
    _consumir_cupo_cancelacion(ip["valor"], 9)

    decimo = cliente.delete(_url(turno), params=_params(turno))
    undecimo = cliente.delete(_url(turno), params={"token": str(uuid.uuid4())})

    assert decimo.status_code == 200
    assert undecimo.status_code == 429
    assert int(undecimo.headers["Retry-After"]) >= 1
