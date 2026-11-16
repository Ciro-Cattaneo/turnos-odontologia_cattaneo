"""Servicio admin de usuarios staff (C-11 D-6/D-7, reglas duras 3 y 7).

Alta con hash argon2id, edición del estado resultante, baja lógica
(`activo=false`, nunca borrado físico) y listado keyset por `id` sin OFFSET.
La guarda "nunca cero admins activos" bloquea el conjunto de admins activos
con un lock ordenado (`ORDER BY id FOR UPDATE`) antes de aplicar el cambio,
de modo que `PUT activo=false` y `DELETE` serializan igual bajo carrera.
"""

from uuid import UUID

from fastapi.exceptions import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.profesional import Profesional
from app.models.usuario_staff import StaffRol, UsuarioStaff
from app.modules.usuarios_staff.schemas import (
    UsuarioStaffCreate,
    UsuarioStaffUpdate,
    validar_vinculo_rol,
)

NO_ENCONTRADO = "No encontrado"
_ULTIMO_ADMIN = {
    "codigo": "ultimo_admin",
    "mensaje": "No se puede dejar el sistema sin admin activo",
}
_EMAIL_DUPLICADO = {
    "codigo": "email_duplicado",
    "mensaje": "El email ya está en uso; reactivá la fila existente",
}


def _out(usuario: UsuarioStaff) -> dict:
    """Recurso de usuario staff (sin `password_hash`, D-6)."""
    return {
        "id": usuario.id,
        "email": usuario.email,
        "rol": usuario.rol,
        "profesional_id": usuario.profesional_id,
        "activo": usuario.activo,
    }


def _campo_400(campo: str, mensaje: str) -> HTTPException:
    """400 por campo con el formato de contrato (regla dura 1)."""
    return HTTPException(
        status_code=400,
        detail=[{"campo": campo, "error": mensaje, "tipo": "value_error"}],
    )


def _campo_422(campo: str, mensaje: str) -> HTTPException:
    """422 por campo cuando la referencia se resuelve en la transición (D-6)."""
    return HTTPException(
        status_code=422,
        detail=[{"campo": campo, "error": mensaje, "tipo": "value_error"}],
    )


def _ultimo_admin() -> HTTPException:
    return HTTPException(status_code=422, detail=dict(_ULTIMO_ADMIN))


def _email_duplicado() -> HTTPException:
    return HTTPException(status_code=409, detail=dict(_EMAIL_DUPLICADO))


def _existe_email(db: Session, email: str) -> bool:
    """Pre-check amable; `CITEXT` compara sin distinguir mayúsculas."""
    return (
        db.query(UsuarioStaff.id)
        .filter(UsuarioStaff.email == email)
        .first()
        is not None
    )


def _cargar(db: Session, usuario_id: UUID) -> UsuarioStaff:
    """Lectura sin lock (solo para 404 y rol actual, D-7)."""
    usuario = (
        db.query(UsuarioStaff)
        .filter(UsuarioStaff.id == usuario_id)
        .one_or_none()
    )
    if usuario is None:
        raise HTTPException(status_code=404, detail=NO_ENCONTRADO)
    return usuario


def _bloquear(db: Session, usuario_id: UUID) -> UsuarioStaff:
    """Bloquea y refresca la fila destino (después del lock de admins)."""
    return (
        db.query(UsuarioStaff)
        .filter(UsuarioStaff.id == usuario_id)
        .populate_existing()
        .with_for_update()
        .one()
    )


def _bloquear_admins_activos(db: Session) -> list:
    """Lock ordenado y único punto de serialización sobre filas admin (D-7)."""
    return (
        db.query(
            UsuarioStaff.id,
            UsuarioStaff.rol,
            UsuarioStaff.activo,
        )
        .filter(
            UsuarioStaff.rol == StaffRol.admin,
            UsuarioStaff.activo.is_(True),
        )
        .order_by(UsuarioStaff.id)
        .with_for_update()
        .all()
    )


def _asegurar_admin_restante(
    db: Session,
    usuario_id: UUID,
    *,
    nuevo_rol: StaffRol | None,
    nuevo_activo: bool | None,
) -> None:
    """422 `ultimo_admin` si el cambio dejaría cero admins activos (D-7).

    Evalúa el estado **resultante** sobre el conjunto de admins bloqueado:
    cubre auto-baja, auto-degradación, `PUT activo=false` y carreras.
    """
    admins = _bloquear_admins_activos(db)
    restantes = 0
    en_conjunto = False
    for fila in admins:
        if fila.id == usuario_id:
            en_conjunto = True
            rol = fila.rol if nuevo_rol is None else nuevo_rol
            activo = fila.activo if nuevo_activo is None else nuevo_activo
            if rol == StaffRol.admin and activo:
                restantes += 1
        else:
            restantes += 1
    if en_conjunto and restantes == 0:
        raise _ultimo_admin()


