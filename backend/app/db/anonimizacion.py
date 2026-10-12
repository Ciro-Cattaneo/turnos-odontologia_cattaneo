"""Anonimización manual Ley 25.326 (PB-04, D-9/D-9a, sin UI v1).

Procedimiento admin-only: nombre→"Eliminado #id", dni/tel/mail→NULL (D-9a los
hace nulables en DB), obra_social→"(eliminado)". Los turnos se conservan como
estadística; por cada turno se escribe una fila `AuditoriaTurno(anonimizar)`
(actor NULL = acto admin manual documentado en `detalle`).
"""

import uuid

from sqlalchemy.orm import Session

from app.models.auditoria import AuditoriaTurno
from app.models.paciente import Paciente
from app.models.turno import Turno


def anonimizar_paciente(session: Session, paciente_id: uuid.UUID) -> Paciente:
    """Ejecuta la anonimización; hace flush (el llamador commitea).

    Lanza `ValueError` si el paciente no existe (sin tocar nada).
    """
    paciente = session.get(Paciente, paciente_id)
    if paciente is None:
        raise ValueError(f"paciente {paciente_id} no existe")
    turnos = session.query(Turno.id).filter(Turno.paciente_id == paciente_id).all()
    paciente.nombre = f"Eliminado #{paciente_id}"
    paciente.dni = None
    paciente.telefono = None
    paciente.email = None
    paciente.obra_social = "(eliminado)"
    for (turno_id,) in turnos:
        session.add(
            AuditoriaTurno(
                turno_id=turno_id,
                actor_id=None,
                accion="anonimizar",
                detalle={
                    "motivo": "ley-25326",
                    "actor": "admin-manual",
                    "paciente_id": str(paciente_id),
                },
            )
        )
    session.flush()
    return paciente
