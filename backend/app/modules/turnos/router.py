"""Turnos: reserva pública (C-05), cancelación por token (C-06) y staff (C-07).

Router delgado: resuelve la sesión antes de parsear el body (D-1), aplica
RBAC de C-03, parsea body/query estricto (`extra='forbid'` → 400 por campo)
y delega la transacción a los servicios. La ruta `DELETE` conserva la
precedencia del token público sobre la sesión staff (D-6).
"""

import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request
from fastapi.exceptions import HTTPException

from app.core import ratelimit
from app.models.turno import Turno, TurnoEstado
from app.models.usuario_staff import StaffRol, UsuarioStaff
from app.modules.agenda.public import parse_query_or_400, staff_opcional
from app.modules.auth.deps import (
    CurrentStaff,
    DbSession,
    require_own_profesional,
    require_role,
)
from app.modules.turnos import cancellation_service, service
from app.modules.turnos.schemas import (
    CancelacionOut,
    CorreccionPacienteIn,
    CorreccionPacienteOut,
    EstadoOut,
    EstadoUpdate,
    FichaQuery,
    MotivoCancelacionIn,
    ReprogramacionOut,
    TurnoCreate,
    TurnoCreateStaff,
    TurnoFichaOut,
    TurnoOut,
    TurnoReprogramar,
    TurnoStaffOut,
    parse_body_or_400,
)

router = APIRouter(prefix="/api/turnos", tags=["turnos"])

RATE_LIMIT = 10
RATE_WINDOW_S = 60

CANCEL_RATE_LIMIT = 10
CANCEL_RATE_WINDOW_S = 60

NO_AUTORIZADO = "No autorizado"
NO_AUTENTICADO = "No autenticado"
SIN_PERMISO = "Sin permiso"

CAMPOS_STAFF_OUT = (
    "id",
    "estado",
    "inicio",
    "fin",
    "duracion_min",
    "notificaciones_encoladas",
)

StaffRecepcion = Annotated[
    UsuarioStaff, Depends(require_role("recepcion", "admin"))
]

BODY_OPCIONAL = Body(default=None)


def get_now_provider() -> Callable[[], datetime]:
    """Reloj inyectable de reserva, cancelación y operación staff (D-14)."""
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


def reserva_throttle(request: Request, ip: ClientIP) -> None:
    """Cupo público solo para anónimos; una cookie inválida la resuelve auth."""
    if request.cookies.get("session"):
        return
    public_reserva_throttle(ip)


def cancelacion_throttle(request: Request, ip: ClientIP) -> None:
    """Cupo público solo para anónimos; el staff no consume la ventana."""
    if request.cookies.get("session"):
        return
    public_cancelacion_throttle(ip)


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


def _es_odontologo(staff: UsuarioStaff) -> bool:
    return getattr(staff.rol, "value", staff.rol) == StaffRol.odontologo.value


def _turno_basico(db, turno_id: uuid.UUID):
    """Lectura mínima para RBAC antes de la operación (sin ORM completo)."""
    return (
        db.query(Turno.id, Turno.profesional_id)
        .filter(Turno.id == turno_id)
        .one_or_none()
    )


@router.post(
    "",
    status_code=201,
    response_model=TurnoOut | TurnoStaffOut,
    dependencies=[Depends(reserva_throttle)],
)
def crear(
    body: dict,
    request: Request,
    db: DbSession,
    now_provider: NowProvider,
) -> dict:
    """Crea reserva online (201) o alta staff con `origen=recepcion` (D-1)."""
    staff = staff_opcional(request, db)
    if staff is None:
        data = parse_body_or_400(TurnoCreate, body)
        return service.reservar(db, data, now_provider=now_provider)

    if _es_odontologo(staff):
        raise HTTPException(status_code=403, detail=SIN_PERMISO)

    data_staff = parse_body_or_400(TurnoCreateStaff, body)
    resultado = service.reservar(
        db,
        data_staff,
        now_provider=now_provider,
        origen=service.TurnoOrigen.recepcion,
        actor_id=staff.id,
        origen_auditoria="recepcion",
        actor=service.actor_detalle(staff),
    )
    return {clave: resultado[clave] for clave in CAMPOS_STAFF_OUT}


def _cancelar_publico(
    token_raw: str, turno_id_raw: str, db, now_provider
) -> dict:
    """Flujo exacto de C-06 (token como única credencial)."""
    turno_id = _parse_uuid(turno_id_raw)
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


