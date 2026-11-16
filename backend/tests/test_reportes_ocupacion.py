"""Reporte de ocupación: schemas y API (capa: unit/schemas + api/DB real).

# AC reportes-ocupacion R1-R5 (tabla, métricas, rango/TZ, sin export, alcance).
"""

import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.exceptions import HTTPException
from fastapi.testclient import TestClient

from app.modules.agenda.public import parse_query_or_400


def _query(raw):
    from app.modules.reportes.schemas import ReporteOcupacionQuery

    with pytest.raises(HTTPException) as exc:
        parse_query_or_400(ReporteOcupacionQuery, raw)
    assert exc.value.status_code == 400
    return exc.value.detail


def _campos(detalle):
    return {d["campo"] for d in detalle}


# --- §1.7 query del reporte ---------------------------------------------


def test_reporte_query_rango_invertido_400():
    """# AC RE-R3: `desde > hasta` → 400 en `hasta`."""
    detalle = _query({"desde": "2026-11-10", "hasta": "2026-11-01"})
    assert _campos(detalle) == {"hasta"}


def test_reporte_query_rango_367_400():
    """# AC RE-R3: 367 días inclusivos → 400 en `hasta`."""
    detalle = _query({"desde": "2026-01-01", "hasta": "2027-01-02"})
    assert _campos(detalle) == {"hasta"}


def test_reporte_query_rango_366_200():
    """# AC RE-R3: 366 días inclusivos es el tope aceptado."""
    from app.modules.reportes.schemas import ReporteOcupacionQuery

    data = ReporteOcupacionQuery(desde="2026-01-01", hasta="2027-01-01")
    assert (data.hasta - data.desde).days + 1 == 366


@pytest.mark.parametrize(
    "raw",
    [
        {"hasta": "2026-11-08"},
        {"desde": "2026-11-02"},
        {"desde": "11/2026", "hasta": "2026-11-08"},
        {"desde": "2026-11-02", "hasta": "11/2026"},
    ],
)
def test_reporte_query_fechas_invalidas_400(raw):
    """# AC RE-R3: fechas faltantes o mal formadas → 400 por campo."""
    detalle = _query(raw)
    assert _campos(detalle) & {"desde", "hasta"}


def test_reporte_query_param_desconocido_400():
    """# AC RE-R3: parámetro extra (`orden`) → 400 en ese campo."""
    detalle = _query({"desde": "2026-11-02", "hasta": "2026-11-08", "orden": "asc"})
    assert "orden" in _campos(detalle)


def test_reporte_query_profesional_id_invalido_400():
    """# AC RE-R1: `profesional_id` malformado → 400 en ese campo."""
    detalle = _query(
        {
            "desde": "2026-11-02",
            "hasta": "2026-11-08",
            "profesional_id": "no-es-uuid",
        }
    )
    assert _campos(detalle) == {"profesional_id"}


def test_reporte_out_estructura_sin_export():
    """# AC RE-R1/R4: la salida es tabla JSON (items + totales), sin export."""
    from app.modules.reportes.schemas import ReporteOcupacionOut

    assert set(ReporteOcupacionOut.model_fields) == {
        "desde",
        "hasta",
        "zona",
        "items",
        "totales",
    }
    assert "format" not in ReporteOcupacionOut.model_fields


# --- §8/§9/§10: agregación, capacidad y contrato HTTP (DB real/API) ------


TZ = ZoneInfo("America/Argentina/Buenos_Aires")
# 2026-10-19 es lunes (`dia_semana=0`).
LUNES = date(2026, 10, 19)


@pytest.fixture
def client(db_session):
    """TestClient https contra PG real con rollback + throttle limpio."""
    from app.core import ratelimit
    from app.db.session import get_db
    from app.main import app

    ratelimit.reset()
    ratelimit.reset_public()
    original = ratelimit.LOGIN_LIMIT
    ratelimit.LOGIN_LIMIT = 1000

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app, base_url="https://testserver") as c:
        yield c
    app.dependency_overrides.clear()
    ratelimit.LOGIN_LIMIT = original


def _staff(db_session, email="admin@cattaneo.test", rol=None):
    from app.models.usuario_staff import StaffRol
    from tests.test_auth_login import mk_staff

    return mk_staff(
        db_session,
        email,
        "password-ficticia-1",
        rol=rol or StaffRol.admin,
    )


