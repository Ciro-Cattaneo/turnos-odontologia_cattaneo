"""Cliente SMTP inyectable del worker (C-08 D-5).

`SMTPSender` usa solo stdlib: `smtplib` + `EmailMessage`. El worker recibe un
`MailSender`, de modo que los tests reemplazan únicamente este borde (duro 9).
"""

import smtplib
import ssl
from email.message import EmailMessage
from typing import Protocol

from app.core.config import get_settings

_MAX_DETALLE = 200


class SendError(Exception):
    """Fallo de conexión/login/envío SMTP (mensaje acotado, sin secretos)."""


class MailSender(Protocol):
    """Borde de envío que el worker consume (inyectable en tests)."""

    def send(self, *, asunto: str, cuerpo: str, destinatario: str) -> None: ...


def _sanitizar(exc: BaseException, password: str) -> str:
    """Acota el detalle y enmascara `SMTP_PASS` (duro 10)."""
    texto = " ".join(str(exc).split())
    if password:
        texto = texto.replace(password, "***")
    return texto[:_MAX_DETALLE]


class SMTPSender:
    """Envío SMTP real: starttls en 587, SSL implícito en 465."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        user: str,
        password: str,
        from_addr: str,
        timeout_s: int = 15,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_addr = from_addr
        self.timeout_s = timeout_s

    def _mensaje(self, asunto: str, cuerpo: str, destinatario: str) -> EmailMessage:
        msg = EmailMessage()
        msg["Subject"] = asunto
        msg["From"] = self.from_addr
        msg["To"] = destinatario
        msg.set_content(cuerpo)
        return msg

    def send(self, *, asunto: str, cuerpo: str, destinatario: str) -> None:
        """Envía un mail de texto plano; cualquier fallo → `SendError`."""
        msg = self._mensaje(asunto, cuerpo, destinatario)
        try:
            if self.port == 465:
                with smtplib.SMTP_SSL(
                    self.host, self.port, timeout=self.timeout_s
                ) as smtp:
                    smtp.login(self.user, self.password)
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=self.timeout_s) as smtp:
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.login(self.user, self.password)
                    smtp.send_message(msg)
        except (smtplib.SMTPException, OSError) as exc:
            raise SendError(_sanitizar(exc, self.password)) from None


def default_sender() -> MailSender:
    """Fábrica por defecto: configuración SMTP del entorno (D-11)."""
    settings = get_settings()
    return SMTPSender(
        host=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        user=settings.SMTP_USER,
        password=settings.SMTP_PASS,
        from_addr=settings.SMTP_FROM,
        timeout_s=settings.SMTP_TIMEOUT_S,
    )
