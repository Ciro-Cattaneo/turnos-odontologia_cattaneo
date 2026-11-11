# frontend-reserva-publica Specification

## Purpose

Define las pantallas públicas de reserva y cancelación del paciente: landing con CTA, búsqueda de disponibilidad por profesional y fecha, reserva con los cinco datos obligatorios, manejo de errores 400/404/409/422/429, cancelación por token como única vía, visualización de fechas en la zona del consultorio y experiencia mobile-first sin exponer datos sensibles.

## Requirements

### Requirement: Landing pública con CTA de reserva

La aplicación SHALL servir una landing pública en `/` con un CTA que lleve a `/reservar`, sin pedir login ni credenciales al paciente.

Justificación: la landing es el punto de entrada público del paciente; se especifica aquí para cubrir el flujo E2E de reserva y no duplicar el requisito del shell.

#### Scenario: Landing muestra CTA de reserva

- **DADO** que el paciente abre `/`
- **CUANDO** la landing termina de renderizar
- **ENTONCES** se muestra el encabezado del consultorio y un CTA de reserva que enlaza a `/reservar`

#### Scenario: Landing no exige login

- **DADO** un paciente sin sesión ni token
- **CUANDO** abre `/`
- **ENTONCES** no se le pide usuario, contraseña ni token y el CTA de reserva queda disponible

### Requirement: Búsqueda de disponibilidad por profesional y fecha

En `/reservar` la aplicación SHALL ofrecer un selector de profesional activo y una fecha, y SHALL consultar la disponibilidad pública del profesional para esa fecha. SHALL acumular todas las páginas de `GET /api/profesionales` iterando `next_cursor`.

Justificación: la búsqueda por profesional y fecha es el primer paso del flujo de reserva; los bordes de lista vacía, paginación y profesional inexistente determinan si el paciente puede reservar o no.

#### Scenario: Carga de profesionales activos

- **DADO** que el paciente abre `/reservar`
- **CUANDO** la consulta pública de profesionales responde correctamente
- **ENTONCES** el selector lista los profesionales activos devueltos por el backend

#### Scenario: Lista vacía de profesionales activos

- **DADO** que `GET /api/profesionales` responde con `items: []`
- **CUANDO** se renderiza `/reservar`
- **ENTONCES** se muestra un mensaje de que no hay profesionales disponibles y no se ofrece selector de fecha ni formulario de reserva

#### Scenario: Profesionales paginados se acumulan

- **DADO** que `GET /api/profesionales` devuelve una primera página con `next_cursor` no nulo
- **CUANDO** la aplicación carga los profesionales
- **ENTONCES** itera el `next_cursor` hasta agotarlo y el selector muestra la unión de todas las páginas

#### Scenario: Consulta por profesional y fecha

- **DADO** un profesional y una fecha elegidos
- **CUANDO** el paciente confirma la búsqueda
- **ENTONCES** la aplicación consulta la disponibilidad de ese profesional para esa fecha

#### Scenario: Fecha sin horarios muestra estado vacío

- **DADO** una fecha sin slots libres
- **CUANDO** la disponibilidad responde con lista vacía
- **ENTONCES** se muestra un estado de "sin horarios" que invita a elegir otra fecha, sin tratarlo como error

#### Scenario: Fallo de red al consultar disponibilidad

- **DADO** un fallo de red al consultar la disponibilidad
- **CUANDO** la llamada falla
- **ENTONCES** se muestra un mensaje de error con opción de reintentar y no se listan slots

#### Scenario: 404 de profesional en disponibilidad

- **DADO** un profesional que responde `404` (inexistente o inactivo) al consultar la disponibilidad
- **CUANDO** la llamada falla
- **ENTONCES** se muestra un mensaje de profesional no disponible, se invita a recargar profesionales o elegir otro, y no se listan slots

### Requirement: Lista de slots solo libres

La aplicación SHALL mostrar únicamente los slots que el backend devuelve como libres, con inicio, fin y duración, y SHALL permitir seleccionar uno para iniciar la reserva.

Justificación: el backend ya excluye ocupados y bloqueados; la UI debe confiar en ese contrato y no recalcular disponibilidad en cliente.

#### Scenario: Solo se muestran slots libres

- **DADO** una respuesta de disponibilidad con slots libres
- **CUANDO** se renderiza la lista
- **ENTONCES** no se muestran slots ocupados ni bloqueados

#### Scenario: Datos visibles por slot

- **DADO** un slot libre listado
- **CUANDO** se muestra
- **ENTONCES** indica hora de inicio, hora de fin y duración

