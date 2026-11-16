# Spec Delta

## Purpose

Define las pantallas staff del consultorio: sesión protegida, agenda día/semana multi-profesional, operación de turnos desde recepción (alta, reprogramación, cancelación normal y forzada, corrección de paciente y asistencia) y panel de notificaciones fallidas, con privacidad de datos, fechas en la zona del consultorio y mobile-first 360px.

## ADDED Requirements

### Requirement: Sesión staff y protección de rutas

La UI SHALL autenticar staff con `POST /api/auth/login` (email+password), mantener la sesión solo en la cookie httpOnly, resolver la identidad con `GET /api/auth/me` al montar el layout staff y redirigir a `/staff/login` ante cualquier `401`. Ningún token de sesión SHALL leerse ni persistirse en JavaScript. (Flujo 5, staff-auth, RN-AU-01.)

#### Scenario: Login válido inicia sesión y abre la agenda

- **DADO** un staff activo y credenciales correctas
- **CUANDO** envía el formulario de `/staff/login`
- **ENTONCES** la app recibe `200` con `email` y `rol`, la cookie httpOnly queda activa y navega a `/staff/agenda` mostrando la agenda del profesional

#### Scenario: Credenciales inválidas muestran un mensaje genérico

- **DADO** un email inexistente o una password incorrecta
- **CUANDO** se envía el login y el backend responde `401`
- **ENTONCES** se muestra un mensaje genérico de credenciales inválidas, sin indicar si el email existe ni si la cuenta está inactiva

#### Scenario: 400 de login marca el campo inválido

- **DADO** un email sin formato válido o una password vacía
- **CUANDO** se envía el login y el backend responde `400` con `detail` por campo
- **ENTONCES** se marca el campo indicado (`email` o `password`), se conserva lo ingresado y no se navega

#### Scenario: Ruta staff sin sesión redirige a login

- **DADO** un usuario sin cookie de sesión
- **CUANDO** abre `/staff/agenda` o `/staff/notificaciones`
- **ENTONCES** `GET /api/auth/me` responde `401` y la app redirige a `/staff/login` sin renderizar datos de agenda

#### Scenario: EDGE — sesión expirada durante una operación redirige a login

- **DADO** una sesión que expira mientras la agenda o una mutación están en curso
- **CUANDO** el backend responde `401`
- **ENTONCES** se descarta el estado en pantalla, se redirige a `/staff/login` con un aviso de sesión expirada y no se muestran datos del turno ni del paciente

#### Scenario: Logout invalida la sesión y vuelve a login

- **DADO** un staff autenticado
- **CUANDO** confirma el logout
- **ENTONCES** se envía `POST /api/auth/logout`, se limpia el estado de sesión y se navega a `/staff/login`; un pedido posterior con la cookie anterior recibe `401`

#### Scenario: EDGE — logout fallido conserva la sesión y muestra el error

- **DADO** un staff autenticado y un `POST /api/auth/logout` que falla por red o responde `5xx`
- **CUANDO** se procesa el error
- **ENTONCES** se muestra un mensaje accionable, no se navega, la sesión local y la cookie siguen activas y las acciones staff permanecen disponibles para reintentar (staff-auth §Logout invalida la sesión, D-3)

#### Scenario: 429 en login muestra el mensaje de demasiados intentos

- **DADO** el rate-limit de login excedido
- **CUANDO** el backend responde `429` sin header `Retry-After` (`POST /api/auth/login` no lo emite en v1)
- **ENTONCES** se muestra un mensaje de demasiados intentos con espera genérica ("esperá un momento antes de reintentar"), no se navega, no se reintenta automáticamente y el formulario queda disponible para reintentar manualmente

#### Scenario: EDGE — 429 en login con `Retry-After` usa la espera indicada

- **DADO** el rate-limit de login excedido y una respuesta `429` que sí incluye `Retry-After`
- **CUANDO** se procesa el error
- **ENTONCES** el mensaje indica la espera exacta en segundos en lugar del texto genérico, sin reintento automático

### Requirement: Agenda día/semana por profesional

