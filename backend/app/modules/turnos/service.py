"""Servicio de reserva online (C-05 D-1/D-2/D-3/D-7/D-8/D-10/D-12).

Transacción de reserva: lock del profesional → validaciones tempranas →
pre-validación del slot → upsert de paciente → turno → notificaciones →
auditoría → commit. El router solo traduce HTTP; este módulo concentra la
persistencia y reutiliza `app.modules.agenda.slot_service` para los slots.
"""

import base64
import binascii
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi.exceptions import HTTPException
from sqlalchemy import func, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, load_only

from app.core.config import get_settings
from app.models.auditoria import AuditoriaTurno
from app.models.notificacion import NotifEstado, Notificacion, NotifTipo
from app.models.paciente import Paciente
from app.models.profesional import Profesional
from app.models.turno import CanalRecordatorio, Turno, TurnoEstado, TurnoOrigen
from app.modules.agenda import slot_service
from app.modules.notificaciones.payload import motivo_turno_reprogramado
from app.modules.turnos.schemas import (
    CorreccionPacienteIn,
    PacienteIn,
    TurnoCreate,
    TurnoReprogramar,
)

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


def _turnos_activos_del_dia(
    db: Session, profesional_id, inicio_dia: datetime, fin_dia: datetime, excluir
):
    """Turnos activos del rango, excluyendo el propio al reprogramar (D-4)."""
    filas = (
        db.query(Turno.id, Turno.inicio, Turno.fin)
        .filter(
            Turno.profesional_id == profesional_id,
            Turno.inicio >= inicio_dia,
            Turno.inicio < fin_dia,
            Turno.estado.in_(list(slot_service.ESTADOS_ACTIVOS)),
        )
        .order_by(Turno.inicio)
        .all()
    )
    return [
        slot_service.TurnoOcupado(inicio=fila.inicio, fin=fila.fin)
        for fila in filas
        if excluir is None or fila.id != excluir
    ]


def _slots_del_dia(
    db: Session,
    profesional_id,
    dia,
    granularidad: int,
    excluir_turno_id=None,
):
    """Slots libres del día local reutilizando `slot_service` (D-6)."""
    inicio_dia = datetime.combine(dia, time.min, tzinfo=TZ).astimezone(UTC)
    fin_dia = inicio_dia + timedelta(days=1)
    return slot_service.compute_slots(
        slot_service.fetch_ventanas(db, profesional_id),
        slot_service.fetch_bloqueos(db, profesional_id, inicio_dia, fin_dia),
        _turnos_activos_del_dia(
            db, profesional_id, inicio_dia, fin_dia, excluir_turno_id
        ),
        granularidad,
        dia,
        dia,
        TZ,
    )


def _slot_disponible(
    db: Session,
    profesional_id,
    inicio: datetime,
    fin: datetime,
    granularidad: int,
    excluir_turno_id=None,
) -> bool:
    """True si todo el bloque `[inicio, fin)` está cubierto por slots libres."""
    libres = {
        slot.inicio.astimezone(UTC)
        for slot in _slots_del_dia(
            db,
            profesional_id,
            inicio.astimezone(TZ).date(),
            granularidad,
            excluir_turno_id,
        )
    }
    paso = timedelta(minutes=granularidad)
    cursor = inicio
    while cursor < fin:
        if cursor not in libres:
            return False
        cursor += paso
    return True


def _inicio_ocupado(
    db: Session, profesional_id, inicio: datetime, excluir_turno_id=None
) -> bool:
    """True si un turno activo cubre exactamente el `inicio` pedido (D-6)."""
    dia = inicio.astimezone(TZ).date()
    inicio_dia = datetime.combine(dia, time.min, tzinfo=TZ).astimezone(UTC)
    fin_dia = inicio_dia + timedelta(days=1)
    return any(
        turno.inicio <= inicio < turno.fin
        for turno in _turnos_activos_del_dia(
            db, profesional_id, inicio_dia, fin_dia, excluir_turno_id
        )
    )


