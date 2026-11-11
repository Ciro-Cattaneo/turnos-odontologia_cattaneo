# Design — c-07-crud-recepcion-backend

## Context

C-05 dejó `POST /api/turnos` público, el `Turno` con `origen` (`online|recepcion`), `token_cancelacion` único, el EXCLUDE `no_solape_prof` restringido a `estado IN ('reservado','confirmado')` y el contrato de `Notificacion.payload` de 11 claves (`backend/app/modules/turnos/{router,service,schemas}.py`). C-06 agregó `DELETE /api/turnos/{id}?token=` con `403` genérico, `422` fuera de plazo y auditoría con `actor_id=NULL`. C-08 ya consume `pendiente` con `payload.enviar_en`, descarta notificaciones de turnos no activos con prefijo `turno_cancelado:` y expone el panel de fallidas con filtro SQL. C-03 dejó `get_current_staff`, `require_role`, `require_own_profesional` y la semántica `401` sin sesión / `403` sin permiso; C-04 dejó `slot_service` para computar y leer slots con columnas explícitas. La tabla `auditoria_turno` tiene trigger append-only (`auditoria_no_update_delete`) e índice por `turno_id`.

Falta la capa staff de turnos (US-006/007/008, Flujo 3). Ver `proposal.md` y `specs/recepcion-turnos/spec.md`.

## Goals / Non-Goals

**Goals:**

- Despachar los contratos público y staff sobre la misma ruta `POST /api/turnos` sin romper C-05.
- Reutilizar la transacción de reserva para el alta staff, parametrizando `origen` y actor.
- Reprogramar con el mismo mecanismo anti-solape (lock del profesional + EXCLUDE) excluyendo el propio turno.
- Cancelar staff con la misma ruta `DELETE`, forzando `<3 h` solo con `motivo` y rol `recepcion`/`admin`.
- Corregir datos del paciente con auditoría antes→después y sin fusionar pacientes.
- Aplicar RN-TU-07 como matriz cerrada en `PATCH /estado`.
- Exponer la ficha con historial keyset, columnas explícitas y sin token.
- Dejar auditoría uniforme y no bloqueante en toda mutación; mantener la cola de mail como única fuente de envío.

**Non-Goals:**

- Frontend de recepción (C-10) y reportes (C-11).
- Reprogramación por el paciente (PB-08) y "mis turnos" por DNI+teléfono (PB-01).
- Corrección de `nombre`/`email` del paciente: v1 solo DNI/teléfono/obra social (scope CHANGES/US-007).
- Mover un turno a otro profesional: la reprogramación conserva `profesional_id`.
- Nuevos tipos de notificación, cambios de SMTP, reintentos o scheduler (C-08 solo suma un motivo de descarte).
- Migraciones, columnas, enums o constraints nuevos.

## Decisions

### D-1. Dos contratos estrictos sobre `POST /api/turnos`, despachados por sesión

Qué: un único handler `POST /api/turnos` resuelve la sesión con `staff_opcional` antes de parsear el body:
1. sin cookie → contrato público de C-05: `TurnoCreate` (`extra='forbid'`, sin `origen`), `origen=online`, `actor_id=NULL`, rate limit público vigente;
2. cookie inválida/expirada/revocada → `401` genérico (no se degrada a público);
3. sesión `recepcion`/`admin` → contrato staff `TurnoCreateStaff` (`origen` obligatorio y exactamente `"recepcion"`, mismos cinco datos del paciente); rate limit público no aplica;
4. sesión `odontologo` → `403` genérico.

Por qué: CHANGES fija `POST /api/turnos` con `origen=recepcion`; partir la ruta en `/staff` inventaría un endpoint. El despacho por cookie es determinista y conserva literalmente el contrato público (un body público con `origen` sigue siendo `400` por campo extra).

Alternativas descartadas: ruta separada `POST /api/turnos/recepcion` (no está en el scope y duplica el contrato); aceptar `origen` opcional en el schema público (permitiría marcar turnos como recepción sin sesión).