def _login(client, email="admin@cattaneo.test"):
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "password-ficticia-1"},
    )
    assert response.status_code == 200


def _pac(db_session):
    from tests.conftest import mk_paciente

    return mk_paciente(db_session)


def _prof_con_ventana(
    db_session,
    *,
    dias=(0,),
    desde=(9, 0),
    hasta=(12, 0),
    duracion=30,
    activo=True,
    vigente_desde=date(2026, 1, 1),
    vigente_hasta=date(2026, 12, 31),
):
    """Profesional ficticio con una ventana semanal explícita."""
    from app.models.disponibilidad import Disponibilidad
    from tests.conftest import mk_profesional

    prof = mk_profesional(db_session, duracion_default_min=duracion, activo=activo)
    for dia in dias:
        db_session.add(
            Disponibilidad(
                profesional_id=prof.id,
                dia_semana=dia,
                hora_desde=time(*desde),
                hora_hasta=time(*hasta),
                vigente_desde=vigente_desde,
                vigente_hasta=vigente_hasta,
            )
        )
    db_session.flush()
    return prof


def _turno(db_session, prof, pac, dia, hora, minuto, estado, duracion=30):
    from tests.conftest import mk_turno

    inicio = datetime(dia.year, dia.month, dia.day, hora, minuto, tzinfo=TZ)
    return mk_turno(
        db_session,
        prof.id,
        pac.id,
        inicio=inicio,
        fin=inicio + timedelta(minutes=duracion),
        estado=estado,
    )


def _params(desde=LUNES, hasta=LUNES, **extra):
    return {"desde": desde.isoformat(), "hasta": hasta.isoformat(), **extra}


def _reporte(client, desde=LUNES, hasta=LUNES, **extra):
    response = client.get(
        "/api/reportes/ocupacion", params=_params(desde, hasta, **extra)
    )
    assert response.status_code == 200, response.text
    return response.json()


def _fila(body, prof):
    """Fila única del profesional (falla si aparece repetida)."""
    filas = [i for i in body["items"] if i["profesional"]["id"] == str(prof.id)]
    assert len(filas) == 1
    return filas[0]


def test_reporte_ocupacion_filas_por_profesional_y_estados(client, db_session):
    """# AC RE-R1: una fila por profesional con contadores por estado."""
    from app.models.turno import TurnoEstado

    prof1 = _prof_con_ventana(db_session)
    prof2 = _prof_con_ventana(db_session)
    pac = _pac(db_session)
    for hora, minuto, estado in (
        (9, 0, TurnoEstado.reservado),
        (9, 30, TurnoEstado.confirmado),
        (10, 0, TurnoEstado.atendido),
        (10, 30, TurnoEstado.ausente),
        (11, 0, TurnoEstado.cancelado),
    ):
        _turno(db_session, prof1, pac, LUNES, hora, minuto, estado)
    db_session.flush()
    _staff(db_session)
    _login(client)

    body = _reporte(client)
    assert body["desde"] == LUNES.isoformat()
    assert body["zona"] == "America/Argentina/Buenos_Aires"
    fila1 = _fila(body, prof1)
    assert fila1["turnos"] == 5
    assert fila1["atendidos"] == 1
    assert fila1["ausentes"] == 1
    assert fila1["cancelados"] == 1
    assert fila1["pendientes"] == 2
    fila2 = _fila(body, prof2)
    assert fila2["turnos"] == 0
    assert fila2["pendientes"] == 0


def test_reporte_ocupacion_porcentaje_y_minutos(client, db_session):
    """# AC RE-R2: 180' ofrecibles, 90' ocupados (cancelado libera) → 50.0."""
    from app.models.turno import TurnoEstado

    prof = _prof_con_ventana(db_session)
    pac = _pac(db_session)
    for hora, minuto, estado in (
        (9, 0, TurnoEstado.atendido),
        (9, 30, TurnoEstado.ausente),
        (10, 0, TurnoEstado.cancelado),
        (10, 30, TurnoEstado.confirmado),
    ):
        _turno(db_session, prof, pac, LUNES, hora, minuto, estado)
    db_session.flush()
    _staff(db_session)
    _login(client)

    fila = _fila(_reporte(client), prof)
    assert fila["minutos_disponibles"] == 180
    assert fila["minutos_ocupados"] == 90
    assert fila["porcentaje_ocupacion"] == 50.0


