# Apply log — c-05-reserva-online-backend

Fecha: 2026-11-04 (lotes A/B) y 2026-11-05 (lotes C/D). **Lote A** (§1
contrato/schemas/validación + §2 reserva feliz y persistencia), **lote B** (§3
disponibilidad, anti-solape, alternativos, concurrencia real y profesional),
**lote C** (§4 notificaciones no bloqueantes) y **lote D** (§5 rate limit +
§6 integración/cierre). Suite: **290 baseline → 309** al cerrar A, **324** al
cerrar B, **335** al cerrar D (5 tests de §4 ya existentes sin contabilizar en
324 + 6 nuevos de §5/R9). `python -m ruff check backend` limpio en todos los
lotes. Sin migración (ver §1.1). **Change completo: 37/37 tareas.**

- Evidencia final §6.1: `python -m pytest backend/tests/test_reserva_online.py
  backend/tests/test_turno_schemas_400.py -q` → **45 passed**;
  `python -m ruff check backend` → **All checks passed!**.
- Evidencia final §6.2: `python -m pytest backend/tests -q` → **335 passed**,
  sin regresiones C-02/C-03/C-04.
- Evidencia final §6.4: `openspec validate c-05-reserva-online-backend
  --strict` → **Change 'c-05-reserva-online-backend' is valid**.

## 1.1 Verificación de migración (precondición de D-13)

- `rg` no está en el PATH de este host; la verificación se hizo con
  `Select-String`/grep sobre `backend/alembic/versions/001_core_models.py`:
  aparecen `no_solape_prof` (línea 40), `ck_turno_duracion_min` (180),
  `ux_turno_token` (188) y `ux_paciente_dni` (85). No hace falta migración.
- `python -m alembic -c backend/alembic.ini current` → `002_agenda_meta (head)`.
- C-05 **no toca** `backend/app/models/` ni `backend/alembic/versions/`; el
  `git status --short` del lote solo muestra `backend/app/modules/turnos/`
  (`router.py` modificado, `schemas.py`/`service.py` nuevos), los dos tests
  nuevos, `tasks.md` y este log, más los `.pyc` de `__pycache__` regenerados
  por la ejecución de tests (artefactos de build, no fuente).
- Conclusión: D-13 se sostiene; no hay `downgrade` ni cambio de schema.

## D-1. Router delgado + servicio + schemas

- `backend/app/modules/turnos/schemas.py`: `TurnoCreate`, `PacienteIn`,
  `TurnoOut`, `AlternativoOut`/`AlternativosOut` (estos últimos preparados para
  §3) con `ConfigDict(extra="forbid")` en raíz y anidados.
- `backend/app/modules/turnos/service.py`: `reservar()` concentra la
  transacción; `backend/app/modules/turnos/router.py` solo parsea el body,
  inyecta el reloj y delega. Se reutiliza `agenda.slot_service` (sin duplicar
  el cómputo de slots).
- El router ya estaba registrado en `app/main.py`; no hubo que tocarlo.

## D-2. Lock por profesional + EXCLUDE como autoridad final

- Implementado: `SELECT ... FOR UPDATE` sobre `profesional` al inicio de la
  transacción (`with_for_update()`), antes de validar o escribir.
- El insert del `Turno` va en `db.begin_nested()` (SAVEPOINT); un
  `IntegrityError` se inspecciona por `diag.constraint_name` con fallback
  textual (`_nombre_constraint`):
  - `no_solape_prof` → `SlotOcupado` (sin rollback dentro del insert); el
    servicio computa alternativos, hace `db.rollback()` y responde
    `409 slot_ocupado`;
  - `ux_turno_token` → reintento único con token uuid4 nuevo;
  - otro → `500` genérico.
- Lote B: `test_reserva_segunda_transaccion_espera_lock_409` y
  `test_reserva_exclude_autoridad_final_409` ejercitan el lock y el EXCLUDE con
  dos conexiones/transacciones reales; ambos verdes. El cálculo de alternativos
  se comparte entre la pre-validación y el camino `SlotOcupado`.

