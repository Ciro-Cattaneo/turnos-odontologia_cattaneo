"""Endpoint liveness `GET /api/health` (capa: API/contract, httpx sin DB).

# AC service-health/S1 — 200 + `status=ok`.
# AC service-health/S2 — sin auth (nunca 401/403).
# AC service-health/S3 — sin DB (liveness puro).
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_responde_200_con_status_ok():
    """# AC service-health/S1 — probe de liveness responde 200 + status ok."""
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_no_requiere_auth():
    """# AC service-health/S2 — sin credenciales nunca 401/403."""
    response = client.get("/api/health")

    assert response.status_code not in (401, 403)


def test_health_sin_conexion_a_db(monkeypatch):
    """# AC service-health/S3 — con DB inalcanzable igual responde 200."""
    from fastapi.routing import APIRoute

    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://user:pass@db-inexistente:5432/x"
    )
    health_routes = [
        r for r in app.routes if isinstance(r, APIRoute) and r.path == "/api/health"
    ]
    assert len(health_routes) == 1
    assert health_routes[0].dependencies == []

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_routers_placeholder_registrados_con_prefijos():
    """D-1 — cada dominio futuro fija su prefijo `/api/...` desde el día 1."""
    import importlib

    for dominio in (
        "turnos",
        "agenda",
        "pacientes",
        "profesionales",
        "notificaciones",
        "auth",
        "reportes",
    ):
        router = importlib.import_module(f"app.modules.{dominio}.router").router
        assert router.prefix == f"/api/{dominio}"
        assert dominio in router.tags

    assert any(route.path == "/api/health" for route in app.routes)
