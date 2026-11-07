# Design — c-06-cancelacion-paciente-backend

## Context

C-05 dejó `POST /api/turnos` público, el `Turno` con `token_cancelacion` único (`ux_turno_token`), el EXCLUDE `no_solape_prof` restringido a `estado IN ('reservado','confirmado')` y el contrato de `Notificacion.payload` de 11 claves (`backend/app/modules/turnos/service.py`, `backend/app/models/turno.py`, `001_core_models.py`). C-08 ya consume `pendiente` con `payload.enviar_en`, envía el tipo `cancelacion` aunque el turno esté `cancelado` y descarta recordatorios de turnos no activos (`backend/app/modules/notificaciones/worker.py` D-8). C-03 dejó el patrón de `403` genérico para no revelar recursos (`app/modules/auth/deps.py`) y `app/core/ratelimit.py` ya expone un limitador público por IP. `CANCEL_HOURS_MIN=3` existe en `app/core/config.py` y `.env.example`.

Falta la operación que consume ese token y ejecuta la transición `reservado|confirmado → cancelado` (RN-TU-07) liberando el slot. Ver `proposal.md` y `specs/cancelacion-paciente/spec.md`.

## Goals / Non-Goals

**Goals:**

- Implementar `DELETE /api/turnos/{id}?token=` público con credencial única y `403` uniforme.
- Aplicar `inicio - now >= CANCEL_HOURS_MIN` con borde exacto inclusivo y `422` informativo fuera de plazo.
- Cancelar como cambio de estado (soft cancel) dentro de una transacción con lock del turno, idempotente en efectos.
- Encolar el mail `cancelacion` sin duplicar la cola ni la lógica SMTP de C-08 y sin bloquear la cancelación si el encolado falla.
- Dejar auditoría append-only con actor paciente/token y respuesta sin datos sensibles.

**Non-Goals:**

- Cancelación staff, forzar <3 h con motivo y `PUT`/`PATCH` de recepción (C-07).
- Reprogramación del paciente (PB-08, fuera de v1) y "mis turnos" por DNI+teléfono (descartado por PB-01).
- Frontend `GET /cancelar?token=` (C-09); este change solo expone la API.
- Envío SMTP, reintentos, plantillas o panel de fallidas (C-08): C-06 solo inserta `Notificacion`.
- Cambios de schema, migraciones, modelos, EXCLUDE, índices o enums.
- Expiración independiente del token: no existe columna de expiración en v1 (ver D-10).

## Decisions

### D-1. Router delgado + `cancellation_service` + schemas de respuesta estrictos

Qué: `backend/app/modules/turnos/router.py` suma la ruta `DELETE /api/turnos/{id}`; la transacción vive en un módulo nuevo `cancellation_service.py`. El router aplica rate limit, parsea la query estricta y traduce errores de dominio a HTTP; el servicio concentra lock, regla temporal, transición, encolado y auditoría. La respuesta usa un `CancelacionOut` con `ConfigDict(extra="forbid")`.

Por qué: C-05 ya separó router y `service.py`; repetir el patrón mantiene la transacción testeable con DB real y no mezcla HTTP con persistencia. Un servicio aparte evita que `service.reservar()` (ya extenso) acumule la cancelación.

Alternativa descartada: poner la transacción en el router. Motivo: impide probar la concurrencia sin HTTP y difumina el orden transaccional.

### D-2. Autenticación por token de query y `403` genérico uniforme

Qué: la **única** credencial es `?token=<uuid>`. El router lee la query manualmente y acepta solo la clave `token`, con esta precedencia determinista:
1. cualquier otra clave (`dni`, `telefono`, `email`, etc.) o `token` repetido → `400` con `detail` por campo (`campo="dni"`, `campo="token"`, etc.), porque los schemas de API usan `extra="forbid"` (regla dura 1) y así no existe una ruta alternativa de credencial;
2. `token` ausente, vacío o no parseable como UUID → `403` genérico, idéntico al de token que no corresponde a ningún turno;
3. `{id}` no parseable como UUID o inexistente → `403` genérico (mismo cuerpo y status), para no revelar existencia;
4. turno existente con token distinto → `403` genérico.

La búsqueda es una sola consulta parametrizada `WHERE turno.id = :id AND turno.token_cancelacion = :token` (comparación en DB, con tipos UUID), tomando `FOR UPDATE` de la fila cuando hay match (D-4). No se consulta por DNI/teléfono y el body no se usa como credencial (si un cliente manda un `DELETE` con body, se ignora; los tests negativos cubren que no habilita nada). El cuerpo del `403` es siempre `{"detail": "No autorizado"}`.

