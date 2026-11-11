# recepcion-turnos Specification

## Purpose

Define la operación staff del turno desde recepción/administración: alta de mostrador con `origen=recepcion`, reprogramación y cambio de duración con anti-solape, cancelación normal y forzada `<3 h` con motivo, corrección de datos del paciente, transiciones de estado RN-TU-07 y ficha con historial auditable.

## ADDED Requirements

### Requirement: Alta staff de turno con origen recepcion

The system SHALL expose `POST /api/turnos` with a valid `recepcion`/`admin` session and body `origen=recepcion` to create a `reservado`/`recepcion` turno with the same five patient fields, duration and anti-overlap rules as online, enqueueing notifications and writing an audit row with the staff actor. Without a session, the public C-05 contract SHALL remain unchanged. (US-006 CA-1, RN-TU-01/02/03, RN-AU-02, duro 1/2/5.)

#### Scenario: Alta staff válida crea turno de recepción y responde 201

- **DADO** un profesional activo con `duracion_default_min=30`, una ventana que cubre el slot, una sesión `recepcion` y un body con `origen=recepcion`, `inicio` futuro y los cinco datos ficticios del paciente
- **CUANDO** se hace `POST /api/turnos` con esa sesión
- **ENTONCES** responde `201`; la fila `turno` persiste con `estado=reservado`, `origen=recepcion` y token no nulo; existe una sola fila `paciente` para ese DNI; la respuesta informa `notificaciones_encoladas=true`; y `auditoria_turno` registra `accion="crear"`, `actor_id` del staff y `detalle.origen="recepcion"` (RN-AU-02, US-006 CA-1)

#### Scenario: La respuesta staff no expone la credencial del paciente

- **DADO** un alta staff válida que responde `201`
- **CUANDO** se inspecciona el cuerpo de la respuesta
- **ENTONCES** el cuerpo contiene `id`, `estado`, `inicio`, `fin`, `duracion_min` y `notificaciones_encoladas`, y no contiene `token_cancelacion` ni `cancel_url`, porque el token solo circula por mail al paciente (RN-TU-06, duro 4)

#### Scenario: Sin sesión, `origen` en el body público sigue siendo 400 por campo

- **DADO** un cliente sin cookie de sesión y un body público válido de C-05 al que se le agrega `origen="recepcion"`
- **CUANDO** se hace `POST /api/turnos`
- **ENTONCES** responde `400` con `detail` en `campo="origen"` y no crea ninguna fila `turno`, porque el contrato público no admite `origen` (regla dura 1, no regresión de C-05)

#### Scenario: Sin sesión y body público válido sigue creando origen online

- **DADO** un cliente sin cookie y un body público válido sin `origen`, con profesional y slot disponibles
- **CUANDO** se hace `POST /api/turnos`
- **ENTONCES** responde `201` y la fila persiste con `origen=online` y `actor_id` de auditoría `NULL`, preservando reserva-online

#### Scenario: Odontólogo no puede crear turnos

- **DADO** una sesión válida con rol `odontologo` y un body staff válido
- **CUANDO** se hace `POST /api/turnos`
- **ENTONCES** responde `403` genérico y no se crea turno ni paciente (RN-AU-01, staff-auth)

#### Scenario: Body staff incompleto responde 400 por campo

- **DADO** una sesión `recepcion` y un body con `paciente={}` y `origen=recepcion`
- **CUANDO** se hace `POST /api/turnos`
- **ENTONCES** responde `400`; `detail` contiene entradas para `paciente.nombre`, `paciente.dni`, `paciente.telefono`, `paciente.obra_social` y `paciente.email`; y no se crea turno (RN-TU-01, duro 1)

#### Scenario: Slot ocupado responde 409 con alternativos y sin paciente nuevo

- **DADO** una sesión `recepcion`, un turno activo en el horario pedido y un DNI que no existe
- **CUANDO** se hace `POST /api/turnos` con `origen=recepcion` para ese horario
- **ENTONCES** responde `409` con `detail.codigo="slot_ocupado"` y hasta cinco alternativos del mismo día; no se crea turno ni paciente (RN-TU-03, duro 2)

#### Scenario: Profesional inexistente o inactivo responde 404

- **DADO** una sesión `recepcion` y un `profesional_id` inexistente o con `activo=false`
- **CUANDO** se hace `POST /api/turnos` con `origen=recepcion`
- **ENTONCES** responde `404` sin revelar detalles internos y no se crea turno ni paciente (RN-AG-01)

