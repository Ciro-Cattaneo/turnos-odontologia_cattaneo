# cancelacion-paciente Specification

## Purpose

Define la cancelación pública del turno por el paciente con `token_cancelacion` como única credencial, la regla de anticipación mínima, la liberación del slot, el encolado del mail de cancelación y la auditoría de la transición.

## Requirements

### Requirement: Cancelación válida, ventana mínima y liberación del slot

The system SHALL cancel a `reservado`/`confirmado` turno when the token matches and `inicio - now >= CANCEL_HOURS_MIN`, responding `200`, setting `estado=cancelado`, preserving the row and freeing the slot. Outside the window it SHALL respond `422` with a message and contact without changing anything. (RN-TU-04, RN-TU-07, US-005 CA-1/CA-2.)

#### Scenario: Cancelación con más de 3h libera el slot y responde 200

- **DADO** un turno `reservado` con `inicio` a más de 3 horas del reloj, un token válido y una ventana de disponibilidad que cubre ese turno
- **CUANDO** se hace `DELETE /api/turnos/{id}?token=<token>`
- **ENTONCES** responde `200`; la fila `turno` persiste con `estado=cancelado`; el slot vuelve a aparecer libre y una nueva reserva del mismo horario responde `201` (RN-TU-04, RN-TU-07)

#### Scenario: Cancelación de un turno confirmado procede igual que reservado

- **DADO** un turno `confirmado` con anticipación mayor a 3 horas y su token válido
- **CUANDO** se hace `DELETE /api/turnos/{id}?token=<token>`
- **ENTONCES** responde `200` y la fila queda `estado=cancelado`, porque ambas transiciones `reservado|confirmado → cancelado` son válidas (RN-TU-07)

#### Scenario: Exactamente 3 horas de anticipación se acepta

- **DADO** un reloj fijo y un turno cuyo `inicio` es exactamente `now + CANCEL_HOURS_MIN`
- **CUANDO** se hace `DELETE /api/turnos/{id}?token=<token>`
- **ENTONCES** responde `200` y el turno queda `estado=cancelado`, porque el borde se evalúa con `>=` (RN-TU-04, US-005 CA-1)

#### Scenario: Cancelación con menos de 3h responde 422 con contacto

- **DADO** un turno `reservado` cuyo `inicio` está a 2 horas 59 minutos del reloj y su token válido
- **CUANDO** se hace `DELETE /api/turnos/{id}?token=<token>`
- **ENTONCES** responde `422` con `detail.codigo="cancelacion_fuera_de_plazo"`, un mensaje en español y `detail.contacto` no vacío; el turno sigue `reservado`; no se encola ninguna `Notificacion` y no se escribe auditoría (RN-TU-04, US-005 CA-2)

#### Scenario: Ventana de cancelación expirada responde 422 y no 403

- **DADO** un turno `reservado` cuyo `inicio` es anterior al reloj, con token válido
- **CUANDO** se hace `DELETE /api/turnos/{id}?token=<token>`
- **ENTONCES** responde `422` con `detail.codigo="cancelacion_fuera_de_plazo"` y el turno no cambia, porque el token es válido pero la ventana de cancelación expiró (RN-TU-04)

#### Scenario: El umbral respeta CANCEL_HOURS_MIN configurado

- **DADO** `CANCEL_HOURS_MIN=5` y un turno cuyo `inicio` está a 4 horas del reloj
- **CUANDO** se hace `DELETE /api/turnos/{id}?token=<token>`
- **ENTONCES** responde `422` con `detail.codigo="cancelacion_fuera_de_plazo"`, porque la regla usa el valor configurado y no un 3 fijo (RN-TU-04)

#### Scenario: La cancelación no elimina la fila del turno

- **DADO** una cancelación válida que responde `200`
- **CUANDO** se consulta la tabla `turno` por ese `id`
- **ENTONCES** la fila sigue existiendo con `estado=cancelado` y no se ejecutó ningún borrado físico (regla dura 3)

### Requirement: Token de cancelación como única credencial con 403 genérico

The system SHALL accept only `?token=<token_cancelacion>` as credential and SHALL respond the same generic `403` for a missing, empty, malformed or non-matching token, and for a non-existent or malformed turno id, without revealing whether the turno exists. (PB-01, RN-TU-06, regla dura 4.)

