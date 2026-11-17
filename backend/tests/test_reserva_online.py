"""Reserva online pública (API/DB, DB/servicio y concurrencia real, PG real).

# AC reserva-online (R1-R5/R8; reloj inyectable, datos ficticios).
"""

import threading
import time as time_module
import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
LUNES = date(2026, 10, 19)
NOW = datetime(2026, 10, 19, 8, 0, tzinfo=TZ)


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


@pytest.fixture
def client_commit(test_engine):
    """TestClient con sesión de request independiente y setup ya commiteado.

    El servicio hace `rollback()` en los 409 (D-12); por eso el setup no puede
    vivir en la transacción de `db_session` (sería revertido con ella).
    """
    from sqlalchemy.orm import Session

    from app.core import ratelimit
    from app.db.session import get_db
    from app.main import app
    from app.modules.turnos.router import get_now_provider

    ratelimit.reset()
    ratelimit.reset_public()

    def _override():
        sesion = Session(bind=test_engine)
        try:
            yield sesion
        finally:
            sesion.close()

    app.dependency_overrides[get_db] = _override
    app.dependency_overrides[get_now_provider] = lambda: lambda: NOW
    with TestClient(app, base_url="https://testserver") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def reloj(client):
    """Reloj fijo inyectado en el router (D-10)."""
    from app.main import app
    from app.modules.turnos.router import get_now_provider

    app.dependency_overrides[get_now_provider] = lambda: lambda: NOW
    return NOW


@pytest.fixture
def client_rate_limit(db_session, monkeypatch):
    """TestClient con reloj fake y IP inyectable (R7, sin sleeps).

    `time.monotonic` se parchea en el módulo global que usa `ratelimit`; la IP
    se toma de un holder mutable para simular clientes distintos. Un reloj
    congelado en `1_000.0` deja `Retry-After` determinista.
    """
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
    app.dependency_overrides[get_now_provider] = lambda: lambda: NOW
    app.dependency_overrides[get_client_ip] = lambda: ip["valor"]
    with TestClient(app, base_url="https://testserver") as c:
        yield c, ahora, ip
    app.dependency_overrides.clear()


def _consumir_cupo(ip: str, veces: int) -> None:
    """Consume `veces` reservas del cupo de esa IP (reloj fake del fixture)."""
    from app.core import ratelimit

    clave = f"turnos-publico:{ip}"
    for _ in range(veces):
        pasa, _ = ratelimit.check_public_rate_limit(clave, limit=10, window_s=60)
        assert pasa, "el cupo se agotó antes de lo esperado"


def _prof(db_session, duracion=30, **kw):
    from tests.conftest import mk_profesional

    return mk_profesional(db_session, duracion_default_min=duracion, **kw)


def _ventana(db_session, prof_id, dia=0, desde=9, hasta=11):
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


def _paciente(**over):
    base = {
        "nombre": "Paciente Ficticio",
        "dni": "30999001",
        "telefono": "+5491100000001",
        "obra_social": "OS Ficticia",
        "email": "paciente@ficticio.test",
    }
    base.update(over)
    return base


def _body(prof_id, inicio="2026-10-19T09:00:00-03:00", **over):
    body = {
        "profesional_id": str(prof_id),
        "inicio": inicio,
        "paciente": _paciente(),
    }
    body.update(over)
    return body


def _turnos(db_session):
    from app.models.turno import Turno

    return db_session.query(Turno).count()


def _turnos_prof(db_session, prof_id):
    from app.models.turno import Turno

    return db_session.query(Turno).filter(Turno.profesional_id == prof_id).count()


@pytest.mark.parametrize(
    "inicio",
    ["2026-10-19T08:00:00-03:00", "2026-10-19T07:59:00-03:00"],
    ids=["igual-a-now", "anterior-a-now"],
)
def test_reserva_inicio_no_futuro_400(client, db_session, reloj, inicio):
    """# AC R2 S6: `inicio <= now` → 400 en `inicio` y sin filas."""
    prof = _prof(db_session)
    resp = client.post("/api/turnos", json=_body(prof.id, inicio=inicio))
    assert resp.status_code == 400
    assert any(d["campo"] == "inicio" for d in resp.json()["detail"])
    assert _turnos(db_session) == 0


def test_reserva_duracion_no_multiplo_400(client, db_session, reloj):
    """# AC R3 S1: `duracion_min` no múltiplo → 400 único en `duracion_min`."""
    prof = _prof(db_session, duracion=30)
    resp = client.post("/api/turnos", json=_body(prof.id, duracion_min=40))
    assert resp.status_code == 400
    detalle = resp.json()["detail"]
    assert len(detalle) == 1
    assert detalle[0]["campo"] == "duracion_min"
    assert detalle[0]["tipo"] == "duracion_no_multiplo_granularidad"
    assert _turnos(db_session) == 0


@pytest.mark.parametrize("duracion", [0, -30], ids=["cero", "negativa"])
def test_reserva_duracion_cero_o_negativa_400(client, db_session, reloj, duracion):
    """# AC R3 S2: duración 0/negativa → 400 único en `duracion_min`."""
    prof = _prof(db_session, duracion=30)
    resp = client.post("/api/turnos", json=_body(prof.id, duracion_min=duracion))
    assert resp.status_code == 400
    detalle = resp.json()["detail"]
    assert len(detalle) == 1
    assert detalle[0]["campo"] == "duracion_min"
    assert _turnos(db_session) == 0