La UI SHALL mostrar la agenda del profesional seleccionado en vista día o semana, con franjas `libre`, `ocupado` (estado y paciente) y `bloqueado` (motivo), más los turnos cerrados del día y la `ultima_actualizacion`. Cambiar de profesional SHALL consultar solo la agenda elegida. (US-001 CA-1/CA-2/CA-3, US-002 CA-3, RN-TU-05.)

#### Scenario: Vista día muestra libres, ocupados y bloqueados

- **DADO** un profesional con una franja libre, un turno activo y un bloqueo en el día
- **CUANDO** se abre la vista día
- **ENTONCES** cada franja se muestra con su tipo, horario y detalle: `libre`, `ocupado` con estado y nombre del paciente, y `bloqueado` con motivo

#### Scenario: Vista semana muestra siete días y navega por fecha

- **DADO** un profesional con ventanas de lunes a viernes
- **CUANDO** se elige la vista semana
- **ENTONCES** se muestran los siete días desde la fecha elegida, ordenados, con navegación al período anterior y siguiente; el `next_cursor` de la respuesta es la fecha del período siguiente (`fecha+7d`, nunca un cursor opaco) y se usa tal cual para avanzar, sin OFFSET (duro 7)

#### Scenario: Cambiar de profesional no recarga agendas ajenas

- **DADO** dos profesionales con agenda propia
- **CUANDO** la recepción cambia el selector de profesional
- **ENTONCES** se consulta únicamente la agenda del profesional elegido para la vista y fecha actuales y no se solicita la agenda de los demás

#### Scenario: Última actualización visible por profesional

- **DADO** un profesional con `ultima_actualizacion` informada por el backend
- **CUANDO** se muestra su agenda
- **ENTONCES** la fecha y hora de última actualización se muestran en la zona del consultorio; si es `null`, se muestra "sin datos cargados" y no se trata como error

#### Scenario: Turnos cerrados del día son visibles como historial

- **DADO** un turno del día en estado `atendido`, `ausente` o `cancelado`
- **CUANDO** se muestra la agenda staff
- **ENTONCES** aparece en la lista de cerrados del día con su estado y paciente, en modo lectura, mientras su horario se sigue mostrando como `libre` porque un turno terminal no ocupa disponibilidad

#### Scenario: Una mutación de turno refresca la agenda sin mover la última actualización

- **DADO** una agenda con `ultima_actualizacion` conocida
- **CUANDO** una mutación staff (alta, reprogramación, cancelación, corrección o estado) responde con éxito y se refresca la agenda
- **ENTONCES** la agenda muestra los cambios del turno y `ultima_actualizacion` conserva el valor informado por el backend, porque solo los cambios de `disponibilidad` o `bloqueo` la mueven (trigger `002_agenda_meta`, RN-TU-05)

#### Scenario: Agenda vacía muestra un estado vacío explícito

- **DADO** un profesional sin ventanas, bloqueos ni turnos para la fecha
- **CUANDO** se muestra la agenda
- **ENTONCES** se informa que no hay horarios ni turnos para el período, sin mostrarlo como error ni inventar franjas

#### Scenario: Profesional inexistente invita a recargar

- **DADO** un `id` de profesional inexistente cuyo `GET /api/profesionales/{id}/agenda` responde `404`
- **CUANDO** se consulta su agenda
- **ENTONCES** se muestra que el profesional no está disponible, se conserva la fecha y se ofrece recargar la lista de profesionales; un profesional inactivo existente no cae en este caso porque el backend responde `200` a staff (ver `agenda-disponibilidad`)

#### Scenario: EDGE — lista de profesionales vacía muestra un estado explícito

- **DADO** un `GET /api/profesionales` que responde `200` con `items: []`
- **CUANDO** se muestra la agenda
- **ENTONCES** se informa que no hay profesionales disponibles en ese momento, no se selecciona ninguno y no se solicita la agenda de un profesional inexistente (RN-AU-01, KB-03 RBAC)

#### Scenario: Error al cargar profesionales permite reintentar

- **DADO** un `GET /api/profesionales` que falla por red o responde `5xx`
- **CUANDO** se procesa el error
- **ENTONCES** se muestra un mensaje con reintento, se conservan la fecha y la vista elegidas, no se inventan ni se seleccionan profesionales y un `401` redirige a `/staff/login` (RN-AU-01, staff-auth §Semántica 401 sin sesión vs 403 sin permiso)

