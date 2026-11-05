# reserva-online Specification

## Purpose

Define la reserva pública sin login: valida los datos del paciente, revalida el slot contra la disponibilidad vigente, crea el turno con anti-solape, encola las notificaciones y deja la auditoría, devolviendo el token de cancelación como única credencial.

## Requirements

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
- **ENTONCES** incluye `id`, `estado=reservado`, `inicio`, `fin`, `duracion_min`, `notificaciones_encoladas`, `token_cancelacion` UUID y `cancel_url` con el formato exacto `https://app.test/cancelar?token=<token_cancelacion>`, sin doble barra (RN-TU-06, regla dura 4)

#### Scenario: Reserva con anticipación mayor a 24h encola tres notificaciones

- **DADO** un turno pedido con más de 24 horas de anticipación respecto del reloj de la reserva
- **CUANDO** la reserva responde `201`
- **ENTONCES** existen tres filas `notificacion` con `estado=pendiente`: `confirmacion`, `recordatorio_24h` y `recordatorio_2h`; cada `payload` contiene `enviar_en` como string ISO-8601 UTC; `recordatorio_24h` usa `inicio-24h` y `recordatorio_2h` usa `inicio-2h` (RN-NO-01)

#### Scenario: Reserva con anticipación entre 2h y 24h omite el recordatorio de 24h

- **DADO** un turno pedido con más de 2 horas y menos de 24 horas de anticipación
- **CUANDO** la reserva responde `201`
- **ENTONCES** existen dos filas `notificacion` pendientes: `confirmacion` y `recordatorio_2h`; no existe `recordatorio_24h` (RN-NO-01)

### Requirement: Validación estricta de los cinco datos y del mail

The system SHALL require the five `paciente` fields, reject unknown fields at root and inside `paciente`, and treat empty or whitespace-only required values as missing. Invalid data SHALL respond `400` with one detail entry per field; an invalid email SHALL produce exactly one entry at `paciente.email`. (RN-TU-01, RN-PA-01, PB-02, duro 1.)

Justificación: aquí van error y borde; el body válido se cubre en R1 S1.

#### Scenario: Faltan campos obligatorios y responde 400 por campo

- **DADO** un body con `profesional_id` e `inicio` válidos y `paciente={}`
- **CUANDO** se hace `POST /api/turnos`
- **ENTONCES** responde `400`; `detail` contiene entradas para `paciente.nombre`, `paciente.dni`, `paciente.telefono`, `paciente.obra_social` y `paciente.email`; y no se crea ninguna fila `turno` (RN-TU-01, regla dura 1)

#### Scenario: Campos vacíos o solo espacios se tratan como faltantes

- **DADO** un body con `paciente.nombre=""`, `paciente.telefono="   "` y `paciente.obra_social=""`, con DNI y mail válidos
- **CUANDO** se hace `POST /api/turnos`
- **ENTONCES** responde `400`; `detail` contiene una entrada por cada campo vacío o solo espacios (`paciente.nombre`, `paciente.telefono`, `paciente.obra_social`); y no se crea ninguna fila `turno` (RN-TU-01, regla dura 1)

#### Scenario: Mail inválido responde 400 solo en paciente.email

- **DADO** un body con los otros cuatro datos válidos y `paciente.email="no-es-email"`
- **CUANDO** se hace `POST /api/turnos`
- **ENTONCES** responde `400`; `detail` contiene exactamente una entrada con `campo="paciente.email"`; y no se crea ninguna fila `turno` (RN-TU-01, PB-02, regla dura 1)

#### Scenario: Campo extra anidado responde 400 en ese campo

- **DADO** un body válido con un campo no declarado dentro de `paciente` (por ejemplo `alergias`)
- **CUANDO** se hace `POST /api/turnos`
- **ENTONCES** responde `400`; `detail` contiene una entrada con `campo="paciente.alergias"`; y no se crea ninguna fila `turno` (regla dura 1)

#### Scenario: Campo extra en la raíz responde 400 en ese campo

