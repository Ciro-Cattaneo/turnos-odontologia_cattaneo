# Design — c-04-agenda-disponibilidad-backend

## Context

C-02 dejó 8 tablas migradas (`001_core_models`): `Profesional` (sin `ultima_actualizacion`), `Disponibilidad` (`ck_disponibilidad_horario` + `ix_disponibilidad_prof_dia`, overlap solo validación app según docstring del modelo), `Bloqueo`, `Turno` con EXCLUDE `no_solape_prof` half-open `[)` + parcial `ix_turno_estado_inicio` + `ix_turno_prof_inicio`. `main.py` ya monta routers stub por dominio (`agenda`, `profesionales`, `turnos`, ...). C-03 diseña en paralelo `require_role` + cookie httpOnly — este change lo consume como interfaz declarada (sin implementarlo, sin tocar `/api/auth/*`). Ver proposal.md (Why) y spec `agenda-disponibilidad`.

## Goals / Non-Goals

**Goals:**

- Superficie legible mínima para reservar: profesionales públicos + slots `ventanas − bloqueos − ocupados` con granularidad por profesional y semántica `[)` coherente con C-02.
- Escritorio recepción funcional: CRUD ventanas + bloqueo con motivo, con `ultima_actualizacion` confiable para UI (SU-01).
- Contrato consumible por C-05: revalidación del slot en la transacción de reserva (este change documenta qué garantiza y qué no).

**Non-Goals:**

- No implementar auth/RBAC (`require_role`, login, scoping odontólogo) — solo declararlo como dependencia de C-03 con firmas esperadas.
- No crear/editar turnos, notificaciones ni reportes (C-05/C-07/C-08/C-11).
- No frontend (C-09/C-10); no CSV (PB-06); no WhatsApp (NO-US-01).
- No cambiar el EXCLUDE de turnos ni los índices C-02.

## Decisions

### D-1. Un único servicio `slot_service` puro + routers delgados

Qué: `backend/app/modules/agenda/slot_service.py` (función pura `compute_slots(ventanas, bloqueos, turnos_activos, duracion_min, desde, hasta, tz)`) consumida por `GET /api/disponibilidad` y `GET .../agenda`; routers (`agenda`, `profesionales`, nuevos `disponibilidades`, `bloqueos`) solo validan schemas (`extra='forbid'`), chequean auth en staff, y emiten SQL parametrizado con columnas explícitas.
Por qué sobre alternativas: alternativa era duplicar el cómputo en cada endpoint — diverge en el borde `[)`; un único puro es testeable con matriz parametrizada sin DB y reutilizable por C-05 en su revalidación.
Queries: ventanas por `ix_disponibilidad_prof_dia`; turnos activos por parcial `ix_turno_estado_inicio` + `ix_turno_prof_inicio` (filtro `profesional_id + inicio BETWEEN + estado IN (...)`); bloqueos por `ix_bloqueo_profesional_id` + filtro `desde/hasta OVERLAPS` con `daterange`/`tstzrange` donde el planner lo aproveche. Agenda día/semana pagina por keyset (`fecha` cursor), jamás OFFSET.

### D-2. `ultima_actualizacion` vía trigger DB (no solo app)

Qué: migración `002_agenda_meta`: `ALTER TABLE profesional ADD COLUMN ultima_actualizacion TIMESTAMPTZ NULL` + función/trigger `touch_profesional_updated()` en `AFTER INSERT/UPDATE/DELETE ON disponibilidad, bloqueo` (backfill `NULL` = "sin datos").
Por qué sobre alternativa app-only: alternativa era actualizar la columna en cada handler — se olvida en un path (seed, script, futuro C-11) y la UI miente (riesgo SU-01/RN-TU-05); el trigger hace el invariante "todo write toca freshness" a nivel DB, observable desde cualquier cliente. Costo: trigger trivial por write de baja frecuencia (recepción, no hot path). Rollback: `downgrade` elimina trigger/función/columna.

### D-3. LOCK — Overlap de `Disponibilidad`: app-level + `SELECT FOR UPDATE` (NO EXCLUDE temporal) ✅

Decisión bloqueada (binding C-02): **mantener validación en app dentro de transacción corta con `SELECT FOR UPDATE` sobre las ventanas del profesional+día; NO agregar EXCLUDE temporal.**

Justificación (3 puntos):

