# Spec Delta

## MODIFIED Requirements

### Requirement: Agenda día/semana por profesional (staff + pública)

The system SHALL expose `GET /api/profesionales/{id}/agenda?vista=dia|semana&fecha=` where staff sees occupied/free/blocked franjas with state, minimal patient data, `turno_id` and `duracion_min`, plus a staff-only list of the day's terminal turns as `tipo="cerrado"`. Public callers SHALL see only free franjas, with no patient data and no `turno_id`. Closed entries are additional history and SHALL NOT alter the free-slot computation. `next_cursor` SHALL be the next period date (`fecha + 1d` en día, `fecha + 7d` en semana), not an opaque cursor, and pagination SHALL NOT use OFFSET. The 404 for a nonexistent or inactive professional SHALL apply only to the public branch; staff SHALL receive 200 with the historical agenda. (duro 7, RN-AU-01, KB-03 RBAC.)

#### Scenario: Vista día staff muestra ocupados/libres/bloqueados

- **DADO** un profesional con ventana lunes 09:00–12:00, un turno `reservado` 09:00–09:30 y un bloqueo 10:00–10:30
- **CUANDO** staff llama `GET /api/profesionales/{id}/agenda?vista=dia&fecha=<lunes>` con sesión
- **ENTONCES** responde 200 con franjas tipificadas: `ocupado` (09:00, estado + paciente mínimo), `bloqueado` (10:00, motivo visible staff), `libre` (resto en granularidad del profesional)

#### Scenario: Franjas staff identifican el turno y su duración

- **DADO** un profesional con un turno activo de 45 minutos y franjas libres alrededor
- **CUANDO** staff pide la agenda del día
- **ENTONCES** la franja `ocupado` incluye `turno_id` y `duracion_min=45`, y cada franja `libre` incluye su `duracion_min` en granularidad del profesional

#### Scenario: Turnos terminales del día se listan como cerrados solo a staff

- **DADO** un profesional con turnos `atendido`, `ausente` y `cancelado` en la fecha consultada
- **CUANDO** staff pide la agenda del día
- **ENTONCES** cada uno aparece además como entrada `tipo="cerrado"` con `turno_id`, `inicio`, `fin`, `duracion_min`, `estado` y paciente mínimo, en modo lectura, sin quitar ni modificar las franjas `libre` ya calculadas

#### Scenario: Vista pública solo libres sin datos paciente

- **DADO** la misma agenda del escenario anterior
- **CUANDO** se llama a la agenda sin auth con flag público
- **ENTONCES** responde 200 solo con slots `libre` (sin nombre/DNI/teléfono de pacientes, sin motivo interno de bloqueo, sin `turno_id` y sin entradas `cerrado`)

#### Scenario: Vista semana navega 7 días con keyset (sin OFFSET)

- **DADO** un profesional con ventanas lun–vie
- **CUANDO** staff pide `vista=semana&fecha=<lunes>`
- **ENTONCES** responde 7 días de franjas y `next_cursor` es la fecha del período siguiente (`fecha + 7d`), no un cursor opaco; la navegación usa ese valor de fecha y nunca OFFSET; `fecha` inválida → 400 con detalle por campo (duro 7)

#### Scenario: Profesional inexistente o inactivo en agenda

- **DADO** un `id` inexistente, o un `id` de profesional inactivo consultado sin sesión staff
- **CUANDO** se pide su agenda pública
- **ENTONCES** responde 404 sin revelar datos staff internos; el 404 por inactividad no aplica a staff (RN-AU-01, KB-03 RBAC: el público no accede a agenda de inactivos)

#### Scenario: EDGE — profesional inactivo sigue accesible a staff

- **DADO** un profesional inactivo y una sesión staff válida
- **CUANDO** staff pide su agenda por `id`
- **ENTONCES** responde 200 con la agenda y los turnos históricos, sin tratarlo como 404, porque el 404 por inactividad aplica solo a la rama pública (KB-03 RBAC: staff lee todos los turnos; agenda-disponibilidad §Agenda día/semana por profesional)

#### Scenario: EDGE — un turno cerrado no ocupa el horario ni duplica franjas

- **DADO** un turno `cancelado` que cubría un bloque de la ventana
- **CUANDO** staff pide la agenda del día
- **ENTONCES** el bloque sigue siendo ofrecible como `libre` y el turno aparece solo en la lista `cerrado`, sin solaparse con las franjas `ocupado` ni consumir disponibilidad