- **DADO** un body válido con un campo no declarado en la raíz (por ejemplo `notas`)
- **CUANDO** se hace `POST /api/turnos`
- **ENTONCES** responde `400`; `detail` contiene una entrada con `campo="notas"`; y no se crea ninguna fila `turno` (regla dura 1)

#### Scenario: inicio no futuro responde 400 en inicio

- **DADO** un reloj fijo y un `inicio` anterior o igual a ese reloj
- **CUANDO** se hace `POST /api/turnos`
- **ENTONCES** responde `400`; `detail` contiene `campo="inicio"`; y no se crea ninguna fila `turno` (regla dura 1, D-10)

#### Scenario: inicio sin zona horaria responde 400 en inicio

- **DADO** un `inicio` ISO sin offset (por ejemplo `2026-11-05T09:00:00`)
- **CUANDO** se hace `POST /api/turnos`
- **ENTONCES** responde `400`; `detail` contiene `campo="inicio"` con tipo `inicio_sin_zona`; y no se crea ninguna fila `turno` (regla dura 1, D-10)

### Requirement: Duración consistente con la granularidad del profesional

The system SHALL use `profesional.duracion_default_min` when `duracion_min` is omitted and SHALL accept `duracion_min` only as a positive multiple of that granularity. Otherwise it SHALL respond `400` with a single detail entry at `duracion_min` and SHALL NOT create the turno. (RN-TU-02, RN-AG-02.)

#### Scenario: duracion_min no múltiplo responde 400 y no crea turno

- **DADO** un profesional con `duracion_default_min=30`
- **CUANDO** se reserva con `duracion_min=40`
- **ENTONCES** responde `400`; `detail` contiene una única entrada con `campo="duracion_min"` y tipo `duracion_no_multiplo_granularidad`; y no se crea ninguna fila `turno` (RN-TU-02, RN-AG-02)

#### Scenario: duracion_min cero o negativa responde 400 y no crea turno

- **DADO** un profesional con `duracion_default_min=30` y un `inicio` válido
- **CUANDO** se reserva con `duracion_min=0` o `duracion_min=-30` (casos parametrizados)
- **ENTONCES** responde `400`; `detail` contiene una única entrada con `campo="duracion_min"`; y no se crea ninguna fila `turno` (RN-TU-02, RN-AG-02)

#### Scenario: duracion_min múltiplo reserva un bloque contiguo

- **DADO** un profesional con `duracion_default_min=30` y una ventana con dos slots libres consecutivos
- **CUANDO** se reserva con `duracion_min=60` en el inicio del primer slot
- **ENTONCES** responde `201`; la fila `turno` persiste `duracion_min=60` y `fin=inicio+60` (RN-TU-02, RN-AG-02)

### Requirement: Revalidación del slot contra la disponibilidad calculada

The system SHALL accept a reservation only when `[inicio, inicio+duracion_min)` is fully covered by free slots of the professional's computed availability for that local day, aligned to the professional's grid. Otherwise it SHALL respond `409` with up to five alternatives of the same day, as blocks of the requested `duracion_min` (or the default when omitted), and SHALL NOT create the turno or a patient. (RN-TU-03, RN-TU-05, RN-AG-01, RN-AG-02.)

#### Scenario: Slot fuera de ventana o bloqueado responde 409 con alternativos

- **DADO** un profesional sin ventana para el horario pedido, o con un bloqueo que cubre ese horario
- **CUANDO** se hace `POST /api/turnos` con ese `inicio`
- **ENTONCES** responde `409`; `detail.codigo="slot_no_disponible"`; `detail.alternativos` contiene hasta cinco slots libres del mismo día local; no se crea ninguna fila `turno`; y no se crea ni actualiza ningún `paciente` (RN-AG-01, RN-TU-05, RN-TU-03)

#### Scenario: inicio no alineado a la grilla responde 409

