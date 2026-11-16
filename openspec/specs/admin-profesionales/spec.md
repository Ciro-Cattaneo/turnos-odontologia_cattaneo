# admin-profesionales Specification

## Purpose

Define el ciclo de vida administrativo del profesional del consultorio (alta, edición, `duracion_default_min`, baja lógica que conserva historial y reactivación), para que un admin opere la agenda sin soporte técnico y sin perder trazabilidad de los turnos ya reservados.

## Requirements

### Requirement: Alta de profesional con duración configurable

The system SHALL expose admin-only `POST /api/profesionales` to create an active professional from `nombre`, optional `matricula`/`especialidad` and `duracion_default_min` (default 30, integer 5–240 in steps of 5), returning 201 with the persisted resource. (US-010 CA-1, RN-TU-02, duro 1.)

#### Scenario: FELIZ — Alta válida crea el profesional activo con duración default

- **DADO** una sesión `admin` y un body con `nombre="Dra. Ficticia Uno"` sin `duracion_default_min`
- **CUANDO** se hace `POST /api/profesionales`
- **ENTONCES** responde `201`; la fila `profesional` persiste con `activo=true` y `duracion_default_min=30`; la respuesta devuelve `id`, `nombre`, `matricula`, `especialidad`, `duracion_default_min`, `activo` y `ultima_actualizacion`, y no incluye turnos (US-010 CA-1)

#### Scenario: FELIZ — Alta con duración configurable persiste el valor pedido

- **DADO** una sesión `admin` y un body con `nombre`, `matricula`, `especialidad` y `duracion_default_min=45`
- **CUANDO** se hace `POST /api/profesionales`
- **ENTONCES** responde `201` y la fila persiste `duracion_default_min=45`, `matricula` y `especialidad` con los valores enviados (US-010 CA-1, RN-AG-02)

#### Scenario: ERROR — Duración fuera de rango o fuera de la grilla responde 400

- **DADO** una sesión `admin`
- **CUANDO** se hace `POST /api/profesionales` con `duracion_default_min` en `0`, `-30`, `32`, `250` o `"treinta"` (casos parametrizados)
- **ENTONCES** responde `400` con `detail` en `campo="duracion_default_min"` y no se crea ningún profesional (RN-TU-02, RN-AG-02, duro 1)

#### Scenario: ERROR — Nombre vacío o campo extra responde 400 por campo

- **DADO** una sesión `admin`
- **CUANDO** se hace `POST /api/profesionales` con `nombre` vacío/solo espacios, o con una clave no declarada como `email` (casos parametrizados)
- **ENTONCES** responde `400` con `detail` en `campo="nombre"` o `campo="email"` respectivamente y no se crea ningún profesional (duro 1)

#### Scenario: BORDE — Duración en los extremos 5 y 240 responde 201

- **DADO** una sesión `admin`
- **CUANDO** se hace `POST /api/profesionales` con `duracion_default_min=5` y luego con `duracion_default_min=240` (casos parametrizados)
- **ENTONCES** ambos responden `201` y persisten el valor exacto, porque 5 y 240 son los bordes inclusivos de la convención de duración (RN-AG-02, D-16)

#### Scenario: BORDE — Matrícula y especialidad son opcionales

- **DADO** una sesión `admin` y un body con solo `nombre`
- **CUANDO** se hace `POST /api/profesionales`
- **ENTONCES** responde `201` con `matricula=null` y `especialidad=null`, porque KB-04 las declara nullable (KB-04)

### Requirement: Edición de profesional sin reescribir turnos existentes

The system SHALL expose admin-only `PUT /api/profesionales/{id}` to edit `nombre`, `matricula`, `especialidad`, `duracion_default_min` and `activo`, returning 200 with the updated resource; invalid or empty bodies SHALL return 400 per field and unknown ids 404. Editing SHALL NOT rewrite existing turnos, and `{"activo": false}` SHALL have the same soft-delete semantics as `DELETE` (see Baja lógica). (US-010, RN-TU-02, duro 1.)

