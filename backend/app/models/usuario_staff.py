"""UsuarioStaff con login (KB-04; auth/RBAC en C-03)."""

import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Text, Uuid
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StaffRol(enum.StrEnum):
    """Roles fijos como enum, sin tabla extra (KB-04)."""

    recepcion = "recepcion"
    odontologo = "odontologo"
    admin = "admin"


class UsuarioStaff(Base):
    """Staff con sesion; `profesional_id` nullable (solo si loguea profesional)."""

    __tablename__ = "usuario_staff"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    rol: Mapped[StaffRol] = mapped_column(
        Enum(StaffRol, native_enum=True, name="staff_rol"), nullable=False
    )
    profesional_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profesional.id"), index=True
    )
    activo: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
