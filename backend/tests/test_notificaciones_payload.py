"""Contrato de `payload` y motivos de error del worker (capa: unit).

# AC notificaciones-mail/Contrato-de-payload (D-1) y Observabilidad (D-10).
# Datos ficticios `.test`; sin DB ni red.
"""

from datetime import UTC, datetime

import pytest

INICIO = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def _payload(**over):
    base = {
        "turno_id": "11111111-1111-4111-8111-111111111111",
        "tipo": "confirmacion",
        "enviar_en": INICIO.isoformat(),
        "paciente_nombre": "Paciente Ficticio",
        "paciente_email": "paciente@ficticio.test",
        "profesional_nombre": "Odontologa Ficticia",
        "inicio": "2026-10-20T12:00:00+00:00",
        "fin": "2026-10-20T12:30:00+00:00",
        "duracion_min": 30,
        "token_cancelacion": "22222222-2222-4222-8222-222222222222",
        "cancel_url": "https://turnos.ficticio.test/cancelar?token=22222222",
    }
    base.update(over)
    return base


def test_payload_completo_devuelve_datos():
    """D-1: con las 11 claves el contrato tipado queda completo."""
    from app.modules.notificaciones.payload import validar_payload

    resultado = validar_payload(_payload())

    assert resultado.tipo == "confirmacion"
    assert resultado.paciente_email == "paciente@ficticio.test"
    assert resultado.profesional_nombre == "Odontologa Ficticia"
    assert resultado.enviar_en == INICIO
    assert resultado.inicio == INICIO
    assert resultado.fin == datetime(2026, 10, 20, 12, 30, tzinfo=UTC)
    assert resultado.duracion_min == 30
    assert resultado.cancel_url.endswith("token=22222222")


@pytest.mark.parametrize(
    "clave",
    [
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
    ],
)
def test_payload_sin_campo_devuelve_incompleto(clave):
    """D-1: cualquier clave faltante se reporta como payload_incompleto."""
    from app.modules.notificaciones.payload import (
        PayloadIncompleto,
        validar_payload,
    )

    payload = _payload()
    payload.pop(clave)

    with pytest.raises(PayloadIncompleto) as exc_info:
        validar_payload(payload)

    assert clave in str(exc_info.value)


def test_payload_enviar_en_invalido_no_parsea():
    """D-1: `enviar_en` no ISO-8601 UTC no se parsea."""
    from app.modules.notificaciones.payload import (
        PayloadIncompleto,
        parsear_enviar_en,
        validar_payload,
    )

    with pytest.raises(PayloadIncompleto):
        parsear_enviar_en(_payload(enviar_en="no-es-una-fecha"))
    with pytest.raises(PayloadIncompleto):
        validar_payload(_payload(enviar_en="2026-10-20T09:00:00"))


def test_motivo_turno_cancelado_se_clasifica_descarte():
    """D-8: el descarte se distingue de un fallo real por el prefijo."""
    from app.modules.notificaciones.payload import (
        clasificar_error,
        motivo_turno_cancelado,
    )

    motivo = motivo_turno_cancelado("cancelado")

    assert motivo.startswith("turno_cancelado:")
    assert clasificar_error(motivo) == "descarte"


def test_motivo_smtp_se_clasifica_fallo():
    """D-4/D-10: SMTP y payload incompleto son fallos, no descartes."""
    from app.modules.notificaciones.payload import (
        clasificar_error,
        motivo_payload_incompleto,
        motivo_smtp,
    )

    smtp = motivo_smtp("timeout de conexión")
    payload = motivo_payload_incompleto("falta paciente_email")

    assert smtp.startswith("smtp:")
    assert payload.startswith("payload_incompleto:")
    assert clasificar_error(smtp) == "fallo"
    assert clasificar_error(payload) == "fallo"
