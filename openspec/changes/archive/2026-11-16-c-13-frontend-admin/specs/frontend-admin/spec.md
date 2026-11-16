# Spec Delta

## Purpose

Define el comportamiento observable de las pantallas de administración del consultorio (profesionales, usuarios staff y reporte de ocupación) y de su gating por rol, para que un admin opere esas tres superficies desde el navegador sin soporte técnico, con errores de negocio accionables y mobile-first 360px.

## ADDED Requirements

### Requirement: Listado admin de profesionales con inactivos

La pantalla `/staff/admin/profesionales` SHALL listar profesionales con `GET /api/profesionales?incluir_inactivos=true` y ofrecer un control para alternar el flag, mostrando estado de carga, estado vacío explícito y el estado activo/inactivo de cada fila. (AP R4, AP R5.)

#### Scenario: FELIZ — El listado con inactivos muestra activos e inactivos distinguidos

- **DADO** una sesión `admin` y un backend que responde `200` con dos profesionales activos y uno con `activo=false`
- **CUANDO** se abre `/staff/admin/profesionales`
- **ENTONCES** se emite `GET /api/profesionales?incluir_inactivos=true`, se renderizan tres filas con `nombre`, `matricula`, `especialidad` y `duracion_default_min`, y la fila inactiva se distingue con la etiqueta "Inactivo"

#### Scenario: FELIZ — El control de inactivos alterna el flag de la consulta

- **DADO** el listado ya cargado con inactivos visibles
- **CUANDO** se desactiva el control "Incluir inactivos"
- **ENTONCES** se emite `GET /api/profesionales` sin el parámetro `incluir_inactivos` y el listado muestra solo los activos devueltos, sin recargar la página completa

#### Scenario: BORDE — Un listado vacío informa que no hay profesionales

- **DADO** una respuesta `200` con `items: []` y `next_cursor: null`
- **CUANDO** se muestra la pantalla
- **ENTONCES** se informa que no hay profesionales para el filtro elegido, no se renderiza una tabla vacía y no se trata como error

#### Scenario: ERROR — Un fallo de red conserva el filtro y permite reintentar

- **DADO** un `GET /api/profesionales` que falla por red o responde `5xx`
- **CUANDO** se procesa el error
- **ENTONCES** se muestra un mensaje con acción de reintento, el control de inactivos conserva su valor y no se inventan filas

### Requirement: Alta de profesional desde la administración

La UI SHALL crear profesionales con `POST /api/profesionales` enviando `nombre`, `matricula`, `especialidad` y `duracion_default_min` (5–240 múltiplo de 5), marcar errores por campo de un `400` y refrescar el listado al recibir `201`. (AP R1, duro 1.)

#### Scenario: FELIZ — Un alta válida crea el profesional y refresca el listado

- **DADO** una sesión `admin` y el formulario de alta con `nombre="Dra. Ficticia Uno"`, `matricula="MP-0001"`, `especialidad="Ortodoncia"` y `duracion_default_min=45`
- **CUANDO** se envía el alta
- **ENTONCES** se emite un único `POST /api/profesionales` con esos cuatro campos numérico/string, y ante `201` se anuncia la creación en una región `aria-live` y se emite un `GET` que refresca el listado

#### Scenario: BORDE — La duración se elige solo dentro de la grilla 5–240

- **DADO** el formulario de alta abierto
- **CUANDO** se inspeccionan las opciones de `duracion_default_min`
- **ENTONCES** las opciones ofrecidas son múltiplos de 5 entre 5 y 240 inclusive, el valor inicial es 30 y no existe un input libre que permita enviar `32`, `0` o `250`

#### Scenario: ERROR — Un 400 por campo marca solo el campo indicado

- **DADO** un envío de alta que el backend rechaza con `400` y `detail[]` en `campo="duracion_default_min"`
- **CUANDO** se procesa la respuesta
- **ENTONCES** solo `duracion_default_min` queda con `aria-invalid` y su mensaje, los demás valores se conservan, el foco va al primer campo con error y no se muestra confirmación de éxito

#### Scenario: ERROR — Nombre vacío no emite la solicitud