def test_reserva_valida_crea_turno_201(client, db_session, reloj):
    """# AC R1 S1: reserva feliz crea turno reservado/online y responde 201."""
    from app.models.paciente import Paciente
    from app.models.turno import Turno, TurnoEstado, TurnoOrigen

    prof = _prof(db_session, duracion=30)
    _ventana(db_session, prof.id, desde=9, hasta=11)

    resp = client.post("/api/turnos", json=_body(prof.id))

    assert resp.status_code == 201
    cuerpo = resp.json()
    assert cuerpo["estado"] == "reservado"
    assert cuerpo["duracion_min"] == 30
    assert cuerpo["notificaciones_encoladas"] is True
    turno = db_session.query(Turno).one()
    assert turno.estado == TurnoEstado.reservado
    assert turno.origen == TurnoOrigen.online
    assert turno.duracion_min == 30
    assert turno.inicio == datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
    assert turno.fin == turno.inicio + timedelta(minutes=30)
    assert turno.token_cancelacion is not None
    assert db_session.query(Paciente).count() == 1


def test_reserva_sin_duracion_usa_default_201(client, db_session, reloj):
    """# AC R1 S2: sin `duracion_min` usa `duracion_default_min=45`."""
    from app.models.turno import Turno

    prof = _prof(db_session, duracion=45)
    _ventana(db_session, prof.id, desde=9, hasta=12)

    resp = client.post("/api/turnos", json=_body(prof.id))

    assert resp.status_code == 201
    assert resp.json()["duracion_min"] == 45
    turno = db_session.query(Turno).one()
    assert turno.duracion_min == 45
    assert turno.fin == turno.inicio + timedelta(minutes=45)


def test_reserva_dni_existente_actualiza_contacto_sin_duplicar(
    client, db_session, reloj
):
    """# AC R1 S3: mismo DNI actualiza contacto y reutiliza la fila."""
    from app.models.paciente import Paciente
    from app.models.turno import Turno

    prof = _prof(db_session, duracion=30)
    _ventana(db_session, prof.id, desde=9, hasta=11)
    previo = Paciente(
        nombre="Paciente Previo",
        dni="30999001",
        telefono="+5491100000000",
        obra_social="OS Vieja",
        email="viejo@ficticio.test",
    )
    db_session.add(previo)
    db_session.flush()
    paciente_id = previo.id

    resp = client.post(
        "/api/turnos",
        json=_body(
            prof.id,
            paciente=_paciente(telefono="+5491100000099", email="nuevo@ficticio.test"),
        ),
    )

    assert resp.status_code == 201
    filas = db_session.query(Paciente).filter(Paciente.dni == "30999001").all()
    assert len(filas) == 1
    assert filas[0].id == paciente_id
    db_session.refresh(filas[0])
    assert filas[0].telefono == "+5491100000099"
    assert filas[0].email == "nuevo@ficticio.test"
    assert db_session.query(Turno).one().paciente_id == paciente_id


def test_reserva_paciente_inactivo_no_reactiva_201(client, db_session, reloj):
    """# AC R1 S4: paciente `activo=false` reserva sin reactivarse."""
    from app.models.paciente import Paciente

    prof = _prof(db_session, duracion=30)
    _ventana(db_session, prof.id, desde=9, hasta=11)
    previo = Paciente(
        nombre="Paciente Inactivo",
        dni="30999003",
        telefono="+5491100000000",
        obra_social="OS Ficticia",
        email="inactivo@ficticio.test",
        activo=False,
    )
    db_session.add(previo)
    db_session.flush()

    resp = client.post(
        "/api/turnos",
        json=_body(
            prof.id,
            paciente=_paciente(
                dni="30999003",
                telefono="+5491100000077",
                email="reactivado@ficticio.test",
            ),
        ),
    )

    assert resp.status_code == 201
    filas = db_session.query(Paciente).filter(Paciente.dni == "30999003").all()
    assert len(filas) == 1
    db_session.refresh(filas[0])
    assert filas[0].activo is False
    assert filas[0].telefono == "+5491100000077"
    assert filas[0].email == "reactivado@ficticio.test"


def test_reserva_escribe_auditoria_crear(db_session):
    """# AC R1 S5: auditoría `crear`, actor NULL, detalle ISO-8601 UTC."""
    from app.models.auditoria import AuditoriaTurno
    from app.modules.turnos import service
    from app.modules.turnos.schemas import TurnoCreate

    prof = _prof(db_session, duracion=30)
    _ventana(db_session, prof.id, desde=9, hasta=11)
    data = TurnoCreate(**_body(prof.id))

    respuesta = service.reservar(db_session, data, now_provider=lambda: NOW)

    audit = db_session.query(AuditoriaTurno).one()
    assert str(audit.turno_id) == str(respuesta["id"])
    assert audit.accion == "crear"
    assert audit.actor_id is None
    detalle = audit.detalle
    assert detalle["origen"] == "online"
    assert detalle["profesional_id"] == str(prof.id)
    assert detalle["duracion_min"] == 30
    assert detalle["notificaciones_encoladas"] is True
    assert isinstance(detalle["inicio"], str)
    assert isinstance(detalle["fin"], str)
    assert datetime.fromisoformat(detalle["inicio"]) == datetime(
        2026, 10, 19, 12, 0, tzinfo=UTC
    )
    assert datetime.fromisoformat(detalle["fin"]) == datetime(
        2026, 10, 19, 12, 30, tzinfo=UTC
    )


def test_reserva_devuelve_token_y_cancel_url_normalizada(
    client, db_session, reloj, monkeypatch
):
    """# AC R1 S6: token UUID y `cancel_url` sin doble barra."""
    monkeypatch.setenv("FRONTEND_URL", "https://app.test/")
    prof = _prof(db_session, duracion=30)
    _ventana(db_session, prof.id, desde=9, hasta=11)

    resp = client.post("/api/turnos", json=_body(prof.id))

    assert resp.status_code == 201
    cuerpo = resp.json()
    token = uuid.UUID(cuerpo["token_cancelacion"])
    assert cuerpo["cancel_url"] == (
        f"https://app.test/cancelar?token={token}&id={cuerpo['id']}"
    )
    assert cuerpo["notificaciones_encoladas"] is True