def _alternativos(
    db: Session,
    profesional_id,
    inicio_pedido: datetime,
    duracion: int,
    granularidad: int,
    limite: int = 5,
    excluir_turno_id=None,
) -> list[dict]:
    """Bloques libres del mismo día, con la duración pedida (D-6/RN-TU-06)."""
    dia = inicio_pedido.astimezone(TZ).date()
    libres = [
        slot.inicio.astimezone(UTC)
        for slot in _slots_del_dia(
            db, profesional_id, dia, granularidad, excluir_turno_id
        )
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
    origen: TurnoOrigen = TurnoOrigen.online,
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
            origen=origen,
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
            raise HTTPException(status_code=500, detail="Error interno") from None
    raise HTTPException(status_code=500, detail="Error interno")


def _cancel_url(token: uuid.UUID, turno_id: uuid.UUID) -> str:
    """Link normalizado sin doble barra, token e id opaco (D-10/D-11)."""
    return (
        f"{get_settings().FRONTEND_URL.rstrip('/')}/cancelar"
        f"?token={token}&id={turno_id}"
    )


def _payload(
    *,
    turno: Turno,
    tipo: NotifTipo,
    enviar_en: datetime,
    paciente_nombre: str,
    paciente_email: str,
    profesional_nombre: str,
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
        "paciente_nombre": paciente_nombre,
        "paciente_email": paciente_email,
        "profesional_nombre": profesional_nombre,
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
    paciente_nombre: str,
    paciente_email: str,
    profesional_nombre: str,
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
                            paciente_nombre=paciente_nombre,
                            paciente_email=paciente_email,
                            profesional_nombre=profesional_nombre,
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
    origen: TurnoOrigen = TurnoOrigen.online,
    actor_id: uuid.UUID | None = None,
    origen_auditoria: str = "online",
    actor: dict | None = None,
) -> dict:
    """Ejecuta la reserva en el orden transaccional de D-12 (D-3)."""
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
        alternativos = _alternativos(db, prof.id, inicio, duracion, granularidad)
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
            origen=origen,
        )
    except SlotOcupado:
        alternativos = _alternativos(db, prof.id, inicio, duracion, granularidad)
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"codigo": "slot_ocupado", "alternativos": alternativos},
        ) from None
    cancel_url = _cancel_url(turno.token_cancelacion, turno.id)
    encoladas = _encolar_notificaciones(
        db,
        turno=turno,
        paciente_nombre=data.paciente.nombre,
        paciente_email=data.paciente.email,
        profesional_nombre=prof.nombre,
        inicio=inicio,
        fin=fin,
        duracion=duracion,
        now=now,
        cancel_url=cancel_url,
    )
    detalle_auditoria: dict = {
        "origen": origen_auditoria,
        "profesional_id": str(prof.id),
        "inicio": _iso_utc(inicio),
        "fin": _iso_utc(fin),
        "duracion_min": duracion,
        "notificaciones_encoladas": encoladas,
    }
    if actor is not None:
        detalle_auditoria["actor"] = actor
        detalle_auditoria["paciente_id"] = str(paciente_id)
    db.add(
        AuditoriaTurno(
            turno_id=turno.id,
            actor_id=actor_id,
            accion="crear",
            detalle=detalle_auditoria,
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


# --- Operación staff (C-07 D-2/D-4/D-5/D-6/D-7/D-8/D-9) ---------------------

ESTADOS_EDITABLES = {TurnoEstado.reservado, TurnoEstado.confirmado}
ESTADOS_CANCELABLES = {TurnoEstado.reservado, TurnoEstado.confirmado}
TIPOS_OBSOLETOS = (
    NotifTipo.confirmacion,
    NotifTipo.recordatorio_24h,
    NotifTipo.recordatorio_2h,
)


class HistorialCursorInvalido(Exception):
    """El cursor de historial no decodifica o no representa `(created_at, id)`."""


def actor_detalle(staff) -> dict:
    """Detalle uniforme del actor staff para `auditoria_turno.detalle` (D-8)."""
    rol = getattr(staff.rol, "value", staff.rol)
    return {"tipo": "staff", "id": str(staff.id), "rol": str(rol)}


def _codigo(detalle: dict) -> HTTPException:
    return HTTPException(status_code=422, detail=detalle)


def _validar_duracion_valor(valor: int, granularidad: int) -> int:
    if valor <= 0:
        raise _error(
            "duracion_min",
            "`duracion_min` debe ser un entero positivo",
            "duracion_invalida",
        )
    if valor % granularidad != 0:
        raise _error(
            "duracion_min",
            "`duracion_min` debe ser múltiplo de la granularidad del profesional",
            "duracion_no_multiplo_granularidad",
        )
    return valor


def _cargar_turno_lock(db: Session, turno_id: uuid.UUID) -> Turno | None:
    """`SELECT ... FOR UPDATE` del turno con columnas explícitas (D-4)."""
    return (
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
                Turno.origen,
                Turno.updated_at,
            )
        )
        .filter(Turno.id == turno_id)
        .with_for_update()
        .one_or_none()
    )


