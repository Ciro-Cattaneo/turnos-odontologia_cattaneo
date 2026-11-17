"""Worker de notificaciones: claim, envío, backoff y descarte (capa: DB real).

# AC notificaciones-mail/Despacho, Reintentos, Descarte, Payload y Observabilidad.
# Mocks SOLO en el borde SMTP y el reloj (duro 9); persistencia contra PG real.
"""

import logging
import os
from datetime import UTC, datetime, timedelta

from app.modules.notificaciones.sender import SendError
from tests.conftest import mk_paciente, mk_profesional, mk_turno

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
CANCEL_URL = "https://turnos.ficticio.test/cancelar?token="


class FakeSender:
    """Borde SMTP falso: registra llamadas y falla por destinatario."""

    def __init__(self, errores=None):
        self.llamadas: list[tuple[str, str, str]] = []
        self.errores = errores or {}

    def send(self, *, asunto: str, cuerpo: str, destinatario: str) -> None:
        self.llamadas.append((asunto, cuerpo, destinatario))
        error = self.errores.get(destinatario)
        if error is not None:
            raise error


def _dependencias(db_session, *, estado_turno=None):
    from app.models.turno import TurnoEstado

    prof = mk_profesional(db_session)
    pac = mk_paciente(db_session)
    turno = mk_turno(
        db_session,
        prof.id,
        pac.id,
        estado=estado_turno or TurnoEstado.reservado,
    )
    return prof, pac, turno


def _payload(turno, *, tipo="confirmacion", enviar_en=None, **over):
    inicio = turno.inicio
    if enviar_en is None:
        enviar_en = NOW - timedelta(minutes=1)
    enviar = enviar_en.isoformat() if isinstance(enviar_en, datetime) else enviar_en
    base = {
        "turno_id": str(turno.id),
        "tipo": tipo,
        "enviar_en": enviar,
        "paciente_nombre": "Paciente Ficticio",
        "paciente_email": "paciente@ficticio.test",
        "profesional_nombre": "Odontologa Ficticia",
        "inicio": inicio.isoformat(),
        "fin": turno.fin.isoformat(),
        "duracion_min": turno.duracion_min,
        "token_cancelacion": str(turno.token_cancelacion),
        "cancel_url": CANCEL_URL + str(turno.token_cancelacion),
    }
    base.update(over)
    return base


def _crear_notificacion(
    db_session,
    turno,
    *,
    tipo="confirmacion",
    estado=None,
    intentos=0,
    enviar_en=None,
    payload=None,
    error=None,
):
    from app.models.notificacion import NotifEstado, Notificacion, NotifTipo

    notif = Notificacion(
        turno_id=turno.id,
        tipo=NotifTipo(tipo),
        estado=estado or NotifEstado.pendiente,
        intentos=intentos,
        payload=payload
        if payload is not None
        else _payload(turno, tipo=tipo, enviar_en=enviar_en),
        error=error,
    )
    db_session.add(notif)
    db_session.flush()
    return notif


def _recargar(db_session, notif):
    from app.models.notificacion import Notificacion

    db_session.expire_all()
    return db_session.get(Notificacion, notif.id)


def _run(db_session, sender, *, now=NOW, batch_size=20):
    from app.modules.notificaciones.worker import run_once

    return run_once(db_session, sender, now=now, batch_size=batch_size)


def _enviar_en(notif):
    return datetime.fromisoformat(notif.payload["enviar_en"])


# --- 4.3 Sender inyectable -------------------------------------------------


def test_worker_usa_sender_inyectado(db_session):
    """D-5/4.3: el worker envía por el `MailSender` inyectado, no por SMTP real."""
    _prof, _pac, turno = _dependencias(db_session)
    notif = _crear_notificacion(db_session, turno)
    sender = FakeSender()

    resumen = _run(db_session, sender)

    assert len(sender.llamadas) == 1
    asunto, cuerpo, destinatario = sender.llamadas[0]
    assert "confirmado" in asunto.lower()
    assert "Paciente Ficticio" in cuerpo
    assert destinatario == "paciente@ficticio.test"
    assert resumen.enviadas == 1
    assert _recargar(db_session, notif).estado.value == "enviada"


