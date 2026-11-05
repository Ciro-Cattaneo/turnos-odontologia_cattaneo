# Design — c-05-reserva-online-backend

## Context

C-02 dejó `Turno` con `EXCLUDE USING gist` `no_solape_prof` half-open `[)`, `ck_turno_duracion_min`, `ux_turno_token` y `ux_paciente_dni`; C-04 dejó `slot_service` (cómputo puro `ventanas − bloqueos − ocupados` + fetchers parametrizados), `core/ratelimit.py` y el mapeo global de `RequestValidationError` a `400` por campo. `backend/app/modules/turnos/router.py` sigue siendo un placeholder. C-05 agrega la capa API de reserva sin tocar modelos, migraciones ni rutas de C-03/C-04. Ver `proposal.md` (Why) y `specs/reserva-online/spec.md` (requisitos).

## Goals / Non-Goals

**Goals:**

- Implementar `POST /api/turnos` público con validación estricta, revalidación del slot y transacción de reserva completa.
- Reutilizar el anti-solape de DB, `slot_service` y `core/ratelimit.py`; no duplicar cómputo ni constraints.
- Garantizar un solo ganador en colisión concurrente y devolver `409` con alternativos útiles.
- Dejar la reserva independiente del envío de mail: C-05 solo encola; C-08 envía.

**Non-Goals:**

- Worker de envío/reintentos, plantillas SMTP y panel de fallidas (C-08).
- Cancelación del paciente (C-06), CRUD/reprogramación de recepción (C-07), frontend (C-09/C-10), reportes (C-11).
- Cambios de schema, migraciones, modelos, EXCLUDE o índices.
- WhatsApp, pagos, lista de espera o validación de obra social contra padrón (post-v1).

## Decisions

### D-1. Router delgado + servicio de reserva + schemas estrictos

Qué: `backend/app/modules/turnos/` incorpora schemas (`TurnoCreate`, `PacienteIn`, `TurnoOut`, `AlternativosOut`), un servicio `reserva_service.reservar()` y un router que solo aplica rate-limit, parsea el body y traduce errores de dominio a HTTP. La lógica de slots se delega a `app.modules.agenda.slot_service`.
Por qué sobre alternativas: poner la transacción en el router mezcla HTTP con persistencia y dificulta el test de concurrencia; duplicar el cómputo de slots en `turnos/` divergiría en el borde `[)` y en la granularidad. Un servicio único reutiliza C-04 y es testeable con DB real.
Alternativa descartada: un endpoint que reimplemente `ventanas − bloqueos − ocupados` con SQL propio. Motivo: repite la semántica ya probada y crea dos fuentes de verdad.

### D-2. Lock por profesional + EXCLUDE como autoridad final; savepoint y mapeo de `IntegrityError` a 409

Qué: al abrir la transacción de reserva se bloquea la fila del `Profesional` activo con `SELECT ... FOR UPDATE` (`profesional WHERE id = :profesional_id`), antes de cualquier validación o escritura. El lock se mantiene hasta el commit o rollback y serializa las reservas de ese profesional, sin serializar entre profesionales distintos. Con el lock tomado se validan datos, se pre-valida el slot (D-6), se hace el upsert de paciente (D-3), se inserta el `Turno` en `session.begin_nested()` (SAVEPOINT), se encolan las notificaciones en otro savepoint (D-7), se audita (D-8) y se commitea, en el orden de D-12.

El EXCLUDE `no_solape_prof` sigue siendo la autoridad final. Si otra ruta no toma el lock (por ejemplo, una escritura de staff de C-07) o el slot se ocupa entre la pre-validación y el insert, el `IntegrityError` se mapea a `409`; nunca hay doble inserción ni `500` por solape. Si salta `IntegrityError`:
- si `exc.orig.diag.constraint_name == "no_solape_prof"` (con fallback a `"no_solape_prof" in str(exc.orig)` para drivers que no exponen `diag`), se revierte solo el savepoint, se consultan alternativos del mismo día, se hace `rollback()` de la transacción exterior (para liberar el lock y no dejar el upsert de paciente pendiente) y se responde `409` con `detail.codigo="slot_ocupado"`;
- si el constraint es `ux_turno_token`, se reintenta una vez con un token uuid4 nuevo dentro de un nuevo savepoint; si vuelve a fallar, `500` genérico;
- cualquier otro `IntegrityError` se revierte y se responde `500` genérico (no se enmascara como 409).