Por qué: PB-01 es explícito ("solo `?token=`, 403 genérico otherwise"). Un `404` distinguiría "no existe" de "token malo"; un `422` de validación distinguiría formatos y permitiría enumerar. El `400` de campos extra no revela existencia: solo describe la forma del request y es el contrato de la regla dura 1. La comparación en DB evita cargar el turno antes de saber que la credencial es válida.

Alternativa descartada: `404` para id inexistente y `403` para token malo. Motivo: filtra existencia de recursos y contradice el contrato de C-06.

Alternativa descartada: parsear la query con un schema Pydantic que exija `token`. Motivo: un token ausente/inválido quedaría como `400` de validación, mezclando "request mal formado" con "credencial inválida"; además el `id` de path tipado produciría `400` antes de poder uniformar el `403`. El parseo manual acotado mantiene la uniformidad y el `400` por campo para extras.

### D-3. Regla temporal `inicio - now() >= CANCEL_HOURS_MIN`, borde exacto inclusivo

Qué: `limite = timedelta(hours=get_settings().CANCEL_HOURS_MIN)` (default 3). La cancelación se permite si `inicio_utc - now_utc >= limite`; exactamente 3 h se acepta (`>=`, no `>`). Si `inicio - now < limite` → `422` con `detail.codigo="cancelacion_fuera_de_plazo"`, `detail.mensaje` en español ("No se puede cancelar con menos de 3 horas de anticipación") y `detail.contacto` tomado de `CONSULTORIO_CONTACTO` (D-11). `CANCEL_HOURS_MIN` se lee de settings y no se hardcodea, pero el texto del mensaje se arma con el valor configurado.

Por qué: RN-TU-04 y US-005 dicen "≥3h"; el borde exacto debe aceptar. Restar datetimes aware en UTC evita ambigüedades de zona y cambios de hora. Un `<` en vez de `>=` rechazaría el caso legítimo de exactamente 3 h que exige la spec.

Alternativa descartada: comparar en hora local. Motivo: la aritmética de instantes es la misma, pero UTC es el formato persistido y evita conversiones repetidas.

Alternativa descartada: permitir configurar el mensaje/contacto por env además de las horas. Motivo: alcanza con un contacto opcional; mensajes se versionan en código para mantener idioma y trazabilidad.

### D-4. Transacción, lock del turno y concurrencia

Qué: el orden es:
1. rate limit (D-8);
2. parseo estricto y `SELECT id, estado, inicio, fin, duracion_min, profesional_id, paciente_id FROM turno WHERE id = :id AND token_cancelacion = :token FOR UPDATE` (parametrizado, columnas explícitas, sin traer el token, regla dura 7); sin fila → `403` genérico;
3. si `estado` es `cancelado` → `422 turno_ya_cancelado`; si es `atendido` o `ausente` → `422 turno_no_cancelable`; si no es `reservado`/`confirmado` → `422 turno_no_cancelable` (defensa ante estados futuros);
4. regla temporal (D-3) → `422` si falla;
5. `estado = cancelado` y `updated_at = now` sobre la fila bloqueada;
6. encolado del mail `cancelacion` en `begin_nested()` (D-6), aislado;
7. `AuditoriaTurno` append-only (D-7);
8. commit y respuesta `200`.

El `FOR UPDATE` sobre la fila del turno serializa dos cancelaciones del mismo turno: la segunda espera, al desbloquearse lee `estado=cancelado` y responde `422` sin segunda transición, sin segundo mail y sin segunda auditoría. El EXCLUDE `no_solape_prof` no se toca ni se revalida: su predicado solo considera `reservado`/`confirmado`, así que pasar a `cancelado` libera el slot automáticamente para `slot_service` y para nuevas reservas. No se hace `DELETE` físico.

Por qué: la fila del turno es el punto de serialización natural para su propia transición; bloquear al profesional (como C-05) sería innecesario y acoplaría la cancelación al orden de locks de reserva. El lock evita el doble mail/auditoría de la carrera. El EXCLUDE ya existente es la autoridad de solape para turnos activos; no hay que reimplementarlo.

