# notificaciones-mail Specification

## Purpose

Entrega asíncrona de los mails de turno (confirmación, recordatorios y cancelación) por SMTP, con reintentos acotados, descarte de mails obsoletos y visibilidad staff de los envíos fallidos.

## Requirements

### Requirement: Despacho de notificaciones vencidas

The system SHALL send every `Notificacion` with `estado=pendiente` whose `payload.enviar_en` is at or before the current time, and SHALL mark it `enviada` with `enviada_at` set only after SMTP confirms acceptance. A notification whose `enviar_en` is in the future SHALL remain untouched. (RN-NO-01, US-009 CA-1.)

#### Scenario: Confirmación vencida se envía y queda enviada

- **DADO** una `Notificacion` tipo `confirmacion`, estado `pendiente`, `intentos=0` y `payload.enviar_en` anterior o igual al reloj del worker
- **CUANDO** corre un ciclo del worker
- **ENTONCES** el mail de confirmación se envía una vez por el borde SMTP; la fila queda `estado=enviada` con `enviada_at` no nulo; y no se modifica el `estado` del turno (RN-NO-01, US-009 CA-1)

#### Scenario: Recordatorio vencido con turno activo se envía

- **DADO** una `Notificacion` tipo `recordatorio_24h` o `recordatorio_2h`, `pendiente`, vencida, cuyo turno está `reservado` o `confirmado`
- **CUANDO** corre un ciclo del worker
- **ENTONCES** el recordatorio se envía una vez y la fila queda `enviada` (RN-NO-01, RN-NO-02)

#### Scenario: Notificación futura permanece pendiente

- **DADO** una `Notificacion` `pendiente` cuyo `payload.enviar_en` es posterior al reloj del worker
- **CUANDO** corre un ciclo del worker
- **ENTONCES** no se envía ningún mail y la fila sigue `pendiente` con `intentos=0` (RN-NO-01)

### Requirement: Reintentos con backoff y fallida tras tres intentos

The system SHALL retry a failed SMTP send up to three total attempts. On each failure it SHALL increment `intentos` and persist a diagnostic `error`; while attempts remain it SHALL keep the notification `pendiente` and re schedule it to `now + 5 × intentos` minutes. After the third failure it SHALL set `estado=fallida`. (RN-NO-02, duro 6.)

#### Scenario: Primer fallo SMTP reprograma con backoff

- **DADO** una `Notificacion` `pendiente` con `intentos=0` vencida y un borde SMTP que rechaza el envío
- **CUANDO** corre un ciclo del worker
- **ENTONCES** la fila sigue `pendiente` con `intentos=1`, `error` no nulo y `payload.enviar_en` igual a `now + 5 minutos` (RN-NO-02)

#### Scenario: Segundo fallo aplica backoff de diez minutos

- **DADO** una `Notificacion` `pendiente` con `intentos=1` vencida y un borde SMTP que rechaza el envío
- **CUANDO** corre un ciclo del worker
- **ENTONCES** la fila sigue `pendiente` con `intentos=2` y `payload.enviar_en` igual a `now + 10 minutos` (RN-NO-02)

#### Scenario: Tercer fallo deja la notificación fallida y visible

- **DADO** una `Notificacion` `pendiente` con `intentos=2` vencida y un borde SMTP que rechaza el envío
- **CUANDO** corre un ciclo del worker
- **ENTONCES** la fila queda `estado=fallida` con `intentos=3` y `error` con el motivo del fallo, y aparece en el panel staff de fallidas (RN-NO-02, US-009 CA-3)

#### Scenario: Reintento exitoso marca enviada

- **DADO** una `Notificacion` `pendiente` con `intentos=1` vencida y un borde SMTP que acepta el envío
- **CUANDO** corre un ciclo del worker
- **ENTONCES** la fila queda `estado=enviada`, `enviada_at` no nulo y `error` nulo (RN-NO-02)

### Requirement: Recordatorio descartado si el turno ya no está activo

The system SHALL NOT send `confirmacion`, `recordatorio_24h` or `recordatorio_2h` when the related turno is not `reservado` or `confirmado`. It SHALL mark the notification `fallida` with a `turno_cancelado` reason, WITHOUT incrementing `intentos` and WITHOUT treating it as an SMTP failure. (RN-NO-01, RN-TU-07, Flujo 4 paso 3.)