#### Scenario: EDGE — odontología no ve la agenda de otro profesional

- **DADO** una sesión de odontología vinculada a un profesional y la agenda de otro profesional
- **CUANDO** la UI recibe `403`
- **ENTONCES** se muestra un mensaje genérico de falta de permiso, sin datos de la agenda ni del paciente; el selector de odontología solo ofrece su propia agenda

#### Scenario: 429 en agenda muestra la espera

- **DADO** un `GET /api/profesionales/{id}/agenda` que responde `429` con `Retry-After`
- **CUANDO** se procesa la respuesta
- **ENTONCES** se muestra el mensaje de demasiados intentos con la espera indicada, sin reintento automático

#### Scenario: Error de red conserva la selección y permite reintentar

- **DADO** un fallo de red al cargar la agenda
- **CUANDO** falla la llamada
- **ENTONCES** se muestra un error con reintento y se conservan el profesional, la vista y la fecha elegidos

### Requirement: Alta de turno de recepción

La UI SHALL permitir a recepción/admin crear un turno desde una franja libre con `origen=recepcion` y los cinco datos obligatorios, refrescando la agenda al recibir `201`. Si el DNI ya existe, el turno SHALL reutilizar ese paciente y actualizar su ficha sin duplicarlo. Los `400` por campo y `409` con alternativos SHALL conservar lo ingresado. Odontología SHALL NOT disponer de la acción. (US-006, RN-TU-01/02/03, RN-PA-02, duro 3.)

#### Scenario: Alta válida crea el turno y refresca la agenda

- **DADO** una franja libre seleccionada y los cinco datos ficticios del paciente completos
- **CUANDO** recepción envía el alta con `origen=recepcion`
- **ENTONCES** el backend responde `201`, se cierra el formulario, se refresca la agenda y la franja pasa a mostrarse ocupada con el paciente

#### Scenario: Campos faltantes marcan inputs y no envían

- **DADO** el formulario con uno o más de los cinco datos obligatorios vacíos
- **CUANDO** se intenta crear el turno
- **ENTONCES** se marcan los campos faltantes, no se envía la solicitud y se conserva la franja elegida (RN-TU-01, duro 1)

#### Scenario: Mail con formato inválido marca solo el campo email

- **DADO** el formulario con los cinco datos completos y un email sin formato válido
- **CUANDO** se intenta crear el turno
- **ENTONCES** se marca únicamente `email` con su mensaje, los demás campos no se marcan como faltantes y no se envía la solicitud; si el backend responde `400` con `detail` solo en `paciente.email`, el error se mapea al mismo campo (RN-TU-01, PB-02, duro 1)

#### Scenario: EDGE — DNI existente reutiliza el paciente y actualiza su ficha

- **DADO** un DNI ya registrado con datos de contacto distintos de los ingresados y el resto de los campos válidos
- **CUANDO** recepción envía el alta
- **ENTONCES** el backend responde `201`, el turno queda asociado al paciente existente y su ficha muestra nombre, email, teléfono y obra social enviados, sin crear un paciente duplicado (RN-PA-02, duro 3, Ley 25.326)

#### Scenario: 409 por slot ocupado muestra alternativos y conserva los datos

- **DADO** un alta sobre una franja que se ocupó después de cargar la agenda
- **CUANDO** el backend responde `409` con `alternativos` del mismo día
- **ENTONCES** se muestra el mensaje de horario ocupado, se listan los alternativos y se conservan los datos del paciente para reintentar con otro horario

#### Scenario: 409 por slot no disponible invita a reconsultar

- **DADO** un alta con una duración que excede los bloques libres contiguos
- **CUANDO** el backend responde `409` con `codigo="slot_no_disponible"`
- **ENTONCES** se informa que el horario ya no está disponible, se conservan los datos y se ofrece refrescar la agenda antes de reintentar

#### Scenario: La duración solo admite múltiplos de la granularidad