- **DADO** el formulario de alta con `nombre` vacío o solo espacios
- **CUANDO** se intenta enviar
- **ENTONCES** no se emite ningún `POST /api/profesionales`, el campo `nombre` se marca como inválido y se conserva el resto de lo ingresado (duro 1)

#### Scenario: ERROR — Un 403 de alta muestra falta de permiso sin datos

- **DADO** una sesión que el backend considera sin permiso para `POST /api/profesionales` (`403`)
- **CUANDO** se envía el alta
- **ENTONCES** se muestra el mensaje genérico "No tenés permiso para esta acción.", el formulario no se marca como exitoso y no se refresca el listado

### Requirement: Edición, baja lógica y reactivación de profesional

La UI SHALL editar un profesional con `PUT /api/profesionales/{id}`, darlo de baja con `DELETE /api/profesionales/{id}` y reactivarlo con `PUT {"activo": true}`, actualizando la fila del listado sin recargar la página. (AP R2, AP R3, AP R4, duro 3.)

#### Scenario: FELIZ — Editar nombre y duración actualiza la fila

- **DADO** un profesional listado y el formulario de edición abierto
- **CUANDO** se guarda con `nombre` y `duracion_default_min` nuevos
- **ENTONCES** se emite `PUT /api/profesionales/{id}` con solo los campos modificados y, ante `200`, la fila del listado muestra los valores nuevos

#### Scenario: FELIZ — La baja lógica deja la fila como inactiva sin eliminarla

- **DADO** un profesional activo en el listado con inactivos
- **CUANDO** se confirma la baja
- **ENTONCES** se emite `DELETE /api/profesionales/{id}` sin parámetros de borrado físico y, ante `200`, la fila sigue presente y pasa a la etiqueta "Inactivo"

#### Scenario: FELIZ — Reactivar devuelve la fila al estado activo

- **DADO** un profesional inactivo en el listado
- **CUANDO** se elige "Reactivar"
- **ENTONCES** se emite `PUT /api/profesionales/{id}` con body `{"activo": true}` y, ante `200`, la fila pasa a "Activo"

#### Scenario: ERROR — Un 404 al editar informa que el profesional no existe

- **DADO** un `PUT /api/profesionales/{id}` que responde `404`
- **CUANDO** se procesa la respuesta
- **ENTONCES** se informa que el profesional ya no está disponible, se cierra el formulario y se refresca el listado sin dejar la fila con acciones habilitadas sobre el recurso inexistente

#### Scenario: BORDE — Repetir la baja de una fila inactiva no ofrece la acción

- **DADO** un profesional con `activo=false` en el listado
- **CUANDO** se inspeccionan sus acciones
- **ENTONCES** la acción disponible es "Reactivar" y no "Dar de baja", sin emitir `DELETE` sobre una fila ya inactiva

### Requirement: Listado y alta de usuarios staff con keyset e invariante de rol

La pantalla `/staff/admin/usuarios` SHALL listar usuarios staff con `GET /api/usuarios-staff` paginando por `limit`/`next_cursor`, y crear usuarios con `POST /api/usuarios-staff` exigiendo `profesional_id` solo cuando `rol="odontologo"`. (SA R1, SA R5, duro 7.)

#### Scenario: FELIZ — La primera página y "Cargar más" usan keyset sin duplicar

- **DADO** una sesión `admin` y una primera página con `items` y `next_cursor` no nulo
- **CUANDO** se abre la pantalla y luego se elige "Cargar más"
- **ENTONCES** la primera carga emite exactamente un `GET /api/usuarios-staff?limit=20`, el click emite un `GET` con ese `next_cursor`, y los ítems se agregan sin duplicar por `id`

#### Scenario: FELIZ — El rol odontólogo exige y envía el vínculo profesional

- **DADO** el formulario de alta con `email`, `password` y `rol="odontologo"`
- **CUANDO** se envía sin elegir profesional
- **ENTONCES** no se emite `POST /api/usuarios-staff`, el selector `profesional_id` se marca como obligatorio y se indica que solo ofrece profesionales activos

#### Scenario: BORDE — Cambiar a recepción oculta y limpia el vínculo

- **DADO** el formulario de alta con `rol="odontologo"` y un `profesional_id` elegido
- **CUANDO** se cambia el rol a `recepcion`
- **ENTONCES** el selector de profesional deja de mostrarse, el vínculo se limpia y el `POST` emitido no incluye un `profesional_id` no nulo

