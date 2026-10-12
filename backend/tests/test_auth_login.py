"""Login por cookie + errores genéricos + flags + sesiones (capa: api, PG real).

# AC staff-auth/Login-sesión, Errores-genéricos, Cookie-flags,
# AC staff-auth/Hash-final-con-rotación (hash rotado verifica directo).
"""

import pytest
from fastapi.testclient import TestClient

from app.models.usuario_staff import StaffRol


@pytest.fixture
def client(db_session):
    """TestClient https contra PG real con rollback + throttle limpio.

    Base https: la cookie de sesión es `Secure` en tests (FRONTEND_URL dummy
    es https) y el jar httpx solo reenvía `Secure` sobre TLS — con http las
    requests autenticadas llegarían sin cookie (falso 401).
    """
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


def mk_staff(
    db_session,
    email,
    password,
    rol=StaffRol.recepcion,
    activo=True,
    profesional_id=None,
    legacy=False,
):
    """Staff ficticio; `legacy=True` simula semilla C-02 sin rotar."""
    from app.core.security import hash_password
    from app.models.usuario_staff import UsuarioStaff

    if legacy:
        import hashlib
        import secrets as _secrets

        salt = _secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
        guardado = f"pbkdf2_sha256$600000${salt.hex()}${digest.hex()}"
    else:
        guardado = hash_password(password)
    user = UsuarioStaff(
        email=email,
        password_hash=guardado,
        rol=rol,
        activo=activo,
        profesional_id=profesional_id,
    )
    db_session.add(user)
    db_session.flush()
    return user


def test_login_valido_emite_cookie_con_rol(client, db_session):
    """# AC staff-auth/Login-sesión: 200 + cookie httpOnly, sin hash."""
    mk_staff(db_session, "recepcion@ficticio.test", "password-ficticia-1")
    response = client.post(
        "/api/auth/login",
        json={"email": "recepcion@ficticio.test", "password": "password-ficticia-1"},
    )
    assert response.status_code == 200
    assert response.json()["rol"] == "recepcion"
    assert response.json()["email"] == "recepcion@ficticio.test"
    assert "password_hash" not in response.json()
    assert "session" in response.cookies
    set_cookie = response.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Secure" in set_cookie
    assert "Max-Age=43200" in set_cookie


def test_login_invalido_indistinguible(client, db_session):
    """# AC staff-auth/Errores-genéricos: wrong ≡ desconocido ≡ inactivo."""
    mk_staff(db_session, "valida@ficticio.test", "password-ficticia-1")
    mk_staff(
        db_session, "inactiva@ficticio.test", "password-ficticia-1", activo=False
    )
    casos = [
        {"email": "valida@ficticio.test", "password": "otra-ficticia"},
        {"email": "nadie@ficticio.test", "password": "cualquiera-ficticia"},
        {"email": "inactiva@ficticio.test", "password": "password-ficticia-1"},
    ]
    cuerpos = set()
    for body in casos:
        response = client.post("/api/auth/login", json=body)
        assert response.status_code == 401
        assert "session" not in response.cookies
        cuerpos.add(response.text)
    assert len(cuerpos) == 1


def test_login_con_hash_legacy_verifica_directo(client, db_session):
    """# AC staff-auth/Hash-final-con-rotación: semilla vieja entra sin fricción."""
    mk_staff(db_session, "legacy@ficticio.test", "password-ficticia-1", legacy=True)
    response = client.post(
        "/api/auth/login",
        json={"email": "legacy@ficticio.test", "password": "password-ficticia-1"},
    )
    assert response.status_code == 200
    assert "session" in response.cookies


