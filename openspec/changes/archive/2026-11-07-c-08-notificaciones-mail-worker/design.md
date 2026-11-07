# Design — c-08-notificaciones-mail-worker

## Context

C-05 (archivado) ya persiste `Notificacion` con `estado=pendiente`, `intentos=0`, `enviada_at=NULL` y `payload.enviar_en` ISO-8601 UTC; ver `openspec/specs/reserva-online/spec.md` y `backend/app/modules/turnos/service.py` (`_encolar_notificaciones`). El modelo `backend/app/models/notificacion.py` ya trae `payload JSONB`, `error TEXT` e `ix_notif_estado` parcial sobre `estado='pendiente'`; no falta persistencia.

Lo que falta es el consumidor: un worker que envíe, reintente, descarte y haga visible el fallo, más el panel staff. Restricciones del proyecto: worker **en-proceso** single-process cada 5–10 min, sin Redis en v1 (PB-03, DD-05/SU-03, duro 6); SMTP Gmail provisorio por env (PB-05, duro 10); errores SMTP nunca bloquean la reserva (duro 5); tests con mocks solo en el borde SMTP y reloj (duro 9).

Ver `proposal.md` (Why / What Changes) y `specs/notificaciones-mail/spec.md` (requisitos y escenarios).

## Goals / Non-Goals

**Goals:**

- Cerrar el circuito de mail de v1: confirmación, recordatorios y cancelación, con reintentos/backoff y `fallida` visible.
- Mantener el contrato de `payload` de C-05 sin migración ni cambios en `reserva-online`.
- Aislar el envío del request de reserva y del resto de la API: un fallo SMTP no cambia turnos ni tumba el proceso.
- Hacer testeable el worker sin red ni sleeps: sender y reloj inyectables, DB real para persistencia.

**Non-Goals:**

- Migración de schema, columna `enviar_en`, cambios al enum `NotifEstado` o al modelo `Notificacion`.
- Redis/ARQ/Celery, jobstore persistente, ejecución multi-host o exactly-once distribuido.
- Reintento manual desde el panel, edición de plantillas por UI, WhatsApp (RN-NO-03).
- Implementar C-06 (cancelación) o C-07 (recepción): C-08 solo consume el estado del turno y soporta el tipo `cancelacion` que C-06 encolará.
- Deploy, backups, hardening de Gmail y cron del host (C-12).

## Decisions

### D-1. Frontera C-05/C-08: C-05 encola, C-08 consume un contrato congelado

C-05 escribe `Notificacion` con el contrato de `payload` de su D-7: `turno_id`, `tipo`, `enviar_en`, `paciente_nombre`, `paciente_email`, `profesional_nombre`, `inicio`, `fin`, `duracion_min`, `token_cancelacion`, `cancel_url` (todos los timestamps como string ISO-8601 UTC). C-08 **no** re-encola, **no** toca `turnos/service.py` y **no** cambia el contrato: solo lee `Notificacion` y actualiza `estado`/`intentos`/`enviada_at`/`error`/`payload.enviar_en`.

Si el payload llega incompleto o con un `enviar_en` no parseable, C-08 lo marca `fallida` con motivo `payload_incompleto` (sin llamar a SMTP, sin incrementar `intentos`, sin abortar el lote) y sigue con la fila siguiente. Esto cumple el pedido de "marcar fallida con motivo, sin romper el loop" y deja el defecto visible en el panel.

Alternativa descartada: que C-08 derive datos faltantes (por ejemplo, reconstruir `cancel_url` desde el token o consultar `Paciente`/`Profesional`). Motivo: duplica la fuente de verdad del mail, introduce PII extra en el worker y enmascara un encolado defectuoso que conviene ver.

### D-2. Selección de pendientes: columnas explícitas, JSONB validado y sin `SELECT *`

El worker procesa **de a una** notificación por transacción corta:

```sql
SELECT n.id, n.turno_id, n.tipo, n.intentos, n.estado, n.payload,
       t.estado, t.inicio, t.fin
FROM notificacion n
JOIN turno t ON t.id = n.turno_id
WHERE n.estado = 'pendiente'
  AND n.canal = 'mail'
  AND n.payload ? 'enviar_en'
  AND pg_input_is_valid(n.payload->>'enviar_en', 'timestamptz')
  AND (n.payload->>'enviar_en')::timestamptz <= :now
  AND (
        n.tipo = 'cancelacion'
        OR t.estado IN ('reservado', 'confirmado')
      )
ORDER BY (n.payload->>'enviar_en')::timestamptz, n.id
FOR UPDATE OF n SKIP LOCKED
LIMIT 1
```

