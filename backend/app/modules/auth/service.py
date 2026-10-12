"""Autenticación staff: lookup + verify + rotación transparente (C-03 D-1).

`authenticate` nunca distingue el motivo del fallo (D-6): desconocido,
password incorrecta e inactivo devuelven `None` idéntico; el camino
desconocido corre `dummy_verify` para no enumerar por tiempos.
Rotación: un verify exitoso sobre hash legacy re-hashea a argon2id y lo
persiste (D-5: sin migración, el prefijo es el marcador).
"""

from sqlalchemy.orm import Session

from app.core.security import dummy_verify, hash_password, needs_rehash, verify_password
from app.models.usuario_staff import UsuarioStaff


def authenticate(db: Session, email: str, password: str) -> UsuarioStaff | None:
    """Verifica credenciales; `None` genérico ante cualquier fallo."""
    usuario = db.query(UsuarioStaff).filter(UsuarioStaff.email == email).one_or_none()
    if usuario is None or not usuario.activo:
        dummy_verify()
        return None
    if not verify_password(password, usuario.password_hash):
        return None
    if needs_rehash(usuario.password_hash):
        usuario.password_hash = hash_password(password)
        db.commit()
        db.refresh(usuario)
    return usuario