#### Scenario: Token válido del turno habilita la cancelación

- **DADO** un turno `reservado` cancelable y su `token_cancelacion` correcto, sin otros parámetros de query
- **CUANDO** se hace `DELETE /api/turnos/{id}?token=<token>`
- **ENTONCES** responde `200` y la credencial es aceptada, sin requerir cookie, header de autorización ni login (PB-01, RN-TU-06)

#### Scenario: Token inválido responde 403 genérico sin efectos

- **DADO** un turno `reservado` con anticipación mayor a 3 horas y un token que no corresponde a ningún turno
- **CUANDO** se hace `DELETE /api/turnos/{id}?token=<token_invalido>`
- **ENTONCES** responde `403` con el cuerpo genérico `{"detail": "No autorizado"}`; el turno sigue `reservado`; no se encola mail ni se escribe auditoría (PB-01, regla dura 4)

#### Scenario: Token ausente, vacío o mal formado responde 403 genérico

- **DADO** un turno existente y solicitudes sin `token`, con `token=` vacío o con `token="no-es-uuid"` (casos parametrizados)
- **CUANDO** se hace `DELETE /api/turnos/{id}` en cada caso
- **ENTONCES** todas responden `403` con el mismo cuerpo genérico, sin distinguir el motivo ni revelar si el turno existe (PB-01, regla dura 4)

#### Scenario: Token válido de otro turno responde 403 genérico

- **DADO** dos turnos existentes y el token del turno A
- **CUANDO** se hace `DELETE /api/turnos/{id_B}?token=<token_A>`
- **ENTONCES** responde `403` genérico y el turno B no cambia, porque el token identifica un turno específico (RN-TU-06, regla dura 4)

#### Scenario: Id inexistente o mal formado responde 403 genérico

- **DADO** un UUID de turno que no existe en la base, o un `id` que no parsea como UUID, con un token bien formado (casos parametrizados)
- **CUANDO** se hace `DELETE /api/turnos/{id}?token=<token>`
- **ENTONCES** ambos responden `403` genérico, igual que un token inválido, sin revelar la inexistencia ni el formato esperado (PB-01, regla dura 4)

### Requirement: No existe credencial alternativa

The system SHALL reject any query parameter other than `token` with `400` per field and SHALL NOT accept DNI, teléfono, email, body credentials or a "mis turnos" route for cancellation. (PB-01, RN-TU-06, regla dura 1, regla dura 4.)

#### Scenario: Solo el token válido por query permite cancelar

- **DADO** un turno cancelable y una solicitud `DELETE /api/turnos/{id}?token=<token>` sin otros parámetros ni body
- **CUANDO** se procesa la solicitud
- **ENTONCES** responde `200` y el turno queda `cancelado`, porque el token por query es la única ruta de credencial aceptada (PB-01, RN-TU-06)

#### Scenario: DNI y teléfono como query no cancelan el turno

- **DADO** un turno existente y una solicitud `DELETE /api/turnos/{id}?dni=<dni>&telefono=<telefono>` con o sin `token`
- **CUANDO** se procesa la solicitud
- **ENTONCES** responde `400` con `detail` por `campo="dni"` y `campo="telefono"`; el turno no cambia y no se encola mail (PB-01, regla dura 1, regla dura 4)

#### Scenario: Un token en el body no autentica la cancelación

- **DADO** un turno existente y un body que contiene su `token_cancelacion`, pero la query no trae `token`
- **CUANDO** se hace `DELETE /api/turnos/{id}` con ese body
- **ENTONCES** responde `403` genérico y el turno no cambia, porque la única credencial aceptada es el token por query (PB-01, RN-TU-06)

#### Scenario: El parámetro token repetido no habilita la cancelación

- **DADO** un turno existente y una solicitud con `token=<token_valido>&token=<otro_token>`
- **CUANDO** se procesa la solicitud
- **ENTONCES** responde `400` con `detail` en `campo="token"` y el turno no se cancela, porque la query no tiene la forma estricta del contrato (PB-01, regla dura 1)

### Requirement: Estados cancelables y transición única bajo concurrencia