def test_reserva_anticipacion_mayor_24h_encola_tres(db_session):
    """# AC R1 S7: >24h encola confirmación + recordatorios 24h y 2h."""
    from app.models.notificacion import NotifEstado, Notificacion
    from app.modules.turnos import service
    from app.modules.turnos.schemas import TurnoCreate

    prof = _prof(db_session, duracion=30)
    _ventana(db_session, prof.id, dia=1, desde=9, hasta=11)
    inicio = datetime(2026, 10, 20, 9, 0, tzinfo=TZ)
    data = TurnoCreate(**_body(prof.id, inicio=inicio.isoformat()))

    respuesta = service.reservar(db_session, data, now_provider=lambda: NOW)

    notifs = (
        db_session.query(Notificacion)
        .filter(Notificacion.turno_id == respuesta["id"])
        .all()
    )
    por_tipo = {n.tipo.value: n for n in notifs}
    assert set(por_tipo) == {
        "confirmacion",
        "recordatorio_24h",
        "recordatorio_2h",
    }
    assert all(n.estado == NotifEstado.pendiente for n in notifs)
    for n in notifs:
        assert isinstance(n.payload["enviar_en"], str)
        datetime.fromisoformat(n.payload["enviar_en"])
    assert datetime.fromisoformat(
        por_tipo["confirmacion"].payload["enviar_en"]
    ) == NOW.astimezone(UTC)
    assert datetime.fromisoformat(
        por_tipo["recordatorio_24h"].payload["enviar_en"]
    ) == (inicio - timedelta(hours=24)).astimezone(UTC)
    assert datetime.fromisoformat(por_tipo["recordatorio_2h"].payload["enviar_en"]) == (
        inicio - timedelta(hours=2)
    ).astimezone(UTC)


def test_reserva_anticipacion_2_a_24h_omite_24h(db_session):
    """# AC R1 S8: entre 2h y 24h encola confirmación + recordatorio 2h."""
    from app.models.notificacion import Notificacion
    from app.modules.turnos import service
    from app.modules.turnos.schemas import TurnoCreate

    prof = _prof(db_session, duracion=30)
    _ventana(db_session, prof.id, desde=9, hasta=22)
    inicio = datetime(2026, 10, 19, 20, 0, tzinfo=TZ)
    data = TurnoCreate(**_body(prof.id, inicio=inicio.isoformat()))

    respuesta = service.reservar(db_session, data, now_provider=lambda: NOW)

    notifs = (
        db_session.query(Notificacion)
        .filter(Notificacion.turno_id == respuesta["id"])
        .all()
    )
    assert {n.tipo.value for n in notifs} == {
        "confirmacion",
        "recordatorio_2h",
    }


def test_reserva_encolado_falla_no_bloquea_201(client, db_session, reloj, monkeypatch):
    """# AC R6 S1: fallo del encolado no bloquea la reserva (201)."""
    from app.models.auditoria import AuditoriaTurno
    from app.models.notificacion import Notificacion
    from app.models.turno import Turno
    from app.modules.turnos import service

    class _BoomNotificacion:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("fallo simulado de encolado")

    monkeypatch.setattr(service, "Notificacion", _BoomNotificacion)
    prof = _prof(db_session, duracion=30)
    _ventana(db_session, prof.id, desde=9, hasta=11)

    resp = client.post("/api/turnos", json=_body(prof.id))

    assert resp.status_code == 201
    assert resp.json()["notificaciones_encoladas"] is False
    assert db_session.query(Turno).count() == 1
    auditoria = db_session.query(AuditoriaTurno).one()
    assert auditoria.detalle["notificaciones_encoladas"] is False
    assert db_session.query(Notificacion).count() == 0


def test_reserva_notificaciones_pendientes_para_worker(db_session):
    """# AC R6 S2: quedan `pendiente`, `intentos=0`, `enviada_at=NULL`."""
    from app.models.notificacion import NotifEstado, Notificacion
    from app.modules.turnos import service
    from app.modules.turnos.schemas import TurnoCreate

    prof = _prof(db_session, duracion=30)
    _ventana(db_session, prof.id, dia=1, desde=9, hasta=11)
    inicio = datetime(2026, 10, 20, 9, 0, tzinfo=TZ)
    data = TurnoCreate(**_body(prof.id, inicio=inicio.isoformat()))

    respuesta = service.reservar(db_session, data, now_provider=lambda: NOW)

    notifs = (
        db_session.query(Notificacion)
        .filter(Notificacion.turno_id == respuesta["id"])
        .all()
    )
    assert notifs
    for notif in notifs:
        assert notif.estado == NotifEstado.pendiente
        assert notif.intentos == 0
        assert notif.enviada_at is None
        assert isinstance(notif.payload["enviar_en"], str)
        datetime.fromisoformat(notif.payload["enviar_en"])


def test_reserva_anticipacion_menor_2h_solo_confirmacion(db_session):
    """# AC R6 S3: <2h encola solo la confirmación."""
    from app.models.notificacion import Notificacion
    from app.modules.turnos import service
    from app.modules.turnos.schemas import TurnoCreate

    prof = _prof(db_session, duracion=30)
    _ventana(db_session, prof.id, desde=9, hasta=11)
    inicio = datetime(2026, 10, 19, 9, 0, tzinfo=TZ)
    data = TurnoCreate(**_body(prof.id, inicio=inicio.isoformat()))

    respuesta = service.reservar(db_session, data, now_provider=lambda: NOW)

    notifs = (
        db_session.query(Notificacion)
        .filter(Notificacion.turno_id == respuesta["id"])
        .all()
    )
    assert {n.tipo.value for n in notifs} == {"confirmacion"}


