"""Servicio de ventanas de disponibilidad (C-04 D-3 LOCK).

Contrato para C-05 (consume esto, no lo reimplementa): el overlap de
`Disponibilidad` es app-level dentro de transacción corta con
`SELECT FOR UPDATE` sobre las ventanas del profesional+día — NO hay EXCLUDE
temporal en DB. Por tanto la reserva NUNCA asume invariante DB en
disponibilidades: revalida en su propia transacción que el slot pedido cae
dentro de una ventana vigente, fuera de bloqueos y sin turno activo solapado
(reutiliza `slot_service.compute_slots` + EXCLUDE `no_solape_prof` de turnos
según RN-TU-03). Contención de writes: recepción/admin serializados, baja.
"""

from datetime import date, time
from uuid import UUID

from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session

from app.models.disponibilidad import Disponibilidad
from app.models.profesional import Profesional


def _vigencias_intersectan(
    a_desde: date | None,
    a_hasta: date | None,
    b_desde: date | None,
    b_hasta: date | None,
) -> bool:
    """Intersección de vigencias (`None` = abierto; borde exacto no intersecta)."""
    ini = max([d for d in (a_desde, b_desde) if d is not None], default=None)
    fin = min([d for d in (a_hasta, b_hasta) if d is not None], default=None)
    if ini is None or fin is None:
        return True
    return ini <= fin


def _hay_solape(
    existentes: list[Disponibilidad],
    dia: int,
    h_desde: time,
    h_hasta: time,
    v_desde: date | None,
    v_hasta: date | None,
    excluir_id: UUID | None = None,
) -> Disponibilidad | None:
    """Primera ventana en conflicto mismo día (`[hora_desde, hora_hasta)`)."""
    for e in existentes:
        if excluir_id is not None and e.id == excluir_id:
            continue
        if e.dia_semana != dia:
            continue
        if not (h_desde < e.hora_hasta and e.hora_desde < h_hasta):
            continue
        if not _vigencias_intersectan(
            v_desde, v_hasta, e.vigente_desde, e.vigente_hasta
        ):
            continue
        return e
    return None


def crear_ventana(
    db: Session,
    profesional_id: UUID,
    dia_semana: int,
    hora_desde: time,
    hora_hasta: time,
    vigente_desde: date | None,
    vigente_hasta: date | None,
) -> Disponibilidad:
    """Crea la ventana con validación sin solape bajo lock (transacción corta).

    # AC agenda-disponibilidad/CRUD-staff (201, 409-con-conflicto, borde
    permitido, distinto-profesional/día permitido).
    """
    prof = (
        db.query(Profesional).filter(Profesional.id == profesional_id).one_or_none()
    )
    if prof is None or not prof.activo:
        raise HTTPException(status_code=404, detail="No encontrado")
    existentes = (
        db.query(Disponibilidad)
        .filter(
            Disponibilidad.profesional_id == profesional_id,
            Disponibilidad.dia_semana == dia_semana,
        )
        .with_for_update()
        .all()
    )
    conflicto = _hay_solape(
        existentes, dia_semana, hora_desde, hora_hasta, vigente_desde, vigente_hasta
    )
    if conflicto is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "solape con ventana existente",
                "conflicto": {
                    "id": str(conflicto.id),
                    "dia_semana": conflicto.dia_semana,
                    "hora_desde": conflicto.hora_desde.isoformat(),
                    "hora_hasta": conflicto.hora_hasta.isoformat(),
                },
            },
        )
    ventana = Disponibilidad(
        profesional_id=profesional_id,
        dia_semana=dia_semana,
        hora_desde=hora_desde,
        hora_hasta=hora_hasta,
        vigente_desde=vigente_desde,
        vigente_hasta=vigente_hasta,
    )
    db.add(ventana)
    db.commit()
    db.refresh(ventana)
    return ventana
