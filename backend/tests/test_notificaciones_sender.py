"""Cliente SMTP del borde (capa: integración de borde; stdlib mockeada).

# AC notificaciones-mail/SMTP-configurable (D-5): TLS 587, SSL 465 y timeout.
"""

import smtplib

import pytest


class _FakeSMTP:
    """Doble del borde `smtplib`: registra conexión, TLS, login y envío."""

    instancias: list["_FakeSMTP"] = []
    error_login: Exception | None = None

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.starttls_kwargs: dict | None = None
        self.login_credenciales: tuple[str, str] | None = None
        self.mensaje = None
        type(self).instancias.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def starttls(self, **kwargs):
        self.starttls_kwargs = kwargs

    def login(self, user, password):
        if _FakeSMTP.error_login is not None:
            raise _FakeSMTP.error_login
        self.login_credenciales = (user, password)

    def send_message(self, mensaje):
        self.mensaje = mensaje


class _FakeSMTPSSL(_FakeSMTP):
    instancias: list["_FakeSMTPSSL"] = []

    def starttls(self, **kwargs):  # pragma: no cover - no debe llamarse en 465
        raise AssertionError("starttls no debe usarse con SMTP_SSL")


@pytest.fixture(autouse=True)
def _reset_fakes(monkeypatch):
    _FakeSMTP.instancias = []
    _FakeSMTPSSL.instancias = []
    _FakeSMTP.error_login = None
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", _FakeSMTPSSL)


def _sender(port=587, timeout_s=15):
    from app.modules.notificaciones.sender import SMTPSender

    return SMTPSender(
        host="smtp.ficticio.test",
        port=port,
        user="usuario-ficticio",
        password="clave-secreta-smtp",
        from_addr="turnos@ficticio.test",
        timeout_s=timeout_s,
    )


def test_sender_587_usa_starttls_y_login():
    """D-5: puerto 587 → SMTP + starttls(contexto) + login + send_message."""
    _sender(port=587).send(
        asunto="Asunto ficticio",
        cuerpo="Cuerpo ficticio",
        destinatario="paciente@ficticio.test",
    )

    assert len(_FakeSMTP.instancias) == 1
    conexion = _FakeSMTP.instancias[0]
    assert (conexion.host, conexion.port) == ("smtp.ficticio.test", 587)
    assert conexion.timeout == 15
    assert conexion.starttls_kwargs is not None
    assert conexion.starttls_kwargs["context"] is not None
    assert conexion.login_credenciales == ("usuario-ficticio", "clave-secreta-smtp")
    assert conexion.mensaje["Subject"] == "Asunto ficticio"
    assert conexion.mensaje["To"] == "paciente@ficticio.test"
    assert conexion.mensaje["From"] == "turnos@ficticio.test"
    assert "Cuerpo ficticio" in conexion.mensaje.get_content()
    assert _FakeSMTPSSL.instancias == []


def test_sender_465_usa_ssl_y_respeta_timeout():
    """D-5: puerto 465 → SMTP_SSL directo con `SMTP_TIMEOUT_S`."""
    _sender(port=465, timeout_s=7).send(
        asunto="Asunto ficticio",
        cuerpo="Cuerpo ficticio",
        destinatario="paciente@ficticio.test",
    )

    assert _FakeSMTP.instancias == []
    assert len(_FakeSMTPSSL.instancias) == 1
    conexion = _FakeSMTPSSL.instancias[0]
    assert conexion.timeout == 7
    assert conexion.login_credenciales == ("usuario-ficticio", "clave-secreta-smtp")
    assert conexion.mensaje["Subject"] == "Asunto ficticio"


def test_sender_error_de_login_se_envuelve_sin_password():
    """D-5/duro 10: el `SendError` acota el detalle y nunca expone SMTP_PASS."""
    from app.modules.notificaciones.sender import SendError

    password = "clave-secreta-smtp"
    _FakeSMTP.error_login = smtplib.SMTPAuthenticationError(
        535, f"credenciales invalidas: {password}".encode()
    )

    with pytest.raises(SendError) as exc_info:
        _sender().send(
            asunto="Asunto ficticio",
            cuerpo="Cuerpo ficticio",
            destinatario="paciente@ficticio.test",
        )

    assert password not in str(exc_info.value)
    assert password not in repr(exc_info.value)
    assert len(str(exc_info.value)) <= 220


def test_sender_error_de_conexion_se_envuelve(monkeypatch):
    """D-5: `OSError` de conexión también se traduce a `SendError`."""
    import app.modules.notificaciones.sender as sender_mod
    from app.modules.notificaciones.sender import SendError

    def _explota(*_args, **_kwargs):
        raise OSError("conexión rechazada")

    monkeypatch.setattr(sender_mod.smtplib, "SMTP", _explota)
    with pytest.raises(SendError) as exc_info:
        _sender().send(
            asunto="Asunto ficticio",
            cuerpo="Cuerpo ficticio",
            destinatario="paciente@ficticio.test",
        )

    assert "conexión rechazada" in str(exc_info.value)