def test_reserva_anticipacion_exacta_24h_omite_recordatorio_24h(db_session):
    """# AC R6 S4: `inicio - 24h == now` → confirmación + recordatorio 2h."""
    from app.models.notificacion import Notificacion
    from app.modules.turnos import service
    from app.modules.turnos.schemas import TurnoCreate

    prof = _prof(db_session, duracion=30)
    _ventana(db_session, prof.id, dia=1, desde=8, hasta=10)
    inicio = datetime(2026, 10, 20, 8, 0, tzinfo=TZ)
    data = TurnoCreate(**_body(prof.id, inicio=inicio.isoformat()))

    respuesta = service.reservar(db_session, data, now_provider=lambda: NOW)

    notifs = (
        db_session.query(Notificacion)
        .filter(Notificacion.turno_id == respuesta["id"])
        .all()
    )
    assert {n.tipo.value for n in notifs} == {
        "confirmacion",
        "recordatorio_2h",
    }


def test_reserva_anticipacion_exacta_2h_omite_recordatorio_2h(db_session):
    """# AC R6 S5: `inicio - 2h == now` → solo confirmación."""
    from app.models.notificacion import Notificacion
    from app.modules.turnos import service
    from app.modules.turnos.schemas import TurnoCreate

    prof = _prof(db_session, duracion=30)
    _ventana(db_session, prof.id, desde=9, hasta=11)
    inicio = datetime(2026, 10, 19, 10, 0, tzinfo=TZ)
    data = TurnoCreate(**_body(prof.id, inicio=inicio.isoformat()))

    respuesta = service.reservar(db_session, data, now_provider=lambda: NOW)

    notifs = (
        db_session.query(Notificacion)
        .filter(Notificacion.turno_id == respuesta["id"])
        .all()
    )
    assert {n.tipo.value for n in notifs} == {"confirmacion"}


def _bloqueo(db_session, prof_id, desde, hasta, motivo="Bloqueo ficticio"):
    from app.models.bloqueo import Bloqueo

    db_session.add(
        Bloqueo(
            profesional_id=prof_id,
            desde=desde,
            hasta=hasta,
            motivo=motivo,
        )
    )
    db_session.flush()


def _turno_activo(db_session, prof_id, inicio, fin, estado="reservado", dni="30999088"):
    from app.models.paciente import Paciente
    from app.models.turno import TurnoEstado
    from tests.conftest import mk_turno

    pac = Paciente(
        nombre="Paciente Ficticio Existente",
        dni=dni,
        telefono="+5491100000088",
        obra_social="OS Ficticia",
        email="existente@ficticio.test",
    )
    db_session.add(pac)
    db_session.flush()
    return mk_turno(
        db_session,
        prof_id,
        pac.id,
        inicio=inicio,
        fin=fin,
        estado=TurnoEstado(estado),
    )


def _bloqueo_commit(test_engine, prof_id, desde, hasta):
    from sqlalchemy.orm import Session

    from app.models.bloqueo import Bloqueo

    sesion = Session(bind=test_engine)
    try:
        sesion.add(
            Bloqueo(
                profesional_id=prof_id,
                desde=desde,
                hasta=hasta,
                motivo="Bloqueo ficticio",
            )
        )
        sesion.commit()
    finally:
        sesion.close()


def _turno_activo_commit(
    test_engine, prof_id, inicio, fin, estado="reservado", dni="30999088"
):
    from sqlalchemy.orm import Session

    from app.models.paciente import Paciente
    from app.models.turno import Turno, TurnoEstado, TurnoOrigen

    sesion = Session(bind=test_engine)
    try:
        pac = Paciente(
            nombre="Paciente Ficticio Existente",
            dni=dni,
            telefono="+5491100000088",
            obra_social="OS Ficticia",
            email="existente@ficticio.test",
        )
        sesion.add(pac)
        sesion.flush()
        sesion.add(
            Turno(
                profesional_id=prof_id,
                paciente_id=pac.id,
                inicio=inicio,
                fin=fin,
                duracion_min=round((fin - inicio).total_seconds() / 60),
                estado=TurnoEstado(estado),
                origen=TurnoOrigen.online,
                token_cancelacion=uuid.uuid4(),
            )
        )
        sesion.commit()
    finally:
        sesion.close()


def _paciente_por_dni(db_session, dni):
    from app.models.paciente import Paciente

    return db_session.query(Paciente).filter(Paciente.dni == dni).count()


def _alternativas(resp):
    return resp.json()["detail"]["alternativos"]


def _inicio_utc(alternativa):
    return datetime.fromisoformat(alternativa["inicio"])


def _setup_concurrencia(test_engine, *, duracion=30, desde=9, hasta=11):
    from sqlalchemy.orm import Session

    from app.models.disponibilidad import Disponibilidad
    from tests.conftest import mk_profesional

    sesion = Session(bind=test_engine)
    try:
        prof = mk_profesional(sesion, duracion_default_min=duracion)
        sesion.add(
            Disponibilidad(
                profesional_id=prof.id,
                dia_semana=0,
                hora_desde=time(desde),
                hora_hasta=time(hasta),
                vigente_desde=date(2026, 1, 1),
                vigente_hasta=date(2026, 12, 31),
            )
        )
        sesion.commit()
        return prof.id
    finally:
        sesion.close()


def _limpiar_concurrencia(test_engine, prof_id, dnis):
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    sesion = Session(bind=test_engine)
    try:
        sesion.execute(
            text(
                "DELETE FROM notificacion WHERE turno_id IN "
                "(SELECT id FROM turno WHERE profesional_id = :prof)"
            ),
            {"prof": str(prof_id)},
        )
        sesion.execute(
            text("DELETE FROM turno WHERE profesional_id = :prof"),
            {"prof": str(prof_id)},
        )
        for dni in dnis:
            sesion.execute(text("DELETE FROM paciente WHERE dni = :dni"), {"dni": dni})
        sesion.execute(
            text("DELETE FROM bloqueo WHERE profesional_id = :prof"),
            {"prof": str(prof_id)},
        )
        sesion.execute(
            text("DELETE FROM disponibilidad WHERE profesional_id = :prof"),
            {"prof": str(prof_id)},
        )
        sesion.execute(
            text("DELETE FROM profesional WHERE id = :prof"),
            {"prof": str(prof_id)},
        )
        sesion.commit()
    finally:
        sesion.close()


