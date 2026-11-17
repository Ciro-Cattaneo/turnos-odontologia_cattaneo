"""Admin de usuarios staff: schemas y API (capa: unit/schemas + api/DB real).

# AC staff-auth R1-R5 (alta/edición/baja/listado/reactivación/RBAC).
"""

import threading
from uuid import uuid4

import pytest
from fastapi.exceptions import HTTPException
from fastapi.testclient import TestClient

from app.models.usuario_staff import StaffRol

PASSWORD = "password-ficticia-1"


def _detalle_body(model, body):
    from app.modules.turnos.schemas import parse_body_or_400

    with pytest.raises(HTTPException) as exc:
        parse_body_or_400(model, body)
    assert exc.value.status_code == 400
    return exc.value.detail


def _campos(detalle):
    return {d["campo"] for d in detalle}


def _body(**over):
    base = {
        "email": "recepcion.ficticia@cattaneo.test",
        "password": "password-ficticia-1",
        "rol": "recepcion",
    }
    base.update(over)
    return base


# --- §1.5 alta: invariante rol ↔ profesional_id + umbrales ---------------


def test_alta_usuario_odontologo_sin_profesional_400():
    """# AC SA-R1: `rol=odontologo` sin `profesional_id` → 400 en el campo."""
    from app.modules.usuarios_staff.schemas import UsuarioStaffCreate

    detalle = _detalle_body(UsuarioStaffCreate, _body(rol="odontologo"))
    assert "profesional_id" in _campos(detalle)


@pytest.mark.parametrize("rol", ["recepcion", "admin"])
def test_alta_usuario_recepcion_con_profesional_400(rol):
    """# AC SA-R1: `recepcion` no lleva vínculo → 400 en `profesional_id`."""
    from app.modules.usuarios_staff.schemas import UsuarioStaffCreate

    detalle = _detalle_body(
        UsuarioStaffCreate, _body(rol=rol, profesional_id=str(uuid4()))
    )
    assert "profesional_id" in _campos(detalle)


def test_alta_usuario_admin_con_profesional_400():
    """# AC SA-R1: `admin` no lleva vínculo → 400 en `profesional_id`."""
    from app.modules.usuarios_staff.schemas import UsuarioStaffCreate

    detalle = _detalle_body(
        UsuarioStaffCreate, _body(rol="admin", profesional_id=str(uuid4()))
    )
    assert "profesional_id" in _campos(detalle)


def test_alta_usuario_password_corta_400():
    """# AC SA-R1: password de 7 → 400 en `password`."""
    from app.modules.usuarios_staff.schemas import UsuarioStaffCreate

    detalle = _detalle_body(UsuarioStaffCreate, _body(password="1234567"))
    assert "password" in _campos(detalle)


def test_alta_usuario_email_invalido_400():
    """# AC SA-R1: email sin arroba → 400 en `email`."""
    from app.modules.usuarios_staff.schemas import UsuarioStaffCreate

    detalle = _detalle_body(UsuarioStaffCreate, _body(email="sin-arroba"))
    assert "email" in _campos(detalle)


def test_alta_usuario_campo_extra_400():
    """# AC SA-R1: clave extra → 400 en esa clave."""
    from app.modules.usuarios_staff.schemas import UsuarioStaffCreate

    detalle = _detalle_body(UsuarioStaffCreate, _body(telefono="123"))
    assert "telefono" in _campos(detalle)


@pytest.mark.parametrize("password", [8, 256])
def test_alta_usuario_password_8_y_256_201(password):
    """# AC SA-R1 borde: password de 8 y 256 → schema válido."""
    from app.modules.usuarios_staff.schemas import UsuarioStaffCreate

    data = UsuarioStaffCreate(**_body(password="p" * password))
    assert len(data.password) == password


@pytest.mark.parametrize("largo", [3, 320])
def test_alta_usuario_email_3_y_320_201(largo):
    """# AC SA-R1 borde: email de 3 y 320 → schema válido (D-16)."""
    from app.modules.usuarios_staff.schemas import UsuarioStaffCreate

    if largo == 3:
        email = "a@b"
    else:
        email = "a" * (largo - len("@cattaneo.test")) + "@cattaneo.test"
    data = UsuarioStaffCreate(**_body(email=email))
    assert len(data.email) == largo


