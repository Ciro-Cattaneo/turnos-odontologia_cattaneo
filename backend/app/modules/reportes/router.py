"""Endpoint del reporte de ocupación (C-11 D-8/D-10, RE-R1..R5).

Borde HTTP delgado: parseo del query `extra='forbid'` → 400 por campo (el
validador de `hasta` emite `campo="hasta"`), sesión obligatoria (401) y
alcance por rol (403 odontólogo ajeno/sin vínculo) delegado a `service`.
Sin export: cualquier `format`/`csv`/`xlsx` es clave desconocida (PB-06).
"""

from fastapi import APIRouter, Request

from app.modules.agenda.public import parse_query_or_400
from app.modules.auth.deps import CurrentStaff, DbSession
from app.modules.reportes import service
from app.modules.reportes.schemas import (
    ReporteOcupacionOut,
    ReporteOcupacionQuery,
)

router = APIRouter(prefix="/api/reportes", tags=["reportes"])


@router.get("/ocupacion", response_model=ReporteOcupacionOut)
def reporte_ocupacion(request: Request, staff: CurrentStaff, db: DbSession) -> dict:
    """Reporte tabular por profesional y período (tabla JSON, sin export)."""
    query = parse_query_or_400(ReporteOcupacionQuery, dict(request.query_params))
    profesional_id = service.resolver_alcance(staff, query.profesional_id)
    return service.generar_reporte(db, query.desde, query.hasta, profesional_id)


__all__ = ["reporte_ocupacion", "router"]