#### Scenario: Selección de slot habilita la reserva

- **DADO** un slot listado
- **CUANDO** el paciente lo selecciona
- **ENTONCES** se abre el formulario de reserva con ese slot como elegido

### Requirement: Formulario de reserva con validación por campo

El formulario SHALL exigir nombre, DNI, teléfono, obra social y email con formato válido antes de enviar la reserva, y SHALL mostrar el detalle 400 por campo del backend. Solo los errores `paciente.*` se mapean a inputs; `inicio`/`duracion_min` se tratan como error de slot.

Justificación: el backend es la autoridad de validación; el mapeo por campo debe distinguir datos del paciente de datos del slot para conservar lo ingresado y reconsultar disponibilidad cuando corresponda.

#### Scenario: Campos faltantes se validan en cliente

- **DADO** el formulario con uno o más de los cinco campos vacíos
- **CUANDO** el paciente intenta reservar
- **ENTONCES** se marcan los campos faltantes y no se envía la reserva

#### Scenario: Mail inválido se marca solo en email

- **DADO** un mail sin formato válido y los otros cuatro campos válidos
- **CUANDO** el paciente intenta reservar
- **ENTONCES** se marca solo el campo email y no se envía la reserva

#### Scenario: 400 del backend se muestra por campo

- **DADO** un envío que el backend rechaza con 400 y `detail` con entradas `paciente.*`
- **CUANDO** la respuesta llega a la aplicación
- **ENTONCES** cada campo `paciente.*` indicado se normaliza al input correspondiente (`paciente.email` → `email`), queda marcado con su mensaje y se conserva lo ingresado

#### Scenario: 400 de inicio o duracion_min se trata como error de slot

- **DADO** un 400 cuyo `detail` incluye `inicio` o `duracion_min` (no son inputs del paciente)
- **CUANDO** la respuesta llega a la aplicación
- **ENTONCES** se muestra un error de slot, se invita a reconsultar la disponibilidad y se conservan los datos del paciente ya ingresados

#### Scenario: Un 400 no muestra el resumen de éxito

- **DADO** un 400 de validación
- **CUANDO** se renderiza el error
- **ENTONCES** no se muestra el resumen de reserva exitosa ni se pierde el slot elegido

#### Scenario: 404 de profesional al reservar

- **DADO** un `POST /api/turnos` que responde `404` porque el profesional ya no existe o está inactivo
- **CUANDO** la respuesta llega a la aplicación
- **ENTONCES** se muestra un mensaje de profesional no disponible, se invita a recargar profesionales o elegir otro, y se conservan los datos del formulario

### Requirement: Reserva exitosa muestra resumen y link de cancelación

Cuando la reserva responde 201, la aplicación SHALL mostrar un resumen del turno y un link de cancelación (token credencial, id localizador opaco) e informar el estado de las notificaciones: encoladas o no encoladas (contactar al consultorio).

Justificación: el paciente necesita confirmación del turno y una vía de cancelación; el estado de encolado de notificaciones evita prometer mails que no se enviarán.

#### Scenario: 201 muestra el resumen del turno

- **DADO** un envío válido
- **CUANDO** el backend responde 201
- **ENTONCES** se muestra profesional, fecha, hora, duración y estado de la reserva

#### Scenario: Link de cancelación con token e id

- **DADO** una respuesta 201 con token de cancelación e id del turno
- **CUANDO** se muestra el resumen
- **ENTONCES** el link de cancelación apunta a `/cancelar?token=<token>&id=<id>`, donde el token es la única credencial y el id es solo un localizador opaco

#### Scenario: Notificaciones encoladas sin aviso de "sin mail"

- **DADO** una respuesta 201 con `notificaciones_encoladas=true`
- **CUANDO** se muestra el resumen
- **ENTONCES** se informa que la confirmación y los recordatorios se enviarán por mail, sin mostrar un aviso de "sin mail"

#### Scenario: Notificaciones no encoladas informa contactar al consultorio

- **DADO** una respuesta 201 con `notificaciones_encoladas=false`
- **CUANDO** se muestra el resumen
- **ENTONCES** se informa que el turno quedó reservado pero no se pudieron encolar los mails y que el paciente debe contactar al consultorio, sin mostrar un fallback de "sin mail" ni ocultar la reserva

### Requirement: Slot ocupado concurrentemente con alternativos

