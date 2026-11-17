"""Scheduler, lifespan y lock del worker (capa: unit + lifespan, sin red).

# AC notificaciones-mail/Worker-en-proceso (job 5 min, flag off, no solape,
# sin Redis).
"""

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import mk_paciente, mk_profesional, mk_turno

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


class FakeScheduler:
    """Scheduler falso para el lifespan: no levanta hilos ni jobs."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.started = False
        self.shutdown_wait: bool | None = None

    def start(self) -> None:
        self.started = True

    def shutdown(self, wait: bool = True) -> None:
        self.shutdown_wait = wait


class FakeSender:
    def __init__(self):
        self.llamadas = []

    def send(self, *, asunto: str, cuerpo: str, destinatario: str) -> None:
        self.llamadas.append((asunto, cuerpo, destinatario))


def _crear_notificacion(db_session):
    from app.models.notificacion import Notificacion, NotifTipo

    prof = mk_profesional(db_session)
    pac = mk_paciente(db_session)
    turno = mk_turno(db_session, prof.id, pac.id)
    notif = Notificacion(
        turno_id=turno.id,
        tipo=NotifTipo.confirmacion,
        intentos=0,
        payload={
            "turno_id": str(turno.id),
            "tipo": "confirmacion",
            "enviar_en": (NOW - timedelta(minutes=1)).isoformat(),
            "paciente_nombre": "Paciente Ficticio",
            "paciente_email": "paciente@ficticio.test",
            "profesional_nombre": "Odontologa Ficticia",
            "inicio": turno.inicio.isoformat(),
            "fin": turno.fin.isoformat(),
            "duracion_min": turno.duracion_min,
            "token_cancelacion": str(turno.token_cancelacion),
            "cancel_url": (
                f"https://turnos.ficticio.test/cancelar?token={turno.token_cancelacion}"
            ),
        },
    )
    db_session.add(notif)
    db_session.flush()
    return notif


# --- 6.1 Scheduler ---------------------------------------------------------


def test_scheduler_registra_job_con_intervalo_configurado():
    """D-7: job `notificaciones-mail` con intervalo, single/coalesce y RAM."""
    from apscheduler.jobstores.memory import MemoryJobStore
    from apscheduler.schedulers.background import BackgroundScheduler

    from app.modules.notificaciones.scheduler import crear_scheduler

    for intervalo in (5, 10):
        scheduler = crear_scheduler(intervalo_min=intervalo, job=lambda: None)

        assert isinstance(scheduler, BackgroundScheduler)
        assert isinstance(scheduler._jobstores["default"], MemoryJobStore)
        job = scheduler.get_job("notificaciones-mail")
        assert job is not None
        assert job.trigger.interval == timedelta(minutes=intervalo)
        assert job.max_instances == 1
        assert job.coalesce is True


# --- 6.2 Lifespan ----------------------------------------------------------


def test_lifespan_arranca_scheduler_con_flag_true(monkeypatch):
    """D-7: con `NOTIF_WORKER_ENABLED=true` arranca y apaga sin esperar."""
    import app.main as main

    creados: list[FakeScheduler] = []

    def _fake_crear_scheduler(**kwargs):
        scheduler = FakeScheduler(**kwargs)
        creados.append(scheduler)
        return scheduler

    monkeypatch.setenv("NOTIF_WORKER_ENABLED", "true")
    monkeypatch.setattr(main, "crear_scheduler", _fake_crear_scheduler)

    with TestClient(main.app, base_url="https://testserver"):
        assert len(creados) == 1
        assert creados[0].started is True
        assert creados[0].kwargs["intervalo_min"] == 5

    assert creados[0].shutdown_wait is False


def test_lifespan_no_arranca_scheduler_con_flag_false(monkeypatch):
    """D-7: `NOTIF_WORKER_ENABLED=false` no registra ni arranca job."""
    import app.main as main

    creados: list[FakeScheduler] = []

    def _fake_crear_scheduler(**kwargs):
        scheduler = FakeScheduler(**kwargs)
        creados.append(scheduler)
        return scheduler

    monkeypatch.setenv("NOTIF_WORKER_ENABLED", "false")
    monkeypatch.setattr(main, "crear_scheduler", _fake_crear_scheduler)

    with TestClient(main.app, base_url="https://testserver") as client:
        assert client.get("/api/health").status_code == 200

    assert creados == []


# --- 6.3 Lock de módulo ----------------------------------------------------


def test_worker_ciclo_solapado_se_omite(db_session, caplog):
    """D-3: con el ciclo en curso, el segundo se omite y se loguea."""
    from app.modules.notificaciones import worker

    notif = _crear_notificacion(db_session)
    sender = FakeSender()

    with worker._LOCK:
        with caplog.at_level(logging.WARNING, logger=worker.logger.name):
            resumen = worker.run_once(db_session, sender, now=NOW)

    recargada = db_session.get(type(notif), notif.id)
    assert sender.llamadas == []
    assert recargada.estado.value == "pendiente"
    assert resumen.enviadas == 0
    assert "solapado" in caplog.text.lower()


def test_worker_libera_lock_tras_ciclo(db_session):
    """D-3: el lock se libera al terminar (dos ciclos seguidos corren)."""
    from app.modules.notificaciones import worker

    _crear_notificacion(db_session)
    sender = FakeSender()

    primero = worker.run_once(db_session, sender, now=NOW)
    segundo = worker.run_once(db_session, sender, now=NOW)

    assert primero.enviadas == 1
    assert segundo.enviadas == 0
    assert len(sender.llamadas) == 1


# --- 6.4 Sin Redis ---------------------------------------------------------


def test_worker_no_requiere_redis():
    """PB-03: ningún módulo del worker referencia `REDIS_URL` ni `redis`."""
    from app.modules.notificaciones import worker

    raiz = Path(worker.__file__).resolve().parent
    fuentes = "\n".join(ruta.read_text(encoding="utf-8") for ruta in raiz.glob("*.py"))

    assert "REDIS_URL" not in fuentes
    assert "import redis" not in fuentes
    assert "from redis" not in fuentes