## D-3. Upsert atómico de `Paciente` por DNI

- `INSERT ... ON CONFLICT (dni) DO UPDATE SET nombre, telefono, obra_social,
  email, updated_at=now() RETURNING id` vía `pg_insert(Paciente)` +
  `on_conflict_do_update` (SQL parametrizado).
- No se toca `activo`: un paciente `activo=false` sigue inactivo (R1 S4).
  Decisión cerrada de D-3, verificada por
  `test_reserva_paciente_inactivo_no_reactiva_201`.
- Detalle no obvio: `paciente.id` tiene default Python (`uuid.uuid4`), no
  server default; el upsert provee el `id` explícitamente.

## D-4. Validación estricta y error por campo

- `PacienteIn`: los cinco campos obligatorios, `trim` previo a `min_length=1`
  (vacío/solo espacios = faltante), `email` con `str` + patrón (sin
  `EmailStr`, por `.test`).
- `TurnoCreate.inicio`: validador que exige `tzinfo`/`utcoffset`; el error usa
  `PydanticCustomError("inicio_sin_zona", ...)` para que `tipo` sea
  `inicio_sin_zona` (R2 S7).
- `parse_body_or_400` normaliza el `loc` quitando el prefijo `body` y devuelve
  `detail: [{campo, error, tipo}]`.
- Verificado por los 6 tests de `test_turno_schemas_400.py`.

## D-5. Duración default o múltiplo positivo

- `_validar_duracion`: si `duracion_min` se omite usa
  `profesional.duracion_default_min or 30`; si viene, debe ser > 0 y múltiplo
  exacto. No múltiplo → `400` único con
  `tipo="duracion_no_multiplo_granularidad"`; 0/negativa → `400` único
  `tipo="duracion_invalida"`. Sin escrituras.
- Verificado por R1 S2, R3 S1 y R3 S2.

## D-6. Revalidación del slot con `slot_service`

- `_slots_del_dia` carga ventanas/bloqueos/turnos activos del día local y
  computa con `compute_slots` (misma semántica `[)` y TZ).
- `_slot_disponible` exige que cada sub-slot de la granularidad cubra
  `[inicio, fin)`; un `inicio` no alineado o un bloque contiguo incompleto no
  está en el conjunto de libres.
- Si no está disponible: `409` con `codigo` clasificado (lote B):
  - `slot_ocupado` si un turno activo cubre el `inicio` pedido
    (`_inicio_ocupado`: `t.inicio <= inicio < t.fin`);
  - `slot_no_disponible` en cualquier otro caso (fuera de ventana, bloqueo,
    desalineado, segundo slot de un bloque ocupado).
- `_alternativos` agrupa los slots libres del mismo día local en bloques de la
  duración pedida (múltiplo de la granularidad), excluye el `inicio` pedido,
  ordena ascendente, devuelve hasta 5 y serializa `inicio`/`fin` como ISO-8601
  UTC. Se computa antes del `rollback` para no perder el snapshot.

## D-7. Notificaciones en savepoint y `payload.enviar_en`

- `confirmacion` siempre; `recordatorio_24h` solo si
  `inicio - 24h > now`; `recordatorio_2h` solo si `inicio - 2h > now`
  (comparación estricta). Estado `pendiente`, `intentos=0`,
  `enviada_at=NULL`; C-05 no envía SMTP.
- El bloque de inserts va en su propio `begin_nested()`; si falla, solo se
  revierte ese savepoint y la reserva sigue con
  `notificaciones_encoladas=false` (regla dura 5). El test de fallo simulado
  es §4.1 (lote C).
- `payload` mínimo: `turno_id`, `tipo`, `enviar_en`, `paciente_nombre`,
  `paciente_email`, `profesional_nombre`, `inicio`, `fin`, `duracion_min`,
  `token_cancelacion`, `cancel_url`. Sin DNI, teléfono ni obra social.
  `enviar_en`, `inicio` y `fin` son strings ISO-8601 UTC (`+00:00`), no
  objetos `datetime` (JSONB).