# --- §1.6 edición: body vacío, email/password inmutables, invariante ------


def test_edicion_usuario_body_vacio_400():
    """# AC SA-R2: body `{}` → 400 en `body`."""
    from app.modules.usuarios_staff.schemas import UsuarioStaffUpdate

    detalle = _detalle_body(UsuarioStaffUpdate, {})
    assert "body" in _campos(detalle)


@pytest.mark.parametrize("campo", ["email", "password"])
def test_edicion_usuario_email_password_extra_400(campo):
    """# AC SA-R2: email/password no editables → 400 en ese campo."""
    from app.modules.usuarios_staff.schemas import UsuarioStaffUpdate

    detalle = _detalle_body(UsuarioStaffUpdate, {campo: "x"})
    assert campo in _campos(detalle)


def test_edicion_usuario_rol_recepcion_link_pendiente_400():
    """# AC SA-R2: `recepcion` con vínculo resultante → 400 en el campo."""
    from app.modules.usuarios_staff.schemas import validar_vinculo_rol

    with pytest.raises(ValueError):
        validar_vinculo_rol(StaffRol.recepcion, uuid4())
    with pytest.raises(ValueError):
        validar_vinculo_rol(StaffRol.odontologo, None)
    assert validar_vinculo_rol(StaffRol.odontologo, uuid4()) is not None
    assert validar_vinculo_rol(StaffRol.admin, None) is None


def test_edicion_usuario_activo_tipo_invalido_400():
    """# AC SA-R2: `activo` no booleano → 400 en `activo`."""
    from app.modules.usuarios_staff.schemas import UsuarioStaffUpdate

    detalle = _detalle_body(UsuarioStaffUpdate, {"activo": "si"})
    assert "activo" in _campos(detalle)


def test_usuario_staff_out_sin_password_hash():
    """# AC SA-R1: la respuesta nunca expone `password_hash`."""
    from app.modules.usuarios_staff.schemas import UsuarioStaffOut

    assert set(UsuarioStaffOut.model_fields) == {
        "id",
        "email",
        "rol",
        "profesional_id",
        "activo",
    }


# --- Fixtures de API (PG real con rollback + throttle holgado) -------------


@pytest.fixture
def client(db_session, monkeypatch):
    """TestClient https contra PG real con rollback + rate-limit holgado."""
    from app.core import ratelimit
    from app.db.session import get_db
    from app.main import app

    monkeypatch.setattr(ratelimit, "LOGIN_LIMIT", 1000)
    ratelimit.reset()
    ratelimit.reset_public()

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app, base_url="https://testserver") as c:
        yield c
    app.dependency_overrides.clear()


def _staff(
    db_session, rol=StaffRol.recepcion, email=None, profesional_id=None, activo=True
):
    """Staff ficticio con password conocida."""
    from tests.test_auth_login import mk_staff

    return mk_staff(
        db_session,
        email or f"staff.{uuid4().hex[:10]}@cattaneo.test",
        PASSWORD,
        rol=rol,
        activo=activo,
        profesional_id=profesional_id,
    )


def _login(client, email, password=PASSWORD):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp


def _prof(db_session, activo=True, **kw):
    from tests.conftest import mk_profesional

    return mk_profesional(db_session, activo=activo, **kw)


def _aislar_admins(db_session):
    """Deja cero admins activos en la vista del test (rollback al final)."""
    from app.models.usuario_staff import UsuarioStaff

    db_session.query(UsuarioStaff).filter(
        UsuarioStaff.rol == StaffRol.admin,
        UsuarioStaff.activo.is_(True),
    ).update({"activo": False}, synchronize_session=False)
    db_session.commit()


def _creditos_422(resp):
    detalle = resp.json()["detail"]
    return {d["campo"] for d in detalle} if isinstance(detalle, list) else set()


# --- �5.1 alta: 201 sin exponer el hash -----------------------------------