Por qué sobre alternativas: `AGENTS.md` regla dura 2 exige `EXCLUDE USING gist` **y** `SELECT FOR UPDATE` en la reserva. La fila de `profesional` es el punto de serialización natural porque no existe una fila de “slot libre” que bloquear; bloquear el profesional evita que dos reservas del mismo profesional se pisen y no serializa reservas de profesionales distintos. El lock no reemplaza al EXCLUDE: el EXCLUDE es la garantía de DB y el lock evita el error de DB en el caso común, de modo que la segunda transacción ve el turno ya commiteado y responde `409` sin llegar al insert. PostgreSQL aborta la transacción completa ante un `IntegrityError`; sin SAVEPOINT, la consulta de alternativos posterior fallaría con “current transaction is aborted”. `begin_nested()` permite revertir solo el insert y seguir leyendo en la transacción exterior (Context7, `/sqlalchemy/sqlalchemy`: `BEGIN SAVEPOINT` / `ROLLBACK TO SAVEPOINT`). La pre-validación no es la autoridad: sirve para evitar el error de DB en el caso común y para dar alternativos sin esperar la carrera.

Alternativa descartada 1: solo EXCLUDE sin lock. Motivo: viola la regla dura 2 y deja que la segunda transacción llegue al insert y dependa del error de DB.
Alternativa descartada 2: advisory lock por `(profesional_id, slot)`. Motivo: agrega una clave y un ciclo de vida extra sin cubrir huecos ni reemplazar el EXCLUDE; el lock de fila es más simple y auditable.
Alternativa descartada 3: capturar `IntegrityError` sin savepoint y consultar alternativos en la misma transacción. Motivo: la transacción queda abortada y la consulta falla.
Evidencia: `docs/skills-mcp/evidencias/01-context7-consultas.md` (consulta 1).

### D-3. Upsert de `Paciente` por DNI atómico

Qué: `INSERT INTO paciente (...) VALUES (...) ON CONFLICT (dni) DO UPDATE SET nombre=..., telefono=..., obra_social=..., email=..., updated_at=now() RETURNING id`. Se actualizan solo los campos de contacto; no se duplica la fila y no se modifica `activo`.
Por qué sobre alternativas: un `SELECT` seguido de `INSERT` tiene carrera entre dos reservas del mismo DNI nuevo; `ON CONFLICT` es atómico y usa `ux_paciente_dni`. `Session.merge()` no tiene clave natural por DNI y podría crear duplicados.
Regla de borde (trazada a R1 S4 y a PB-04 / regla dura 3): si el paciente existente está `activo=false`, la reserva igual procede, se actualizan solo los campos de contacto y no se reactiva. `activo` es visibilidad para staff (PB-04), no una credencial de reserva; reactivar o bloquear es una política de recepción/admin que no está en el scope de C-05.
Alternativa descartada: reactivar automáticamente al reservar. Motivo: cambia el significado de “desactivar” sin una regla de negocio que lo respalde; si recepción necesita reactivación explícita, se resuelve en C-07.

### D-4. Validación Pydantic estricta y error por campo

