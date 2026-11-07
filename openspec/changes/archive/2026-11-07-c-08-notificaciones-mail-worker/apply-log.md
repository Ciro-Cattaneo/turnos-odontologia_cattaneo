# Apply Log — c-08-notificaciones-mail-worker

## Lote 2 (2026-11-06) — secciones 6, 7, 8

### TDD (RED → GREEN → TRIANGULATE)

- **Safety net (baseline):** `python -m pytest backend/tests/test_notificaciones_worker.py backend/tests/test_health.py backend/tests/test_config.py -q` → **40 passed**.
- **RED:** tras crear `test_notificaciones_scheduler.py`, `test_notificaciones_fallidas.py` y `test_notificaciones_integracion.py`:
  `python -m pytest backend/tests/test_notificaciones_scheduler.py backend/tests/test_notificaciones_fallidas.py backend/tests/test_notificaciones_integracion.py -q` → **15 failed, 1 passed** (fallas esperadas por módulo `scheduler`/endpoint/lock inexistentes).
- **GREEN:** implementados `scheduler.py`, lifespan, lock de módulo, `schemas.py`, `service.py` y `router.py` → **16 passed**.
- **TRIANGULATE:** agregados casos de borde (intervalos 5/10, liberación del lock, codec de cursor ida/vuelta, `limit` 0/201) → **20 passed**.

Evidencia por tarea:

| Task | Test(s) | Capa |
|------|---------|------|
| 6.1 | `test_scheduler_registra_job_con_intervalo_configurado` (5 y 10 min, job id, max_instances=1, coalesce, MemoryJobStore) | unit |
| 6.2 | `test_lifespan_arranca_scheduler_con_flag_true`, `test_lifespan_no_arranca_scheduler_con_flag_false` | lifespan (scheduler fake, sin red) |
| 6.3 | `test_worker_ciclo_solapado_se_omite`, `test_worker_libera_lock_tras_ciclo` | unit |
| 6.4 | `test_worker_no_requiere_redis` | static |
| 7.1 | `test_fallidas_query_campo_extra_400`, `test_cursor_invalido_400`, `test_cursor_codec_ida_y_vuelta`, `test_fallidas_limit_fuera_de_rango_400` | schemas/API |
| 7.2 | `test_fallidas_lista_solo_fallos_smtp`, `test_fallidas_orden_por_inicio_descendente`, `test_fallidas_keyset_devuelve_next_cursor` | DB real |
| 7.3 | `test_fallidas_recepcion_200`, `test_fallidas_odontologo_403`, `test_fallidas_sin_sesion_401` | API/DB |
| 7.4 | `test_fallidas_no_expone_secretos`, `test_openapi_incluye_endpoint_fallidas` | API/contrato |
| 8.1 | `test_reserva_confirmacion_se_envia_en_el_siguiente_ciclo` | DB real + sender fake |

### 8.2 Suite completa

```
python -m pytest backend/tests -q
...
400 passed, 26 warnings in 62.82s (0:01:02)
```

```
python -m ruff check backend
All checks passed!
```

### 8.3 Migraciones

```
git status --short   # sin backend/alembic/versions/
python -m alembic -c backend/alembic.ini current
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
002_agenda_meta (head)
```

### 8.4 OpenSpec

```
openspec validate c-08-notificaciones-mail-worker --strict
Change 'c-08-notificaciones-mail-worker' is valid
```

```
openspec status --change c-08-notificaciones-mail-worker --json
{
  "changeName": "c-08-notificaciones-mail-worker",
  "schemaName": "spec-driven",
  "isPlanningComplete": true,
  "isComplete": true
}
```

### 8.5 Alcance (`git status --short`)

Sin commits. Archivos nuevos/modificados de este lote:

- `backend/app/modules/notificaciones/scheduler.py` (nuevo)
- `backend/app/modules/notificaciones/schemas.py` (nuevo)
- `backend/app/modules/notificaciones/service.py` (nuevo)
- `backend/app/modules/notificaciones/router.py` (endpoint de fallidas)
- `backend/app/modules/notificaciones/worker.py` (lock de módulo)
- `backend/app/main.py` (lifespan)
- `backend/tests/test_notificaciones_scheduler.py`, `test_notificaciones_fallidas.py`, `test_notificaciones_integracion.py` (nuevos)
- `openspec/changes/c-08-notificaciones-mail-worker/{tasks.md,design.md,apply-log.md}`

Preexistentes del lote 1 (no tocados en este lote): `.env.example`, `CHANGES.md`, `backend/app/core/config.py`, `backend/requirements.txt`, `backend/tests/conftest.py`, `backend/tests/test_config.py`, `payload.py`, `sender.py`, `templates.py`, `worker.py`. Los `.pyc` son ruido de ejecución local.

### Coherencia de diseño

`design.md` D-2: agregada nota de corrección — el claim **no** filtra `t.estado`; la validación de estado del turno se hace por fila en D-13 paso 4 (con excepción de `cancelacion`), para que los descartes D-8 no queden `pendiente` para siempre.
