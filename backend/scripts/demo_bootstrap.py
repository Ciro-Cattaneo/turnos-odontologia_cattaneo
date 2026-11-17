#!/usr/bin/env python3
"""Bootstrap idempotente de datos ficticios para la demo local de un comando.

Uso (SIEMPRE desde la raiz del repo, porque `Settings` lee `.env` del CWD):

    python backend/scripts/demo_bootstrap.py

Que hace:
- Lee la configuracion con `app.core.config.get_settings()` (`.env` del CWD;
  si no existe, cae a `os.environ`).
- Se niega a escribir con `ENV=prod` (exit 2, sin abrir conexion).
- Reutiliza `app.db.seed.seed_admin` para el admin (idempotente).
- Crea 3 profesionales demo, horarios lun-vie 09-12 / 14-18, turnos futuros y
  pasados. Todo con clave natural idempotente (profesional + inicio): re-ejecutar
  no duplica.
- Solo datos ficticios: `@ficticio.test`, DNI sinteticos, nombres inventados
  (Ley 25.326 / regla dura 12).
- No imprime secretos: solo el email/password admin de la demo (regla dura 10).
"""

from __future__ import annotations

import hashlib
import os
import sys
import uuid
from datetime import UTC, date, datetime, time as dt_time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.seed import seed_admin  # noqa: E402
from app.models.disponibilidad import Disponibilidad  # noqa: E402
from app.models.paciente import Paciente  # noqa: E402
from app.models.profesional import Profesional  # noqa: E402
from app.models.turno import Turno, TurnoEstado, TurnoOrigen  # noqa: E402
from app.models.usuario_staff import UsuarioStaff  # noqa: E402

TZ = ZoneInfo("America/Argentina/Buenos_Aires")

PROFESIONALES_DEMO = (
    ("DEMO-001", "Dra. Demo Uno", "Odontologia general", 30),
    ("DEMO-002", "Dr. Demo Dos", "Odontologia general", 45),
    ("DEMO-003", "Dra. Demo Tres", "Odontologia general", 60),
)

VENTANAS_DEMO = ((dt_time(9, 0), dt_time(12, 0)), (dt_time(14, 0), dt_time(18, 0)))

NOMBRES_PACIENTES = (
    "Paciente Demo Alfa",
    "Paciente Demo Beta",
    "Paciente Demo Gamma",
    "Paciente Demo Delta",
    "Paciente Demo Epsilon",
    "Paciente Demo Zeta",
)

ESTADOS_FUTUROS = (TurnoEstado.reservado, TurnoEstado.confirmado)
ORIGENES_DEMO = (TurnoOrigen.online, TurnoOrigen.recepcion)
ESTADOS_PASADOS = (
    TurnoEstado.atendido,
    TurnoEstado.ausente,
    TurnoEstado.cancelado,
)


def _leer_env_crudo(nombre: str) -> str | None:
    """Lee una clave de `os.environ` o, si falta, del `.env` del CWD."""
    valor = os.environ.get(nombre)
    if valor is not None:
        return valor
    ruta = Path(".env")
    if not ruta.is_file():
        return None
    for linea in ruta.read_text(encoding="utf-8", errors="ignore").splitlines():
        limpia = linea.strip()
        if not limpia or limpia.startswith("#") or "=" not in limpia:
            continue
        clave, _, resto = limpia.partition("=")
        if clave.strip() == nombre:
            return resto.strip().strip('"').strip("'")
    return None


def _digest(clave: str) -> str:
    return hashlib.sha256(clave.encode("utf-8")).hexdigest()


def _dni_sintetico(clave: str) -> str:
    """DNI sintetico estable y unico por clave natural (solo digitos)."""
    digitos = "".join(c for c in _digest(clave) if c.isdigit())
    return ("9" + digitos[:10])[:11]


def _nombre_paciente(clave: str) -> str:
    return NOMBRES_PACIENTES[int(_digest(clave), 16) % len(NOMBRES_PACIENTES)]


def _dias_habiles(desde: date, cantidad: int, paso: int) -> list[date]:
    """`cantidad` dias habiles desde `desde` (paso +1 futuro, -1 pasado)."""
    dias: list[date] = []
    dia = desde
    while len(dias) < cantidad:
        if dia.weekday() < 5:
            dias.append(dia)
        dia += timedelta(days=paso)
    return dias