def test_reporte_ocupacion_cancelado_no_ocupa_ausente_si(client, db_session):
    """# AC RE-R2: cancelado cuenta pero no ocupa; ausente ocupa minutos."""
    from app.models.turno import TurnoEstado

    prof = _prof_con_ventana(db_session)
    pac = _pac(db_session)
    _turno(db_session, prof, pac, LUNES, 9, 0, TurnoEstado.ausente)
    _turno(db_session, prof, pac, LUNES, 9, 30, TurnoEstado.cancelado)
    db_session.flush()
    _staff(db_session)
    _login(client)

    fila = _fila(_reporte(client), prof)
    assert fila["turnos"] == 2
    assert fila["ausentes"] == 1
    assert fila["cancelados"] == 1
    assert fila["minutos_ocupados"] == 30


def test_reporte_ocupacion_totales_cuadran(client, db_session):
    """# AC RE-R1: `totales` es la suma de las filas y recalcula el %."""
    from app.models.turno import TurnoEstado

    prof1 = _prof_con_ventana(db_session)
    prof2 = _prof_con_ventana(db_session)
    pac = _pac(db_session)
    _turno(db_session, prof1, pac, LUNES, 9, 0, TurnoEstado.atendido)
    _turno(db_session, prof1, pac, LUNES, 9, 30, TurnoEstado.atendido)
    _turno(db_session, prof1, pac, LUNES, 10, 0, TurnoEstado.cancelado)
    _turno(db_session, prof2, pac, LUNES, 9, 0, TurnoEstado.ausente)
    db_session.flush()
    _staff(db_session)
    _login(client)

    body = _reporte(client)
    totales = body["totales"]
    for campo in (
        "turnos",
        "atendidos",
        "ausentes",
        "cancelados",
        "pendientes",
        "minutos_ocupados",
        "minutos_disponibles",
    ):
        assert totales[campo] == sum(i[campo] for i in body["items"])
    assert totales["porcentaje_ocupacion"] == round(
        totales["minutos_ocupados"] / totales["minutos_disponibles"] * 100, 1
    )
    assert _fila(body, prof1)["minutos_ocupados"] == 60
    assert _fila(body, prof2)["minutos_ocupados"] == 30


def test_reporte_ocupacion_profesional_sin_turnos_fila_ceros(client, db_session):
    """# AC RE-R1: activo sin turnos y con capacidad → ceros y 0.0."""
    prof = _prof_con_ventana(db_session)
    db_session.flush()
    _staff(db_session)
    _login(client)

    fila = _fila(_reporte(client), prof)
    assert fila["turnos"] == 0
    assert fila["atendidos"] == 0
    assert fila["ausentes"] == 0
    assert fila["cancelados"] == 0
    assert fila["pendientes"] == 0
    assert fila["minutos_ocupados"] == 0
    assert fila["minutos_disponibles"] == 180
    assert fila["porcentaje_ocupacion"] == 0.0


def test_reporte_ocupacion_profesional_id_sin_turnos_sin_capacidad_null(
    client, db_session
):
    """# AC RE-R1: filtrado sin turnos ni disponibilidad → fila y `null`."""
    prof = _prof_con_ventana(db_session, dias=())
    db_session.flush()
    _staff(db_session)
    _login(client)

    body = _reporte(client, profesional_id=str(prof.id))
    assert len(body["items"]) == 1
    fila = body["items"][0]
    assert fila["profesional"]["id"] == str(prof.id)
    assert fila["minutos_disponibles"] == 0
    assert fila["porcentaje_ocupacion"] is None


def test_reporte_ocupacion_inactivo_con_historial_aparece(client, db_session):
    """# AC RE-R1: inactivo con turnos históricos sigue en el reporte."""
    from app.models.turno import TurnoEstado

    prof = _prof_con_ventana(db_session, activo=False)
    pac = _pac(db_session)
    _turno(db_session, prof, pac, LUNES, 9, 0, TurnoEstado.atendido)
    db_session.flush()
    _staff(db_session)
    _login(client)

    fila = _fila(_reporte(client), prof)
    assert fila["profesional"]["activo"] is False
    assert fila["turnos"] == 1
    assert fila["atendidos"] == 1


