"""Agregación y capacidad del reporte de ocupación (C-11 D-8..D-11).

- Una sola agregación de turnos (`GROUP BY profesional_id, estado`, columnas
  explícitas, sin `SELECT *` ni `OFFSET`).
- Capacidad ofrecible = `len(compute_slots(..., ocupados=[])) * duracion` con
  la configuración vigente al consultar (D-9): reutiliza la grilla de C-04.
- Rango local `[desde 00:00, hasta+1d 00:00)` en `America/Argentina/
  Buenos_Aires` convertido a UTC para comparar con `turno.inicio` (duro 10).
- `%` = minutos ocupados / minutos disponibles, `null` si capacidad 0 y sin
  recorte a 100 (señala sobreasignación).
"""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi.exceptions import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.profesional import Profesional
from app.models.turno import Turno
from app.modules.agenda import slot_service

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
ZONA = "America/Argentina/Buenos_Aires"

# Estados que ocupan minutos (el `cancelado` liberó el slot, D-9).
ESTADOS_OCUPAN = ("reservado", "confirmado", "atendido", "ausente")

_DEFAULT_DURACION = 30


def capacidad_ofrecible(
    ventanas: list, bloqueos: list, duracion_min: int, desde: date, hasta: date, tz=TZ
) -> int:
    """Minutos ofrecibles por la grilla real sin turnos (RE-R2, D-9).

    Reutiliza `slot_service.compute_slots` con `ocupados=[]`, por lo que
    respeta bloqueos y `vigente_desde`/`vigente_hasta`, y descuenta el resto
    no múltiplo de la ventana.
    """
    slots = slot_service.compute_slots(
        ventanas, bloqueos, [], duracion_min, desde, hasta, tz
    )
    return len(slots) * duracion_min


def porcentaje_ocupacion(
    minutos_ocupados: int, minutos_disponibles: int
) -> float | None:
    """`%` redondeado a un decimal; `null` si no hay capacidad (D-9)."""
    if minutos_disponibles <= 0:
        return None
    return round(minutos_ocupados / minutos_disponibles * 100, 1)


def _borde_utc(desde: date, hasta: date) -> tuple[datetime, datetime]:
    """`[desde 00:00, hasta+1d 00:00)` local → instantes UTC (D-10)."""
    inicio = datetime(desde.year, desde.month, desde.day, tzinfo=TZ)
    fin = datetime(hasta.year, hasta.month, hasta.day, tzinfo=TZ) + timedelta(days=1)
    return inicio.astimezone(UTC), fin.astimezone(UTC)


def _agregado(
    db: Session,
    desde_utc: datetime,
    hasta_utc: datetime,
    profesional_id: UUID | None,
) -> list:
    """Una sola agregación condicional por profesional y estado (D-11)."""
    q = (
        db.query(
            Turno.profesional_id,
            Turno.estado,
            func.count(),
            func.sum(Turno.duracion_min),
        )
        .filter(Turno.inicio >= desde_utc, Turno.inicio < hasta_utc)
        .group_by(Turno.profesional_id, Turno.estado)
    )
    if profesional_id is not None:
        q = q.filter(Turno.profesional_id == profesional_id)
    return q.all()


def _contadores(agregado: list) -> dict:
    """Acumula el agregado por profesional (pendientes deriva del total)."""
    data: dict = {}
    for profesional_id, estado, cantidad, minutos in agregado:
        valor = estado.value if hasattr(estado, "value") else str(estado)
        acc = data.setdefault(
            profesional_id,
            {
                "turnos": 0,
                "atendidos": 0,
                "ausentes": 0,
                "cancelados": 0,
                "minutos_ocupados": 0,
            },
        )
        acc["turnos"] += cantidad
        if valor == "atendido":
            acc["atendidos"] += cantidad
        elif valor == "ausente":
            acc["ausentes"] += cantidad
        elif valor == "cancelado":
            acc["cancelados"] += cantidad
        if valor in ESTADOS_OCUPAN:
            acc["minutos_ocupados"] += minutos or 0
    return data