def test_alta_usuario_recepcion_201_sin_hash(client, db_session):
    """# AC SA-R1 FELIZ: 201 con argon2id persistido y sin hash en la respuesta."""
    from app.models.usuario_staff import UsuarioStaff

    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    _login(client, admin.email)

    resp = client.post(
        "/api/usuarios-staff",
        json=_body(email="recepcion.nueva@cattaneo.test"),
    )
    assert resp.status_code == 201, resp.text
    cuerpo = resp.json()
    assert "password_hash" not in cuerpo
    assert cuerpo["email"] == "recepcion.nueva@cattaneo.test"
    assert cuerpo["rol"] == "recepcion"
    assert cuerpo["profesional_id"] is None
    assert cuerpo["activo"] is True

    fila = (
        db_session.query(UsuarioStaff)
        .filter(UsuarioStaff.email == "recepcion.nueva@cattaneo.test")
        .one()
    )
    assert fila.password_hash.startswith("$argon2id$")


# --- �5.2 alta de odont�logo vinculado -------------------------------------


def test_alta_usuario_odontologo_con_profesional_201(client, db_session):
    """# AC SA-R1 FELIZ: odont�logo con profesional activo persiste el v�nculo."""
    from app.models.usuario_staff import UsuarioStaff

    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    _login(client, admin.email)
    prof = _prof(db_session)
    db_session.commit()

    resp = client.post(
        "/api/usuarios-staff",
        json=_body(
            email="odonto.nuevo@cattaneo.test",
            rol="odontologo",
            profesional_id=str(prof.id),
        ),
    )
    assert resp.status_code == 201, resp.text
    fila = (
        db_session.query(UsuarioStaff)
        .filter(UsuarioStaff.email == "odonto.nuevo@cattaneo.test")
        .one()
    )
    assert fila.rol == StaffRol.odontologo
    assert fila.profesional_id == prof.id


@pytest.mark.parametrize("caso", ["inexistente", "inactivo"])
def test_alta_usuario_profesional_inexistente_o_inactivo_400(client, db_session, caso):
    """# AC SA-R1 ERROR: profesional inexistente o inactivo ? 400 por campo."""
    from app.models.usuario_staff import UsuarioStaff

    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    _login(client, admin.email)
    if caso == "inexistente":
        profesional_id = uuid4()
    else:
        prof = _prof(db_session, activo=False)
        profesional_id = prof.id
    db_session.commit()

    resp = client.post(
        "/api/usuarios-staff",
        json=_body(
            email="odonto.invalido@cattaneo.test",
            rol="odontologo",
            profesional_id=str(profesional_id),
        ),
    )
    assert resp.status_code == 400, resp.text
    assert "profesional_id" in {d["campo"] for d in resp.json()["detail"]}
    assert (
        db_session.query(UsuarioStaff)
        .filter(UsuarioStaff.email == "odonto.invalido@cattaneo.test")
        .count()
        == 0
    )


# --- �5.3 unicidad de email (409) ------------------------------------------