#### Scenario: Turno cancelado no recibe recordatorio

- **DADO** una `Notificacion` `pendiente` vencida de tipo `recordatorio_2h` cuyo turno está `cancelado`
- **CUANDO** corre un ciclo del worker
- **ENTONCES** no se envía ningún mail; la notificación queda `fallida` con motivo `turno_cancelado` e `intentos` sin cambios; y no aparece en el panel de fallidas SMTP (RN-NO-01, Flujo 4)

#### Scenario: Turno atendido no recibe recordatorio vencido

- **DADO** una `Notificacion` `pendiente` vencida de tipo `recordatorio_24h` cuyo turno está `atendido` o `ausente`
- **CUANDO** corre un ciclo del worker
- **ENTONCES** no se envía ningún mail y la notificación se descarta con motivo `turno_cancelado` (RN-NO-01, Flujo 4)

#### Scenario: Notificación ya descartada por reprogramación no se reenvía

- **DADO** una `Notificacion` de tipo `confirmacion` que quedó `fallida` con `error="turno_reprogramado: ..."` tras una reprogramación, y un turno que sigue `reservado`
- **CUANDO** corre un ciclo del worker
- **ENTONCES** el worker no la toma (ya no está `pendiente`), no se envía ningún mail viejo y `intentos` sigue intacto (RN-NO-01)

### Requirement: Mail de cancelación se envía aunque el turno esté cancelado

The system SHALL send a `cancelacion` notification even when its turno is `cancelado`, because it is enqueued by the cancellation flow after the state change. The active-turno filter SHALL apply only to confirmation and reminder types. (RN-NO-01, Flujo 2 paso 3.)

#### Scenario: Mail de cancelación se envía con turno cancelado

- **DADO** una `Notificacion` `pendiente` vencida de tipo `cancelacion` cuyo turno está `cancelado`
- **CUANDO** corre un ciclo del worker
- **ENTONCES** el mail de cancelación se envía una vez y la fila queda `enviada` (Flujo 2 paso 3)

### Requirement: Contrato de payload y payload incompleto

The system SHALL require `turno_id`, `tipo`, `enviar_en`, `paciente_nombre`, `paciente_email`, `profesional_nombre`, `inicio`, `fin`, `duracion_min`, `token_cancelacion` and `cancel_url` in `payload`. When a required key is missing, empty or unparseable, it SHALL mark the notification `fallida` with a `payload_incompleto` reason, SHALL NOT call SMTP and SHALL keep processing the rest of the batch. (RN-NO-01, duro 5.)

#### Scenario: Payload sin mail del paciente se marca fallida sin romper el lote

- **DADO** una `Notificacion` `pendiente` vencida cuyo `payload` no tiene `paciente_email`, junto con otra notificación válida en la misma tanda
- **CUANDO** corre un ciclo del worker
- **ENTONCES** la notificación incompleta queda `fallida` con motivo `payload_incompleto` sin invocar SMTP; la notificación válida se envía; y el ciclo termina sin excepción (RN-NO-01)

#### Scenario: enviar_en inválido se marca fallida

- **DADO** una `Notificacion` `pendiente` cuyo `payload.enviar_en` no es un timestamp ISO-8601 UTC parseable
- **CUANDO** corre un ciclo del worker
- **ENTONCES** la fila queda `fallida` con motivo `payload_incompleto`, sin llamada SMTP y sin afectar otras filas (RN-NO-01)

### Requirement: Panel staff de notificaciones fallidas

The system SHALL expose `GET /api/notificaciones/fallidas` to `recepcion` and `admin` only, returning only SMTP/`payload_incompleto` failures (not discarded ones, including `turno_cancelado:` and `turno_reprogramado:`), ordered by turno start descending with an opaque keyset cursor. It SHALL return `id`, `turno_id`, `tipo`, `intentos`, `error`, `enviar_en`, `paciente_nombre`, `paciente_email`, `inicio` and `fin` per item, and SHALL reject unknown query fields or invalid cursors with `400` per field. (RN-NO-02, duro 1, duro 7.)

#### Scenario: Recepción lista fallidas con paginación keyset

- **DADO** tres notificaciones `fallida` por SMTP de turnos con inicios distintos y una `fallida` por `turno_cancelado`
- **CUANDO** un usuario `recepcion` pide `GET /api/notificaciones/fallidas?limit=2`
- **ENTONCES** responde `200` con dos items ordenados por inicio de turno descendente, `next_cursor` no nulo y sin incluir la descartada; al pedir el cursor devuelve el item restante y `next_cursor=null` (RN-NO-02, duro 7)