#### Scenario: FELIZ — Cambiar la duración default no altera los turnos ya reservados

- **DADO** un profesional con `duracion_default_min=30` y un turno futuro con `duracion_min=30` y una sesión `admin`
- **CUANDO** se hace `PUT /api/profesionales/{id}` con `duracion_default_min=45`
- **ENTONCES** responde `200` y la fila `profesional` persiste `45`; el turno existente conserva `duracion_min=30`, su `inicio` y su `fin` (RN-TU-02, RN-AG-02)

#### Scenario: FELIZ — Edición de datos del profesional responde 200

- **DADO** un profesional activo y una sesión `admin`
- **CUANDO** se hace `PUT /api/profesionales/{id}` con `nombre`, `matricula` y `especialidad` nuevos
- **ENTONCES** responde `200` con los valores nuevos y la fila queda actualizada (US-010)

#### Scenario: ERROR — Body vacío o con campo extra responde 400

- **DADO** una sesión `admin` y un profesional existente
- **CUANDO** se hace `PUT /api/profesionales/{id}` con `{}` o con una clave como `turnos` (casos parametrizados)
- **ENTONCES** responde `400` con `detail` en `campo="body"` o en la clave rechazada, y el profesional no cambia (duro 1)

#### Scenario: BORDE — Editar a los mismos valores es un 200 sin efectos

- **DADO** un profesional y una sesión `admin`
- **CUANDO** se hace `PUT /api/profesionales/{id}` con los mismos `nombre` y `duracion_default_min` actuales
- **ENTONCES** responde `200` sin cambios en la fila y sin tocar `ultima_actualizacion`, porque la frescura de disponibilidad la mantiene el trigger de C-04 (RN-TU-05)

#### Scenario: ERROR — Profesional inexistente responde 404

- **DADO** una sesión `admin` y un UUID que no corresponde a ningún profesional
- **CUANDO** se hace `PUT /api/profesionales/{id}`, `DELETE /api/profesionales/{id}` o `PUT` con `{"activo": true}` sobre ese id (casos parametrizados)
- **ENTONCES** responde `404` sin datos internos (staff-auth)

### Requirement: Baja lógica de profesional que conserva historial, siempre sin guarda de turnos futuros

The system SHALL expose admin-only `DELETE /api/profesionales/{id}` as a logical deactivation (`activo=false`) that keeps the row, its turnos, disponibilidades and bloqueos. Deactivation SHALL always return 200, SHALL NOT be blocked by future `reservado`/`confirmado` turnos, and those turnos SHALL remain intact and manageable by staff. `PUT` with `{"activo": false}` SHALL be equivalent. (US-010 CA-2, duro 3, PB-08.)

#### Scenario: FELIZ — Baja deja activo=false y conserva la fila y sus turnos históricos

- **DADO** un profesional activo con turnos `atendido`, `ausente` y `cancelado` en el pasado y una sesión `admin`
- **CUANDO** se hace `DELETE /api/profesionales/{id}`
- **ENTONCES** responde `200` con `activo=false`; la fila `profesional` sigue existiendo con el mismo `id`; y sus turnos históricos conservan estado, `inicio` y `duracion_min` (US-010 CA-2, duro 3)

#### Scenario: FELIZ — Baja con turnos futuros activos responde 200 y no toca los turnos

- **DADO** un profesional con un turno `reservado` o `confirmado` con `inicio` futuro y una sesión `admin`
- **CUANDO** se hace `DELETE /api/profesionales/{id}` (casos parametrizados por estado)
- **ENTONCES** responde `200` con `activo=false`; el turno futuro conserva `estado`, `inicio` y `duracion_min`; no se encola ni se cancela ninguna notificación; y la baja no responde `409` ni expone un código de "turnos futuros" (US-010 CA-2, duro 3)

