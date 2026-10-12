"""Seed admin idempotente desde env (capa: db, PG real con rollback).

# AC core-models/Seed-admin-idempotente (2 corridas → 1 admin, hash no texto).
# AC staff-auth/Hash-final-con-rotación (hashes nuevos `$argon2id$`).
"""

import sqlalchemy


def test_seed_admin_idempotente_dos_corridas_un_admin(db_session):
    """# AC core-models/Seed-admin-idempotente: existe exactamente uno."""
    from app.db.seed import seed_admin

    email = "admin-seed@ficticio.test"
    primero = seed_admin(db_session, email, "password-ficticia-1")
    segundo = seed_admin(db_session, email, "password-ficticia-2")
    assert str(primero.id) == str(segundo.id)
    n = db_session.execute(
        sqlalchemy.text("SELECT count(*) FROM usuario_staff WHERE email = :email"),
        {"email": email},
    ).scalar()
    assert n == 1


def test_seed_admin_guarda_hash_argon2id_no_plaintext(db_session):
    """# AC staff-auth/Hash-final-con-rotación: seed nueva en esquema final."""
    from app.core.security import verify_password
    from app.db.seed import seed_admin

    email = "admin-hash@ficticio.test"
    password = "password-ficticia-solo-tests"
    admin = seed_admin(db_session, email, password)
    guardado = db_session.execute(
        sqlalchemy.text("SELECT password_hash, rol FROM usuario_staff WHERE id = :id"),
        {"id": str(admin.id)},
    ).one()
    assert guardado.password_hash != password
    assert guardado.password_hash.startswith("$argon2id$")
    assert guardado.rol == "admin"
    assert verify_password(password, guardado.password_hash) is True
    assert verify_password("otra-ficticia", guardado.password_hash) is False


def test_hash_legacy_de_semilla_anterior_sigue_verificando(db_session):
    """# AC staff-auth/Hash-final-con-rotación: verify dual solo-lectura."""
    import hashlib
    import hmac
    import secrets

    from app.core.security import verify_password
    from app.models.usuario_staff import StaffRol, UsuarioStaff

    password = "password-ficticia-legacy"
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    legacy = f"pbkdf2_sha256$600000${salt.hex()}${digest.hex()}"
    assert hmac.compare_digest(legacy, legacy) is True
    db_session.add(
        UsuarioStaff(
            email="admin-legacy@ficticio.test",
            password_hash=legacy,
            rol=StaffRol.admin,
        )
    )
    db_session.flush()
    assert verify_password(password, legacy) is True
    assert verify_password("otra-ficticia", legacy) is False
