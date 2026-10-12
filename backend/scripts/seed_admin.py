#!/usr/bin/env python3
"""Seed del admin inicial desde env (D-7, idempotente).

Uso:  ADMIN_EMAIL=... ADMIN_PASSWORD=... python backend/scripts/seed_admin.py
La rotación al primer login es scope C-03; aquí solo creación.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.seed import seed_admin_from_env


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("error: falta DATABASE_URL en el entorno", file=sys.stderr)
        return 2
    engine = create_engine(database_url)
    try:
        with Session(bind=engine) as session:
            admin = seed_admin_from_env(session)
            session.commit()
            print(f"admin ok: {admin.email} (id={admin.id})")
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