#### Scenario: ERROR — Un 409 de email duplicado explica cómo resolverlo

- **DADO** un alta que responde `409` con `detail.codigo="email_duplicado"`
- **CUANDO** se procesa la respuesta
- **ENTONCES** se muestra un mensaje que indica que el email ya está tomado, incluso por un usuario inactivo, y que debe reactivarse la fila existente; no se muestra éxito y se conservan `email`, `rol` y vínculo

#### Scenario: ERROR — Un 400 de vínculo inválido marca solo profesional_id

- **DADO** un alta de odontólogo que responde `400` con `detail[]` en `campo="profesional_id"`
- **CUANDO** se procesa la respuesta
- **ENTONCES** solo el selector `profesional_id` queda marcado con su mensaje, los demás valores se conservan y no se muestra confirmación de éxito

### Requirement: Edición, baja y reactivación de usuarios staff con guarda de último admin

La UI SHALL editar `rol`, `profesional_id` y `activo` con `PUT /api/usuarios-staff/{id}`, dar de baja con `DELETE /api/usuarios-staff/{id}` y reactivar con `PUT {"activo": true}`, sin ofrecer edición de `email` ni `password` y mostrando `422 ultimo_admin` como error accionable. (SA R2, SA R3, SA R4.)

#### Scenario: FELIZ — Editar rol y vínculo envía solo esos campos

- **DADO** un usuario listado y el formulario de edición abierto
- **CUANDO** se cambia `rol` a `odontologo` y se elige un profesional activo
- **ENTONCES** se emite `PUT /api/usuarios-staff/{id}` con `rol` y `profesional_id`, y ante `200` la fila muestra el rol y el vínculo nuevos

#### Scenario: BORDE — Email y password no son editables en la UI

- **DADO** el formulario de edición de un usuario existente
- **CUANDO** se inspeccionan sus campos
- **ENTONCES** `email` y `password` se muestran en modo lectura (o no se muestran) y no existe ningún input que pueda incluirlos en el `PUT`

#### Scenario: ERROR — Un 422 ultimo_admin impide dejar el sistema sin admin

- **DADO** una edición o baja sobre el único admin activo que responde `422` con `detail.codigo="ultimo_admin"`
- **CUANDO** se procesa la respuesta
- **ENTONCES** se muestra un mensaje que explica que debe quedar al menos un admin activo, la fila conserva su rol y estado, no se muestra éxito y el listado no se marca como actualizado

#### Scenario: FELIZ — La baja y la reactivación actualizan la fila

- **DADO** un usuario activo en el listado
- **CUANDO** se confirma la baja y luego se elige "Reactivar"
- **ENTONCES** la baja emite `DELETE /api/usuarios-staff/{id}` y la reactivación emite `PUT /api/usuarios-staff/{id}` con `{"activo": true}`, y en cada `200` la fila cambia su etiqueta de estado sin recargar la página

#### Scenario: ERROR — Un 404 al editar cierra el formulario y refresca

- **DADO** un `PUT` o `DELETE` sobre `/api/usuarios-staff/{id}` que responde `404`
- **CUANDO** se procesa la respuesta
- **ENTONCES** se informa que el usuario ya no está disponible, se cierra el formulario y se refresca el listado sin acciones habilitadas sobre el recurso inexistente

### Requirement: Reporte de ocupación con rango, filas por profesional y totales

La pantalla `/staff/admin/reportes` SHALL consultar `GET /api/reportes/ocupacion` con `desde`/`hasta` (default últimos 30 días, tope 366) y `profesional_id` opcional, y mostrar una fila por profesional más los totales y la `zona` devueltos. (RE R1, RE R3, duro 10.)

#### Scenario: FELIZ — La carga inicial pide los últimos 30 días del consultorio

- **DADO** una sesión `admin` y el día calendario actual en `America/Argentina/Buenos_Aires`
- **CUANDO** se abre `/staff/admin/reportes`
- **ENTONCES** se emite un `GET /api/reportes/ocupacion` con `desde` = hoy − 29 días y `hasta` = hoy en formato `YYYY-MM-DD`, y se renderiza una fila por `items[]` con `turnos`, `atendidos`, `ausentes`, `cancelados`, `pendientes`, `minutos_ocupados` y el porcentaje

