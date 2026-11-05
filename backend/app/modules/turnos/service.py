"""Servicio de reserva online (C-05 D-1/D-2/D-3/D-7/D-8/D-10/D-12).

Transacción de reserva: lock del profesional → validaciones tempranas →
pre-validación del slot → upsert de paciente → turno → notificaciones →
auditoría → commit. El router solo traduce HTTP; este módulo concentra la
persistencia y reutiliza `app.modules.agenda.slot_service` para los slots.
"""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi.exceptions import HTTPException
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.auditoria import AuditoriaTurno
from app.models.notificacion import NotifEstado, Notificacion, NotifTipo
from app.models.paciente import Paciente
from app.models.profesional import Profesional
from app.models.turno import CanalRecordatorio, Turno, TurnoEstado, TurnoOrigen
from app.modules.agenda import slot_service
from app.modules.turnos.schemas import PacienteIn, TurnoCreate

TZ = ZoneInfo("America/Argentina/Buenos_Aires")


def now_utc() -> datetime:
    """Reloj por defecto (inyectable en tests, D-10)."""
    return datetime.now(UTC)


def _iso_utc(value: datetime) -> str:
    """Datetime JSONB como string ISO-8601 UTC (D-7/D-8)."""
    return value.astimezone(UTC).isoformat()


def _error(campo: str, error: str, tipo: str = "value_error") -> HTTPException:
    """400 con detalle por campo (regla dura 1)."""
    return HTTPException(
        status_code=400, detail=[{"campo": campo, "error": error, "tipo": tipo}]
    )


class SlotOcupado(Exception):
    """Colisión de anti-solape detectada por el EXCLUDE (D-2)."""


def _validar_duracion(data: TurnoCreate, granularidad: int) -> int:
    """Duración efectiva: default o múltiplo positivo de la granularidad (D-5)."""
    if data.duracion_min is None:
        return granularidad
    if data.duracion_min <= 0:
        raise _error(
            "duracion_min",
            "`duracion_min` debe ser un entero positivo",
            "duracion_invalida",
        )
    if data.duracion_min % granularidad != 0:
        raise _error(
            "duracion_min",
            "`duracion_min` debe ser múltiplo de la granularidad del profesional",
            "duracion_no_multiplo_granularidad",
        )
    return data.duracion_min


def _slots_del_dia(db: Session, profesional_id, dia, granularidad: int):
    """Slots libres del día local reutilizando `slot_service` (D-6)."""
    inicio_dia = datetime.combine(dia, time.min, tzinfo=TZ).astimezone(UTC)
    fin_dia = inicio_dia + timedelta(days=1)
    return slot_service.compute_slots(
        slot_service.fetch_ventanas(db, profesional_id),
        slot_service.fetch_bloqueos(db, profesional_id, inicio_dia, fin_dia),
        slot_service.fetch_turnos_activos(db, profesional_id, inicio_dia, fin_dia),
        granularidad,
        dia,
        dia,
        TZ,
    )


def _slot_disponible(
    db: Session, profesional_id, inicio: datetime, fin: datetime, granularidad: int
) -> bool:
    """True si todo el bloque `[inicio, fin)` está cubierto por slots libres."""
    libres = {
        slot.inicio.astimezone(UTC)
        for slot in _slots_del_dia(
            db, profesional_id, inicio.astimezone(TZ).date(), granularidad
        )
    }
    paso = timedelta(minutes=granularidad)
    cursor = inicio
    while cursor < fin:
        if cursor not in libres:
            return False
        cursor += paso
    return True


def _inicio_ocupado(db: Session, profesional_id, inicio: datetime) -> bool:
    """True si un turno activo cubre exactamente el `inicio` pedido (D-6)."""
    dia = inicio.astimezone(TZ).date()
    inicio_dia = datetime.combine(dia, time.min, tzinfo=TZ).astimezone(UTC)
    fin_dia = inicio_dia + timedelta(days=1)
    return any(
        turno.inicio <= inicio < turno.fin
        for turno in slot_service.fetch_turnos_activos(
            db, profesional_id, inicio_dia, fin_dia
        )
    )


