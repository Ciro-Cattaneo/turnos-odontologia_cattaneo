"""Punto unico de registro de modelos para `Base.metadata` y Alembic (D-1)."""

from app.models.auditoria import AuditoriaTurno
from app.models.bloqueo import Bloqueo
from app.models.disponibilidad import Disponibilidad
from app.models.notificacion import NotifEstado, Notificacion, NotifTipo
from app.models.paciente import Paciente
from app.models.profesional import Profesional
from app.models.turno import CanalRecordatorio, Turno, TurnoEstado, TurnoOrigen
from app.models.usuario_staff import StaffRol, UsuarioStaff

__all__ = [
    "AuditoriaTurno",
    "Bloqueo",
    "CanalRecordatorio",
    "Disponibilidad",
    "NotifEstado",
    "NotifTipo",
    "Notificacion",
    "Paciente",
    "Profesional",
    "StaffRol",
    "Turno",
    "TurnoEstado",
    "TurnoOrigen",
    "UsuarioStaff",
]