### D-2. RBAC por operación y scoping del odontólogo

Qué: la matriz aplicada es la de KB-03:
- alta, reprogramación, cancelación (normal/forzada) y corrección de paciente: solo `recepcion`/`admin`;
- ficha y `PATCH /estado`: `recepcion`/`admin` sobre cualquier turno; `odontologo` solo si `staff.profesional_id == turno.profesional_id`, si no `403`;
- `odontologo` puede mover a `confirmado`/`atendido` de sus turnos, pero no a `ausente` (KB-03 limita al odontólogo a confirmado/atendido; `ausente` queda para recepción/admin);
- sin sesión → `401`; rol ajeno → `403` genérico, sin datos del turno.

Por qué: KB-03 es el contrato de seguridad y su fila de odontólogo es más restrictiva que US-008; se aplica el principio de mínimo privilegio. La recepcionista ve todos los profesionales (escala <50, sin ABAC).

Alternativas descartadas: permitir `ausente` al odontólogo (contradice la matriz RBAC); ABAC por recurso (RN-AU-01 lo excluye en v1).

### D-3. Alta staff reutiliza la transacción de reserva con `origen` y actor parametrizados

Qué: `service.reservar()` suma parámetros con default compatible (`origen=TurnoOrigen.online`, `actor_id=None`, `origen_auditoria="online"`). El alta staff llama al mismo flujo con `origen=recepcion` y `actor_id=staff.id`, y encola confirmación/recordatorios con el mismo helper. La respuesta staff es `TurnoStaffOut` (sin `token_cancelacion` ni `cancel_url`): el paciente recibe el link por mail.

Por qué: duplicar la transacción repetiría lock, validación de duración, pre-validación de slot, upsert de paciente, EXCLUDE, encolado y auditoría; parametrizar mantiene una sola verdad. No devolver el token al staff reduce la exposición de la credencial del paciente.

Alternativas descartadas: copiar `reservar()` en un servicio staff (dos fuentes de verdad); devolver `TurnoOut` completo al staff (expone innecesariamente el token).

### D-4. Reprogramación con lock del profesional y anti-solape excluyendo el propio turno

Qué: `PUT /api/turnos/{id}`:
1. `SELECT ... FOR UPDATE` del turno por id (estado, inicio, fin, duración, profesional, paciente) con columnas explícitas;
2. si el estado no es `reservado`/`confirmado` → `422 turno_no_editable`;
3. si no viene `inicio` ni `duracion_min` → `400` por campo;
4. `inicio` (si viene) debe ser futuro y `duracion_min` positiva y múltiplo de `duracion_default_min` → `400` por campo;
5. `SELECT ... FOR UPDATE` del profesional (mismo orden de locks que C-05), cómputo de slots libres del día **excluyendo el turno propio** y pre-validación del bloque completo;
6. si no está cubierto → `409` con `codigo="slot_ocupado"|"slot_no_disponible"` y hasta cinco alternativos del mismo día, sin cambios, sin notificaciones y sin auditoría;
7. update de `inicio/fin/duracion_min`, `updated_at`, descarte de notificaciones obsoletas, reencolado (D-10), auditoría `reprogramar` y commit.

El EXCLUDE `no_solape_prof` sigue siendo la autoridad final: si otra escritura gana la carrera, el `IntegrityError` se mapea a `409` con alternativos, nunca a `500`. No se cambia `profesional_id`, `origen`, `estado` ni `token_cancelacion`.

Por qué: es el mismo mecanismo que C-05 (RN-TU-03, regla dura 2) y el borde half-open `[inicio, fin)` ya está fijado. Excluir el turno propio es imprescindible: sin eso, todo intento de mover un turno colisionaría consigo mismo.

Alternativas descartadas: update directo confiando solo en el EXCLUDE (no permite dar alternativos ni distinguir `slot_ocupado` de `slot_no_disponible`); cambiar de profesional (fuera de scope).

### D-5. Matriz de estados cerrada en `PATCH /estado`