@router.delete(
    "/{id}",
    status_code=200,
    response_model=CancelacionOut,
    dependencies=[Depends(cancelacion_throttle)],
)
def cancelar(
    id: str,
    request: Request,
    db: DbSession,
    now_provider: NowProvider,
    body: dict | None = BODY_OPCIONAL,
) -> dict:
    """Cancela por `?token=` (C-06) o como staff sin query (C-07 D-6)."""
    if request.query_params:
        return _cancelar_publico(
            _parse_query_token(request), id, db, now_provider
        )

    staff = staff_opcional(request, db)
    if staff is None:
        # C-06 no regresión: sin query ni body (o con token en el body) la
        # credencial pública ausente sigue respondiendo 403 genérico.
        if body is None or "token" in body:
            return _cancelar_publico("", id, db, now_provider)
        raise HTTPException(status_code=401, detail=NO_AUTENTICADO)
    if _es_odontologo(staff):
        raise HTTPException(status_code=403, detail=SIN_PERMISO)

    data = parse_body_or_400(MotivoCancelacionIn, body or {})
    turno_id = _parse_uuid(id)
    if turno_id is None:
        raise HTTPException(status_code=404, detail="No encontrado")
    return service.cancelar_staff(
        db,
        turno_id,
        motivo=data.motivo,
        actor=service.actor_detalle(staff),
        now_provider=now_provider,
    )


@router.put(
    "/{id}",
    response_model=ReprogramacionOut,
    dependencies=[Depends(require_role("recepcion", "admin"))],
)
def reprogramar(
    id: str,
    body: dict,
    db: DbSession,
    now_provider: NowProvider,
    staff: StaffRecepcion,
) -> dict:
    """Reprograma y/o cambia la duración con anti-solape (D-4)."""
    data = parse_body_or_400(TurnoReprogramar, body)
    turno_id = _parse_uuid(id)
    if turno_id is None:
        raise HTTPException(status_code=404, detail="No encontrado")
    return service.reprogramar(
        db,
        turno_id,
        data,
        actor=service.actor_detalle(staff),
        now_provider=now_provider,
    )


@router.put(
    "/{id}/paciente",
    response_model=CorreccionPacienteOut,
    dependencies=[Depends(require_role("recepcion", "admin"))],
)
def corregir_paciente(
    id: str,
    body: dict,
    db: DbSession,
    now_provider: NowProvider,
    staff: StaffRecepcion,
) -> dict:
    """Corrige DNI/teléfono/obra social del paciente con auditoría (D-7)."""
    data = parse_body_or_400(CorreccionPacienteIn, body)
    turno_id = _parse_uuid(id)
    if turno_id is None:
        raise HTTPException(status_code=404, detail="No encontrado")
    return service.actualizar_paciente(
        db,
        turno_id,
        data,
        actor=service.actor_detalle(staff),
        now_provider=now_provider,
    )


@router.patch("/{id}/estado", response_model=EstadoOut)
def cambiar_estado(
    id: str,
    body: dict,
    db: DbSession,
    now_provider: NowProvider,
    staff: CurrentStaff,
) -> dict:
    """Aplica RN-TU-07 con scoping del odontólogo y auditoría (D-5)."""
    turno_id = _parse_uuid(id)
    if turno_id is None:
        raise HTTPException(status_code=404, detail="No encontrado")
    fila = _turno_basico(db, turno_id)
    if fila is None:
        raise HTTPException(status_code=404, detail="No encontrado")
    if _es_odontologo(staff):
        require_own_profesional(fila.profesional_id, staff)

    data = parse_body_or_400(EstadoUpdate, body)
    if _es_odontologo(staff) and data.estado == TurnoEstado.ausente:
        raise HTTPException(status_code=403, detail=SIN_PERMISO)
    return service.cambiar_estado(
        db,
        turno_id,
        data.estado,
        actor=service.actor_detalle(staff),
        now_provider=now_provider,
    )


@router.get("/{id}", response_model=TurnoFichaOut)
def ficha(
    id: str,
    request: Request,
    db: DbSession,
    staff: CurrentStaff,
) -> dict:
    """Ficha del turno con historial keyset y sin token (D-9)."""
    turno_id = _parse_uuid(id)
    if turno_id is None:
        raise HTTPException(status_code=404, detail="No encontrado")
    fila = _turno_basico(db, turno_id)
    if fila is None:
        raise HTTPException(status_code=404, detail="No encontrado")
    if _es_odontologo(staff):
        require_own_profesional(fila.profesional_id, staff)

    query = parse_query_or_400(FichaQuery, dict(request.query_params))
    try:
        return service.obtener_ficha(
            db,
            turno_id,
            historial_limit=query.historial_limit,
            historial_cursor=query.historial_cursor,
        )
    except service.HistorialCursorInvalido as exc:
        raise HTTPException(
            status_code=400,
            detail=[
                {
                    "campo": "historial_cursor",
                    "error": str(exc),
                    "tipo": "cursor_invalido",
                }
            ],
        ) from None
