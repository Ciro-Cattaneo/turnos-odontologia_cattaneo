"""Punto de entrada FastAPI (monolito modular, KB-08)."""

import sys

from fastapi import FastAPI

from app.core.config import get_settings
from app.modules.agenda.router import router as agenda_router
from app.modules.auth.router import router as auth_router
from app.modules.notificaciones.router import router as notificaciones_router
from app.modules.pacientes.router import router as pacientes_router
from app.modules.profesionales.router import router as profesionales_router
from app.modules.reportes.router import router as reportes_router
from app.modules.turnos.router import router as turnos_router

try:
    settings = get_settings()
except RuntimeError as exc:
    print(f"error: {exc}", file=sys.stderr)
    raise SystemExit(1) from exc

app = FastAPI(title="Turnos Odontología Cattaneo")

for router in (
    turnos_router,
    agenda_router,
    pacientes_router,
    profesionales_router,
    notificaciones_router,
    auth_router,
    reportes_router,
):
    app.include_router(router)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness puro: sin auth y sin DB (spec service-health)."""
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "turnos-odontologia", "tz": settings.TZ}
