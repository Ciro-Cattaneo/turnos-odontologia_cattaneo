"""Matriz RBAC + scoping odontólogo + 401-vs-403 (capa: api, PG real).

# AC staff-auth/require_role-herencia, Odontólogo-scoping, 401-vs-403.
"""

from uuid import UUID

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from app.models.usuario_staff import StaffRol
from app.modules.auth.deps import CurrentStaff, require_own_profesional, require_role
from tests.test_auth_login import mk_staff

LECTURA = "/api/test-only/lectura"
ESCRITURA = "/api/test-only/escritura"
ADMIN = "/api/test-only/gestion"


def _montar_rutas():
    """Rutas de prueba sobre la app real (contrato que C-04/C-07 copian)."""
    from app.main import app

    if any(r.path == LECTURA for r in app.routes):
        return

    @app.get(LECTURA, dependencies=[Depends(require_role("recepcion"))])
    def lectura() -> dict[str, bool]:
        return {"ok": True}

    @app.post(ESCRITURA, dependencies=[Depends(require_role("recepcion"))])
    def escritura() -> dict[str, bool]:
        return {"ok": True}

    @app.get(ADMIN, dependencies=[Depends(require_role("admin"))])
    def gestion() -> dict[str, bool]:
        return {"ok": True}

    @app.get(
        "/api/test-only/agenda/{profesional_id}",
        dependencies=[Depends(require_role("odontologo"))],
    )
    def agenda(profesional_id: UUID, staff: CurrentStaff) -> dict[str, bool]:
        require_own_profesional(profesional_id, staff)
        return {"ok": True}


_montar_rutas()


@pytest.fixture
def client(db_session, monkeypatch):
    """TestClient https con throttle holgado (la matriz hace >10 logins)."""
    from app.core import ratelimit
    from app.db.session import get_db
    from app.main import app

    monkeypatch.setattr(ratelimit, "LOGIN_LIMIT", 1000)
    ratelimit.reset()

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app, base_url="https://testserver") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def usuarios(db_session):
    """Un staff por rol + odontólogo sin link (datos ficticios)."""
    from tests.conftest import mk_profesional

    p1 = mk_profesional(db_session)
    p2 = mk_profesional(db_session)
    mk_staff(
        db_session, "admin@ficticio.test", "password-ficticia-1", rol=StaffRol.admin
    )
    mk_staff(
        db_session,
        "recepcion@ficticio.test",
        "password-ficticia-1",
        rol=StaffRol.recepcion,
    )
    mk_staff(
        db_session,
        "odonto@ficticio.test",
        "password-ficticia-1",
        rol=StaffRol.odontologo,
        profesional_id=p1.id,
    )
    mk_staff(
        db_session,
        "odonto-sin-link@ficticio.test",
        "password-ficticia-1",
        rol=StaffRol.odontologo,
    )
    return {"p1": str(p1.id), "p2": str(p2.id)}


def _login_como(client, email):
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "password-ficticia-1"},
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    "email,ruta,metodo,esperado",
    [
        ("admin@ficticio.test", LECTURA, "get", 200),
        ("admin@ficticio.test", ESCRITURA, "post", 200),
        ("admin@ficticio.test", ADMIN, "get", 200),
        ("recepcion@ficticio.test", LECTURA, "get", 200),
        ("recepcion@ficticio.test", ESCRITURA, "post", 200),
        ("recepcion@ficticio.test", ADMIN, "get", 403),
        ("odonto@ficticio.test", LECTURA, "get", 403),
        ("odonto@ficticio.test", ESCRITURA, "post", 403),
        ("odonto@ficticio.test", ADMIN, "get", 403),
    ],
)
def test_matriz_rbac_rol_por_recurso(
    client, db_session, usuarios, email, ruta, metodo, esperado
):
    """# AC staff-auth/require_role-herencia: admin ⊇ recepción; odonto aparte."""
    _login_como(client, email)
    response = getattr(client, metodo)(ruta)
    assert response.status_code == esperado


def test_odontologo_ve_su_agenda_propia(client, db_session, usuarios):
    """# AC staff-auth/Odontólogo-scoping: P1 propio → 200."""
    _login_como(client, "odonto@ficticio.test")
    response = client.get(f"/api/test-only/agenda/{usuarios['p1']}")
    assert response.status_code == 200


def test_odontologo_no_ve_agenda_ajena(client, db_session, usuarios):
    """# AC staff-auth/Odontólogo-scoping: P2 → 403 sin datos."""
    _login_como(client, "odonto@ficticio.test")
    response = client.get(f"/api/test-only/agenda/{usuarios['p2']}")
    assert response.status_code == 403
    assert "p2" not in response.text.lower().replace("test-only", "")
    assert usuarios["p2"] not in response.text


def test_odontologo_sin_link_no_accede_agendas(client, db_session, usuarios):
    """# AC staff-auth/Odontólogo-scoping: sin `profesional_id` → 403."""
    _login_como(client, "odonto-sin-link@ficticio.test")
    response = client.get(f"/api/test-only/agenda/{usuarios['p1']}")
    assert response.status_code == 403


def test_admin_accede_cualquier_agenda(client, db_session, usuarios):
    """# AC staff-auth/require_role-herencia: admin → todo, incluso agendas."""
    _login_como(client, "admin@ficticio.test")
    assert client.get(f"/api/test-only/agenda/{usuarios['p1']}").status_code == 200
    assert client.get(f"/api/test-only/agenda/{usuarios['p2']}").status_code == 200


def test_sin_cookie_todo_staff_es_401(client, db_session, usuarios):
    """# AC staff-auth/401-vs-403: sin sesión nunca 403 ni dato."""
    assert client.get(LECTURA).status_code == 401
    assert client.post(ESCRITURA).status_code == 401
    assert client.get(ADMIN).status_code == 401
    agenda = client.get(f"/api/test-only/agenda/{usuarios['p1']}")
    assert agenda.status_code == 401


def test_rol_insuficiente_no_rompe_sesion(client, db_session, usuarios):
    """# AC staff-auth/401-vs-403: tras un 403 la sesión sigue válida."""
    _login_como(client, "recepcion@ficticio.test")
    assert client.get(ADMIN).status_code == 403
    assert client.get(LECTURA).status_code == 200


def test_contrato_para_c04_importable_y_estable():
    """# AC staff-auth/require_role-herencia: C-04/C-07 importan, no duplican."""
    import inspect

    import app.modules.auth.deps as deps

    assert callable(deps.require_role("recepcion"))
    assert callable(deps.require_role("admin"))
    assert list(inspect.signature(deps.require_own_profesional).parameters) == [
        "profesional_id",
        "staff",
    ]
    assert list(inspect.signature(deps.get_current_staff).parameters) == [
        "session",
        "db",
    ]
    assert deps.CurrentStaff is not None
    assert deps.DbSession is not None
