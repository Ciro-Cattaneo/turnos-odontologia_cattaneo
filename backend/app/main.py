"""Punto de entrada FastAPI (monolito modular, KB-08)."""

import sys

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.modules.agenda.router import disponibilidad_router
from app.modules.agenda.router import router as agenda_router
from app.modules.auth.router import router as auth_router
from app.modules.bloqueos.router import router as bloqueos_router
from app.modules.disponibilidades.router import router as disponibilidades_router
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
    disponibilidad_router,
    disponibilidades_router,
    bloqueos_router,
    pacientes_router,
    profesionales_router,
    notificaciones_router,
    auth_router,
    reportes_router,
):
    app.include_router(router)


@app.exception_handler(RequestValidationError)
async def validation_400(request: Request, exc: RequestValidationError) -> JSONResponse:
    """D-6: validación Pydantic (`extra='forbid'`, rangos, enums) → 400 por campo.

    FastAPI responde 422 por defecto; el contrato del proyecto (regla dura 1,
    D-6) exige 400 con detalle por campo en TODOS los schemas de API.
    """
    return JSONResponse(
        status_code=400,
        content={
            "detail": [
                {
                    "campo": ".".join(str(p) for p in e["loc"]),
                    "error": e["msg"],
                    "tipo": e.get("type", "value_error"),
                }
                for e in exc.errors()
            ]
        },
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness puro: sin auth y sin DB (spec service-health)."""
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "turnos-odontologia", "tz": settings.TZ}
