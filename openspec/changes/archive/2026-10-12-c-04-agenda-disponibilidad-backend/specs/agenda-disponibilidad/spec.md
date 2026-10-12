# Spec Delta — agenda-disponibilidad

## Purpose

Expone la agenda computable del consultorio (profesionales, ventanas, bloqueos y slots libres) para que pacientes reserven online y recepción mantenga horarios reales con trazabilidad de actualización.

## ADDED Requirements

### Requirement: Listado público de profesionales activos

The system SHALL expose `GET /api/profesionales` publicly without auth, returning only `activo=true` professionals with explicit columns `id, nombre, especialidad, matricula, duracion_default_min, ultima_actualizacion`, ordered by keyset on `id`.

#### Scenario: Lista pública solo activos sin datos staff

- **DADO** 2 profesionales activos y 1 inactivo (`activo=false`)
- **CUANDO** se llama `GET /api/profesionales` sin auth
- **ENTONCES** responde 200 con los 2 activos (columnas explícitas, sin email/hash/rol staff) y keyset `next_cursor`; el inactivo no aparece

#### Scenario: Profesional inactivo dado de baja no lista pero conserva historial

- **DADO** un profesional con turnos históricos dado de baja (`activo=false`)
- **CUANDO** se lista `GET /api/profesionales` y se consulta su agenda histórica por staff
- **ENTONCES** el listado lo excluye pero sus turnos históricos siguen legibles (baja lógica, sin hard-delete)

### Requirement: Agenda día/semana por profesional (staff + pública)

The system SHALL expose `GET /api/profesionales/{id}/agenda?vista=dia|semana&fecha=` where staff sees occupied/free/blocked slots with state and minimal patient data, and public callers see only free slots with no patient data.

#### Scenario: Vista día staff muestra ocupados/libres/bloqueados

- **DADO** un profesional con ventana lunes 09:00–12:00, un turno `reservado` 09:00–09:30 y un bloqueo 10:00–10:30
- **CUANDO** staff llama `GET /api/profesionales/{id}/agenda?vista=dia&fecha=<lunes>` con sesión
- **ENTONCES** responde 200 con franjas tipificadas: `ocupado` (09:00, estado + paciente mínimo), `bloqueado` (10:00, motivo visible staff), `libre` (resto en granularidad del profesional)

#### Scenario: Vista pública solo libres sin datos paciente

- **DADO** la misma agenda del escenario anterior
- **CUANDO** se llama a la agenda sin auth con flag público
- **ENTONCES** responde 200 solo con slots `libre` (sin nombre/DNI/teléfono de pacientes, sin motivo interno de bloqueo)

#### Scenario: Vista semana navega 7 días con keyset (sin OFFSET)

- **DADO** un profesional con ventanas lun–vie
- **CUANDO** staff pide `vista=semana&fecha=<lunes>`
- **ENTONCES** responde 7 días de franjas paginadas por keyset (`fecha` cursor, nunca OFFSET) y `fecha` inválida → 400 con detalle por campo

#### Scenario: Profesional inexistente o inactivo en agenda

- **DADO** un `id` inexistente o de profesional inactivo
- **CUANDO** se pide su agenda pública
- **ENTONCES** responde 404 sin revelar datos staff internos

### Requirement: Cómputo público de disponibilidad (ventanas − bloqueos − ocupados)

The system SHALL expose `GET /api/disponibilidad?profesional_id=&desde=&hasta=` publicly computing slots as `Disponibilidad windows − Bloqueos − active Turnos (reservado, confirmado)` with granularity `duracion_default_min` of the professional and half-open `[)` boundary semantics.

#### Scenario: Cómputo feliz resta bloqueos y ocupados

- **DADO** profesional con `duracion_default_min=30`, ventana 09:00–11:00 un día, bloqueo 09:30–10:00 y turno `reservado` 10:00–10:30
- **CUANDO** se llama `GET /api/disponibilidad?profesional_id=&desde=<09:00>&hasta=<11:00>`
- **ENTONCES** responde 200 con slots `[09:00, 10:30, 10:30]` libres (09:30 y 10:00 excluidos), cada slot `{inicio, fin, duracion_min=30}` en TZ `America/Argentina/Buenos_Aires` persistida UTC

