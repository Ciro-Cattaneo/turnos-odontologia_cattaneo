"""Hasher final argon2id + verify dual con rotación (capa: unit/service, sin DB).

# AC staff-auth/Hash-final-con-rotación (happy + rotated-hash login).
"""

import hashlib
import hmac
import secrets


def _legacy_hash(password: str) -> str:
    """Vector conocido legacy: PBKDF2 transitorio de C-02 (stdlib, salt fijo)."""
    salt = bytes.fromhex("00" * 16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return f"pbkdf2_sha256$600000${salt.hex()}${digest.hex()}"


def test_hash_nuevo_usa_argon2id_y_verifica():
    """# AC staff-auth/Hash-final-con-rotación: hash nuevo verifica True."""
    from app.core.security import hash_password, verify_password

    guardado = hash_password("password-ficticia-1")
    assert guardado.startswith("$argon2id$")
    assert guardado != "password-ficticia-1"
    assert verify_password("password-ficticia-1", guardado) is True


def test_hash_legacy_pbkdf2_sigue_verificando():
    """# AC staff-auth/Hash-final-con-rotación: semilla C-02 verifica True."""
    from app.core.security import verify_password

    vector = _legacy_hash("password-ficticia-1")
    assert vector.startswith("pbkdf2_sha256$")
    assert verify_password("password-ficticia-1", vector) is True


def test_password_incorrecta_no_verifica_en_ningun_esquema():
    """# AC staff-auth/Hash-final-con-rotación: wrong → False en ambos."""
    from app.core.security import hash_password, verify_password

    nuevo = hash_password("password-ficticia-1")
    assert verify_password("otra-ficticia", nuevo) is False
    legacy = _legacy_hash("password-ficticia-1")
    assert verify_password("otra-ficticia", legacy) is False


def test_hash_corrupto_o_desconocido_no_verifica():
    """# AC staff-auth/Hash-final-con-rotación: formato corrupto → False."""
    from app.core.security import verify_password

    assert verify_password("x", "no-es-un-hash") is False
    assert verify_password("x", "") is False
    assert verify_password("x", "pbkdf2_sha256$iter-mal$$") is False
    assert verify_password("x", "$argon2id$corrupto") is False
    assert verify_password("x", "bcrypt$2b$10$abc") is False


def test_needs_rehash_solo_para_legacy():
    """# AC staff-auth/Hash-final-con-rotación: rotación detectable por prefijo."""
    from app.core.security import hash_password, needs_rehash

    assert needs_rehash(_legacy_hash("password-ficticia-1")) is True
    assert needs_rehash(hash_password("password-ficticia-1")) is False
    assert needs_rehash("corrupto") is True


def test_hash_nunca_guarda_plaintext():
    """# AC core-models/Seed-admin-idempotente: password no aparece en claro."""
    from app.core.security import hash_password

    password = "password-ficticia-solo-tests"
    assert password not in hash_password(password)
    first = hash_password(password)
    second = hash_password(password)
    assert first != second  # salt aleatorio por hash
    assert secrets.compare_digest(first, first) is True
    assert hmac.compare_digest(first, first) is True