#### Scenario: Fallo del encolado no bloquea el alta staff

- **DADO** una sesión `recepcion`, un body válido y un fallo simulado del insert de `Notificacion`
- **CUANDO** se hace `POST /api/turnos`
- **ENTONCES** responde `201`; el turno y la auditoría persisten; `notificaciones_encoladas=false` en respuesta y auditoría; no se propaga error de servidor (RN-NO-02, duro 5)

#### Scenario: `origen` ausente o distinto de recepcion responde 400

- **DADO** una sesión `recepcion` y un body staff sin `origen` o con `origen="online"` (casos parametrizados)
- **CUANDO** se hace `POST /api/turnos`
- **ENTONCES** responde `400` con `detail` en `campo="origen"` y no se crea turno (duro 1, US-006 CA-1)

### Requirement: Reprogramación y cambio de duración con anti-solape

The system SHALL expose `PUT /api/turnos/{id}` to reschedule and/or change `duracion_min` of a `reservado`/`confirmado` turno, applying the same anti-overlap rules as online (409 with same-day alternatives), rejecting non-editable states and invalid values, preserving the professional and token, and auditing `reprogramar` with before→after. (US-006 CA-2, RN-TU-02/03, RN-AU-02, duro 2.)

#### Scenario: Reprogramación válida mueve el turno y audita antes→después

- **DADO** un turno `reservado` con `inicio` futuro, una sesión `recepcion` y un nuevo `inicio` libre y alineado a la grilla
- **CUANDO** se hace `PUT /api/turnos/{id}` con ese `inicio`
- **ENTONCES** responde `200`; la fila actualiza `inicio` y `fin` conservando `duracion_min`, `profesional_id`, `estado` y `token_cancelacion`; y `auditoria_turno` registra `accion="reprogramar"` con `detalle.cambios.inicio.antes` y `.despues` (RN-AU-02)

#### Scenario: Cambio de duración recalcula fin y respeta la granularidad

- **DADO** un turno `confirmado` de 30 minutos con una sesión `recepcion` y un profesional con `duracion_default_min=30`
- **CUANDO** se hace `PUT /api/turnos/{id}` con `duracion_min=60` y el bloque contiguo libre
- **ENTONCES** responde `200`; persiste `duracion_min=60` y `fin=inicio+60`; la auditoría registra el cambio de duración (RN-TU-02, RN-AG-02)

#### Scenario: Destino ocupado responde 409 con alternativos y sin efectos

- **DADO** un turno `reservado` y otro turno activo que ocupa el `inicio` destino
- **CUANDO** se hace `PUT /api/turnos/{id}` hacia ese horario
- **ENTONCES** responde `409` con `detail.codigo="slot_ocupado"` y alternativos del mismo día; el turno no cambia; no se encolan notificaciones y no se agrega auditoría (RN-TU-03, duro 2)

#### Scenario: Destino fuera de ventana o no contiguo responde 409 slot_no_disponible

- **DADO** un turno `reservado`, un profesional con ventana de atención configurada y una sesión `recepcion`
- **CUANDO** se hace `PUT /api/turnos/{id}` con un `inicio` fuera de la ventana, en un día no laborable o con un bloque no contiguo (casos parametrizados)
- **ENTONCES** responde `409` con `detail.codigo="slot_no_disponible"`; el turno no cambia; no se encolan notificaciones y no se agrega auditoría (RN-AG-01, RN-TU-05, duro 2)

#### Scenario: Turno cancelado, atendido o ausente no es editable

- **DADO** un turno en `cancelado`, `atendido` o `ausente` (casos parametrizados)
- **CUANDO** se hace `PUT /api/turnos/{id}` con un `inicio` futuro libre
- **ENTONCES** responde `422` con `detail.codigo="turno_no_editable"` y el turno no cambia (RN-TU-07)

#### Scenario: `inicio` pasado o sin zona responde 400

- **DADO** una sesión `recepcion` y un `inicio` anterior al reloj o sin offset (casos parametrizados)
- **CUANDO** se hace `PUT /api/turnos/{id}`
- **ENTONCES** responde `400` con `detail` en `campo="inicio"` y el turno no cambia (duro 1, RN-TU-05)

#### Scenario: `duracion_min` inválida responde 400

- **DADO** un profesional con `duracion_default_min=30` y una sesión `recepcion`
- **CUANDO** se hace `PUT /api/turnos/{id}` con `duracion_min=0`, `-30` o `40` (casos parametrizados)
- **ENTONCES** responde `400` con `detail` en `campo="duracion_min"` y el turno no cambia (RN-TU-02, RN-AG-02)