Qué: el body acepta cualquier valor de `TurnoEstado` (`extra='forbid'`); un valor desconocido → `400` por campo. La lógica aplica RN-TU-07 en este orden:
- `reservado → confirmado`: `200`;
- `confirmado → atendido` y `confirmado → ausente`: `200`;
- `reservado → atendido|ausente`: `422 transicion_invalida`;
- cualquier target `reservado`/`confirmado` desde `confirmado` o terminal: `422`;
- target `cancelado`: `422 transicion_invalida` (la cancelación va por `DELETE`);
- desde `cancelado`/`atendido`/`ausente` cualquier target: `422`.

El turno se bloquea con `FOR UPDATE` antes de leer el estado, de modo que dos PATCH concurrentes serializan y el segundo ve el estado nuevo y responde `422` sin segunda auditoría.

Por qué: RN-TU-07 enumera la cadena exacta y exige `422` para transiciones inválidas. Aceptar el enum completo en el schema permite separar "valor desconocido" (`400`) de "transición inválida" (`422`), tal como pide el contrato.

Alternativas descartadas: permitir `reservado → atendido` (salta la confirmación y contradice RN-TU-07); idempotencia `confirmado → confirmado` con `200` (la matriz es estricta y una repetición no es una transición).

### D-6. Cancelación staff sobre la misma ruta `DELETE`, despachada por presencia de `token`

Qué: el handler `DELETE /api/turnos/{id}` conserva la precedencia de C-06:
1. si la query trae `token` (o cualquier parámetro), se ejecuta el flujo público exacto de C-06 (token como única credencial, `403` genérico, regla `>=3 h`); la sesión, si existe, no escala privilegios;
2. si no hay parámetros de query, exige sesión staff `recepcion`/`admin` (sin sesión → `401`; `odontologo` → `403`);
3. body staff `{"motivo": str|None}` (`extra='forbid'`); `motivo` si viene se trimea y exige 3–200 caracteres (`400` si es inválido);
4. estados cancelables `reservado|confirmado`; `cancelado` → `422 turno_ya_cancelado`; `atendido|ausente` → `422 turno_no_cancelable`;
5. `inicio - now >= CANCEL_HOURS_MIN` → cancelación normal, `motivo` opcional (si viene, se trimea y se guarda en `detalle.motivo`), auditoría `cancelar`;
6. `inicio - now < CANCEL_HOURS_MIN` → cancelación forzada; sin `motivo` → `422 motivo_requerido`; con `motivo` → `200`, auditoría `forzar_cancelacion` con `motivo`;
7. siempre `estado=cancelado` + `updated_at`, encolado de `cancelacion` y commit; nunca `DELETE` físico.

El borde exactamente `3 h` cae en la rama normal (`>=`), igual que C-06. `CANCEL_HOURS_MIN` se lee de settings.

Por qué: mantener una sola ruta evita dos endpoints para el mismo recurso y conserva el contrato público. La presencia de `token` como discriminador es explícita y no permite usar la cookie para saltear la credencial del paciente (ni al revés). El motivo obligatorio solo en la rama forzada refleja RN-TU-04 y Flujo 3.

Alternativas descartadas: `DELETE /api/turnos/{id}/staff` (endpoint inventado); exigir motivo siempre (la KB solo lo exige al forzar); permitir que una sesión staff omita el token en la rama pública (mezcla credenciales).

### D-7. Corrección del paciente sobre la fila compartida; DNI duplicado = `409` sin merge

Qué: `PUT /api/turnos/{id}/paciente` acepta `dni`, `telefono`, `obra_social` opcionales (al menos uno; trim; mismas longitudes que `PacienteIn`). Actualiza la fila `Paciente` referenciada por el turno (modelo N:1): el cambio se refleja en todos los turnos de ese paciente, no se crea un snapshot por turno. Si el DNI nuevo ya pertenece a otro `Paciente` → `409 dni_duplicado` sin cambios (no se fusionan pacientes ni se reasignan turnos). Si los valores enviados igualan los actuales → `200` no-op sin auditoría. Se permite corregir en cualquier estado del turno (también cancelado/atendido) porque es dato de referencia. Auditoría `editar_paciente` con `cambios={campo:{antes,despues}}`.