#### Scenario: Granularidad 45 minutos por profesional

- **DADO** profesional con `duracion_default_min=45` y ventana 09:00–12:00 sin bloqueos ni turnos
- **CUANDO** se pide disponibilidad de ese día
- **ENTONCES** responde slots de 45' (`09:00, 09:45, 10:30, 11:15`) y ningún slot de 30'

#### Scenario: Sin ventana no hay slots

- **DADO** un profesional sin `Disponibilidad` vigente el día pedido (o fuera de `vigente_desde/hasta`)
- **CUANDO** se pide disponibilidad
- **ENTONCES** responde 200 con lista vacía (no error, no horarios inventados)

#### Scenario: EDGE — slot exactamente en el borde de la ventana es ofrecido

- **DADO** ventana 09:00–10:00 con granularidad 30' sin ocupados
- **CUANDO** se computa disponibilidad
- **ENTONCES** se ofrecen `[09:00, 09:30]` y el slot que termina exactamente en `10:00` se incluye; ningún slot excede `hora_hasta` (`[)` half-open, simétrico a C-02 turno-lifecycle)

#### Scenario: Turnos cancelado/atendido/ausente liberan el slot

- **DADO** ventana 09:00–10:00 con turnos `cancelado` 09:00–09:30 y `atendido` 09:30–10:00 (sin activos)
- **CUANDO** se pide disponibilidad
- **ENTONCES** ambos slots se ofrecen libres (solo `reservado`/`confirmado` ocupan, coherente con el predicado EXCLUDE C-02)

#### Scenario: Parámetros inválidos o rango excesivo

- **DADO** cualquier profesional
- **CUANDO** se pide sin `profesional_id`, con `desde > hasta`, o rango mayor a 31 días
- **ENTONCES** responde 400 con detalle por campo (`extra='forbid'`; campos desconocidos también 400)

### Requirement: CRUD staff de disponibilidades con validación sin solape (app-level bloqueado)

The system SHALL expose staff-only `CRUD /api/disponibilidades` (fields `profesional_id, dia_semana 0–6, hora_desde < hora_hasta, vigente_desde/hasta`) rejecting overlaps for the same professional+day at the application level inside a short transaction with `SELECT FOR UPDATE`, returning 409 on overlap (LOCKED decision: NO temporal EXCLUDE — see design §3).

#### Scenario: Crear ventana válida actualiza ultima_actualizacion

- **DADO** staff recepción con sesión y un profesional sin ventana el martes
- **CUANDO** `POST /api/disponibilidades {profesional_id, dia_semana=1, hora_desde=09:00, hora_hasta=12:00}` válido
- **ENTONCES** responde 201, la ventana persiste y `profesional.ultima_actualizacion` avanza al `now()` del write (visible para UI)

#### Scenario: BUSINESS-ERROR — ventana solapada mismo profesional+día es rechazada 409

- **DADO** ventana existente martes 09:00–12:00 del profesional P
- **CUANDO** staff intenta `POST /api/disponibilidades {P, martes, 11:00–13:00}` (solapa 11:00–12:00)
- **ENTONCES** responde 409 con detalle del conflicto (rango existente) y no persiste; C-05 puede reintentar tras corrección

#### Scenario: EDGE — ventana adyacente en el borde es permitida

- **DADO** ventana martes 09:00–12:00 de P
- **CUANDO** staff crea martes 12:00–14:00 de P (empieza exactamente donde termina la otra)
- **ENTONCES** responde 201 (borde `[)` no es solape, simétrico a turnos)

#### Scenario: Mismo horario distinto profesional o distinto día es permitido

