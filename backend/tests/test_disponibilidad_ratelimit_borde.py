"""Rate-limit público 30 req/min/IP (capa: api, reloj fake, sin sleeps).

# AC agenda-disponibilidad/Rate-limit (30 ok, 31 → 429 + Retry-After,
# reset tras 60s). Reloj fake vía `monkeypatch` sobre `time.monotonic`.
"""

import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(db_session, monkeypatch):
    """TestClient https + reloj fake controlable (sin `sleep` real)."""
    from app.core import ratelimit
    from app.db.session import get_db
    from app.main import app

    ratelimit.reset()
    ratelimit.reset_public()
    ahora = [1_000.0]
    monkeypatch.setattr(time, "monotonic", lambda: ahora[0])

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app, base_url="https://testserver") as c:
        yield c, ahora
    app.dependency_overrides.clear()


@pytest.fixture
def prof_con_ventana(db_session):
    """Profesional con ventana lunes 09-11 (respuestas 200 deterministas)."""
    from datetime import date
    from datetime import time as dtime

    from app.models.disponibilidad import Disponibilidad
    from tests.conftest import mk_profesional

    prof = mk_profesional(db_session)
    db_session.add(
        Disponibilidad(
            profesional_id=prof.id,
            dia_semana=0,
            hora_desde=dtime(9, 0),
            hora_hasta=dtime(11, 0),
            vigente_desde=date(2026, 1, 1),
            vigente_hasta=date(2026, 12, 31),
        )
    )
    db_session.flush()
    return prof


def _params(pid):
    return {
        "profesional_id": str(pid),
        "desde": "2026-10-19T09:00:00-03:00",
        "hasta": "2026-10-19T11:00:00-03:00",
    }


def test_30_requests_ok(client, prof_con_ventana):
    """# AC tráfico-normal: 30 requests en 60s → todas 200."""
    c, _ = client
    for _ in range(30):
        respuesta = c.get("/api/disponibilidad", params=_params(prof_con_ventana.id))
        assert respuesta.status_code == 200


def test_31_rechazada_429_con_retry_after(client, prof_con_ventana):
    """# AC exceso: request 31 en la ventana → 429 + `Retry-After`, sin slots."""
    c, _ = client
    for _ in range(30):
        c.get("/api/disponibilidad", params=_params(prof_con_ventana.id))
    respuesta = c.get("/api/disponibilidad", params=_params(prof_con_ventana.id))
    assert respuesta.status_code == 429
    assert "retry-after" in {k.lower() for k in respuesta.headers}
    assert int(respuesta.headers["Retry-After"]) >= 1


def test_ventana_resetea_tras_60s(client, prof_con_ventana):
    """# AC reset-ventana: tras 60s el contador vuelve a 0 (reloj fake)."""
    c, ahora = client
    for _ in range(30):
        c.get("/api/disponibilidad", params=_params(prof_con_ventana.id))
    assert (
        c.get("/api/disponibilidad", params=_params(prof_con_ventana.id)).status_code
        == 429
    )
    ahora[0] += 61.0
    respuesta = c.get("/api/disponibilidad", params=_params(prof_con_ventana.id))
    assert respuesta.status_code == 200
    assert respuesta.json()["slots"]