Por qué: KB-04 modela `Turno N→1 Paciente` y RN-PA-02 dice que el teléfono es mutable por paciente; no existe snapshot histórico. Fusionar pacientes por DNI excede el scope y podría reasignar turnos entre historias clínicas; `409` es la salida segura. Permitir la corrección en turnos cerrados facilita arreglar datos para reportes.

Alternativas descartadas: copiar los datos del paciente al turno (migración y duplicación); fusionar automáticamente al detectar DNI duplicado (riesgo de mezclar pacientes).

### D-8. Contrato único de `AuditoriaTurno`

Qué: toda mutación staff escribe **una** fila en la misma transacción con `actor_id=staff.id` y `detalle` con esta forma base:
```
{
  "actor": {"tipo": "staff", "id": "<uuid>", "rol": "recepcion|admin|odontologo"},
  "origen": "recepcion|staff",
  "estado_previo": "...", "estado_nuevo": "...",        // cuando aplica
  "cambios": {"<campo>": {"antes": ..., "despues": ...}}, // reprogramar/editar_paciente
  "motivo": "...",                                       // opcional en cancelar, obligatorio en forzar_cancelacion
  "notificaciones_encoladas": true|false                 // crear/reprogramar/cancelar
}
```
Acciones: `crear`, `reprogramar`, `cancelar`, `forzar_cancelacion`, `editar_paciente`, `cambiar_estado`. El alta conserva el detalle de C-05 (`profesional_id`, `inicio`, `fin`, `duracion_min`, `paciente_id`, `origen`) más el actor. Timestamps como strings ISO-8601 UTC en `detalle`; el `created_at` lo pone la DB. Las solicitudes rechazadas (`400/401/403/409/422`) no escriben auditoría.

Por qué: RN-AU-02 exige quién/cuándo y el historial de la ficha necesita antes→después; unificarlo permite renderizar el historial sin lógica por acción. La misma transacción evita mutaciones sin trail y el trigger existente impide reescribirlo.

Alternativas descartadas: un JSON distinto por acción (la ficha necesitaría casos especiales); auditar después del commit (deja huecos).

### D-9. Ficha con historial keyset, columnas explícitas y sin token

Qué: `GET /api/turnos/{id}?historial_limit=&historial_cursor=` devuelve:
- turno: `id`, `estado`, `origen`, `inicio`, `fin`, `duracion_min`;
- profesional: `id`, `nombre`, `especialidad`;
- paciente: `id`, `nombre`, `dni`, `telefono`, `obra_social`, `email`, `activo`;
- `auditoria: {items:[{id, accion, actor, created_at, detalle}], next_cursor}`.

Nunca incluye `token_cancelacion`. La consulta usa join explícito `Turno→Paciente→Profesional` con columnas nombradas (sin `SELECT *`, regla dura 7). El historial se lee de `auditoria_turno` ordenado por `(created_at, id)` ascendente, `LIMIT limit+1`, cursor opaco `base64url(created_at|id)`; sin `OFFSET`. Query con `extra='forbid'` y `historial_limit` 1–100 (default 50). El actor se resuelve con `LEFT JOIN usuario_staff` (`email`, `rol`); `actor_id=NULL` se muestra como `paciente`.

Por qué: US-007 CA-1 pide datos + historial; keyset cumple la regla dura 7 sin paginar por offset. Excluir el token evita que la ficha se convierta en un distribuidor de la credencial del paciente.

Alternativas descartadas: devolver todo el historial sin paginar (crece sin límite); usar la entidad ORM completa (arrastra columnas y relaciones).

### D-10. Notificaciones de reprogramación: descartar obsoletas y reencolar

