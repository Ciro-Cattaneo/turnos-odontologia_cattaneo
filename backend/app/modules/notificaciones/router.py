"""Panel staff de notificaciones fallidas (C-08 D-9).

Router delgado: valida query (`extra='forbid'` → 400), aplica RBAC de C-03
(`require_role`) y delega la consulta keyset/opaca a `service`.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import HTTPException

from app.modules.agenda.public import parse_query_or_400
from app.modules.auth.deps import DbSession, require_role
from app.modules.notificaciones import service
from app.modules.notificaciones.schemas import FallidasPage, FallidasQuery

router = APIRouter(prefix="/api/notificaciones", tags=["notificaciones"])


@router.get(
    "/fallidas",
    response_model=FallidasPage,
    dependencies=[Depends(require_role("recepcion", "admin"))],
)
def listar_fallidas(request: Request, db: DbSession) -> dict:
    """Lista fallos SMTP/payload ordenados por inicio de turno descendente."""
    query = parse_query_or_400(FallidasQuery, dict(request.query_params))
    try:
        return service.listar_fallidas(
            db, limit=query.limit, cursor=query.cursor
        )
    except service.CursorInvalido as exc:
        raise HTTPException(
            status_code=400,
            detail=[
                {
                    "campo": "cursor",
                    "error": str(exc),
                    "tipo": "cursor_invalido",
                }
            ],
        ) from None
