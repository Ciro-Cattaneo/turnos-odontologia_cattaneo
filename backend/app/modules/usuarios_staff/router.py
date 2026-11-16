"""Endpoints admin de usuarios staff (C-11 D-6/D-7).

RBAC `admin` sobre todo el router (`require_role`, importado de C-03, sin
duplicar auth). Schemas `extra='forbid'` → 400 por campo; el servicio resuelve
alta/edición/baja/listado con hash argon2id y guarda de último admin.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.modules.agenda.public import parse_query_or_400
from app.modules.auth.deps import DbSession, require_role
from app.modules.turnos.schemas import parse_body_or_400
from app.modules.usuarios_staff import service
from app.modules.usuarios_staff.schemas import (
    ListadoUsuariosStaffOut,
    UsuariosStaffQuery,
    UsuarioStaffCreate,
    UsuarioStaffOut,
    UsuarioStaffUpdate,
)

ADMIN = [Depends(require_role("admin"))]

router = APIRouter(
    prefix="/api/usuarios-staff", tags=["usuarios-staff"], dependencies=ADMIN
)


@router.get("", response_model=ListadoUsuariosStaffOut)
def listar_usuarios(request: Request, db: DbSession) -> dict:
    """Listado admin keyset (incluye inactivos, sin `password_hash`)."""
    query = parse_query_or_400(UsuariosStaffQuery, dict(request.query_params))
    return service.listar(db, query.limit, query.cursor)


@router.post("", status_code=201, response_model=UsuarioStaffOut)
def crear_usuario(body: dict, db: DbSession) -> dict:
    """Alta admin: 201 sin exponer el hash; 409 si el email está tomado."""
    data = parse_body_or_400(UsuarioStaffCreate, body)
    return service.crear(db, data)


@router.put("/{usuario_id}", response_model=UsuarioStaffOut)
def actualizar_usuario(usuario_id: UUID, body: dict, db: DbSession) -> dict:
    """Edición admin de rol/vínculo/activo con guarda de último admin."""
    data = parse_body_or_400(UsuarioStaffUpdate, body)
    return service.actualizar(db, usuario_id, data)


@router.delete("/{usuario_id}", response_model=UsuarioStaffOut)
def eliminar_usuario(usuario_id: UUID, db: DbSession) -> dict:
    """Baja lógica admin: `activo=false`, fila conservada, idempotente."""
    return service.dar_de_baja(db, usuario_id)


__all__ = [
    "actualizar_usuario",
    "crear_usuario",
    "eliminar_usuario",
    "listar_usuarios",
    "router",
]
