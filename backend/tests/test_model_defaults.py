"""Defaults de enums y nulabilidad D-9a (capa: unit, sin DB).

# AC turno-lifecycle/Canal-default (canal_recordatorio default mail).
# AC turno-lifecycle/Post-v1-nulas (pago_estado/lista_espera_pos NULL sin logica).
# AC paciente-privacidad/Anonimizacion-NULL-posible (dni/tel/mail nulables en DB).
"""

import uuid
from datetime import UTC, datetime

import pytest

from app.models.notificacion import NotifEstado, Notificacion, NotifTipo
from app.models.paciente import Paciente
from app.models.profesional import Profesional
from app.models.turno import CanalRecordatorio, Turno, TurnoEstado, TurnoOrigen
from app.models.usuario_staff import StaffRol


def _turno_minimo(**overrides):
    base = {
        "profesional_id": uuid.uuid4(),
        "paciente_id": uuid.uuid4(),
        "inicio": datetime(2026, 10, 13, 13, 0, tzinfo=UTC),
        "fin": datetime(2026, 10, 13, 13, 30, tzinfo=UTC),
        "origen": TurnoOrigen.online,
        "token_cancelacion": uuid.uuid4(),
    }
    base.update(overrides)
    return Turno(**base)


def test_estado_default_reservado():
    """# AC turno-lifecycle/Canal-default: `estado` defaultea a `reservado`."""
    default = Turno.__table__.c.estado.default
    assert default is not None
    assert default.arg == TurnoEstado.reservado


def test_canal_recordatorio_default_mail():
    """# AC turno-lifecycle/Canal-default: `canal_recordatorio` defaultea a `mail`."""
    default = Turno.__table__.c.canal_recordatorio.default
    assert default is not None
    assert default.arg == CanalRecordatorio.mail


def test_columnas_post_v1_nulas_por_defecto():
    """# AC turno-lifecycle/Post-v1-nulas: pago/lista en NULL sin logica v1."""
    turno = _turno_minimo()
    assert turno.pago_estado is None
    assert turno.lista_espera_pos is None
    assert Turno.__table__.c.pago_estado.nullable is True
    assert Turno.__table__.c.lista_espera_pos.nullable is True


@pytest.mark.parametrize("column", ["dni", "telefono", "email"])
def test_paciente_contacto_nulable_en_db(column):
    """# AC paciente-privacidad/Anonimizacion-NULL-posible: D-9a nulable en DB."""
    assert Paciente.__table__.c[column].nullable is True


@pytest.mark.parametrize("column", ["nombre", "obra_social"])
def test_paciente_identidad_nulable_en_db(column):
    """# AC paciente-privacidad/Anonimizacion-NULL-posible: D-9a cubre las 5."""
    assert Paciente.__table__.c[column].nullable is True


@pytest.mark.parametrize(
    ("enum_cls", "esperados"),
    [
        (TurnoEstado, {"reservado", "confirmado", "cancelado", "atendido", "ausente"}),
        (TurnoOrigen, {"online", "recepcion"}),
        (CanalRecordatorio, {"mail"}),
        (
            NotifTipo,
            {"confirmacion", "recordatorio_24h", "recordatorio_2h", "cancelacion"},
        ),
        (NotifEstado, {"pendiente", "enviada", "fallida"}),
        (StaffRol, {"recepcion", "odontologo", "admin"}),
    ],
)
def test_vocabulario_enum_cerrado(enum_cls, esperados):
    """D-3: vocabularios RN-TU-07/RN-NO cerrados (ni mas ni menos valores)."""
    assert {m.value for m in enum_cls} == esperados


def test_notificacion_default_pendiente_sin_intentos():
    """Worker C-08: toda notificacion nace `pendiente` con 0 intentos."""
    assert Notificacion.__table__.c.estado.default.arg == NotifEstado.pendiente
    assert Notificacion.__table__.c.intentos.default.arg == 0


def test_defaults_nivel_servidor_para_insert_crudo():
    """Los defaults viven tambien en DB (server_default), no solo en el ORM."""
    assert "reservado" in str(Turno.__table__.c.estado.server_default.arg)
    assert "mail" in str(Turno.__table__.c.canal_recordatorio.server_default.arg)
    assert Paciente.__table__.c.activo.default.arg is True
    assert Profesional.__table__.c.activo.default.arg is True
    assert Turno.__table__.c.duracion_min.default.arg == 30
