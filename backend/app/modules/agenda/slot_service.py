"""Cómputo puro de slots `ventanas − bloqueos − ocupados` (C-04 D-1).

Puro: sin DB ni IO — testeable con matriz parametrizada sin fixtures.
La reserva (C-05) REVALIDA el slot en su propia transacción con este mismo
módulo + `SELECT FOR UPDATE`/EXCLUDE de turnos (contrato D-3): NO asumir
invariante DB en disponibilidades — el overlap de ventanas es app-level con
`SELECT FOR UPDATE` en writes (`disponibilidades_service`), no EXCLUDE.

Semántica half-open `[)`: un slot/bloqueo/turno que empieza exactamente donde
termina otro NO solapa (simétrico al EXCLUDE `no_solape_prof` de C-02).
TZ display `America/Argentina/Buenos_Aires`; persistencia UTC (regla dura 10):
este módulo trabaja con datetimes aware y no convierte a naive.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

# Estados que ocupan un slot (coherente con el predicado EXCLUDE C-02 y el
# parcial `ix_turno_estado_inicio`): solo reservado/confirmado.
ESTADOS_ACTIVOS = ("reservado", "confirmado")


@dataclass(frozen=True)
class Ventana:
    """Ventana semanal recurrente (refleja `Disponibilidad`)."""

    dia_semana: int  # 0=lunes … 6=domingo (== `date.weekday()`)
    hora_desde: time
    hora_hasta: time
    vigente_desde: date | None = None
    vigente_hasta: date | None = None


@dataclass(frozen=True)
class BloqueoRango:
    """Rango absoluto que resta slots (aware)."""

    desde: datetime
    hasta: datetime


@dataclass(frozen=True)
class TurnoOcupado:
    """Turno ACTIVO ya filtrado (reservado/confirmado) que resta slots."""

    inicio: datetime
    fin: datetime


@dataclass(frozen=True)
class Slot:
    """Slot libre ofrecido (aware, `[inicio, fin)`)."""

    inicio: datetime
    fin: datetime

    @property
    def duracion_min(self) -> int:
        """Duración entera del slot en minutos."""
        return round((self.fin - self.inicio).total_seconds() / 60)


def _solapa(a_ini: datetime, a_fin: datetime, b_ini: datetime, b_fin: datetime) -> bool:
    """Solape half-open `[)`: borde exacto no es solape."""
    return a_ini < b_fin and b_ini < a_fin


def compute_slots(
    ventanas: list[Ventana],
    bloqueos: list[BloqueoRango],
    ocupados: list[TurnoOcupado],
    duracion_min: int,
    desde: date,
    hasta: date,
    tz: ZoneInfo,
) -> list[Slot]:
    """Calcula slots libres en `[desde, hasta]` (fechas inclusivas).

    # AC agenda-disponibilidad/Cómputo-público (feliz, 45', sin-ventana,
    # borde, liberan-slot).
    """
    if desde > hasta:
        raise ValueError("rango invertido: `desde` > `hasta`")
    if duracion_min <= 0:
        raise ValueError("`duracion_min` debe ser positiva")
    paso = timedelta(minutes=duracion_min)
    libres: list[Slot] = []
    dia = desde
    while dia <= hasta:
        for v in ventanas:
            if v.dia_semana != dia.weekday():
                continue
            if v.vigente_desde is not None and dia < v.vigente_desde:
                continue
            if v.vigente_hasta is not None and dia > v.vigente_hasta:
                continue
            ini = datetime.combine(dia, v.hora_desde, tzinfo=tz)
            fin_vent = datetime.combine(dia, v.hora_hasta, tzinfo=tz)
            cursor = ini
            while cursor + paso <= fin_vent:
                slot_fin = cursor + paso
                ocupado = any(
                    _solapa(cursor, slot_fin, b.desde, b.hasta) for b in bloqueos
                ) or any(
                    _solapa(cursor, slot_fin, t.inicio, t.fin) for t in ocupados
                )
                if not ocupado:
                    libres.append(Slot(inicio=cursor, fin=slot_fin))
                cursor = slot_fin
        dia += timedelta(days=1)
    return sorted(libres, key=lambda s: s.inicio)


# --- Lectura parametrizada (columnas explícitas, sin SELECT *) ---


def fetch_ventanas(db, profesional_id) -> list[Ventana]:
    """Ventanas del profesional (usa `ix_disponibilidad_prof_dia`).

    # AC D-1: columnas explícitas, query parametrizada, sin SELECT *.
    """
    from app.models.disponibilidad import Disponibilidad

    rows = (
        db.query(
            Disponibilidad.dia_semana,
            Disponibilidad.hora_desde,
            Disponibilidad.hora_hasta,
            Disponibilidad.vigente_desde,
            Disponibilidad.vigente_hasta,
        )
        .filter(Disponibilidad.profesional_id == profesional_id)
        .order_by(Disponibilidad.dia_semana, Disponibilidad.hora_desde)
        .all()
    )
    return [
        Ventana(
            dia_semana=r[0],
            hora_desde=r[1],
            hora_hasta=r[2],
            vigente_desde=r[3],
            vigente_hasta=r[4],
        )
        for r in rows
    ]


def fetch_bloqueos(
    db, profesional_id, desde: datetime, hasta: datetime
) -> list[BloqueoRango]:
    """Bloqueos que intersectan `[desde, hasta)` (índice `ix_bloqueo_profesional_id`).

    # AC D-1: columnas explícitas + filtro OVERLAPS half-open.
    """
    from app.models.bloqueo import Bloqueo

    rows = (
        db.query(Bloqueo.desde, Bloqueo.hasta)
        .filter(
            Bloqueo.profesional_id == profesional_id,
            Bloqueo.desde < hasta,
            Bloqueo.hasta > desde,
        )
        .order_by(Bloqueo.desde)
        .all()
    )
    return [BloqueoRango(desde=r[0], hasta=r[1]) for r in rows]


def fetch_turnos_activos(
    db, profesional_id, desde: datetime, hasta: datetime
) -> list[TurnoOcupado]:
    """Turnos activos en el rango (parcial estado + `ix_turno_prof_inicio`).

    # AC D-1: filtro `profesional_id + inicio BETWEEN + estado IN
    # (reservado, confirmado)` para que el planner use el parcial de estado.
    """
    from app.models.turno import Turno

    rows = (
        db.query(Turno.inicio, Turno.fin)
        .filter(
            Turno.profesional_id == profesional_id,
            Turno.inicio >= desde,
            Turno.inicio < hasta,
            Turno.estado.in_(list(ESTADOS_ACTIVOS)),
        )
        .order_by(Turno.inicio)
        .all()
    )
    return [TurnoOcupado(inicio=r[0], fin=r[1]) for r in rows]