#### Scenario: Reprogramar a los mismos valores es un 200 no-op

- **DADO** un turno `reservado` y una sesión `recepcion`
- **CUANDO** se hace `PUT /api/turnos/{id}` con el mismo `inicio` y la misma `duracion_min` actuales
- **ENTONCES** responde `200` sin cambios, con `notificaciones_encoladas=false` y sin nueva fila de auditoría

#### Scenario: Dos reprogramaciones concurrentes al mismo slot tienen un solo ganador

- **DADO** dos sesiones staff que reprograman dos turnos distintos hacia el mismo slot libre
- **CUANDO** ambas ejecutan `PUT /api/turnos/{id}` de forma concurrente
- **ENTONCES** una responde `200` y la otra `409` con alternativos (nunca `500`); en la base queda un solo turno activo en ese slot (RN-TU-03, duro 2)

#### Scenario: Campo extra en el body responde 400 por campo

- **DADO** una sesión `recepcion` y un body con `profesional_id` u otra clave no declarada
- **CUANDO** se hace `PUT /api/turnos/{id}`
- **ENTONCES** responde `400` con `detail` en `campo="profesional_id"` y el turno no cambia (duro 1)

### Requirement: Cancelación staff normal y forzada con motivo

The system SHALL expose staff `DELETE /api/turnos/{id}` without query parameters to soft-cancel a `reservado`/`confirmado` turno. At or above `CANCEL_HOURS_MIN` it SHALL audit `cancelar`; below it SHALL require `motivo`, cancel and audit `forzar_cancelacion` with the reason. It SHALL never physically delete, always enqueue `cancelacion`, and keep the public token contract unchanged. (RN-TU-04/07, RN-AU-02, Flujo 3, duro 3/5.)

#### Scenario: Cancelación staff con 3 h o más audita `cancelar`

- **DADO** un turno `reservado` con `inicio` a más de 3 horas del reloj y una sesión `recepcion`
- **CUANDO** se hace `DELETE /api/turnos/{id}` sin parámetros de query
- **ENTONCES** responde `200`; el turno queda `cancelado`; se encola un mail `cancelacion`; `auditoria_turno` registra `accion="cancelar"` con `actor_id` del staff y `estado_nuevo="cancelado"` (RN-TU-04, RN-AU-02)

#### Scenario: Un motivo enviado en la rama normal se guarda en la auditoría

- **DADO** un turno `reservado` con `inicio` a más de 3 horas y una sesión `recepcion`
- **CUANDO** se hace `DELETE /api/turnos/{id}` con `{"motivo": "El paciente avisó por teléfono"}`
- **ENTONCES** responde `200`, la auditoría registra `accion="cancelar"` y `detalle.motivo` con el texto recibido, porque el motivo es opcional fuera del plazo forzado (RN-TU-04, RN-AU-02)

#### Scenario: Exactamente 3 horas se trata como cancelación normal

- **DADO** un reloj fijo y un turno cuyo `inicio` es exactamente `now + CANCEL_HOURS_MIN`
- **CUANDO** se hace `DELETE /api/turnos/{id}` sin `motivo`
- **ENTONCES** responde `200` y la auditoría registra `accion="cancelar"`, porque el borde se evalúa con `>=` (RN-TU-04)

#### Scenario: Cancelación forzada con menos de 3 h y motivo audita `forzar_cancelacion`

- **DADO** un turno `reservado` con `inicio` a 2 horas 59 minutos del reloj y una sesión `recepcion`
- **CUANDO** se hace `DELETE /api/turnos/{id}` con `{"motivo": "El paciente no puede asistir"}`
- **ENTONCES** responde `200`; el turno queda `cancelado`; `auditoria_turno` registra `accion="forzar_cancelacion"`, `actor_id` del staff y `detalle.motivo` no vacío (RN-TU-04, RN-AU-02, Flujo 3)

#### Scenario: Forzar sin motivo responde 422 y no cambia nada

- **DADO** un turno `reservado` con `inicio` a menos de 3 horas y una sesión `recepcion`
- **CUANDO** se hace `DELETE /api/turnos/{id}` con body vacío o sin body
- **ENTONCES** responde `422` con `detail.codigo="motivo_requerido"`; el turno sigue `reservado`; no se encola mail ni se escribe auditoría (RN-TU-04)

