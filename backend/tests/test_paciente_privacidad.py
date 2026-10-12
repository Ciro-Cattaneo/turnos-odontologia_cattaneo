"""PB-04 soft-delete + DELETE solo cero turnos + trigger append-only (capa: db).

# AC paciente-privacidad/Desactivar-conserva-turnos (activo=false, historial).
# AC paciente-privacidad/Reactivar-restaura (activo=true, historial intacto).
# AC paciente-privacidad/Desactivar-idempotente (repetir no rompe nada).
# AC paciente-privacidad/Borrar-sin-turnos (DELETE físico permitido).
# AC paciente-privacidad/Borrar-con-turnos (FK RESTRICT rechaza).
# AC paciente-privacidad/Borrar-solo-cancelado (cancelados también retienen).
# AC paciente-privacidad/Mutacion-escribe-auditoria (trail crear legible).
# AC paciente-privacidad/UPDATE-auditoria-rechazado (trigger D-8).
# AC paciente-privacidad/DELETE-auditoria-rechazado (trigger D-8).
"""

from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy

from tests.conftest import mk_paciente, mk_profesional, mk_turno

BASE = datetime(2026, 10, 24, 13, 0, tzinfo=UTC)


def _con_turnos(db_session, n=2, estado=None):
    """Paciente + profesional con `n` turnos históricos (distintos slots)."""
    from app.models.turno import TurnoEstado

    prof = mk_profesional(db_session)
    pac = mk_paciente(db_session)
    for k in range(n):
        mk_turno(
            db_session,
            prof.id,
            pac.id,
            inicio=BASE + timedelta(hours=k),
            fin=BASE + timedelta(hours=k, minutes=30),
            estado=estado or TurnoEstado.atendido,
        )
    return prof, pac


def _turnos_de(db_session, paciente_id) -> int:
    return db_session.execute(
        sqlalchemy.text("SELECT count(*) FROM turno WHERE paciente_id = :id"),
        {"id": str(paciente_id)},
    ).scalar()


def _activos(db_session):
    return db_session.execute(
        sqlalchemy.text("SELECT id FROM paciente WHERE activo = true")
    ).all()


def test_desactivar_conserva_turnos_y_oculta_de_activos(db_session):
    """# AC paciente-privacidad/Desactivar-conserva-turnos: soft, no borra."""
    from app.models.paciente import Paciente

    _, pac = _con_turnos(db_session)
    pac.activo = False
    db_session.flush()
    assert _turnos_de(db_session, pac.id) == 2
    assert all(str(r.id) != str(pac.id) for r in _activos(db_session))
    fila = db_session.get(Paciente, pac.id)
    assert fila.activo is False


def test_reactivar_restaura_visibilidad_con_historial(db_session):
    """# AC paciente-privacidad/Reactivar-restaura: vuelve sin perder nada."""
    _, pac = _con_turnos(db_session)
    pac.activo = False
    db_session.flush()
    pac.activo = True
    db_session.flush()
    assert any(str(r.id) == str(pac.id) for r in _activos(db_session))
    assert _turnos_de(db_session, pac.id) == 2


def test_desactivar_ya_desactivado_es_idempotente(db_session):
    """# AC paciente-privacidad/Desactivar-idempotente: repetir no falla."""
    _, pac = _con_turnos(db_session, n=1)
    pac.activo = False
    db_session.flush()
    pac.activo = False
    db_session.flush()
    assert _turnos_de(db_session, pac.id) == 1


def test_borrar_paciente_sin_turnos_permitido(db_session):
    """# AC paciente-privacidad/Borrar-sin-turnos: DELETE físico sin huérfanos."""
    from app.models.paciente import Paciente

    pac = mk_paciente(db_session)
    pac_id = pac.id
    db_session.delete(pac)
    db_session.flush()
    assert db_session.get(Paciente, pac_id) is None


@pytest.mark.parametrize(
    "estado",
    ["reservado", "confirmado", "cancelado", "atendido", "ausente"],
    ids=["reservado", "confirmado", "cancelado", "atendido", "ausente"],
)
def test_borrar_paciente_con_turnos_rechazado(db_session, estado):
    """# AC paciente-privacidad/Borrar-con-turnos + solo-cancelado: RESTRICT.

    Cubre también el EDGE solo-cancelado: los cancelados se conservan para
    reportes/ausentismo, así que retienen igual que un activo.
    """
    from app.models.turno import TurnoEstado

    _, pac = _con_turnos(db_session, n=1, estado=TurnoEstado(estado))
    with pytest.raises(sqlalchemy.exc.IntegrityError, match="paciente"):
        db_session.delete(pac)
        db_session.flush()


def test_mutacion_staff_escribe_auditoria_legible(db_session):
    """# AC paciente-privacidad/Mutacion-escribe-auditoria: trail por ficha."""
    from app.models.auditoria import AuditoriaTurno
    from app.models.usuario_staff import StaffRol, UsuarioStaff

    prof = mk_profesional(db_session)
    pac = mk_paciente(db_session)
    turno = mk_turno(
        db_session, prof.id, pac.id, inicio=BASE, fin=BASE + timedelta(minutes=30)
    )
    staff = UsuarioStaff(
        email="auditor@ficticio.test",
        password_hash="h-ficticio",
        rol=StaffRol.recepcion,
    )
    db_session.add(staff)
    db_session.flush()
    db_session.add(
        AuditoriaTurno(
            turno_id=turno.id,
            actor_id=staff.id,
            accion="cancelar",
            detalle={"motivo": "paciente no puede asistir"},
        )
    )
    db_session.flush()
    filas = db_session.execute(
        sqlalchemy.text(
            "SELECT turno_id, actor_id, accion, created_at "
            "FROM auditoria_turno WHERE turno_id = :id"
        ),
        {"id": str(turno.id)},
    ).all()
    assert len(filas) == 1
    assert str(filas[0].actor_id) == str(staff.id)
    assert filas[0].accion == "cancelar"
    assert filas[0].created_at is not None


@pytest.mark.parametrize("operacion", ["update", "delete"])
def test_auditoria_no_admite_update_ni_delete(db_session, operacion):
    """# AC paciente-privacidad/UPDATE-DELETE-rechazados: trigger D-8 PG."""
    from app.models.auditoria import AuditoriaTurno

    prof = mk_profesional(db_session)
    pac = mk_paciente(db_session)
    turno = mk_turno(
        db_session, prof.id, pac.id, inicio=BASE, fin=BASE + timedelta(minutes=30)
    )
    fila = AuditoriaTurno(turno_id=turno.id, actor_id=None, accion="crear", detalle={})
    db_session.add(fila)
    db_session.flush()
    if operacion == "update":
        sentencia = sqlalchemy.text(
            "UPDATE auditoria_turno SET accion = :nueva WHERE id = :id"
        )
        parametros = {"nueva": "forzar_cancelacion", "id": str(fila.id)}
    else:
        sentencia = sqlalchemy.text("DELETE FROM auditoria_turno WHERE id = :id")
        parametros = {"id": str(fila.id)}
    # El trigger D-8 dispara en el servidor al ejecutar (savepoint: el resto
    # del test sigue intacto tras el rechazo).
    savepoint = db_session.begin_nested()
    with pytest.raises(sqlalchemy.exc.DBAPIError, match="append-only"):
        db_session.execute(sentencia, parametros)
    savepoint.rollback()
    queda = db_session.execute(
        sqlalchemy.text("SELECT count(*) FROM auditoria_turno WHERE id = :id"),
        {"id": str(fila.id)},
    ).scalar()
    assert queda == 1