#### Scenario: FELIZ — Los turnos futuros siguen gestionables por staff tras la baja

- **DADO** un profesional dado de baja con un turno futuro `reservado` y una sesión staff válida
- **CUANDO** staff consulta `GET /api/profesionales/{id}/agenda?vista=dia&fecha=<día del turno>` y luego cancela el turno por `DELETE /api/turnos/{id}`
- **ENTONCES** la agenda responde `200` mostrando el turno con su estado y `duracion_min`, y la cancelación responde `200`, porque los turnos futuros no quedan huérfanos de operación (agenda-disponibilidad, recepción-turnos)

#### Scenario: FELIZ — El profesional dado de baja sale del catálogo público y del alta de reservas

- **DADO** un profesional que acaba de quedar `activo=false` con un turno futuro intacto
- **CUANDO** se consulta `GET /api/profesionales` sin sesión y se intenta reservar un turno nuevo con ese `profesional_id`
- **ENTONCES** el profesional no aparece en el catálogo público y el alta de reserva lo rechaza según el contrato existente de C-05, sin afectar el turno futuro ya existente (agenda-disponibilidad, US-010 CA-2)

#### Scenario: BORDE — PUT con activo=false tiene la misma semántica que DELETE

- **DADO** un profesional con turnos futuros `reservado`/`confirmado` y una sesión `admin`
- **CUANDO** se hace `PUT /api/profesionales/{id}` con `{"activo": false}`
- **ENTONCES** responde `200` con `activo=false`, conserva turnos, disponibilidades y bloqueos, y se comporta igual que `DELETE` (idempotente, sin `409`, sin borrado físico) (US-010 CA-2, duro 3)

#### Scenario: BORDE — Repetir la baja es idempotente

- **DADO** un profesional con `activo=false` y una sesión `admin`
- **CUANDO** se repite `DELETE /api/profesionales/{id}` o `PUT` con `{"activo": false}`
- **ENTONCES** responde `200` con `activo=false` y no se modifica ningún turno ni disponibilidad (duro 3)

#### Scenario: BORDE — La baja nunca ejecuta un borrado físico

- **DADO** una baja válida que responde `200`
- **CUANDO** se consultan las tablas `profesional`, `turno`, `disponibilidad` y `bloqueo` por ese `profesional_id`
- **ENTONCES** todas las filas siguen existiendo; solo cambió `profesional.activo` a `false` (duro 3)

#### Scenario: ERROR — Una variante de baja física responde 400 por campo

- **DADO** una sesión `admin` y un profesional existente
- **CUANDO** se hace `DELETE /api/profesionales/{id}?fisico=true`
- **ENTONCES** responde `400` con `detail` en `campo="fisico"` y no se borra ninguna fila, porque el borrado físico no existe en v1 (duro 1, duro 3)

### Requirement: Listado admin con inactivos y reactivación

The system SHALL let an admin list inactive professionals with `GET /api/profesionales?incluir_inactivos=true` and reactivate one with `PUT /api/profesionales/{id}` with `{"activo": true}`. Without the flag the public catalogue SHALL keep its current contract: only active professionals, the same explicit columns (no `activo`) and no session resolution. (US-010, no regresión de agenda-disponibilidad.)

#### Scenario: FELIZ — Listado admin con inactivos incluye a los dados de baja

- **DADO** un profesional activo, otro con `activo=false` y una sesión `admin`
- **CUANDO** se hace `GET /api/profesionales?incluir_inactivos=true`
- **ENTONCES** responde `200` con ambos profesionales en `items` y cada fila informa `activo` (US-010)

#### Scenario: FELIZ — El catálogo público sigue mostrando solo activos

- **DADO** un profesional activo y otro inactivo
- **CUANDO** se hace `GET /api/profesionales` sin sesión o sin el flag
- **ENTONCES** responde `200` solo con el activo, preservando el contrato público de agenda-disponibilidad (no regresión)

