"""Rate-limit en login sin lockout (capa: api + unit, PG real donde hay HTTP).

# AC staff-auth/Rate-limit-sin-lockout (happy + business-error).
"""

import time

import pytest
from fastapi.testclient import TestClient

from tests.test_auth_login import mk_staff


@pytest.fixture
def client(db_session):
    """TestClient https con throttle limpio por test."""
    from app.core import ratelimit
    from app.db.session import get_db
    from app.main import app

    ratelimit.reset()

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app, base_url="https://testserver") as c:
        yield c
    app.dependency_overrides.clear()


def test_ventana_deslizante_poda_intentos_viejos():
    """# AC staff-auth/Rate-limit-sin-lockout: fuera de ventana vuelve a pasar."""
    from app.core.ratelimit import check_rate_limit_with, reset

    reset()
    assert check_rate_limit_with("ip-ficticia-1", limit=2, window_s=1) is True
    assert check_rate_limit_with("ip-ficticia-1", limit=2, window_s=1) is True
    assert check_rate_limit_with("ip-ficticia-1", limit=2, window_s=1) is False
    time.sleep(1.1)
    assert check_rate_limit_with("ip-ficticia-1", limit=2, window_s=1) is True


def test_ips_distintas_no_comparten_cupo():
    """# AC staff-auth/Rate-limit-sin-lockout: el cupo es por IP."""
    from app.core.ratelimit import check_rate_limit_with, reset

    reset()
    assert check_rate_limit_with("ip-ficticia-a", limit=1, window_s=60) is True
    assert check_rate_limit_with("ip-ficticia-a", limit=1, window_s=60) is False
    assert check_rate_limit_with("ip-ficticia-b", limit=1, window_s=60) is True


def test_rafaga_sobre_limite_es_429(client, db_session, monkeypatch):
    """# AC staff-auth/Rate-limit-sin-lockout: exceder el límite → 429."""
    from app.core import ratelimit

    monkeypatch.setattr(ratelimit, "LOGIN_LIMIT", 3)
    mk_staff(db_session, "limite@ficticio.test", "password-ficticia-1")
    body = {"email": "limite@ficticio.test", "password": "password-ficticia-1"}
    for _ in range(3):
        assert client.post("/api/auth/login", json=body).status_code == 200
    excedido = client.post("/api/auth/login", json=body)
    assert excedido.status_code == 429


def test_429_identico_con_credenciales_validas_e_invalidas(
    client, db_session, monkeypatch
):
    """# AC staff-auth/Rate-limit-sin-lockout BUSINESS-ERROR: 429 no distingue."""
    from app.core import ratelimit

    monkeypatch.setattr(ratelimit, "LOGIN_LIMIT", 1)
    mk_staff(db_session, "igual@ficticio.test", "password-ficticia-1")
    valida = {"email": "igual@ficticio.test", "password": "password-ficticia-1"}
    invalida = {"email": "igual@ficticio.test", "password": "otra-ficticia"}
    assert client.post("/api/auth/login", json=valida).status_code == 200
    con_validas = client.post("/api/auth/login", json=valida)
    con_invalidas = client.post("/api/auth/login", json=invalida)
    assert con_validas.status_code == 429
    assert con_invalidas.status_code == 429
    assert con_validas.text == con_invalidas.text


def test_tras_la_ventana_login_valido_sin_bloqueo(
    client, db_session, monkeypatch
):
    """# AC staff-auth/Rate-limit-sin-lockout: sin lockout permanente en v1."""
    from app.core import ratelimit

    monkeypatch.setattr(ratelimit, "LOGIN_LIMIT", 1)
    monkeypatch.setattr(ratelimit, "LOGIN_WINDOW_S", 1)
    mk_staff(db_session, "ventana@ficticio.test", "password-ficticia-1")
    body = {"email": "ventana@ficticio.test", "password": "password-ficticia-1"}
    assert client.post("/api/auth/login", json=body).status_code == 200
    assert client.post("/api/auth/login", json=body).status_code == 429
    time.sleep(1.1)
    assert client.post("/api/auth/login", json=body).status_code == 200