#### Scenario: FELIZ — El filtro por profesional acota el reporte a una fila

- **DADO** el reporte cargado con varios profesionales
- **CUANDO** se elige un profesional en el filtro y se consulta
- **ENTONCES** se emite un `GET` con `profesional_id` igual al elegido y la tabla muestra solo la fila devuelta

#### Scenario: FELIZ — Los totales y la zona quedan visibles

- **DADO** una respuesta `200` con `totales` y `zona="America/Argentina/Buenos_Aires"`
- **CUANDO** se muestra la pantalla
- **ENTONCES** un panel de totales reproduce cada contador y los minutos de `totales`, y la `zona` del consultorio aparece visible en la pantalla

#### Scenario: ERROR — Un rango de 367 días no se consulta y se marca en hasta

- **DADO** `desde` y `hasta` elegidos con `(hasta − desde).days + 1 = 367`, o con `hasta` anterior a `desde`
- **CUANDO** se intenta consultar
- **ENTONCES** no se emite el `GET`, el campo `hasta` se marca como inválido con su mensaje y el foco va a ese campo; si el backend igual responde `400` con `detail[]` en `campo="hasta"`, el error se marca en `hasta`

#### Scenario: BORDE — Un profesional_id inexistente deja la tabla vacía sin error

- **DADO** un `GET` con un `profesional_id` cuyo `items` vuelve vacío y `totales` en cero
- **CUANDO** se muestra la respuesta `200`
- **ENTONCES** se informa que no hay turnos para el rango y el profesional elegido, los totales se muestran en cero y la pantalla no se trata como error

### Requirement: Porcentaje de ocupación nulo y mayor a cien en la tabla

La UI SHALL representar `porcentaje_ocupacion=null` como "—" y los valores mayores a `100` con su valor real sin recorte, porque el backend los usa para señalar falta de capacidad o sobreasignación. (RE R2, US-011.)

#### Scenario: FELIZ — Un porcentaje nulo se muestra como guion

- **DADO** una fila con `minutos_disponibles=0` y `porcentaje_ocupacion=null`
- **CUANDO** se renderiza la tabla
- **ENTONCES** la celda de porcentaje muestra "—" y la fila conserva sus contadores y minutos visibles

#### Scenario: BORDE — Un porcentaje mayor a cien se muestra sin recortar

- **DADO** una fila con `porcentaje_ocupacion=150.0`
- **CUANDO** se renderiza la tabla
- **ENTONCES** la celda muestra "150 %" y no "100 %", sin marcar la fila como inválida

#### Scenario: BORDE — Una fila sin turnos muestra ceros

- **DADO** una fila con todos los contadores en `0` y `porcentaje_ocupacion=0.0`
- **CUANDO** se renderiza la tabla
- **ENTONCES** la fila muestra cada contador en `0` y el porcentaje "0 %", sin ocultarse ni tratarse como vacío

### Requirement: Reporte de solo lectura sin exportación en v1

La pantalla del reporte SHALL NOT ofrecer ningún control de exportación o descarga y SHALL informar de forma explícita que en v1 el reporte es solo tabla. (RE R5, PB-06.)

#### Scenario: ERROR — La pantalla no ofrece exportar

- **DADO** el reporte cargado
- **CUANDO** se inspeccionan los controles de la pantalla
- **ENTONCES** no existe botón, link ni control con texto "Exportar", "CSV", "Excel" o "Descargar", y ninguna acción emite un pedido con `format`

#### Scenario: FELIZ — El aviso de no exportación es visible

- **DADO** la pantalla del reporte renderizada
- **CUANDO** se lee su contenido
- **ENTONCES** se muestra el aviso de que en v1 el reporte es solo tabla y no hay exportación a CSV ni Excel

#### Scenario: BORDE — La respuesta JSON no dispara una descarga

- **DADO** una respuesta `200` del reporte en JSON
- **CUANDO** se procesa y renderiza
- **ENTONCES** la pantalla solo pinta la tabla y no crea ningún archivo ni enlace de descarga en el navegador

