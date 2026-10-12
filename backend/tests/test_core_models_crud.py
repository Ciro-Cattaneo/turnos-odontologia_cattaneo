"""Persistencia de las 8 entidades (capa: db, PG real con rollback por test).

# AC core-models/Crear-ocho-entidades (las 8 filas persisten, FK resueltas).
# AC core-models/DNI-duplicado-rechazado (UNIQUE ux_paciente_dni).
# AC core-models/hora_desde-rechazada (CHECK ck_disponibilidad_horario).
"""

from datetime import UTC, datetime, time

import pytest
import sqlalchemy

from tests.conftest import mk_paciente, mk_profesional, mk_turno


def test_crear_ocho_entidades_persiste_con_fk_resueltas(db_session):
    """# AC core-models/Crear-ocho-entidades: grafo completo legible por PK."""
    from app.models.auditoria import AuditoriaTurno
    from app.models.bloqueo import Bloqueo
    from app.models.disponibilidad import Disponibilidad
    from app.models.notificacion import NotifEstado, Notificacion, NotifTipo
    from app.models.turno import CanalRecordatorio
    from app.models.usuario_staff import StaffRol, UsuarioStaff

    prof = mk_profesional(db_session)
    pac = mk_paciente(db_session)
    db_session.add(
        Disponibilidad(
            profesional_id=prof.id,
            dia_semana=1,
            hora_desde=time(9, 0),
            hora_hasta=time(13, 0),
        )
    )
    db_session.add(
        Bloqueo(
            profesional_id=prof.id,
            desde=datetime(2026, 10, 21, 9, 0, tzinfo=UTC),
            hasta=datetime(2026, 10, 21, 10, 0, tzinfo=UTC),
            motivo="Feriado ficticio",
        )
    )
    turno = mk_turno(db_session, prof.id, pac.id)
    db_session.add(
        Notificacion(
            turno_id=turno.id,
            canal=CanalRecordatorio.mail,
            tipo=NotifTipo.confirmacion,
            estado=NotifEstado.pendiente,
            payload={"para": "paciente@ficticio.test"},
        )
    )
    staff = UsuarioStaff(
        email="recepcion@ficticio.test",
        password_hash="hash-ficticio-no-plaintext",
        rol=StaffRol.recepcion,
    )
    db_session.add(staff)
    db_session.flush()
    db_session.add(
        AuditoriaTurno(
            turno_id=turno.id,
            actor_id=staff.id,
            accion="crear",
            detalle={"origen": "recepcion"},
        )
    )
    db_session.flush()

    # Columnas explícitas (sql-optimization: nunca SELECT * ni en tests).
    fila = db_session.execute(
        sqlalchemy.text(
            "SELECT id, profesional_id, paciente_id, estado FROM turno WHERE id = :id"
        ),
        {"id": str(turno.id)},
    ).one()
    assert str(fila.profesional_id) == str(prof.id)
    assert str(fila.paciente_id) == str(pac.id)
    assert fila.estado == "reservado"
    assert turno.created_at is not None and turno.created_at.tzinfo is not None


def test_segundo_paciente_mismo_dni_rechazado(db_session):
    """# AC core-models/DNI-duplicado-rechazado: ux_paciente_dni sin 2ª fila."""
    from app.models.paciente import Paciente

    primero = mk_paciente(db_session)
    savepoint = db_session.begin_nested()
    db_session.add(
        Paciente(
            nombre="Duplicado Ficticio",
            dni=primero.dni,
            telefono="+5491100010000",
            email="duplicado@ficticio.test",
        )
    )
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        db_session.flush()
    savepoint.rollback()
    n = db_session.execute(
        sqlalchemy.text("SELECT count(*) FROM paciente WHERE dni = :dni"),
        {"dni": primero.dni},
    ).scalar()
    assert n == 1


@pytest.mark.parametrize(
    ("desde", "hasta"),
    [(time(13, 0), time(9, 0)), (time(10, 0), time(10, 0))],
    ids=["invertida", "igual"],
)
def test_disponibilidad_horario_invalido_rechazada(db_session, desde, hasta):
    """# AC core-models/hora_desde-rechazada: CHECK hora_desde < hora_hasta."""
    from app.models.disponibilidad import Disponibilidad

    prof = mk_profesional(db_session)
    db_session.add(
        Disponibilidad(
            profesional_id=prof.id,
            dia_semana=2,
            hora_desde=desde,
            hora_hasta=hasta,
        )
    )
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        db_session.flush()


def test_disponibilidad_horario_valido_persiste(db_session):
    """Triangulación: el CHECK solo rechaza lo inválido, acepta 9:00–13:00."""
    from app.models.disponibilidad import Disponibilidad

    prof = mk_profesional(db_session)
    ventana = Disponibilidad(
        profesional_id=prof.id,
        dia_semana=2,
        hora_desde=time(9, 0),
        hora_hasta=time(13, 0),
    )
    db_session.add(ventana)
    db_session.flush()
    assert ventana.id is not None


@pytest.mark.parametrize(
    ("email", "dni", "vale"),
    [
        ("sin-arroba", "32111001", False),
        ("@sin-local", "32111002", False),
        ("valido@ficticio.test", "32111003", True),
        (None, "32111004", True),
    ],
)
def test_paciente_email_formato_laxo(db_session, email, dni, vale):
    """D-5: CHECK laxo acepta NULL y exige algo antes de `@`; C-05 el 400."""
    from app.models.paciente import Paciente

    db_session.add(Paciente(nombre="Mail Ficticio", dni=dni, email=email))
    if vale:
        db_session.flush()
    else:
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            db_session.flush()


@pytest.mark.parametrize("variante", ["igual", "distinto-case"])
def test_staff_email_unico_case_insensitive(db_session, variante):
    """CITEXT KB-04: el login no distingue mayúsculas en el UNIQUE."""
    from app.models.usuario_staff import StaffRol, UsuarioStaff

    base = "Unico@Ficticio.test"
    db_session.add(
        UsuarioStaff(email=base, password_hash="h1-ficticio", rol=StaffRol.recepcion)
    )
    db_session.flush()
    otro = base if variante == "igual" else "unico@ficticio.test"
    db_session.add(
        UsuarioStaff(email=otro, password_hash="h2-ficticio", rol=StaffRol.admin)
    )
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        db_session.flush()