def test_reporte_ocupacion_filtro_profesional_id(client, db_session):
    """# AC RE-R1: el filtro acota el reporte a esa única fila."""
    from app.models.turno import TurnoEstado
    from tests.conftest import mk_profesional

    prof1 = _prof_con_ventana(db_session)
    prof2 = mk_profesional(db_session)
    pac = _pac(db_session)
    _turno(db_session, prof1, pac, LUNES, 9, 0, TurnoEstado.atendido)
    _turno(db_session, prof2, pac, LUNES, 9, 0, TurnoEstado.atendido)
    db_session.flush()
    _staff(db_session)
    _login(client)

    body = _reporte(client, profesional_id=str(prof1.id))
    assert len(body["items"]) == 1
    assert body["items"][0]["profesional"]["id"] == str(prof1.id)


def test_reporte_ocupacion_profesional_id_inexistente_vacio(client, db_session):
    """# AC RE-R1: UUID inexistente → 200, `items=[]` y totales en cero."""
    _staff(db_session)
    _login(client)
    body = _reporte(client, profesional_id=str(uuid.uuid4()))
    assert body["items"] == []
    assert body["totales"]["turnos"] == 0
    assert body["totales"]["minutos_disponibles"] == 0
    assert body["totales"]["porcentaje_ocupacion"] is None


def test_reporte_capacidad_usa_configuracion_vigente_al_consultar(client, db_session):
    """# AC RE-R2: la capacidad usa duración/disponibilidad actuales."""
    from app.models.disponibilidad import Disponibilidad
    from app.models.turno import TurnoEstado

    prof = _prof_con_ventana(db_session, desde=(9, 0), hasta=(10, 0))
    pac = _pac(db_session)
    _turno(db_session, prof, pac, LUNES, 9, 0, TurnoEstado.atendido)
    db_session.flush()

    prof.duracion_default_min = 60
    ventana = (
        db_session.query(Disponibilidad)
        .filter(Disponibilidad.profesional_id == prof.id)
        .one()
    )
    ventana.hora_hasta = time(12, 0)
    db_session.flush()
    _staff(db_session)
    _login(client)

    fila = _fila(_reporte(client), prof)
    assert fila["minutos_disponibles"] == 180


def test_reporte_rango_borde_dia_local(client, db_session):
    """# AC RE-R3: 23:30 del `hasta` cuenta; 00:00 local del día siguiente no."""
    from app.models.turno import TurnoEstado

    prof = _prof_con_ventana(db_session, dias=())
    pac = _pac(db_session)
    _turno(db_session, prof, pac, LUNES, 23, 30, TurnoEstado.atendido)
    _turno(db_session, prof, pac, date(2026, 10, 20), 0, 0, TurnoEstado.atendido)
    db_session.flush()
    _staff(db_session)
    _login(client)

    assert _fila(_reporte(client), prof)["turnos"] == 1


def test_reporte_turno_utc_cuenta_en_dia_local(client, db_session):
    """# AC RE-R3: 22:00 local (UTC del día siguiente) se imputa al local."""
    from app.models.turno import TurnoEstado

    prof = _prof_con_ventana(db_session, dias=())
    pac = _pac(db_session)
    _turno(db_session, prof, pac, LUNES, 22, 0, TurnoEstado.atendido)
    db_session.flush()
    _staff(db_session)
    _login(client)

    assert _fila(_reporte(client), prof)["turnos"] == 1
    manana = date(2026, 10, 20)
    assert _fila(_reporte(client, desde=manana, hasta=manana), prof)["turnos"] == 0


def test_reporte_porcentaje_null_sin_capacidad(client, db_session):
    """# AC RE-R2: activo sin disponibilidad vigente → 0' y `null`."""
    prof = _prof_con_ventana(db_session, dias=())
    db_session.flush()
    _staff(db_session)
    _login(client)

    fila = _fila(_reporte(client), prof)
    assert fila["minutos_disponibles"] == 0
    assert fila["porcentaje_ocupacion"] is None