- **DADO** un profesional con `duracion_default_min` de 30 o 45 minutos
- **CUANDO** se elige la duración del turno
- **ENTONCES** las opciones son múltiplos de esa granularidad y la UI no ofrece valores que el backend rechazaría

#### Scenario: EDGE — odontología no ve la acción de alta

- **DADO** una sesión con rol odontología
- **CUANDO** se muestra la agenda
- **ENTONCES** no se ofrece la acción de crear turno; un `403` defensivo se muestra como falta de permiso sin datos

#### Scenario: Encolado de mails fallido se informa sin ocultar el alta

- **DADO** un alta que responde `201` con `notificaciones_encoladas=false`
- **CUANDO** se muestra el resultado
- **ENTONCES** se informa que el turno quedó creado pero no se pudieron encolar los mails y se invita a contactar al consultorio, sin mostrar el turno como fallido

### Requirement: Reprogramación y cambio de duración

La UI SHALL permitir reprogramar `inicio` y/o `duracion_min` de turnos `reservado`/`confirmado`, ofreciendo solo franjas libres y duraciones múltiplo de la granularidad. Turnos terminales SHALL NOT ofrecer reprogramación. Un `409` SHALL conservar la ficha abierta y mostrar alternativos. (US-006 CA-2, RN-TU-02/03/07.)

#### Scenario: Reprogramación a un slot libre actualiza ficha y agenda

- **DADO** un turno `reservado` o `confirmado` y una franja libre del mismo profesional
- **CUANDO** recepción confirma la reprogramación
- **ENTONCES** el backend responde `200`, la ficha muestra el nuevo inicio y fin, y la agenda de origen y destino se refresca

#### Scenario: Cambio de duración válido recalcula el fin

- **DADO** un turno activo y una duración múltiplo de la granularidad con bloques contiguos libres
- **CUANDO** recepción cambia solo la duración
- **ENTONCES** el backend responde `200`, la ficha muestra la nueva duración y el nuevo `fin`

#### Scenario: 409 en el destino muestra alternativos sin mover el turno

- **DADO** un destino que se ocupó antes de confirmar
- **CUANDO** el backend responde `409` con alternativos
- **ENTONCES** se muestran los alternativos, la ficha sigue con los datos anteriores y no se muestra éxito

#### Scenario: Turno terminal no ofrece reprogramación

- **DADO** un turno `cancelado`, `atendido` o `ausente`
- **CUANDO** se abre su ficha
- **ENTONCES** no se ofrece la acción de reprogramar; si el backend responde `422 turno_no_editable`, se informa el estado y se refresca la ficha sin mostrar éxito

#### Scenario: EDGE — inicio pasado o duración inválida marca el campo

- **DADO** un `inicio` anterior al reloj o una duración no múltiplo de la granularidad
- **CUANDO** el backend responde `400` por campo
- **ENTONCES** se marca el campo `inicio` o `duracion_min` y el turno no se muestra modificado

### Requirement: Cancelación normal y forzada con motivo

La UI SHALL cancelar turnos staff; solo los turnos `reservado` y `confirmado` SHALL ofrecer la acción, mientras que `atendido`, `ausente` y `cancelado` SHALL NOT ofrecerla. Cuando falten menos de 3 horas para `inicio` SHALL exigir un motivo no vacío antes de enviar. `turno_ya_cancelado` y `turno_no_cancelable` SHALL informar el estado sin ofrecer reintento. Odontología SHALL NOT cancelar. (US-006 CA-3, RN-TU-04/07, RN-AU-02.)

#### Scenario: Cancelación con 3 horas o más confirma y libera el slot

- **DADO** un turno activo con `inicio` a 3 horas o más del reloj
- **CUANDO** recepción confirma la cancelación sin motivo
- **ENTONCES** el backend responde `200`, el turno queda `cancelado`, la agenda muestra la franja como libre y el turno como cerrado cancelado

#### Scenario: EDGE — menos de 3 horas sin motivo no permite confirmar

- **DADO** un turno activo con `inicio` a menos de 3 horas del reloj
- **CUANDO** se abre la cancelación
- **ENTONCES** el campo motivo es obligatorio, la acción de confirmar permanece deshabilitada hasta ingresar un motivo no vacío y no se envía ninguna solicitud