def _cargar_profesional_lock(db: Session, profesional_id) -> Profesional | None:
    return (
        db.query(Profesional)
        .options(
            load_only(
                Profesional.id,
                Profesional.nombre,
                Profesional.duracion_default_min,
                Profesional.activo,
            )
        )
        .filter(Profesional.id == profesional_id)
        .with_for_update()
        .one_or_none()
    )


def _descartar_pendientes(db: Session, *, turno_id: uuid.UUID, detalle: str) -> bool:
    """Marca `fallida` las pendientes viejas con prefijo propio (D-10 paso 1)."""
    try:
        with db.begin_nested():
            db.execute(
                update(Notificacion)
                .where(
                    Notificacion.turno_id == turno_id,
                    Notificacion.estado == NotifEstado.pendiente,
                    Notificacion.tipo.in_(TIPOS_OBSOLETOS),
                )
                .values(
                    estado=NotifEstado.fallida,
                    error=motivo_turno_reprogramado(detalle),
                )
            )
            db.flush()
        return True
    except Exception:
        return False


def _respuesta_reprogramacion(turno: Turno, encoladas: bool) -> dict:
    return {
        "id": turno.id,
        "estado": turno.estado.value,
        "inicio": _iso_utc(_utc_aware(turno.inicio)),
        "fin": _iso_utc(_utc_aware(turno.fin)),
        "duracion_min": turno.duracion_min,
        "notificaciones_encoladas": encoladas,
    }


def _utc_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise HTTPException(status_code=500, detail="Error interno")
    return value.astimezone(UTC)