def test_reserva_duracion_multiplo_bloque_contiguo_201(client, db_session, reloj):
    """# AC R3 S3: `duracion_min=60` reserva dos slots contiguos."""
    from app.models.turno import Turno

    prof = _prof(db_session)
    _ventana(db_session, prof.id, desde=9, hasta=11)

    resp = client.post(
        "/api/turnos",
        json=_body(prof.id, duracion_min=60),
    )

    assert resp.status_code == 201
    turno = db_session.query(Turno).one()
    assert turno.duracion_min == 60
    assert turno.fin == turno.inicio + timedelta(minutes=60)


def test_reserva_slot_fuera_ventana_409_alternativos(
    client_commit, db_session, test_engine
):
    """# AC R4 S1: fuera de ventana → 409 con alternativos del mismo día."""
    prof_id = _setup_concurrencia(test_engine)
    try:
        resp = client_commit.post(
            "/api/turnos",
            json=_body(prof_id, inicio="2026-10-19T15:00:00-03:00"),
        )

        assert resp.status_code == 409
        detalle = resp.json()["detail"]
        assert detalle["codigo"] == "slot_no_disponible"
        assert [_inicio_utc(a) for a in detalle["alternativos"]] == [
            datetime(2026, 10, 19, 12, 0, tzinfo=UTC),
            datetime(2026, 10, 19, 12, 30, tzinfo=UTC),
            datetime(2026, 10, 19, 13, 0, tzinfo=UTC),
            datetime(2026, 10, 19, 13, 30, tzinfo=UTC),
        ]
        assert _turnos_prof(db_session, prof_id) == 0
        assert _paciente_por_dni(db_session, "30999001") == 0
    finally:
        _limpiar_concurrencia(test_engine, prof_id, ["30999001"])


def test_reserva_slot_bloqueado_409_alternativos(
    client_commit, db_session, test_engine
):
    """# AC R4 S1: bloqueo que cubre el slot → 409 con alternativos."""
    prof_id = _setup_concurrencia(test_engine)
    try:
        _bloqueo_commit(
            test_engine,
            prof_id,
            datetime(2026, 10, 19, 12, 30, tzinfo=UTC),
            datetime(2026, 10, 19, 13, 30, tzinfo=UTC),
        )
        resp = client_commit.post(
            "/api/turnos",
            json=_body(prof_id, inicio="2026-10-19T10:00:00-03:00"),
        )

        assert resp.status_code == 409
        assert resp.json()["detail"]["codigo"] == "slot_no_disponible"
        assert [_inicio_utc(a) for a in _alternativas(resp)] == [
            datetime(2026, 10, 19, 12, 0, tzinfo=UTC),
            datetime(2026, 10, 19, 13, 30, tzinfo=UTC),
        ]
        assert _turnos_prof(db_session, prof_id) == 0
        assert _paciente_por_dni(db_session, "30999001") == 0
    finally:
        _limpiar_concurrencia(test_engine, prof_id, ["30999001"])


def test_reserva_inicio_no_alineado_409(client_commit, db_session, test_engine):
    """# AC R4 S2: `inicio` fuera de la grilla → 409 con alternativos alineados."""
    prof_id = _setup_concurrencia(test_engine)
    try:
        resp = client_commit.post(
            "/api/turnos",
            json=_body(prof_id, inicio="2026-10-19T09:15:00-03:00"),
        )

        assert resp.status_code == 409
        assert resp.json()["detail"]["codigo"] == "slot_no_disponible"
        alts = _alternativas(resp)
        assert alts
        for alternativa in alts:
            local = _inicio_utc(alternativa).astimezone(TZ)
            assert local.minute % 30 == 0
        assert _turnos_prof(db_session, prof_id) == 0
        assert _paciente_por_dni(db_session, "30999001") == 0
    finally:
        _limpiar_concurrencia(test_engine, prof_id, ["30999001"])


def test_reserva_bloque_contiguo_segundo_slot_ocupado_409(
    client_commit, db_session, test_engine
):
    """# AC R4 S3: el segundo slot del bloque está ocupado → 409 sin filas."""
    prof_id = _setup_concurrencia(test_engine)
    try:
        _turno_activo_commit(
            test_engine,
            prof_id,
            datetime(2026, 10, 19, 12, 30, tzinfo=UTC),
            datetime(2026, 10, 19, 13, 0, tzinfo=UTC),
        )
        resp = client_commit.post(
            "/api/turnos",
            json=_body(prof_id, duracion_min=60),
        )

        assert resp.status_code == 409
        assert resp.json()["detail"]["codigo"] == "slot_no_disponible"
        assert [_inicio_utc(a) for a in _alternativas(resp)] == [
            datetime(2026, 10, 19, 13, 0, tzinfo=UTC)
        ]
        assert _turnos_prof(db_session, prof_id) == 1
        assert _paciente_por_dni(db_session, "30999001") == 0
    finally:
        _limpiar_concurrencia(test_engine, prof_id, ["30999001", "30999088"])


def test_reserva_borde_ventana_fin_hasta_201(client, db_session, reloj):
    """# AC R4 S4: el slot termina exactamente en `hora_hasta` (half-open)."""
    from app.models.turno import Turno

    prof = _prof(db_session)
    _ventana(db_session, prof.id, desde=9, hasta=10)

    resp = client.post(
        "/api/turnos",
        json=_body(prof.id, inicio="2026-10-19T09:30:00-03:00"),
    )

    assert resp.status_code == 201
    turno = db_session.query(Turno).one()
    assert turno.fin == datetime(2026, 10, 19, 13, 0, tzinfo=UTC)


