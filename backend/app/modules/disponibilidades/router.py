"""CRUD staff de disponibilidades (C-04 D-3/D-4/D-6).

Escritura: `recepcion`/`admin` (vía `require_role` de C-03, importado).
Lectura: staff autenticado (odonto solo propia). `ultima_actualizacion`
avanza vía trigger DB (migración 002), no en la app.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import HTTPException
from pydantic import ValidationError

from app.models.disponibilidad import Disponibilidad
from app.modules.agenda.schemas import DisponibilidadCreate
from app.modules.auth.deps import (
    CurrentStaff,
    DbSession,
    require_own_profesional,
    require_role,
)
from app.modules.disponibilidades import service

router = APIRouter(prefix="/api/disponibilidades", tags=["disponibilidades"])


def _body_or_400(raw: dict) -> DisponibilidadCreate:
    try:
        return DisponibilidadCreate(**raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=[
                {"campo": ".".join(str(p) for p in e["loc"]), "error": e["msg"]}
                for e in exc.errors()
            ],
        ) from None


@router.post(
    "", status_code=201, dependencies=[Depends(require_role("recepcion", "admin"))]
)
def crear(body: dict, db: DbSession) -> dict:
    """Crea ventana (201; 409 solape mismo profesional+día; 400 por campo)."""
    parsed = _body_or_400(body)
    ventana = service.crear_ventana(
        db,
        parsed.profesional_id,
        parsed.dia_semana,
        parsed.hora_desde,
        parsed.hora_hasta,
        parsed.vigente_desde,
        parsed.vigente_hasta,
    )
    return {
        "id": str(ventana.id),
        "profesional_id": str(ventana.profesional_id),
        "dia_semana": ventana.dia_semana,
        "hora_desde": ventana.hora_desde.isoformat(),
        "hora_hasta": ventana.hora_hasta.isoformat(),
    }


@router.get("")
def listar(
    request: Request,
    db: DbSession,
    staff: CurrentStaff,
) -> dict:
    """Lista ventanas (staff; odonto solo propias; keyset por `id`)."""
    from pydantic import ConfigDict

    from app.modules.agenda.schemas import ProfesionalesQuery

    class _Filtro(ProfesionalesQuery):
        model_config = ConfigDict(extra="forbid")
        profesional_id: UUID | None = None

    # `ProfesionalesQuery` ya es forbid; el campo extra se declara aquí.
    try:
        filtro = _Filtro(**dict(request.query_params))
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=[
                {"campo": ".".join(str(p) for p in e["loc"]), "error": e["msg"]}
                for e in exc.errors()
            ],
        ) from None
    if staff.rol == "odontologo":
        require_own_profesional(filtro.profesional_id, staff)
    elif staff.rol not in ("recepcion", "admin"):
        raise HTTPException(status_code=403, detail="Sin permiso")
    q = (
        db.query(
            Disponibilidad.id,
            Disponibilidad.profesional_id,
            Disponibilidad.dia_semana,
            Disponibilidad.hora_desde,
            Disponibilidad.hora_hasta,
        )
        .order_by(Disponibilidad.id)
    )
    if filtro.profesional_id is not None:
        q = q.filter(Disponibilidad.profesional_id == filtro.profesional_id)
    if filtro.cursor is not None:
        q = q.filter(Disponibilidad.id > filtro.cursor)
    filas = q.limit(filtro.limit + 1).all()
    items = [
        {
            "id": str(r[0]),
            "profesional_id": str(r[1]),
            "dia_semana": r[2],
            "hora_desde": r[3].isoformat(),
            "hora_hasta": r[4].isoformat(),
        }
        for r in filas[: filtro.limit]
    ]
    next_cursor = str(filas[filtro.limit - 1][0]) if len(filas) > filtro.limit else None
    return {"items": items, "next_cursor": next_cursor}


@router.delete(
    "/{ventana_id}", dependencies=[Depends(require_role("recepcion", "admin"))]
)
def eliminar(ventana_id: UUID, db: DbSession) -> dict:
    """Elimina ventana (baja física de configuración; turnos intactos)."""
    ventana = (
        db.query(Disponibilidad).filter(Disponibilidad.id == ventana_id).one_or_none()
    )
    if ventana is None:
        raise HTTPException(status_code=404, detail="No encontrado")
    db.delete(ventana)
    db.commit()
    return {"ok": True}