- Interpretación H-14: “siempre encolados” = sin fallback por falta de mail
  (el mail es obligatorio); los recordatorios se condicionan por anticipación,
  no por ausencia de mail.
- Punto de coordinación con C-08: el worker consumirá `payload.enviar_en`; si
  necesita una columna propia, la agrega en su change con migración.

## D-8. Auditoría append-only en la misma transacción

- `AuditoriaTurno` con `accion="crear"`, `actor_id=NULL` (acción del paciente),
  `detalle={origen:"online", profesional_id, inicio, fin, duracion_min,
  notificaciones_encoladas}`; `inicio`/`fin` como strings ISO-8601 UTC.
- Se escribe después del encolado y antes del commit. El trigger
  `auditoria_no_update_delete` de `001` sigue siendo la garantía append-only.

## D-10. Tiempo: `inicio` aware, futuro y día local

- `inicio` sin zona → `400 inicio_sin_zona` (schema). Se normaliza a UTC para
  persistir. `inicio <= now` → `400 campo=inicio`.
- Reloj inyectable: `service.now_utc` + dependencia `get_now_provider` en el
  router; los tests lo sobrescriben con `app.dependency_overrides` (sin
  sleeps). El día local se obtiene con `inicio.astimezone(TZ).date()`.

## D-11. Contrato HTTP y respuesta

- `201` con `id`, `estado=reservado`, `inicio`, `fin`, `duracion_min`,
  `profesional{id,nombre}`, `paciente{nombre,dni,email}`,
  `token_cancelacion`, `cancel_url`, `notificaciones_encoladas`.
- `cancel_url = FRONTEND_URL.rstrip("/") + "/cancelar?token=" + token`
  (probado con `https://app.test/` → sin doble barra).
- `400` por campo; `404` genérico; `409` con `detail.codigo`; `500` genérico.
  `TurnoOut` usa `extra="forbid"`.
- `inicio`/`fin` de la respuesta son strings ISO-8601 UTC.

## D-12. Orden transaccional y límites de fallo

Orden implementado en `reservar()`:
1. `SELECT ... FOR UPDATE` del profesional activo (404 si no existe/inactivo);
2. validar duración e `inicio` futuro (400 tempranos, sin escrituras);
3. pre-validar el slot con `slot_service` (409 temprano, sin escrituras);
4. upsert de paciente por DNI;
5. insertar `Turno` en `begin_nested()`;
6. insertar `Notificacion` en `begin_nested()` aislado;
7. insertar `AuditoriaTurno`;
8. `commit` y respuesta `201`.

Un 400/409 temprano no deja escrituras; un `409` por colisión revierte todo
(incluido el upsert); un fallo de encolado solo revierte su savepoint.

## D-13. Sin migración

Ver §1.1: no hay cambios de schema, modelos, constraints ni índices. El
`payload` JSONB cubre la programación de recordatorios.

## D-9. Rate limit del endpoint público (lote D)

- Implementado en `backend/app/modules/turnos/router.py` como dependencia de
  operación (`dependencies=[Depends(public_reserva_throttle)]`), de modo que
  corre **antes** de parsear el body. Clave `turnos-publico:{ip}`, ventana fija
  60 s, límite 10/min/IP; excedido → `429` con
  `Retry-After: max(1, int(retry) + 1)` (misma fórmula que la agenda de C-04).
- Reutiliza `core.ratelimit.check_public_rate_limit(key, limit=10, window_s=60)`;
  el reloj fake se inyecta parcheando `time.monotonic` (módulo global que usa
  `ratelimit`) y la IP se inyecta con `get_client_ip` overrideable. No se usan
  sleeps.
- El cupo es por IP y no comparte estado con el limitador de login ni con el
  público de agenda (claves distintas). En v1 el contador es en-proceso.