#### Scenario: ERROR — Un incluir_inactivos no booleano responde 400 por campo

- **DADO** una sesión `admin`
- **CUANDO** se hace `GET /api/profesionales?incluir_inactivos=maybe`
- **ENTONCES** responde `400` con `detail` en `campo="incluir_inactivos"`, antes de resolver sesión o consultar la base (duro 1)

#### Scenario: BORDE — El listado público con cookie inválida o vencida sigue respondiendo 200

- **DADO** un cliente sin sesión válida (sin cookie, con cookie vencida y con cookie corrupta, casos parametrizados) y un profesional activo
- **CUANDO** se hace `GET /api/profesionales` sin `incluir_inactivos`
- **ENTONCES** responde `200` con el activo, porque la rama pública no resuelve sesión y una cookie inválida no puede convertir el 200 en `401` (no regresión)

#### Scenario: BORDE — El listado público conserva sus columnas explícitas y no expone activo

- **DADO** un profesional activo
- **CUANDO** se hace `GET /api/profesionales` sin el flag
- **ENTONCES** cada fila trae exactamente `id`, `nombre`, `especialidad`, `matricula`, `duracion_default_min` y `ultima_actualizacion`, sin `activo` ni otros campos staff (agenda-disponibilidad, no regresión)

#### Scenario: ERROR — La rama admin sin rol admin responde 403

- **DADO** una sesión válida de `recepcion` o de `odontologo` (casos parametrizados)
- **CUANDO** se hace `GET /api/profesionales?incluir_inactivos=true`
- **ENTONCES** responde `403` genérico y no devuelve ningún profesional inactivo (RN-AU-01, KB-03)

#### Scenario: FELIZ — Reactivar devuelve al profesional al catálogo público

- **DADO** un profesional con `activo=false` y una sesión `admin`
- **CUANDO** se hace `PUT /api/profesionales/{id}` con `{"activo": true}`
- **ENTONCES** responde `200` con `activo=true` y el profesional vuelve a aparecer en `GET /api/profesionales` público (US-010)

#### Scenario: BORDE — Reactivar un profesional ya activo es un 200 sin efectos

- **DADO** un profesional con `activo=true` y una sesión `admin`
- **CUANDO** se hace `PUT /api/profesionales/{id}` con `{"activo": true}`
- **ENTONCES** responde `200` y la fila no cambia (duro 3)

### Requirement: Acceso admin exclusivo a la gestión de profesionales

The system SHALL require an `admin` session for every professional write and for `incluir_inactivos=true`, answering 401 without session and 403 for `recepcion`/`odontologo`, without revealing data. (RN-AU-01, KB-03.)

#### Scenario: ERROR — Recepción y odontólogo no administran profesionales

- **DADO** una sesión `recepcion` y una sesión `odontologo` (casos parametrizados)
- **CUANDO** cada una intenta `POST`, `PUT` y `DELETE` sobre `/api/profesionales`, o `GET ?incluir_inactivos=true`
- **ENTONCES** todas responden `403` genérico y ningún profesional cambia (RN-AU-01, KB-03)

#### Scenario: ERROR — Sin sesión no hay escritura de profesionales

- **DADO** un cliente sin cookie de sesión
- **CUANDO** intenta `POST`, `PUT` o `DELETE` sobre `/api/profesionales`, o pide `?incluir_inactivos=true`
- **ENTONCES** responde `401` genérico y no se crea ni modifica ningún profesional (staff-auth)

#### Scenario: FELIZ — El listado público no cambia de contrato

- **DADO** un cliente sin sesión
- **CUANDO** hace `GET /api/profesionales` con `limit` y `cursor` válidos
- **ENTONCES** responde `200` con `items` de activos y `next_cursor` que permite pedir la página siguiente, exactamente como en agenda-disponibilidad (no regresión)