The system SHALL respond `422` when the matching token belongs to a turno already `cancelado`, `atendido` or `ausente`, SHALL NOT change state, enqueue another mail or write another audit, and SHALL serialize concurrent cancellations so exactly one transition occurs. (RN-TU-07, Flujo 2, regla dura 2.)

#### Scenario: Turno reservado con token válido es cancelable

- **DADO** un turno `reservado` con anticipación suficiente y su token válido
- **CUANDO** se hace `DELETE /api/turnos/{id}?token=<token>`
- **ENTONCES** responde `200` y la fila queda `estado=cancelado` (RN-TU-07)

#### Scenario: Turno ya cancelado responde 422 sin efectos laterales

- **DADO** un turno `cancelado` con su token válido y una `Notificacion` de cancelación ya encolada
- **CUANDO** se repite `DELETE /api/turnos/{id}?token=<token>`
- **ENTONCES** responde `422` con `detail.codigo="turno_ya_cancelado"`; no se modifica `updated_at`, no se encola otra `Notificacion` y no se agrega otra fila de auditoría (RN-TU-07, Flujo 2)

#### Scenario: Turno atendido o ausente responde 422

- **DADO** un turno con `estado=atendido` o `estado=ausente` (casos parametrizados) y su token válido
- **CUANDO** se hace `DELETE /api/turnos/{id}?token=<token>`
- **ENTONCES** responde `422` con `detail.codigo="turno_no_cancelable"` y el estado no cambia (RN-TU-07)

#### Scenario: Dos cancelaciones concurrentes producen un solo efecto

- **DADO** dos transacciones reales que cancelan el mismo turno con el mismo token; la primera ya tomó el lock del turno y todavía no commiteó
- **CUANDO** la segunda intenta cancelar el mismo turno
- **ENTONCES** la segunda espera el lock, luego responde `422 turno_ya_cancelado` (no `500`); en la base hay una sola transición a `cancelado`, una sola `Notificacion cancelacion` y una sola fila de auditoría (RN-TU-07, regla dura 2)

### Requirement: Mail de cancelación encolado sin bloquear la operación

The system SHALL enqueue exactly one `Notificacion` of type `cancelacion`, `canal=mail`, `estado=pendiente` and `intentos=0` for a successful cancellation, using the frozen 11-key payload contract with ISO-8601 UTC timestamps, and SHALL commit the cancellation even if enqueueing fails. (RN-NO-01, regla dura 5.)

#### Scenario: Cancelación exitosa encola un mail cancelacion pendiente

- **DADO** una cancelación válida que responde `200`
- **CUANDO** se consultan las `Notificacion` del turno
- **ENTONCES** existe exactamente una fila nueva de tipo `cancelacion`, `canal=mail`, `estado=pendiente`, `intentos=0` y `enviada_at=NULL`; su `payload` contiene las 11 claves de C-08 y `payload.enviar_en` es un string ISO-8601 UTC; la respuesta informa `notificaciones_encoladas=true` (RN-NO-01, regla dura 5)

#### Scenario: Fallo del encolado no deshace la cancelación

- **DADO** una cancelación válida y un fallo simulado del insert de `Notificacion`
- **CUANDO** se hace `DELETE /api/turnos/{id}?token=<token>`
- **ENTONCES** responde `200`; el turno queda `cancelado`; la auditoría y la respuesta informan `notificaciones_encoladas=false`; no se propaga un error de servidor (regla dura 5)

#### Scenario: C-06 no envía SMTP ni duplica la cola

- **DADO** una cancelación válida
- **CUANDO** se ejecuta la solicitud sin correr el worker de C-08
- **ENTONCES** no se llama a SMTP, la `Notificacion cancelacion` queda `pendiente` para el worker y no se crea ninguna estructura de cola alternativa (RN-NO-01, C-08 D-8)

### Requirement: Auditoría append-only con actor paciente y token

The system SHALL write one `AuditoriaTurno` row in the same transaction as a successful cancellation, with `accion="cancelar"`, `actor_id=NULL`, and a detail identifying the paciente/token credential and the previous state, without persisting the token value. (KB-04 §AuditoriaTurno, RN-AU-02, regla dura 3.)

#### Scenario: Cancelación escribe auditoría con actor paciente