#### Scenario: Las fallidas por reprogramación no aparecen en el panel

- **DADO** dos notificaciones `fallida`: una por SMTP y otra con `error="turno_reprogramado: 2026-11-08T12:00:00Z"` de un turno que sigue activo
- **CUANDO** un usuario `recepcion` pide `GET /api/notificaciones/fallidas`
- **ENTONCES** responde `200` y devuelve solo la fallida SMTP; la descartada por reprogramación queda excluida (RN-NO-02, C-07)

#### Scenario: Odontólogo no accede al panel de fallidas

- **DADO** una sesión válida con rol `odontologo`
- **CUANDO** pide `GET /api/notificaciones/fallidas`
- **ENTONCES** responde `403` genérico y no se devuelve ningún item (RBAC C-03, duro 4)

#### Scenario: Sin sesión responde 401

- **DADO** un cliente sin cookie de sesión
- **CUANDO** pide `GET /api/notificaciones/fallidas`
- **ENTONCES** responde `401` genérico (RBAC C-03)

#### Scenario: Parámetro desconocido responde 400 por campo

- **DADO** un usuario `recepcion` autenticado
- **CUANDO** pide `GET /api/notificaciones/fallidas?orden=asc`
- **ENTONCES** responde `400` con `detail` por `campo="orden"` y no se listan items (duro 1)

#### Scenario: Cursor inválido responde 400 por campo

- **DADO** un usuario `admin` autenticado y `cursor="no-es-un-cursor"`
- **CUANDO** pide `GET /api/notificaciones/fallidas`
- **ENTONCES** responde `400` con `detail` por `campo="cursor"` (duro 1)

### Requirement: Worker en-proceso con ciclo configurable

The system SHALL run the mail worker inside the API process as a single-process background job, started and stopped with the application lifespan, with a configurable interval between 5 and 10 minutes (default 5). It SHALL NOT start when disabled by configuration, SHALL prevent overlapping runs of the same job, and SHALL NOT require Redis or an external queue in v1. (PB-03, DD-05/SU-03, duro 6.)

#### Scenario: Scheduler arranca con la aplicación habilitada

- **DADO** `NOTIF_WORKER_ENABLED=true` y un intervalo configurado de 5 minutos
- **CUANDO** arranca la aplicación
- **ENTONCES** el job queda registrado con trigger de intervalo de 5 minutos y arranca junto con el lifespan (PB-03)

#### Scenario: Scheduler no arranca en tests o con el flag apagado

- **DADO** `NOTIF_WORKER_ENABLED=false`
- **CUANDO** arranca la aplicación
- **ENTONCES** no se registra ni ejecuta ningún job de envío, y la API responde normalmente (PB-03)

#### Scenario: Ciclos solapados no duplican envíos

- **DADO** un ciclo del worker todavía en ejecución
- **CUANDO** el scheduler dispara un segundo ciclo
- **ENTONCES** el segundo ciclo se omite y cada notificación se envía a lo sumo una vez por ciclo efectivo (duro 6)

### Requirement: SMTP configurable por entorno y aislado del turno

The system SHALL send mail over SMTP using `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM` and `SMTP_TIMEOUT_S`, with TLS on port 587 and implicit TLS on port 465, reading secrets only from environment. A send failure SHALL NEVER change the related turno nor abort the worker batch. In tests the SMTP boundary is the only mocked component. (PB-05, duro 9, duro 10.)

#### Scenario: Fallo SMTP no modifica el turno

- **DADO** una `Notificacion` vencida y un borde SMTP que lanza una excepción de conexión
- **CUANDO** corre un ciclo del worker
- **ENTONCES** la notificación se reprograma o queda `fallida` según los intentos, el turno conserva su `estado` y el ciclo continúa con la siguiente fila (RN-NO-02, duro 5)

#### Scenario: Secreto SMTP nunca se expone

- **DADO** la configuración de entorno de la aplicación
- **CUANDO** se inspeccionan los artefactos y la respuesta del panel de fallidas
- **ENTONCES** `SMTP_PASS` no aparece en el repo, en `payload`, en `error` ni en logs, y el panel solo devuelve los campos declarados (duro 10)