def test_reserva_alternativos_mismo_dia_duracion_pedida(
    client_commit, db_session, test_engine
):
    """# AC R4 S5: alternativos del mismo día, sin el pedido, +60, máx. 5."""
    prof_id = _setup_concurrencia(test_engine, desde=9, hasta=13)
    try:
        inicio = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
        _turno_activo_commit(
            test_engine,
            prof_id,
            inicio,
            inicio + timedelta(minutes=60),
        )
        resp = client_commit.post(
            "/api/turnos",
            json=_body(prof_id, duracion_min=60),
        )

        assert resp.status_code == 409
        assert resp.json()["detail"]["codigo"] == "slot_ocupado"
        alts = _alternativas(resp)
        assert len(alts) == 5
        inicios = [_inicio_utc(a) for a in alts]
        assert inicios == sorted(inicios)
        assert inicios == [
            datetime(2026, 10, 19, 13, 0, tzinfo=UTC),
            datetime(2026, 10, 19, 13, 30, tzinfo=UTC),
            datetime(2026, 10, 19, 14, 0, tzinfo=UTC),
            datetime(2026, 10, 19, 14, 30, tzinfo=UTC),
            datetime(2026, 10, 19, 15, 0, tzinfo=UTC),
        ]
        for alternativa in alts:
            ini = _inicio_utc(alternativa)
            assert ini.astimezone(TZ).date() == date(2026, 10, 19)
            assert ini != inicio
            assert datetime.fromisoformat(alternativa["fin"]) == ini + timedelta(
                minutes=60
            )
            assert alternativa["duracion_min"] == 60
            assert ini.astimezone(TZ).minute % 30 == 0
    finally:
        _limpiar_concurrencia(test_engine, prof_id, ["30999001", "30999088"])


def test_reserva_turno_cancelado_no_bloquea_201(client, db_session, reloj):
    """# AC R4 S6: un turno cancelado no ocupa el slot."""
    from app.models.turno import Turno

    prof = _prof(db_session)
    _ventana(db_session, prof.id, desde=9, hasta=11)
    _turno_activo(
        db_session,
        prof.id,
        datetime(2026, 10, 19, 12, 0, tzinfo=UTC),
        datetime(2026, 10, 19, 12, 30, tzinfo=UTC),
        estado="cancelado",
    )

    resp = client.post("/api/turnos", json=_body(prof.id))

    assert resp.status_code == 201
    assert db_session.query(Turno).count() == 2


def test_reserva_slot_ocupado_409_con_alternativos(
    client_commit, db_session, test_engine
):
    """# AC R5 S1: slot ocupado → `slot_ocupado`, alternativos y sin paciente."""
    prof_id = _setup_concurrencia(test_engine)
    try:
        _turno_activo_commit(
            test_engine,
            prof_id,
            datetime(2026, 10, 19, 12, 0, tzinfo=UTC),
            datetime(2026, 10, 19, 12, 30, tzinfo=UTC),
        )
        resp = client_commit.post("/api/turnos", json=_body(prof_id))

        assert resp.status_code == 409
        detalle = resp.json()["detail"]
        assert detalle["codigo"] == "slot_ocupado"
        assert [_inicio_utc(a) for a in detalle["alternativos"]] == [
            datetime(2026, 10, 19, 12, 30, tzinfo=UTC),
            datetime(2026, 10, 19, 13, 0, tzinfo=UTC),
            datetime(2026, 10, 19, 13, 30, tzinfo=UTC),
        ]
        assert _turnos_prof(db_session, prof_id) == 1
        assert _paciente_por_dni(db_session, "30999001") == 0
    finally:
        _limpiar_concurrencia(test_engine, prof_id, ["30999001", "30999088"])


def test_reserva_segunda_transaccion_espera_lock_409(test_engine):
    """# AC R5 S2: la 2.ª tx espera el FOR UPDATE y termina en 409, no 500."""
    from sqlalchemy.orm import Session

    from app.models.paciente import Paciente
    from app.models.profesional import Profesional
    from app.models.turno import Turno, TurnoEstado, TurnoOrigen
    from app.modules.turnos import service
    from app.modules.turnos.schemas import TurnoCreate

    inicio = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)  # 09:00 local
    fin = inicio + timedelta(minutes=30)
    dni_a = f"3{uuid.uuid4().int % 10**9:09d}"
    dni_b = f"4{uuid.uuid4().int % 10**9:09d}"
    prof_id = _setup_concurrencia(test_engine)

    conn_a = test_engine.connect()
    txn_a = conn_a.begin()
    sesion_a = Session(bind=conn_a)
    resultado: dict = {}
    try:
        sesion_a.query(Profesional).filter(
            Profesional.id == prof_id
        ).with_for_update().one()
        pac_a = Paciente(
            nombre="Paciente A",
            dni=dni_a,
            telefono="+5491100000101",
            obra_social="OS Ficticia",
            email="a@ficticio.test",
        )
        sesion_a.add(pac_a)
        sesion_a.flush()
        sesion_a.add(
            Turno(
                profesional_id=prof_id,
                paciente_id=pac_a.id,
                inicio=inicio,
                fin=fin,
                duracion_min=30,
                estado=TurnoEstado.reservado,
                origen=TurnoOrigen.online,
                token_cancelacion=uuid.uuid4(),
            )
        )
        sesion_a.flush()

        arrancada = threading.Event()

        def segunda():
            from fastapi.exceptions import HTTPException
            from sqlalchemy.orm import Session as SessionB

            conn_b = test_engine.connect()
            txn_b = conn_b.begin()
            sesion_b = SessionB(bind=conn_b)
            try:
                data = TurnoCreate(
                    **_body(
                        prof_id,
                        inicio=inicio.isoformat(),
                        paciente=_paciente(dni=dni_b),
                    )
                )
                arrancada.set()
                service.reservar(sesion_b, data, now_provider=lambda: NOW)
                resultado["status"] = 201
            except HTTPException as exc:
                resultado["status"] = exc.status_code
                resultado["detail"] = exc.detail
            except Exception as exc:  # pragma: no cover - diagnóstico
                resultado["status"] = type(exc).__name__
                resultado["detail"] = str(exc)
            finally:
                if txn_b.is_active:
                    txn_b.rollback()
                sesion_b.close()
                conn_b.close()

        hilo = threading.Thread(target=segunda)
        hilo.start()
        assert arrancada.wait(timeout=5)
        threading.Event().wait(0.5)
        assert hilo.is_alive(), "la segunda transacción no esperó el lock"
        txn_a.commit()
        hilo.join(timeout=15)
        assert not hilo.is_alive()
        assert resultado["status"] == 409, resultado
        assert resultado["detail"]["codigo"] == "slot_ocupado"
        assert resultado["detail"]["alternativos"]
        verificacion = Session(bind=test_engine)
        try:
            activos = (
                verificacion.query(Turno)
                .filter(
                    Turno.profesional_id == prof_id,
                    Turno.estado.in_([TurnoEstado.reservado, TurnoEstado.confirmado]),
                )
                .count()
            )
            assert activos == 1
            assert (
                verificacion.query(Paciente).filter(Paciente.dni == dni_b).count() == 0
            )
        finally:
            verificacion.close()
    finally:
        if txn_a.is_active:
            txn_a.rollback()
        sesion_a.close()
        conn_a.close()
        _limpiar_concurrencia(test_engine, prof_id, [dni_a, dni_b])


