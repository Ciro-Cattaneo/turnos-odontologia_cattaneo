"""Serving de la SPA desde la imagen única (DO-R1, capa API/TestClient).

La app se re-importa con `STATIC_DIR` apuntando a un build ficticio (lo que
en la imagen es `./static`): nunca se requiere Docker para estos tests.
"""

import importlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main_module

INDEX_FICTICIO = (
    '<!doctype html><html lang="es"><body>'
    '<div id="root">SPA ficticia</div></body></html>'
)


def _recargar(monkeypatch: pytest.MonkeyPatch, static_dir: Path | None) -> TestClient:
    if static_dir is None:
        monkeypatch.delenv("STATIC_DIR", raising=False)
    else:
        monkeypatch.setenv("STATIC_DIR", str(static_dir))
    modulo = importlib.reload(main_module)
    return TestClient(modulo.app)


@pytest.fixture
def spa_client(monkeypatch, tmp_path) -> Iterator[TestClient]:
    """App con un build ficticio de la SPA presente."""
    build = tmp_path / "static"
    (build / "assets").mkdir(parents=True)
    (build / "assets" / "app-ficticio.js").write_text("console.log('spa');")
    (build / "index.html").write_text(INDEX_FICTICIO, encoding="utf-8")
    client = _recargar(monkeypatch, build)
    with client:
        yield client
    _recargar(monkeypatch, None)


@pytest.fixture
def sin_build_client(monkeypatch) -> Iterator[TestClient]:
    """App sin directorio de estáticos (modo desarrollo)."""
    client = _recargar(monkeypatch, None)
    with client:
        yield client
    _recargar(monkeypatch, None)


def test_spa_root_sirve_index_html_200(spa_client):
    """# AC DO-R1 FELIZ — `/` devuelve el index.html compilado."""
    respuesta = spa_client.get("/")

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/html")
    assert "SPA ficticia" in respuesta.text


@pytest.mark.parametrize(
    "ruta", ["/agenda", "/cancelar?token=ficticio"], ids=["agenda", "cancelar"]
)
def test_spa_ruta_profunda_sin_api_200_html(spa_client, ruta):
    """# AC DO-R1 BORDE — una ruta del router cliente devuelve el index."""
    respuesta = spa_client.get(ruta)

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/html")
    assert respuesta.text == INDEX_FICTICIO


def test_api_inexistente_404_json(spa_client):
    """# AC DO-R1 ERROR — `/api/*` desconocida conserva 404 JSON."""
    respuesta = spa_client.get("/api/ruta-inexistente")

    assert respuesta.status_code == 404
    assert respuesta.headers["content-type"].startswith("application/json")
    assert respuesta.json()["detail"] == "Not Found"


def test_health_sigue_200_sin_auth(spa_client):
    """# AC DO-R1 FELIZ — la SPA no tapa el liveness sin auth."""
    respuesta = spa_client.get("/api/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}


def test_spa_sin_build_conserva_api_y_root_json(sin_build_client):
    """# AC DO-R1 BORDE — sin build (dev) la API y `/` siguen igual."""
    assert sin_build_client.get("/api/health").status_code == 200

    respuesta = sin_build_client.get("/")

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("application/json")
    assert respuesta.json()["service"] == "turnos-odontologia"