@pytest.mark.parametrize(
    "email",
    ["recepcion.ficticia@cattaneo.test", "RECEPCION.FICTICIA@CATTANEO.TEST"],
)
def test_alta_usuario_email_duplicado_409(client, db_session, email):
    """# AC SA-R4 ERROR: email tomado (case-insensitive) ? 409 email_duplicado."""
    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    _login(client, admin.email)
    primero = client.post("/api/usuarios-staff", json=_body())
    assert primero.status_code == 201, primero.text

    resp = client.post(
        "/api/usuarios-staff",
        json=_body(email=email, password="otra-password-ficticia"),
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["codigo"] == "email_duplicado"


def test_alta_usuario_email_inactivo_409(client, db_session):
    """# AC SA-R4 ERROR: el email de una fila inactiva sigue tomado."""
    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    _login(client, admin.email)
    _staff(
        db_session,
        StaffRol.recepcion,
        email="inactivo.tomado@cattaneo.test",
        activo=False,
    )
    db_session.commit()

    resp = client.post(
        "/api/usuarios-staff",
        json=_body(email="inactivo.tomado@cattaneo.test"),
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["codigo"] == "email_duplicado"


def test_alta_usuario_carrera_email_409(client, db_session, monkeypatch):
    """# AC SA-R4 ERROR: carrera de unicidad (IntegrityError) ? 409 de borde."""
    from app.modules.usuarios_staff import service

    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    _login(client, admin.email)
    client.post("/api/usuarios-staff", json=_body())
    db_session.commit()

    monkeypatch.setattr(service, "_existe_email", lambda db, email: False)
    resp = client.post(
        "/api/usuarios-staff",
        json=_body(email="RECEPCION.FICTICIA@cattaneo.test"),
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["codigo"] == "email_duplicado"


# --- �5.4 umbrales por HTTP -----------------------------------------------


@pytest.mark.parametrize("password", [8, 256])
def test_alta_usuario_password_8_y_256_http_201(client, db_session, password):
    """# AC SA-R1 BORDE: password de 8 y 256 ? 201 (D-16)."""
    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    _login(client, admin.email)
    resp = client.post(
        "/api/usuarios-staff",
        json=_body(
            email=f"pwd.{uuid4().hex[:8]}@cattaneo.test",
            password="p" * password,
        ),
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.parametrize("password", [7, 257])
def test_alta_usuario_password_7_y_257_400(client, db_session, password):
    """# AC SA-R1 ERROR: password de 7 y 257 ? 400 en `password`."""
    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    _login(client, admin.email)
    resp = client.post(
        "/api/usuarios-staff",
        json=_body(
            email=f"pwd.{uuid4().hex[:8]}@cattaneo.test",
            password="p" * password,
        ),
    )
    assert resp.status_code == 400, resp.text
    assert "password" in {d["campo"] for d in resp.json()["detail"]}


@pytest.mark.parametrize("largo", [3, 320])
def test_alta_usuario_email_3_y_320_http_201(client, db_session, largo):
    """# AC SA-R1 BORDE: email de 3 y 320 ? 201 (D-16)."""
    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    _login(client, admin.email)
    if largo == 3:
        email = "a@b"
    else:
        email = (
            f"{uuid4().hex}"
            + "a" * (largo - 32 - len("@cattaneo.test"))
            + "@cattaneo.test"
        )
    assert len(email) == largo
    resp = client.post("/api/usuarios-staff", json=_body(email=email))
    assert resp.status_code == 201, resp.text


@pytest.mark.parametrize(
    "email",
    [
        "ab",
        "a" * 309 + "@cattaneo.test",
    ],
)
def test_alta_usuario_email_2_y_321_400(client, db_session, email):
    """# AC SA-R1 ERROR: email de 2 y 321 ? 400 en `email`."""
    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    _login(client, admin.email)
    resp = client.post("/api/usuarios-staff", json=_body(email=email))
    assert resp.status_code == 400, resp.text
    assert "email" in {d["campo"] for d in resp.json()["detail"]}


# --- �5.5 edici�n de rol y v�nculo ----------------------------------------


def test_edicion_usuario_rol_y_link_200(client, db_session):
    """# AC SA-R2 FELIZ: recepci�n ? odont�logo con v�nculo persistido."""
    from app.models.usuario_staff import UsuarioStaff

    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    _login(client, admin.email)
    prof = _prof(db_session)
    usuario = _staff(db_session, StaffRol.recepcion)
    db_session.commit()

    resp = client.put(
        f"/api/usuarios-staff/{usuario.id}",
        json={"rol": "odontologo", "profesional_id": str(prof.id)},
    )
    assert resp.status_code == 200, resp.text
    fila = db_session.get(UsuarioStaff, usuario.id)
    db_session.refresh(fila)
    assert fila.rol == StaffRol.odontologo
    assert fila.profesional_id == prof.id


def test_edicion_usuario_invariante_inconsistente_400(client, db_session):
    """# AC SA-R2 ERROR: quitar el v�nculo sin cambiar de rol deja 400."""
    from app.models.usuario_staff import UsuarioStaff

    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    _login(client, admin.email)
    prof = _prof(db_session)
    usuario = _staff(db_session, StaffRol.odontologo, profesional_id=prof.id)
    db_session.commit()

    resp = client.put(
        f"/api/usuarios-staff/{usuario.id}",
        json={"profesional_id": None},
    )
    assert resp.status_code == 400, resp.text
    assert "profesional_id" in {d["campo"] for d in resp.json()["detail"]}
    fila = db_session.get(UsuarioStaff, usuario.id)
    db_session.refresh(fila)
    assert fila.profesional_id == prof.id


@pytest.mark.parametrize("metodo", ["put", "delete"])
def test_edicion_y_baja_usuario_inexistente_404(client, db_session, metodo):
    """# AC SA-R2 ERROR: UUID inexistente ? 404 sin datos internos."""
    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    _login(client, admin.email)
    url = f"/api/usuarios-staff/{uuid4()}"
    if metodo == "put":
        resp = client.put(url, json={"activo": False})
    else:
        resp = client.delete(url)
    assert resp.status_code == 404, resp.text
    assert "usuario_staff" not in resp.text


# --- �5.6 / �5.7 validaci�n del v�nculo en edici�n -------------------------


@pytest.mark.parametrize("caso", ["inexistente", "inactivo"])
def test_edicion_usuario_profesional_id_inexistente_o_inactivo_422(
    client, db_session, caso
):
    """# AC SA-R2 ERROR: v�nculo inexistente/inactivo ? 422 en el campo."""
    from app.models.usuario_staff import UsuarioStaff

    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    _login(client, admin.email)
    usuario = _staff(db_session, StaffRol.recepcion)
    if caso == "inexistente":
        profesional_id = uuid4()
    else:
        profesional_id = _prof(db_session, activo=False).id
    db_session.commit()

    resp = client.put(
        f"/api/usuarios-staff/{usuario.id}",
        json={"rol": "odontologo", "profesional_id": str(profesional_id)},
    )
    assert resp.status_code == 422, resp.text
    assert "profesional_id" in _creditos_422(resp)
    fila = db_session.get(UsuarioStaff, usuario.id)
    db_session.refresh(fila)
    assert fila.rol == StaffRol.recepcion
    assert fila.profesional_id is None


def test_edicion_usuario_vinculado_a_profesional_inactivo_200(client, db_session):
    """# AC SA-R2 FELIZ: el v�nculo previo no se revalida si no se env�a."""
    from app.models.usuario_staff import UsuarioStaff

    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    _login(client, admin.email)
    prof = _prof(db_session)
    usuario = _staff(db_session, StaffRol.odontologo, profesional_id=prof.id)
    prof.activo = False
    db_session.commit()

    resp = client.put(
        f"/api/usuarios-staff/{usuario.id}",
        json={"rol": "recepcion", "profesional_id": None},
    )
    assert resp.status_code == 200, resp.text
    fila = db_session.get(UsuarioStaff, usuario.id)
    db_session.refresh(fila)
    assert fila.rol == StaffRol.recepcion
    assert fila.profesional_id is None


# --- �5.8 �ltimo admin por PUT --------------------------------------------


def test_edicion_usuario_auto_degradacion_ultimo_admin_422(client, db_session):
    """# AC SA-R2 ERROR: el �nico admin no puede degradarse ? 422."""
    from app.models.usuario_staff import UsuarioStaff

    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    _login(client, admin.email)

    resp = client.put(
        f"/api/usuarios-staff/{admin.id}",
        json={"rol": "recepcion"},
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["codigo"] == "ultimo_admin"
    fila = db_session.get(UsuarioStaff, admin.id)
    db_session.refresh(fila)
    assert fila.rol == StaffRol.admin
    assert fila.activo is True


def test_edicion_usuario_desactivarse_ultimo_admin_422(client, db_session):
    """# AC SA-R2 ERROR: `PUT activo=false` del �nico admin ? 422."""
    from app.models.usuario_staff import UsuarioStaff

    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    _login(client, admin.email)

    resp = client.put(
        f"/api/usuarios-staff/{admin.id}",
        json={"activo": False},
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["codigo"] == "ultimo_admin"
    fila = db_session.get(UsuarioStaff, admin.id)
    db_session.refresh(fila)
    assert fila.activo is True


def test_edicion_usuario_auto_degradacion_con_otro_admin_200_403(client, db_session):
    """# AC SA-R2 FELIZ: con otro admin activo degradarse corta el acceso admin."""
    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    _staff(db_session, StaffRol.admin)
    _login(client, admin.email)

    resp = client.put(
        f"/api/usuarios-staff/{admin.id}",
        json={"rol": "recepcion"},
    )
    assert resp.status_code == 200, resp.text
    assert client.get("/api/usuarios-staff").status_code == 403


# --- �6.1��6.3 baja l�gica ------------------------------------------------


def test_baja_usuario_activo_false_401_siguiente_request(client, db_session):
    """# AC SA-R3 FELIZ: la baja corta la sesi�n vigente en el siguiente request."""
    from app.models.usuario_staff import UsuarioStaff

    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    usuario = _staff(
        db_session, StaffRol.recepcion, email="baja.recepcion@cattaneo.test"
    )
    db_session.commit()
    _login(client, usuario.email)
    cookie_usuario = client.cookies.get("session")
    _login(client, admin.email)

    resp = client.delete(f"/api/usuarios-staff/{usuario.id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["activo"] is False
    fila = db_session.get(UsuarioStaff, usuario.id)
    db_session.refresh(fila)
    assert fila is not None and fila.activo is False

    client.cookies.set("session", cookie_usuario)
    assert client.get("/api/auth/me").status_code == 401


def test_baja_usuario_ultimo_admin_422(client, db_session):
    """# AC SA-R3 ERROR: el �nico admin no puede darse de baja ? 422."""
    from app.models.usuario_staff import UsuarioStaff

    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    _login(client, admin.email)

    resp = client.delete(f"/api/usuarios-staff/{admin.id}")
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["codigo"] == "ultimo_admin"
    fila = db_session.get(UsuarioStaff, admin.id)
    db_session.refresh(fila)
    assert fila.activo is True


@pytest.mark.parametrize("caso", ["otro_admin", "auto_baja"])
def test_baja_usuario_admin_con_otro_activo_200(client, db_session, caso):
    """# AC SA-R3 FELIZ: con otro admin activo la baja procede."""
    from app.models.usuario_staff import UsuarioStaff

    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    otro = _staff(db_session, StaffRol.admin)
    _login(client, admin.email)

    destino = otro if caso == "otro_admin" else admin
    resp = client.delete(f"/api/usuarios-staff/{destino.id}")
    assert resp.status_code == 200, resp.text
    fila = db_session.get(UsuarioStaff, destino.id)
    db_session.refresh(fila)
    assert fila.activo is False


# --- �6.4 / �6.5 carreras reales entre admins -----------------------------


def _crear_usuarios_conc(test_engine, cantidad, rol=StaffRol.admin):
    """Crea admins reales y desactiva cualquier admin previo (se restaura)."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    from app.core.security import hash_password
    from app.models.usuario_staff import UsuarioStaff

    sesion = Session(bind=test_engine)
    try:
        previos = [
            r[0]
            for r in sesion.execute(
                text(
                    "SELECT id FROM usuario_staff "
                    "WHERE rol = 'admin' AND activo IS TRUE"
                )
            ).all()
        ]
        sesion.execute(
            text("UPDATE usuario_staff SET activo = false WHERE rol = 'admin'")
        )
        ids = []
        for _ in range(cantidad):
            usuario = UsuarioStaff(
                email=f"conc.{uuid4().hex[:12]}@cattaneo.test",
                password_hash=hash_password(PASSWORD),
                rol=rol,
                activo=True,
            )
            sesion.add(usuario)
            sesion.flush()
            ids.append(usuario.id)
        sesion.commit()
        return ids, previos
    finally:
        sesion.close()


def _limpiar_conc(test_engine, ids, previos):
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    sesion = Session(bind=test_engine)
    try:
        for usuario_id in ids:
            sesion.execute(
                text("DELETE FROM usuario_staff WHERE id = :i"), {"i": usuario_id}
            )
        for usuario_id in previos:
            sesion.execute(
                text("UPDATE usuario_staff SET activo = true WHERE id = :i"),
                {"i": usuario_id},
            )
        sesion.commit()
    finally:
        sesion.close()


def _admins_activos(test_engine):
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    sesion = Session(bind=test_engine)
    try:
        return sesion.execute(
            text("SELECT count(*) FROM usuario_staff WHERE rol = 'admin' AND activo")
        ).scalar()
    finally:
        sesion.close()


def _correr_carrera(operaciones):
    """Dos operaciones concurrentes; devuelve {clave: status}."""
    from sqlalchemy.orm import Session

    resultados: dict[str, int] = {}
    barrera = threading.Barrier(len(operaciones))

    def ejecutar(clave, operacion):
        sesion = Session(bind=operaciones[clave]["engine"])
        try:
            barrera.wait(timeout=10)
            try:
                operacion["fn"](sesion)
                resultados[clave] = 200
            except HTTPException as exc:
                resultados[clave] = exc.status_code
            except Exception as exc:  # pragma: no cover - diagn�stico
                resultados[clave] = type(exc).__name__
        finally:
            sesion.close()

    hilos = [
        threading.Thread(target=ejecutar, args=(clave, op))
        for clave, op in operaciones.items()
    ]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=30)
    assert all(not hilo.is_alive() for hilo in hilos), resultados
    return resultados


def test_baja_usuario_dos_admins_concurrentes_queda_uno(test_engine):
    """# AC SA-R3 BORDE: DELETE�DELETE deja exactamente un admin activo."""
    from app.modules.usuarios_staff import service

    ids, previos = _crear_usuarios_conc(test_engine, 2)
    try:
        resultados = _correr_carrera(
            {
                "a": {
                    "engine": test_engine,
                    "fn": lambda s: service.dar_de_baja(s, ids[1]),
                },
                "b": {
                    "engine": test_engine,
                    "fn": lambda s: service.dar_de_baja(s, ids[0]),
                },
            }
        )
        assert sorted(str(v) for v in resultados.values()) == ["200", "422"], resultados
        assert _admins_activos(test_engine) == 1
    finally:
        _limpiar_conc(test_engine, ids, previos)


@pytest.mark.parametrize("caso", ["put_delete", "put_put"])
def test_carrera_put_activo_false_y_delete_queda_un_admin(test_engine, caso):
    """# AC SA-R3 BORDE: carreras mixtas dejan exactamente un admin activo."""
    from app.modules.usuarios_staff import service
    from app.modules.usuarios_staff.schemas import UsuarioStaffUpdate

    ids, previos = _crear_usuarios_conc(test_engine, 2)
    try:
        if caso == "put_delete":
            operaciones = {
                "a": {
                    "engine": test_engine,
                    "fn": lambda s: service.actualizar(
                        s, ids[0], UsuarioStaffUpdate(activo=False)
                    ),
                },
                "b": {
                    "engine": test_engine,
                    "fn": lambda s: service.dar_de_baja(s, ids[1]),
                },
            }
        else:
            operaciones = {
                "a": {
                    "engine": test_engine,
                    "fn": lambda s: service.actualizar(
                        s, ids[0], UsuarioStaffUpdate(activo=False)
                    ),
                },
                "b": {
                    "engine": test_engine,
                    "fn": lambda s: service.actualizar(
                        s, ids[1], UsuarioStaffUpdate(activo=False)
                    ),
                },
            }
        resultados = _correr_carrera(operaciones)
        assert sorted(str(v) for v in resultados.values()) == ["200", "422"], resultados
        assert _admins_activos(test_engine) == 1
    finally:
        _limpiar_conc(test_engine, ids, previos)


# --- �6.6��6.8 idempotencia y reactivaci�n ---------------------------------


def test_baja_usuario_repetida_200_idempotente(client, db_session):
    """# AC SA-R3 BORDE: repetir la baja ? 200 sin alterar otros datos."""
    from app.models.usuario_staff import UsuarioStaff

    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    usuario = _staff(db_session, StaffRol.recepcion)
    _login(client, admin.email)

    assert client.delete(f"/api/usuarios-staff/{usuario.id}").status_code == 200
    segunda = client.delete(f"/api/usuarios-staff/{usuario.id}")
    assert segunda.status_code == 200
    assert segunda.json()["activo"] is False
    fila = db_session.get(UsuarioStaff, usuario.id)
    db_session.refresh(fila)
    assert fila.rol == StaffRol.recepcion


def test_reactivacion_usuario_200_login_previo_200(client, db_session):
    """# AC SA-R4 FELIZ: reactivar habilita el login previo sin crear otra fila."""
    from app.models.usuario_staff import UsuarioStaff

    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    prof = _prof(db_session)
    usuario = _staff(
        db_session,
        StaffRol.odontologo,
        email="reactivar.odonto@cattaneo.test",
        profesional_id=prof.id,
        activo=False,
    )
    _login(client, admin.email)

    resp = client.put(
        f"/api/usuarios-staff/{usuario.id}",
        json={"activo": True},
    )
    assert resp.status_code == 200, resp.text

    client.cookies.clear()
    _login(client, usuario.email)
    assert (
        db_session.query(UsuarioStaff)
        .filter(UsuarioStaff.email == usuario.email)
        .count()
        == 1
    )


def test_reactivacion_usuario_ya_activo_200(client, db_session):
    """# AC SA-R4 BORDE: reactivar un usuario activo ? 200 sin cambios."""
    from app.models.usuario_staff import UsuarioStaff

    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    usuario = _staff(db_session, StaffRol.recepcion)
    db_session.commit()
    antes = db_session.get(UsuarioStaff, usuario.id)
    datos_antes = (antes.email, antes.rol, antes.profesional_id, antes.activo)
    _login(client, admin.email)

    resp = client.put(
        f"/api/usuarios-staff/{usuario.id}",
        json={"activo": True},
    )
    assert resp.status_code == 200, resp.text
    despues = db_session.get(UsuarioStaff, usuario.id)
    db_session.refresh(despues)
    assert (
        despues.email,
        despues.rol,
        despues.profesional_id,
        despues.activo,
    ) == datos_antes


# --- �7.1��7.3 listado keyset ---------------------------------------------


def test_listado_usuarios_incluye_inactivos_sin_hash(client, db_session):
    """# AC SA-R5 FELIZ: activos e inactivos, columnas expl�citas sin hash."""
    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    activo = _staff(
        db_session, StaffRol.recepcion, email="activo.listado@cattaneo.test"
    )
    inactivo = _staff(
        db_session,
        StaffRol.odontologo,
        email="inactivo.listado@cattaneo.test",
        profesional_id=_prof(db_session).id,
        activo=False,
    )
    db_session.commit()
    _login(client, admin.email)

    resp = client.get("/api/usuarios-staff", params={"limit": 100})
    assert resp.status_code == 200, resp.text
    cuerpo = resp.json()
    por_id = {item["id"]: item for item in cuerpo["items"]}
    assert str(activo.id) in por_id
    assert str(inactivo.id) in por_id
    for item in cuerpo["items"]:
        assert set(item) == {"id", "email", "rol", "profesional_id", "activo"}
    assert "next_cursor" in cuerpo


def test_listado_usuarios_keyset_paginas(client, db_session):
    """# AC SA-R5 FELIZ: keyset con limit=2 no repite ni omite usuarios."""
    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    creados = [
        _staff(db_session, StaffRol.recepcion, email=f"keyset.{i}@cattaneo.test").id
        for i in range(3)
    ]
    db_session.commit()
    _login(client, admin.email)

    vistos: list[str] = []
    cursor = None
    paginas = 0
    while True:
        params = {"limit": 2}
        if cursor is not None:
            params["cursor"] = cursor
        resp = client.get("/api/usuarios-staff", params=params)
        assert resp.status_code == 200, resp.text
        cuerpo = resp.json()
        vistos.extend(item["id"] for item in cuerpo["items"])
        paginas += 1
        cursor = cuerpo["next_cursor"]
        if cursor is None:
            break
        assert paginas < 10
    assert len(vistos) == len(set(vistos))
    for usuario_id in creados:
        assert str(usuario_id) in vistos


def test_listado_usuarios_cursor_invalido_400(client, db_session):
    """# AC SA-R5 ERROR: cursor no UUID ? 400 en `cursor`."""
    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    _login(client, admin.email)

    resp = client.get("/api/usuarios-staff", params={"cursor": "no-es-uuid"})
    assert resp.status_code == 400, resp.text
    assert "cursor" in {d["campo"] for d in resp.json()["detail"]}


@pytest.mark.parametrize("limit", [0, 101])
def test_listado_usuarios_limit_fuera_rango_400(client, db_session, limit):
    """# AC SA-R5 ERROR: limit 0/101 ? 400 en `limit`."""
    _aislar_admins(db_session)
    admin = _staff(db_session, StaffRol.admin)
    _login(client, admin.email)

    resp = client.get("/api/usuarios-staff", params={"limit": limit})
    assert resp.status_code == 400, resp.text
    assert "limit" in {d["campo"] for d in resp.json()["detail"]}