- Punto abierto: el valor 10/min es ajustable sin cambiar la spec (ver
  "Puntos abiertos").

## Evidencia TDD (lote A)

| Tarea | Archivo de test | Capa | Safety net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| 1.1 | — (proceso) | migración | `pytest backend/tests -q` (290) | N/A | verificación de constraints + `alembic current` | `git status` sin modelos/migraciones | N/A |
| 1.2 | `test_turno_schemas_400.py` | schemas/API | suite base 290 | `ModuleNotFoundError` confirmado | 6 passed tras 1.3 | 6 escenarios R2 S1-S5/S7 | imports/orden ruff |
| 1.3 | `test_turno_schemas_400.py` | schemas/API | 1.2 rojo | (1.2) | 6 passed | faltantes/vacíos/email/extra anidado/extra raíz/sin zona | `parse_body_or_400` reutilizable |
| 1.4 | `test_reserva_online.py` | API/servicio | 11 tests previos | `ImportError get_now_provider` | 5 passed | inicio igual/anterior; duración 0/-30 parametrizadas | helper `_error` |
| 2.1 | `test_reserva_online.py` | API/DB | 11 previos | `NotImplementedError` | 1 passed | — | servicio transaccional |
| 2.2 | `test_reserva_online.py` | API/DB | 12 previos | mutación `default→30` mata el test | 1 passed | default 45 | — |
| 2.3 | `test_reserva_online.py` | API/DB | 13 previos | mutación `DO UPDATE→DO NOTHING` mata el test | 1 passed | una fila/reutiliza id | — |
| 2.4 | `test_reserva_online.py` | API/DB | 14 previos | mutación `activo=True` en el upsert mata el test | 1 passed | contacto actualizado + `activo=false` | — |
| 2.5 | `test_reserva_online.py` | DB/servicio | 15 previos | mutación `accion` mata el test | 1 passed | ISO-8601 UTC parseable | — |
| 2.6 | `test_reserva_online.py` | API/DB | 16 previos | mutación `rstrip` mata el test | 1 passed | `FRONTEND_URL` con barra final | — |
| 2.7 | `test_reserva_online.py` | DB/servicio | 17 previos | mutación `recordatorio_24h` mata el test | 2 passed | >24h (3) y 2-24h (2); `enviar_en` ISO | — |

Nota: 2.2–2.7 comparten la implementación genérica que pidió el RED de 2.1; se
validó que cada test mata una mutación dirigida (script temporal, restaurado
después) para descartar tests que pasan por casualidad.

## Evidencia TDD (lote B)

| Tarea | Archivo de test | Capa | RED | GREEN | TRIANGULATE | MUTACIÓN |
|---|---|---|---|---|---|---|
| 3.1 | `test_reserva_online.py` | API/DB | `duracion_min=60` no cubría dos slots | 1 passed | bloque de 2 slots | `_validar_duracion` ignora el pedido → mata |
| 3.2 | `test_reserva_online.py` | API/servicio | `alternativos=[]` | 2 passed | fuera de ventana + bloqueo | `_alternativos` devuelve `[]` → mata |
| 3.3 | `test_reserva_online.py` | API/servicio | `alternativos=[]` | 1 passed | `09:15` no alineado | `_alternativos` devuelve `[]` → mata |
| 3.4 | `test_reserva_online.py` | API/DB | `alternativos=[]` | 1 passed | primer slot libre / segundo ocupado | `_slot_disponible` solo mira el primero → mata |
| 3.5 | `test_reserva_online.py` | API/DB | ya verde con la implementación de A | 1 passed | borde `fin=hora_hasta` | `while cursor <= fin` → mata |
| 3.6 | `test_reserva_online.py` | API/servicio | `alternativos=[]` | 1 passed | mismo día, duración 60, máx. 5, orden | `_alternativos` devuelve `[]` → mata |
| 3.7 | `test_reserva_online.py` | API/DB | ya verde con la implementación de A | 1 passed | solo reservado/confirmado ocupan | `ESTADOS_ACTIVOS` incluye cancelado → mata |
| 3.8 | `test_reserva_online.py` | API/DB | `codigo=slot_no_disponible` | 1 passed | turno activo cubre el inicio | `_inicio_ocupado` siempre `False` → mata |
| 3.9 | `test_reserva_online.py` | DB/servicio (concurrencia real) | 2.ª tx esperaba el lock | 1 passed | thread B bloqueado y luego 409 | (cubierto por el RED real) |
| 3.10 | `test_reserva_online.py` | DB/servicio (concurrencia real) | insert esperaba el EXCLUDE | 1 passed | thread B bloqueado y luego 409 | (cubierto por el RED real) |
| 3.11 | `test_reserva_online.py` | API/DB | ya verde con la implementación de A | 1 passed | contiguo `[)` no solapa | `_solapa` inclusivo → mata |
| 3.12 | `test_reserva_online.py` | API/DB | ya verde con la implementación de A | 3 passed | inexistente/inactivo/activo | `prof.activo` ignorado → mata |