def _validar_profesional_activo(db: Session, profesional_id: UUID) -> None:
    """400 al alta, si el vínculo del body no existe o está inactivo (D-6)."""
    profesional = (
        db.query(Profesional.activo)
        .filter(Profesional.id == profesional_id)
        .one_or_none()
    )
    if profesional is None or not profesional[0]:
        raise _campo_400(
            "profesional_id", "el profesional no existe o está inactivo"
        )


def crear(db: Session, data: UsuarioStaffCreate) -> dict:
    """Alta admin: hash argon2id y 409 si el email ya está tomado (D-6)."""
    if data.profesional_id is not None:
        _validar_profesional_activo(db, data.profesional_id)
    if _existe_email(db, data.email):
        raise _email_duplicado()
    usuario = UsuarioStaff(
        email=data.email,
        password_hash=hash_password(data.password),
        rol=data.rol,
        profesional_id=data.profesional_id,
    )
    db.add(usuario)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise _email_duplicado() from None
    db.commit()
    return _out(usuario)


def actualizar(
    db: Session, usuario_id: UUID, data: UsuarioStaffUpdate
) -> dict:
    """Edición admin sobre el estado resultante (D-6/D-7)."""
    _cargar(db, usuario_id)
    enviados = data.model_fields_set
    if "rol" in enviados and data.rol is None:
        raise _campo_400("rol", "el rol no puede ser nulo")
    if "activo" in enviados and data.activo is None:
        raise _campo_400("activo", "`activo` no puede ser nulo")
    nuevo_rol = data.rol if "rol" in enviados else None
    nuevo_activo = data.activo if "activo" in enviados else None
    if "rol" in enviados or "activo" in enviados:
        _asegurar_admin_restante(
            db,
            usuario_id,
            nuevo_rol=nuevo_rol,
            nuevo_activo=nuevo_activo,
        )
    usuario = _bloquear(db, usuario_id)

    if "profesional_id" in enviados and data.profesional_id is not None:
        profesional = (
            db.query(Profesional.activo)
            .filter(Profesional.id == data.profesional_id)
            .one_or_none()
        )
        if profesional is None or not profesional[0]:
            raise _campo_422(
                "profesional_id",
                "el profesional no existe o está inactivo",
            )

    rol_resultante = nuevo_rol if nuevo_rol is not None else usuario.rol
    prof_resultante = (
        data.profesional_id
        if "profesional_id" in enviados
        else usuario.profesional_id
    )
    try:
        validar_vinculo_rol(rol_resultante, prof_resultante)
    except ValueError as exc:
        raise _campo_400("profesional_id", str(exc)) from None

    for campo in ("rol", "profesional_id", "activo"):
        if campo in enviados:
            setattr(usuario, campo, getattr(data, campo))
    db.flush()
    db.commit()
    return _out(usuario)


def dar_de_baja(db: Session, usuario_id: UUID) -> dict:
    """Baja lógica idempotente (`activo=false`) con guarda de último admin."""
    _cargar(db, usuario_id)
    _asegurar_admin_restante(
        db, usuario_id, nuevo_rol=None, nuevo_activo=False
    )
    usuario = _bloquear(db, usuario_id)
    usuario.activo = False
    db.flush()
    db.commit()
    return _out(usuario)


def listar(db: Session, limit: int, cursor: UUID | None) -> dict:
    """Listado admin keyset: activos e inactivos, columnas explícitas (D-6)."""
    q = db.query(
        UsuarioStaff.id,
        UsuarioStaff.email,
        UsuarioStaff.rol,
        UsuarioStaff.profesional_id,
        UsuarioStaff.activo,
    ).order_by(UsuarioStaff.id)
    if cursor is not None:
        q = q.filter(UsuarioStaff.id > cursor)
    filas = q.limit(limit + 1).all()
    items = [
        {
            "id": str(r[0]),
            "email": r[1],
            "rol": r[2],
            "profesional_id": r[3],
            "activo": r[4],
        }
        for r in filas[:limit]
    ]
    next_cursor = str(filas[limit - 1][0]) if len(filas) > limit else None
    return {"items": items, "next_cursor": next_cursor}