def reprogramar(
    db: Session,
    turno_id: uuid.UUID,
    data: TurnoReprogramar,
    *,
    actor: dict,
    now_provider: Callable[[], datetime] | None = None,
) -> dict:
    """Reprograma/cambia duración con anti-solape y auditoría (D-4/D-10/D-11)."""
    now = (now_provider or now_utc)().astimezone(UTC)

    turno = _cargar_turno_lock(db, turno_id)
    if turno is None:
        raise HTTPException(status_code=404, detail="No encontrado")
    if turno.estado not in ESTADOS_EDITABLES:
        raise _codigo(
            {"codigo": "turno_no_editable", "mensaje": "El turno no es editable"}
        )

    inicio_previo = _utc_aware(turno.inicio)
    fin_previo = _utc_aware(turno.fin)
    duracion_previa = turno.duracion_min

    nuevo_inicio = inicio_previo
    if data.inicio is not None:
        nuevo_inicio = data.inicio.astimezone(UTC)
        if nuevo_inicio <= now:
            raise _error("inicio", "`inicio` debe ser una fecha futura")

    profesional = _cargar_profesional_lock(db, turno.profesional_id)
    if profesional is None or not profesional.activo:
        raise HTTPException(status_code=404, detail="No encontrado")
    granularidad = profesional.duracion_default_min or 30

    nueva_duracion = duracion_previa
    if data.duracion_min is not None:
        nueva_duracion = _validar_duracion_valor(data.duracion_min, granularidad)
    nuevo_fin = nuevo_inicio + timedelta(minutes=nueva_duracion)

    if nuevo_inicio == inicio_previo and nueva_duracion == duracion_previa:
        return {
            "id": turno.id,
            "estado": turno.estado.value,
            "inicio": _iso_utc(inicio_previo),
            "fin": _iso_utc(fin_previo),
            "duracion_min": duracion_previa,
            "notificaciones_encoladas": False,
        }

    if not _slot_disponible(
        db,
        profesional.id,
        nuevo_inicio,
        nuevo_fin,
        granularidad,
        excluir_turno_id=turno.id,
    ):
        codigo = (
            "slot_ocupado"
            if _inicio_ocupado(
                db, profesional.id, nuevo_inicio, excluir_turno_id=turno.id
            )
            else "slot_no_disponible"
        )
        alternativos = _alternativos(
            db,
            profesional.id,
            nuevo_inicio,
            nueva_duracion,
            granularidad,
            excluir_turno_id=turno.id,
        )
        raise HTTPException(
            status_code=409,
            detail={"codigo": codigo, "alternativos": alternativos},
        )

    turno.inicio = nuevo_inicio
    turno.fin = nuevo_fin
    turno.duracion_min = nueva_duracion
    turno.updated_at = now
    try:
        db.flush()
    except IntegrityError as exc:
        if _nombre_constraint(exc) == "no_solape_prof":
            db.rollback()
            alternativos = _alternativos(
                db, profesional.id, nuevo_inicio, nueva_duracion, granularidad
            )
            raise HTTPException(
                status_code=409,
                detail={"codigo": "slot_ocupado", "alternativos": alternativos},
            ) from None
        raise HTTPException(status_code=500, detail="Error interno") from None

    paciente = db.query(Paciente).filter(Paciente.id == turno.paciente_id).one()
    detalle_descarte = f"inicio {_iso_utc(inicio_previo)} -> {_iso_utc(nuevo_inicio)}"
    descartadas = _descartar_pendientes(db, turno_id=turno.id, detalle=detalle_descarte)
    encoladas = False
    if descartadas:
        encoladas = _encolar_notificaciones(
            db,
            turno=turno,
            paciente_nombre=paciente.nombre or "",
            paciente_email=paciente.email or "",
            profesional_nombre=profesional.nombre,
            inicio=nuevo_inicio,
            fin=nuevo_fin,
            duracion=nueva_duracion,
            now=now,
            cancel_url=_cancel_url(turno.token_cancelacion, turno.id),
        )

    cambios: dict = {}
    if nuevo_inicio != inicio_previo:
        cambios["inicio"] = {
            "antes": _iso_utc(inicio_previo),
            "despues": _iso_utc(nuevo_inicio),
        }
    if nueva_duracion != duracion_previa:
        cambios["duracion_min"] = {
            "antes": duracion_previa,
            "despues": nueva_duracion,
        }
    db.add(
        AuditoriaTurno(
            turno_id=turno.id,
            actor_id=uuid.UUID(actor["id"]),
            accion="reprogramar",
            detalle={
                "actor": actor,
                "origen": "staff",
                "estado_previo": turno.estado.value,
                "estado_nuevo": turno.estado.value,
                "cambios": cambios,
                "notificaciones_encoladas": encoladas,
            },
        )
    )
    db.flush()
    respuesta = _respuesta_reprogramacion(turno, encoladas)
    db.commit()
    return respuesta


