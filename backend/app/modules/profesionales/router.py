"""Profesionales públicos + agenda día/semana (C-04 D-1/D-4/D-6).

Delgado (D-1): valida schemas (`extra='forbid'` → 400), resuelve staff
opcional (pública sin auth; staff con sesión), y delega el cómputo a
`slot_service`. Auth consumida de C-03 (`require_role`,
`require_own_profesional`): se IMPORTA, no se duplica.
"""

from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import HTTPException

from app.models.paciente import Paciente
from app.models.profesional import Profesional
from app.models.turno import Turno
from app.modules.agenda import slot_service
from app.modules.agenda.public import (
    parse_query_or_400,
    public_throttle,
    staff_opcional,
)
from app.modules.agenda.schemas import AgendaQuery, ProfesionalesQuery
from app.modules.auth.deps import DbSession, require_own_profesional

router = APIRouter(prefix="/api/profesionales", tags=["profesionales"])

TZ = ZoneInfo("America/Argentina/Buenos_Aires")


@router.get("", dependencies=[Depends(public_throttle)])
def listar_profesionales(request: Request, db: DbSession) -> dict:
    """Lista pública paginada por keyset (`id` cursor, sin OFFSET).

    # AC agenda-disponibilidad/Listado-público (solo activos, columnas
    explícitas, sin datos staff).
    """
    query = parse_query_or_400(
        ProfesionalesQuery, dict(request.query_params)
    )
    q = (
        db.query(
            Profesional.id,
            Profesional.nombre,
            Profesional.especialidad,
            Profesional.matricula,
            Profesional.duracion_default_min,
            Profesional.ultima_actualizacion,
        )
        .filter(Profesional.activo.is_(True))
        .order_by(Profesional.id)
    )
    if query.cursor is not None:
        q = q.filter(Profesional.id > query.cursor)
    filas = q.limit(query.limit + 1).all()
    items = [
        {
            "id": str(r[0]),
            "nombre": r[1],
            "especialidad": r[2],
            "matricula": r[3],
            "duracion_default_min": r[4],
            "ultima_actualizacion": r[5].isoformat() if r[5] else None,
        }
        for r in filas[: query.limit]
    ]
    next_cursor = str(filas[query.limit - 1][0]) if len(filas) > query.limit else None
    return {"items": items, "next_cursor": next_cursor}


def _rango_dias(vista: str, fecha: date) -> list[date]:
    if vista == "dia":
        return [fecha]
    return [fecha + timedelta(days=i) for i in range(7)]


@router.get("/{profesional_id}/agenda", dependencies=[Depends(public_throttle)])
def agenda_por_profesional(
    profesional_id: UUID, request: Request, db: DbSession
) -> dict:
    """Agenda día/semana: pública (solo libres) o staff (tipificada).

    # AC agenda-disponibilidad/Agenda-día/semana (staff + pública, keyset por
    `fecha`, 404 inactivo para público, histórico visible para staff).
    """
    query = parse_query_or_400(AgendaQuery, dict(request.query_params))
    staff = staff_opcional(request, db)
    prof = (
        db.query(Profesional).filter(Profesional.id == profesional_id).one_or_none()
    )
    if prof is None:
        raise HTTPException(status_code=404, detail="No encontrado")
    if not prof.activo and staff is None:
        raise HTTPException(status_code=404, detail="No encontrado")
    if staff is not None:
        if staff.rol == "odontologo":
            require_own_profesional(profesional_id, staff)
        elif staff.rol not in ("recepcion", "admin"):
            raise HTTPException(status_code=403, detail="Sin permiso")
    dias = _rango_dias(query.vista, query.fecha)
    ventanas = slot_service.fetch_ventanas(db, prof.id)
    dur = prof.duracion_default_min or 30
    dias_out = []
    for d in dias:
        dia_ini = datetime(d.year, d.month, d.day, tzinfo=TZ)
        dia_fin = dia_ini + timedelta(days=1)
        libres = slot_service.compute_slots(
            ventanas,
            slot_service.fetch_bloqueos(db, prof.id, dia_ini, dia_fin),
            slot_service.fetch_turnos_activos(db, prof.id, dia_ini, dia_fin),
            dur,
            d,
            d,
            TZ,
        )
        franjas = [
            {"tipo": "libre", "inicio": s.inicio.isoformat(), "fin": s.fin.isoformat()}
            for s in libres
        ]
        if staff is not None:
            franjas.extend(_franjas_staff(db, prof.id, dia_ini, dia_fin))
            franjas.sort(key=lambda f: f["inicio"])
        dias_out.append({"fecha": d.isoformat(), "franjas": franjas})
    avance = 1 if query.vista == "dia" else 7
    return {
        "profesional_id": str(prof.id),
        "vista": query.vista,
        "dias": dias_out,
        "next_cursor": (query.fecha + timedelta(days=avance)).isoformat(),
        "ultima_actualizacion": (
            prof.ultima_actualizacion.isoformat()
            if prof.ultima_actualizacion
            else None
        ),
    }


def _franjas_staff(
    db: DbSession, profesional_id: UUID, dia_ini: datetime, dia_fin: datetime
) -> list[dict]:
    """Ocupados (estado + paciente mínimo) y bloqueados (motivo) del día."""
    from app.models.bloqueo import Bloqueo

    turnos = (
        db.query(
            Turno.inicio, Turno.fin, Turno.estado, Paciente.id, Paciente.nombre
        )
        .join(Paciente, Paciente.id == Turno.paciente_id)
        .filter(
            Turno.profesional_id == profesional_id,
            Turno.inicio >= dia_ini,
            Turno.inicio < dia_fin,
            Turno.estado.in_(list(slot_service.ESTADOS_ACTIVOS)),
        )
        .order_by(Turno.inicio)
        .all()
    )
    bloqueos = (
        db.query(Bloqueo.desde, Bloqueo.hasta, Bloqueo.motivo)
        .filter(
            Bloqueo.profesional_id == profesional_id,
            Bloqueo.desde < dia_fin,
            Bloqueo.hasta > dia_ini,
        )
        .order_by(Bloqueo.desde)
        .all()
    )
    franjas = [
        {
            "tipo": "ocupado",
            "inicio": t[0].isoformat(),
            "fin": t[1].isoformat(),
            "estado": str(t[2].value if hasattr(t[2], "value") else t[2]),
            "paciente": {"id": str(t[3]), "nombre": t[4]},
        }
        for t in turnos
    ]
    franjas.extend(
        {
            "tipo": "bloqueado",
            "inicio": b[0].isoformat(),
            "fin": b[1].isoformat(),
            "motivo": b[2],
        }
        for b in bloqueos
    )
    return franjas


# Re-export para que `func` no quede sin uso si el linter lo marca.
__all__ = ["agenda_por_profesional", "listar_profesionales"]
