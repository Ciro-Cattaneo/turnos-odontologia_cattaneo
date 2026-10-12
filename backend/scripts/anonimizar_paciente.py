#!/usr/bin/env python3
"""CLI admin para anonimización Ley 25.326 (ver docs/anonimizacion-ley-25326.md).

Uso (solo admin, NUNCA en UI):
    python backend/scripts/anonimizar_paciente.py --paciente-id <uuid>

Lee `DATABASE_URL` del entorno, anonimiza, commitea e imprime el resultado.
Datos ficticios en tests; NUNCA datos reales en repo/ejemplos (regla dura 12).
"""

import argparse
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.anonimizacion import anonimizar_paciente


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Anonimiza un paciente (Ley 25.326, admin-only)."
    )
    parser.add_argument("--paciente-id", required=True, help="UUID del paciente")
    args = parser.parse_args()
    paciente_id = uuid.UUID(args.paciente_id)
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("error: falta DATABASE_URL en el entorno", file=sys.stderr)
        return 2
    engine = create_engine(database_url)
    try:
        with Session(bind=engine) as session:
            paciente = anonimizar_paciente(session, paciente_id)
            session.commit()
            print(f"paciente {paciente.id} anonimizado: {paciente.nombre}")
            print("turnos conservados como estadística; auditoría 'anonimizar' escrita")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