def _alternativos(
    db: Session,
    profesional_id,
    inicio_pedido: datetime,
    duracion: int,
    granularidad: int,
    limite: int = 5,
) -> list[dict]:
    """Bloques libres del mismo día, con la duración pedida (D-6/RN-TU-06)."""
    dia = inicio_pedido.astimezone(TZ).date()
    libres = [
        slot.inicio.astimezone(UTC)
        for slot in _slots_del_dia(db, profesional_id, dia, granularidad)
    ]
    disponibles = set(libres)
    paso = timedelta(minutes=granularidad)
    bloques = duracion // granularidad
    alternativos: list[dict] = []
    for inicio in libres:
        if inicio == inicio_pedido:
            continue
        if all(inicio + paso * i in disponibles for i in range(bloques)):
            alternativos.append(
                {
                    "inicio": _iso_utc(inicio),
                    "fin": _iso_utc(inicio + timedelta(minutes=duracion)),
                    "duracion_min": duracion,
                }
            )
            if len(alternativos) >= limite:
                break
    return alternativos


def _upsert_paciente(db: Session, paciente: PacienteIn) -> uuid.UUID:
    """Upsert atómico por DNI; no toca `activo` (D-3/PB-04)."""
    stmt = (
        pg_insert(Paciente)
        .values(
            id=uuid.uuid4(),
            nombre=paciente.nombre,
            dni=paciente.dni,
            telefono=paciente.telefono,
            obra_social=paciente.obra_social,
            email=paciente.email,
        )
        .on_conflict_do_update(
            index_elements=["dni"],
            set_={
                "nombre": paciente.nombre,
                "telefono": paciente.telefono,
                "obra_social": paciente.obra_social,
                "email": paciente.email,
                "updated_at": func.now(),
            },
        )
        .returning(Paciente.id)
    )
    return db.execute(stmt).scalar_one()


def _nombre_constraint(exc: IntegrityError) -> str | None:
    """Nombre del constraint violado, con fallback textual por driver (D-2)."""
    orig = getattr(exc, "orig", None)
    diag = getattr(orig, "diag", None)
    nombre = getattr(diag, "constraint_name", None)
    if nombre:
        return nombre
    texto = str(orig or exc)
    for candidato in ("no_solape_prof", "ux_turno_token", "ux_paciente_dni"):
        if candidato in texto:
            return candidato
    return None


def _insertar_turno(
    db: Session,
    *,
    profesional_id,
    paciente_id,
    inicio: datetime,
    fin: datetime,
    duracion: int,
) -> Turno:
    """Inserta el turno en SAVEPOINT; mapea colisiones a 409/500 (D-2)."""
    for intento in range(2):
        turno = Turno(
            profesional_id=profesional_id,
            paciente_id=paciente_id,
            inicio=inicio,
            fin=fin,
            duracion_min=duracion,
            estado=TurnoEstado.reservado,
            origen=TurnoOrigen.online,
            token_cancelacion=uuid.uuid4(),
        )
        try:
            with db.begin_nested():
                db.add(turno)
                db.flush()
            return turno
        except IntegrityError as exc:
            constraint = _nombre_constraint(exc)
            if constraint == "ux_turno_token" and intento == 0:
                continue
            if constraint == "no_solape_prof":
                raise SlotOcupado from None
            raise HTTPException(
                status_code=500, detail="Error interno"
            ) from None
    raise HTTPException(status_code=500, detail="Error interno")


def _cancel_url(token: uuid.UUID) -> str:
    """Link normalizado sin doble barra (D-11)."""
    return f"{get_settings().FRONTEND_URL.rstrip('/')}/cancelar?token={token}"


def _payload(
    *,
    turno: Turno,
    tipo: NotifTipo,
    enviar_en: datetime,
    paciente: PacienteIn,
    profesional: Profesional,
    inicio: datetime,
    fin: datetime,
    duracion: int,
    cancel_url: str,
) -> dict:
    """Payload mínimo del mail; sin DNI, teléfono ni obra social (D-7)."""
    return {
        "turno_id": str(turno.id),
        "tipo": tipo.value,
        "enviar_en": _iso_utc(enviar_en),
        "paciente_nombre": paciente.nombre,
        "paciente_email": paciente.email,
        "profesional_nombre": profesional.nombre,
        "inicio": _iso_utc(inicio),
        "fin": _iso_utc(fin),
        "duracion_min": duracion,
        "token_cancelacion": str(turno.token_cancelacion),
        "cancel_url": cancel_url,
    }