- **DADO** un profesional con `duracion_default_min=30` y una ventana que cubre las 09:00
- **CUANDO** se reserva con `inicio=09:15` local
- **ENTONCES** responde `409`; `detail.codigo="slot_no_disponible"`; `detail.alternativos` contiene solo inicios alineados a la grilla; no se crea ninguna fila `turno`; y no se crea ni actualiza ningún `paciente` (RN-AG-02, RN-TU-05)

#### Scenario: Bloque contiguo con el segundo slot ocupado responde 409

- **DADO** un profesional con `duracion_default_min=30`, el primer slot libre y el segundo slot ocupado por un turno activo
- **CUANDO** se reserva con `duracion_min=60` en el inicio del primer slot
- **ENTONCES** responde `409`; `detail.codigo="slot_no_disponible"`; no se crea ninguna fila `turno`; y no se crea ni actualiza ningún `paciente` (RN-TU-05, RN-AG-02, RN-TU-03)

#### Scenario: Reserva en el borde de la ventana es aceptada

- **DADO** una ventana local de 09:00 a 10:00 sin bloqueos ni turnos activos
- **CUANDO** se reserva un slot de 30 minutos que termina exactamente a las 10:00
- **ENTONCES** responde `201` y la fila `turno` persiste con `fin=10:00`, porque el intervalo es half-open `[inicio, fin)` (RN-AG-01, RN-TU-05)

#### Scenario: Alternativos son del mismo día, excluyen el pedido y respetan la duración pedida

- **DADO** un slot pedido ocupado y otros slots libres ese mismo día local, con `duracion_min=60` solicitada
- **CUANDO** la API responde `409`
- **ENTONCES** todos los `alternativos` tienen la misma fecha local que el `inicio` pedido, ninguno tiene el mismo `inicio` pedido, están ordenados por `inicio` ascendente, son como máximo cinco y cada uno cumple `fin=inicio+60`, alineado a la grilla del profesional (RN-TU-03, RN-AG-02)

#### Scenario: Turno cancelado no bloquea el slot

- **DADO** un `Turno` con `estado=cancelado` en el horario pedido
- **CUANDO** se reserva ese mismo horario con un profesional y paciente válidos
- **ENTONCES** responde `201` y se crea una nueva fila `turno` activa en ese horario (RN-TU-05, RN-TU-07)

### Requirement: Anti-solape y colisión concurrente con un solo ganador

The system SHALL rely on the database anti-overlap exclusion as the final authority and SHALL map its constraint violation to `409` with alternatives. It SHALL also take a `SELECT ... FOR UPDATE` lock on the professional row at the start of the reservation transaction, so that two concurrent reservations of the same slot produce exactly one `Turno` and the second transaction waits for the lock and ends in `409`, never in `500` or a double insert. (RN-TU-03, regla dura 2, RN-PA-02.)

#### Scenario: Slot ocupado responde 409 con alternativos y sin paciente nuevo

- **DADO** un `Turno` activo (`reservado` o `confirmado`) del profesional en el horario pedido
- **CUANDO** se hace `POST /api/turnos` para el mismo horario
- **ENTONCES** responde `409`; `detail.codigo="slot_ocupado"`; `detail.alternativos` contiene hasta cinco slots del mismo día; el conteo de turnos del profesional no aumenta; y no se crea ni actualiza ningún `paciente` (RN-TU-03, regla dura 2, RN-PA-02)

#### Scenario: La segunda transacción espera el lock del profesional y termina en 409

- **DADO** dos transacciones reales que reservan el mismo profesional, `inicio` y `duracion_min`, con pacientes distintos; la primera ya tomó el `SELECT ... FOR UPDATE` del profesional y todavía no commiteó
- **CUANDO** la segunda intenta reservar el mismo slot
- **ENTONCES** la segunda espera el lock hasta que la primera commitea, luego responde `409` con alternativos (no `500`), en la base queda exactamente una fila `turno` activa para ese slot y no queda un `paciente` huérfano de la segunda transacción (RN-TU-03, regla dura 2, RN-PA-02)