Alternativa descartada: `UPDATE ... WHERE id AND token AND estado IN (...)` atómico sin lock explícito. Motivo: el `UPDATE` condicional evita la doble transición, pero no permite distinguir de forma estable `403` (sin match) de `422` (estado) ni encolar/auditar con el estado previo sin una lectura; el lock da una lectura consistente y el contrato claro.

Alternativa descartada: tomar lock del profesional además del turno. Motivo: agrega un segundo lock y riesgo de deadlock con C-05/C-07 sin aportar nada: la cancelación no reserva ni ocupa slot.

### D-5. Idempotencia relativa: repetir la llamada no repite efectos

Qué: una segunda llamada con el mismo `id` y token válido encuentra el turno `cancelado` y responde `422 turno_ya_cancelado`; no cambia estado, no reescribe `updated_at`, no encola otro mail y no escribe otra auditoría. No se responde `200` por idempotencia porque el contrato de Flujo 2 y US-005 fija `422` para turno ya cancelado.

Por qué: el paciente que recarga el link no debe generar mails duplicados ni auditoría espuria, pero la API debe seguir diciendo que la operación no es aplicable. "Idempotencia relativa" se define así: mismo resultado observable y cero efectos laterales, con el status que exige la KB.

Alternativa descartada: devolver `200` con `estado=cancelado` en la segunda llamada. Motivo: contradice el escenario explícito "turno ya cancelado → 422" y haría indistinguible una cancelación nueva de una repetida.

### D-6. Contrato de encolado del mail `cancelacion` y relación con C-08

Qué: en la misma transacción se inserta una `Notificacion` con `turno_id`, `canal=mail`, `tipo=cancelacion`, `estado=pendiente`, `intentos=0`, `enviada_at=NULL` y el payload de 11 claves congelado por C-05/C-08 (`turno_id`, `tipo`, `enviar_en`, `paciente_nombre`, `paciente_email`, `profesional_nombre`, `inicio`, `fin`, `duracion_min`, `token_cancelacion`, `cancel_url`). `enviar_en = now` y todos los timestamps son strings ISO-8601 UTC. El payload se arma con una consulta de `Paciente` y `Profesional` por claves, sin `SELECT *`. El insert va en `begin_nested()`; si falla, se revierte solo el savepoint, la cancelación commitea igual y la respuesta informa `notificaciones_encoladas=false` (regla dura 5).

C-06 **no** envía SMTP, no reimplementa plantillas ni reintentos y no inserta en otra cola: usa la misma tabla `notificacion` y el mismo tipo que C-08 ya sabe procesar, incluso con el turno `cancelado` (C-08 D-8). No se encola `confirmacion` ni recordatorios nuevos; los pendientes de un turno cancelado serán descartados por el worker (`turno_cancelado`), comportamiento ya especificado en `notificaciones-mail`.

Por qué: duplicar el sender o una cola propia crearía dos fuentes de verdad y rompería el panel de fallidas/observabilidad de C-08. Aislar el insert mantiene la promesa "un fallo de mail nunca bloquea la operación de negocio".

Alternativa descartada: encolar después del commit. Motivo: un fallo entre commit y encolado deja la cancelación sin mail y sin rastro; la auditoría debe reflejar `notificaciones_encoladas`.

Alternativa descartada: borrar las notificaciones pendientes del turno al cancelar. Motivo: el worker ya las descarta con motivo auditable; borrarlas perdería trazabilidad y mezclaría responsabilidades.

### D-7. Auditoría `AuditoriaTurno` con actor paciente/token

Qué: se inserta `AuditoriaTurno(turno_id, actor_id=NULL, accion="cancelar", detalle)` con `detalle = {actor: "paciente", credencial: "token_cancelacion", estado_previo, inicio, fin, duracion_min, profesional_id, notificaciones_encoladas}`; `inicio`/`fin` como strings ISO-8601 UTC. El token no se persiste ni se loguea en claro: `credencial` identifica el tipo de credencial, no el secreto. Se escribe en la misma transacción, antes del commit.

Por qué: RN-AU-02 exige trail de mutaciones; aunque la regla nombra staff, el precedente de C-05 audita la acción del paciente con `actor_id=NULL`. No guardar el token evita que la tabla append-only se convierta en un depósito de credenciales. La misma transacción impide turnos cancelados sin auditoría.

Alternativa descartada: auditar después del commit. Motivo: un fallo intermedio deja la transición sin trail.
Alternativa descartada: guardar el token completo en `detalle`. Motivo: cualquier lectura de auditoría permitiría cancelar/repetir acciones; el token es la credencial.