1. El dominio es semanal-recurrente (`dia_semana + hora_desde/hasta + vigencia`), no un rango tstz único — un EXCLUDE exigiría materializar rangos (`daterange × timerange` o expansión por fecha) o una columna generada frágil; el costo de modelado y el riesgo de falso rechazo (vigencias disjuntas que comparten día/hora) superan el beneficio para writes de bajísima contención (recepción edita horarios, no cientos de concurrentes).
2. La contención real que exige invariante DB duro es la de **turnos** (pacientes concurrentes sobre el mismo slot) — ya cubierta por `no_solape_prof` EXCLUDE `[)`; las ventanas cambian por staff serializado, donde `SELECT FOR UPDATE` + re-chequeo del solape en la misma transacción es suficiente y mantiene transacciones cortas (supabase-postgres-best-practices: lock solo donde la contención lo justifica).
3. Alternativa considerada (EXCLUDE con `gist (profesional_id WITH =, daterange(vigente_desde, vigente_hasta) WITH &&, timerange... )`): rechazada por requerir extensión/tipos adicionales, intersección vigencia-vs-día sutil, y mensajes 409 menos explicativos que la validación app (que devuelve el rango en conflicto para la UI).

Contrato para C-05 (consume esto): **no asumir invariante DB en disponibilidades**; la reserva revalida en su transacción que el slot pedido cae dentro de una ventana vigente, fuera de bloqueos y sin turno activo solapado (usa `slot_service` + `SELECT FOR UPDATE`/EXCLUDE de turnos según RN-TU-03). ACs que lo fijan: spec §"CRUD staff…" escenarios 409-solape, borde-adyacente-permitido y distinto-profesional/día-permitido.

### D-4. Auth consumida como interfaz declarada (contrato con C-03)

Qué: staff endpoints declaran `Depends(require_role("recepcion", "admin"))` para disponibilidades/bloqueos (lectura propia odontólogo: `require_role("odontologo",...)` + chequeo `profesional_id` propio — implementado por C-03, aquí solo la firma consumida); públicos sin `Depends`. Errores: sin sesión → 401, rol insuficiente → 403 genérico.
Por qué: evita colisión con el agente C-03 (mismo `UsuarioStaff`, distinto router); si C-03 aún no mergeó, los tests de este change usan un stub de dependencia (`app.dependency_overrides`) marcado como borde, no como mock interno de lógica.

### D-5. Rate-limit 30 req/min/IP en capa app con ventana fija + headers

Qué: middleware/dependencia sobre `GET /api/disponibilidad` (y GETs públicos de profesionales) con contador por IP (memoria en-proceso v1, clave `REDIS_URL` solo documentada para escalar), ventana fija 60s, respuesta 429 + `Retry-After` al exceder; tests con reloj fake.
Por qué sobre token-bucket distribuido: volumen v1 es single-host y el objetivo es anti-scraping (RN-AU-03), no fairness fina; ventana fija es suficiente y auditable en tests de borde (30 ok / 31 rechazado).

### D-6. Respuestas y códigos explícitos

Qué: 200 lectura/201 creación/400 por campo (`extra='forbid'`, Pydantic estricto)/401 sin sesión/403 rol o token genérico (no aplica aquí pero coherente)/404 profesional inexistente/409 solape disponibilidad/422 reservado para estados (turnos, no este change)/429 rate-limit. OpenAPI documenta cada router. `duracion_min` del slot = `duracion_default_min` vigente al computar; TZ `America/Argentina/Buenos_Aires` display, UTC persistido (hard rule 10).

## Risks / Trade-offs

- [Riesgo] Recepción no carga ventanas → slots vacíos parecen "sistema roto" → Mitigación: `ultima_actualizacion=NULL` + UI "sin datos" + spec escenario sin-ventana→vacío (no inventar horarios); SU-01 mitigado, no eliminado.
- [Riesgo] Doble write concurrente de ventanas elude el chequeo app sin EXCLUDE → Mitigación: `SELECT FOR UPDATE` serializa por profesional+día; frecuencia despreciable; C-05 no depende de este invariante para correctitud de reservas.
- [Riesgo] Rango `desde/hasta` amplio degrada el cómputo → Mitigación: tope 31 días (400 si se excede) + columnas explícitas + índices C-02; EXPLAIN en tasks para validar uso de `ix_turno_prof_inicio`/parcial.
- [Trade-off] Trigger DB vs app-only freshness: se acepta lógica mínima en DB a cambio de invariante total; documentado en migración 002 con `downgrade` completo.
- [Riesgo] Divergencia con C-03 en la firma `require_role` → Mitigación: este change declara la firma esperada en tasks y usa `dependency_overrides` en tests; el apply no mergea hasta que C-03 archive su firma (nota de coordinación en tasks).

## Migration Plan

1. `alembic upgrade 001 → 002_agenda_meta` (aditiva: columna nullable + trigger; sin backfill destructivo; `downgrade` revierte trigger/función/columna).
2. Deploy routers nuevos bajo `/api/*` existentes (sin breaking: no se tocan rutas C-01/C-02/C-03).
3. Rollback: `downgrade -1` + redeploy sin los routers (los GET públicos responden 404 tras rollback — ventana breve, sin pérdida de datos).

## Open Questions

Ninguna bloqueante. Menor (no cambia specs ni tasks): nombre exacto del módulo de rate-limit (`app/core/rate_limit.py` vs dependencia local en `agenda/`) — se resuelve en apply según lo que C-03 haya creado para login, reutilizando si existe.
