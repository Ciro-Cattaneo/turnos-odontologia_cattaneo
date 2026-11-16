# Spec Delta — reportes-ocupacion

## Purpose

Define el reporte mínimo de ocupación y ausentismo por profesional y período, en formato tabla, para que recepción y admin detecten huecos de agenda y el odontólogo vea solo su propia actividad.

## ADDED Requirements

### Requirement: Reporte tabular de ocupación por profesional y período

The system SHALL expose `GET /api/reportes/ocupacion` to staff with `desde` and `hasta` (inclusive local dates) and optional `profesional_id`, returning one row per professional plus a `totales` row, with explicit counters and no pagination or export. A row without turnos SHALL report every counter in zero and resolve `porcentaje_ocupacion` by the capacity rule (`null` when capacity is zero). (US-011 CA-1/CA-2, PB-06.)

#### Scenario: FELIZ — Reporte con datos mixtos devuelve una fila por profesional

- **DADO** dos profesionales ficticios activos, uno con turnos en el rango en estados `reservado`, `confirmado`, `atendido`, `ausente` y `cancelado`, y otro sin turnos; una sesión `recepcion`
- **CUANDO** se hace `GET /api/reportes/ocupacion?desde=2026-11-02&hasta=2026-11-08`
- **ENTONCES** responde `200` con `desde`, `hasta`, `zona="America/Argentina/Buenos_Aires"` e `items` con una fila por profesional que incluye `profesional` (`id`, `nombre`, `activo`), `turnos`, `atendidos`, `ausentes`, `cancelados`, `pendientes`, `minutos_ocupados`, `minutos_disponibles` y `porcentaje_ocupacion` (US-011 CA-1/CA-2)

#### Scenario: FELIZ — El filtro por profesional acota el reporte a esa fila

- **DADO** dos profesionales con turnos en el rango y una sesión `admin`
- **CUANDO** se hace `GET /api/reportes/ocupacion?desde=...&hasta=...&profesional_id=<P1>`
- **ENTONCES** responde `200` con `items` de una sola fila correspondiente a `P1` (US-011 CA-2)

#### Scenario: BORDE — Un profesional_id inexistente devuelve una tabla vacía sin error

- **DADO** una sesión `admin` y un UUID que no corresponde a ningún profesional
- **CUANDO** se hace `GET /api/reportes/ocupacion?desde=...&hasta=...&profesional_id=<inexistente>`
- **ENTONCES** responde `200` con `items=[]` y `totales` en cero, porque es un filtro y no una lectura de recurso (US-011)

#### Scenario: BORDE — Profesional activo sin turnos aparece con contadores en cero

- **DADO** un profesional activo sin turnos en el rango y con capacidad ofrecible mayor a cero, y una sesión `recepcion`
- **CUANDO** se pide el reporte del rango
- **ENTONCES** su fila aparece con `turnos=0`, `atendidos=0`, `ausentes=0`, `cancelados=0`, `pendientes=0`, `minutos_ocupados=0` y `porcentaje_ocupacion=0.0`, porque el objetivo es detectar huecos (US-011)

#### Scenario: BORDE — Un profesional_id filtrado sin turnos y sin capacidad informa porcentaje nulo

- **DADO** un profesional sin turnos en el rango, sin disponibilidad vigente y una sesión `admin`
- **CUANDO** se pide el reporte con `profesional_id=<P1>`
- **ENTONCES** `items` trae exactamente la fila de `P1` con todos los contadores en `0`, `minutos_disponibles=0` y `porcentaje_ocupacion=null`, porque la fila se incluye siempre y la división por cero se evita con `null` (US-011, D-9)

#### Scenario: FELIZ — Un profesional inactivo con turnos históricos sigue apareciendo

- **DADO** un profesional con `activo=false` y turnos dentro del rango, y una sesión `admin`
- **CUANDO** se pide el reporte del rango
- **ENTONCES** su fila aparece con `profesional.activo=false` y los conteos de sus turnos, para no perder historial (US-010 CA-2, US-011)

#### Scenario: FELIZ — Los totales cuadran con la suma de las filas

- **DADO** un reporte con dos o más filas de profesionales
- **CUANDO** se compara `totales` con la suma de `items`
- **ENTONCES** cada contador y `minutos_ocupados`/`minutos_disponibles` de `totales` es igual a la suma de las filas, y `porcentaje_ocupacion` de `totales` se recalcula sobre esos totales (US-011)

#### Scenario: ERROR — Un profesional_id malformado responde 400 por campo

- **DADO** una sesión `admin`
- **CUANDO** se hace `GET /api/reportes/ocupacion?desde=...&hasta=...&profesional_id="no-es-uuid"`
- **ENTONCES** responde `400` con `detail` en `campo="profesional_id"` y no se ejecuta la consulta (duro 1)

