"""End-to-end reserva (C-05) + worker (C-08) (capa: DB real + sender fake).

# AC notificaciones-mail/Despacho — la confirmación encolada por la reserva
# se envía en el siguiente ciclo, sin tocar el turno.
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from tests.conftest import mk_profesional

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
NOW = datetime(2026, 10, 19, 8, 0, tzinfo=TZ)


class FakeSender:
    def __init__(self):
        self.llamadas: list[tuple[str, str, str]] = []

    def send(self, *, asunto: str, cuerpo: str, destinatario: str) -> None:
        self.llamadas.append((asunto, cuerpo, destinatario))


def _ventana(db_session, profesional_id):
    from app.models.disponibilidad import Disponibilidad

    db_session.add(
        Disponibilidad(
            profesional_id=profesional_id,
            dia_semana=0,
            hora_desde=time(9, 0),
            hora_hasta=time(11, 0),
            vigente_desde=date(2026, 1, 1),
            vigente_hasta=date(2026, 12, 31),
        )
    )
    db_session.flush()


def _body(profesional_id):
    return {
        "profesional_id": str(profesional_id),
        "inicio": "2026-10-19T09:00:00-03:00",
        "paciente": {
            "nombre": "Paciente Ficticio",
            "dni": "30999001",
            "telefono": "+5491100000001",
            "obra_social": "OS Ficticia",
            "email": "paciente@ficticio.test",
        },
    }


def test_reserva_confirmacion_se_envia_en_el_siguiente_ciclo(db_session):
    """D-13: reserva → `run_once` inmediato envía la confirmación (< 1 ciclo)."""
    from app.models.notificacion import NotifEstado, Notificacion
    from app.models.turno import Turno
    from app.modules.notificaciones.worker import run_once
    from app.modules.turnos import service
    from app.modules.turnos.schemas import TurnoCreate

    prof = mk_profesional(db_session, duracion_default_min=30)
    _ventana(db_session, prof.id)

    respuesta = service.reservar(
        db_session, TurnoCreate(**_body(prof.id)), now_provider=lambda: NOW
    )

    sender = FakeSender()
    resumen = run_once(db_session, sender, now=NOW)

    notifs = (
        db_session.query(Notificacion)
        .filter(Notificacion.turno_id == respuesta["id"])
        .all()
    )
    por_tipo = {n.tipo.value: n for n in notifs}
    assert set(por_tipo) == {"confirmacion"}
    confirmacion = por_tipo["confirmacion"]
    assert confirmacion.estado == NotifEstado.enviada
    assert confirmacion.enviada_at == NOW.astimezone(UTC)
    assert confirmacion.error is None
    assert resumen.enviadas == 1
    assert len(sender.llamadas) == 1
    assert "confirmado" in sender.llamadas[0][0].lower()
    assert sender.llamadas[0][2] == "paciente@ficticio.test"

    turno = db_session.get(Turno, respuesta["id"])
    assert turno.estado.value == "reservado"
    assert turno.inicio == datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
    assert turno.fin == turno.inicio + timedelta(minutes=30)