Ante un 409 por slot ocupado o no disponible, la aplicación SHALL mostrar un mensaje claro y los alternativos del mismo día devueltos por el backend, y SHALL permitir elegir uno para reintentar.

Justificación: el slot puede ocuparse entre la consulta y el `POST`; los alternativos permiten recuperar el flujo sin perder los datos ya ingresados.

#### Scenario: 409 muestra los alternativos del mismo día

- **DADO** un 409 con alternativos del mismo día
- **CUANDO** se muestra la respuesta
- **ENTONCES** se listan los alternativos con inicio y fin y no se muestra el resumen de éxito

#### Scenario: Elegir alternativo reintenta con el nuevo slot

- **DADO** un alternativo listado
- **CUANDO** el paciente lo elige
- **ENTONCES** el formulario usa ese nuevo slot y conserva los datos ya ingresados

#### Scenario: 409 sin alternativos invita a otra fecha

- **DADO** un 409 sin alternativos
- **CUANDO** se muestra la respuesta
- **ENTONCES** se invita a buscar otra fecha y no se pierde lo ingresado

### Requirement: Cancelación por token como única vía

La ruta `/cancelar?token=<token>&id=<id>` SHALL ser la única forma de cancelar: SHALL pedir confirmación genérica sin datos del turno (C-06 es DELETE-only) y no ofrecer búsqueda por DNI ni teléfono. El token es la única credencial; el id no autentica. El `200` devuelve solo estado y mensaje.

Justificación: el token es la única credencial y C-06 no expone lectura previa; una confirmación genérica evita inventar un GET público.

#### Scenario: Token válido muestra confirmación genérica sin datos

- **DADO** un link `/cancelar?token=<token>&id=<id>` válido
- **CUANDO** se abre la ruta
- **ENTONCES** se muestra una confirmación genérica para cancelar (sin profesional, fecha, hora ni datos del paciente) y una acción de confirmar cancelación

#### Scenario: Cancelación exitosa muestra confirmación

- **DADO** el link de cancelación válido
- **CUANDO** el paciente confirma y el backend responde `200` con `estado` y `mensaje`
- **ENTONCES** se muestra el mensaje de éxito de la cancelación (estado/mensaje del `200`) sin datos del turno

#### Scenario: Sin token no se ofrece cancelar

- **DADO** que se abre `/cancelar` sin token
- **CUANDO** se renderiza la ruta
- **ENTONCES** se muestra un mensaje genérico y no existe formulario de DNI+teléfono ni sección "mis turnos"

#### Scenario: id ausente o malformado muestra error genérico

- **DADO** un link `/cancelar` con token pero sin `id` o con un `id` que no es un UUID válido
- **CUANDO** se renderiza la ruta
- **ENTONCES** se muestra el mismo mensaje genérico de link no válido y no se muestra ningún dato del turno

#### Scenario: Token que no corresponde al id responde 403 genérico

- **DADO** un `token` válido de un turno y un `id` que corresponde a otro turno o a ninguno
- **CUANDO** la página intenta cancelar
- **ENTONCES** se muestra un 403 genérico, sin revelar si el turno existe ni datos del paciente

#### Scenario: La credencial fallida no expone datos del turno

- **DADO** un link cuya credencial (token) no valida contra el turno indicado por el id
- **CUANDO** la página procesa la respuesta de error
- **ENTONCES** no se muestran profesional, fecha, hora ni datos del paciente, y solo aparece el mensaje genérico

#### Scenario: La URL de cancelación solo lleva token e id opaco

- **DADO** cualquier uso de `/cancelar`
- **CUANDO** se inspecciona la URL
- **ENTONCES** solo contiene los parámetros `token` e `id`, sin DNI, teléfono, obra social ni email

### Requirement: Cancelación fuera de plazo con contacto

Ante un 422 de cancelación fuera de plazo, la aplicación SHALL mostrar el mensaje del backend y el contacto del consultorio, sin ofrecer reintentar la cancelación. Para `turno_ya_cancelado` o `turno_no_cancelable` SHALL informar el estado del turno, sin mostrar contacto ni ofrecer reintento.

Justificación: el contacto solo es accionable cuando el paciente puede resolver el caso con el consultorio; para un turno ya cancelado o no cancelable no hay gestión posible.

#### Scenario: 422 fuera de plazo muestra el contacto

- **DADO** un 422 con código `cancelacion_fuera_de_plazo`
- **CUANDO** se muestra la respuesta
- **ENTONCES** aparece el mensaje y el contacto del consultorio, sin ofrecer reintentar la cancelación

