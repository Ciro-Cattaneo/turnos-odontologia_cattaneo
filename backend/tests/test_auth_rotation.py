"""Rotación E2E de semilla legacy al primer login (capa: api+db, PG real).

# AC staff-auth/Hash-final-con-rotación (cierra el handoff C-02).
"""

import pytest
from fastapi.testclient import TestClient


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


def _hash_legacy(password: str) -> str:
    """Semilla C-02 sin rotar (stdlib, formato `pbkdf2_sha256$…`)."""
    import hashlib
    import secrets as _secrets

    salt = _secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return f"pbkdf2_sha256$600000${salt.hex()}${digest.hex()}"


def test_primer_login_rota_hash_legacy_a_argon2id(client, db_session):
    """# AC staff-auth/Hash-final-con-rotación: 200 + hash reescrito."""
    import sqlalchemy

    from app.models.usuario_staff import StaffRol, UsuarioStaff

    password = "password-ficticia-legacy"
    db_session.add(
        UsuarioStaff(
            email="rota@ficticio.test",
            password_hash=_hash_legacy(password),
            rol=StaffRol.admin,
        )
    )
    db_session.flush()
    antes = db_session.execute(
        sqlalchemy.text(
            "SELECT password_hash FROM usuario_staff WHERE email = :email"
        ),
        {"email": "rota@ficticio.test"},
    ).scalar()
    assert antes.startswith("pbkdf2_sha256$")
    primero = client.post(
        "/api/auth/login",
        json={"email": "rota@ficticio.test", "password": password},
    )
    assert primero.status_code == 200
    db_session.expire_all()
    despues = db_session.execute(
        sqlalchemy.text(
            "SELECT password_hash FROM usuario_staff WHERE email = :email"
        ),
        {"email": "rota@ficticio.test"},
    ).scalar()
    assert despues.startswith("$argon2id$")
    assert despues != password


def test_segundo_login_usa_hash_rotado_directo(client, db_session):
    """# AC staff-auth/Hash-final-con-rotación: segundo login 200 sin fricción."""
    import sqlalchemy

    from app.models.usuario_staff import StaffRol, UsuarioStaff

    password = "password-ficticia-legacy"
    db_session.add(
        UsuarioStaff(
            email="rota2@ficticio.test",
            password_hash=_hash_legacy(password),
            rol=StaffRol.admin,
        )
    )
    db_session.flush()
    body = {"email": "rota2@ficticio.test", "password": password}
    assert client.post("/api/auth/login", json=body).status_code == 200
    assert client.post("/api/auth/login", json=body).status_code == 200
    guardado = db_session.execute(
        sqlalchemy.text(
            "SELECT password_hash FROM usuario_staff WHERE email = :email"
        ),
        {"email": "rota2@ficticio.test"},
    ).scalar()
    assert guardado.startswith("$argon2id$")


def test_password_incorrecta_no_rota_hash_legacy(client, db_session):
    """# AC staff-auth/Hash-final-con-rotación: fallo no reescribe nada."""
    import sqlalchemy

    from app.models.usuario_staff import StaffRol, UsuarioStaff

    db_session.add(
        UsuarioStaff(
            email="norota@ficticio.test",
            password_hash=_hash_legacy("password-ficticia-legacy"),
            rol=StaffRol.recepcion,
        )
    )
    db_session.flush()
    fallo = client.post(
        "/api/auth/login",
        json={"email": "norota@ficticio.test", "password": "otra-ficticia"},
    )
    assert fallo.status_code == 401
    guardado = db_session.execute(
        sqlalchemy.text(
            "SELECT password_hash FROM usuario_staff WHERE email = :email"
        ),
        {"email": "norota@ficticio.test"},
    ).scalar()
    assert guardado.startswith("pbkdf2_sha256$")
