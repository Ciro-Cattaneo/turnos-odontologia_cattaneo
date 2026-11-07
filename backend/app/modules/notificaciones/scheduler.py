"""Scheduler en-proceso del worker de mail (C-08 D-3/D-7).

`BackgroundScheduler` con jobstore en memoria y un único job `notificaciones-mail`.
Sin Redis ni proceso externo (PB-03): el estado de la cola vive en Postgres.
"""

import logging
from datetime import UTC

from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from app.db.session import SessionLocal
from app.modules.notificaciones.sender import default_sender
from app.modules.notificaciones.worker import Resumen, run_once

logger = logging.getLogger(__name__)

JOB_ID = "notificaciones-mail"


def ejecutar_ciclo() -> Resumen | None:
    """Job del scheduler: un ciclo del worker con el sender real del entorno."""
    try:
        return run_once(SessionLocal, default_sender())
    except Exception as exc:  # el hilo del scheduler no debe morir
        logger.error(
            "notificacion_ciclo_error resultado=error tipo=%s",
            type(exc).__name__,
        )
        return None


def crear_scheduler(
    *,
    intervalo_min: int,
    job=None,
) -> BackgroundScheduler:
    """Registra el job periódico del worker con jobstore en memoria (D-7)."""
    scheduler = BackgroundScheduler(
        jobstores={"default": MemoryJobStore()},
        timezone=UTC,
    )
    scheduler.add_job(
        job or ejecutar_ciclo,
        trigger="interval",
        minutes=intervalo_min,
        id=JOB_ID,
        max_instances=1,
        coalesce=True,
    )
    return scheduler
