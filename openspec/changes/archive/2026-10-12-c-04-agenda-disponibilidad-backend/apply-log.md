# Apply log — c-04-agenda-disponibilidad-backend

Fecha: 2026-10-12. Suite: 170 baseline → 290 final (120 tests C-04 nuevos).
`ruff check backend` limpio. `alembic upgrade head / downgrade -1 / upgrade head`
verificado en PG local (head `001` → `002_agenda_meta` → `001` → `002`).
`openspec validate --strict` en verde.

## 1. LOCK D-3 (app + SELECT FOR UPDATE, NO EXCLUDE temporal)

Decisión binding de C-02, implementada en
`backend/app/modules/disponibilidades/service.py` (`crear_ventana`):

- El overlap de `Disponibilidad` (semanal-recurrente: `dia_semana + hora + vigencia`,
  no un tstz único) se valida en app dentro de transacción corta con
  `SELECT FOR UPDATE` sobre las ventanas del mismo profesional+día
  (`.with_for_update()`), chequeando solape `[hora_desde, hora_hasta)` half-open +
  intersección de vigencia (`None` = abierto).
- NO se agrega EXCLUDE temporal: exigiría materializar rangos
  (`daterange × timerange`) con riesgo de falso rechazo en vigencias disjuntas;
  la contención real (turnos concurrentes) ya la cubre `no_solape_prof`.
- ACs que lo fijan: `test_solapada_mismo_dia_rechazada_409` (409 con detalle del
  conflicto), `test_adyacente_borde_permitida_201` (borde `[)` permitido),
  `test_distinto_profesional_o_dia_permitida_201` (scope `profesional+día`).
- Contrato para C-05 (docstring del servicio): NO asumir invariante DB en
  disponibilidades; la reserva revalida el slot en su transacción
  (`slot_service.compute_slots` + EXCLUDE de turnos, RN-TU-03).

## 2. Firma `require_role` consumida (C-03) vs implementada

- C-04 IMPORTA de `app.modules.auth.deps`: `get_current_staff`, `require_role`,
  `require_own_profesional`, `CurrentStaff`, `DbSession`. Nada reimplementado.
- Firmas consumidas: `require_role("recepcion", "admin")` en escritura
  (disponibilidades POST/DELETE, bloqueos POST); lectura propia odontólogo vía
  `require_own_profesional(profesional_id, staff)` en agenda staff y
  disponibilidades GET. Semántica verificada: sin sesión 401, rol ajeno 403,
  admin pasa todo (`test_agenda_auth_contrato.py`, 4 tests).
- C-03 archivó su firma antes de este apply (contrato estable, verificado en
  `test_contrato_para_c04_importable_y_estable` de C-03 + nuestro
  `test_firma_require_role_consumida_no_duplicada`).

## 3. Notas EXPLAIN (1.4, PG local, tabla casi vacía pero planes por índice)

- `ventanas (profesional+día)`: **Index Scan using `ix_disponibilidad_prof_dia`**
  (Index Cond prof+día, buffers hit, sin seq-scan).
- `turnos activos día y semana (prof + inicio BETWEEN + estado IN
  (reservado,confirmado))`: **Index Scan using `ix_turno_prof_inicio`**
  (Index Cond prof+rango, Filter estado). El planner elige `ix_turno_prof_inicio`
  sobre el parcial `ix_turno_estado_inicio` con tabla vacía; ambos existen y
  ningún plan hace seq-scan sobre `turno` para el rango. Aceptado: el filtro de
  combo `profesional+rango` domina la selectividad del predicado de agenda.
- `bloqueos (prof + OVERLAPS)`: **Bitmap Heap Scan + Bitmap Index Scan on
  `ix_bloqueo_profesional_id`** (Recheck prof, Filter rango), sin seq-scan.
- Decisión derivada: no se agrega índice compuesto de rango en `bloqueo` v1
  (baja frecuencia, bitmap suficiente); re-evaluar si EXPLAIN con volumen
  muestra degradación (puerta documentada, no cambio).

## 4. Decisiones no-obvias fuera de D-1…D-6 (governance MEDIO)

1. `RequestValidationError → 400` global en `app/main.py` (D-6/regla dura 1):
   FastAPI responde 422 por defecto; el contrato exige 400 con detalle por campo
   en todos los schemas. Ningún test C-03 fija 422 (suite verde tras el cambio);
   el login hereda el 400 — coherente con su AC "400 por campo".
2. Router agenda desdoblado: `router` conserva prefix `/api/agenda` (contrato C-01
   fijado por `test_routers_placeholder_registrados_con_prefijos`) y la ruta viva
   `GET /api/disponibilidad` vive en `disponibilidad_router` (prefix `/api`).
3. `GET /api/disponibilidades` (lectura staff) no estaba en tasks como endpoint
   propio pero es necesario para que recepción liste ventanas (el CRUD lo exige);
   con scoping odonto-propio. Sin fuga: columnas explícitas, sin datos paciente.
4. Alcance real de archivos vs 5.2 ("solo toca…"): además de lo listado se tocó
   `app/main.py` (registro + handler 400), `models/profesional.py` (columna 002)
   y `core/ratelimit.py` (límiter público, `REDIS_URL` sigue solo documentada).
   `/api/auth/*` intacto (el diff en `auth/router.py` y `db/seed.py` es previo a
   este apply, trabajo C-03 sin commitear en el workspace).
5. `test_migration_001.py` actualizado (`downgrade -1` → `downgrade base` en el
   test de "elimina todo"): con 2 migraciones, `-1` solo revierte la 002 y dejaba
   la DB de tests en 001 a mitad de sesión (cascada de 31 fallos por columna
   ausente). Intención del AC intacta (baja total + re-upgrade idempotente).
6. `now()` transaccional: el trigger usa `now()` (inicio de transacción); en tests
   con sesión compartida dos writes dan el mismo timestamp — el test de bloqueo
   fija un freshness viejo para observar el avance de forma determinista.
7. `test_health.py` usa `TestClient(app)` sin `base_url` https: no afecta (solo
   health, sin cookies). Sin cambios.