- **DADO** una cancelación válida que responde `200`
- **CUANDO** se consulta `auditoria_turno` para el turno
- **ENTONCES** existe exactamente una fila con `accion="cancelar"`, `actor_id=NULL` y `detalle` con `actor="paciente"`, `credencial="token_cancelacion"`, `estado_previo`, `inicio`, `fin`, `duracion_min` y `notificaciones_encoladas`; `inicio`/`fin` son strings ISO-8601 UTC (RN-AU-02)

#### Scenario: Una solicitud rechazada no escribe auditoría

- **DADO** una solicitud con token inválido, fuera de plazo o sobre un turno no cancelable
- **CUANDO** se procesa y responde `403` o `422`
- **ENTONCES** no se agrega ninguna fila a `auditoria_turno` para ese turno (RN-AU-02, regla dura 3)

#### Scenario: La auditoría no guarda el token en claro

- **DADO** una cancelación válida y su `token_cancelacion`
- **CUANDO** se inspecciona el `detalle` de la auditoría
- **ENTONCES** el valor completo del token no aparece en `detalle` ni en logs, y solo se identifica el tipo de credencial (regla dura 10, regla dura 12)

### Requirement: Respuesta sin datos sensibles ni existencia filtrada

The system SHALL respond with only `id`, `estado`, `inicio`, `fin`, `duracion_min`, `notificaciones_encoladas` and `mensaje` on success, rendering datetimes as ISO-8601 UTC, and SHALL NOT include patient name, DNI, phone, email or token. (regla dura 4, regla dura 12.)

#### Scenario: Respuesta 200 no expone datos del paciente

- **DADO** una cancelación válida de un turno con paciente ficticio
- **CUANDO** se lee el cuerpo de la respuesta `200`
- **ENTONCES** solo aparecen los campos declarados; no aparecen `nombre`, `dni`, `telefono`, `email`, `obra_social` ni el `token_cancelacion`; `inicio` y `fin` son strings ISO-8601 UTC (regla dura 4, regla dura 12)

#### Scenario: Respuesta 403 no revela existencia ni datos del turno

- **DADO** un turno existente y un token inválido
- **CUANDO** se hace `DELETE /api/turnos/{id}?token=<token_invalido>`
- **ENTONCES** el cuerpo es siempre `{"detail": "No autorizado"}`, idéntico al de un id inexistente, y no incluye estado, fecha, paciente ni token (PB-01, regla dura 4)

#### Scenario: Un campo desconocido en la respuesta es imposible por contrato

- **DADO** el modelo de respuesta de cancelación con `extra="forbid"`
- **CUANDO** se serializa una respuesta exitosa
- **ENTONCES** el cliente recibe exactamente el conjunto de campos declarados y ningún campo interno del ORM (regla dura 1)

### Requirement: Rate limit del endpoint público de cancelación

The system SHALL rate-limit `DELETE /api/turnos/{id}` per client IP with a fixed window of 60 seconds and 10 attempts per IP, responding `429` with `Retry-After` in seconds when exceeded, without cancelling the turno for the rejected request. (RN-AU-03 por analogía, D-8.)

#### Scenario: Cancelación dentro del límite responde 200

- **DADO** una IP con menos de 10 intentos en la ventana de 60 segundos y un turno cancelable con token válido
- **CUANDO** se hace `DELETE /api/turnos/{id}?token=<token>`
- **ENTONCES** responde `200`, el turno queda `cancelado` y la IP consume un intento de la ventana (RN-AU-03, D-8)

#### Scenario: Exceso de intentos responde 429 sin cancelar

- **DADO** una IP que agotó sus 10 intentos en la ventana de 60 segundos y un token válido de un turno cancelable
- **CUANDO** hace un intento número 11
- **ENTONCES** responde `429` con el header `Retry-After`; el turno sigue `reservado` y no se encola mail (RN-AU-03, D-8)

#### Scenario: El intento 10 pasa y el 11 responde 429

- **DADO** una IP con 9 intentos consumidos en la ventana y un reloj fijo
- **CUANDO** hace el intento 10 y luego el 11
- **ENTONCES** el intento 10 se evalúa normalmente y el 11 responde `429` antes de evaluar la credencial, para frenar el sondeo de tokens (RN-AU-03, D-8)