Nota: 3.5/3.7/3.11/3.12 ya pasaban con la implementación del lote A; se validó
que cada uno mata una mutación dirigida (edit temporal, restaurado después)
para descartar falsos verdes. 3.9/3.10 usan `threading` + conexiones reales
(`Session(bind=test_engine)`), con setup commiteado y limpieza SQL cruda.

## Fixture de 409: setup commiteado

Durante el lote B se confirmó con pruebas dirigidas que, en `db_session`
(`Session(bind=conn)` con `txn` externa), `session.commit()` commitea un
savepoint (la `txn` externa sigue viva y su rollback descarta todo), pero
`session.rollback()` **revierte la transacción externa completa**. Como el
servicio hace `rollback()` en los 409 (D-12), los tests de 409 usan el fixture
`client_commit` (sesión de request independiente sobre `test_engine`) y crean
el setup con sesiones que commitean (`_setup_concurrencia`,
`_bloqueo_commit`, `_turno_activo_commit`), limpiando en `finally`. Esto
también evita el `SAWarning: transaction already deassociated` en esos tests.

## Lote C — Notificaciones no bloqueantes (§4)

- Los 5 tests de §4 ya existían en `backend/tests/test_reserva_online.py` y
  pasaron en verde sin cambios de código (R6 S1–S5). Se verificó con
  `pytest ... -k "encolado_falla or pendientes_para_worker or anticipacion..."`
  → **5 passed**. La implementación es la de D-7 (savepoint aislado, comparación
  estricta de anticipación).
- **4.6 Contrato de `Notificacion.payload`:** claves `turno_id`, `tipo`,
  `enviar_en`, `paciente_nombre`, `paciente_email`, `profesional_nombre`,
  `inicio`, `fin`, `duracion_min`, `token_cancelacion`, `cancel_url`. Datos
  mínimos para el mail; **sin DNI, teléfono ni obra social**. `enviar_en`,
  `inicio` y `fin` son strings ISO-8601 UTC (`+00:00`) por ser JSONB (nunca
  objetos `datetime`). Verificado por `test_reserva_notificaciones_pendientes_para_worker`
  y `test_reserva_anticipacion_mayor_24h_encola_tres`.
- **H-14 — interpretación de “siempre encolados”:** no existe fallback por
  falta de mail (el mail es obligatorio, RN-TU-01/PB-02); la `confirmacion` se
  encola siempre. Los recordatorios dependen de la anticipación, no del mail:
  `recordatorio_24h` si `inicio - 24h > now`, `recordatorio_2h` si
  `inicio - 2h > now` (comparación estricta, RN-NO-01). Sin envío SMTP en C-05.
- **Decisión cerrada de paciente inactivo:** una reserva con `Paciente.activo=false`
  procede (`201`), actualiza solo contacto y **no reactiva** la fila (D-3/R1 S4,
  PB-04). Una reactivación explícita, si recepción la necesita, es de C-07/admin.
  Cubierto por `test_reserva_paciente_inactivo_no_reactiva_201`.