def _encolar_notificaciones(
    db: Session,
    *,
    turno: Turno,
    paciente: PacienteIn,
    profesional: Profesional,
    inicio: datetime,
    fin: datetime,
    duracion: int,
    now: datetime,
    cancel_url: str,
) -> bool:
    """Encola confirmación + recordatorios según anticipación (D-7/RN-NO-01).

    Un fallo del insert se aísla en su savepoint y la reserva sigue (regla dura 5).
    """
    programadas: list[tuple[NotifTipo, datetime]] = [(NotifTipo.confirmacion, now)]
    if inicio - timedelta(hours=24) > now:
        programadas.append((NotifTipo.recordatorio_24h, inicio - timedelta(hours=24)))
    if inicio - timedelta(hours=2) > now:
        programadas.append((NotifTipo.recordatorio_2h, inicio - timedelta(hours=2)))
    try:
        with db.begin_nested():
            for tipo, enviar_en in programadas:
                db.add(
                    Notificacion(
                        turno_id=turno.id,
                        canal=CanalRecordatorio.mail,
                        tipo=tipo,
                        estado=NotifEstado.pendiente,
                        intentos=0,
                        payload=_payload(
                            turno=turno,
                            tipo=tipo,
                            enviar_en=enviar_en,
                            paciente=paciente,
                            profesional=profesional,
                            inicio=inicio,
                            fin=fin,
                            duracion=duracion,
                            cancel_url=cancel_url,
                        ),
                    )
                )
            db.flush()
        return True
    except Exception:
        return False


def reservar(
    db: Session,
    data: TurnoCreate,
    *,
    now_provider: Callable[[], datetime] | None = None,
) -> dict:
    """Ejecuta la reserva en el orden transaccional de D-12."""
    now = (now_provider or now_utc)().astimezone(UTC)

    prof = (
        db.query(Profesional)
        .filter(Profesional.id == data.profesional_id)
        .with_for_update()
        .one_or_none()
    )
    if prof is None or not prof.activo:
        raise HTTPException(status_code=404, detail="No encontrado")

    granularidad = prof.duracion_default_min or 30
    duracion = _validar_duracion(data, granularidad)

    inicio = data.inicio.astimezone(UTC)
    if inicio <= now:
        raise _error("inicio", "`inicio` debe ser una fecha futura")

    fin = inicio + timedelta(minutes=duracion)

    if not _slot_disponible(db, prof.id, inicio, fin, granularidad):
        codigo = (
            "slot_ocupado"
            if _inicio_ocupado(db, prof.id, inicio)
            else "slot_no_disponible"
        )
        alternativos = _alternativos(
            db, prof.id, inicio, duracion, granularidad
        )
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"codigo": codigo, "alternativos": alternativos},
        )

    paciente_id = _upsert_paciente(db, data.paciente)
    try:
        turno = _insertar_turno(
            db,
            profesional_id=prof.id,
            paciente_id=paciente_id,
            inicio=inicio,
            fin=fin,
            duracion=duracion,
        )
    except SlotOcupado:
        alternativos = _alternativos(
            db, prof.id, inicio, duracion, granularidad
        )
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"codigo": "slot_ocupado", "alternativos": alternativos},
        ) from None
    cancel_url = _cancel_url(turno.token_cancelacion)
    encoladas = _encolar_notificaciones(
        db,
        turno=turno,
        paciente=data.paciente,
        profesional=prof,
        inicio=inicio,
        fin=fin,
        duracion=duracion,
        now=now,
        cancel_url=cancel_url,
    )
    db.add(
        AuditoriaTurno(
            turno_id=turno.id,
            actor_id=None,
            accion="crear",
            detalle={
                "origen": "online",
                "profesional_id": str(prof.id),
                "inicio": _iso_utc(inicio),
                "fin": _iso_utc(fin),
                "duracion_min": duracion,
                "notificaciones_encoladas": encoladas,
            },
        )
    )
    db.flush()

    respuesta = {
        "id": turno.id,
        "estado": turno.estado.value,
        "inicio": _iso_utc(inicio),
        "fin": _iso_utc(fin),
        "duracion_min": duracion,
        "profesional": {"id": prof.id, "nombre": prof.nombre},
        "paciente": {
            "nombre": data.paciente.nombre,
            "dni": data.paciente.dni,
            "email": data.paciente.email,
        },
        "token_cancelacion": turno.token_cancelacion,
        "cancel_url": cancel_url,
        "notificaciones_encoladas": encoladas,
    }
    db.commit()
    return respuesta