### Requirement: Métricas y porcentaje de ocupación

The system SHALL define `turnos` as all turnos whose `inicio` falls in range, `pendientes` as what remains after `atendidos`+`ausentes`+`cancelados`, and `porcentaje_ocupacion` as occupied minutes over capacity minutes, `null` when capacity is zero. Capacity SHALL be computed with the configuration in force at query time (current `duracion_default_min` and current disponibilidad/bloqueos). (US-011 CA-1, RN-TU-07.)

#### Scenario: FELIZ — Los contadores por estado cuadran con los turnos del rango

- **DADO** un profesional con, en un mismo día, un turno `atendido` de 30, uno `ausente` de 30, uno `cancelado` de 30 y uno `confirmado` de 30
- **CUANDO** se pide el reporte de ese día
- **ENTONCES** la fila informa `turnos=4`, `atendidos=1`, `ausentes=1`, `cancelados=1`, `pendientes=1` y `turnos = atendidos + ausentes + cancelados + pendientes` (US-011 CA-1, RN-TU-07)

#### Scenario: FELIZ — El porcentaje de ocupación usa minutos ocupados sobre capacidad ofrecible

- **DADO** un profesional con una ventana local de 09:00 a 12:00, sin bloqueos, `duracion_default_min=30`, y en ese día los cuatro turnos del caso anterior (todos de 30)
- **CUANDO** se pide el reporte de ese día
- **ENTONCES** informa `minutos_disponibles=180`, `minutos_ocupados=90` y `porcentaje_ocupacion=50.0`, porque los `cancelado` liberan capacidad y los `reservado`/`confirmado`/`atendido`/`ausente` la ocupan (US-011 CA-1)

#### Scenario: BORDE — Los bloqueos y la vigencia de la ventana reducen la capacidad

- **DADO** un profesional con ventana 09:00–12:00, un bloqueo 10:00–11:00, `duracion_default_min=30` y una ventana con `vigente_desde` posterior a un día del rango
- **CUANDO** se pide el reporte
- **ENTONCES** `minutos_disponibles` refleja solo los slots realmente ofrecibles (120 minutos en el día bloqueado) y no cuenta los días previos a `vigente_desde` (RN-AG-01, RN-TU-05)

#### Scenario: BORDE — Sin capacidad en el rango el porcentaje es nulo

- **DADO** un profesional activo sin ninguna `disponibilidad` vigente en el rango y una sesión `recepcion`
- **CUANDO** se pide el reporte
- **ENTONCES** su fila informa `minutos_disponibles=0` y `porcentaje_ocupacion=null`, sin error de división (US-011)

#### Scenario: BORDE — Turnos fuera de la disponibilidad pueden superar el 100 por ciento

- **DADO** un profesional con una ventana de 09:00 a 12:00 y un turno de 30 minutos forzado por recepción a las 12:00 del mismo día
- **CUANDO** se pide el reporte
- **ENTONCES** el turno suma a `minutos_ocupados` y `porcentaje_ocupacion` puede superar `100.0`, sin recorte ni error, porque señala sobreasignación (US-011)

#### Scenario: BORDE — La capacidad usa la configuración vigente al momento de la consulta

- **DADO** un profesional con `duracion_default_min=30` y una ventana 09:00–10:00 al momento de crear los turnos del rango, y luego el admin cambia `duracion_default_min` a 60 y la ventana a 09:00–12:00
- **CUANDO** se pide el reporte de ese mismo rango pasado después del cambio
- **ENTONCES** `minutos_disponibles` se calcula con la duración y la disponibilidad **actuales** (no con las vigentes cuando se agendaron los turnos), y ese comportamiento queda fijado por un test para que el denominador sea reproducible (US-011, D-9)

### Requirement: Semántica de rango y zona horaria del reporte

The system SHALL interpret `desde`/`hasta` as inclusive dates in `America/Argentina/Buenos_Aires`, count a turno by its `inicio` in the half-open range `[desde 00:00, hasta+1d 00:00)` local, and reject inverted ranges or ranges whose inclusive length exceeds 366 days (`(hasta - desde).days + 1 > 366`) with 400 whose `detail.campo` is `"hasta"`. (duro 10, US-011 CA-2.)

#### Scenario: BORDE — El borde del rango se evalúa en el día local

- **DADO** un turno con `inicio` a las 23:30 local del `hasta` y otro a las 00:00 local del día siguiente
- **CUANDO** se pide el reporte `desde`–`hasta`
- **ENTONCES** el primero cuenta en el rango y el segundo no, porque el borde superior es exclusivo en `hasta+1 día` local (duro 10)

#### Scenario: BORDE — Un turno persistido en UTC se cuenta en su día local