def _dias_pasados(hoy: date, cantidad: int = 12, ventana_dias: int = 20) -> list[date]:
    """Hasta `cantidad` dias habiles dentro de los ultimos `ventana_dias`."""
    dias: list[date] = []
    dia = hoy - timedelta(days=1)
    while len(dias) < cantidad and (hoy - dia).days <= ventana_dias:
        if dia.weekday() < 5:
            dias.append(dia)
        dia -= timedelta(days=1)
    return dias


def _profesional(
    session: Session,
    matricula: str,
    nombre: str,
    especialidad: str,
    duracion: int,
) -> tuple[Profesional, bool]:
    existente = (
        session.query(Profesional)
        .filter(Profesional.matricula == matricula)
        .one_or_none()
    )
    if existente is not None:
        return existente, False
    profesional = Profesional(
        nombre=nombre,
        matricula=matricula,
        especialidad=especialidad,
        duracion_default_min=duracion,
        activo=True,
    )
    session.add(profesional)
    session.flush()
    return profesional, True


def _ventana(
    session: Session,
    profesional_id: uuid.UUID,
    dia_semana: int,
    hora_desde: dt_time,
    hora_hasta: dt_time,
    vigente_desde: date,
) -> bool:
    """Crea la ventana si no existe una identica abierta (sin vigente_hasta)."""
    existente = (
        session.query(Disponibilidad.id)
        .filter(
            Disponibilidad.profesional_id == profesional_id,
            Disponibilidad.dia_semana == dia_semana,
            Disponibilidad.hora_desde == hora_desde,
            Disponibilidad.hora_hasta == hora_hasta,
            Disponibilidad.vigente_hasta.is_(None),
        )
        .one_or_none()
    )
    if existente is not None:
        return False
    session.add(
        Disponibilidad(
            profesional_id=profesional_id,
            dia_semana=dia_semana,
            hora_desde=hora_desde,
            hora_hasta=hora_hasta,
            vigente_desde=vigente_desde,
            vigente_hasta=None,
        )
    )
    session.flush()
    return True


def _crear_turno(
    session: Session,
    profesional: Profesional,
    inicio_local: datetime,
    estado: TurnoEstado,
    origen: TurnoOrigen,
    clave: str,
) -> bool:
    """Crea paciente + turno si no existe un turno del profesional a esa hora."""
    inicio_utc = inicio_local.astimezone(UTC)
    existente = (
        session.query(Turno.id)
        .filter(
            Turno.profesional_id == profesional.id,
            Turno.inicio == inicio_utc,
        )
        .one_or_none()
    )
    if existente is not None:
        return False

    fin_local = inicio_local + timedelta(minutes=profesional.duracion_default_min)
    dni = _dni_sintetico(clave)
    paciente = Paciente(
        nombre=_nombre_paciente(clave),
        dni=dni,
        telefono="+5491100000000",
        email=f"paciente-{dni}@ficticio.test",
        obra_social="Obra Social Ficticia",
    )
    session.add(paciente)
    session.flush()
    session.add(
        Turno(
            profesional_id=profesional.id,
            paciente_id=paciente.id,
            inicio=inicio_utc,
            fin=fin_local.astimezone(UTC),
            duracion_min=profesional.duracion_default_min,
            estado=estado,
            origen=origen,
            token_cancelacion=uuid.uuid4(),
        )
    )
    session.flush()
    return True


def _resumen(
    admin_existia: bool,
    profesionales: tuple[int, int],
    ventanas: tuple[int, int],
    futuros: tuple[int, int],
    pasados: tuple[int, int],
    pacientes_creados: int,
    settings,
) -> None:
    print("=== Demo bootstrap (datos ficticios) ===")
    print(f"admin: {'existente' if admin_existia else 'creado'} ({settings.ADMIN_EMAIL})")
    print(f"profesionales: creados={profesionales[0]} existentes={profesionales[1]}")
    print(f"disponibilidades: creadas={ventanas[0]} existentes={ventanas[1]}")
    print(f"turnos futuros: creados={futuros[0]} existentes={futuros[1]}")
    print(f"turnos pasados: creados={pasados[0]} existentes={pasados[1]}")
    print(f"pacientes: creados={pacientes_creados}")
    print("")
    print(f"login staff: email={settings.ADMIN_EMAIL} password={settings.ADMIN_PASSWORD}")
    print("datos ficticios (Ley 25.326): no usar en produccion")


