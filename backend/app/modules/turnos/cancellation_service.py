"""Servicio de cancelación pública por token (C-06 D-1/D-4/D-6/D-7/D-9/D-10).

Transacción de cancelación: `SELECT ... FOR UPDATE` por `id`+`token` →
chequeo de estado → regla temporal → `estado=cancelado` → encolado del mail
`cancelacion` en savepoint aislado → auditoría append-only → commit. El router
traduce los errores de dominio a HTTP; este módulo concentra la persistencia.
"""

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session, load_only

from app.core.config import get_settings
from app.models.auditoria import AuditoriaTurno
from app.models.notificacion import NotifEstado, Notificacion, NotifTipo
from app.models.paciente import Paciente
from app.models.profesional import Profesional
from app.models.turno import CanalRecordatorio, Turno, TurnoEstado
from app.modules.turnos.service import _cancel_url, _iso_utc, now_utc

logger = logging.getLogger(__name__)

ESTADOS_CANCELABLES = {TurnoEstado.reservado, TurnoEstado.confirmado}


class NoAutorizado(Exception):
    """El token no corresponde a ese turno (o el turno no existe)."""


class TurnoYaCancelado(Exception):
    """Segunda llamada sobre un turno ya cancelado (D-5)."""


class TurnoNoCancelable(Exception):
    """Estado `atendido`/`ausente`/futuro: transición no permitida (RN-TU-07)."""


class FueraDePlazo(Exception):
    """`inicio - now < CANCEL_HOURS_MIN` (RN-TU-04, US-005 CA-2)."""

    def __init__(self, mensaje: str, contacto: str) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.contacto = contacto


class DatoInvalido(Exception):
    """Dato persistido inconsistente (p. ej. `inicio` naive)."""


def _utc(value: datetime) -> datetime:
    """Normaliza a UTC y rechaza datetimes naive (D-10)."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise DatoInvalido("`inicio` sin zona horaria")
    return value.astimezone(UTC)


def _payload(
    *,
    turno: Turno,
    enviar_en: datetime,
    paciente: Paciente,
    profesional: Profesional,
) -> dict:
    """Payload de 11 claves congelado por C-05/C-08 (D-6)."""
    return {
        "turno_id": str(turno.id),
        "tipo": NotifTipo.cancelacion.value,
        "enviar_en": _iso_utc(enviar_en),
        "paciente_nombre": paciente.nombre,
        "paciente_email": paciente.email,
        "profesional_nombre": profesional.nombre,
        "inicio": _iso_utc(_utc(turno.inicio)),
        "fin": _iso_utc(_utc(turno.fin)),
        "duracion_min": turno.duracion_min,
        "token_cancelacion": str(turno.token_cancelacion),
        "cancel_url": _cancel_url(turno.token_cancelacion, turno.id),
    }


def _encolar(
    db: Session,
    *,
    turno: Turno,
    now: datetime,
) -> bool:
    """Inserta la `Notificacion cancelacion` en savepoint aislado (D-6)."""
    try:
        with db.begin_nested():
            paciente = (
                db.query(Paciente)
                .filter(Paciente.id == turno.paciente_id)
                .one()
            )
            profesional = (
                db.query(Profesional)
                .filter(Profesional.id == turno.profesional_id)
                .one()
            )
            db.add(
                Notificacion(
                    turno_id=turno.id,
                    canal=CanalRecordatorio.mail,
                    tipo=NotifTipo.cancelacion,
                    estado=NotifEstado.pendiente,
                    intentos=0,
                    payload=_payload(
                        turno=turno,
                        enviar_en=now,
                        paciente=paciente,
                        profesional=profesional,
                    ),
                )
            )
            db.flush()
        return True
    except Exception:
        logger.warning("cancelacion_encolado_fallido turno_id=%s", turno.id)
        return False


def cancelar(
    db: Session,
    *,
    turno_id: uuid.UUID,
    token: uuid.UUID,
    now_provider: Callable[[], datetime] | None = None,
) -> dict:
    """Cancela un turno por token; devuelve la respuesta pública (D-11)."""
    now = (now_provider or now_utc)().astimezone(UTC)

    turno = (
        db.query(Turno)
        .options(
            load_only(
                Turno.id,
                Turno.estado,
                Turno.inicio,
                Turno.fin,
                Turno.duracion_min,
                Turno.profesional_id,
                Turno.paciente_id,
                Turno.token_cancelacion,
            )
        )
        .filter(Turno.id == turno_id, Turno.token_cancelacion == token)
        .with_for_update()
        .one_or_none()
    )
    if turno is None:
        raise NoAutorizado

    if turno.estado == TurnoEstado.cancelado:
        raise TurnoYaCancelado
    if turno.estado not in ESTADOS_CANCELABLES:
        raise TurnoNoCancelable

    estado_previo = turno.estado
    inicio = _utc(turno.inicio)
    fin = _utc(turno.fin)

    settings = get_settings()
    limite = timedelta(hours=settings.CANCEL_HOURS_MIN)
    if inicio - now < limite:
        raise FueraDePlazo(
            "No se puede cancelar con menos de "
            f"{settings.CANCEL_HOURS_MIN} horas de anticipación",
            settings.CONSULTORIO_CONTACTO,
        )

    turno.estado = TurnoEstado.cancelado
    turno.updated_at = now
    db.flush()

    encoladas = _encolar(db, turno=turno, now=now)

    db.add(
        AuditoriaTurno(
            turno_id=turno.id,
            actor_id=None,
            accion="cancelar",
            detalle={
                "actor": "paciente",
                "credencial": "token_cancelacion",
                "estado_previo": estado_previo.value,
                "inicio": _iso_utc(inicio),
                "fin": _iso_utc(fin),
                "duracion_min": turno.duracion_min,
                "profesional_id": str(turno.profesional_id),
                "notificaciones_encoladas": encoladas,
            },
        )
    )
    db.flush()

    respuesta = {
        "id": turno.id,
        "estado": TurnoEstado.cancelado.value,
        "inicio": _iso_utc(inicio),
        "fin": _iso_utc(fin),
        "duracion_min": turno.duracion_min,
        "notificaciones_encoladas": encoladas,
        "mensaje": "Turno cancelado",
    }
    db.commit()
    return respuesta
