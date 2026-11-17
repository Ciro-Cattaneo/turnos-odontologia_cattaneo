"""Validación estricta del body de reserva (capa: schemas/API, sin DB).

# AC reserva-online/Validación-estricta (R2 S1-S5, S7; regla dura 1, D-4).
"""

import pytest
from fastapi.exceptions import HTTPException

from app.modules.turnos.schemas import TurnoCreate, parse_body_or_400

PROF = "00000000-0000-0000-0000-000000000001"


def _paciente(**over):
    base = {
        "nombre": "Paciente Ficticio",
        "dni": "30999001",
        "telefono": "+5491100000001",
        "obra_social": "OS Ficticia",
        "email": "paciente@ficticio.test",
    }
    base.update(over)
    return base


def _body(paciente=None, **over):
    body = {
        "profesional_id": PROF,
        "inicio": "2026-10-19T09:00:00-03:00",
        "paciente": _paciente() if paciente is None else paciente,
    }
    body.update(over)
    return body


def _detalle(body):
    with pytest.raises(HTTPException) as exc:
        parse_body_or_400(TurnoCreate, body)
    assert exc.value.status_code == 400
    return exc.value.detail


def test_reserva_faltantes_400_por_campo():
    """# AC R2 S1: `paciente={}` → un detalle por cada campo obligatorio."""
    detalle = _detalle(_body(paciente={}))
    campos = {d["campo"] for d in detalle}
    assert {
        "paciente.nombre",
        "paciente.dni",
        "paciente.telefono",
        "paciente.obra_social",
        "paciente.email",
    } <= campos


def test_reserva_vacios_400_por_campo():
    """# AC R2 S2: vacío o solo espacios cuenta como faltante."""
    detalle = _detalle(
        _body(paciente=_paciente(nombre="", telefono="   ", obra_social=""))
    )
    campos = {d["campo"] for d in detalle}
    assert {
        "paciente.nombre",
        "paciente.telefono",
        "paciente.obra_social",
    } <= campos


def test_reserva_email_invalido_400_solo_email():
    """# AC R2 S3: mail inválido → exactamente una entrada en `paciente.email`."""
    detalle = _detalle(_body(paciente=_paciente(email="no-es-email")))
    assert len(detalle) == 1
    assert detalle[0]["campo"] == "paciente.email"


def test_reserva_campo_extra_anidado_400():
    """# AC R2 S4: campo extra dentro de `paciente` → 400 en ese campo."""
    detalle = _detalle(_body(paciente=_paciente(alergias="penicilina")))
    assert any(d["campo"] == "paciente.alergias" for d in detalle)


def test_reserva_campo_extra_raiz_400():
    """# AC R2 S5: campo extra en la raíz → 400 en ese campo."""
    detalle = _detalle(_body(notas="observación"))
    assert any(d["campo"] == "notas" for d in detalle)


def test_reserva_inicio_sin_zona_400():
    """# AC R2 S7: `inicio` sin offset → 400 `campo=inicio`, tipo inicio_sin_zona."""
    detalle = _detalle(_body(inicio="2026-11-05T09:00:00"))
    assert len(detalle) == 1
    assert detalle[0]["campo"] == "inicio"
    assert detalle[0]["tipo"] == "inicio_sin_zona"