- **DADO** un turno cuyo `inicio` en UTC equivale a las 22:00 del día anterior en `America/Argentina/Buenos_Aires`
- **CUANDO** se pide el reporte de ese día local anterior
- **ENTONCES** el turno se cuenta en ese día y no en el día UTC, porque el rango se convierte a instantes locales antes de consultar (duro 10)

#### Scenario: FELIZ — Un rango de exactamente 366 días es aceptado

- **DADO** una sesión `admin` y `desde`/`hasta` con `(hasta - desde).days + 1 = 366`
- **CUANDO** se pide el reporte
- **ENTONCES** responde `200` y ejecuta la consulta, porque el tope es inclusivo (D-8, D-16)

#### Scenario: ERROR — Rango invertido responde 400 en hasta

- **DADO** una sesión `admin` y `desde=2026-11-10&hasta=2026-11-01`
- **CUANDO** se pide el reporte
- **ENTONCES** responde `400` con `detail` en `campo="hasta"` y no se ejecuta la consulta (duro 1)

#### Scenario: ERROR — Rango de 367 días responde 400 en hasta

- **DADO** una sesión `admin` y `desde`/`hasta` con `(hasta - desde).days + 1 = 367`
- **CUANDO** se pide el reporte
- **ENTONCES** responde `400` con `detail` en `campo="hasta"` (nunca `campo="query"`), porque el reporte acota el cómputo de capacidad (duro 1, duro 7)

#### Scenario: ERROR — Fechas faltantes o mal formadas responden 400 por campo

- **DADO** una sesión `recepcion`
- **CUANDO** se pide el reporte sin `desde` y `hasta`, o con `desde="11/2026"` (casos parametrizados)
- **ENTONCES** responde `400` con `detail` en el campo faltante o inválido correspondiente (duro 1)

### Requirement: Sin exportación en v1

The system SHALL return the occupancy report only as a JSON table; it SHALL NOT accept any export or format parameter, so a CSV or Excel request SHALL fail with 400 instead of producing a file. (PB-06, GATE 2026-10-11.)

#### Scenario: ERROR — Un pedido de CSV responde 400

- **DADO** una sesión `admin`
- **CUANDO** se pide `GET /api/reportes/ocupacion?desde=...&hasta=...&format=csv`
- **ENTONCES** responde `400` con `detail` en `campo="format"` y no devuelve ningún archivo (PB-06)

#### Scenario: ERROR — Un pedido de Excel responde 400

- **DADO** una sesión `admin`
- **CUANDO** se pide `GET /api/reportes/ocupacion?desde=...&hasta=...&format=xlsx`
- **ENTONCES** responde `400` con `detail` en `campo="format"` y no devuelve ningún archivo, porque no existe variante Excel en v1 (PB-06)

#### Scenario: FELIZ — La respuesta es JSON sin cabecera de descarga

- **DADO** un reporte válido que responde `200`
- **CUANDO** se inspeccionan las cabeceras y el cuerpo
- **ENTONCES** el `Content-Type` es JSON y no hay `Content-Disposition` de adjunto, porque en v1 el reporte es tabla y no export (PB-06)

### Requirement: Alcance del reporte por rol

The system SHALL allow `admin` and `recepcion` to read every professional row, allow `odontologo` only their own row (403 for a different one), and require a valid session (401). (US-011, RN-AU-01, KB-03.)

#### Scenario: FELIZ — Admin y recepción leen todos los profesionales

- **DADO** una sesión `admin` y una sesión `recepcion` (casos parametrizados)
- **CUANDO** cada una pide el reporte sin `profesional_id`
- **ENTONCES** ambas responden `200` con las filas de todos los profesionales del rango (RN-AU-01, KB-03)

#### Scenario: FELIZ — El odontólogo obtiene solo su propia fila

- **DADO** una sesión `odontologo` vinculada al profesional `P1` y otros profesionales con turnos en el rango
- **CUANDO** pide el reporte sin `profesional_id`
- **ENTONCES** responde `200` con una única fila de `P1`, sin datos de los demás (US-011, KB-03)

#### Scenario: ERROR — El odontólogo no consulta otro profesional

- **DADO** una sesión `odontologo` vinculada a `P1`
- **CUANDO** pide el reporte con `profesional_id=<P2>`
- **ENTONCES** responde `403` genérico sin datos de `P2` (RN-AU-01)

#### Scenario: ERROR — Un odontólogo sin profesional vinculado no accede al reporte

- **DADO** una sesión `odontologo` con `profesional_id=null`
- **CUANDO** pide el reporte
- **ENTONCES** responde `403` genérico, porque no hay alcance propio que resolver (RN-AU-01)

#### Scenario: ERROR — Sin sesión el reporte responde 401

- **DADO** un cliente sin cookie de sesión
- **CUANDO** pide `GET /api/reportes/ocupacion` con un rango válido
- **ENTONCES** responde `401` genérico sin ejecutar la consulta (staff-auth)
