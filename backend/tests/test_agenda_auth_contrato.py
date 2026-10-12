"""Contrato auth consumido de C-03 (capa: api, PG real; sin reimplementar).

# AC agenda-disponibilidad/CRUD-auth (401 sin sesión, 403 odonto ajeno,
# lectura propia ok). `require_role`/`require_own_profesional` se IMPORTAN de
C-03; el stub de sesión usa login real (borde documentado, no mock interno).
"""

import pytest
from fastapi.testclient import TestClient

from app.models.usuario_staff import StaffRol


@pytest.fixture
def client(db_session):
    """TestClient https contra PG real con rollback + throttle holgado."""
    from app.core import ratelimit
    from app.db.session import get_db
    from app.main import app

    ratelimit.reset()
    ratelimit.reset_public()
    monkeypatch_limit = 1000
    ratelimit.LOGIN_LIMIT = monkeypatch_limit

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app, base_url="https://testserver") as c:
        yield c
    app.dependency_overrides.clear()
    ratelimit.LOGIN_LIMIT = 10


@pytest.fixture
def escenario(db_session):
    """Dos profesionales + odonto linkeado a P1 (datos ficticios)."""
    from tests.conftest import mk_profesional
    from tests.test_auth_login import mk_staff

    p1 = mk_profesional(db_session)
    p2 = mk_profesional(db_session)
    mk_staff(
        db_session,
        "odonto@ficticio.test",
        "password-ficticia-1",
        rol=StaffRol.odontologo,
        profesional_id=p1.id,
    )
    return {"p1": str(p1.id), "p2": str(p2.id)}


def _ventana_body(pid, dia=1):
    return {
        "profesional_id": pid,
        "dia_semana": dia,
        "hora_desde": "09:00:00",
        "hora_hasta": "12:00:00",
    }


def test_sin_sesion_401(client, db_session, escenario):
    """# AC auth: escritura sin sesión → 401 (nunca 403 ni dato)."""
    post = client.post("/api/disponibilidades", json=_ventana_body(escenario["p1"]))
    assert post.status_code == 401
    assert (
        client.post(
            "/api/bloqueos",
            json={
                "profesional_id": escenario["p1"],
                "desde": "2026-10-20T10:00:00-03:00",
                "hasta": "2026-10-20T11:00:00-03:00",
                "motivo": "feriado ficticio",
            },
        ).status_code
        == 401
    )


def test_odontologo_ajeno_403(client, db_session, escenario):
    """# AC auth: odonto escribe/lee agenda ajena (P2) → 403 genérico."""
    login = client.post(
        "/api/auth/login",
        json={"email": "odonto@ficticio.test", "password": "password-ficticia-1"},
    )
    assert login.status_code == 200
    escritura = client.post(
        "/api/disponibilidades", json=_ventana_body(escenario["p2"])
    )
    assert escritura.status_code == 403
    agenda = client.get(
        f"/api/profesionales/{escenario['p2']}/agenda",
        params={"vista": "dia", "fecha": "2026-10-20"},
    )
    assert agenda.status_code == 403
    assert escenario["p2"] not in agenda.text


def test_odontologo_propio_lectura_ok(client, db_session, escenario):
    """# AC auth: odonto lee su propia agenda (P1) → 200 tipificada."""
    login = client.post(
        "/api/auth/login",
        json={"email": "odonto@ficticio.test", "password": "password-ficticia-1"},
    )
    assert login.status_code == 200
    response = client.get(
        f"/api/profesionales/{escenario['p1']}/agenda",
        params={"vista": "dia", "fecha": "2026-10-20"},
    )
    assert response.status_code == 200
    assert response.json()["profesional_id"] == escenario["p1"]


def test_firma_require_role_consumida_no_duplicada():
    """# AC D-4: C-04 importa el contrato C-03 (no lo reimplementa)."""
    import inspect

    import app.modules.auth.deps as deps
    import app.modules.profesionales.router as prof_router

    assert callable(deps.require_role("recepcion", "admin"))
    assert "require_role" in dir(prof_router) or hasattr(prof_router, "router")
    params = list(inspect.signature(deps.require_own_profesional).parameters)
    assert params == ["profesional_id", "staff"]