- `SELECT` de columnas explícitas (duro 7), SQL parametrizado (duro 2), sin `OFFSET`.
- `payload ? 'enviar_en'` + `pg_input_is_valid(..., 'timestamptz')` evita que un payload corrupto haga fallar el cast y garantiza PG16. Sin ese guard, un `::timestamptz` sobre basura abortaría la transacción y frenaría el worker.
- Una pasada previa de saneamiento toma `LIMIT :batch` filas `pendiente` con `enviar_en` ausente/inválido (`NOT (...)` de las mismas condiciones) y las marca `fallida` con `payload_incompleto`, también con `FOR UPDATE OF n SKIP LOCKED`.
- `ORDER BY enviar_en, id` da un orden determinista y estable; el endpoint staff usa keyset (D-9). El lote interno usa `LIMIT 1` por transacción, no keyset, porque no es un listado paginado.

> **Corrección de implementación (lote 1 → lote 2):** el bloque SQL literal de arriba conserva el filtro `t.estado IN ('reservado','confirmado')` solo como referencia histórica. La implementación final **no** lo aplica en el claim: el claim selecciona toda `pendiente` vencida y la validación de estado del turno se hace por fila en D-13 paso 4 (con la excepción de `cancelacion`). Mantener el filtro en el `SELECT` dejaría los recordatorios de turnos `cancelado`/`atendido` en `pendiente` para siempre (nunca serían tomados ni saneados), contradiciendo D-8 y la tarea 5.6. Ver `backend/app/modules/notificaciones/worker.py` (`_SQL_CLAIM`).

**Índice / migración:** el parcial `ix_notif_estado` (`WHERE estado='pendiente'`) ya acota el conjunto a la cola. En v1 (<50 pacientes, single host) el número de pendientes es mínimo y el filtro por `enviar_en` se resuelve sobre ese subconjunto. No se crea índice de expresión ni columna. Si el volumen creciera, el candidato es:

```sql
CREATE INDEX ix_notif_pendiente_enviar_en
ON notificacion (((payload->>'enviar_en'))::timestamptz)
WHERE estado = 'pendiente';
```

Queda documentado como optimización v1.1, **no** en el plan de migraciones de este change. Ver D-12.

Alternativa descartada: agregar `enviar_en TIMESTAMPTZ` con migración y backfill. Motivo: C-05 D-13 lo evitó explícitamente y el contrato JSONB ya cubre v1; sumar schema ahora duplica la programación (payload y columna) y obliga a sincronizar ambos.

Alternativa descartada: comparar `payload->>'enviar_en'` como texto (`<= :now_iso`). Motivo: funciona solo si todos los strings son UTC y de ancho fijo; un payload con otro offset o formato ordenaría mal. El cast validado en PG16 es más robusto y no necesita cambios de C-05.

### D-3. Concurrencia, locks e idempotencia: single-process, `SKIP LOCKED`, marcar después del envío

- **Dentro del proceso:** `BackgroundScheduler` con `max_instances=1` y `coalesce=True`; además un `threading.Lock` no bloqueante en el módulo como defensa contra disparos manuales o solapamiento accidental. Si el lock está tomado, el ciclo se omite y se loguea.
- **Entre procesos/instancias:** cada fila se toma con `FOR UPDATE ... SKIP LOCKED`; dos workers (accidentalmente) no procesan la misma fila a la vez. v1 es single-host (PB-03), así que esto es una red de seguridad, no una garantía distribuida.
- **Orden de actualización:** se envía por SMTP primero y **después** se actualiza la fila (`enviada` + `enviada_at`, o `intentos++`/backoff/`fallida`) y se commitea. Nunca se marca `enviada` antes del OK de SMTP.
- **Garantía:** at-least-once. Si el proceso muere entre el OK de SMTP y el commit, la fila sigue `pendiente` y se reenvía en el próximo ciclo (duplicado posible, pérdida no). Para recordatorios se acepta duplicar antes que perder.
- **Transacción corta por fila:** el lock de la notificación se mantiene durante la llamada SMTP (acotada por `SMTP_TIMEOUT_S`, default 15 s) y se libera al commit. Con `LIMIT 1` no se retienen locks de filas aún no procesadas.