def main() -> int:
    declarado = _leer_env_crudo("ENV")
    if declarado == "prod":
        print(
            "refuse: demo_bootstrap no se ejecuta con ENV=prod",
            file=sys.stderr,
        )
        return 2

    try:
        settings = get_settings()
    except RuntimeError as exc:
        print(f"error de configuracion: {exc}", file=sys.stderr)
        return 1
    if settings.ENV == "prod":
        print(
            "refuse: demo_bootstrap no se ejecuta con ENV=prod",
            file=sys.stderr,
        )
        return 2

    profes_creados = profes_existentes = 0
    ventanas_creadas = ventanas_existentes = 0
    futuros_creados = futuros_existentes = 0
    pasados_creados = pasados_existentes = 0
    pacientes_creados = 0

    engine = create_engine(settings.DATABASE_URL)
    try:
        with Session(bind=engine) as session:
            admin_existia = (
                session.query(UsuarioStaff.id)
                .filter(UsuarioStaff.email == settings.ADMIN_EMAIL)
                .one_or_none()
                is not None
            )
            seed_admin(session, settings.ADMIN_EMAIL, settings.ADMIN_PASSWORD)

            profesionales: list[Profesional] = []
            for matricula, nombre, especialidad, duracion in PROFESIONALES_DEMO:
                profesional, creado = _profesional(
                    session, matricula, nombre, especialidad, duracion
                )
                profesionales.append(profesional)
                if creado:
                    profes_creados += 1
                else:
                    profes_existentes += 1

            hoy = datetime.now(TZ).date()
            vigente_desde = hoy - timedelta(days=30)
            for profesional in profesionales:
                for dia_semana in range(5):
                    for hora_desde, hora_hasta in VENTANAS_DEMO:
                        if _ventana(
                            session,
                            profesional.id,
                            dia_semana,
                            hora_desde,
                            hora_hasta,
                            vigente_desde,
                        ):
                            ventanas_creadas += 1
                        else:
                            ventanas_existentes += 1

            # Futuros: proximos 5 dias habiles, 2 turnos/dia/profesional en la
            # grilla (manana 09:00; tarde 14:00 + duracion), sin solapes.
            for dia_idx, dia in enumerate(_dias_habiles(hoy + timedelta(days=1), 5, 1)):
                for prof_idx, profesional in enumerate(profesionales):
                    duracion = profesional.duracion_default_min
                    inicios = (
                        datetime.combine(dia, dt_time(9, 0), tzinfo=TZ),
                        datetime.combine(dia, dt_time(14, 0), tzinfo=TZ)
                        + timedelta(minutes=duracion),
                    )
                    for slot_idx, inicio in enumerate(inicios):
                        indice = dia_idx + prof_idx + slot_idx
                        clave = (
                            f"futuro:{profesional.matricula}:{dia.isoformat()}:"
                            f"{slot_idx}"
                        )
                        creado = _crear_turno(
                            session,
                            profesional,
                            inicio,
                            ESTADOS_FUTUROS[indice % 2],
                            ORIGENES_DEMO[indice % 2],
                            clave,
                        )
                        if creado:
                            futuros_creados += 1
                            pacientes_creados += 1
                        else:
                            futuros_existentes += 1

            # Pasados: hasta 12 dias habiles en los ultimos 20, estados
            # atendido/ausente/cancelado para que el reporte tenga datos.
            for idx, dia in enumerate(_dias_pasados(hoy)):
                profesional = profesionales[idx % len(profesionales)]
                duracion = profesional.duracion_default_min
                inicio = datetime.combine(
                    dia, dt_time(9, 0), tzinfo=TZ
                ) + timedelta(minutes=2 * duracion)
                clave = f"pasado:{profesional.matricula}:{dia.isoformat()}"
                creado = _crear_turno(
                    session,
                    profesional,
                    inicio,
                    ESTADOS_PASADOS[idx % 3],
                    ORIGENES_DEMO[idx % 2],
                    clave,
                )
                if creado:
                    pasados_creados += 1
                    pacientes_creados += 1
                else:
                    pasados_existentes += 1

            session.commit()

        _resumen(
            admin_existia,
            (profes_creados, profes_existentes),
            (ventanas_creadas, ventanas_existentes),
            (futuros_creados, futuros_existentes),
            (pasados_creados, pasados_existentes),
            pacientes_creados,
            settings,
        )
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
