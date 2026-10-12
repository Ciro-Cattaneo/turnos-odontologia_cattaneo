#!/usr/bin/env python3
"""Seed demo staging-only: 2 profesionales + 20 turnos ficticios (D-7).

Rehúsa en producción (`ENV=prod` → exit 2 sin tocar la DB). NUNCA datos
reales: todo contacto vive en `@ficticio.test` (regla dura 12).
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.seed import seed_demo


def main() -> int:
    if os.getenv("ENV") == "prod":
        print("refuse: seed_demo NUNCA se ejecuta en producción", file=sys.stderr)
        return 2
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("error: falta DATABASE_URL en el entorno", file=sys.stderr)
        return 2
    engine = create_engine(database_url)
    try:
        with Session(bind=engine) as session:
            resumen = seed_demo(session)
            session.commit()
            print(f"demo ok: {resumen}")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