Alternativa descartada: procesar un batch completo dentro de una transacción y commitear al final. Motivo: un fallo en la fila N pierde el progreso de las N−1 ya enviadas (duplicados masivos) y retiene locks de todo el batch durante SMTP.

Alternativa descartada: estado intermedio `enviando` para un claim en dos fases. Motivo: requiere migración de enum y no aporta sobre `SKIP LOCKED` en v1.

### D-4. Backoff y transición a `fallida`

`intentos` cuenta los intentos de envío ya realizados (arranca en 0). Ante fallo SMTP:

1. `intentos = intentos + 1`.
2. Si `intentos >= 3` → `estado = fallida`, `error = "smtp: <detalle acotado>"`.
3. Si `intentos < 3` → sigue `pendiente` y `payload.enviar_en = now + (5 × intentos) minutos` (5 min tras el 1.º, 10 min tras el 2.º), `error` con el último motivo.

Forma exacta: `enviar_en = now + timedelta(minutes=5 * intentos)`; `now` viene del reloj inyectable. Tras 3 fallos no se vuelve a programar. El panel staff expone `intentos` y `error` para que recepción decida el contacto manual.

Alternativa descartada: backoff exponencial (`2^intentos`). Motivo: con 3 intentos y ventana de 5–10 min, 5/10 min ya espacia lo suficiente y es trivial de explicar/testear; exponencial no cambia el resultado operativo en v1.

Alternativa descartada: contar el intento inicial como "0" y hacer 3 reintentos (4 envíos). Motivo: RN-NO-02 dice "3 intentos... tras 3 fallos → fallida"; se implementan 3 envíos totales.

### D-5. Cliente SMTP: `smtplib` estándar, sender inyectable, TLS y timeout

Se usa **stdlib** `smtplib.SMTP` + `email.message.EmailMessage`, sin dependencia nueva. `SMTPSender` es un objeto invocable (`send(mensaje, destinatario)`) inyectado en el worker:

- Puerto 587 (Gmail): `SMTP(host, port, timeout=SMTP_TIMEOUT_S)`, `starttls(context=ssl.create_default_context())`, `login(SMTP_USER, SMTP_PASS)`, `send_message(msg)`.
- Puerto 465: `SMTP_SSL(host, port, timeout=...)` + `login`.
- `SMTP_FROM` como remitente; `SMTP_PASS` leído solo de env y nunca logueado.
- Los tests inyectan un fake/`Mock` en el borde (`send` del sender) o parchean el sender; **no** se mockea la DB, el reloj ni la lógica del worker (duro 9). Alternativa: `unittest.mock.patch("smtplib.SMTP")` directo; se prefiere inyección explícita para no acoplar el test al detalle de conexión.

Alternativa descartada: `aiosmtplib` o SDK de proveedor. Motivo: agrega dependencia y async innecesario en un job de fondo síncrono con 3 mails por turno; migrar a un proveedor transaccional es de C-12/PB-05.

Alternativa descartada: enviar dentro del request de reserva. Motivo: viola RN-NO-02 y la reserva quedaría bloqueada por SMTP (duro 5).

### D-6. Plantillas: español, hora local y datos mínimos

Un módulo de plantillas (`render(tipo, payload) -> (asunto, cuerpo_texto)`) arma el mensaje por tipo:

- `confirmacion`: "Turno confirmado"; datos del turno + link de cancelación.
- `recordatorio_24h`: "Recordatorio: tu turno es mañana"; ídem.
- `recordatorio_2h`: "Recordatorio: tu turno es en 2 horas"; ídem.
- `cancelacion`: "Turno cancelado"; sin link de cancelación (ya está cancelado).

El cuerpo incluye `paciente_nombre`, `profesional_nombre`, fecha y hora local (`payload.inicio` UTC → `zoneinfo` America/Argentina/Buenos_Aires), duración y `cancel_url`. **No** incluye DNI, teléfono ni obra social (no están en el payload; el worker no consulta `Paciente`). El link se usa tal cual viene (`cancel_url` normalizado por C-05). Se envía solo `text/plain` en v1 (HTML es post-v1); no hay secretos en el cuerpo.

Alternativa descartada: templates HTML con Jinja2. Motivo: dependencia, superficie XSS/escape y peso para tres mails de texto; v1 no lo necesita.