# --- 5.1 Claim -------------------------------------------------------------


def test_worker_toma_pendiente_vencida(db_session):
    """D-2: una pendiente vencida de canal mail se toma y se envía."""
    _prof, _pac, turno = _dependencias(db_session)
    notif = _crear_notificacion(db_session, turno)
    sender = FakeSender()

    _run(db_session, sender)

    assert len(sender.llamadas) == 1
    assert _recargar(db_session, notif).estado.value == "enviada"


def test_worker_no_toma_notificacion_futura(db_session):
    """D-2: `enviar_en > now` queda intacta (pendiente, intentos=0)."""
    _prof, _pac, turno = _dependencias(db_session)
    notif = _crear_notificacion(
        db_session, turno, enviar_en=NOW + timedelta(minutes=30)
    )
    sender = FakeSender()

    _run(db_session, sender)

    assert sender.llamadas == []
    recargada = _recargar(db_session, notif)
    assert recargada.estado.value == "pendiente"
    assert recargada.intentos == 0


# --- 5.2 Camino feliz ------------------------------------------------------


def test_worker_confirmacion_vencida_queda_enviada(db_session):
    """D-3/D-13: OK de SMTP → enviada + `enviada_at`, `error` nulo."""
    _prof, _pac, turno = _dependencias(db_session)
    notif = _crear_notificacion(db_session, turno)

    _run(db_session, FakeSender())

    recargada = _recargar(db_session, notif)
    assert recargada.estado.value == "enviada"
    assert recargada.enviada_at == NOW
    assert recargada.error is None


def test_worker_no_modifica_estado_del_turno(db_session):
    """Duro 5: el envío no toca el turno (sigue `reservado`)."""
    _prof, _pac, turno = _dependencias(db_session)
    _crear_notificacion(db_session, turno)

    _run(db_session, FakeSender())

    db_session.refresh(turno)
    assert turno.estado.value == "reservado"


# --- 5.3 Backoff -----------------------------------------------------------


def test_worker_primer_fallo_reprograma_cinco_minutos(db_session):
    """D-4: 1.er fallo → intentos=1 y `enviar_en = now + 5 min`."""
    _prof, _pac, turno = _dependencias(db_session)
    notif = _crear_notificacion(db_session, turno)
    sender = FakeSender({"paciente@ficticio.test": SendError("timeout")})

    resumen = _run(db_session, sender)

    recargada = _recargar(db_session, notif)
    assert recargada.estado.value == "pendiente"
    assert recargada.intentos == 1
    assert recargada.error and recargada.error.startswith("smtp:")
    assert _enviar_en(recargada) == NOW + timedelta(minutes=5)
    assert resumen.reintentos == 1


def test_worker_segundo_fallo_reprograma_diez_minutos(db_session):
    """D-4: 2.º fallo → intentos=2 y `enviar_en = now + 10 min`."""
    _prof, _pac, turno = _dependencias(db_session)
    notif = _crear_notificacion(db_session, turno, intentos=1)
    sender = FakeSender({"paciente@ficticio.test": SendError("timeout")})

    _run(db_session, sender)

    recargada = _recargar(db_session, notif)
    assert recargada.estado.value == "pendiente"
    assert recargada.intentos == 2
    assert _enviar_en(recargada) == NOW + timedelta(minutes=10)


# --- 5.4 Tercer fallo ------------------------------------------------------


def test_worker_tercer_fallo_queda_fallida(db_session):
    """D-4: 3.er fallo → fallida con intentos=3 y sin reprogramar."""
    _prof, _pac, turno = _dependencias(db_session)
    notif = _crear_notificacion(db_session, turno, intentos=2)
    original = _enviar_en(notif)
    sender = FakeSender({"paciente@ficticio.test": SendError("timeout")})

    resumen = _run(db_session, sender)

    recargada = _recargar(db_session, notif)
    assert recargada.estado.value == "fallida"
    assert recargada.intentos == 3
    assert recargada.error and recargada.error.startswith("smtp:")
    assert _enviar_en(recargada) == original
    assert resumen.fallidas == 1