- **Coordinación con C-08:** el worker consumirá `payload.enviar_en` para
  programar los recordatorios; C-05 no agrega columna ni migración. Si C-08
  necesita una columna propia (`enviar_en TIMESTAMPTZ`), la agrega en su change
  con migración y backfill. Contrato estable: las claves de D-7 no cambian.

## Lote D — Rate limit e integración (§5–§6)

- **§5:** `public_reserva_throttle` en `router.py` con `turnos-publico:{ip}`,
  10/min/IP, ventana fija 60 s y `429 + Retry-After` (D-9). Corre antes del
  parseo del body; la IP se resuelve con `get_client_ip` (overrideable en
  tests). Los tests usan un reloj fake (`monkeypatch` de `time.monotonic`) y un
  holder mutable de IP; sin sleeps. La 11.ª reserva no crea `turno`.
- **Hueco R9 cerrado:** se agregaron `test_reserva_tokens_distintos_por_turno`,
  `test_reserva_sin_login_201` y `test_reserva_dni_telefono_raiz_400`, y se
  amplió el texto de la tarea 2.6 para mencionarlos (coherencia de trazabilidad
  R9 → 2.6). Los tres son verdes y se validó que matan una mutación dirigida
  (token fijo, `extra="ignore"`).
- **§6.3 alcance:** `git status --short` solo muestra
  `backend/app/modules/turnos/{router.py (M), schemas.py, service.py}`,
  `backend/tests/{test_reserva_online.py, test_turno_schemas_400.py}`,
  `openspec/changes/c-05-reserva-online-backend/{tasks.md, apply-log.md}` y los
  `.pyc` de `__pycache__` (artefactos de build). Sin cambios en
  `backend/app/models/`, `backend/alembic/versions/`, `CHANGES.md`, `AGENTS.md`,
  `CLAUDE.md`, `README.md` ni `.atl/skill-registry.md`.
- **§6.4:** `openspec validate c-05-reserva-online-backend --strict` → válido;
  `openspec status --change ... --json` → `isPlanningComplete: true`,
  `isComplete: true`.

## Evidencia TDD (lotes C y D)

| Tarea | Archivo de test | Capa | RED | GREEN | TRIANGULATE | MUTACIÓN / nota |
|---|---|---|---|---|---|---|
| 4.1 | `test_reserva_online.py` | API/servicio (mock de borde) | ya existía; `201` con fallo simulado | 1 passed | turno + auditoría persistidos, `notificaciones_encoladas=false` | mock del borde `service.Notificacion` (no interno) |
| 4.2 | `test_reserva_online.py` | DB/servicio | ya existía | 1 passed | `pendiente/0/NULL`, `enviar_en` ISO | cubre contrato del payload |
| 4.3 | `test_reserva_online.py` | DB/servicio | ya existía | 1 passed | <2h → solo confirmación | comparación estricta |
| 4.4 | `test_reserva_online.py` | DB/servicio | ya existía | 1 passed | 24h exactas → sin recordatorio_24h | borde estricto |
| 4.5 | `test_reserva_online.py` | DB/servicio | ya existía | 1 passed | 2h exactas → sin recordatorio_2h | borde estricto |
| 4.6 | — (contrato) | documentación | N/A | apply log escrito | `enviar_en` en 3 tests | lectura + contrato C-08 |
| 5.1 | `test_reserva_online.py` | API/dependencia | `ImportError get_client_ip` | 1 passed | 201 + exactamente 1 cupo consumido | throttle no-op → mata |
| 5.2 | `test_reserva_online.py` | API/dependencia | `ImportError get_client_ip` | 1 passed | 9→10 = 201, 11 = 429 + `Retry-After`, 1 turno | throttle no-op / clave global → mata |
| 5.3 | `test_reserva_online.py` | API/dependencia | `ImportError get_client_ip` | 1 passed | IP A agotada → 429, IP B → 201 | clave global (sin IP) → mata |
| R9 S1 | `test_reserva_online.py` | API/DB | pasaba con la implementación | 1 passed | dos slots, tokens distintos y no nulos | token fijo → mata (500 por `ux_turno_token`) |
| R9 S2 | `test_reserva_online.py` | API/DB | pasaba con la implementación | 1 passed | sin cookie/header → 201 + token | contrato de no-auth |
| R9 S3 | `test_reserva_online.py` | API/DB | pasaba con la implementación | 1 passed | `dni`/`telefono` raíz → 400, sin turno | `extra="ignore"` → mata |

