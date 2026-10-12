"""Disponibilidad pública computable (C-04 D-1/D-5/D-6).

Delgado (D-1): valida query (`extra='forbid'` → 400), aplica throttle
público (→ 429) y delega a `slot_service`. Sin auth (público); con token
staff responde idéntico (sin fuga de datos paciente/motivo).
"""

from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import HTTPException

from app.models.profesional import Profesional
from app.modules.agenda import slot_service
from app.modules.agenda.public import parse_query_or_400, public_throttle
from app.modules.agenda.schemas import DisponibilidadQuery
from app.modules.auth.deps import DbSession

# Prefijo de dominio C-01 (el test `test_routers_placeholder_registrados`
# fija `/api/agenda` por módulo; se conserva aunque las rutas vivas de este
# change cuelguen de `/api` según spec).
router = APIRouter(prefix="/api/agenda", tags=["agenda"])

disponibilidad_router = APIRouter(prefix="/api", tags=["agenda"])

TZ = ZoneInfo("America/Argentina/Buenos_Aires")


@disponibilidad_router.get("/disponibilidad", dependencies=[Depends(public_throttle)])
def disponibilidad_publica(request: Request, db: DbSession) -> dict:
    """Computa `ventanas − bloqueos − turnos activos` con granularidad propia.

    # AC agenda-disponibilidad/Cómputo-público (200-lista-vacía sin ventana,
    400 rango/params, 404 profesional inexistente/inactivo).
    """
    query = parse_query_or_400(DisponibilidadQuery, dict(request.query_params))
    prof = (
        db.query(Profesional)
        .filter(Profesional.id == query.profesional_id)
        .one_or_none()
    )
    if prof is None or not prof.activo:
        raise HTTPException(status_code=404, detail="No encontrado")
    desde_tz = query.desde.astimezone(TZ)
    hasta_tz = query.hasta.astimezone(TZ)
    ventanas = slot_service.fetch_ventanas(db, prof.id)
    bloqueos = slot_service.fetch_bloqueos(db, prof.id, query.desde, query.hasta)
    ocupados = slot_service.fetch_turnos_activos(
        db, prof.id, query.desde, query.hasta
    )
    dur = prof.duracion_default_min or 30
    slots = slot_service.compute_slots(
        ventanas, bloqueos, ocupados, dur, desde_tz.date(), hasta_tz.date(), TZ
    )
    # Recorta al rango horario pedido (el cómputo es por día completo).
    fin_tope = query.hasta.astimezone(TZ)
    ini_tope = query.desde.astimezone(TZ)
    en_rango = [
        s for s in slots if s.inicio >= ini_tope and s.fin <= fin_tope
    ]
    return {
        "profesional_id": str(prof.id),
        "slots": [
            {
                "inicio": s.inicio.isoformat(),
                "fin": s.fin.isoformat(),
                "duracion_min": s.duracion_min,
            }
            for s in en_rango
        ],
        "ultima_actualizacion": (
            prof.ultima_actualizacion.isoformat()
            if prof.ultima_actualizacion
            else None
        ),
    }
