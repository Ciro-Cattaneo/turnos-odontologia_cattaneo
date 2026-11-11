"""Contrato de `Notificacion.payload` y motivos de error (C-08 D-1/D-4/D-8/D-10).

C-05 encola con 11 claves congeladas; este módulo las valida sin consultar
`Paciente`/`Profesional` y clasifica los motivos persistidos en `error`.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from app.models.notificacion import NotifTipo

REQUIRED_KEYS: tuple[str, ...] = (
    "turno_id",
    "tipo",
    "enviar_en",
    "paciente_nombre",
    "paciente_email",
    "profesional_nombre",
    "inicio",
    "fin",
    "duracion_min",
    "token_cancelacion",
    "cancel_url",
)

PREFIJO_SMTP = "smtp:"
PREFIJO_PAYLOAD_INCOMPLETO = "payload_incompleto:"
PREFIJO_TURNO_CANCELADO = "turno_cancelado:"
PREFIJO_TURNO_REPROGRAMADO = "turno_reprogramado:"

_MAX_DETALLE = 200


class PayloadIncompleto(Exception):
    """El payload no cumple el contrato de D-1 (faltante, vacío o inválido)."""

    def __init__(self, detalle: str) -> None:
        super().__init__(detalle)
        self.detalle = detalle


@dataclass(frozen=True, slots=True)
class PayloadValido:
    """Vista tipada de las 11 claves que consume el worker."""

    turno_id: str
    tipo: str
    enviar_en: datetime
    paciente_nombre: str
    paciente_email: str
    profesional_nombre: str
    inicio: datetime
    fin: datetime
    duracion_min: int
    token_cancelacion: str
    cancel_url: str


def _texto(payload: dict, clave: str) -> str:
    valor = payload.get(clave)
    if not isinstance(valor, str) or not valor.strip():
        raise PayloadIncompleto(f"falta o es inválido `{clave}`")
    return valor.strip()


def _timestamp(payload: dict, clave: str) -> datetime:
    raw = _texto(payload, clave)
    try:
        valor = datetime.fromisoformat(raw)
    except ValueError:
        raise PayloadIncompleto(f"`{clave}` no es ISO-8601") from None
    if valor.tzinfo is None or valor.utcoffset() is None:
        raise PayloadIncompleto(f"`{clave}` no tiene zona horaria")
    return valor.astimezone(UTC)


def parsear_enviar_en(payload: dict) -> datetime:
    """Parsea `payload.enviar_en` como timestamp aware (D-1)."""
    if not isinstance(payload, dict):
        raise PayloadIncompleto("el payload no es un objeto JSON")
    return _timestamp(payload, "enviar_en")


def validar_payload(payload: dict) -> PayloadValido:
    """Valida las 11 claves y devuelve el contrato tipado (D-1)."""
    if not isinstance(payload, dict):
        raise PayloadIncompleto("el payload no es un objeto JSON")

    tipo = _texto(payload, "tipo")
    if tipo not in {t.value for t in NotifTipo}:
        raise PayloadIncompleto(f"`tipo` desconocido: {tipo}")

    duracion = payload.get("duracion_min")
    if isinstance(duracion, bool) or not isinstance(duracion, int) or duracion <= 0:
        raise PayloadIncompleto("`duracion_min` inválido")

    return PayloadValido(
        turno_id=_texto(payload, "turno_id"),
        tipo=tipo,
        enviar_en=_timestamp(payload, "enviar_en"),
        paciente_nombre=_texto(payload, "paciente_nombre"),
        paciente_email=_texto(payload, "paciente_email"),
        profesional_nombre=_texto(payload, "profesional_nombre"),
        inicio=_timestamp(payload, "inicio"),
        fin=_timestamp(payload, "fin"),
        duracion_min=duracion,
        token_cancelacion=_texto(payload, "token_cancelacion"),
        cancel_url=_texto(payload, "cancel_url"),
    )


def _acotar(detalle: str) -> str:
    """Acota el detalle persistido/logueado y evita saltos de línea."""
    plano = " ".join(str(detalle).split())
    return plano[:_MAX_DETALLE]


def motivo_smtp(detalle: str) -> str:
    """Motivo de fallo SMTP persistido en `error` (D-4)."""
    return f"{PREFIJO_SMTP} {_acotar(detalle)}"


def motivo_payload_incompleto(detalle: str) -> str:
    """Motivo de saneamiento de payload (D-1)."""
    return f"{PREFIJO_PAYLOAD_INCOMPLETO} {_acotar(detalle)}"


def motivo_turno_cancelado(estado: str) -> str:
    """Motivo de descarte por turno no activo (D-8)."""
    return f"{PREFIJO_TURNO_CANCELADO} {_acotar(estado)}"


def motivo_turno_reprogramado(detalle: str) -> str:
    """Motivo de descarte por reprogramación (C-07 D-10)."""
    return f"{PREFIJO_TURNO_REPROGRAMADO} {_acotar(detalle)}"


def clasificar_error(error: str | None) -> str:
    """Clasifica `error` en `descarte` (obsoleto) o `fallo` (envío/payload)."""
    if error and (
        error.startswith(PREFIJO_TURNO_CANCELADO)
        or error.startswith(PREFIJO_TURNO_REPROGRAMADO)
    ):
        return "descarte"
    return "fallo"
