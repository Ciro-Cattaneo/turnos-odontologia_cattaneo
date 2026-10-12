"""Invariantes del ciclo de vida de `Turno` a nivel modelo (capa: db).

# AC turno-lifecycle/Crear-reservado-online (fila válida + created_at + token).
# AC turno-lifecycle/Token-duplicado-o-nulo (UNIQUE + NOT NULL ux_turno_token).
# AC turno-lifecycle/Estado-origen-enum (vocabularios cerrados).
# AC turno-lifecycle/Fin-mayor-inicio (CHECK ck_turno_fin_gt_inicio).
# AC turno-lifecycle/Duracion-cero-borde (rango vacío rechazado).
# AC turno-lifecycle/Duracion-inconsistente (CHECK ck_turno_duracion_min §2).
# AC turno-lifecycle/Canal-default (mail sin indicar).
# AC turno-lifecycle/Post-v1-nulas (pago/lista NULL sin lógica).
# AC turno-lifecycle/Canal-futuro-rechazado (whatsapp viola enum v1).
"""

from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy

from tests.conftest import mk_paciente, mk_profesional, mk_turno, unique_token

BASE = datetime(2026, 10, 23, 13, 0, tzinfo=UTC)


def test_crear_reservado_online_con_token_persiste(db_session):
    """# AC turno-lifecycle/Crear-reservado-online: fila válida recuperable."""
    from app.models.turno import TurnoEstado, TurnoOrigen

    prof = mk_profesional(db_session)
    pac = mk_paciente(db_session)
    turno = mk_turno(
        db_session,
        prof.id,
        pac.id,
        inicio=BASE,
        fin=BASE + timedelta(minutes=30),
        estado=TurnoEstado.reservado,
        origen=TurnoOrigen.online,
    )
    assert turno.created_at is not None
    fila = db_session.execute(
        sqlalchemy.text("SELECT id FROM turno WHERE token_cancelacion = :token"),
        {"token": str(turno.token_cancelacion)},
    ).one()
    assert str(fila.id) == str(turno.id)


def test_token_duplicado_rechazado(db_session):
    """# AC turno-lifecycle/Token-duplicado-o-nulo: mismo token 2× → UNIQUE."""
    prof = mk_profesional(db_session)
    pac = mk_paciente(db_session)
    token = unique_token()
    mk_turno(
        db_session,
        prof.id,
        pac.id,
        inicio=BASE,
        fin=BASE + timedelta(minutes=30),
        token_cancelacion=token,
    )
    with pytest.raises(sqlalchemy.exc.IntegrityError, match="ux_turno_token"):
        mk_turno(
            db_session,
            prof.id,
            pac.id,
            inicio=BASE + timedelta(hours=1),
            fin=BASE + timedelta(hours=1, minutes=30),
            token_cancelacion=token,
        )


def test_token_nulo_rechazado(db_session):
    """# AC turno-lifecycle/Token-duplicado-o-nulo: token NULL → NOT NULL."""
    prof = mk_profesional(db_session)
    pac = mk_paciente(db_session)
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        mk_turno(
            db_session,
            prof.id,
            pac.id,
            inicio=BASE,
            fin=BASE + timedelta(minutes=30),
            token_cancelacion=None,
        )


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("estado", "en_espera"),
        ("origen", "whatsapp"),
        ("canal_recordatorio", "whatsapp"),
    ],
    ids=["estado", "origen", "canal-futuro"],
)
def test_vocabulario_fuera_de_enum_rechazado(db_session, campo, valor):
    """# AC turno-lifecycle/Estado-origen-enum + Canal-futuro: enum v1 cierra."""
    from app.models.turno import Turno

    prof = mk_profesional(db_session)
    pac = mk_paciente(db_session)
    atributos = {
        "profesional_id": prof.id,
        "paciente_id": pac.id,
        "inicio": BASE,
        "fin": BASE + timedelta(minutes=30),
        "duracion_min": 30,
        "origen": "online",
        "token_cancelacion": unique_token(),
    }
    atributos[campo] = valor
    # El enum nativo PG rechaza el valor (`InvalidTextRepresentation` → DataError).
    with pytest.raises(sqlalchemy.exc.DataError, match=valor):
        db_session.add(Turno(**atributos))
        db_session.flush()


@pytest.mark.parametrize(
    ("inicio", "fin"),
    [
        (BASE + timedelta(minutes=30), BASE),
        (BASE, BASE),
    ],
    ids=["fin-anterior", "duracion-cero"],
)
def test_rango_invalido_rechazado(db_session, inicio, fin):
    """# AC turno-lifecycle/Fin-mayor-inicio + Duracion-cero: fin > inicio."""
    prof = mk_profesional(db_session)
    pac = mk_paciente(db_session)
    with pytest.raises(sqlalchemy.exc.IntegrityError, match="ck_turno_fin_gt_inicio"):
        mk_turno(db_session, prof.id, pac.id, inicio=inicio, fin=fin)


def test_duracion_inconsistente_rechazada(db_session):
    """# AC turno-lifecycle/Duracion-inconsistente: 10:00–10:30 ≠ 45 min."""
    prof = mk_profesional(db_session)
    pac = mk_paciente(db_session)
    with pytest.raises(sqlalchemy.exc.IntegrityError, match="ck_turno_duracion_min"):
        mk_turno(
            db_session,
            prof.id,
            pac.id,
            inicio=BASE,
            fin=BASE + timedelta(minutes=30),
            duracion_min=45,
        )


@pytest.mark.parametrize("duracion", [15, 45], ids=["por-debajo", "por-encima"])
def test_duracion_desviada_ambos_lados_rechazada(db_session, duracion):
    """Mutación `=`→`>=`/`<=` en ck_turno_duracion_min: ambos lados mueren."""
    prof = mk_profesional(db_session)
    pac = mk_paciente(db_session)
    with pytest.raises(sqlalchemy.exc.IntegrityError, match="ck_turno_duracion_min"):
        mk_turno(
            db_session,
            prof.id,
            pac.id,
            inicio=BASE + timedelta(hours=2),
            fin=BASE + timedelta(hours=2, minutes=30),
            duracion_min=duracion,
        )


def test_duracion_consistente_acepta_bordes(db_session):
    """Triangulación: 1 min exacto (duracion 1) SÍ persiste."""
    prof = mk_profesional(db_session)
    pac = mk_paciente(db_session)
    turno = mk_turno(
        db_session,
        prof.id,
        pac.id,
        inicio=BASE,
        fin=BASE + timedelta(minutes=1),
    )
    assert turno.duracion_min == 1


def test_canal_default_mail_y_post_v1_nulas(db_session):
    """# AC turno-lifecycle/Canal-default + Post-v1-nulas: mail, pago/lista NULL."""
    from app.models.turno import CanalRecordatorio

    prof = mk_profesional(db_session)
    pac = mk_paciente(db_session)
    turno = mk_turno(
        db_session, prof.id, pac.id, inicio=BASE, fin=BASE + timedelta(minutes=30)
    )
    db_session.refresh(turno, ["canal_recordatorio", "pago_estado"])
    assert turno.canal_recordatorio == CanalRecordatorio.mail
    assert turno.pago_estado is None
    assert turno.lista_espera_pos is None