#### Scenario: Motivo vacío o demasiado corto responde 400

- **DADO** una sesión `recepcion` y un turno con menos de 3 horas
- **CUANDO** se hace `DELETE /api/turnos/{id}` con `motivo=""`, `"   "` o `"ab"` (casos parametrizados)
- **ENTONCES** responde `400` con `detail` en `campo="motivo"` y el turno no cambia (duro 1)

#### Scenario: Turno ya cancelado responde 422 sin efectos laterales

- **DADO** un turno `cancelado` y una sesión `recepcion`
- **CUANDO** se repite `DELETE /api/turnos/{id}`
- **ENTONCES** responde `422` con `detail.codigo="turno_ya_cancelado"`; no cambia `updated_at`, no se encola otro mail y no se agrega auditoría (RN-TU-07)

#### Scenario: Turno atendido o ausente responde 422

- **DADO** un turno `atendido` o `ausente` (casos parametrizados) y una sesión `recepcion`
- **CUANDO** se hace `DELETE /api/turnos/{id}`
- **ENTONCES** responde `422` con `detail.codigo="turno_no_cancelable"` y el estado no cambia (RN-TU-07)

#### Scenario: La cancelación staff no elimina la fila del turno

- **DADO** una cancelación staff válida que responde `200`
- **CUANDO** se consulta la tabla `turno` por ese `id`
- **ENTONCES** la fila sigue existiendo con `estado=cancelado`; no se ejecutó ningún borrado físico (duro 3)

#### Scenario: El token público sigue funcionando y tiene precedencia

- **DADO** un turno cancelable y una sesión staff; la query trae `?token=<token_válido>`
- **CUANDO** se hace `DELETE /api/turnos/{id}?token=<token_válido>`
- **ENTONCES** se ejecuta el flujo público de C-06 (`200` y auditoría de paciente con `actor_id=NULL`), sin mezclar la sesión staff (PB-01)

#### Scenario: Odontólogo y cliente sin sesión no cancelan como staff

- **DADO** un `DELETE /api/turnos/{id}` sin query params, con una sesión `odontologo` y sin sesión (casos parametrizados)
- **CUANDO** se procesa cada solicitud
- **ENTONCES** el odontólogo recibe `403` y el cliente sin sesión `401`; el turno no cambia (RN-AU-01)

#### Scenario: Campo extra en el body staff responde 400

- **DADO** una sesión `recepcion` y un body con `{"motivo": "válido", "forzar": true}`
- **CUANDO** se hace `DELETE /api/turnos/{id}`
- **ENTONCES** responde `400` con `detail` en `campo="forzar"` y el turno no cambia (duro 1)

### Requirement: Corrección de datos del paciente con auditoría

The system SHALL expose `PUT /api/turnos/{id}/paciente` for `recepcion`/`admin` to correct `dni`, `telefono` and `obra_social` of the turno's `Paciente`, validating non-empty values, rejecting a DNI already used by another patient with 409 and no merge, and auditing `editar_paciente` with before→after. A correction with no effective change SHALL be a 200 no-op without audit. (US-007, RN-PA-02, RN-AU-02, duro 1/3.)

#### Scenario: Corrección de teléfono y obra social audita antes→después

- **DADO** un turno con paciente ficticio y una sesión `recepcion`
- **CUANDO** se hace `PUT /api/turnos/{id}/paciente` con `telefono` y `obra_social` nuevos
- **ENTONCES** responde `200`; la fila `paciente` persiste los valores nuevos; y `auditoria_turno` registra `accion="editar_paciente"` con `detalle.cambios.telefono.antes` y `.despues` (RN-AU-02)

#### Scenario: DNI con formato inválido responde 400

- **DADO** una sesión `recepcion` y un turno existente
- **CUANDO** se hace `PUT /api/turnos/{id}/paciente` con `dni="30ABC001"` o `dni="123"` (casos parametrizados)
- **ENTONCES** responde `400` con `detail` en `campo="dni"` y no se modifica el paciente (RN-TU-01, duro 1)

#### Scenario: DNI ya usado por otro paciente responde 409 sin fusionar

- **DADO** dos pacientes ficticios A y B, y un turno de A
- **CUANDO** se hace `PUT /api/turnos/{id}/paciente` con el DNI de B
- **ENTONCES** responde `409` con `detail.codigo="dni_duplicado"`; A y B siguen existiendo por separado; el turno de A no cambia y no se escribe auditoría (RN-PA-02, duro 3)