Qué: la reprogramación ejecuta dos pasos aislados, en este orden:
1. `begin_nested()` para marcar `estado=fallida` en las `Notificacion` del turno con `estado=pendiente` y tipo `confirmacion|recordatorio_24h|recordatorio_2h`, con `error="turno_reprogramado: <detalle>"`; `intentos` no cambia y no cuenta como fallo SMTP;
2. `begin_nested()` para encolar una `confirmacion` (`enviar_en=now`) y los recordatorios que la nueva anticipación permita, reutilizando el helper de C-05.

Si el paso 1 falla, no se intenta el paso 2 (evita duplicar y dejar vigente una notificación con la hora vieja) y `notificaciones_encoladas=false`. Si el paso 1 funciona y el 2 falla, queda sin mail nuevo pero sin mail obsoleto. En ambos casos la reprogramación commitea (regla dura 5) y la auditoría refleja el bool. La cancelación staff encola `cancelacion` como C-06 y deja que el worker descarte los recordatorios pendientes por turno no activo (mecanismo ya existente).

Esta decisión requiere un delta mínimo en `notificaciones-mail`: el prefijo `turno_reprogramado:` se clasifica como descarte y el panel de fallidas lo excluye. No se toca el worker ni el sender.

Por qué: si no se descartan, el worker enviaría recordatorios con la hora anterior (dato incorrecto al paciente); si solo se descarta sin reencolar, el paciente pierde la confirmación y los recordatorios de la nueva hora. El prefijo propio evita reutilizar `turno_cancelado:` para un turno que sigue activo, lo que mentiría en el motivo persistido.

Alternativas descartadas: actualizar el `payload` en sitio de las pendientes (complejo con recordatorios ya vencidos y menos auditable); borrar filas (pierde trazabilidad); reutilizar `turno_cancelado:reprogramado` (motivo engañoso).

### D-11. Idempotencia y no-op explícitos

Qué:
- `PUT /api/turnos/{id}` con valores resultantes iguales a los actuales → `200` no-op, sin auditoría y con `notificaciones_encoladas=false`;
- `PUT /api/turnos/{id}/paciente` sin cambios efectivos → `200` no-op, sin auditoría;
- `PATCH /estado` hacia el mismo estado → `422 transicion_invalida` (la matriz es estricta);
- `DELETE` staff sobre un turno ya `cancelado` → `422 turno_ya_cancelado`, sin segunda notificación ni auditoría;
- ningún endpoint hace `DELETE` físico de `turno`, `paciente`, `notificacion` ni `auditoria_turno`.

Por qué: un PUT repetido no debe generar mails ni filas de auditoría espurias; a la vez, el contrato de C-06 fija `422` para un turno ya cancelado y RN-TU-07 no admite auto-transiciones.

Alternativas descartadas: `409` para no-op (el recurso existe y el resultado es el pedido); `200` para `PATCH` repetido (oculta que no hubo transición).

### D-12. Códigos HTTP y códigos de negocio

Qué:
- `201` alta staff; `200` reprogramación, corrección, cambio de estado y cancelación;
- `400` por campo: body/query inválidos, extra, `origen` distinto de `recepcion`, `inicio` pasado, `duracion_min` inválida, `motivo` vacío/corto, `estado` desconocido;
- `401` sin sesión en rutas staff; `403` rol insuficiente o odontólogo sobre turno ajeno;
- `404` turno/profesional inexistente en rutas staff (el flujo público conserva su `403` genérico);
- `409` con `detail.codigo`: `slot_ocupado` / `slot_no_disponible` (+`alternativos`) y `dni_duplicado`;
- `422` con `detail.codigo`: `turno_no_editable`, `turno_ya_cancelado`, `turno_no_cancelable`, `motivo_requerido`, `transicion_invalida`;
- `500` genérico para fallos inesperados.

Por qué: replica los códigos ya fijados por C-05/C-06 y agrega los códigos de negocio necesarios para que el frontend de C-10 distinga motivo, transición y colisión sin parsear mensajes.

Alternativas descartadas: `409` para transiciones inválidas (RN-TU-07 pide `422`); `400` para `motivo_requerido` (es una regla de negocio, no un schema inválido).

