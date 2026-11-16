"""CORS restringido a `FRONTEND_URL` (SC-R3; capa API/TestClient)."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

ORIGEN_PERMITIDO = get_settings().FRONTEND_URL

client = TestClient(app)


def _preflight(origen: str) -> object:
    return client.options(
        "/api/turnos",
        headers={
            "Origin": origen,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )


def test_cors_preflight_origen_permitido_200_credenciales():
    """# AC SC-R3 FELIZ — FRONTEND_URL recibe el origen y credenciales."""
    respuesta = _preflight(ORIGEN_PERMITIDO)

    assert respuesta.status_code == 200
    assert respuesta.headers["access-control-allow-origin"] == ORIGEN_PERMITIDO
    assert respuesta.headers["access-control-allow-credentials"] == "true"


def test_same_origin_sin_origin_200():
    """# AC SC-R3 BORDE — request same-origin sin `Origin` no se afecta."""
    respuesta = client.get("/api/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}


@pytest.mark.parametrize(
    "origen",
    ["https://malicioso.test", "http://localhost:5173"],
    ids=["malicioso", "otro-puerto"],
)
def test_cors_preflight_origen_ajeno_rechazado_sin_allow_origin(origen):
    """# AC SC-R3 ERROR — ningún origen fuera de la allowlist obtiene ACAO."""
    respuesta = _preflight(origen)

    assert "access-control-allow-origin" not in respuesta.headers
    assert respuesta.status_code != 200
