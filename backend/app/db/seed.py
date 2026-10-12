"""Seeds C-02 (D-7): admin idempotente desde env + demo staging-only.

Password hashing (C-03 D-1): esquema final argon2id vía `app.core.security`
(hashes nuevos `$argon2id$…`); `verify_password` dual por prefijo (acepta el
PBKDF2 transitorio `pbkdf2_sha256$…` solo-lectura para la rotación al primer
login — aquí solo creación, la rotación vive en `modules/auth/service.py`).

Ninguna función commitea: hacen flush y el llamador (CLI/tests) commitea o
revierte — transacciones cortas (supabase-postgres-best-practices).
"""

import os
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.paciente import Paciente
from app.models.profesional import Profesional
from app.models.turno import Turno, TurnoEstado, TurnoOrigen
from app.models.usuario_staff import StaffRol, UsuarioStaff

__all__ = ["hash_password", "verify_password", "seed_admin", "seed_admin_from_env"]


def seed_admin(session: Session, email: str, password: str) -> UsuarioStaff:
    """Crea el admin si falta; idempotente (`ON CONFLICT`-like por email)."""
    existente = (
        session.query(UsuarioStaff).filter(UsuarioStaff.email == email).one_or_none()
    )
    if existente is not None:
        return existente
    admin = UsuarioStaff(
        email=email, password_hash=hash_password(password), rol=StaffRol.admin
    )
    session.add(admin)
    session.flush()
    return admin


def seed_admin_from_env(session: Session) -> UsuarioStaff:
    """Lee `ADMIN_EMAIL`/`ADMIN_PASSWORD` del entorno y delega en `seed_admin`."""
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")
    if not email or not password:
        raise RuntimeError("faltan ADMIN_EMAIL/ADMIN_PASSWORD en el entorno")
    return seed_admin(session, email, password)


def seed_demo(session: Session) -> dict[str, int]:
    """2 profesionales + 20 turnos ficticios (staging-only; el CLI filtra prod).

    Sufijo único por corrida (`tag`) para que el script sea re-ejecutable sin
    chocar con `UNIQUE(dni)` de corridas previas; el marcador `Demo Seed` en
    nombres permite contar lo propio sin depender de tablas vacías.
    """
    tag = uuid.uuid4().hex[:6]
    tag_num = f"{uuid.uuid4().int % 1_000_000:06d}"
    base = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)  # 09:00 America/Argentina
    profesionales = []
    for i in (1, 2):
        prof = Profesional(
            nombre=f"Demo Seed {tag} {i}",
            especialidad="Odontología general ficticia",
        )
        session.add(prof)
        profesionales.append(prof)
    session.flush()
    n_turnos = 0
    for i, prof in enumerate(profesionales):
        for k in range(10):
            inicio = base + timedelta(minutes=30 * k)
            pac = Paciente(
                nombre=f"Demo Seed Paciente {tag}-{i}-{k}",
                dni=f"33999{tag_num}{i}{k}",
                telefono="+549110000000",
                email=f"demo-seed-{tag}-{i}-{k}@ficticio.test",
                obra_social="OS Ficticia",
            )
            session.add(pac)
            session.flush()
            session.add(
                Turno(
                    profesional_id=prof.id,
                    paciente_id=pac.id,
                    inicio=inicio,
                    fin=inicio + timedelta(minutes=30),
                    duracion_min=30,
                    estado=TurnoEstado.reservado
                    if (i + k) % 2 == 0
                    else TurnoEstado.confirmado,
                    origen=TurnoOrigen.online if k % 2 == 0 else TurnoOrigen.recepcion,
                    token_cancelacion=uuid.uuid4(),
                )
            )
            n_turnos += 1
    session.flush()
    return {"profesionales": len(profesionales), "turnos": n_turnos}