#### Scenario: Turno ya cancelado o no cancelable informa el estado

- **DADO** un 422 por `turno_ya_cancelado` o `turno_no_cancelable`
- **CUANDO** se muestra la respuesta
- **ENTONCES** se informa el estado del turno, sin mostrar el contacto del consultorio ni ofrecer cancelarlo de nuevo

### Requirement: Token inválido o turno inexistente con mensaje genérico

Ante un 403 de cancelación (token inválido, turno inexistente o id malformado), la aplicación SHALL mostrar un mensaje genérico que no revele si el turno existe ni datos del paciente. Un 404 de ruta inexistente se trata con el mismo mensaje genérico.

Justificación: la respuesta de error no debe permitir enumerar turnos ni distinguir token inválido de turno inexistente; un único mensaje genérico cierra ese canal.

#### Scenario: Token inválido muestra mensaje genérico

- **DADO** un token inválido
- **CUANDO** el backend responde 403
- **ENTONCES** se muestra un mensaje genérico de link no válido, sin datos del turno

#### Scenario: Turno inexistente o malformado usa el mismo mensaje

- **DADO** un turno inexistente, un `id` malformado o una ruta que responde 404
- **CUANDO** se procesa la respuesta
- **ENTONCES** se muestra el mismo mensaje genérico que para un token inválido, sin revelar la inexistencia

### Requirement: Layout mobile-first a 360px sin overflow

Las páginas `/reservar` y `/cancelar` SHALL renderizar a 360px de ancho sin scroll horizontal ni solapamiento de acciones táctiles. Los estilos SHALL vivir en CSS modules y ningún `*.module.css` SHALL declarar anchos fijos mayores a 360px ni acciones táctiles con `min-height` menor a 44px.

Justificación: el paciente usa el celular; el contrato mobile-first del proyecto exige 360px sin overflow y targets táctiles de al menos 44px en todos los módulos.

#### Scenario: Reservar a 360px sin overflow

- **DADO** un viewport de 360×640
- **CUANDO** se renderiza `/reservar`
- **ENTONCES** el ancho de scroll del documento no supera 360px y no hay overflow horizontal

#### Scenario: Cancelar a 360px sin overflow

- **DADO** un viewport de 360×640
- **CUANDO** se renderiza `/cancelar` con un token válido
- **ENTONCES** el ancho de scroll del documento no supera 360px y no hay overflow horizontal

#### Scenario: Acciones táctiles de tamaño mínimo

- **DADO** un viewport de 360px
- **CUANDO** se muestran CTA, slots y campos
- **ENTONCES** las acciones principales tienen un área táctil de al menos 44px de alto en todos los `*.module.css`

### Requirement: Estados de carga y error tipado

La aplicación SHALL mostrar estados explícitos de carga, vacío y error; los errores de red o de respuesta inesperada SHALL mostrarse como mensajes genéricos con reintento, sin exponer detalles internos.

Justificación: distinguir carga, vacío y error evita que el paciente interprete una respuesta incompleta como éxito y permite reintentar fallos transitorios.

#### Scenario: Estado de carga durante la consulta

- **DADO** una consulta en curso
- **CUANDO** se espera la respuesta
- **ENTONCES** se muestra un indicador de carga y las acciones que dependen de datos quedan deshabilitadas

#### Scenario: Error de red con reintento

- **DADO** un fallo de red
- **CUANDO** falla la llamada
- **ENTONCES** se muestra un mensaje de error con opción de reintentar, sin stack ni detalles internos

#### Scenario: Respuesta inesperada se trata como error

- **DADO** una respuesta que no cumple el contrato esperado
- **CUANDO** la aplicación la detecta
- **ENTONCES** se muestra un error genérico y no se renderiza el flujo como si hubiera sido exitoso

### Requirement: No exposición de datos sensibles en URL

La aplicación SHALL mantener los datos del paciente fuera de la URL y del historial del navegador; las únicas excepciones son el token de cancelación y el id opaco del turno en `/cancelar?token=<token>&id=<id>`, donde el id no es credencial.

Justificación: la URL queda en historial y logs; ningún dato del paciente debe viajar por ella, y la recarga no debe recuperar datos sensibles.

#### Scenario: Reserva sin datos en la URL

- **DADO** el flujo de reserva
- **CUANDO** se navega entre búsqueda, formulario y resumen inspeccionando `router.state.location` (con `createMemoryRouter`)
- **ENTONCES** la URL no contiene nombre, DNI, teléfono, obra social ni email, y no hay query params con datos del paciente

