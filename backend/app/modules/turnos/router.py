"""Reserva pública sin login (C-05 D-1/D-9/D-11) y cancelación por token.

Router delgado: parsea el body/query estricto (`extra='forbid'` → 400 por
campo), inyecta el reloj y delega la transacción a los servicios. La
cancelación traduce los errores de dominio de `cancellation_service` a HTTP.
"""

import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import HTTPException

from app.core import ratelimit
from app.modules.auth.deps import DbSession
from app.modules.turnos import cancellation_service, service
from app.modules.turnos.schemas import (
    CancelacionOut,
    TurnoCreate,
    TurnoOut,
    parse_body_or_400,
)

router = APIRouter(prefix="/api/turnos", tags=["turnos"])

RATE_LIMIT = 10
RATE_WINDOW_S = 60

CANCEL_RATE_LIMIT = 10
CANCEL_RATE_WINDOW_S = 60

NO_AUTORIZADO = "No autorizado"


def get_now_provider() -> Callable[[], datetime]:
    """Reloj inyectable de reserva y cancelación (D-10)."""
    return service.now_utc


NowProvider = Annotated[Callable[[], datetime], Depends(get_now_provider)]


def get_client_ip(request: Request) -> str:
    """IP del cliente para particionar el cupo (D-9)."""
    return request.client.host if request.client else "desconocida"


ClientIP = Annotated[str, Depends(get_client_ip)]


def public_reserva_throttle(ip: ClientIP) -> None:
    """D-9: 10 reservas/min/IP, ventana fija; excedido → 429 + `Retry-After`."""
    pasa, retry = ratelimit.check_public_rate_limit(
        f"turnos-publico:{ip}", limit=RATE_LIMIT, window_s=RATE_WINDOW_S
    )
    if not pasa:
        raise HTTPException(
            status_code=429,
            detail="Demasiadas reservas",
            headers={"Retry-After": str(max(1, int(retry) + 1))},
        )


def public_cancelacion_throttle(ip: ClientIP) -> None:
    """C-06 D-8: 10 cancelaciones/min/IP antes de evaluar la credencial."""
    pasa, retry = ratelimit.check_public_rate_limit(
        f"turnos-cancelacion:{ip}",
        limit=CANCEL_RATE_LIMIT,
        window_s=CANCEL_RATE_WINDOW_S,
    )
    if not pasa:
        raise HTTPException(
            status_code=429,
            detail="Demasiadas solicitudes",
            headers={"Retry-After": str(max(1, int(retry) + 1))},
        )


def _parse_uuid(valor: str) -> uuid.UUID | None:
    """UUID o `None` (id/token mal formado → 403 genérico, D-2)."""
    try:
        return uuid.UUID(valor)
    except (AttributeError, TypeError, ValueError):
        return None


def _campo_error(campo: str, error: str, tipo: str) -> HTTPException:
    """400 con detalle por campo (regla dura 1)."""
    return HTTPException(
        status_code=400,
        detail=[{"campo": campo, "error": error, "tipo": tipo}],
    )


def _parse_query_token(request: Request) -> str:
    """Query estricta de D-2: solo `token`, extras/repetido → 400 por campo."""
    extras: list[str] = []
    tokens: list[str] = []
    for clave, valor in request.query_params.multi_items():
        if clave == "token":
            tokens.append(valor)
        else:
            extras.append(clave)
    if extras:
        raise HTTPException(
            status_code=400,
            detail=[
                {
                    "campo": clave,
                    "error": "parámetro no permitido",
                    "tipo": "extra_forbidden",
                }
                for clave in sorted(set(extras))
            ],
        )
    if len(tokens) > 1:
        raise _campo_error("token", "parámetro repetido", "value_error")
    return tokens[0] if tokens else ""


def _no_autorizado() -> HTTPException:
    """403 genérico uniforme: no revela existencia ni formato (D-2)."""
    return HTTPException(status_code=403, detail=NO_AUTORIZADO)


@router.post(
    "",
    status_code=201,
    response_model=TurnoOut,
    dependencies=[Depends(public_reserva_throttle)],
)
def crear(body: dict, db: DbSession, now_provider: NowProvider) -> dict:
    """Crea una reserva online (201; 400 por campo; 404/409 según D-11)."""
    data = parse_body_or_400(TurnoCreate, body)
    return service.reservar(db, data, now_provider=now_provider)


@router.delete(
    "/{id}",
    status_code=200,
    response_model=CancelacionOut,
    dependencies=[Depends(public_cancelacion_throttle)],
)
def cancelar(
    id: str,
    request: Request,
    db: DbSession,
    now_provider: NowProvider,
) -> dict:
    """Cancela el turno por `?token=` (403 genérico; 422; 400; 429)."""
    token_raw = _parse_query_token(request)
    turno_id = _parse_uuid(id)
    token = _parse_uuid(token_raw)
    if turno_id is None or token is None:
        raise _no_autorizado()

    try:
        return cancellation_service.cancelar(
            db, turno_id=turno_id, token=token, now_provider=now_provider
        )
    except cancellation_service.NoAutorizado:
        raise _no_autorizado() from None
    except cancellation_service.TurnoYaCancelado:
        raise HTTPException(
            status_code=422,
            detail={
                "codigo": "turno_ya_cancelado",
                "mensaje": "El turno ya está cancelado",
            },
        ) from None
    except cancellation_service.TurnoNoCancelable:
        raise HTTPException(
            status_code=422,
            detail={
                "codigo": "turno_no_cancelable",
                "mensaje": "El turno no se puede cancelar en su estado actual",
            },
        ) from None
    except cancellation_service.FueraDePlazo as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "codigo": "cancelacion_fuera_de_plazo",
                "mensaje": exc.mensaje,
                "contacto": exc.contacto,
            },
        ) from None
    except cancellation_service.DatoInvalido:
        raise HTTPException(status_code=500, detail="Error interno") from None