#### Scenario: Corregir al mismo DNI actual es un 200 no-op

- **DADO** un turno cuyo paciente ya tiene `dni=30999001`
- **CUANDO** se hace `PUT /api/turnos/{id}/paciente` con `dni="30999001"`
- **ENTONCES** responde `200` sin cambios, sin nueva auditoría y sin tocar `updated_at`

#### Scenario: Campo vacío o solo espacios responde 400

- **DADO** una sesión `recepcion` y un turno existente
- **CUANDO** se hace `PUT /api/turnos/{id}/paciente` con `telefono=""` o `"   "` (casos parametrizados)
- **ENTONCES** responde `400` con `detail` en `campo="telefono"` y no se modifica el paciente (duro 1)

#### Scenario: Body sin campos responde 400

- **DADO** una sesión `recepcion` y un turno existente
- **CUANDO** se hace `PUT /api/turnos/{id}/paciente` con `{}`
- **ENTONCES** responde `400` con `detail` en `campo="body"` y no se modifica el paciente (duro 1)

#### Scenario: `nombre` o `email` fuera del contrato responde 400

- **DADO** una sesión `recepcion` y un turno existente
- **CUANDO** se hace `PUT /api/turnos/{id}/paciente` con `nombre` o `email` (casos parametrizados)
- **ENTONCES** responde `400` con `detail` en ese campo y no se modifica el paciente, porque v1 solo corrige DNI/teléfono/OS (US-007, duro 1)

#### Scenario: Odontólogo no corrige datos del paciente

- **DADO** una sesión `odontologo` y un turno propio
- **CUANDO** se hace `PUT /api/turnos/{id}/paciente` con un teléfono nuevo
- **ENTONCES** responde `403` y el paciente no cambia (RN-AU-01)

#### Scenario: La corrección se refleja en los demás turnos del mismo paciente

- **DADO** un paciente con dos turnos y una corrección de teléfono exitosa desde uno de ellos
- **CUANDO** se consulta el otro turno del mismo `paciente_id`
- **ENTONCES** ambos turnos muestran el teléfono nuevo, porque el dato vive en la fila `Paciente` compartida (KB-04, RN-PA-02)

#### Scenario: Se permite corregir datos de un turno cancelado

- **DADO** un turno `cancelado` con datos de contacto a corregir y una sesión `recepcion`
- **CUANDO** se hace `PUT /api/turnos/{id}/paciente` con un teléfono nuevo
- **ENTONCES** responde `200`, el paciente se actualiza y se escribe auditoría, porque es dato de referencia y no una transición de estado (US-007)

### Requirement: Transiciones de estado RN-TU-07

The system SHALL expose `PATCH /api/turnos/{id}/estado` accepting `confirmado`, `atendido` or `ausente` targets under the closed RN-TU-07 matrix, responding 422 `transicion_invalida` for any other transition and 400 for unknown values, locking the turno and auditing `cambiar_estado`. `cancelado` SHALL only be reached through cancellation. (US-008, RN-TU-07, RN-AU-02.)

#### Scenario: reservado a confirmado responde 200 y audita

- **DADO** un turno `reservado` y una sesión `recepcion`
- **CUANDO** se hace `PATCH /api/turnos/{id}/estado` con `{"estado": "confirmado"}`
- **ENTONCES** responde `200`; el turno queda `confirmado`; y la auditoría registra `accion="cambiar_estado"` con `estado_previo="reservado"` y `estado_nuevo="confirmado"` (RN-TU-07, RN-AU-02)

#### Scenario: confirmado a atendido responde 200

- **DADO** un turno `confirmado` y una sesión `recepcion`
- **CUANDO** se hace `PATCH` con `{"estado": "atendido"}`
- **ENTONCES** responde `200`, el turno queda `atendido` y se audita la transición (RN-TU-07)

#### Scenario: confirmado a ausente responde 200

- **DADO** un turno `confirmado` y una sesión `recepcion`
- **CUANDO** se hace `PATCH` con `{"estado": "ausente"}`
- **ENTONCES** responde `200`, el turno queda `ausente` y se audita la transición (RN-TU-07, US-008 CA-2)

#### Scenario: reservado a atendido o ausente responde 422

- **DADO** un turno `reservado` y una sesión `recepcion`
- **CUANDO** se hace `PATCH` con `{"estado": "atendido"}` o `{"estado": "ausente"}` (casos parametrizados)
- **ENTONCES** responde `422` con `detail.codigo="transicion_invalida"`; el turno sigue `reservado` y no se escribe auditoría (RN-TU-07)

