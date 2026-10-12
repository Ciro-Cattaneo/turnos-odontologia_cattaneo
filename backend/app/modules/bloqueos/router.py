"""Bloqueos staff (C-04 D-6): `motivo` obligatorio, `creado_por` desde sesión.

Escritura: `recepcion`/`admin` (vía `require_role` de C-03, importado).
El bloqueo oculta slots de inmediato (el cómputo resta bloqueos siempre).
"""

from fastapi import APIRouter, Depends
from fastapi.exceptions import HTTPException
from pydantic import ValidationError

from app.models.bloqueo import Bloqueo
from app.models.profesional import Profesional
from app.modules.agenda.schemas import BloqueoCreate
from app.modules.auth.deps import CurrentStaff, DbSession, require_role

router = APIRouter(prefix="/api/bloqueos", tags=["bloqueos"])


@router.post(
    "", status_code=201, dependencies=[Depends(require_role("recepcion", "admin"))]
)
def crear(body: dict, db: DbSession, staff: CurrentStaff) -> dict:
    """Crea bloqueo (201; 400 motivo/rango/campo; toca freshness vía trigger).

    # AC agenda-disponibilidad/Bloqueos-staff.
    """
    try:
        parsed = BloqueoCreate(**body)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=[
                {"campo": ".".join(str(p) for p in e["loc"]), "error": e["msg"]}
                for e in exc.errors()
            ],
        ) from None
    prof = (
        db.query(Profesional)
        .filter(Profesional.id == parsed.profesional_id)
        .one_or_none()
    )
    if prof is None or not prof.activo:
        raise HTTPException(status_code=404, detail="No encontrado")
    bloqueo = Bloqueo(
        profesional_id=parsed.profesional_id,
        desde=parsed.desde,
        hasta=parsed.hasta,
        motivo=parsed.motivo.strip(),
        creado_por=staff.id,
    )
    db.add(bloqueo)
    db.commit()
    db.refresh(bloqueo)
    return {
        "id": str(bloqueo.id),
        "profesional_id": str(bloqueo.profesional_id),
        "desde": bloqueo.desde.isoformat(),
        "hasta": bloqueo.hasta.isoformat(),
        "motivo": bloqueo.motivo,
    }