### Requirement: Plantillas de mail con datos mínimos y link de cancelación

The system SHALL build each mail with a subject and body per notification type containing the patient name, professional name, local date and time, duration and the cancellation link. It SHALL render times in `America/Argentina/Buenos_Aires` while persisting UTC, and SHALL NOT include DNI, phone or obra social. (RN-NO-01, duro 10, duro 12.)

#### Scenario: Mail de recordatorio incluye link y hora local

- **DADO** una `Notificacion` válida de tipo `recordatorio_24h` con `payload.inicio` en UTC
- **CUANDO** el worker construye y envía el mail
- **ENTONCES** el asunto y el cuerpo están en español, incluyen la hora local de Buenos Aires, el nombre del profesional y `payload.cancel_url` como link `GET /cancelar?token=` (RN-NO-01, PB-01)

#### Scenario: Mail no incluye datos sensibles innecesarios

- **DADO** una `Notificacion` válida con `payload` sin DNI, teléfono ni obra social
- **CUANDO** el worker construye el mail
- **ENTONCES** el cuerpo no contiene DNI, teléfono ni obra social, y solo usa los campos declarados del payload (duro 12)

### Requirement: Observabilidad de envíos y fallos

The system SHALL emit one structured log entry per sent, retried, discarded and failed notification, including notification id, type, attempt count and outcome, without including secrets or sensitive patient data beyond the masked recipient. Logging SHALL NOT block or abort the batch. (RN-NO-02.)

#### Scenario: Envío exitoso deja rastro estructurado

- **DADO** una `Notificacion` vencida y un borde SMTP que acepta el envío
- **CUANDO** corre un ciclo del worker
- **ENTONCES** se emite un log con `notificacion_id`, `tipo`, `intentos` y resultado `enviada`, y la fila persiste `enviada_at` (RN-NO-02)

#### Scenario: Fallo deja rastro y no propaga excepción

- **DADO** una `Notificacion` vencida y un borde SMTP que falla
- **CUANDO** corre un ciclo del worker
- **ENTONCES** se emite un log con resultado `reintento` o `fallida` y el motivo, sin `SMTP_PASS` ni datos sensibles, y el ciclo termina normalmente (RN-NO-02)

### Requirement: Descarte de notificaciones obsoletas por reprogramación

The system SHALL provide a way to discard the pending `confirmacion`, `recordatorio_24h` and `recordatorio_2h` notifications of a turno when it is rescheduled, marking them `fallida` with an `error` prefixed `turno_reprogramado:` WITHOUT incrementing `intentos` and WITHOUT calling SMTP. It SHALL classify that prefix as a discard (not an SMTP failure) so discarded rows never reach the failed-notifications panel. (RN-NO-01, RN-NO-02, duro 5, C-07.)

#### Scenario: El prefijo turno_reprogramado se clasifica como descarte

- **DADO** una `Notificacion` `fallida` con `error="turno_reprogramado: inicio 2026-11-08T12:00:00Z -> 2026-11-09T12:00:00Z"`
- **CUANDO** el servicio de notificaciones clasifica el error
- **ENTONCES** devuelve la categoría de descarte, no la de fallo SMTP, y el panel de fallidas la excluye (RN-NO-02)

#### Scenario: Descartar pendientes no altera intentos ni invoca SMTP

- **DADO** un turno con una `confirmacion` y dos recordatorios `pendiente`, todos con `intentos=0`
- **CUANDO** se ejecuta el descarte por reprogramación
- **ENTONCES** las tres filas quedan `fallida` con `error` que empieza con `turno_reprogramado:`, `intentos` sigue en `0` y no se llamó a SMTP (RN-NO-01, duro 5)

#### Scenario: El descarte no afecta notificaciones de otros turnos

- **DADO** dos turnos, cada uno con notificaciones `pendiente`
- **CUANDO** se reprograma uno de ellos
- **ENTONCES** solo las notificaciones del turno reprogramado quedan `fallida` con `turno_reprogramado:`; las del otro turno siguen `pendiente` (RN-NO-02)

#### Scenario: Una notificación enviada nunca se marca fallida por reprogramación

- **DADO** una `Notificacion` con `estado=enviada` del turno a reprogramar
- **CUANDO** se ejecuta el descarte
- **ENTONCES** la fila `enviada` permanece intacta; el descarte solo toca filas `pendiente` (RN-NO-02)
