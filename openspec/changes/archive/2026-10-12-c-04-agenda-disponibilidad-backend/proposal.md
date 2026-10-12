# Proposal — c-04-agenda-disponibilidad-backend

## Why

Sin agenda computable no hay reserva posible: hoy existen los modelos C-02 (`Profesional`, `Disponibilidad`, `Bloqueo`, `Turno` + EXCLUDE anti-solape) pero ningún endpoint expone ventanas − bloqueos − ocupados ni permite a recepción mantenerlos. Etapa 6.1 del plan: la disponibilidad pública + la agenda staff son la superficie MVP contra la que C-05 reserva; camino crítico C-02 → C-04 → C-05 — sin este change C-05 no tiene slots que bloquear.

## What Changes

- `GET /api/profesionales` público (solo `activo=true`; columnas explícitas `id, nombre, especialidad, matricula?, duracion_default_min, ultima_actualizacion`; keyset por `id`; sin datos staff internos).
- `GET /api/profesionales/{id}/agenda?vista=dia|semana&fecha=` — vista día/semana con slots ocupados/libres/bloqueados + estado y paciente mínimo para staff; cómputo público de slots según flag (público: solo libres, sin datos paciente).
- `GET /api/disponibilidad?profesional_id=&desde=&hasta=` PÚBLICO, rate-limited 30 req/min/IP: computa `ventanas − bloqueos − turnos activos (reservado, confirmado)` con granularidad `duracion_default_min` del profesional; `cancelado/atendido/ausente` liberan el slot.
- Staff (auth vía interfaz declarada `require_role` de C-03 — este change la CONSUME, no la implementa): `CRUD /api/disponibilidades` (día, desde/hasta, vigencia `vigente_desde/hasta`; validación sin solape mismo profesional+día) + `POST /api/bloqueos` (motivo obligatorio, `creado_por` staff desde sesión).
- Migración `002_agenda_meta`: agrega `profesional.ultima_actualizacion TIMESTAMPTZ NULL` (+ trigger/función que la actualiza ante cualquier write en `disponibilidad`/`bloqueo` del profesional) para UI (mitiga SU-01); backfill `NULL` inicial = "sin datos".
- Decisión bloqueada (binding C-02): overlap de `Disponibilidad` se mantiene **app-level + `SELECT FOR UPDATE` en writes** (NO EXCLUDE temporal) — ver design §3. Contrato para C-05: la reserva revalida el slot contra ventanas/bloqueos/turnos en su propia transacción; no asume invariante DB en disponibilidades.

## Capabilities

### New Capabilities

- `agenda-disponibilidad`: superficie de agenda y disponibilidad — listado público de profesionales, agenda día/semana (staff + pública), cómputo de slots `ventanas − bloqueos − ocupados` con granularidad por profesional, CRUD staff de disponibilidades con validación sin solape app-level, creación de bloqueos, `ultima_actualizacion` por profesional, rate-limit público 30 req/min/IP.

### Modified Capabilities

- Ninguna (C-02 `core-models` / `turno-lifecycle` no cambian de requisitos: se consumen `ix_turno_prof_inicio`, parcial `ix_turno_estado_inicio`, EXCLUDE `[)` y semántica de estados; la columna nueva es aditiva vía migración 002).

## Impact

- APIs nuevas sin overlap con C-03 (rutas propias: `/api/profesionales/*`, `/api/disponibilidad*`, `/api/disponibilidades*`, `/api/bloqueos*`; C-03 posee `/api/auth/*`): coordinación solo lectura de modelos C-02 + consumo de `require_role` como interfaz declarada.
- DB: solo migración aditiva 002 (`ultima_actualizacion` + trigger); sin cambios a tablas C-02 ni al EXCLUDE de turnos; `SELECT FOR UPDATE` confinado a writes de disponibilidades (contención baja, rol recepción/admin).
- C-05 consume el contrato de slot computation + revalidación; C-09/C-10 consumen los GET públicos/agenda; sin frontend en este change.