Qué: todos los schemas usan `ConfigDict(extra="forbid")`. `PacienteIn` exige `nombre`, `dni`, `telefono`, `obra_social` y `email` no vacíos; `email` se valida con `str` + patrón (`Field(pattern=...)` o `field_validator`), no con `EmailStr`. El router parsea el body con un helper `parse_body_or_400` que, ante `ValidationError`, devuelve `400` con `detail: [{campo, error, tipo}]` y normaliza el `loc` de FastAPI quitando el prefijo `body` (así `paciente.email` queda como `campo="paciente.email"`).
Por qué sobre alternativas: `EmailStr` usa el validador RFC y rechaza el TLD reservado `.test` que exige la regla dura 12; el precedente `LoginIn` de C-03 ya usa patrón por ese motivo. Cambiar el handler global para quitar `body` afectaría a todos los endpoints; un helper local mantiene el contrato de C-05 sin tocar C-03. Pydantic reporta `extra_forbidden` en el `loc` del campo extra y los errores anidados como ruta (`paciente.email`), lo que permite devolver exactamente una entrada para el mail inválido (Context7, `/websites/pydantic_dev_validation`).
Alternativa descartada: `EmailStr` + `email-validator`. Motivo: incompatibilidad con los datos ficticios `.test` y con el contrato de tests del repo.
Evidencia: `docs/skills-mcp/evidencias/01-context7-consultas.md` (consulta 2).

### D-5. Duración: default o múltiplo positivo de la granularidad

Qué: si `duracion_min` se omite, se usa `profesional.duracion_default_min` (con fallback `or 30` si el dato viniera en 0). Si viene, debe ser entero positivo y múltiplo exacto de esa granularidad; si no, `400` con una única entrada `campo="duracion_min"`, `tipo="duracion_no_multiplo_granularidad"` y sin crear turno. El bloque `[inicio, inicio+duracion_min)` debe estar completamente cubierto por slots libres alineados a la grilla del profesional; si no, es un `409` de disponibilidad (D-6), no un `400`.
Por qué sobre alternativas: redondear en silencio viola el requisito de rechazo explícito; aceptar cualquier duración rompe la grilla y hace que los alternativos no sean comparables; limitar a exactamente el default quita la flexibilidad de RN-TU-02 para bloques múltiplos.
Alternativa descartada: aceptar `duracion_min` arbitraria y recortar al slot. Motivo: produce turnos que no respetan la granularidad ni la ventana.

### D-6. Revalidación del slot y alternativos reutilizando `slot_service`

Qué: para el día local de `inicio` (`America/Argentina/Buenos_Aires`), se cargan ventanas, bloqueos y turnos activos con los fetchers de `slot_service`, se computan slots con `duracion_default_min` y se verifica que el bloque pedido esté cubierto por slots libres contiguos y alineados. Si no, se responde `409` con `detail.codigo="slot_no_disponible"` y hasta cinco alternativos del mismo día local, ordenados por `inicio` ascendente y excluyendo el `inicio` pedido. El helper de alternativos reutiliza el mismo cómputo: agrupa slots libres contiguos para bloques de `duracion_min` y toma los primeros cinco.
Por qué sobre alternativas: reutilizar `slot_service` mantiene una única semántica `[)`, TZ y granularidad; una query SQL de solape propia duplicaría la lógica y podría discrepar del endpoint público de disponibilidad.
Alternativa descartada: devolver alternativos de días posteriores. Motivo: el contrato de RN-TU-03 y la spec piden alternativos del mismo día; si el día está lleno, la lista vacía es una respuesta válida y el frontend puede pedir otra fecha.

### D-7. Notificaciones: encolado en savepoint, `enviar_en` en `payload`

Qué: tras crear el turno se insertan `Notificacion` con `canal=mail`, `estado=pendiente`, `intentos=0`:
- `confirmacion` siempre, con `payload.enviar_en = now`;
- `recordatorio_24h` solo si `inicio - 24h > now`, con `payload.enviar_en = inicio - 24h`;
- `recordatorio_2h` solo si `inicio - 2h > now`, con `payload.enviar_en = inicio - 2h`.
El `payload` incluye solo lo necesario para el mail (`turno_id`, `tipo`, `enviar_en`, `paciente_nombre`, `paciente_email`, `profesional_nombre`, `inicio`, `fin`, `duracion_min`, `token_cancelacion`, `cancel_url`); no incluye DNI, teléfono ni obra social. Todos los datetimes del `payload` (`enviar_en`, `inicio`, `fin`) se serializan como strings ISO-8601 UTC (por ejemplo `2026-11-05T12:00:00+00:00`), nunca como objetos `datetime` crudos: `payload` es JSONB y `json.dumps` no serializa `datetime` por defecto. El bloque de inserts va en un `begin_nested()` propio: si falla, se revierte solo ese savepoint, se registra `notificaciones_encoladas=false` en la auditoría y la reserva commitea igual con `201`.