#### Scenario: El EXCLUDE es autoridad final ante una escritura fuera del lock

- **DADO** un slot libre pre-validado y una escritura concurrente que inserta un turno activo en ese slot sin tomar el lock del profesional (por ejemplo, una ruta de staff)
- **CUANDO** la reserva intenta insertar su `Turno`
- **ENTONCES** el `IntegrityError` de `no_solape_prof` se mapea a `409` con alternativos, no a `500`, y no queda una segunda fila activa para ese slot; la transacción completa se revierte, incluido el upsert de paciente (RN-TU-03, regla dura 2, RN-PA-02)

#### Scenario: Reservas contiguas no colisionan

- **DADO** un turno activo que termina exactamente cuando empieza el slot pedido
- **CUANDO** se reserva ese slot contiguo
- **ENTONCES** responde `201` y existen dos filas `turno` activas contiguas, porque el rango es half-open `[inicio, fin)` (RN-TU-03)

### Requirement: Encolado de notificaciones no bloqueante

The system SHALL enqueue a `confirmacion` notification for every reservation, without any fallback for a missing mail, and SHALL enqueue `recordatorio_24h`/`recordatorio_2h` only when the anticipation allows it: `recordatorio_24h` if `inicio - 24h > now` and `recordatorio_2h` if `inicio - 2h > now` (strict comparison). It SHALL leave them `pendiente` for the C-08 worker and SHALL commit the reservation even if the enqueue insert fails. (RN-NO-01, RN-NO-02, regla dura 5.)

#### Scenario: Fallo del encolado no bloquea la reserva

- **DADO** una reserva válida y un fallo simulado al insertar las `Notificacion`
- **CUANDO** se hace `POST /api/turnos`
- **ENTONCES** responde `201`; la fila `turno` y la fila `auditoria_turno` persisten; la auditoría registra `notificaciones_encoladas=false`; la respuesta también informa `notificaciones_encoladas=false`; y no se propaga un error de servidor (RN-NO-02, regla dura 5)

#### Scenario: Notificaciones quedan pendientes para el worker

- **DADO** una reserva válida que responde `201`
- **CUANDO** se consultan las filas `notificacion` del turno
- **ENTONCES** todas tienen `estado=pendiente`, `intentos=0` y `enviada_at=NULL`; sus `payload.enviar_en` son strings ISO-8601 UTC; C-05 no envía SMTP ni marca ninguna como `enviada` (RN-NO-01, RN-NO-02)

#### Scenario: Anticipación menor a 2h encola solo la confirmación

- **DADO** un turno pedido con menos de 2 horas de anticipación respecto del reloj de la reserva
- **CUANDO** la reserva responde `201`
- **ENTONCES** existe una sola fila `notificacion` pendiente, de tipo `confirmacion`; no existen `recordatorio_24h` ni `recordatorio_2h` (RN-NO-01)

#### Scenario: Anticipación exactamente 24h omite solo el recordatorio de 24h

- **DADO** un turno pedido con exactamente 24 horas de anticipación (`inicio - 24h == now`)
- **CUANDO** la reserva responde `201`
- **ENTONCES** existen dos filas `notificacion` pendientes: `confirmacion` y `recordatorio_2h`; no existe `recordatorio_24h`, porque la comparación `inicio - 24h > now` es estricta (RN-NO-01)

#### Scenario: Anticipación exactamente 2h omite el recordatorio de 2h

- **DADO** un turno pedido con exactamente 2 horas de anticipación (`inicio - 2h == now`)
- **CUANDO** la reserva responde `201`
- **ENTONCES** existe una sola fila `notificacion` pendiente, de tipo `confirmacion`; no existe `recordatorio_2h` ni `recordatorio_24h`, porque las comparaciones son estrictas (RN-NO-01)

### Requirement: Rate limit del endpoint público de reserva

The system SHALL rate-limit `POST /api/turnos` per client IP with a fixed window of 60 seconds and a limit of 10 reservations per IP (D-9), and SHALL respond `429` with `Retry-After` in seconds until the window reset when the limit is exceeded, without creating a turno for the rejected request. (RN-AU-03.)

