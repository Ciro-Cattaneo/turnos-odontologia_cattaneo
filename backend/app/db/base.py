"""Base declarativa SQLAlchemy 2.x (sin modelos de dominio en C-01)."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Superclase de todos los modelos (C-02 añade tablas aquí)."""

    pass