#### Scenario: Cancelar por PATCH estado responde 422

- **DADO** un turno `reservado` o `confirmado` y una sesión `recepcion`
- **CUANDO** se hace `PATCH` con `{"estado": "cancelado"}`
- **ENTONCES** responde `422` con `detail.codigo="transicion_invalida"` y el turno no cambia, porque la cancelación se hace por `DELETE` (RN-TU-07)

#### Scenario: Volver a reservado o repetir confirmado responde 422

- **DADO** un turno `reservado` o `confirmado` (casos parametrizados)
- **CUANDO** se hace `PATCH` con `{"estado": "reservado"}` o con el mismo estado actual
- **ENTONCES** responde `422` con `detail.codigo="transicion_invalida"` y el turno no cambia (RN-TU-07)

#### Scenario: Estados terminales no admiten transiciones

- **DADO** un turno `cancelado`, `atendido` o `ausente` (casos parametrizados)
- **CUANDO** se hace `PATCH` con cualquier target `confirmado`, `atendido` o `ausente`
- **ENTONCES** responde `422` con `detail.codigo="transicion_invalida"` y el estado no cambia (RN-TU-07)

#### Scenario: Estado desconocido responde 400

- **DADO** una sesión `recepcion` y un turno existente
- **CUANDO** se hace `PATCH` con `{"estado": "en_espera"}`
- **ENTONCES** responde `400` con `detail` en `campo="estado"` y el turno no cambia (duro 1)

#### Scenario: Odontólogo marca estado de sus propios turnos

- **DADO** una sesión `odontologo` vinculada al profesional del turno
- **CUANDO** se hace `PATCH` con `{"estado": "confirmado"}` o `{"estado": "atendido"}`
- **ENTONCES** responde `200` y se audita con el actor del odontólogo (RN-AU-01, KB-03)

#### Scenario: Odontólogo no marca estado de turnos ajenos

- **DADO** una sesión `odontologo` vinculada a otro profesional
- **CUANDO** se hace `PATCH` sobre el turno
- **ENTONCES** responde `403` genérico y el estado no cambia (RN-AU-01, staff-auth)

#### Scenario: Odontólogo no marca ausente

- **DADO** una sesión `odontologo` vinculada al profesional del turno y un turno `confirmado`
- **CUANDO** se hace `PATCH` con `{"estado": "ausente"}`
- **ENTONCES** responde `403` y el estado no cambia, porque KB-03 limita al odontólogo a confirmado/atendido (RN-AU-01)

#### Scenario: Dos PATCH concurrentes producen una sola transición

- **DADO** un turno `reservado` y dos sesiones staff que lo confirman de forma concurrente
- **CUANDO** ambas ejecutan `PATCH` con `{"estado": "confirmado"}`
- **ENTONCES** una responde `200` y la otra `422 transicion_invalida`; en la base hay una sola transición y una sola fila de auditoría (RN-TU-07, duro 2)

### Requirement: Ficha del turno con historial auditable

The system SHALL expose `GET /api/turnos/{id}` to staff returning turno, professional and patient data plus the `AuditoriaTurno` history with keyset pagination, explicit columns, no `token_cancelacion`, and 401/403/404 semantics. (US-007 CA-1, RN-AU-02, duro 4/7.)

#### Scenario: Ficha muestra datos e historial ascendente

- **DADO** un turno con paciente y profesional ficticios y dos filas de auditoría
- **CUANDO** una sesión `recepcion` hace `GET /api/turnos/{id}`
- **ENTONCES** responde `200` con `id`, `estado`, `origen`, `inicio`, `fin`, `duracion_min`, datos mínimos del profesional y del paciente, y `auditoria.items` con las dos filas ordenadas por `(created_at, id)` ascendente (US-007 CA-1)

#### Scenario: Historial usa keyset sin OFFSET

- **DADO** un turno con tres filas de auditoría y una sesión `recepcion`
- **CUANDO** se pide `GET /api/turnos/{id}?historial_limit=2` y luego el `next_cursor`
- **ENTONCES** la primera respuesta trae dos items y `next_cursor` no nulo; la segunda trae el item restante y `next_cursor=null`; no se usa `OFFSET` (duro 7)

#### Scenario: Historial con límite fuera de rango responde 400

- **DADO** una sesión `recepcion` y un turno existente
- **CUANDO** se pide `GET /api/turnos/{id}?historial_limit=0` o `historial_limit=101` (casos parametrizados)
- **ENTONCES** responde `400` con `detail` en `campo="historial_limit"` y no se devuelve historial (duro 1)