def test_reporte_porcentaje_supera_100_fuera_ventana(client, db_session):
    """# AC RE-R2: turnos forzados fuera de la ventana no se recortan."""
    from app.models.turno import TurnoEstado

    prof_literal = _prof_con_ventana(db_session, desde=(9, 0), hasta=(12, 0))
    prof_over = _prof_con_ventana(db_session, desde=(9, 0), hasta=(12, 0))
    pac = _pac(db_session)
    _turno(db_session, prof_literal, pac, LUNES, 12, 0, TurnoEstado.reservado)
    _turno(
        db_session,
        prof_over,
        pac,
        LUNES,
        12,
        0,
        TurnoEstado.reservado,
        duracion=240,
    )
    db_session.flush()
    _staff(db_session)
    _login(client)

    body = _reporte(client)
    literal = _fila(body, prof_literal)
    assert literal["minutos_ocupados"] == 30
    assert literal["porcentaje_ocupacion"] == round(30 / 180 * 100, 1)
    over = _fila(body, prof_over)
    assert over["porcentaje_ocupacion"] > 100.0
    assert over["porcentaje_ocupacion"] == round(240 / 180 * 100, 1)


def test_reporte_rango_366_200_y_367_400_campo_hasta(client, db_session):
    """# AC RE-R3: tope inclusivo 366 días; 367 → 400 en `hasta`."""
    _staff(db_session)
    _login(client)
    ok = client.get(
        "/api/reportes/ocupacion",
        params={"desde": "2026-01-01", "hasta": "2027-01-01"},
    )
    assert ok.status_code == 200
    excedido = client.get(
        "/api/reportes/ocupacion",
        params={"desde": "2026-01-01", "hasta": "2027-01-02"},
    )
    assert excedido.status_code == 400
    assert {d["campo"] for d in excedido.json()["detail"]} == {"hasta"}


def test_reporte_rango_invertido_400_campo_hasta(client, db_session):
    """# AC RE-R3: rango invertido → 400 en `hasta` (nunca `query`)."""
    _staff(db_session)
    _login(client)
    response = client.get(
        "/api/reportes/ocupacion",
        params={"desde": "2026-11-10", "hasta": "2026-11-01"},
    )
    assert response.status_code == 400
    assert {d["campo"] for d in response.json()["detail"]} == {"hasta"}


def test_reporte_profesional_id_malformado_400(client, db_session):
    """# AC RE-R1: `profesional_id` malformado → 400 en ese campo."""
    _staff(db_session)
    _login(client)
    response = client.get(
        "/api/reportes/ocupacion",
        params=_params(profesional_id="no-es-uuid"),
    )
    assert response.status_code == 400
    assert {d["campo"] for d in response.json()["detail"]} == {"profesional_id"}


@pytest.mark.parametrize("formato", ["csv", "xlsx"])
def test_reporte_format_csv_400(client, db_session, formato):
    """# AC RE-R4: cualquier `format` de export → 400 en `format` (PB-06)."""
    _staff(db_session)
    _login(client)
    response = client.get("/api/reportes/ocupacion", params=_params(format=formato))
    assert response.status_code == 400
    assert {d["campo"] for d in response.json()["detail"]} == {"format"}


def test_reporte_respuesta_json_sin_content_disposition(client, db_session):
    """# AC RE-R4: la respuesta es JSON de tabla, sin cabecera de adjunto."""
    _staff(db_session)
    _login(client)
    response = client.get("/api/reportes/ocupacion", params=_params())
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "content-disposition" not in response.headers


def test_reporte_query_extras_400(client, db_session):
    """# AC RE-R3: un parámetro desconocido → 400 en ese campo."""
    _staff(db_session)
    _login(client)
    response = client.get("/api/reportes/ocupacion", params=_params(orden="asc"))
    assert response.status_code == 400
    assert {d["campo"] for d in response.json()["detail"]} == {"orden"}


@pytest.mark.parametrize(
    "params",
    [
        {"hasta": "2026-11-08"},
        {"desde": "2026-11-02"},
        {"desde": "11/2026", "hasta": "2026-11-08"},
    ],
)
def test_reporte_fechas_faltantes_400(client, db_session, params):
    """# AC RE-R3: fechas faltantes/mal formadas → 400 por campo (HTTP)."""
    from app.models.usuario_staff import StaffRol

    _staff(db_session, rol=StaffRol.recepcion)
    _login(client)
    response = client.get("/api/reportes/ocupacion", params=params)
    assert response.status_code == 400
    assert response.json()["detail"]