#### Scenario: Cancelación solo con token e id opaco

- **DADO** el link de cancelación
- **CUANDO** se abre
- **ENTONCES** la URL contiene únicamente `token` e `id` como parámetros, sin datos del paciente

#### Scenario: Recarga no recupera datos sensibles

- **DADO** el resumen de una reserva exitosa
- **CUANDO** se recarga o se remonta la ruta (`createMemoryRouter` con la misma `location`)
- **ENTONCES** los datos sensibles no se recuperan desde la URL ni de la query

### Requirement: Accesibilidad básica del formulario y estados

El formulario y los estados SHALL ser operables con teclado y lectores de pantalla: etiquetas asociadas, errores anunciados y foco visible. El test automatizado cubre labels, `aria` y orden DOM; `:focus-visible` se verifica manualmente.

Justificación: sin `user-event` el foco real no es verificable en jsdom; se cubre lo automatizable (labels, aria, orden DOM) y se documenta la verificación manual del foco visible.

#### Scenario: Campos con etiqueta asociada

- **DADO** el formulario de reserva
- **CUANDO** se inspeccionan los campos
- **ENTONCES** cada campo tiene una etiqueta asociada

#### Scenario: Errores por campo anunciados

- **DADO** un error de validación por campo
- **CUANDO** se muestra
- **ENTONCES** el mensaje queda asociado al campo y es anunciado

#### Scenario: Orden DOM y foco visible (verificación manual de `:focus-visible`)

- **DADO** el formulario y sus acciones
- **CUANDO** se inspecciona el orden DOM y los atributos `aria`
- **ENTONCES** el orden es el esperado y cada control es accesible; el foco visible con `:focus-visible` se verifica manualmente en navegador

### Requirement: Rate limit con espera según Retry-After

Ante un `429` en `GET /api/profesionales`, `GET /api/disponibilidad`, `POST /api/turnos` o `DELETE /api/turnos/{id}`, la aplicación SHALL mostrar un mensaje de "demasiados intentos" y SHALL indicar la espera según `Retry-After` cuando esté presente, sin reintentar automáticamente.

Justificación: el backend aplica rate limit público; la UI debe informar la espera para que el paciente no reintente en loop y entienda cuándo volver a intentar.

#### Scenario: 429 al cargar profesionales

- **DADO** un `GET /api/profesionales` que responde `429` con `Retry-After`
- **CUANDO** se procesa la respuesta
- **ENTONCES** se muestra el mensaje de demasiados intentos y la espera indicada por `Retry-After`

#### Scenario: 429 al consultar disponibilidad

- **DADO** un `GET /api/disponibilidad` que responde `429` con `Retry-After`
- **CUANDO** se procesa la respuesta
- **ENTONCES** se muestra el mensaje de demasiados intentos y la espera indicada por `Retry-After`

#### Scenario: 429 al crear el turno

- **DADO** un `POST /api/turnos` que responde `429` con `Retry-After`
- **CUANDO** se procesa la respuesta
- **ENTONCES** se muestra el mensaje de demasiados intentos y la espera indicada por `Retry-After`, conservando los datos del formulario

#### Scenario: 429 al cancelar

- **DADO** un `DELETE /api/turnos/{id}?token=` que responde `429` con `Retry-After`
- **CUANDO** se procesa la respuesta
- **ENTONCES** se muestra el mensaje de demasiados intentos y la espera indicada por `Retry-After`

### Requirement: Visualización de fechas en zona Buenos Aires

La aplicación SHALL formatear slots, resumen y cualquier fecha visible con `timeZone: "America/Argentina/Buenos_Aires"`, independientemente de la zona horaria del navegador.

Justificación: el consultorio opera en Buenos Aires; un paciente con otra zona horaria debe ver la misma hora local que el consultorio, no la de su navegador.

#### Scenario: Slots se formatean en zona Buenos Aires con navegador en otra TZ

- **DADO** un navegador configurado en una zona horaria distinta de `America/Argentina/Buenos_Aires`
- **CUANDO** se renderizan los slots
- **ENTONCES** las horas mostradas corresponden a `America/Argentina/Buenos_Aires`

#### Scenario: Resumen se formatea en zona Buenos Aires con navegador en otra TZ

- **DADO** un navegador configurado en una zona horaria distinta de `America/Argentina/Buenos_Aires`
- **CUANDO** se muestra el resumen del 201
- **ENTONCES** la fecha y la hora del resumen corresponden a `America/Argentina/Buenos_Aires`