#### Scenario: Reserva dentro del límite responde 201 y consume cupo

- **DADO** una IP que no consumió reservas en la ventana de 60 segundos y un body válido
- **CUANDO** se hace `POST /api/turnos`
- **ENTONCES** responde `201` y la IP queda con una reserva consumida en la ventana (RN-AU-03)

#### Scenario: La reserva número 10 pasa y la 11 responde 429

- **DADO** una IP con 9 reservas consumidas en la ventana de 60 segundos y un reloj fijo
- **CUANDO** esa IP hace la reserva número 10 y luego la número 11 con bodies válidos
- **ENTONCES** la número 10 responde `201`; la número 11 responde `429`, incluye el header `Retry-After` con los segundos hasta el reset y no crea una fila `turno` (RN-AU-03)

#### Scenario: IPs distintas no comparten el cupo de reservas

- **DADO** una IP A que agotó sus 10 reservas en la ventana
- **CUANDO** una IP B hace una reserva con un body válido
- **ENTONCES** la IP B recibe `201`, porque el contador es por IP (RN-AU-03)

### Requirement: Profesional inexistente o inactivo

The system SHALL respond `404` without revealing internal details when `profesional_id` does not exist or is inactive, and SHALL NOT create a `Turno` or a `Paciente`. (RN-AG-01, RN-TU-05.)

#### Scenario: Profesional inexistente responde 404

- **DADO** un `profesional_id` UUID que no existe en la base
- **CUANDO** se hace `POST /api/turnos` con un body por lo demás válido
- **ENTONCES** responde `404`; no se crea ninguna fila `turno`; y no se crea ni actualiza ningún `paciente` (RN-AG-01, RN-TU-05)

#### Scenario: Profesional inactivo responde 404

- **DADO** un profesional existente con `activo=false` y una ventana cargada
- **CUANDO** se hace `POST /api/turnos` con un body por lo demás válido
- **ENTONCES** responde `404`; no se crea ninguna fila `turno`; y no se crea ni actualiza ningún `paciente` (RN-AG-01, RN-TU-05)

#### Scenario: Profesional activo con el mismo body responde 201

- **DADO** el mismo body válido del caso 404, pero con un profesional activo y ventana disponible
- **CUANDO** se hace `POST /api/turnos`
- **ENTONCES** responde `201` y se crea el `turno`, para que la regla de rechazo no afecte a profesionales activos (RN-TU-05)

### Requirement: Token de cancelación como única credencial

The system SHALL generate a unique `token_cancelacion` per turno, SHALL return it only in the reservation response as part of the cancellation link, and SHALL NOT require login or accept DNI+teléfono as credentials. (RN-TU-06, PB-01, regla dura 4.)

#### Scenario: Dos reservas generan tokens distintos

- **DADO** dos reservas válidas en slots distintos
- **CUANDO** ambas responden `201`
- **ENTONCES** cada fila `turno` tiene un `token_cancelacion` no nulo y distinto del otro (RN-TU-06, PB-01)

#### Scenario: La reserva no requiere login

- **DADO** un cliente sin cookie de sesión ni header de autorización
- **CUANDO** hace `POST /api/turnos` con un body válido
- **ENTONCES** responde `201` y la respuesta entrega el `token_cancelacion`, sin exigir autenticación (RN-TU-06, regla dura 4)

#### Scenario: DNI y teléfono en la raíz no funcionan como credencial

- **DADO** un body que intenta enviar `dni` y `telefono` como campos de la raíz, además del `paciente` válido
- **CUANDO** se hace `POST /api/turnos`
- **ENTONCES** responde `400` con `detail` por `campo="dni"` y `campo="telefono"` (campos extra), no se crea ninguna fila `turno` y la única credencial sigue siendo el `token_cancelacion` devuelto al reservar (regla dura 4, regla dura 1, RN-TU-06)
