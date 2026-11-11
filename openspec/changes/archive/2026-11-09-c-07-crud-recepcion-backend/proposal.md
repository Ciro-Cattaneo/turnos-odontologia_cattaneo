# Proposal — c-07-crud-recepcion-backend

## Why

C-05 y C-06 cubren la reserva pública y la cancelación por token, y C-08 la cola de mail, pero hoy recepción no puede operar el mostrador: no existe alta de turno con `origen=recepcion`, reprogramación, corrección de datos del paciente, marcado de asistencia ni cancelación forzada `<3 h` con motivo y auditoría. Sin C-07 quedan incompletos US-006, US-007, US-008 y el Flujo 3, y todo turno telefónico o presencial queda fuera del sistema.

## What Changes

- `POST /api/turnos` con sesión staff (`recepcion`/`admin`) y `origen=recepcion`: mismos cinco datos obligatorios que online, misma duración y anti-solape, mismo encolado de notificaciones y auditoría con actor staff. Sin sesión, el contrato público de C-05 queda intacto.
- `PUT /api/turnos/{id}` para reprogramar y/o cambiar `duracion_min`, con la misma validación anti-solape que online (`409` + alternativos) y `422` cuando el estado no es editable.
- `DELETE /api/turnos/{id}` staff (sin `?token=`): borrado = `estado=cancelado`, nunca `DELETE` físico. Con `<3 h` de anticipación exige `motivo`, solo `recepcion`/`admin`, y audita `forzar_cancelacion`; en el resto de los casos audita `cancelar`.
- `PUT /api/turnos/{id}/paciente`: corrección de DNI, teléfono y obra social con auditoría antes→después y `409` si el DNI corregido ya pertenece a otro paciente.
- `PATCH /api/turnos/{id}/estado`: `confirmado`/`atendido`/`ausente` respetando la matriz RN-TU-07; transición inválida → `422` y `cancelado` solo por la ruta de cancelación.
- `GET /api/turnos/{id}`: ficha staff con datos del turno, paciente y profesional + historial de cambios leído de `AuditoriaTurno` con paginación keyset.
- Reutiliza la cola existente: alta y reprogramación encolan confirmación/recordatorios; cancelación encola `cancelacion`; la reprogramación descarta como obsoletas las notificaciones pendientes de la hora anterior. Un fallo de encolado nunca bloquea la operación (regla dura 5).
- Todos los bodies con `extra='forbid'` y `400` por campo (regla dura 1); RBAC con `401`/`403`; sin migración (modelo, EXCLUDE y trigger append-only ya existen).

## Capabilities

### New Capabilities

- `recepcion-turnos`: operación staff del turno — alta con `origen=recepcion`, reprogramación/cambio de duración, cancelación normal y forzada con motivo, corrección de datos del paciente, transiciones de estado RN-TU-07 y ficha con historial auditable.

### Modified Capabilities

- `notificaciones-mail`: se agrega el descarte de notificaciones obsoletas por reprogramación con motivo `turno_reprogramado` y el panel de fallidas deja de listarlas. No cambia el despacho SMTP, los reintentos ni el contrato de payload.

## Impact

- Backend: `backend/app/modules/turnos/` (`router.py`, `service.py` parametrizado por origen/actor, nuevo `recepcion_service.py`, `schemas.py`), `backend/app/modules/notificaciones/` (`payload.py`, `service.py` — solo el filtro de descarte) y tests nuevos/ajustados.
- API: nuevas rutas y verbos sobre `/api/turnos`; el contrato público de `POST /api/turnos` y `DELETE /api/turnos/{id}?token=` no cambia.
- DB: sin migración; se usan `turno`, `paciente`, `notificacion`, `auditoria_turno`, el EXCLUDE `no_solape_prof` y el trigger append-only existentes.
- Fuera de alcance: frontend de recepción (C-10), reportes (C-11), reprogramación por paciente (PB-08, v1.1), corrección de nombre/email del paciente (solo DNI/tel/OS en v1), alta de profesionales/usuarios (C-11), WhatsApp, pagos y lista de espera.
- Gobernanza: **ALTO**. Riesgos principales: que un cliente sin sesión use el contrato staff, que la reprogramación pise un slot ocupado y que una cancelación forzada quede sin motivo/auditoría. Mitigación: despacho determinista por sesión, lock del profesional + EXCLUDE como autoridad final, y `motivo` obligatorio con auditoría `forzar_cancelacion` en la misma transacción.