def test_reserva_exclude_autoridad_final_409(test_engine):
    """# AC R5 S3: EXCLUDE mapea a 409 y revierte el upsert de paciente."""
    from sqlalchemy.orm import Session

    from app.models.paciente import Paciente
    from app.models.turno import Turno, TurnoEstado, TurnoOrigen
    from app.modules.turnos import service
    from app.modules.turnos.schemas import TurnoCreate

    inicio = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
    fin = inicio + timedelta(minutes=30)
    dni_a = f"5{uuid.uuid4().int % 10**9:09d}"
    dni_b = f"6{uuid.uuid4().int % 10**9:09d}"
    prof_id = _setup_concurrencia(test_engine)

    conn_a = test_engine.connect()
    txn_a = conn_a.begin()
    sesion_a = Session(bind=conn_a)
    resultado: dict = {}
    try:
        pac_a = Paciente(
            nombre="Paciente A",
            dni=dni_a,
            telefono="+5491100000111",
            obra_social="OS Ficticia",
            email="a2@ficticio.test",
        )
        sesion_a.add(pac_a)
        sesion_a.flush()
        sesion_a.add(
            Turno(
                profesional_id=prof_id,
                paciente_id=pac_a.id,
                inicio=inicio,
                fin=fin,
                duracion_min=30,
                estado=TurnoEstado.reservado,
                origen=TurnoOrigen.online,
                token_cancelacion=uuid.uuid4(),
            )
        )
        sesion_a.flush()

        arrancada = threading.Event()

        def segunda():
            from fastapi.exceptions import HTTPException
            from sqlalchemy.orm import Session as SessionB

            conn_b = test_engine.connect()
            txn_b = conn_b.begin()
            sesion_b = SessionB(bind=conn_b)
            try:
                data = TurnoCreate(
                    **_body(
                        prof_id,
                        inicio=inicio.isoformat(),
                        paciente=_paciente(dni=dni_b),
                    )
                )
                arrancada.set()
                service.reservar(sesion_b, data, now_provider=lambda: NOW)
                resultado["status"] = 201
            except HTTPException as exc:
                resultado["status"] = exc.status_code
                resultado["detail"] = exc.detail
            except Exception as exc:  # pragma: no cover - diagnóstico
                resultado["status"] = type(exc).__name__
                resultado["detail"] = str(exc)
            finally:
                if txn_b.is_active:
                    txn_b.rollback()
                sesion_b.close()
                conn_b.close()

        hilo = threading.Thread(target=segunda)
        hilo.start()
        assert arrancada.wait(timeout=5)
        threading.Event().wait(0.5)
        assert hilo.is_alive(), "el insert no esperó el EXCLUDE"
        txn_a.commit()
        hilo.join(timeout=15)
        assert not hilo.is_alive()
        assert resultado["status"] == 409, resultado
        assert resultado["detail"]["codigo"] == "slot_ocupado"
        assert resultado["detail"]["alternativos"]
        verificacion = Session(bind=test_engine)
        try:
            activos = (
                verificacion.query(Turno)
                .filter(
                    Turno.profesional_id == prof_id,
                    Turno.estado.in_([TurnoEstado.reservado, TurnoEstado.confirmado]),
                )
                .count()
            )
            assert activos == 1
            assert (
                verificacion.query(Paciente).filter(Paciente.dni == dni_b).count() == 0
            )
        finally:
            verificacion.close()
    finally:
        if txn_a.is_active:
            txn_a.rollback()
        sesion_a.close()
        conn_a.close()
        _limpiar_concurrencia(test_engine, prof_id, [dni_a, dni_b])


def test_reserva_contigua_no_solapa_201(client, db_session, reloj):
    """# AC R5 S4: `[inicio, fin)` permite un turno contiguo."""
    from app.models.turno import Turno

    prof = _prof(db_session)
    _ventana(db_session, prof.id, desde=9, hasta=11)
    _turno_activo(
        db_session,
        prof.id,
        datetime(2026, 10, 19, 12, 0, tzinfo=UTC),
        datetime(2026, 10, 19, 12, 30, tzinfo=UTC),
    )

    resp = client.post(
        "/api/turnos",
        json=_body(prof.id, inicio="2026-10-19T09:30:00-03:00"),
    )

    assert resp.status_code == 201
    assert db_session.query(Turno).count() == 2