#### Scenario: Menos de 3 horas con motivo cancela y queda auditado

- **DADO** un turno activo con `inicio` a menos de 3 horas y un motivo válido ingresado
- **CUANDO** recepción confirma la cancelación forzada
- **ENTONCES** el backend responde `200`, el turno queda `cancelado` y el historial de la ficha muestra la acción de cancelación forzada con el motivo y el actor

#### Scenario: 422 motivo_requerido reabre el campo y no cancela

- **DADO** un envío sin motivo que el backend rechaza con `422 motivo_requerido` porque su reloj o configuración difieren de la UI
- **CUANDO** se procesa la respuesta
- **ENTONCES** se conserva el turno sin cambios, se revela el campo motivo como obligatorio y no se muestra éxito

#### Scenario: Turno ya cancelado o no cancelable informa el estado

- **DADO** un `422` con `turno_ya_cancelado` o `turno_no_cancelable`
- **CUANDO** se procesa la respuesta
- **ENTONCES** se informa el estado del turno, se refresca la ficha y no se ofrece reintentar la cancelación

#### Scenario: Estados terminales no ofrecen cancelar

- **DADO** un turno `atendido`, `ausente` o `cancelado`
- **CUANDO** se abre su ficha
- **ENTONCES** la acción de cancelar no se ofrece y el turno se muestra en modo lectura (RN-TU-07)

#### Scenario: EDGE — odontología no ve la acción de cancelar

- **DADO** una sesión con rol odontología y un turno propio
- **CUANDO** se muestra la ficha
- **ENTONCES** no se ofrece cancelar; un `403` defensivo se muestra como falta de permiso sin datos

### Requirement: Corrección de datos del paciente con historial

La ficha SHALL mostrar datos del paciente y su historial auditable; recepción/admin SHALL corregir DNI, teléfono y obra social. Nombre y email SHALL NOT ofrecerse como editables. Un `409 dni_duplicado` SHALL informarse sin fusionar pacientes. (US-007, RN-PA-02, RN-AU-02.)

#### Scenario: Ficha muestra datos e historial

- **DADO** un turno con paciente y filas de auditoría
- **CUANDO** recepción abre la ficha
- **ENTONCES** se muestran estado, origen, inicio, fin, duración, profesional, datos del paciente y el historial con acción, actor, fecha y cambios

#### Scenario: La ficha no ofrece editar nombre ni email

- **DADO** una ficha de turno con nombre y email del paciente
- **CUANDO** recepción abre la corrección
- **ENTONCES** los únicos campos editables son DNI, teléfono y obra social; nombre y email se muestran en modo lectura

#### Scenario: 404 al refrescar la ficha cierra el panel

- **DADO** una ficha abierta cuyo turno ya no existe o responde `404`
- **CUANDO** se refresca la ficha
- **ENTONCES** se informa que el turno no está disponible, se cierra el panel y se refresca la agenda sin dejar acciones habilitadas sobre el turno inexistente

#### Scenario: Corrección válida refresca ficha e historial

- **DADO** un turno existente y nuevos teléfono y obra social
- **CUANDO** recepción guarda la corrección
- **ENTONCES** el backend responde `200`, la ficha muestra los valores nuevos y el historial agrega la corrección con antes y después

#### Scenario: DNI duplicado informa sin fusionar

- **DADO** un DNI que ya pertenece a otro paciente
- **CUANDO** el backend responde `409 dni_duplicado`
- **ENTONCES** se informa que el DNI ya está en uso, se conservan ambos pacientes por separado y la ficha no cambia

#### Scenario: DNI inválido o campo vacío marca el input

- **DADO** un DNI con formato inválido o un teléfono/obra social vacío
- **CUANDO** el backend responde `400` por campo
- **ENTONCES** se marca el campo indicado y no se muestra la corrección como exitosa

#### Scenario: EDGE — un turno cancelado permite corregir datos

- **DADO** un turno `cancelado` con datos de contacto a corregir
- **CUANDO** recepción guarda la corrección
- **ENTONCES** la corrección se aplica y el historial la registra, porque es dato de referencia y no una transición de estado