# --- 5.5 Reintento exitoso -------------------------------------------------


def test_worker_reintento_exitoso_queda_enviada(db_session):
    """D-4: con intentos previos, un envío OK limpia `error` y marca enviada."""
    _prof, _pac, turno = _dependencias(db_session)
    notif = _crear_notificacion(
        db_session, turno, intentos=1, error="smtp: timeout previo"
    )

    _run(db_session, FakeSender())

    recargada = _recargar(db_session, notif)
    assert recargada.estado.value == "enviada"
    assert recargada.enviada_at == NOW
    assert recargada.error is None
    assert recargada.intentos == 1


# --- 5.6 Descarte por turno no activo --------------------------------------


def test_worker_turno_cancelado_no_envia_recordatorio(db_session):
    """D-8: recordatorio con turno cancelado → fallida/turno_cancelado, sin SMTP."""
    from app.models.turno import TurnoEstado

    _prof, _pac, turno = _dependencias(db_session, estado_turno=TurnoEstado.cancelado)
    notif = _crear_notificacion(db_session, turno, tipo="recordatorio_2h", intentos=1)
    sender = FakeSender()

    resumen = _run(db_session, sender)

    recargada = _recargar(db_session, notif)
    assert sender.llamadas == []
    assert recargada.estado.value == "fallida"
    assert recargada.error and recargada.error.startswith("turno_cancelado:")
    assert recargada.intentos == 1
    assert resumen.descartadas == 1


def test_worker_turno_atendido_descarta_recordatorio(db_session):
    """D-8: turno atendido/ausente → descarte sin llamar SMTP."""
    from app.models.turno import TurnoEstado

    _prof, _pac, turno = _dependencias(db_session, estado_turno=TurnoEstado.atendido)
    notif = _crear_notificacion(db_session, turno, tipo="recordatorio_24h", intentos=0)
    sender = FakeSender()

    _run(db_session, sender)

    recargada = _recargar(db_session, notif)
    assert sender.llamadas == []
    assert recargada.estado.value == "fallida"
    assert recargada.error and recargada.error.startswith("turno_cancelado:")
    assert recargada.intentos == 0


# --- 5.7 Cancelación con turno cancelado -----------------------------------


def test_worker_cancelacion_se_envia_con_turno_cancelado(db_session):
    """D-8: `cancelacion` se envía aunque el turno ya esté cancelado."""
    from app.models.turno import TurnoEstado

    _prof, _pac, turno = _dependencias(db_session, estado_turno=TurnoEstado.cancelado)
    notif = _crear_notificacion(db_session, turno, tipo="cancelacion")
    sender = FakeSender()

    _run(db_session, sender)

    assert len(sender.llamadas) == 1
    assert "cancelado" in sender.llamadas[0][0].lower()
    assert _recargar(db_session, notif).estado.value == "enviada"


# --- 5.8 Payload incompleto ------------------------------------------------


def test_worker_payload_sin_email_se_marca_fallida_sin_romper_lote(db_session):
    """D-1: payload sin `paciente_email` → fallida, y la fila válida se envía."""
    _prof, _pac, turno = _dependencias(db_session)
    incompleto = _crear_notificacion(
        db_session,
        turno,
        payload=_payload(turno, paciente_email=""),
    )
    valido = _crear_notificacion(db_session, turno)
    sender = FakeSender()

    resumen = _run(db_session, sender)

    assert _recargar(db_session, incompleto).estado.value == "fallida"
    assert _recargar(db_session, incompleto).error.startswith("payload_incompleto:")
    assert _recargar(db_session, incompleto).intentos == 0
    assert _recargar(db_session, valido).estado.value == "enviada"
    assert len(sender.llamadas) == 1
    assert resumen.payload_invalidos == 1


