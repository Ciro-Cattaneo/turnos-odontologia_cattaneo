"""Plantillas de mail en español, hora local y datos mínimos (capa: unit).

# AC notificaciones-mail/Plantillas (D-6): sin DNI, teléfono ni obra social.
"""

import pytest

CANCEL_URL = "https://turnos.ficticio.test/cancelar?token=22222222"


def _valido(tipo="recordatorio_24h", **over):
    from app.modules.notificaciones.payload import validar_payload

    payload = {
        "turno_id": "11111111-1111-4111-8111-111111111111",
        "tipo": tipo,
        "enviar_en": "2026-10-19T12:00:00+00:00",
        "paciente_nombre": "Paciente Ficticio",
        "paciente_email": "paciente@ficticio.test",
        "profesional_nombre": "Odontologa Ficticia",
        "inicio": "2026-10-20T12:00:00+00:00",
        "fin": "2026-10-20T12:30:00+00:00",
        "duracion_min": 30,
        "token_cancelacion": "22222222-2222-4222-8222-222222222222",
        "cancel_url": CANCEL_URL,
    }
    payload.update(over)
    return validar_payload(payload)


def test_plantilla_confirmacion_incluye_hora_local_y_link():
    """D-6: confirmación en español con hora de Buenos Aires y link."""
    from app.modules.notificaciones.templates import render

    asunto, cuerpo = render("confirmacion", _valido("confirmacion"))

    assert "confirmado" in asunto.lower()
    assert "Paciente Ficticio" in cuerpo
    assert "20/10/2026" in cuerpo
    assert "09:00" in cuerpo  # 12:00 UTC = 09:00 America/Argentina/Buenos_Aires
    assert CANCEL_URL in cuerpo


def test_plantilla_recordatorio_incluye_profesional_y_link():
    """D-6: recordatorio con profesional, duración y link de cancelación."""
    from app.modules.notificaciones.templates import render

    asunto, cuerpo = render("recordatorio_2h", _valido("recordatorio_2h"))

    assert "recordatorio" in asunto.lower()
    assert "Odontologa Ficticia" in cuerpo
    assert "30" in cuerpo
    assert CANCEL_URL in cuerpo


def test_plantilla_no_incluye_dni_telefono_ni_obra_social():
    """D-6/duro 12: solo usa las claves declaradas, aunque el payload traiga más."""
    from app.modules.notificaciones.templates import render

    payload = _valido(
        "confirmacion",
        paciente_dni="30999001",
        paciente_telefono="+5491100000001",
        obra_social="OS Ficticia",
    )

    asunto, cuerpo = render("confirmacion", payload)

    texto = f"{asunto}\n{cuerpo}"
    assert "30999001" not in texto
    assert "+5491100000001" not in texto
    assert "OS Ficticia" not in texto
    assert "obra social" not in texto.lower()
    assert "dni" not in texto.lower()
    assert "teléfono" not in texto.lower()


def test_plantilla_cancelacion_no_incluye_link_de_cancelacion():
    """D-6: el mail de cancelación no invita a cancelar de nuevo."""
    from app.modules.notificaciones.templates import render

    asunto, cuerpo = render("cancelacion", _valido("cancelacion"))

    assert "cancelado" in asunto.lower()
    assert "Odontologa Ficticia" in cuerpo
    assert CANCEL_URL not in cuerpo
    assert "cancelar?token=" not in cuerpo


def test_plantilla_tipo_desconocido_falla():
    """D-6: solo existen los cuatro tipos del dominio."""
    from app.modules.notificaciones.templates import render

    with pytest.raises(ValueError):
        render("otro", _valido())