#### Scenario: Odontología no ve la edición de paciente

- **DADO** una sesión con rol odontología
- **CUANDO** se abre la ficha de un turno propio
- **ENTONCES** no se ofrece editar DNI, teléfono ni obra social; un `403` defensivo se muestra como falta de permiso

### Requirement: Marcado de asistencia con transiciones válidas

La UI SHALL ofrecer solo transiciones válidas de RN-TU-07 según estado y rol: `reservado→confirmado`; `confirmado→atendido`; y `confirmado→ausente` solo recepción/admin. Odontología SHALL limitarse a `confirmado`/`atendido` de sus turnos. Un `422` SHALL informarse y refrescar el estado. (US-008, RN-TU-07, RN-AU-01.)

#### Scenario: Un turno reservado solo ofrece confirmar

- **DADO** un turno `reservado`
- **CUANDO** se muestra su ficha
- **ENTONCES** la única acción de estado ofrecida es `confirmado`, sin `atendido` ni `ausente`

#### Scenario: Un turno confirmado ofrece atendido y, para recepción, ausente

- **DADO** un turno `confirmado`
- **CUANDO** se muestra su ficha
- **ENTONCES** se ofrecen `atendido` y, para recepción/admin, también `ausente`

#### Scenario: Transición válida actualiza el estado y las acciones

- **DADO** un turno `reservado` y una sesión de recepción
- **CUANDO** se marca `confirmado`
- **ENTONCES** el backend responde `200`, el estado visible pasa a `confirmado` y las acciones se recalculan para ese nuevo estado

#### Scenario: Estados terminales no ofrecen acciones de estado

- **DADO** un turno `atendido`, `ausente` o `cancelado`
- **CUANDO** se muestra su ficha
- **ENTONCES** no se ofrecen acciones de estado

#### Scenario: EDGE — transición inválida no se renderiza y el 422 se recupera

- **DADO** un turno `reservado` y un envío defensivo hacia `atendido` (por estado desactualizado)
- **CUANDO** el backend responde `422 transicion_invalida`
- **ENTONCES** se informa el error, se refresca la ficha y solo se vuelven a ofrecer las transiciones válidas del estado real

#### Scenario: Odontología no ve marcar ausente

- **DADO** una sesión de odontología y un turno `confirmado` propio
- **CUANDO** se muestra su ficha
- **ENTONCES** se ofrecen `atendido` y no `ausente`; un `403` defensivo se muestra como falta de permiso

#### Scenario: Turno ajeno responde 403 genérico

- **DADO** un odontólogo y un turno de otro profesional
- **CUANDO** intenta marcarlo
- **ENTONCES** se muestra un mensaje genérico de falta de permiso, sin datos del turno ni del paciente

### Requirement: Panel de notificaciones fallidas

La UI SHALL mostrar a recepción/admin el panel de `GET /api/notificaciones/fallidas` con tipo, intentos, error, fecha de envío, paciente y horario del turno, paginando por `next_cursor`. El estado vacío SHALL ser explícito y odontología SHALL NOT ver la entrada ni acceder al panel. (US-009 CA-3, RN-NO-02.)

#### Scenario: Recepción lista las fallidas con sus campos

- **DADO** notificaciones fallidas por SMTP ordenadas por inicio de turno descendente
- **CUANDO** recepción abre el panel
- **ENTONCES** se muestran tipo, intentos, error, fecha de envío, nombre y email del paciente y horario del turno en la zona del consultorio

#### Scenario: Panel vacío muestra un estado explícito

- **DADO** una respuesta con `items: []` y `next_cursor: null`
- **CUANDO** se muestra el panel
- **ENTONCES** se informa que no hay notificaciones fallidas, sin tratarlo como error

#### Scenario: Paginación con cargar más

- **DADO** una primera página con `next_cursor` no nulo
- **CUANDO** recepción pide cargar más
- **ENTONCES** se consulta el cursor y se agregan los items restantes sin duplicar los ya listados

#### Scenario: EDGE — odontología no accede al panel