Interpretación de “siempre encolados” (regla dura 5 vs. RN-NO-01, H-14): significa que no existe fallback por falta de mail —el mail es obligatorio (RN-TU-01/PB-02) y la `confirmacion` se encola siempre—. Los recordatorios se encolan solo si la anticipación lo permite: `recordatorio_24h` si `inicio - 24h > now` y `recordatorio_2h` si `inicio - 2h > now` (comparación estricta). No se condiciona el encolado por ausencia de mail; se condiciona por anticipación, como fija RN-NO-01.

Por qué sobre alternativas: `Notificacion` no tiene columna de programación; usar `payload.enviar_en` evita una migración en C-05 y deja el contrato al worker C-08. Enviar SMTP dentro del request violaría RN-NO-02 (asincrónico, reintentos) y haría que un fallo de mail bloquee la reserva. Fallar el request si el encolado falla contradice “la reserva nunca se bloquea por fallo de mail”.
Alternativa descartada: agregar `notificacion.enviar_en TIMESTAMPTZ` en C-05. Motivo: cambio de schema fuera de scope; si C-08 necesita una columna, la agrega en su propio change con migración y backfill.
Alternativa descartada: ignorar el fallo de encolado en silencio. Motivo: la auditoría debe dejar rastro (`notificaciones_encoladas=false`) para operación.

### D-8. Auditoría append-only en la misma transacción

Qué: se inserta `AuditoriaTurno` con `turno_id`, `actor_id=NULL` (acción del paciente), `accion="crear"` y `detalle={origen:"online", profesional_id, inicio, fin, duracion_min, notificaciones_encoladas}`. `detalle.inicio` y `detalle.fin` se serializan como strings ISO-8601 UTC, igual que en `Notificacion.payload` (D-7), porque `detalle` es JSONB. La escritura ocurre antes del commit y después del encolado.
Por qué sobre alternativas: el trigger `auditoria_no_update_delete` ya garantiza append-only; escribir la auditoría en la misma transacción evita turnos sin trail. Un servicio de auditoría separado con otra transacción podría perder el registro si falla el commit.
Alternativa descartada: auditar después del commit. Motivo: un fallo entre commit y auditoría deja un turno sin registro.

### D-9. Rate limit del POST reutilizando `core/ratelimit.py`

Qué: dependencia de rate-limit que corre antes de parsear el body; clave `turnos-publico:{ip}`, ventana fija de 60 s, límite de 10 reservas/min/IP; al exceder, `429` con header `Retry-After`. Se usa `check_public_rate_limit(key, limit=10, window_s=60)` y el reloj inyectable (`now`) para tests sin sleeps. En v1 el contador es en-proceso; `REDIS_URL` queda solo documentada (PB-03).
Por qué sobre alternativas: reutiliza el mecanismo ya probado en C-04; 10/min es más restrictivo que las lecturas públicas (30/min) porque cada request escribe. Un límite separado evita que un scrapeo de disponibilidad consuma el cupo de reservas.
Alternativa descartada: reutilizar el limitador de login (ventana deslizante, 10/min). Motivo: semántica distinta y estado compartido con auth; mejor clave y ventana propias.

### D-10. Tiempo: `inicio` aware, futuro y día local

