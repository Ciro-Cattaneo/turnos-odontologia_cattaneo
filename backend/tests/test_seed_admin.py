"""Seed admin idempotente desde env (capa: db, PG real con rollback).

# AC core-models/Seed-admin-idempotente (2 corridas → 1 admin, hash no texto).
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


def test_seed_admin_guarda_hash_no_plaintext(db_session):
    """La password queda hasheada (formato `pbkdf2_sha256$…`) y verifica."""
    from app.db.seed import seed_admin, verify_password

    email = "admin-hash@ficticio.test"
    password = "password-ficticia-solo-tests"
    admin = seed_admin(db_session, email, password)
    guardado = db_session.execute(
        sqlalchemy.text("SELECT password_hash, rol FROM usuario_staff WHERE id = :id"),
        {"id": str(admin.id)},
    ).one()
    assert guardado.password_hash != password
    assert guardado.password_hash.startswith("pbkdf2_sha256$")
    assert guardado.rol == "admin"
    assert verify_password(password, guardado.password_hash) is True
    assert verify_password("otra-ficticia", guardado.password_hash) is False