### D-7. Ciclo de vida del scheduler con el lifespan de FastAPI

`app/main.py` pasa a usar `@asynccontextmanager lifespan`:

- Si `NOTIF_WORKER_ENABLED` es verdadero, crea `BackgroundScheduler(timezone=UTC)`, registra el job `notificaciones-mail` con trigger `interval` de `NOTIF_WORKER_INTERVAL_MIN` (validado 5–10; default 5), `max_instances=1`, `coalesce=True`, `misfire_grace_time` acorde, y lo arranca.
- En el shutdown llama `scheduler.shutdown(wait=False)` (no interrumpe un envío en curso; el lock y el timeout acotan).
- Jobstore en memoria (default) y sin Redis: el estado de la cola vive en Postgres; el scheduler no persiste jobs.
- `NOTIF_WORKER_ENABLED=false` desactiva el arranque. `conftest.py` fija ese flag para que la suite no lance ciclos reales; los tests del worker llaman a `run_once(...)` directo, sin scheduler.

Context7 (`/websites/apscheduler_readthedocs_io_en_3_x`): `BackgroundScheduler.start()` retorna inmediato y corre en un hilo; `shutdown(wait=...)`; `add_job(func, trigger="interval", minutes=..., id=..., max_instances=..., coalesce=...)`. Se usa la API 3.x estable, no la 4.x (cambia el modelo de schedulers y no está en el stack declarado).

Alternativa descartada: `AsyncIOScheduler` dentro del event loop. Motivo: el envío SMTP es bloqueante (stdlib) y el job abre una sesión de DB síncrona; un `BackgroundScheduler` con hilo propio no bloquea el loop de FastAPI y evita mezclar async con SQLAlchemy síncrono.

Alternativa descartada: proceso worker separado en `docker-compose`. Motivo: PB-03 fija en-proceso para v1; un servicio extra complica el deploy y el estado compartido sin Redis.

### D-8. Cancelación: filtro por tipo, descarte sin contar intentos

El `JOIN` con `turno` filtra `reservado|confirmado` **solo** para `confirmacion`, `recordatorio_24h` y `recordatorio_2h`. El tipo `cancelacion` se envía aunque el turno esté `cancelado` (C-06 lo encola después de cambiar el estado; Flujo 2 paso 3). Si aun así una notificación de recordatorio se selecciona y el turno ya no está activo (carrera con C-06), el worker la descarta: `estado=fallida`, `error="turno_cancelado: <estado>"`, `intentos` sin cambios, sin SMTP.

Se reutiliza `fallida` en vez de crear un estado nuevo: el enum `NotifEstado` no tiene `descartada` y agregarlo requiere migración (`ALTER TYPE`). El `error` con prefijo `turno_cancelado` distingue el descarte de un fallo real, y el endpoint del panel excluye ese prefijo (D-9). El descarte queda auditado en la fila (`error`) y en logs; no se borra nada.

Alternativa descartada: borrar la fila. Motivo: pierde rastro y dificulta explicar por qué no salió un recordatorio; además mezcla "obsoleto" con "inexistente".
Alternativa descartada: dejar la fila `pendiente`. Motivo: queda en la cola para siempre y ensucia métricas.
Alternativa descartada: agregar `descartada` al enum. Motivo: no es imprescindible para v1 y suma una migración que C-05 D-13 quiso evitar; se reevalúa si operación necesita métricas separadas.

### D-9. Contrato del panel de fallidas: RBAC, keyset y 400 por campo

`GET /api/notificaciones/fallidas` en `backend/app/modules/notificaciones/router.py`:

- Dependencia `Depends(require_role("recepcion", "admin"))` de C-03: `401` sin sesión, `403` genérico para `odontologo`. Se reutiliza, no se duplica RBAC.
- Query schema `FallidasQuery` con `ConfigDict(extra="forbid")`: `cursor: str | None = None`, `limit: int = Field(50, ge=1, le=200)`. Un campo desconocido o un `limit` fuera de rango → `400` con `detail` por campo (mismo formato que el resto).
- Cursor opaco = `base64url(f"{inicio_iso}|{id}")`; si no decodifica o no parsea → `400` `campo="cursor"`.
- Query con columnas explícitas, `ORDER BY t.inicio DESC, n.id DESC`, `WHERE (t.inicio, n.id) < (:cursor_inicio, :cursor_id)` (comparación de tupla parametrizada) y `LIMIT limit + 1` para calcular `next_cursor`. Sin `OFFSET` (duro 7).
- Solo filas `estado='fallida'` y `error NOT LIKE 'turno_cancelado%'` (o `error IS NULL` para robustez); el panel es de fallos de envío/payload, no de descartes esperados.
- Item: `id`, `turno_id`, `tipo`, `intentos`, `error`, `enviar_en`, `paciente_nombre`, `paciente_email`, `inicio`, `fin`. `paciente_email` es necesario para el contacto de recepción y ya estaba en el payload; no se agregan DNI/teléfono/OS.
- Respuesta `{items, next_cursor}`.

Alternativa descartada: keyset por `id` (UUIDv4). Motivo: no es cronológico y el panel se usa para priorizar turnos próximos; `inicio DESC` es el orden operativo.
Alternativa descartada: `OFFSET`. Motivo: prohibido por duro 7 y se degrada con la cola.

### D-10. Observabilidad: logs estructurados + columnas, sin `AuditoriaTurno`

Cada transición emite un log (`logger.info/warning`) con `evento` (`notificacion_enviada`, `notificacion_reintento`, `notificacion_fallida`, `notificacion_descartada`, `notificacion_payload_invalido`), `notificacion_id`, `turno_id`, `tipo`, `intentos` y `resultado`. El destinatario se enmascara (`p***@dominio`) y nunca se loguea `SMTP_PASS` ni el cuerpo completo.

El rastro persistente son las columnas de `Notificacion` (`estado`, `intentos`, `error`, `enviada_at`). **No** se escribe `AuditoriaTurno`: esa tabla es append-only para mutaciones staff sobre turnos (RN-AU-02) y el envío de un mail no cambia el turno; usarla inflaría el historial y ensuciaría reportes. Un fallo de logging no corta el lote (se envuelve en try/except y se sigue).

Alternativa descartada: una tabla de eventos de notificación. Motivo: schema nuevo sin necesidad; `error`/`intentos`/`enviada_at` cubren v1 y los logs cubren diagnóstico.

### D-11. Configuración por entorno (sin secretos en repo)

Se agregan a `backend/app/core/config.py` (con default, sin secretos):

| Var | Default | Uso |
|-----|---------|-----|
| `SMTP_TIMEOUT_S` | `15` | timeout de conexión/IO SMTP |
| `NOTIF_WORKER_ENABLED` | `True` | arranca o no el scheduler |
| `NOTIF_WORKER_INTERVAL_MIN` | `5` | intervalo del loop (5–10) |
| `NOTIF_WORKER_BATCH_SIZE` | `20` | tope de saneamiento/filas por ciclo |

`SMTP_HOST/PORT/USER/PASS/FROM` ya existen y siguen siendo obligatorias. `.env.example` se actualiza con las nuevas vars y valores ficticios; `.env` sigue fuera del repo. `NOTIF_WORKER_INTERVAL_MIN` se valida en el arranque (fuera de 5–10 → error claro, mismo estilo fail-fast de `get_settings`). `REDIS_URL` queda documentada y **no** se usa.

### D-12. Sin migración; plan de despliegue

No hay cambios de schema: se reutilizan `payload.enviar_en` (C-05 D-13), `estado`, `intentos`, `enviada_at`, `error` y `ix_notif_estado`. El índice de expresión de D-2 queda como optimización documentada, no creada.

Plan:
1. Agregar `apscheduler` a `backend/requirements.txt` e instalar.
2. Desplegar código (worker, sender, templates, endpoint, config, lifespan) con `NOTIF_WORKER_ENABLED=true` en producción y `false` en tests.
3. Verificar en logs el primer ciclo y que `GET /api/notificaciones/fallidas` responda `200` con staff.
4. Rollback: `NOTIF_WORKER_ENABLED=false` (detiene envíos sin tocar datos) y redeploy del código anterior. No hay `alembic downgrade` porque no hay migración; las filas `enviada`/`fallida` quedan como historial.

### D-13. Orden de una unidad de trabajo (ciclo del worker)

`run_once(session_factory, sender, now, batch_size) -> Resumen`:

1. Saneamiento (hasta `batch_size`): `pendiente` con `enviar_en` ausente/inválido → `fallida` + `payload_incompleto`; commit por fila o al final del saneamiento (no hay envío).
2. Para cada fila (hasta `batch_size`): `SELECT ... FOR UPDATE OF n SKIP LOCKED LIMIT 1`; si no hay fila, fin.
3. Validar payload y `canal=mail`; si inválido → `fallida`/`payload_incompleto`, commit, siguiente.
4. Releer/validar estado del turno según tipo (D-8); si obsoleto → `fallida`/`turno_cancelado`, commit, siguiente.
5. Renderizar plantilla y enviar por el sender inyectado.
6. OK → `enviada`, `enviada_at=now`, `error=NULL`; fallo → D-4. Commit y siguiente.
7. Devolver contadores (`enviadas`, `reintentos`, `fallidas`, `descartadas`, `payload_invalidos`) para logs y tests.

Un ciclo nunca propaga la excepción de una fila al resto: cada fila se envuelve en try/except y se loguea. El lock del módulo evita solapamiento (D-3).

Alternativa descartada: un único `commit` al final del ciclo. Motivo: pierde progreso ante crash y multiplica duplicados; el commit por fila es barato a esta escala.

## Risks / Trade-offs

- [Riesgo] At-least-once: crash entre SMTP OK y commit reenvía el mail → Mitigación: aceptado para recordatorios (duplicar es preferible a perder); se documenta y el `enviada_at` acota el diagnóstico.
- [Riesgo] Un SMTP lento retiene el lock de la fila hasta `SMTP_TIMEOUT_S` → Mitigación: timeout configurable (15 s), `SKIP LOCKED` deja procesar otras filas y el ciclo siguiente retoma.
- [Riesgo] `pg_input_is_valid` requiere PG16 → Mitigación: el stack fija Postgres 16 (KB-02); si se bajara de versión, el guard falla de forma visible en tests de integración.
- [Riesgo] El índice parcial no cubre `enviar_en` a gran volumen → Mitigación: documentado; consulta acotada por `estado='pendiente'`; índice de expresión candidato para v1.1.
- [Riesgo] Descarte marcado `fallida`/`turno_cancelado` podría confundir si alguien mira la tabla directo → Mitigación: prefijo de `error`, logs y exclusión explícita en el endpoint.
- [Riesgo] Carrera entre el chequeo de estado del turno y el envío: una cancelación concurrente podría recibir el recordatorio → Mitigación: el chequeo se hace justo antes de enviar; se acepta la ventana mínima en v1 y C-06 bloquea el turno al cancelar.
- [Trade-off] Sin Redis/multi-host, dos instancias mal configuradas podrían duplicar envíos → Mitigación: single-host fijado por PB-03, `max_instances=1`, lock de módulo y `SKIP LOCKED`; exactly-once queda fuera de v1.
- [Riesgo] `SMTP_PASS` mal configurada deja todo en `fallida` sin bloquear reservas → Mitigación: panel visible, logs, y C-12 documenta Gmail/app password; no se reintenta indefinidamente.
- [Trade-off] Solo `text/plain`; sin HTML ni adjuntos → Mitigación: suficiente para US-009; se reevalúa post-v1.

## Migration Plan

Ver D-12. Sin migración Alembic. Rollback operativo por flag `NOTIF_WORKER_ENABLED=false` + redeploy; no se borran datos ni se ejecuta `downgrade`.

## Open Questions

- Frecuencia exacta dentro de 5–10 min: default 5; ajustable por env sin cambiar la spec. Operación puede pedir 10 si el volumen de mails crece.
- Proveedor SMTP definitivo y límites de Gmail (PB-05): se mantiene Gmail provisorio; el sender está aislado para migrar en C-12 sin tocar el worker.
- Métricas/estado `descartada` separado: se reevalúa si recepción necesita distinguir descartes de fallos en el panel (hoy se distinguen por `error`).

## Consultas Context7 (evidencia)

- `/websites/apscheduler_readthedocs_io_en_3_x` — `BackgroundScheduler` (hilo separado, `start()` no bloquea), `shutdown(wait=...)`, `add_job(func, trigger="interval", minutes=..., id=..., max_instances=..., coalesce=...)`. Confirma D-7 y D-3.
- `/python/cpython` — `smtplib.SMTP(host, port, timeout)`, `starttls(context=...)`, `sendmail`/`EmailMessage`, `SMTP_SSL`. Confirma D-5.