Qué: `inicio` debe ser `datetime` con `tzinfo` y `utcoffset()` no nulos; sin zona → `400` `campo="inicio"`, `tipo="inicio_sin_zona"`. Se normaliza a UTC para persistir. La validación de futuro usa un reloj inyectable (`now_provider`, default `datetime.now(UTC)`): `inicio` debe ser estrictamente mayor que `now`; si no, `400` `campo="inicio"`. El día local para ventanas y alternativos se obtiene con `inicio.astimezone(TZ).date()`.
Por qué sobre alternativas: aceptar naive obliga a asumir Argentina y crea ambigüedad en el cambio de hora; el proyecto persiste UTC y muestra local (regla dura 10). Un reloj inyectable hace deterministas los tests de borde.
Alternativa descartada: asumir `America/Argentina/Buenos_Aires` para naive. Motivo: silencio ante un dato ambiguo y difícil de auditar.

### D-11. Contrato HTTP y respuesta

Qué: `201` en éxito con resumen (`id`, `estado`, `inicio`, `fin`, `duracion_min`, `profesional{id,nombre}`, `paciente{nombre,dni,email}`, `token_cancelacion`, `cancel_url`, `notificaciones_encoladas`); los datetimes de la respuesta (`inicio`, `fin`) se serializan como ISO-8601 UTC. `400` con `detail` lista por campo; `404` genérico para profesional inexistente/inactivo; `409` con `detail.codigo` (`slot_ocupado` o `slot_no_disponible`) y `detail.alternativos`; `429` con `Retry-After` en segundos hasta el reset de la ventana; `500` genérico para errores inesperados. `cancel_url = FRONTEND_URL.rstrip("/") + "/cancelar?token=" + token`, de modo que una `FRONTEND_URL` con barra final no produce `//cancelar`. Los response models también usan `extra="forbid"`.
Por qué sobre alternativas: `201` refleja creación y coincide con C-04; `400` (no `422`) es el contrato del proyecto para validación; un objeto de error distinto para `409` permite a la UI leer alternativos sin parsear strings.
Alternativa descartada: devolver `200` o `422`. Motivo: inconsistente con el resto del backend y con la regla dura 1.

### D-12. Orden transaccional y límites de fallo

Qué: la transacción sigue este orden:
1. abrir la transacción y resolver el `Profesional` activo bloqueando su fila con `SELECT ... FOR UPDATE` (`404` si no existe o está inactivo; el lock es la serialización por profesional de D-2);
2. validar duración, `inicio` futuro/aware (`400` tempranos, sin escrituras);
3. pre-validar el slot contra `slot_service` (`409` temprano, sin escrituras);
4. upsert de `Paciente` por DNI (D-3);
5. insertar `Turno` dentro de `begin_nested()` (D-2);
6. insertar `Notificacion` dentro de `begin_nested()` (D-7);
7. insertar `AuditoriaTurno` (D-8);
8. commit y `201`.

El lock del paso 1 se libera en el commit o en cualquier rollback. Si la validación o la pre-validación fallan (`400`/`409`), se hace rollback sin escrituras y se libera el lock. Si el turno choca (`409` por `IntegrityError`), se revierte la transacción completa: no queda paciente huérfano ni auditoría. Si el encolado falla, solo se revierte su savepoint y se commitea turno + auditoría con `notificaciones_encoladas=false`. Si falla la auditoría o el commit, se revierte todo y se responde `500` genérico.
Por qué sobre alternativas: el lock al inicio garantiza que la segunda reserva del mismo profesional espere (regla dura 2) y que, al obtenerlo, la pre-validación vea el turno ya commiteado y responda `409`; commitear el paciente antes del turno deja huérfanos en un `409`; encolar antes del turno viola la FK; auditar fuera de la transacción pierde el trail.
Alternativa descartada: una transacción por paso. Motivo: rompe atomicidad y permite turnos sin paciente o sin auditoría. Alternativa descartada: lock después de la pre-validación. Motivo: dos reservas podrían pre-validar en paralelo y llegar al insert; el EXCLUDE las separaría, pero se perdería la serialización temprana que exige la regla dura 2.