### D-8. Rate limit del endpoint público coherente con C-05

Qué: dependencia previa al parseo con clave `turnos-cancelacion:{ip}`, ventana fija de 60 s y límite de 10 intentos/min/IP usando `check_public_rate_limit`; al exceder → `429` + `Retry-After` en segundos hasta el reset. Incluye intentos con token inválido, que es justamente el vector de fuerza bruta. En v1 el contador es en-proceso; `REDIS_URL` sigue solo documentada (PB-03).

Por qué: el endpoint es público y acepta una credencial en query; sin límite, un atacante puede intentar UUIDs (aunque el espacio sea grande) o martillar la DB. 10/min por IP replica el criterio de `POST /api/turnos` y no molesta al paciente que hace una o dos llamadas.

Alternativa descartada: limitar solo los `403`. Motivo: requiere contar después de resolver la credencial y deja pasar el costo de DB; el limitador debe correr antes.

Alternativa descartada: un límite más laxo (30/min como lecturas). Motivo: las cancelaciones escriben y son acciones sensibles; 10/min es el precedente de escritura pública.

### D-9. Soft cancel, nunca `DELETE` físico

Qué: la ruta HTTP usa el verbo `DELETE`, pero la única mutación permitida es `estado=cancelado` (más `updated_at`). No se ejecuta `session.delete(turno)` ni SQL `DELETE` sobre `turno`, `notificacion` ni `auditoria_turno`. El turno cancelado se conserva para reportes y ausentismo y deja de bloquear el slot porque el EXCLUDE y los índices parciales filtran por estado activo.

Por qué: regla dura 3 y RN-TU-07; "liberar el slot" es semántico (el turno deja de ser activo), no una eliminación de fila. Cualquier `DELETE` físico rompería la FK de notificaciones/auditoría y el historial.

Alternativa descartada: borrar el turno cancelado. Motivo: pierde historial, viola Ley 25.326/reportes y las FK lo impedirían.

### D-10. TZ/UTC, `inicio` aware y ausencia de expiración independiente del token

Qué: `inicio` se lee como `timestamptz` (aware) y se normaliza a UTC; `now` viene de un proveedor inyectable (`service.now_utc` o uno propio del módulo) y se normaliza a UTC. La comparación se hace entre instantes aware. Si por un dato corrupto `inicio` llegara naive, se rechaza como `500`/no cancelable en vez de asumir zona silenciosamente. No existe expiración de token separada del turno: el token vale mientras el turno exista; su ventana útil la define la regla de ≥3 h y el estado. Un turno ya iniciado o pasado cae en `inicio - now < 3 h` → `422 fuera_de_plazo`, no en `403`.

Por qué: el proyecto persiste UTC y muestra local (regla dura 10); asumir Argentina para naive crearía un dato ambiguo. Inventar una expiración de token requeriría schema nuevo y una regla de negocio que la KB no tiene. "Token expirado" en la spec se interpreta como token de un turno ya no cancelable (inicio pasado) o token que no existe: `422` en el primer caso y `403` en el segundo.

Alternativa descartada: agregar `token_expira_at` con migración. Motivo: no está en RN/KB, no hay requisito de US-005 y el token ya tiene ciclo de vida atado al turno.

Alternativa descartada: comparar contra `datetime.utcnow()` directo. Motivo: impide tests deterministas del borde exacto de 3 h; se inyecta el reloj.

### D-11. Contrato HTTP, códigos de error y contacto del consultorio

Qué:
- Éxito `200` con `CancelacionOut`: `id`, `estado` (`cancelado`), `inicio`, `fin`, `duracion_min`, `notificaciones_encoladas`, `mensaje` (`"Turno cancelado"`); sin DNI, teléfono, email ni token.
- `403` genérico: `{"detail": "No autorizado"}` para token ausente/vacío/malformado/no corresponde/id inexistente/malformado.
- `400` por campo solo para parámetros de query extra (regla dura 1).
- `422` con `detail` objeto: `{codigo, mensaje}` para `turno_ya_cancelado`, `turno_no_cancelable` y `cancelacion_fuera_de_plazo`; este último agrega `contacto`.
- `429` + `Retry-After` (D-8).
- `500` genérico para errores inesperados.

`CONSULTORIO_CONTACTO` es una variable opcional nueva (no secreta, default `"Comunicate con el consultorio para coordinar la cancelación"`) usada solo en el `422` de fuera de plazo; se documenta en `.env.example`. No se agrega a las obligatorias de `service-config` (tiene default).

