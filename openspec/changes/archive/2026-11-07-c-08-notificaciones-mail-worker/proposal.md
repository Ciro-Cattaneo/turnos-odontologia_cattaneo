# Proposal — c-08-notificaciones-mail-worker

## Why

C-05 dejó las `Notificacion` en `pendiente` con `payload.enviar_en`, pero nadie las envía: sin worker, el paciente nunca recibe la confirmación ni los recordatorios y los fallos SMTP no son visibles para recepción (US-009, RN-NO-01/02). Este change cierra el circuito de mail de v1.

## What Changes

- Worker **en-proceso** con APScheduler (`BackgroundScheduler`) que cada 5–10 min toma una tanda de `Notificacion pendiente` vencidas (`payload.enviar_en <= now`), envía por SMTP y actualiza estado.
- Envío de `confirmacion`, `recordatorio_24h`, `recordatorio_2h` y `cancelacion` (este último encolado por C-06, se envía aunque el turno esté `cancelado`).
- Reintentos con backoff (3 intentos) y transición a `fallida`; `error` persistido para diagnóstico.
- Descarte de recordatorios cuyo turno ya no está activo (`reservado`/`confirmado`); no se envía mail obsoleto.
- `GET /api/notificaciones/fallidas` (solo `recepcion`/`admin`) con paginación keyset y campos mínimos para el panel.
- Configuración SMTP por env (`SMTP_*` ya existen) + `SMTP_TIMEOUT_S`, `NOTIF_WORKER_ENABLED`, `NOTIF_WORKER_INTERVAL_MIN`, `NOTIF_WORKER_BATCH_SIZE`; secretos fuera del repo.
- Plantillas de mail en español con fecha/hora local (`America/Argentina/Buenos_Aires`) y link `GET /cancelar?token=`; sin DNI, teléfono ni obra social en el payload.
- Arranque/parada del scheduler con el `lifespan` de FastAPI y flag para no arrancarlo en tests.
- **Sin migración de base**: se reutilizan `payload.enviar_en`, `estado`, `intentos`, `enviada_at`, `error` y el índice parcial `ix_notif_estado` existente.

## Capabilities

### New Capabilities

- `notificaciones-mail`: envío asíncrono de mails de turno, reintentos/backoff, descarte por turno cancelado, contrato de payload y panel staff de fallidas.

### Modified Capabilities

<!-- Ninguna: C-05 sigue encolando igual y reserva-online no cambia de comportamiento observable. -->

## Impact

- **Backend**: nuevo paquete `backend/app/modules/notificaciones/` (worker, sender SMTP, templates, schemas, router), extensión de `app/core/config.py` y `app/main.py` (lifespan), `backend/requirements.txt` (`apscheduler`).
- **API**: nuevo `GET /api/notificaciones/fallidas` (RBAC staff). No cambia ningún contrato de C-03/C-04/C-05.
- **Operación**: proceso single-host con scheduler en el mismo proceso; `REDIS_URL` sigue solo documentada (sin Redis en v1). Gmail provisorio/PB-05 sin cambios.
- **Tests**: nuevos `backend/tests/test_notificaciones_worker.py` y `test_notificaciones_fallidas.py`; `conftest.py` fija `NOTIF_WORKER_ENABLED=false`.
- **Datos**: no se crean ni alteran tablas, columnas, constraints ni índices.