- **DADO** una sesión de odontología
- **CUANDO** se muestra la navegación staff
- **ENTONCES** no aparece la entrada al panel; si accede directo a `/staff/notificaciones` y el backend responde `403`, se muestra un mensaje genérico de falta de permiso sin items

#### Scenario: 401 en el panel redirige a login

- **DADO** una sesión expirada
- **CUANDO** se carga el panel y el backend responde `401`
- **ENTONCES** se redirige a `/staff/login` sin mostrar items

#### Scenario: 400 por cursor inválido informa y reinicia

- **DADO** un cursor que el backend rechaza con `400`
- **CUANDO** se procesa la respuesta
- **ENTONCES** se informa el error, se descarta el cursor y se ofrece recargar el panel desde el inicio

#### Scenario: 429 en el panel muestra la espera

- **DADO** un `429` con `Retry-After`
- **CUANDO** se procesa la respuesta
- **ENTONCES** se muestra el mensaje de demasiados intentos con la espera indicada, sin reintento automático

### Requirement: Errores y estados de carga de las operaciones staff

Las operaciones staff SHALL deshabilitar acciones mientras están en curso y SHALL distinguir `400` por campo, `401`, `403`, `404`, `409`, `422`, `429` y errores de red o respuesta inesperada con mensajes accionables, sin exponer detalles internos ni datos de otros recursos. Los `403` staff SHALL ser genéricos y se trazan al RBAC de KB-03, no a la credencial de paciente por token (staff-auth §Semántica 401 sin sesión vs 403 sin permiso, KB-03 RBAC, RN-AU-01).

#### Scenario: Operación en curso deshabilita acciones

- **DADO** una mutación enviada y pendiente de respuesta
- **CUANDO** se muestra el formulario
- **ENTONCES** la acción de confirmar queda deshabilitada y no se permite un segundo envío

#### Scenario: 400 por campo se mapea al formulario

- **DADO** un `400` con `detail` por campo
- **CUANDO** se procesa la respuesta
- **ENTONCES** cada campo indicado queda marcado con su mensaje, se conservan los valores y no se muestra éxito

#### Scenario: Error de red no muestra éxito y permite reintentar

- **DADO** un fallo de red al crear, reprogramar, cancelar o corregir
- **CUANDO** se procesa el error
- **ENTONCES** se muestra un mensaje con reintento, se conservan los datos y la ficha o agenda no se muestran como actualizadas

#### Scenario: 403 genérico sin datos

- **DADO** un `403` en cualquier operación staff
- **CUANDO** se procesa la respuesta
- **ENTONCES** se muestra un mensaje genérico de falta de permiso, sin revelar la existencia del recurso ni datos del paciente

#### Scenario: 429 muestra la espera indicada

- **DADO** un `429` con `Retry-After`
- **CUANDO** se procesa la respuesta
- **ENTONCES** se muestra el mensaje de demasiados intentos y la espera, sin reintento automático

#### Scenario: EDGE — respuesta inesperada se trata como error

- **DADO** una respuesta que no cumple el contrato esperado
- **CUANDO** la app la detecta
- **ENTONCES** se muestra un error genérico y la operación no se marca como exitosa

### Requirement: Privacidad de datos fuera de la URL

La UI staff SHALL NOT colocar datos del paciente (nombre, DNI, teléfono, obra social ni email) en la URL ni en el historial del navegador; el detalle de turno SHALL abrirse en estado de la página. Solo identificadores opacos no sensibles podrán viajar por query si fueran necesarios. (Ley 25.326, duro 12; sin error de negocio aplicable: es una restricción estructural de la UI.)

#### Scenario: Agenda y formularios no agregan datos a la URL

- **DADO** la navegación por agenda, alta, reprogramación, cancelación y corrección
- **CUANDO** se inspecciona la ubicación del router
- **ENTONCES** la URL no contiene nombre, DNI, teléfono, obra social ni email del paciente

#### Scenario: El detalle de turno no abre una ruta con datos del paciente

- **DADO** una franja ocupada o cerrada
- **CUANDO** se abre su detalle
- **ENTONCES** el detalle se muestra en la página (panel en estado) sin navegar a una URL con datos del paciente

#### Scenario: EDGE — recargar no repuebla datos sensibles desde la URL

