"""Panel staff de notificaciones fallidas (capa: API + DB real).

# AC notificaciones-mail/Panel-staff (keyset por inicio DESC, RBAC, 400 por
# campo, sin secretos).
"""

import base64
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.models.usuario_staff import StaffRol
from tests.conftest import mk_paciente, mk_profesional, mk_turno
from tests.test_auth_login import mk_staff

BASE = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
CANCEL_URL = "https://turnos.ficticio.test/cancelar?token="


@pytest.fixture
def client(db_session):
    """TestClient https contra PG real con rollback + throttle limpio."""
    from app.core import ratelimit
    from app.db.session import get_db
    from app.main import app

    ratelimit.reset()
    original = ratelimit.LOGIN_LIMIT
    ratelimit.LOGIN_LIMIT = 1000

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app, base_url="https://testserver") as c:
        yield c
    app.dependency_overrides.clear()
    ratelimit.LOGIN_LIMIT = original


@pytest.fixture
def staff(db_session):
    """Sesiones ficticias de recepción y odontólogo."""
    mk_staff(db_session, "recepcion@ficticio.test", "password-ficticia-1")
    mk_staff(
        db_session,
        "odonto@ficticio.test",
        "password-ficticia-1",
        rol=StaffRol.odontologo,
    )


def _login(client, email):
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "password-ficticia-1"},
    )
    assert response.status_code == 200


def _fallida(
    db_session,
    *,
    inicio: datetime,
    error: str | None = "smtp: timeout",
    estado: str = "fallida",
    tipo: str = "confirmacion",
    intentos: int = 3,
):
    from app.models.notificacion import NotifEstado, Notificacion, NotifTipo

    prof = mk_profesional(db_session)
    pac = mk_paciente(db_session)
    turno = mk_turno(
        db_session,
        prof.id,
        pac.id,
        inicio=inicio,
        fin=inicio + timedelta(minutes=30),
    )
    notif = Notificacion(
        turno_id=turno.id,
        tipo=NotifTipo(tipo),
        estado=NotifEstado(estado),
        intentos=intentos,
        error=error,
        payload={
            "turno_id": str(turno.id),
            "tipo": tipo,
            "enviar_en": (inicio - timedelta(hours=1)).isoformat(),
            "paciente_nombre": "Paciente Ficticio",
            "paciente_email": "paciente@ficticio.test",
            "profesional_nombre": "Odontologa Ficticia",
            "inicio": inicio.isoformat(),
            "fin": (inicio + timedelta(minutes=30)).isoformat(),
            "duracion_min": 30,
            "token_cancelacion": str(turno.token_cancelacion),
            "cancel_url": CANCEL_URL + str(turno.token_cancelacion),
        },
    )
    db_session.add(notif)
    db_session.flush()
    return notif


def _cursor(inicio: datetime, notif_id) -> str:
    raw = f"{inicio.isoformat()}|{notif_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


# --- 7.1 Query y cursor ----------------------------------------------------


def test_fallidas_query_campo_extra_400(client, db_session, staff):
    """Duro 1: query desconocida → 400 por `orden` y sin items."""
    _login(client, "recepcion@ficticio.test")

    response = client.get("/api/notificaciones/fallidas?orden=asc")

    assert response.status_code == 400
    detalle = response.json()["detail"]
    assert any(d["campo"] == "orden" for d in detalle)
    assert "items" not in response.json()


def test_cursor_invalido_400(client, db_session, staff):
    """D-9: cursor que no decodifica → 400 por `cursor`."""
    _login(client, "recepcion@ficticio.test")

    response = client.get(
        "/api/notificaciones/fallidas", params={"cursor": "no-es-un-cursor"}
    )

    assert response.status_code == 400
    detalle = response.json()["detail"]
    assert any(d["campo"] == "cursor" for d in detalle)


def test_cursor_codec_ida_y_vuelta():
    """D-9: el cursor opaco decodifica exactamente `(inicio, id)`."""
    from uuid import uuid4

    from app.modules.notificaciones.service import (
        codificar_cursor,
        decodificar_cursor,
    )

    inicio = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
    notif_id = uuid4()

    cursor = codificar_cursor(inicio, notif_id)

    assert "=" not in cursor
    decodificado_inicio, decodificado_id = decodificar_cursor(cursor)
    assert decodificado_inicio == inicio
    assert decodificado_id == notif_id


@pytest.mark.parametrize("limit", [0, 201], ids=["cero", "excede-tope"])
def test_fallidas_limit_fuera_de_rango_400(client, db_session, staff, limit):
    """D-9: `limit` fuera de 1–200 → 400 por `limit`."""
    _login(client, "recepcion@ficticio.test")

    response = client.get(
        "/api/notificaciones/fallidas", params={"limit": limit}
    )

    assert response.status_code == 400
    assert any(d["campo"] == "limit" for d in response.json()["detail"])


# --- 7.2 Consulta keyset ---------------------------------------------------


