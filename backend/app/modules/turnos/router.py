"""Reserva pública sin login (C-05 D-1/D-9/D-11).

Router delgado: parsea el body estricto (`extra='forbid'` → 400 por campo),
inyecta el reloj y delega la transacción a `reserva_service.reservar()`.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import HTTPException

from app.core import ratelimit
from app.modules.auth.deps import DbSession
from app.modules.turnos import service
from app.modules.turnos.schemas import TurnoCreate, TurnoOut, parse_body_or_400

router = APIRouter(prefix="/api/turnos", tags=["turnos"])

RATE_LIMIT = 10
RATE_WINDOW_S = 60


def get_now_provider() -> Callable[[], datetime]:
    """Reloj inyectable de la reserva (D-10)."""
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