### D-13. Sin migración

Qué: no se crean tablas, columnas, enums, índices ni constraints. Se reutilizan `turno.origen` (`recepcion` ya en el enum), `turno.estado`, `turno.updated_at`, `paciente.dni` (`ux_paciente_dni`), `notificacion` (`notif_tipo` existente), `auditoria_turno` (trigger append-only e `ix_auditoria_turno_turno_id`) y el EXCLUDE `no_solape_prof`. `alembic upgrade head` no cambia.

Por qué: toda la información nueva (motivo, antes→después, actor) entra en `auditoria_turno.detalle` JSONB; el historial se filtra por el índice existente. Agregar columnas o enums solo por comodidad rompería la regla de no migrar sin necesidad.

Alternativas descartadas: `motivo_cancelacion` en `turno` (duplica lo que ya guarda la auditoría); `NotifTipo.reprogramacion` (migración de enum y un mail nuevo sin plantilla).

### D-14. Reloj inyectable, UTC y pruebas

Qué: `now` se obtiene de un proveedor inyectable (el de C-05 para reserva; uno propio para recepción) y se normaliza a UTC. Los datetimes persistidos son aware. Los tests corren contra Postgres real (`db_session`); los mocks se limitan al reloj y a fallos simulados de encolado. Datos ficticios `.test`, DNI sintéticos y tokens aleatorios (regla dura 12).

Por qué: el borde exacto de 3 h, la reprogramación "en el pasado" y las notificaciones relativas necesitan un reloj determinista (regla dura 9). El resto de la lógica se prueba contra la DB real para validar el EXCLUDE y el trigger.

Alternativas descartadas: `datetime.now()` directo (tests flaky); mocks de repositorio (regla dura 9).

## Risks / Trade-offs

- [Riesgo] Un cliente con cookie válida de `odontologo` no puede usar el alta/reprogramación y recibe `403` → Mitigación: es la matriz RBAC de KB-03; la UI de C-10 oculta esas acciones.
- [Riesgo] La reprogramación descarta notificaciones pendientes y un fallo del encolado nuevo deja al paciente sin mail → Mitigación: el paso de descarte y el de reencolado son independientes; se prioriza no enviar información vieja y se informa `notificaciones_encoladas=false` en respuesta/auditoría.
- [Riesgo] El nuevo prefijo `turno_reprogramado:` toca C-08 → Mitigación: cambio acotado a la clasificación/filtro; no se modifica el envío, los reintentos ni el contrato de payload; queda cubierto por el delta de `notificaciones-mail`.
- [Riesgo] Corregir el DNI de un paciente afecta a todos sus turnos (fila compartida) → Mitigación: se documenta en la ficha y en la auditoría; un DNI ya usado por otro paciente responde `409` y no se fusiona nada.
- [Trade-off] `PATCH` hacia el mismo estado devuelve `422` → Mitigación: es la matriz estricta de RN-TU-07; el frontend no debe reenviar el estado actual.
- [Riesgo] La ficha de odontólogo revela datos de pacientes de sus propios turnos → Mitigación: es su agenda clínica; el scoping impide ver turnos de otros profesionales.
- [Riesgo] Sin migración, el historial depende de `auditoria_turno.detalle` → Mitigación: el contrato de D-8 se fija en la spec y se testea; el trigger append-only ya existe.

## Migration Plan

1. Sin migración Alembic: `alembic upgrade head` queda igual (001/002 ya aplicadas).
2. Deploy de los cambios de `turnos` y del filtro de `notificaciones`; verificar que `POST`/`DELETE ?token=` públicos responden igual que en C-05/C-06.
3. Rollback: redeploy sin las rutas staff; los turnos creados con `origen=recepcion` se conservan (regla dura 3). No ejecutar `downgrade`.

## Open Questions

- Ninguna que cambie el contrato. El texto exacto de `motivo` lo define la operación en la UI de C-10; la API solo exige 3–200 caracteres.