- **DADO** ventana martes 09:00–12:00 de P1
- **CUANDO** staff crea martes 09:00–12:00 de P2, o lunes 09:00–12:00 de P1
- **ENTONCES** ambas persisten (la validación compara `profesional_id + dia_semana` + solape de `[hora_desde, hora_hasta)` + intersección de vigencia)

#### Scenario: Sin auth o rol odontólogo ajeno es rechazado

- **DADO** endpoint `POST /api/disponibilidades`
- **CUANDO** se llama sin sesión, o con odontólogo cuyo `profesional_id` ≠ objetivo
- **ENTONCES** responde 401 sin token / 403 genérico (interfaz `require_role` de C-03, consumida no implementada); odontólogo solo lectura de la propia agenda

#### Scenario: Schema permisivo o día inválido es 400 por campo

- **DADO** staff autenticado
- **CUANDO** `POST /api/disponibilidades` con campo extra desconocido, `dia_semana=9`, o `hora_desde >= hora_hasta`
- **ENTONCES** responde 400 con detalle por campo (`extra='forbid'`; hard rule 1)

### Requirement: Bloqueos staff con motivo y creado_por

The system SHALL expose staff-only `POST /api/bloqueos` requiring `{profesional_id, desde < hasta (timestamptz), motivo non-empty}` and recording `creado_por` from the staff session; affected slots immediately stop being offered.

#### Scenario: Crear bloqueo oculta los slots afectados

- **DADO** ventana lunes 09:00–12:00 con slots libres y staff recepción con sesión
- **CUANDO** `POST /api/bloqueos {profesional_id, desde=<lun 10:00>, hasta=<lun 11:00>, motivo="feriado"}` (creado_por = staff de la sesión)
- **ENTONCES** responde 201, `profesional.ultima_actualizacion` avanza, y la disponibilidad posterior ya no ofrece 10:00–11:00

#### Scenario: Bloqueo sin motivo o rango inválido es 400 por campo

- **DADO** staff autenticado
- **CUANDO** `POST /api/bloqueos` con `motivo` vacío, `desde >= hasta`, o campo extra
- **ENTONCES** responde 400 con detalle por campo y no persiste

### Requirement: ultima_actualizacion por profesional (mitiga SU-01)

The system SHALL maintain `profesional.ultima_actualizacion TIMESTAMPTZ NULL` updated on every write to `disponibilidad`/`bloqueo` of that professional, exposed in `GET /api/profesionales` and agenda responses; `NULL` means "sin datos cargados".

#### Scenario: UI ve freshness tras cada cambio

- **DADO** profesional con `ultima_actualizacion=T0`
- **CUANDO** staff crea/edita/elimina una ventana o crea un bloqueo de ese profesional
- **ENTONCES** `ultima_actualizacion > T0` en la siguiente lectura (trigger DB o write transaccional — decisión en design)

#### Scenario: Profesional sin ventanas muestra sin-datos

- **DADO** profesional recién creado sin disponibilidades ni bloqueos
- **CUANDO** se lee `GET /api/profesionales`
- **ENTONCES** `ultima_actualizacion=null` y la UI lo interpreta como "sin datos" (no como error)

### Requirement: Rate-limit público 30 req/min/IP

The system SHALL rate-limit public `GET /api/disponibilidad` (y `GET /api/profesionales*` público) to 30 requests/minute per client IP, returning 429 with `Retry-After` when exceeded, without affecting staff-authenticated calls differently than documented.

#### Scenario: Tráfico normal dentro del límite pasa

- **DADO** IP nueva sin historial
- **CUANDO** realiza 30 `GET /api/disponibilidad` dentro de 60s (reloj fake en test)
- **ENTONCES** las 30 responden 200

#### Scenario: Request 31 en la ventana es rechazada 429

- **DADO** IP que ya consumió 30 requests en 60s
- **CUANDO** realiza la request 31 en la misma ventana
- **ENTONCES** responde 429 con header `Retry-After` y no computa slots; la ventana se resetea tras 60s (reloj fake, sin sleeps en tests)