def test_dos_dispositivos_sesiones_independientes(client, db_session):
    """# AC staff-auth/Login-sesión EDGE: dos logins → dos `jti` distintos."""
    import jwt

    from app.core.config import get_settings

    mk_staff(db_session, "multi@ficticio.test", "password-ficticia-1")
    body = {"email": "multi@ficticio.test", "password": "password-ficticia-1"}
    primero = client.post("/api/auth/login", json=body)
    segundo = client.post("/api/auth/login", json=body)
    assert primero.status_code == 200
    assert segundo.status_code == 200
    secreto = get_settings().SECRET_KEY
    jti_1 = jwt.decode(
        primero.cookies["session"], secreto, algorithms=["HS256"]
    )["jti"]
    jti_2 = jwt.decode(
        segundo.cookies["session"], secreto, algorithms=["HS256"]
    )["jti"]
    assert jti_1 != jti_2


def test_logout_limpia_cookie_y_reuse_es_401(client, db_session):
    """# AC staff-auth/Logout-invalida: logout → 200 + reuse posterior 401."""
    from fastapi.exceptions import HTTPException

    from app.modules.auth.deps import get_current_staff

    mk_staff(db_session, "sale@ficticio.test", "password-ficticia-1")
    login = client.post(
        "/api/auth/login",
        json={"email": "sale@ficticio.test", "password": "password-ficticia-1"},
    )
    vieja = login.cookies["session"]
    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200
    assert "session" not in client.cookies
    assert 'Max-Age=0' in logout.headers["set-cookie"]
    reuse = client.post("/api/auth/logout", cookies={"session": vieja})
    assert reuse.status_code == 200
    with pytest.raises(HTTPException) as exc:
        get_current_staff(session=vieja, db=db_session)
    assert exc.value.status_code == 401


def test_logout_sin_sesion_es_noop_seguro(client):
    """# AC staff-auth/Logout-invalida EDGE: sin cookie → 200 sin fugas."""
    response = client.post("/api/auth/logout")
    assert response.status_code == 200
    assert "password_hash" not in response.text


def test_me_con_sesion_devuelve_email_rol_y_profesional(client, db_session):
    """# AC soporte C-10: sesión válida → 200 con identidad mínima."""
    from tests.conftest import mk_profesional

    prof = mk_profesional(db_session)
    mk_staff(
        db_session,
        "odonto@ficticio.test",
        "password-ficticia-1",
        rol=StaffRol.odontologo,
        profesional_id=prof.id,
    )
    login = client.post(
        "/api/auth/login",
        json={"email": "odonto@ficticio.test", "password": "password-ficticia-1"},
    )
    assert login.status_code == 200
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == {
        "email": "odonto@ficticio.test",
        "rol": "odontologo",
        "profesional_id": str(prof.id),
    }
    assert "password_hash" not in me.text


def test_me_sin_sesion_es_401(client):
    """# AC soporte C-10: sin cookie → 401 genérico."""
    me = client.get("/api/auth/me")
    assert me.status_code == 401


def test_me_refleja_rol_actualizado_desde_db(client, db_session):
    """# AC soporte C-10: la DB manda; el cambio de rol se ve sin re-login."""
    import sqlalchemy

    mk_staff(db_session, "cambia@ficticio.test", "password-ficticia-1")
    login = client.post(
        "/api/auth/login",
        json={"email": "cambia@ficticio.test", "password": "password-ficticia-1"},
    )
    assert login.status_code == 200
    db_session.execute(
        sqlalchemy.text(
            "UPDATE usuario_staff SET rol = 'admin' WHERE email = :email"
        ),
        {"email": "cambia@ficticio.test"},
    )
    db_session.flush()
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["rol"] == "admin"


def test_cookie_local_http_sin_secure(client, db_session, monkeypatch):
    """# AC staff-auth/Cookie-flags: con front http local no se marca Secure."""
    from app.main import app

    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173")
    mk_staff(db_session, "local@ficticio.test", "password-ficticia-1")
    with TestClient(app, base_url="http://testserver") as http_client:
        response = http_client.post(
            "/api/auth/login",
            json={
                "email": "local@ficticio.test",
                "password": "password-ficticia-1",
            },
        )
    assert response.status_code == 200
    assert "Secure" not in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