### D-13. Sin migración

Qué: C-05 no agrega columnas, tablas, constraints ni índices. Todo lo necesario ya existe en `001_core_models` (`btree_gist`, `no_solape_prof`, `ck_turno_duracion_min`, `ux_turno_token`, `ux_paciente_dni`, enums) y en `002_agenda_meta` (freshness, no usada por la reserva).
Por qué: la capa API no requiere persistencia nueva; `payload` JSONB cubre la programación de recordatorios. Si C-08 necesita `enviar_en` como columna, lo resuelve en su change.
Alternativa descartada: migración aditiva para `notificacion.enviar_en`. Motivo: deuda de schema prematura; el worker puede leer `payload.enviar_en` sin migración.

## Risks / Trade-offs

- [Riesgo] El nombre del constraint puede no venir en `exc.orig.diag` según el driver → Mitigación: detección por `diag.constraint_name` con fallback a búsqueda de `"no_solape_prof"` en el texto; test de colisión real contra PG.
- [Riesgo] El `SELECT FOR UPDATE` del profesional serializa todas las reservas de ese profesional y puede aumentar la latencia bajo carga → Mitigación: el lock se toma solo durante la transacción corta de reserva, se libera en commit/rollback y no se comparte entre profesionales; test de dos transacciones verifica que la segunda espera y termina en `409`, no en `500`.
- [Riesgo] Un lock tomado en distinto orden con otra ruta podría producir deadlock → Mitigación: C-05 toma un único lock (fila de `profesional`) al inicio; C-07 debe respetar el mismo orden de lock por profesional.
- [Riesgo] El savepoint del turno hace flush del upsert de paciente; si luego hay `409`, se revierte todo → Mitigación: es el comportamiento deseado (no dejar paciente sin turno); test de `409` verifica cero filas nuevas de paciente y turno.
- [Trade-off] Si el encolado falla, la reserva queda sin notificaciones y el worker no las verá → Mitigación: auditoría con `notificaciones_encoladas=false`, log de warning; se acepta porque un fallo de insert es un fallo de DB, no un fallo SMTP, y la regla prioriza no bloquear la reserva.
- [Riesgo] `payload.enviar_en` es un contrato implícito con C-08 → Mitigación: documentarlo en el apply log y en el payload; C-08 lo consume sin migración.
- [Riesgo] Alternativos solo del mismo día; si el día está lleno, lista vacía → Mitigación: la spec lo permite; C-09 puede ofrecer “ver otro día” usando `GET /api/disponibilidad`.
- [Trade-off] Rate-limit en-proceso se resetea en deploy y no es compartido entre procesos → Mitigación: v1 single-host (PB-03); `REDIS_URL` documentada para escalar.
- [Riesgo] Paciente `activo=false` que vuelve a reservar queda invisible para staff → Mitigación: decisión D-3; se revisa en C-07 si recepción necesita reactivación explícita.

## Migration Plan

1. Sin migración de base: `alembic upgrade head` queda igual; verificar que `001`/`002` ya están aplicadas.
2. Deploy del router/servicio/schemas nuevos bajo `/api/turnos`; no se tocan rutas existentes.
3. Rollback: redeploy sin el endpoint; no hay datos nuevos que revertir más allá de los turnos creados por C-05 (que se conservan como historial, regla dura 3). No ejecutar `downgrade` por este change.

## Open Questions

- Forma exacta del `payload` que C-08 consumirá: se fija `enviar_en` y los datos mínimos en D-7; si C-08 necesita más claves, se agregan sin cambiar el contrato de C-05.
- Límite exacto de reservas por IP (10/min): es una decisión de diseño ajustable sin cambiar la spec; se documenta en el apply log si operación pide otro valor.

> Decisión cerrada (ya no es open question): la reserva con `Paciente.activo=false` procede sin reactivarlo (D-3, R1 S4). Una reactivación explícita, si recepción la necesita, corresponde a C-07/admin.
