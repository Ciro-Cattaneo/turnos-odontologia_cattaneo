"""Servicio admin de profesionales (C-11 D-3/D-4, reglas duras 3 y 7).

Alta/edición/baja lógica y listado admin. La baja es idempotente (`activo=false`)
y NUNCA borra filas ni toca turnos/disponibilidades/bloqueos; `_lock` serializa
con la reserva online por la fila `profesional` (`SELECT ... FOR UPDATE`).
Listados con columnas explícitas y keyset por `id` (sin OFFSET).
"""

from datetime import datetime
from uuid import UUID

from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session

from app.models.profesional import Profesional
from app.modules.profesionales.schemas import (
    ProfesionalCreate,
    ProfesionalUpdate,
)

NO_ENCONTRADO = "No encontrado"

# D-3: campos editables; `ultima_actualizacion` la mantiene el trigger DB.
CAMPOS_EDITABLES = (
    "nombre",
    "matricula",
    "especialidad",
    "duracion_default_min",
    "activo",
)


def _out(prof: Profesional) -> dict:
    """Recurso admin (sin turnos ni conteos, D-3)."""
    return {
        "id": prof.id,
        "nombre": prof.nombre,
        "matricula": prof.matricula,
        "especialidad": prof.especialidad,
        "duracion_default_min": prof.duracion_default_min,
        "activo": prof.activo,
        "ultima_actualizacion": prof.ultima_actualizacion,
    }


def _lock(db: Session, profesional_id: UUID) -> Profesional:
    """Fila `profesional` bloqueada; inexistente → 404 genérico."""
    prof = (
        db.query(Profesional)
        .filter(Profesional.id == profesional_id)
        .with_for_update()
        .one_or_none()
    )
    if prof is None:
        raise HTTPException(status_code=404, detail=NO_ENCONTRADO)
    return prof


def crear(db: Session, data: ProfesionalCreate) -> dict:
    """Alta admin: `activo=true` y `duracion_default_min` por default."""
    prof = Profesional(
        nombre=data.nombre,
        matricula=data.matricula,
        especialidad=data.especialidad,
        duracion_default_min=data.duracion_default_min,
    )
    db.add(prof)
    db.flush()
    db.commit()
    return _out(prof)


def actualizar(db: Session, profesional_id: UUID, data: ProfesionalUpdate) -> dict:
    """Edición parcial: solo campos enviados; no reescribe turnos (D-3)."""
    prof = _lock(db, profesional_id)
    enviados = data.model_fields_set & set(CAMPOS_EDITABLES)
    for campo in enviados:
        setattr(prof, campo, getattr(data, campo))
    db.flush()
    db.commit()
    return _out(prof)


def dar_de_baja(db: Session, profesional_id: UUID) -> dict:
    """Baja lógica idempotente: `activo=false`, historial intacto (D-4)."""
    prof = _lock(db, profesional_id)
    prof.activo = False
    db.flush()
    db.commit()
    return _out(prof)


def listar_admin(db: Session, limit: int, cursor: UUID | None) -> dict:
    """Listado admin keyset: incluye inactivos y expone `activo` (D-5)."""
    q = db.query(
        Profesional.id,
        Profesional.nombre,
        Profesional.matricula,
        Profesional.especialidad,
        Profesional.duracion_default_min,
        Profesional.activo,
        Profesional.ultima_actualizacion,
    ).order_by(Profesional.id)
    if cursor is not None:
        q = q.filter(Profesional.id > cursor)
    filas = q.limit(limit + 1).all()
    items = [
        {
            "id": str(r[0]),
            "nombre": r[1],
            "matricula": r[2],
            "especialidad": r[3],
            "duracion_default_min": r[4],
            "activo": r[5],
            "ultima_actualizacion": _iso(r[6]),
        }
        for r in filas[:limit]
    ]
    next_cursor = str(filas[limit - 1][0]) if len(filas) > limit else None
    return {"items": items, "next_cursor": next_cursor}


def _iso(valor: datetime | None) -> str | None:
    return valor.isoformat() if valor else None