def test_worker_enviar_en_invalido_se_marca_fallida(db_session):
    """D-1/D-2: `enviar_en` no parseable se sanea a fallida sin SMTP."""
    _prof, _pac, turno = _dependencias(db_session)
    notif = _crear_notificacion(
        db_session,
        turno,
        payload=_payload(turno, enviar_en="no-es-una-fecha"),
    )
    sender = FakeSender()

    resumen = _run(db_session, sender)

    recargada = _recargar(db_session, notif)
    assert sender.llamadas == []
    assert recargada.estado.value == "fallida"
    assert recargada.error and recargada.error.startswith("payload_incompleto:")
    assert resumen.payload_invalidos == 1


# --- 5.9 Aislamiento y resumen ---------------------------------------------


def test_worker_excepcion_inesperada_no_aborta_lote(db_session):
    """D-13: una excepción inesperada en una fila no corta el resto del lote."""
    _prof, _pac, turno = _dependencias(db_session)
    _prof2, _pac2, turno2 = _dependencias(db_session)
    falla = _crear_notificacion(
        db_session,
        turno,
        payload=_payload(turno, paciente_email="falla@ficticio.test"),
    )
    valida = _crear_notificacion(
        db_session,
        turno2,
        payload=_payload(turno2, paciente_email="valida@ficticio.test"),
    )
    sender = FakeSender({"falla@ficticio.test": RuntimeError("boom")})

    resumen = _run(db_session, sender)

    assert _recargar(db_session, valida).estado.value == "enviada"
    recargada = _recargar(db_session, falla)
    assert recargada.estado.value == "pendiente"
    assert recargada.intentos == 1
    assert _enviar_en(recargada) == NOW + timedelta(minutes=5)
    assert resumen.enviadas == 1
    assert resumen.reintentos == 1


def test_worker_resumen_cuenta_resultados(db_session):
    """D-13: el `Resumen` separa enviadas, reintentos, fallidas, descartes y payload."""
    from app.models.turno import TurnoEstado

    _p1, _pa1, t1 = _dependencias(db_session)
    _p2, _pa2, t2 = _dependencias(db_session)
    _p3, _pa3, t3 = _dependencias(db_session)
    _p4, _pa4, t4 = _dependencias(db_session, estado_turno=TurnoEstado.cancelado)
    _p5, _pa5, t5 = _dependencias(db_session)

    _crear_notificacion(
        db_session, t1, payload=_payload(t1, paciente_email="ok@ficticio.test")
    )
    _crear_notificacion(
        db_session, t2, payload=_payload(t2, paciente_email="retry@ficticio.test")
    )
    _crear_notificacion(
        db_session,
        t3,
        intentos=2,
        payload=_payload(t3, paciente_email="falla@ficticio.test"),
    )
    _crear_notificacion(db_session, t4, tipo="recordatorio_24h", intentos=0)
    _crear_notificacion(
        db_session,
        t5,
        payload=_payload(t5, paciente_email="", turno_id=str(t5.id)),
    )
    sender = FakeSender(
        {
            "retry@ficticio.test": SendError("timeout"),
            "falla@ficticio.test": SendError("timeout"),
        }
    )

    resumen = _run(db_session, sender)

    assert (resumen.enviadas, resumen.reintentos, resumen.fallidas) == (1, 1, 1)
    assert resumen.descartadas == 1
    assert resumen.payload_invalidos == 1


# --- 5.10 Logs -------------------------------------------------------------


def test_worker_log_de_fallo_no_incluye_password(db_session, caplog):
    """D-10/duro 10: el log del fallo nunca expone `SMTP_PASS`."""
    _prof, _pac, turno = _dependencias(db_session)
    _crear_notificacion(db_session, turno)
    sender = FakeSender(
        {"paciente@ficticio.test": SendError("autenticación rechazada")}
    )
    password = os.environ["SMTP_PASS"]

    with caplog.at_level(logging.WARNING):
        _run(db_session, sender)

    assert password not in caplog.text
    assert "resultado=reintento" in caplog.text
