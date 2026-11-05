# Proposal — c-05-reserva-online-backend

## Why

C-02 dejó el modelo `Turno` con anti-solape en DB y C-04 dejó el cómputo público de disponibilidad, pero todavía no existe la operación que convierte un slot libre en una reserva real. Sin `POST /api/turnos` el paciente no puede reservar sin login y el camino crítico `C-02 → C-04 → C-05` queda cortado. Este change agrega la capa API de reserva online reutilizando lo ya implementado: no rediseña modelos, constraints ni cómputo de slots.

## What Changes

- `POST /api/turnos` público (sin login), rate-limited por IP, con body `{profesional_id, inicio, duracion_min?, paciente:{nombre, dni, telefono, obra_social, email}}`.
- Validación Pydantic estricta (`extra='forbid'`): los cinco datos del paciente son obligatorios; el mail es obligatorio y con formato válido. Faltantes o mail inválido → `400` con detalle por campo (el mail inválido produce un único error en `paciente.email`, PB-02).
- `duracion_min` opcional: si se omite se usa `profesional.duracion_default_min`; si viene, debe ser múltiplo positivo de esa granularidad, si no → `400` explícito en `duracion_min` (no se ignora en silencio).
- Transacción de reserva: `SELECT ... FOR UPDATE` sobre la fila del profesional activo (serializa reservas por profesional, regla dura 2) → validaciones → pre-validación del slot → upsert de `Paciente` por `dni` (actualiza contacto sin duplicar) → crea `Turno` `reservado`/`origen=online` con `token_cancelacion` uuid4 y `fin=inicio+duracion_min` → encola `Notificacion` `confirmacion` + recordatorios según anticipación → escribe `AuditoriaTurno` → commit.
- Pre-validación amable del slot contra la disponibilidad calculada y mapeo de `IntegrityError(no_solape_prof)` a `409` con hasta 5 alternativos del mismo día local; el EXCLUDE sigue siendo la autoridad final y la colisión concurrente deja un solo ganador.
- El encolado de notificaciones no bloquea la reserva: C-05 nunca envía SMTP (el worker es C-08) y un fallo del insert de encolado se aísla en un savepoint.
- Respuesta `201` con resumen del turno, `token_cancelacion` y `cancel_url` (`FRONTEND_URL` + `/cancelar?token=`); el token es la única credencial del paciente.
- Rate limit en `POST /api/turnos` reutilizando `app/core/ratelimit.py` (`429` + `Retry-After`).
- Sin migración: `btree_gist`, `no_solape_prof`, `ck_turno_duracion_min`, `ux_turno_token`, `ux_paciente_dni` y los enums ya existen en `001_core_models`.

## Capabilities

### New Capabilities

- `reserva-online`: contrato de reserva pública sin login — validación de los cinco obligatorios y mail, duración/granularidad, revalidación del slot, anti-solape con alternativos, upsert de paciente por DNI, encolado de notificaciones, auditoría, token de cancelación y rate limit del endpoint.

### Modified Capabilities

- Ninguna. C-05 consume `turno-lifecycle` (estados, token, duración), `paciente-privacidad` (upsert/soft-delete) y `agenda-disponibilidad` (cómputo de slots) sin cambiar sus requisitos. La capa API nueva vive en `reserva-online`.

## Impact

- Backend: `backend/app/modules/turnos/` (router + schemas + servicio de reserva) y tests nuevos; se reutilizan `app/models/*`, `app/modules/agenda/slot_service.py`, `app/core/ratelimit.py` y `app/db/session.py`. No se tocan modelos, migraciones ni rutas de C-02/C-03/C-04.
- DB: solo lectura/escritura de tablas existentes (`paciente`, `turno`, `notificacion`, `auditoria_turno`); no hay cambios de schema.
- Fuera de alcance: worker de envío y reintentos (C-08), cancelación del paciente (C-06), CRUD de recepción/reprogramación (C-07), frontend (C-09/C-10), WhatsApp (NO-US-01) y reportes (C-11).
- Governance: **ALTO**. Riesgo principal: que una carrera entre dos reservas del mismo slot produzca doble reserva o que el manejo del `IntegrityError` impida devolver alternativos. Mitigación: el `SELECT ... FOR UPDATE` del profesional serializa las reservas de ese profesional, el EXCLUDE `no_solape_prof` ya probado queda como autoridad final, el insert va en `begin_nested()` y hay tests de colisión concurrente con un solo ganador y de segunda transacción que espera el lock y termina en `409`. Trade-off: las reservas de un mismo profesional se serializan durante la transacción corta; profesionales distintos no se bloquean entre sí.