### Requirement: Estados de carga, vacío y error de las pantallas admin

Las pantallas admin SHALL distinguir carga, vacío, `400` por campo, `401`, `403`, `404`, `409`, `422`, `429` y error de red con mensajes accionables, redirigiendo a login solo ante `401`. (SA R5, RE R3, duro 1.)

#### Scenario: FELIZ — La carga se anuncia y no duplica envíos

- **DADO** una pantalla admin esperando la respuesta de su `GET` inicial o de una mutación
- **CUANDO** se muestra
- **ENTONCES** se informa el estado de carga en una región `aria-live` y la acción de enviar queda deshabilitada mientras la operación está en curso

#### Scenario: ERROR — Un 401 redirige a login sin mostrar datos

- **DADO** una sesión expirada y un `GET` o mutación que responde `401`
- **CUANDO** se procesa el error
- **ENTONCES** se descarta el estado en pantalla y se redirige a `/staff/login` sin mostrar filas ni datos de profesionales o usuarios

#### Scenario: ERROR — Un 403 muestra falta de permiso sin llamar a la API de escritura

- **DADO** un usuario con rol `recepcion` u `odontologo` que abre por URL directa una ruta `/staff/admin/*`
- **CUANDO** la pantalla resuelve su acceso
- **ENTONCES** se muestra "No tenés permiso para esta acción." sin renderizar formularios ni emitir `POST`, `PUT` o `DELETE` de administración

#### Scenario: ERROR — Un 400 por campo se mapea al formulario

- **DADO** una mutación que responde `400` con `detail[]` de `campo`/`error`/`tipo`
- **CUANDO** se procesa la respuesta
- **ENTONCES** cada campo indicado queda marcado con su mensaje, los valores se conservan, el foco va al primer campo con error y no se muestra éxito

#### Scenario: ERROR — Un 429 muestra la espera y no reintenta solo

- **DADO** una respuesta `429` con `Retry-After`
- **CUANDO** se procesa
- **ENTONCES** se muestra el mensaje de demasiados intentos con la espera indicada, sin reintento automático y con la acción disponible para reintentar manualmente

#### Scenario: ERROR — Un error de red conserva los datos y permite reintentar

- **DADO** un fallo de red al listar o al mutar
- **CUANDO** se procesa el error
- **ENTONCES** se muestra un mensaje con reintento, se conservan los filtros y valores ingresados, y nada se muestra como actualizado con éxito

### Requirement: Mobile-first 360 y accesibilidad de las pantallas admin

Las pantallas admin SHALL usar CSS modules fluidos sin overflow horizontal a 360px, tablas que degradan a tarjetas o scroll accesible, etiquetas asociadas, `aria-live` para feedback y foco visible. (duro 8.)

#### Scenario: FELIZ — Los módulos CSS declaran layout fluido

- **DADO** los `*.module.css` de las pantallas admin
- **CUANDO** se inspeccionan sus reglas
- **ENTONCES** la raíz de cada módulo declara `width: 100%` y `max-width: 100%`, y ningún módulo declara `width`, `min-width` ni `max-width` en px mayores a 360 (duro 8)

#### Scenario: BORDE — La tabla del reporte no fuerza overflow de página

- **DADO** el reporte con varias filas y columnas renderizado a 360px
- **CUANDO** se inspecciona su estructura
- **ENTONCES** las métricas se presentan en tarjetas por profesional o en un contenedor con scroll propio, y la raíz de la página no declara un ancho fijo mayor a 360

#### Scenario: FELIZ — Errores y éxito se anuncian y el foco va al primer error

- **DADO** un formulario admin con un error de validación o un mensaje de éxito
- **CUANDO** se muestra el resultado
- **ENTONCES** cada campo tiene etiqueta asociada, el campo inválido expone `aria-invalid` y `aria-describedby`, el mensaje se anuncia por `role="alert"` o `aria-live`, y el foco se mueve al primer campo inválido

#### Scenario: BORDE — Las acciones principales son táctiles

- **DADO** cualquier `*.module.css` de las pantallas admin
- **CUANDO** se inspeccionan las reglas de acciones
- **ENTONCES** los controles principales declaran un alto mínimo de 44px y ninguna acción depende de hover para ser descubierta