Nota: R9 S1–S3 ya pasaban con la implementación de A/B; se aplicó una mutación
dirigida temporal (token fijo para S1, `extra="ignore"` para S3) y se restauró,
confirmando que los tests no pasan por casualidad. Para S2 la garantía es el
contrato (no hay dependencia de auth en el endpoint).

## Decisiones no obvias nuevas (lote C/D)

8. **`time` está shadoweado en `test_reserva_online.py`:** el módulo se importa
   como `time as time_module` porque `from datetime import time` ya ocupa el
   nombre; el reloj fake parchea `time_module.monotonic` (el mismo objeto
   módulo que usa `ratelimit`).
9. **IP inyectable sin confiar en headers:** `get_client_ip` lee
   `request.client.host`; los tests lo overridean con un holder mutable. No se
   usa `X-Forwarded-For` (no confiable sin proxy propio).
10. **Orden dependencia → body:** el throttle va en
    `dependencies=[...]` de la operación, garantizando que el `429` se emita
    antes de validar el body y sin crear turno.
11. **`Retry-After` conservador:** se replica `max(1, int(retry) + 1)` de C-04
    (redondeo hacia arriba implícito) para no invitar a reintentar antes del
    reset exacto.

## Puntos abiertos / coordinación

- **Contrato de payload con C-08:** estable en D-7; el worker consume
  `payload.enviar_en`. Si C-08 necesita columna propia, la agrega con migración
  en su change (no en C-05).
- **Límite exacto de rate limit:** 10/min/IP (D-9). Ajustable sin cambiar la
  spec si operación pide otro valor; solo se toca `RATE_LIMIT` en el router.
- Sin otros pendientes: **change completo (37/37)**; próximo paso
  `/opsx:archive c-05-reserva-online-backend` bajo orden explícita.

## Decisiones no obvias / desviaciones

1. `rg` no está en PATH; 1.1 se verificó con `Select-String`/grep.
2. `paciente.id` no tiene server default; el upsert pasa `uuid4()` explícito.
3. **Corrección del lote B:** en `db_session` (`Session(bind=conn)` con `txn`
   externa), `session.rollback()` revierte la transacción exterior completa
   (no solo un savepoint). Por eso los tests de 409 usan `client_commit` con
   setup commiteado; en producción el `rollback()` revierte la transacción
   real, que es lo buscado por D-12.
4. El `409` de disponibilidad ya devuelve alternativos reales (mismo día,
   duración pedida, máx. 5) y clasifica `slot_ocupado` vs `slot_no_disponible`
   según si un turno activo cubre el `inicio` pedido (lote B).
5. El mapeo `IntegrityError` a `SlotOcupado` y el reintento de token están
   cubiertos por §3.9/§3.10 (concurrencia real) y por los 409 de §3.
6. No se implementó rate limit (§5) ni se tocó `app/main.py` (el router ya
   estaba registrado).
7. **Inconsistencia de trazabilidad (R9):** la tabla de `tasks.md` mapea R9 a
   la tarea 2.6, pero el texto de 2.6 no incluye los tests
   `test_reserva_tokens_distintos_por_turno`, `test_reserva_sin_login_201` y
   `test_reserva_dni_telefono_raiz_400`. No se agregaron en el lote A; quedan
   como hueco a resolver en el lote D (o en un follow-up) antes de archivar el
   change.
