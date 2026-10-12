"""Schemas estrictos de login (capa: schemas/unit, sin DB).

# AC staff-auth/Schemas-estrictos (400 por campo, `extra='forbid'`).
"""

import pytest
from pydantic import ValidationError


def test_login_rechaza_campo_extra():
    """# AC staff-auth/Schemas-estrictos: `remember_me` → error en ese campo."""
    from app.modules.auth.schemas import LoginIn

    with pytest.raises(ValidationError) as exc:
        LoginIn(
            email="recepcion@ficticio.test",
            password="password-ficticia-1",
            remember_me=True,  # type: ignore[call-arg]
        )
    assert "remember_me" in str(exc.value)


def test_login_email_malformado_es_error_por_campo():
    """# AC staff-auth/Schemas-estrictos: email inválido identifica `email`."""
    from app.modules.auth.schemas import LoginIn

    with pytest.raises(ValidationError) as exc:
        LoginIn(email="no-es-email", password="password-ficticia-1")
    campos = {e["loc"][0] for e in exc.value.errors()}
    assert "email" in campos


def test_login_sin_password_es_error_por_campo():
    """# AC staff-auth/Schemas-estrictos: falta `password` → error en campo."""
    from app.modules.auth.schemas import LoginIn

    with pytest.raises(ValidationError) as exc:
        LoginIn(email="recepcion@ficticio.test")  # type: ignore[call-arg]
    campos = {e["loc"][0] for e in exc.value.errors()}
    assert "password" in campos


def test_login_valido_acepta_y_no_expone_hash():
    """# AC staff-auth/Schemas-estrictos: body válido pasa sin extras."""
    from app.modules.auth.schemas import LoginIn

    login = LoginIn(email="recepcion@ficticio.test", password="password-ficticia-1")
    assert login.email == "recepcion@ficticio.test"
    assert "password_hash" not in login.model_dump()