def _filas_profesionales(
    db: Session, profesional_id: UUID | None, con_turnos: set
) -> list:
    """Activos + inactivos con turnos; el filtrado se incluye siempre (D-9)."""
    columnas = (
        Profesional.id,
        Profesional.nombre,
        Profesional.activo,
        Profesional.duracion_default_min,
    )
    if profesional_id is not None:
        fila = (
            db.query(*columnas).filter(Profesional.id == profesional_id).one_or_none()
        )
        return [] if fila is None else [fila]
    return (
        db.query(*columnas)
        .filter(
            or_(
                Profesional.activo.is_(True),
                Profesional.id.in_(con_turnos),
            )
        )
        .order_by(Profesional.nombre, Profesional.id)
        .all()
    )


def _minutos_disponibles(
    db: Session,
    profesional_id: UUID,
    duracion_default_min: int | None,
    desde: date,
    hasta: date,
    desde_utc: datetime,
    hasta_utc: datetime,
) -> int:
    """Capacidad del rango con ventanas/bloqueos y duración actuales (D-9)."""
    ventanas = slot_service.fetch_ventanas(db, profesional_id)
    bloqueos = slot_service.fetch_bloqueos(db, profesional_id, desde_utc, hasta_utc)
    duracion = duracion_default_min or _DEFAULT_DURACION
    return capacidad_ofrecible(ventanas, bloqueos, duracion, desde, hasta, TZ)


def _fila(
    db: Session,
    profesional,
    contadores: dict,
    desde: date,
    hasta: date,
    desde_utc: datetime,
    hasta_utc: datetime,
) -> dict:
    profesional_id, nombre, activo, duracion = profesional
    acc = contadores.get(
        profesional_id,
        {
            "turnos": 0,
            "atendidos": 0,
            "ausentes": 0,
            "cancelados": 0,
            "minutos_ocupados": 0,
        },
    )
    pendientes = acc["turnos"] - acc["atendidos"] - acc["ausentes"] - acc["cancelados"]
    disponibles = _minutos_disponibles(
        db, profesional_id, duracion, desde, hasta, desde_utc, hasta_utc
    )
    return {
        "profesional": {
            "id": profesional_id,
            "nombre": nombre,
            "activo": activo,
        },
        "turnos": acc["turnos"],
        "atendidos": acc["atendidos"],
        "ausentes": acc["ausentes"],
        "cancelados": acc["cancelados"],
        "pendientes": pendientes,
        "minutos_ocupados": acc["minutos_ocupados"],
        "minutos_disponibles": disponibles,
        "porcentaje_ocupacion": porcentaje_ocupacion(
            acc["minutos_ocupados"], disponibles
        ),
    }


def _totales(items: list) -> dict:
    """Suma de las filas y `%` recalculado sobre las sumas (RE-R1, D-9)."""
    totales = {
        campo: sum(fila[campo] for fila in items)
        for campo in (
            "turnos",
            "atendidos",
            "ausentes",
            "cancelados",
            "pendientes",
            "minutos_ocupados",
            "minutos_disponibles",
        )
    }
    totales["porcentaje_ocupacion"] = porcentaje_ocupacion(
        totales["minutos_ocupados"], totales["minutos_disponibles"]
    )
    return totales


def generar_reporte(
    db: Session,
    desde: date,
    hasta: date,
    profesional_id: UUID | None = None,
) -> dict:
    """Reporte tabular de ocupación para el alcance ya resuelto (D-8/D-9)."""
    desde_utc, hasta_utc = _borde_utc(desde, hasta)
    agregado = _agregado(db, desde_utc, hasta_utc, profesional_id)
    contadores = _contadores(agregado)
    profesionales = _filas_profesionales(db, profesional_id, set(contadores))
    items = [
        _fila(db, prof, contadores, desde, hasta, desde_utc, hasta_utc)
        for prof in profesionales
    ]
    return {
        "desde": desde,
        "hasta": hasta,
        "zona": ZONA,
        "items": items,
        "totales": _totales(items),
    }


def resolver_alcance(staff, profesional_id: UUID | None) -> UUID | None:
    """Alcance por rol (RE-R5, D-2): total o solo la fila propia del odontólogo."""
    if staff.rol in ("admin", "recepcion"):
        return profesional_id
    if staff.profesional_id is None:
        raise HTTPException(status_code=403, detail="Sin permiso") from None
    propio = UUID(str(staff.profesional_id))
    if profesional_id is not None and UUID(str(profesional_id)) != propio:
        raise HTTPException(status_code=403, detail="Sin permiso") from None
    return propio