def test_fallidas_lista_solo_fallos_smtp(client, db_session, staff):
    """D-9: excluye descartes `turno_cancelado`; lista solo fallos reales."""
    _fallida(db_session, inicio=datetime(2026, 10, 21, 12, 0, tzinfo=UTC))
    _fallida(
        db_session,
        inicio=datetime(2026, 10, 21, 13, 0, tzinfo=UTC),
        error="payload_incompleto: falta paciente_email",
    )
    _fallida(
        db_session,
        inicio=datetime(2026, 10, 21, 14, 0, tzinfo=UTC),
        error="turno_cancelado: cancelado",
        tipo="recordatorio_24h",
    )
    _login(client, "recepcion@ficticio.test")

    response = client.get("/api/notificaciones/fallidas")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert all(not i["error"].startswith("turno_cancelado") for i in items)


def test_fallidas_orden_por_inicio_descendente(client, db_session, staff):
    """D-9: orden operativo `t.inicio DESC, n.id DESC`."""
    _fallida(db_session, inicio=datetime(2026, 10, 21, 10, 0, tzinfo=UTC))
    _fallida(db_session, inicio=datetime(2026, 10, 21, 12, 0, tzinfo=UTC))
    _fallida(db_session, inicio=datetime(2026, 10, 21, 11, 0, tzinfo=UTC))
    _login(client, "recepcion@ficticio.test")

    items = client.get("/api/notificaciones/fallidas").json()["items"]

    inicios = [datetime.fromisoformat(i["inicio"]) for i in items]
    assert inicios == [
        datetime(2026, 10, 21, 12, 0, tzinfo=UTC),
        datetime(2026, 10, 21, 11, 0, tzinfo=UTC),
        datetime(2026, 10, 21, 10, 0, tzinfo=UTC),
    ]


def test_fallidas_keyset_devuelve_next_cursor(client, db_session, staff):
    """D-9: `limit+1` calcula `next_cursor`; el cursor devuelve el resto."""
    _fallida(db_session, inicio=datetime(2026, 10, 21, 10, 0, tzinfo=UTC))
    _fallida(db_session, inicio=datetime(2026, 10, 21, 11, 0, tzinfo=UTC))
    _fallida(db_session, inicio=datetime(2026, 10, 21, 12, 0, tzinfo=UTC))
    _login(client, "recepcion@ficticio.test")

    primera = client.get(
        "/api/notificaciones/fallidas", params={"limit": 2}
    ).json()
    assert len(primera["items"]) == 2
    assert primera["next_cursor"] is not None

    segunda = client.get(
        "/api/notificaciones/fallidas",
        params={"limit": 2, "cursor": primera["next_cursor"]},
    ).json()
    assert len(segunda["items"]) == 1
    assert segunda["next_cursor"] is None
    assert datetime.fromisoformat(segunda["items"][0]["inicio"]) == datetime(
        2026, 10, 21, 10, 0, tzinfo=UTC
    )


# --- 7.3 RBAC --------------------------------------------------------------


def test_fallidas_recepcion_200(client, db_session, staff):
    """D-9: recepción autenticada lista fallidas con `200`."""
    _fallida(db_session, inicio=datetime(2026, 10, 21, 12, 0, tzinfo=UTC))
    _login(client, "recepcion@ficticio.test")

    response = client.get("/api/notificaciones/fallidas")

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1


def test_fallidas_odontologo_403(client, db_session, staff):
    """D-9: odontólogo → 403 genérico sin datos."""
    _fallida(db_session, inicio=datetime(2026, 10, 21, 12, 0, tzinfo=UTC))
    _login(client, "odonto@ficticio.test")

    response = client.get("/api/notificaciones/fallidas")

    assert response.status_code == 403
    assert "items" not in response.json()


def test_fallidas_sin_sesion_401(client, db_session, staff):
    """D-9: sin cookie de sesión → 401 genérico."""
    response = client.get("/api/notificaciones/fallidas")

    assert response.status_code == 401


# --- 7.4 Sin secretos y contrato -------------------------------------------


def test_fallidas_no_expone_secretos(client, db_session, staff):
    """Duro 10: solo los campos de D-9; nunca `SMTP_PASS` ni PII extra."""
    import os

    _fallida(db_session, inicio=datetime(2026, 10, 21, 12, 0, tzinfo=UTC))
    _login(client, "recepcion@ficticio.test")

    response = client.get("/api/notificaciones/fallidas")

    assert response.status_code == 200
    items = response.json()["items"]
    assert set(items[0]) == {
        "id",
        "turno_id",
        "tipo",
        "intentos",
        "error",
        "enviar_en",
        "paciente_nombre",
        "paciente_email",
        "inicio",
        "fin",
    }
    assert os.environ["SMTP_PASS"] not in response.text
    for prohibido in ("payload", "dni", "telefono", "obra_social", "password"):
        assert prohibido not in response.text.lower()


def test_openapi_incluye_endpoint_fallidas():
    """Contrato: el endpoint del panel aparece documentado en OpenAPI."""
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/api/notificaciones/fallidas" in paths
    assert "get" in paths["/api/notificaciones/fallidas"]


def test_panel_fallidas_excluye_reprogramadas(client, db_session, staff):
    """C-07 D-10: los descartes por reprogramación no son fallos del panel."""
    smtp = _fallida(db_session, inicio=BASE + timedelta(hours=1))
    reprogramada = _fallida(
        db_session,
        inicio=BASE + timedelta(hours=2),
        error="turno_reprogramado: inicio movido",
    )
    _login(client, "recepcion@ficticio.test")

    response = client.get("/api/notificaciones/fallidas")

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert str(smtp.id) in ids
    assert str(reprogramada.id) not in ids
