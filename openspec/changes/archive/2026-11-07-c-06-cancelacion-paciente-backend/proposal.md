# Proposal — c-06-cancelacion-paciente-backend

## Why

C-05 permite reservar sin login y entrega `token_cancelacion` como única credencial (RN-TU-06, PB-01), pero el paciente todavía no puede liberar el slot: no existe el `DELETE /api/turnos/{id}` público. Sin cancelación con ≥3 h, el turno queda reservado hasta que recepción lo gestione a mano, el slot no se reutiliza y el mail de cancelación que C-08 ya sabe enviar nunca se encola. Este change cierra el Flujo 2 (US-005, RN-TU-04) reutilizando el modelo, el anti-solape y la cola de notificaciones ya implementados: no rediseña C-05, C-08 ni C-07.

## What Changes

- `DELETE /api/turnos/{id}?token=<token_cancelacion>` público, sin login. **ÚNICA credencial el token por query**; no se aceptan DNI+teléfono ni una ruta "mis turnos", y el body no se usa como credencial (GATE 2026-10-11 PB-01 FINAL, RN-TU-06, regla dura 4).
- Regla de anticipación `inicio - now() >= CANCEL_HOURS_MIN` (3 h por config): si cumple, el turno pasa a `cancelado` (soft cancel, sin DELETE físico), el slot queda libre para futuras reservas, se encola el mail `cancelacion` y se escribe `AuditoriaTurno`. Si no cumple → `422` con mensaje y contacto del consultorio (RN-TU-04, US-005 CA-2).
- Credencial inválida, turno inexistente o token que no corresponde → `403` genérico, sin revelar si el turno existe. Turno ya `atendido`, `ausente` o `cancelado` → `422` (Flujo 2, RN-TU-07).
- Idempotencia relativa: una segunda llamada con el mismo token sobre un turno ya cancelado por ese mismo flujo responde `422` "ya cancelado", no reescribe estado, no re-encola mail ni duplica auditoría.
- Mail de cancelación: se encola una `Notificacion` tipo `cancelacion`, `canal=mail`, `estado=pendiente`, con el mismo contrato de `payload` de 11 claves de C-05/C-08. C-06 solo encola; el worker de C-08 la envía aunque el turno esté `cancelado` (no se duplica cola ni lógica de envío).
- Auditoría append-only `AuditoriaTurno(accion="cancelar", actor_id=NULL, detalle)` con actor paciente identificado por el token (nunca el token completo en claro en el detalle).
- Rate limit del endpoint público por IP, coherente con C-05 (`core/ratelimit.py`), para evitar fuerza bruta de tokens y abuso.
- Sin migración: `turno.estado`, `token_cancelacion`, `notificacion`, `auditoria_turno` e índices ya existen; no se agregan columnas, tablas, constraints ni enums.

## Capabilities

### New Capabilities

- `cancelacion-paciente`: cancelación pública del turno por token de cancelación — autenticación con credencial única, regla de ≥3 h, transición a `cancelado` con liberación del slot, respuesta `422` de no-cancelable, `403` genérico, idempotencia relativa, encolado del mail de cancelación, auditoría y rate limit.

### Modified Capabilities

- Ninguna. C-06 consume `reserva-online` (token y contrato de payload), `turno-lifecycle` (transiciones RN-TU-07), `notificaciones-mail` (tipo `cancelacion` ya soportado por C-08), `staff-auth` (403 genérico como precedente de no revelar recursos) y `service-config` (`CANCEL_HOURS_MIN`) sin cambiar sus requisitos. La capa API nueva y su contrato viven en `cancelacion-paciente`.

## Impact

- Backend: `backend/app/modules/turnos/` (nuevo `cancellation_service.py`, ruta `DELETE` en `router.py`, schemas de cancelación), tests nuevos. Se reutilizan `app/models/turno.py`, `app/models/notificacion.py`, `app/models/auditoria.py`, `app/core/ratelimit.py` y `app/core/config.py` (`CANCEL_HOURS_MIN` ya existe con default 3; se agrega `CONSULTORIO_CONTACTO` opcional con default no secreto para el `422` fuera de plazo, también en `.env.example`).
- DB: solo lectura/escritura de `turno`, `notificacion` y `auditoria_turno`; no hay cambios de schema ni migraciones.
- API: nuevo endpoint público `DELETE /api/turnos/{id}?token=`. No cambia ningún contrato de C-03/C-04/C-05/C-08.
- Fuera de alcance: cancelación staff y forzar <3 h con motivo (C-07), reprogramación por paciente (PB-08, v1.1), frontend `GET /cancelar?token=` (C-09), "mis turnos" por DNI+teléfono (descartado por PB-01), worker/envío SMTP/plantillas (C-08), WhatsApp (NO-US-01), pagos y lista de espera.
- Gobernanza: **MEDIO**. Riesgo principal: filtrar existencia de turnos o aceptar una credencial alternativa. Mitigación: `403` uniforme para token inválido/inexistente/mismatch, token solo por query y tests negativos de rutas alternativas. Riesgo secundario: doble cancelación concurrente que duplique mail/auditoría; se mitiga con `SELECT ... FOR UPDATE` del turno y chequeo de estado dentro de la transacción.
