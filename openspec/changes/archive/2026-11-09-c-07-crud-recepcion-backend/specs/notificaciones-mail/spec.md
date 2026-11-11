# notificaciones-mail Specification

## Purpose

Define la cola de notificaciones por mail, los reintentos con backoff, el descarte de notificaciones obsoletas y el panel staff de fallidas. Este delta agrega el motivo de descarte `turno_reprogramado` introducido por C-07 y lo excluye del panel de fallidas SMTP.

## MODIFIED Requirements

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

## ADDED Requirements

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