#### Scenario: La ficha no expone el token de cancelación

- **DADO** un turno con `token_cancelacion` no nulo
- **CUANDO** una sesión `recepcion` hace `GET /api/turnos/{id}`
- **ENTONCES** el cuerpo no contiene `token_cancelacion` ni `cancel_url` (duro 4)

#### Scenario: Odontólogo no ve la ficha de un turno ajeno

- **DADO** una sesión `odontologo` vinculada a otro profesional
- **CUANDO** hace `GET /api/turnos/{id}` sobre el turno ajeno
- **ENTONCES** responde `403` genérico y no aparece ningún dato del turno ni del paciente (RN-AU-01, staff-auth)

#### Scenario: Ficha sin sesión responde 401

- **DADO** un cliente sin cookie de sesión
- **CUANDO** hace `GET /api/turnos/{id}`
- **ENTONCES** responde `401` genérico sin revelar si el turno existe (staff-auth)

#### Scenario: Query desconocida responde 400 por campo

- **DADO** una sesión `recepcion`
- **CUANDO** hace `GET /api/turnos/{id}?orden=asc`
- **ENTONCES** responde `400` con `detail` en `campo="orden"` (duro 1)

#### Scenario: Cursor de historial inválido responde 400

- **DADO** una sesión `recepcion` y `historial_cursor="no-es-un-cursor"`
- **CUANDO** hace `GET /api/turnos/{id}`
- **ENTONCES** responde `400` con `detail` en `campo="historial_cursor"` (duro 1)

#### Scenario: Turno inexistente responde 404

- **DADO** una sesión `recepcion` y un UUID que no existe
- **CUANDO** hace `GET /api/turnos/{id}`
- **ENTONCES** responde `404` sin datos internos (staff-auth)

### Requirement: RBAC staff y separación de credenciales

The system SHALL enforce 401 without a session and 403 for insufficient role on every staff turno endpoint, SHALL NOT accept `token_cancelacion` or DNI/phone as staff credentials, and SHALL keep the public reservation and token cancellation contracts unchanged. (RN-AU-01, RN-TU-06, PB-01, duro 4.)

#### Scenario: Token de paciente no autentica rutas staff

- **DADO** un turno con `token_cancelacion` válido y ninguna cookie de sesión
- **CUANDO** se hace `GET /api/turnos/{id}`, `PUT /api/turnos/{id}` o `PATCH /api/turnos/{id}/estado` con `?token=<token>` (casos parametrizados)
- **ENTONCES** todas responden `401`, porque el token solo habilita la cancelación pública (PB-01, RN-TU-06)

#### Scenario: Cookie inválida o expirada responde 401 y no degrada a público

- **DADO** una cookie de sesión con firma inválida o expirada y un body público válido
- **CUANDO** se hace `POST /api/turnos`
- **ENTONCES** responde `401` genérico y no crea turno como público, porque una credencial inválida nunca se ignora para reencauzar el contrato (staff-auth, D-1)

#### Scenario: Recepción accede a todas las operaciones staff

- **DADO** una sesión `recepcion`
- **CUANDO** ejecuta alta, ficha, reprogramación, corrección de paciente, cambio de estado y cancelación sobre turnos de cualquier profesional
- **ENTONCES** todas las operaciones autorizadas responden con sus códigos de éxito (RN-AU-01, KB-03)

#### Scenario: Odontólogo no accede a escrituras de recepción

- **DADO** una sesión `odontologo` y un turno propio
- **CUANDO** intenta alta, reprogramación, corrección de paciente o cancelación
- **ENTONCES** responde `403` en cada una y no hay efectos (RN-AU-01, KB-03)

#### Scenario: Admin hereda las operaciones de recepción

- **DADO** una sesión `admin`
- **CUANDO** ejecuta cualquier operación staff de turnos
- **ENTONCES** responde con el código de éxito correspondiente (RN-AU-01, KB-03)

#### Scenario: Los contratos públicos no cambian

- **DADO** un cliente sin sesión
- **CUANDO** reserva con `POST /api/turnos` y cancela con `DELETE /api/turnos/{id}?token=` dentro del plazo
- **ENTONCES** responde `201` y `200` respectivamente, con los contratos de reserva-online y cancelacion-paciente intactos (no regresión)

### Requirement: Auditoría append-only en toda mutación staff