def cancelar_staff(
    db: Session,
    turno_id: uuid.UUID,
    *,
    motivo: str | None,
    actor: dict,
    now_provider: Callable[[], datetime] | None = None,
) -> dict:
    """Cancela como staff, forzando `<3 h` solo con motivo (D-6)."""
    from app.modules.turnos import cancellation_service

    now = (now_provider or now_utc)().astimezone(UTC)
    turno = _cargar_turno_lock(db, turno_id)
    if turno is None:
        raise HTTPException(status_code=404, detail="No encontrado")
    if turno.estado == TurnoEstado.cancelado:
        raise _codigo(
            {
                "codigo": "turno_ya_cancelado",
                "mensaje": "El turno ya está cancelado",
            }
        )
    if turno.estado not in ESTADOS_CANCELABLES:
        raise _codigo(
            {
                "codigo": "turno_no_cancelable",
                "mensaje": "El turno no se puede cancelar en su estado actual",
            }
        )

    inicio = _utc_aware(turno.inicio)
    fin = _utc_aware(turno.fin)
    estado_previo = turno.estado
    limite = timedelta(hours=get_settings().CANCEL_HOURS_MIN)
    forzada = inicio - now < limite
    if forzada and motivo is None:
        raise _codigo(
            {
                "codigo": "motivo_requerido",
                "mensaje": "Se requiere `motivo` para forzar la cancelación",
            }
        )

    turno.estado = TurnoEstado.cancelado
    turno.updated_at = now
    db.flush()

    encoladas = cancellation_service._encolar(db, turno=turno, now=now)
    detalle: dict = {
        "actor": actor,
        "origen": "staff",
        "estado_previo": estado_previo.value,
        "estado_nuevo": TurnoEstado.cancelado.value,
        "inicio": _iso_utc(inicio),
        "fin": _iso_utc(fin),
        "duracion_min": turno.duracion_min,
        "notificaciones_encoladas": encoladas,
    }
    if motivo is not None:
        detalle["motivo"] = motivo
    db.add(
        AuditoriaTurno(
            turno_id=turno.id,
            actor_id=uuid.UUID(actor["id"]),
            accion="forzar_cancelacion" if forzada else "cancelar",
            detalle=detalle,
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


def _paciente_out(paciente: Paciente) -> dict:
    return {
        "id": paciente.id,
        "nombre": paciente.nombre,
        "dni": paciente.dni,
        "telefono": paciente.telefono,
        "obra_social": paciente.obra_social,
        "email": paciente.email,
        "activo": paciente.activo,
    }


def actualizar_paciente(
    db: Session,
    turno_id: uuid.UUID,
    data: CorreccionPacienteIn,
    *,
    actor: dict,
    now_provider: Callable[[], datetime] | None = None,
) -> dict:
    """Corrige la fila `Paciente` compartida con auditoría antes→después (D-7)."""
    now = (now_provider or now_utc)().astimezone(UTC)
    turno = _cargar_turno_lock(db, turno_id)
    if turno is None:
        raise HTTPException(status_code=404, detail="No encontrado")

    paciente = (
        db.query(Paciente)
        .filter(Paciente.id == turno.paciente_id)
        .with_for_update()
        .one_or_none()
    )
    if paciente is None:
        raise HTTPException(status_code=404, detail="No encontrado")

    enviados = {
        campo: valor
        for campo, valor in (
            ("dni", data.dni),
            ("telefono", data.telefono),
            ("obra_social", data.obra_social),
        )
        if valor is not None
    }
    cambios: dict = {}
    for campo, valor in enviados.items():
        antes = getattr(paciente, campo)
        if antes != valor:
            cambios[campo] = {"antes": antes, "despues": valor}

    if not cambios:
        return {
            "id": turno.id,
            "paciente": _paciente_out(paciente),
            "notificaciones_encoladas": False,
        }

    nuevo_dni = cambios.get("dni", {}).get("despues")
    if nuevo_dni is not None:
        duplicado = (
            db.query(Paciente.id)
            .filter(Paciente.dni == nuevo_dni, Paciente.id != paciente.id)
            .first()
        )
        if duplicado is not None:
            raise HTTPException(status_code=409, detail={"codigo": "dni_duplicado"})

    for campo, detalle_cambio in cambios.items():
        setattr(paciente, campo, detalle_cambio["despues"])
    paciente.updated_at = now
    try:
        db.flush()
    except IntegrityError as exc:
        if _nombre_constraint(exc) == "ux_paciente_dni":
            db.rollback()
            raise HTTPException(
                status_code=409, detail={"codigo": "dni_duplicado"}
            ) from None
        raise HTTPException(status_code=500, detail="Error interno") from None

    db.add(
        AuditoriaTurno(
            turno_id=turno.id,
            actor_id=uuid.UUID(actor["id"]),
            accion="editar_paciente",
            detalle={
                "actor": actor,
                "origen": "staff",
                "cambios": cambios,
                "notificaciones_encoladas": False,
            },
        )
    )
    db.flush()
    respuesta = {
        "id": turno.id,
        "paciente": _paciente_out(paciente),
        "notificaciones_encoladas": False,
    }
    db.commit()
    return respuesta


TRANSICIONES_VALIDAS = {
    (TurnoEstado.reservado, TurnoEstado.confirmado),
    (TurnoEstado.confirmado, TurnoEstado.atendido),
    (TurnoEstado.confirmado, TurnoEstado.ausente),
}


def cambiar_estado(
    db: Session,
    turno_id: uuid.UUID,
    nuevo: TurnoEstado,
    *,
    actor: dict,
    now_provider: Callable[[], datetime] | None = None,
) -> dict:
    """Aplica la matriz cerrada de RN-TU-07 con lock y auditoría (D-5)."""
    now = (now_provider or now_utc)().astimezone(UTC)
    turno = _cargar_turno_lock(db, turno_id)
    if turno is None:
        raise HTTPException(status_code=404, detail="No encontrado")

    previo = turno.estado
    if (previo, nuevo) not in TRANSICIONES_VALIDAS:
        raise _codigo(
            {
                "codigo": "transicion_invalida",
                "mensaje": f"No se puede pasar de {previo.value} a {nuevo.value}",
            }
        )

    turno.estado = nuevo
    turno.updated_at = now
    db.flush()
    db.add(
        AuditoriaTurno(
            turno_id=turno.id,
            actor_id=uuid.UUID(actor["id"]),
            accion="cambiar_estado",
            detalle={
                "actor": actor,
                "origen": "staff",
                "estado_previo": previo.value,
                "estado_nuevo": nuevo.value,
                "notificaciones_encoladas": False,
            },
        )
    )
    db.flush()
    respuesta = {
        "id": turno.id,
        "estado": nuevo.value,
        "estado_previo": previo.value,
        "notificaciones_encoladas": False,
    }
    db.commit()
    return respuesta


def codificar_cursor_historial(created_at: datetime, auditoria_id: uuid.UUID) -> str:
    """Cursor opaco `base64url(created_at_iso|id)` del historial (D-9)."""
    crudo = f"{created_at.astimezone(UTC).isoformat()}|{auditoria_id}"
    return base64.urlsafe_b64encode(crudo.encode("utf-8")).decode().rstrip("=")


def decodificar_cursor_historial(cursor: str) -> tuple[datetime, uuid.UUID]:
    """Inverso del cursor de historial; anomalía → `HistorialCursorInvalido`."""
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        crudo = base64.b64decode(padded, altchars=b"-_", validate=True).decode("utf-8")
        created_texto, separador, id_texto = crudo.partition("|")
        if not separador or not created_texto or not id_texto:
            raise ValueError("formato inesperado")
        created = datetime.fromisoformat(created_texto)
        if created.tzinfo is None or created.utcoffset() is None:
            raise ValueError("created_at sin zona horaria")
        return created.astimezone(UTC), uuid.UUID(id_texto)
    except (binascii.Error, UnicodeDecodeError, ValueError):
        raise HistorialCursorInvalido("cursor inválido") from None


_SQL_FICHA = text(
    """
    SELECT t.id,
           t.estado,
           t.origen,
           t.inicio,
           t.fin,
           t.duracion_min,
           p.id AS profesional_id,
           p.nombre AS profesional_nombre,
           p.especialidad AS profesional_especialidad,
           pa.id AS paciente_id,
           pa.nombre AS paciente_nombre,
           pa.dni AS paciente_dni,
           pa.telefono AS paciente_telefono,
           pa.obra_social AS paciente_obra_social,
           pa.email AS paciente_email,
           pa.activo AS paciente_activo
    FROM turno AS t
    JOIN profesional AS p ON p.id = t.profesional_id
    JOIN paciente AS pa ON pa.id = t.paciente_id
    WHERE t.id = :turno_id
    """
)

_SQL_HISTORIAL = text(
    """
    SELECT a.id,
           a.accion,
           a.actor_id,
           a.created_at,
           a.detalle,
           u.email AS actor_email,
           u.rol AS actor_rol
    FROM auditoria_turno AS a
    LEFT JOIN usuario_staff AS u ON u.id = a.actor_id
    WHERE a.turno_id = :turno_id
    ORDER BY a.created_at ASC, a.id ASC
    LIMIT :limite
    """
)

_SQL_HISTORIAL_CURSOR = text(
    """
    SELECT a.id,
           a.accion,
           a.actor_id,
           a.created_at,
           a.detalle,
           u.email AS actor_email,
           u.rol AS actor_rol
    FROM auditoria_turno AS a
    LEFT JOIN usuario_staff AS u ON u.id = a.actor_id
    WHERE a.turno_id = :turno_id
      AND (a.created_at, a.id) > (
          CAST(:cursor_created AS timestamptz),
          CAST(:cursor_id AS uuid)
      )
    ORDER BY a.created_at ASC, a.id ASC
    LIMIT :limite
    """
)


def _actor_out(fila) -> dict:
    if fila.actor_id is None:
        return {"tipo": "paciente"}
    return {
        "tipo": "staff",
        "id": str(fila.actor_id),
        "email": fila.actor_email,
        "rol": str(fila.actor_rol) if fila.actor_rol is not None else None,
    }


def obtener_ficha(
    db: Session,
    turno_id: uuid.UUID,
    *,
    historial_limit: int,
    historial_cursor: str | None,
) -> dict:
    """Ficha con columnas explícitas y historial keyset sin OFFSET (D-9)."""
    fila = db.execute(_SQL_FICHA, {"turno_id": turno_id}).first()
    if fila is None:
        raise HTTPException(status_code=404, detail="No encontrado")

    parametros: dict = {"turno_id": turno_id, "limite": historial_limit + 1}
    sentencia = _SQL_HISTORIAL
    if historial_cursor is not None:
        created, auditoria_id = decodificar_cursor_historial(historial_cursor)
        parametros["cursor_created"] = created
        parametros["cursor_id"] = auditoria_id
        sentencia = _SQL_HISTORIAL_CURSOR
    filas = db.execute(sentencia, parametros).all()
    visibles = filas[:historial_limit]
    next_cursor = (
        codificar_cursor_historial(visibles[-1].created_at, visibles[-1].id)
        if len(filas) > historial_limit
        else None
    )

    return {
        "id": fila.id,
        "estado": fila.estado,
        "origen": fila.origen,
        "inicio": fila.inicio,
        "fin": fila.fin,
        "duracion_min": fila.duracion_min,
        "profesional": {
            "id": fila.profesional_id,
            "nombre": fila.profesional_nombre,
            "especialidad": fila.profesional_especialidad,
        },
        "paciente": {
            "id": fila.paciente_id,
            "nombre": fila.paciente_nombre,
            "dni": fila.paciente_dni,
            "telefono": fila.paciente_telefono,
            "obra_social": fila.paciente_obra_social,
            "email": fila.paciente_email,
            "activo": fila.paciente_activo,
        },
        "auditoria": {
            "items": [
                {
                    "id": item.id,
                    "accion": item.accion,
                    "actor": _actor_out(item),
                    "created_at": item.created_at,
                    "detalle": item.detalle,
                }
                for item in visibles
            ],
            "next_cursor": next_cursor,
        },
    }
