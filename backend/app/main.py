"""Punto de entrada FastAPI (monolito modular, KB-08)."""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.modules.agenda.router import disponibilidad_router
from app.modules.agenda.router import router as agenda_router
from app.modules.auth.router import router as auth_router
from app.modules.bloqueos.router import router as bloqueos_router
from app.modules.disponibilidades.router import router as disponibilidades_router
from app.modules.notificaciones.router import router as notificaciones_router
from app.modules.notificaciones.scheduler import crear_scheduler
from app.modules.pacientes.router import router as pacientes_router
from app.modules.profesionales.router import router as profesionales_router
from app.modules.reportes.router import router as reportes_router
from app.modules.turnos.router import router as turnos_router
from app.modules.usuarios_staff.router import router as usuarios_staff_router

try:
    settings = get_settings()
except RuntimeError as exc:
    print(f"error: {exc}", file=sys.stderr)
    raise SystemExit(1) from exc


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Arranca/para el worker en-proceso según `NOTIF_WORKER_ENABLED` (D-7)."""
    actuales = get_settings()
    scheduler = None
    if actuales.NOTIF_WORKER_ENABLED:
        scheduler = crear_scheduler(
            intervalo_min=actuales.NOTIF_WORKER_INTERVAL_MIN
        )
        scheduler.start()
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)


app = FastAPI(title="Turnos Odontología Cattaneo", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

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
    usuarios_staff_router,
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


STATIC_DIR = Path(settings.STATIC_DIR)


def _montar_spa(aplicacion: FastAPI) -> None:
    """D-2: un solo contenedor sirve la SPA y la API en el mismo origen.

    Registrado DESPUÉS de routers y de `/api/health`: el catch-all solo
    aplica a rutas fuera de `/api`, que conservan el 404 JSON de la API.
    """
    assets = STATIC_DIR / "assets"
    if assets.is_dir():
        aplicacion.mount("/assets", StaticFiles(directory=assets), name="assets")

    @aplicacion.get("/", include_in_schema=False)
    def spa_index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @aplicacion.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(STATIC_DIR / "index.html")


if STATIC_DIR.is_dir():
    _montar_spa(app)
else:

    @app.get("/")
    def root() -> dict[str, str]:
        return {"service": "turnos-odontologia", "tz": settings.TZ}