The system SHALL write exactly one append-only `AuditoriaTurno` row in the same transaction as every successful staff mutation, recording actor id/role, action, timestamp and before→after detail, and SHALL write none for rejected requests. (RN-AU-02, KB-04, duro 3.)

#### Scenario: Cada mutación staff escribe una fila de auditoría

- **DADO** una sesión `recepcion` y turnos válidos para cada operación
- **CUANDO** se ejecutan alta, reprogramación, cancelación, cancelación forzada, corrección de paciente y cambio de estado (casos parametrizados)
- **ENTONCES** cada operación exitosa agrega exactamente una fila a `auditoria_turno` con `actor_id` del staff, `accion` correspondiente y `created_at` poblado (RN-AU-02)

#### Scenario: Una solicitud rechazada no escribe auditoría

- **DADO** solicitudes que responden `400`, `401`, `403`, `409` o `422` (casos parametrizados)
- **CUANDO** se procesan sobre un turno existente
- **ENTONCES** el conteo de filas de `auditoria_turno` del turno no cambia (RN-AU-02)

#### Scenario: Reprogramación y corrección guardan antes y después

- **DADO** una reprogramación y una corrección de paciente exitosas
- **CUANDO** se lee el `detalle` de sus filas de auditoría
- **ENTONCES** ambas incluyen `cambios` con los valores `antes` y `despues` del campo modificado (RN-AU-02)

#### Scenario: La auditoría identifica actor y rol

- **DADO** una mutación staff exitosa
- **CUANDO** se lee su fila de auditoría
- **ENTONCES** `actor_id` es el staff y `detalle.actor` incluye `tipo="staff"`, `id` y `rol`, además del timestamp de la fila (RN-AU-02)

#### Scenario: La auditoría sigue siendo append-only

- **DADO** una fila de auditoría escrita por C-07
- **CUANDO** la aplicación intenta `UPDATE` o `DELETE` sobre ella
- **ENTONCES** el trigger `auditoria_no_update_delete` rechaza la operación y la fila queda intacta (KB-04, duro 3)

### Requirement: Notificaciones staff no bloqueantes

The system SHALL enqueue staff operation notifications in the existing `notificacion` queue: confirmation + reminders on create, `cancelacion` on cancel, and on reschedule a new confirmation + reminders while discarding stale pending ones as `turno_reprogramado`. Enqueue failures SHALL never block the operation and SHALL be reported as `notificaciones_encoladas=false`. (RN-NO-01/02, duro 5.)

#### Scenario: Alta staff encola confirmación y recordatorios según anticipación

- **DADO** un alta staff con más de 24 horas de anticipación
- **CUANDO** responde `201`
- **ENTONCES** existen tres `Notificacion` pendientes (`confirmacion`, `recordatorio_24h`, `recordatorio_2h`) con el payload de 11 claves y `enviar_en` ISO-8601 UTC (RN-NO-01)

#### Scenario: Cancelación staff encola el mail cancelacion

- **DADO** una cancelación staff válida
- **CUANDO** responde `200`
- **ENTONCES** existe exactamente una `Notificacion` nueva de tipo `cancelacion`, `canal=mail`, `estado=pendiente` e `intentos=0`; no se llama a SMTP (RN-NO-01, C-08)

#### Scenario: Reprogramación descarta lo obsoleto y encola lo nuevo

- **DADO** un turno con recordatorios pendientes y una reprogramación válida
- **CUANDO** responde `200`
- **ENTONCES** las notificaciones pendientes anteriores quedan `fallida` con `error` que empieza con `turno_reprogramado:` e `intentos` sin cambios; existe una `confirmacion` nueva con el `inicio` actualizado y los recordatorios que la nueva anticipación permita; la respuesta informa `notificaciones_encoladas=true` (RN-NO-01/02)

#### Scenario: Fallo del encolado no bloquea la mutación staff

- **DADO** una operación staff válida y un fallo simulado del insert de `Notificacion`
- **CUANDO** se ejecuta
- **ENTONCES** la operación responde con su código de éxito, persiste el cambio y la auditoría, e informa `notificaciones_encoladas=false`; no se propaga error de servidor (RN-NO-02, duro 5)

#### Scenario: C-07 no envía SMTP en la request

- **DADO** cualquier operación staff de turnos
- **CUANDO** se ejecuta sin correr el worker de C-08
- **ENTONCES** no se llama al sender SMTP y las notificaciones quedan `pendiente` para el worker (RN-NO-01, C-08)
