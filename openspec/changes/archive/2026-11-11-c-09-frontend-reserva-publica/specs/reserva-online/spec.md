# Spec Delta

## MODIFIED Requirements

### Requirement: Reserva online crea turno, paciente, notificaciones y auditoría

The system SHALL create in one transaction the upserted `Paciente`, the `Turno` `reservado`/`online` with unique token, the append-only `AuditoriaTurno` and the pending `Notificacion` rows, isolating enqueue failures. It SHALL respond `201` with `notificaciones_encoladas` and the normalized cancellation link. (RN-TU-01/05/06, RN-PA-02, RN-NO-01, RN-AU-02, duro 5.)

Justificación: los errores 400 y 409 se cubren en R2-R5; aquí se especifican el camino feliz y los bordes de persistencia.

#### Scenario: Reserva válida crea turno reservado y responde 201

- **DADO** un profesional activo con `duracion_default_min=30`, una ventana local de 09:00 a 11:00 para el día pedido, sin bloqueos ni turnos activos, y un reloj fijo anterior a `inicio`
- **CUANDO** se hace `POST /api/turnos` con `inicio` futuro, `duracion_min` omitido y un `paciente` ficticio con los cinco datos y mail válido
- **ENTONCES** responde `201`; existe una fila `turno` con `estado=reservado`, `origen=online`, `duracion_min=30`, `fin=inicio+30` y token no nulo; existe una fila `paciente`; no se crea ninguna fila adicional para el mismo DNI; y la respuesta incluye `notificaciones_encoladas=true` (RN-TU-01, RN-TU-05, RN-AU-02)

#### Scenario: Reserva sin duracion_min usa la duración default del profesional

- **DADO** un profesional activo con `duracion_default_min=45` y una ventana local que cubre el slot pedido
- **CUANDO** se reserva omitiendo `duracion_min`
- **ENTONCES** responde `201` y la fila `turno` persiste `duracion_min=45` con `fin=inicio+45` (RN-TU-02, RN-AG-02)

#### Scenario: Reserva con DNI existente actualiza contacto sin duplicar paciente

- **DADO** un `Paciente` existente con `dni=30999001` y un teléfono anterior
- **CUANDO** se reserva con el mismo DNI, un teléfono nuevo y un mail válido
- **ENTONCES** responde `201`; sigue existiendo exactamente una fila `paciente` con ese DNI; el teléfono y el mail quedan actualizados; y el `turno.paciente_id` apunta a la fila existente (RN-PA-02)

#### Scenario: Reserva con paciente inactivo procede sin reactivarlo

- **DADO** un `Paciente` existente con `dni=30999003` y `activo=false`
- **CUANDO** se reserva con ese DNI y un contacto nuevo
- **ENTONCES** responde `201`; la fila `paciente` sigue con `activo=false`; el contacto se actualiza; y existe una sola fila `paciente` para ese DNI (PB-04, regla dura 3)

#### Scenario: Reserva escribe auditoría append-only con actor paciente

- **DADO** una reserva válida que responde `201`
- **CUANDO** se consulta `auditoria_turno` para el turno creado
- **ENTONCES** existe exactamente una fila con `accion=crear`, `actor_id=NULL` y `detalle` con `origen=online`, `profesional_id`, `inicio`, `fin`, `duracion_min` y `notificaciones_encoladas`; `detalle.inicio` y `detalle.fin` son strings ISO-8601 UTC, no objetos `datetime` (RN-AU-02)

#### Scenario: Reserva devuelve token y link de cancelación normalizado

- **DADO** una reserva válida que responde `201` y una `FRONTEND_URL` configurada con barra final (por ejemplo `https://app.test/`)
- **CUANDO** se lee el cuerpo de la respuesta
- **ENTONCES** incluye `id`, `estado=reservado`, `inicio`, `fin`, `duracion_min`, `notificaciones_encoladas`, `token_cancelacion` UUID y `cancel_url` con el formato exacto `https://app.test/cancelar?token=<token_cancelacion>&id=<turno_id>`, sin doble barra y con el `token` como primer parámetro (RN-TU-06, regla dura 4)

#### Scenario: El id del link de cancelación coincide con el id del turno

- **DADO** una reserva válida que responde `201`
- **CUANDO** se compara el parámetro `id` de `cancel_url` con el `id` del turno devuelto en la misma respuesta
- **ENTONCES** coinciden exactamente; el `id` es un localizador opaco (UUID) que no autentica y la credencial sigue siendo el `token_cancelacion` (RN-TU-06, regla dura 4)

#### Scenario: Reserva con anticipación mayor a 24h encola tres notificaciones

- **DADO** un turno pedido con más de 24 horas de anticipación respecto del reloj de la reserva
- **CUANDO** la reserva responde `201`
- **ENTONCES** existen tres filas `notificacion` con `estado=pendiente`: `confirmacion`, `recordatorio_24h` y `recordatorio_2h`; cada `payload` contiene `enviar_en` como string ISO-8601 UTC; `recordatorio_24h` usa `inicio-24h` y `recordatorio_2h` usa `inicio-2h` (RN-NO-01)

#### Scenario: Reserva con anticipación entre 2h y 24h omite el recordatorio de 24h

- **DADO** un turno pedido con más de 2 horas y menos de 24 horas de anticipación
- **CUANDO** la reserva responde `201`
- **ENTONCES** existen dos filas `notificacion` pendientes: `confirmacion` y `recordatorio_2h`; no existe `recordatorio_24h` (RN-NO-01)