Por qué: US-005 CA-2 exige "mensaje y contacto del consultorio"; sin una fuente de contacto el texto sería incompleto. Una variable opcional evita romper el boot y no inventa un teléfono.

Alternativa descartada: hardcodear un teléfono ficticio. Motivo: dato falso en producción y regla dura 12 (nada de datos reales/ficticios confundibles); la operación configura el real sin tocar código.

Alternativa descartada: reutilizar `FRONTEND_URL` como contacto. Motivo: no es un canal de contacto del consultorio y confunde al paciente.

### D-12. Sin migración

Qué: no se crean columnas, tablas, índices, enums ni constraints. Se reutilizan `turno.estado`, `turno.token_cancelacion` (`ux_turno_token`), `turno.updated_at`, `notificacion` (con `notif_tipo.cancelacion` ya en el enum), `auditoria_turno` y los índices existentes. `alembic upgrade head` no cambia.

Por qué: la operación es un cambio de estado y un insert en tablas existentes; C-05 D-13 y C-08 D-12 ya fijaron que `payload.enviar_en` cubre la programación sin columna nueva.

Alternativa descartada: agregar `cancelado_at` o `cancelado_por` a `turno`. Motivo: no lo pide la KB; `updated_at` y `AuditoriaTurno` cubren el rastro sin schema nuevo.

### D-13. Respuesta y pruebas sin datos reales

Qué: los tests usan DNI sintéticos, dominio `.test` y tokens UUID aleatorios (regla dura 12). El reloj se inyecta para el borde exacto de 3 h; el único mock de borde permitido es el reloj y, si se prueba el aislamiento del encolado, un fallo simulado del insert; la persistencia corre contra Postgres real (`db_session`). La suite no ejecuta SMTP.

Por qué: regla dura 9 y precedente de C-05; el borde `== 3 h` es imposible de probar de forma estable con reloj real.

Alternativa descartada: dormir para probar el borde. Motivo: tests lentos y flaky.

## Risks / Trade-offs

- [Riesgo] Un `400` por query extra podría revelar que `dni`/`telefono` no son credenciales válidas → Mitigación: es el contrato de la regla dura 1 y no distingue existencia de turnos; el 403 uniforme cubre toda falla de token/id.
- [Riesgo] Comparar `token` en SQL puede tener diferencias de tiempo entre match/no match → Mitigación: la comparación es de tipos UUID en índice único; la alternativa de comparación constante en app no elimina el costo de DB y agrega una lectura previa. Se acepta en v1; el rate limit acota el sondeo.
- [Riesgo] El lock del turno durante el insert de notificación/auditoría alarga la transacción → Mitigación: son pocos inserts, sin SMTP dentro del lock; el envío queda para C-08.
- [Riesgo] Si el encolado falla, la cancelación queda sin mail → Mitigación: `notificaciones_encoladas=false` en respuesta y auditoría, log de warning; se prioriza no bloquear la operación (regla dura 5).
- [Trade-off] La segunda cancelación responde `422` y no `200` → Mitigación: es el contrato de Flujo 2; los efectos laterales sí son idempotentes.
- [Riesgo] `CONSULTORIO_CONTACTO` sin configurar deja un texto genérico → Mitigación: default claro y variable documentada en `.env.example`; operación la ajusta en deploy.
- [Riesgo] Un turno con `inicio` corrupto/naive podría romper la resta → Mitigación: DB usa `timestamptz`; se normaliza y se responde `500` genérico en vez de asumir zona.
- [Trade-off] Rate limit en-proceso se resetea en deploy y no se comparte entre procesos → Mitigación: v1 single-host (PB-03); `REDIS_URL` documentada.

## Migration Plan

1. Sin migración Alembic: `alembic upgrade head` queda igual; verificar que `001_core_models`/`002_agenda_meta` ya están aplicadas.
2. Deploy del router/servicio/schemas nuevos; agregar `CONSULTORIO_CONTACTO` opcional a `.env.example` (sin secreto).
3. Rollback: redeploy sin la ruta; los turnos cancelados se conservan como historial (regla dura 3). No ejecutar `downgrade` por este change.

## Open Questions

- Ninguna que cambie el contrato. El valor real de `CONSULTORIO_CONTACTO` (teléfono/WhatsApp/instrucción) lo define operación en deploy; el default no bloquea v1.
