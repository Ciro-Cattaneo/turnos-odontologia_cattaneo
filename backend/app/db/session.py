"""Engine + sesión por request (D-3: pool chico, single-instance PG16)."""

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def build_engine(database_url: str | None = None) -> Engine:
    """Crea el engine sin abrir conexiones (pool_size=5, max_overflow=5)."""
    url = database_url or get_settings().DATABASE_URL
    return create_engine(url, pool_size=5, max_overflow=5)


def build_factory(engine: Engine) -> sessionmaker[Session]:
    """Fábrica de sesiones ligada al engine dado (seam testeable)."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


engine = build_engine()
SessionLocal = build_factory(engine)


def get_db() -> Iterator[Session]:
    """Dependencia FastAPI: sesión por request con cierre garantizado."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