- **DADO** una pantalla staff con una ficha abierta
- **CUANDO** se recarga o se remonta la ruta
- **ENTONCES** no se recuperan desde la URL datos del paciente ni datos del turno

### Requirement: Mobile-first 360 y accesibilidad

Las pantallas staff SHALL usar layout fluido en CSS modules: raíz `width/max-width: 100%`, reset `box-sizing: border-box`, sin anchos en px mayores a 360 ni overflow forzado, acciones de 44px, etiquetas, errores anunciados y foco visible. La ausencia real de scroll a 360px, el foco, la tabulación y el lector de pantalla son QA manual, no automatizable en jsdom. (duro 8.)

#### Scenario: Login y agenda a 360px declaran layout fluido

- **DADO** los `*.module.css` de `/staff/login` y `/staff/agenda`
- **CUANDO** se inspeccionan sus reglas
- **ENTONCES** la raíz de cada módulo declara `width: 100%` y `max-width: 100%`, el reset global declara `box-sizing: border-box` con `overflow-x: clip`, y ningún módulo declara `width`, `min-width` ni `max-width` en px mayores a 360 (duro 8)

#### Scenario: Ficha y panel de fallidas a 360px declaran layout fluido

- **DADO** los `*.module.css` de la ficha de turno y del panel de fallidas
- **CUANDO** se inspeccionan sus reglas
- **ENTONCES** ambos módulos usan ancho disponible (`width: 100%`, `max-width: 100%`) sin anchos fijos en px mayores a 360 ni contenedores que fuercen overflow horizontal (duro 8)

#### Scenario: QA manual — viewport real de 360px sin scroll horizontal

- **DADO** un navegador real con viewport de 360×640
- **CUANDO** se recorren login, agenda, ficha y fallidas como QA manual documentada
- **ENTONCES** no aparece scroll horizontal ni solapamiento; este escenario no se automatiza en jsdom y queda registrado como checklist manual (duro 8)

#### Scenario: Acciones táctiles de tamaño mínimo

- **DADO** cualquier `*.module.css` staff
- **CUANDO** se inspeccionan las reglas de acciones
- **ENTONCES** los controles principales tienen un área táctil de al menos 44px de alto y ningún archivo declara anchos fijos mayores a 360px

#### Scenario: EDGE — etiquetas, errores anunciados y foco visible

- **DADO** un formulario staff con un error de validación
- **CUANDO** se muestra el error
- **ENTONCES** cada campo tiene etiqueta asociada, el campo inválido expone `aria-invalid` y `aria-describedby`, y el mensaje se anuncia con `role="alert"`; el foco visible con `:focus-visible`, el orden de tabulación sin `tabIndex` positivo y los anuncios del lector de pantalla se verifican en QA manual de navegador (duro 8)

### Requirement: Fechas en la zona del consultorio

La UI SHALL formatear toda fecha y hora visible (agenda, `ultima_actualizacion`, ficha, historial y fallidas) en `America/Argentina/Buenos_Aires`, independientemente de la zona del navegador, y SHALL calcular el día calendario del consultorio para la fecha inicial de la agenda. (duro 10; sin error de negocio aplicable: es una restricción estructural de la UI.)

#### Scenario: Agenda y última actualización usan la zona del consultorio

- **DADO** un navegador configurado en una zona horaria distinta de `America/Argentina/Buenos_Aires`
- **CUANDO** se muestra la agenda y la última actualización
- **ENTONCES** las horas y fechas corresponden a `America/Argentina/Buenos_Aires`

#### Scenario: Ficha, historial y fallidas usan la zona del consultorio

- **DADO** un navegador en otra zona horaria
- **CUANDO** se muestran la ficha, su historial y el panel de fallidas
- **ENTONCES** todas las fechas y horas visibles corresponden a `America/Argentina/Buenos_Aires`

#### Scenario: EDGE — la fecha inicial es el día del consultorio

- **DADO** un instante en el que el día calendario del navegador difiere del de Buenos Aires
- **CUANDO** se abre la agenda sin fecha elegida
- **ENTONCES** la fecha inicial es el día calendario de `America/Argentina/Buenos_Aires`, no el del navegador
