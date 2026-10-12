"""Listado público de profesionales (capa: api, PG real).

# AC agenda-disponibilidad/Listado-público (solo activos, sin staff, keyset).
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(db_session):
    """TestClient https contra PG real con rollback (público: sin auth)."""
    from app.core import ratelimit
    from app.db.session import get_db
    from app.main import app

    ratelimit.reset()
    ratelimit.reset_public()

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app, base_url="https://testserver") as c:
        yield c
    app.dependency_overrides.clear()


def test_lista_solo_activos_sin_staff(client, db_session):
    """# AC lista-pública: 2 activos + 1 inactivo → 200 con los 2, sin hash/rol."""
    from tests.conftest import mk_profesional

    mk_profesional(db_session, nombre="Activa Uno")
    mk_profesional(db_session, nombre="Activa Dos")
    mk_profesional(db_session, nombre="Inactiva Tres", activo=False)
    response = client.get("/api/profesionales")
    assert response.status_code == 200
    body = response.json()
    nombres = [p["nombre"] for p in body["items"]]
    assert "Inactiva Tres 3" not in nombres
    assert len(body["items"]) == 2
    for item in body["items"]:
        assert set(item) == {
            "id",
            "nombre",
            "especialidad",
            "matricula",
            "duracion_default_min",
            "ultima_actualizacion",
        }
        assert "password_hash" not in str(body)
        assert "rol" not in str(body).replace("profesional", "")


def test_baja_excluye_pero_historial_permanece(client, db_session):
    """# AC baja-lógica: inactivo con turnos históricos → fuera del listado."""
    from tests.conftest import mk_paciente, mk_profesional, mk_turno

    prof = mk_profesional(db_session, activo=False)
    pac = mk_paciente(db_session)
    mk_turno(db_session, prof.id, pac.id)
    response = client.get("/api/profesionales")
    assert response.status_code == 200
    ids = [p["id"] for p in response.json()["items"]]
    assert str(prof.id) not in ids
    # El historial sigue legible a nivel modelo (baja lógica, sin hard-delete).
    from app.models.turno import Turno

    assert (
        db_session.query(Turno).filter(Turno.profesional_id == prof.id).count() == 1
    )


def test_keyset_sin_offset(client, db_session):
    """# AC keyset: cursor avanza sin OFFSET ni duplicados."""
    from tests.conftest import mk_profesional

    for _ in range(3):
        mk_profesional(db_session)
    primera = client.get("/api/profesionales", params={"limit": 2})
    assert primera.status_code == 200
    cuerpo1 = primera.json()
    assert len(cuerpo1["items"]) == 2
    assert cuerpo1["next_cursor"] is not None
    segunda = client.get(
        "/api/profesionales", params={"limit": 2, "cursor": cuerpo1["next_cursor"]}
    )
    assert segunda.status_code == 200
    cuerpo2 = segunda.json()
    ids1 = {p["id"] for p in cuerpo1["items"]}
    ids2 = {p["id"] for p in cuerpo2["items"]}
    assert not (ids1 & ids2)
    assert len(ids1 | ids2) == 3