def test_reserva_profesional_inexistente_404(client, db_session, reloj):
    """# AC R8 S1: profesional inexistente → 404 sin turno ni paciente."""
    resp = client.post("/api/turnos", json=_body(uuid.uuid4()))

    assert resp.status_code == 404
    assert _turnos(db_session) == 0
    assert _paciente_por_dni(db_session, "30999001") == 0


def test_reserva_profesional_inactivo_404(client, db_session, reloj):
    """# AC R8 S2: profesional inactivo → 404 sin turno ni paciente."""
    prof = _prof(db_session, activo=False)
    _ventana(db_session, prof.id, desde=9, hasta=11)

    resp = client.post("/api/turnos", json=_body(prof.id))

    assert resp.status_code == 404
    assert _turnos(db_session) == 0
    assert _paciente_por_dni(db_session, "30999001") == 0


def test_reserva_profesional_activo_201(client, db_session, reloj):
    """# AC R8 S3: el mismo body con un profesional activo → 201."""
    prof = _prof(db_session)
    _ventana(db_session, prof.id, desde=9, hasta=11)

    resp = client.post("/api/turnos", json=_body(prof.id))

    assert resp.status_code == 201
    assert _turnos(db_session) == 1


def test_reserva_tokens_distintos_por_turno(client, db_session, reloj):
    """# AC R9 S1: dos reservas válidas generan tokens distintos y no nulos."""
    from app.models.turno import Turno

    prof = _prof(db_session)
    _ventana(db_session, prof.id, desde=9, hasta=11)

    primera = client.post(
        "/api/turnos", json=_body(prof.id, inicio="2026-10-19T09:00:00-03:00")
    )
    segunda = client.post(
        "/api/turnos",
        json=_body(
            prof.id,
            inicio="2026-10-19T09:30:00-03:00",
            paciente=_paciente(dni="30999002", email="otro@ficticio.test"),
        ),
    )

    assert primera.status_code == 201
    assert segunda.status_code == 201
    tokens = {t.token_cancelacion for t in db_session.query(Turno).all()}
    assert None not in tokens
    assert len(tokens) == 2


def test_reserva_sin_login_201(client, db_session, reloj):
    """# AC R9 S2: sin cookie ni header de auth la reserva responde 201."""
    prof = _prof(db_session)
    _ventana(db_session, prof.id, desde=9, hasta=11)

    resp = client.post("/api/turnos", json=_body(prof.id))

    assert resp.status_code == 201
    assert uuid.UUID(resp.json()["token_cancelacion"])
    assert "authorization" not in {k.lower() for k in resp.request.headers}
    assert "cookie" not in {k.lower() for k in resp.request.headers}


def test_reserva_dni_telefono_raiz_400(client, db_session, reloj):
    """# AC R9 S3: `dni`/`telefono` en la raíz → 400 por campo extra."""
    prof = _prof(db_session)
    _ventana(db_session, prof.id, desde=9, hasta=11)
    body = _body(prof.id, dni="30999001", telefono="+5491100000001")

    resp = client.post("/api/turnos", json=body)

    assert resp.status_code == 400
    campos = {d["campo"] for d in resp.json()["detail"]}
    assert {"dni", "telefono"} <= campos
    assert _turnos(db_session) == 0


def test_reserva_rate_limit_dentro_limite_201(client_rate_limit, db_session):
    """# AC R7 S1: una reserva dentro del límite responde 201 y consume cupo."""
    from app.core import ratelimit

    cliente, _, ip = client_rate_limit
    prof = _prof(db_session)
    _ventana(db_session, prof.id, desde=9, hasta=11)

    resp = cliente.post("/api/turnos", json=_body(prof.id))

    assert resp.status_code == 201
    _consumir_cupo(ip["valor"], 9)
    clave = f"turnos-publico:{ip['valor']}"
    pasa, _ = ratelimit.check_public_rate_limit(clave, limit=10, window_s=60)
    assert pasa is False


def test_reserva_rate_limit_decima_pasa_undecima_429(client_rate_limit, db_session):
    """# AC R7 S2: 9 consumidas → la 10 da 201 y la 11 da 429 sin turno."""
    from app.models.turno import Turno

    cliente, _, ip = client_rate_limit
    prof = _prof(db_session)
    _ventana(db_session, prof.id, desde=9, hasta=11)
    _consumir_cupo(ip["valor"], 9)

    decima = cliente.post(
        "/api/turnos", json=_body(prof.id, inicio="2026-10-19T09:00:00-03:00")
    )
    undecima = cliente.post(
        "/api/turnos",
        json=_body(
            prof.id,
            inicio="2026-10-19T09:30:00-03:00",
            paciente=_paciente(dni="30999002", email="otro@ficticio.test"),
        ),
    )

    assert decima.status_code == 201
    assert undecima.status_code == 429
    assert int(undecima.headers["Retry-After"]) >= 1
    assert db_session.query(Turno).count() == 1


def test_reserva_rate_limit_ips_independientes(client_rate_limit, db_session):
    """# AC R7 S3: con la IP A agotada, la IP B todavía reserva (201)."""
    cliente, _, ip = client_rate_limit
    prof = _prof(db_session)
    _ventana(db_session, prof.id, desde=9, hasta=11)
    _consumir_cupo("10.0.0.1", 10)

    ip["valor"] = "10.0.0.1"
    agotada = cliente.post("/api/turnos", json=_body(prof.id))
    ip["valor"] = "10.0.0.2"
    otra = cliente.post("/api/turnos", json=_body(prof.id))

    assert agotada.status_code == 429
    assert otra.status_code == 201
