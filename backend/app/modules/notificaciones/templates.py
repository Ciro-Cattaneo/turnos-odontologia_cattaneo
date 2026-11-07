"""Plantillas de mail en español, hora local y datos mínimos (C-08 D-6).

Solo `text/plain` en v1. Usa exclusivamente las 11 claves del payload: nunca
DNI, teléfono ni obra social (duro 12).
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.modules.notificaciones.payload import PayloadValido

TZ = ZoneInfo("America/Argentina/Buenos_Aires")


def _fecha(valor: datetime) -> str:
    return valor.astimezone(TZ).strftime("%d/%m/%Y")


def _hora(valor: datetime) -> str:
    return valor.astimezone(TZ).strftime("%H:%M")


def _datos_turno(payload: PayloadValido) -> str:
    return (
        f"Fecha: {_fecha(payload.inicio)}\n"
        f"Hora: {_hora(payload.inicio)}\n"
        f"Profesional: {payload.profesional_nombre}\n"
        f"Duración: {payload.duracion_min} minutos"
    )


def _confirmacion(payload: PayloadValido) -> tuple[str, str]:
    cuerpo = (
        f"Hola {payload.paciente_nombre}:\n\n"
        "Tu turno quedó confirmado.\n\n"
        f"{_datos_turno(payload)}\n\n"
        "Si no podés asistir, cancelalo desde este link:\n"
        f"{payload.cancel_url}\n"
    )
    return "Turno confirmado", cuerpo


def _recordatorio(payload: PayloadValido, cuando: str) -> tuple[str, str]:
    cuerpo = (
        f"Hola {payload.paciente_nombre}:\n\n"
        f"Te recordamos que tu turno es {cuando}.\n\n"
        f"{_datos_turno(payload)}\n\n"
        "Si no podés asistir, cancelalo desde este link:\n"
        f"{payload.cancel_url}\n"
    )
    return f"Recordatorio: tu turno es {cuando}", cuerpo


def _cancelacion(payload: PayloadValido) -> tuple[str, str]:
    cuerpo = (
        f"Hola {payload.paciente_nombre}:\n\n"
        "Tu turno fue cancelado.\n\n"
        f"Fecha: {_fecha(payload.inicio)}\n"
        f"Hora: {_hora(payload.inicio)}\n"
        f"Profesional: {payload.profesional_nombre}\n\n"
        "Si querés reprogramar, comunicate con la clínica.\n"
    )
    return "Turno cancelado", cuerpo


def render(tipo: str, payload: PayloadValido) -> tuple[str, str]:
    """Devuelve `(asunto, cuerpo)` para el tipo de notificación (D-6)."""
    if tipo == "confirmacion":
        return _confirmacion(payload)
    if tipo == "recordatorio_24h":
        return _recordatorio(payload, "mañana")
    if tipo == "recordatorio_2h":
        return _recordatorio(payload, "en 2 horas")
    if tipo == "cancelacion":
        return _cancelacion(payload)
    raise ValueError(f"tipo de notificación desconocido: {tipo}")
