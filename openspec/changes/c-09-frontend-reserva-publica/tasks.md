# Tasks — c-09-frontend-reserva-publica

> Orden TDD: primero el test rojo, después la implementación mínima, después refactor. La sección §0 es backend (pytest); el resto es frontend con Vitest + Testing Library y jsdom. Los flujos de frontend se prueban con `fetch` mockeado en el borde (`vi.stubGlobal`) y datos ficticios `.test` con DNI sintéticos (regla dura 12). No se instala ninguna dependencia. Sin commit (regla dura 11). **Ninguna tarea está tildada en este propose.**

## 0. Delta backend `cancel_url` con id (D-10 Opción A, previo al frontend)

- [x] 0.1 Escribir en rojo `test_reserva_devuelve_token_y_cancel_url_normalizada` actualizado (reserva-online MODIFIED, D-10) en `backend/tests/test_reserva_online.py:393`: `cancel_url` es exactamente `https://app.test/cancelar?token={token}&id={turno_id}` con `FRONTEND_URL="https://app.test/"` (sin doble barra, `token` primero), y el `id` del link coincide con el `id` del turno devuelto en la respuesta; correr `pytest backend/tests/test_reserva_online.py -q` y confirmar rojo — capa: backend/TDD.
- [x] 0.2 Escribir en rojo (solo rojo, sin verde) la aserción del payload de cancelación (notificaciones-mail MODIFIED) en `test_cancelacion_encola_mail_cancelacion_pendiente` (`backend/tests/test_cancelacion_paciente.py:804-805`): `payload["cancel_url"].endswith(f"/cancelar?token={turno.token_cancelacion}&id={turno.id}")`, manteniendo exactamente las **11 claves** del payload y las prohibiciones de `dni`/`telefono`/`obra_social`; el verde de este test queda para 0.5, después de la implementación 0.4 — capa: backend/TDD.
- [x] 0.3 Escribir en rojo el fixture `CANCEL_URL` de `backend/tests/test_notificaciones_templates.py:8` con `&id=<id>` (`https://turnos.ficticio.test/cancelar?token=22222222&id=<uuid>`) y el assert del cuerpo (`assert CANCEL_URL in cuerpo`, incluyendo `&id=`), y agregar aserciones de que el payload generado por `reservar()` (`backend/tests/test_notificaciones_integracion.py:65`) y por `reprogramar()` (`backend/tests/test_turnos_staff.py:2108`) incluye `cancel_url` terminado en `&id=<turno.id>` (notificaciones-mail MODIFIED, D-10) — capa: backend/TDD.
- [x] 0.4 Implementar `_cancel_url(token: uuid.UUID, turno_id: uuid.UUID)` en `backend/app/modules/turnos/service.py:285` devolviendo `f"{FRONTEND_URL.rstrip('/')}/cancelar?token={token}&id={turno_id}"`; actualizar los call sites `reservar()` (L436) y `reprogramar()` (L725) para pasar `turno.id`; en `backend/app/modules/turnos/cancellation_service.py:80` pasar `turno.id` en `_payload()` — capa: backend/implementación.
- [x] 0.5 Correr `pytest backend/tests/test_reserva_online.py backend/tests/test_cancelacion_paciente.py backend/tests/test_notificaciones_templates.py backend/tests/test_notificaciones_integracion.py backend/tests/test_turnos_staff.py -q` y confirmar verde (incluye el rojo de 0.2 y 0.3) — capa: backend/verificación.
- [x] 0.6 Correr la suite completa del backend (`pytest -q` en `backend/`) y confirmar cero regresiones, en especial `test_notificaciones_*`: los fixtures de `test_notificaciones_payload.py` usan un `cancel_url` propio con `?token=` y no dependen de `_cancel_url`, pero revisar que ningún test integre el payload generado por reserva/cancelación — capa: backend/regresión.

## 1. Cliente API tipado y guards de respuesta

- [ ] 1.1 Escribir en rojo `test_guards_aceptan_respuestas_del_contrato` y `test_guards_rechazan_respuesta_incompleta` (R11 S3) en `frontend/src/shared/api/__tests__/reserva.test.ts`: los guards `isProfesionalesResponse`, `isDisponibilidadResponse`, `isTurnoOut` e `isCancelacionOut` aceptan payloads válidos y rechazan campos faltantes o de tipo incorrecto sin usar `any`; correr `npm test -- reserva` y confirmar rojo — capa: unit/cliente.
- [ ] 1.2 Escribir en rojo `test_error_400_mapea_campos` (R4 S3), `test_error_409_expone_alternativos` (R6 S1), `test_error_422_expone_contacto` (R8 S1), `test_error_403_y_404_son_genericos` (R9 S1-S2) y `test_error_429_expone_retry_after` (R14): `ApiHttpError` transporta `detail: ApiErrorDetail` tipado, `status` correcto y `retryAfter` numérico en `429`; `403/404` no interpretan `detail` — capa: unit/cliente.
- [ ] 1.3 Implementar en `frontend/src/shared/api/client.ts` `ApiErrorDetail` (unión discriminada con `FieldError[] | { codigo, alternativos } | { codigo, mensaje, contacto? } | string | unknown`), `ApiHttpError extends ApiError` con `retryAfter?: number` y el helper `requestWithDetail<T>` sin modificar la firma de `request<T>` ni `getHealth`; crear `frontend/src/shared/api/reserva.ts` con `getProfesionales`, `getDisponibilidad`, `crearTurno`, `cancelarTurno` y los guards; verificar 1.1–1.2 verdes — capa: implementación/cliente.
- [ ] 1.4 Escribir en rojo y hacer verde `test_disponibilidad_construye_rango_dia_utc_menos_3` (R2 S4, D-5): el helper arma `desde=YYYY-MM-DDT00:00:00-03:00` y `hasta=YYYY-MM-DDT23:59:59-03:00` para la fecha elegida y envía `inicio` del slot con offset — capa: unit/cliente.
- [ ] 1.5 Escribir en rojo y hacer verde `test_cancelar_turno_usa_id_y_token` (R7 S1): `cancelarTurno(id, token)` arma `DELETE /api/turnos/{id}?token=<token>` con el token codificado y no agrega parámetros extra — capa: unit/cliente.
- [ ] 1.6 Escribir en rojo y hacer verde `test_get_profesionales_itera_next_cursor_dos_paginas` (R2 S3): `getProfesionales()` sigue el `next_cursor` y acumula los `items` de dos páginas hasta que `next_cursor` es nulo — capa: unit/cliente.

## 2. Componentes de búsqueda y slots

- [ ] 2.1 Escribir en rojo y hacer verde `test_selector_profesionales_lista_solo_activos` (R2 S1) y `test_profesionales_vacio_muestra_mensaje_sin_formulario` (R2 S2): el selector renderiza los `items` y permite elegir uno; con `items: []` muestra el mensaje de "no hay profesionales disponibles" y no ofrece fecha ni formulario — capa: unit/componente.
- [ ] 2.2 Escribir en rojo y hacer verde `test_disponibilidad_muestra_carga_y_deshabilita_acciones` (R11 S1), `test_disponibilidad_error_de_red_muestra_reintento` (R2 S6, R11 S2), `test_disponibilidad_404_profesional_invita_recargar` (R2 S7) y `test_disponibilidad_429_muestra_espera` (R14) sobre el hook/estado de la búsqueda — capa: unit/componente.
- [ ] 2.3 Escribir en rojo y hacer verde `test_disponibilidad_sin_slots_muestra_estado_vacio` (R2 S5): lista vacía se muestra como "sin horarios", no como error — capa: unit/componente.
- [ ] 2.4 Escribir en rojo y hacer verde `test_slots_muestra_solo_libres_con_inicio_fin_duracion` (R3 S1-S2): se renderizan solo los `slots` del contrato con inicio, fin y duración — capa: unit/componente.
- [ ] 2.5 Escribir en rojo y hacer verde `test_seleccionar_slot_habilita_formulario` (R3 S3): al elegir un slot se abre el formulario con ese slot como elegido — capa: unit/componente.

## 3. Formulario de reserva y resumen

- [ ] 3.1 Escribir en rojo y hacer verde `test_formulario_campos_faltantes_no_envia` (R4 S1) y `test_formulario_mail_invalido_marca_solo_email` (R4 S2): validación local de los cinco campos con trim y patrón `/.+@.+\..+/` — capa: unit/componente.
- [ ] 3.2 Escribir en rojo y hacer verde `test_formulario_400_marca_campos_y_conserva_valores` (R4 S3), `test_formulario_400_inicio_duracion_es_error_slot` (R4 S4) y `test_formulario_400_no_muestra_resumen` (R4 S5): mapea solo `detail[].campo` con prefijo `paciente.*` (`paciente.email` → `email`), trata `inicio`/`duracion_min` como error de slot invitando a reconsultar disponibilidad, y mantiene el slot y los datos elegidos — capa: unit/componente.
- [ ] 3.3 Escribir en rojo y hacer verde `test_resumen_201_muestra_turno_y_link` (R5 S1-S2): muestra profesional, fecha, hora, duración, estado y link `/cancelar?token=<token>&id=<id>` (token como credencial, id como localizador opaco) — capa: unit/componente.
- [ ] 3.4 Escribir en rojo y hacer verde `test_resumen_201_notificaciones_encoladas_parametrizado` con `it.each([true, false])` (R5 S3-S4): `true` informa confirmación/recordatorios por mail sin aviso de "sin mail"; `false` informa turno reservado + "no se pudieron encolar los mails, contactá al consultorio", sin fallback de "sin mail" — capa: unit/componente.
- [ ] 3.5 Escribir en rojo y hacer verde `test_409_muestra_alternativos_y_conserva_datos` (R6 S1-S3): lista alternativos del mismo día, permite elegir uno y conserva los datos del formulario; sin alternativos invita a otra fecha — capa: unit/componente.
- [ ] 3.6 Escribir en rojo y hacer verde `test_slots_y_resumen_se_formatean_en_zona_buenos_aires` (R15 S1-S2): con el navegador en una TZ distinta de `America/Argentina/Buenos_Aires`, slots y resumen se formatean con `timeZone: "America/Argentina/Buenos_Aires"` — capa: unit/componente.

## 4. Página `/reservar` e integración de flujos

- [ ] 4.1 Escribir en rojo y hacer verde `test_reserva_feliz_201` (R2/R3/R5) en `frontend/src/pages/__tests__/reserva.test.tsx` con `createMemoryRouter` y `fetch` mockeado en secuencia (`/api/profesionales` → `/api/disponibilidad` → `/api/turnos`) — capa: integración.
- [ ] 4.2 Escribir en rojo y hacer verde `test_reserva_400_por_campo` (R4) y `test_reserva_409_con_alternativos` (R6) con respuestas HTTP reales simuladas en el borde — capa: integración.
- [ ] 4.3 Escribir en rojo y hacer verde `test_reserva_error_de_red_con_reintento`, `test_reserva_respuesta_inesperada_es_error` (R11 S2-S3), `test_reserva_404_profesional_conserva_formulario` (R4 S6) y `test_reserva_429_post_turnos_muestra_espera` (R14) — capa: integración.
- [ ] 4.4 Escribir en rojo y hacer verde `test_reserva_no_expone_datos_en_url` (R12 S1, S3): usar `createMemoryRouter` e inspeccionar `router.state.location` (no `MemoryRouter` plano); tras búsqueda, formulario y resumen la `location` no contiene nombre, DNI, teléfono, obra social ni email y no hay query con datos del paciente; agregar un caso de recarga/remontaje con la misma `location` y aserción de que no se recuperan datos — capa: integración.
- [ ] 4.5 Escribir en rojo y hacer verde `test_landing_cta_navega_a_reservar` y `test_landing_no_pide_login` (R1 S1-S2) reutilizando la Home existente — capa: integración.

## 5. Routing y delta del shell

- [ ] 5.1 Registrar `/reservar` y `/cancelar` en `frontend/src/App.tsx` y escribir en rojo/verde `test_ruta_reservar_renderiza_pagina` y `test_ruta_cancelar_renderiza_pagina` (frontend-shell MODIFIED) sin romper `/` ni `*` — capa: integración/routing.
- [ ] 5.2 Correr `npm test -- shell` y confirmar que S1 (landing con CTA), S2 (not-found), S3 (360 sin overflow) y S4 (error tipado) siguen verdes — capa: regresión.

## 6. Página `/cancelar`

> Orden TDD: primero todos los rojos (6.1–6.9), después la implementación única (6.10). No hay un paso de implementación antes de los rojos.

- [ ] 6.1 Escribir en rojo `test_cancelar_token_valido_muestra_confirmacion_generica_sin_datos` (R7 S1) con `fetch` mockeado para el `DELETE /api/turnos/{id}?token=` acordado en §0: la confirmación es genérica y no muestra profesional, fecha, hora ni datos del paciente — capa: integración.
- [ ] 6.2 Escribir en rojo `test_cancelar_confirmacion_200_muestra_exito` (R7 S2): el `200` con `estado`/`mensaje` se muestra como éxito de cancelación, sin datos del turno — capa: integración.
- [ ] 6.3 Escribir en rojo `test_cancelar_sin_token_muestra_generico_sin_formulario_dni` (R7 S3): no hay formulario DNI+teléfono ni sección "mis turnos" — capa: integración.
- [ ] 6.4 Escribir en rojo `test_cancelar_url_solo_token_e_id_sin_datos_paciente` (R7 S7, R12 S2): la URL tiene únicamente `token` e `id`, sin DNI, teléfono, obra social ni email — capa: integración.
- [ ] 6.5 Escribir en rojo `test_cancelar_422_fuera_de_plazo_muestra_contacto` (R8 S1) y `test_cancelar_422_turno_ya_cancelado_sin_contacto_ni_reintento` (R8 S2): fuera de plazo muestra `mensaje` + `contacto`; ya cancelado/no cancelable informa el estado sin contacto ni reintento — capa: integración.
- [ ] 6.6 Escribir en rojo `test_cancelar_403_y_404_muestran_mismo_generico` (R9 S1-S2): token inválido, turno inexistente, id malformado (403) y ruta inexistente (404) muestran el mismo genérico, sin datos del turno — capa: integración.
- [ ] 6.7 Escribir en rojo `test_cancelar_id_ausente_o_malformado_muestra_generico` (R7 S4): sin `id` o con `id` no-UUID se muestra el mensaje genérico y no se llama al backend — capa: integración.
- [ ] 6.8 Escribir en rojo `test_cancelar_token_no_corresponde_al_id_403_generico` (R7 S5-S6): un token válido con el `id` de otro turno (o inexistente) produce 403 genérico y la página no renderiza profesional, fecha, hora ni datos del paciente — capa: integración.
- [ ] 6.9 Escribir en rojo `test_cancelar_429_muestra_espera_retry_after` (R14): un `DELETE` que responde `429` con `Retry-After` muestra "demasiados intentos" y la espera — capa: integración.
- [ ] 6.10 Implementar `/cancelar` (lectura de `token` e `id`, confirmación genérica, llamada a `DELETE /api/turnos/{id}?token=`, manejo 200/403/404/422/429) y hacer verdes 6.1–6.9 — capa: implementación/integración.

## 7. Estilos CSS modules, accesibilidad y mobile-first

- [ ] 7.1 Crear tokens y reset en `frontend/src/styles.css` (`:root` con colores, espaciado, radios y `:focus-visible`) y los primeros `*.module.css` de páginas/componentes; verificación: `npm run build` compila los módulos y el test del shell sigue leyendo el contrato global — capa: estilos.
- [ ] 7.2 Escribir en rojo y hacer verde `test_formulario_campos_con_etiqueta` (R13 S1), `test_formulario_errores_anunciados` (R13 S2) y `test_formulario_orden_dom_y_aria` (R13 S3): labels, `aria-invalid`/`aria-describedby`, `role="alert"` y orden DOM; el test NO verifica `:focus-visible` (no se instala `user-event`), y se documenta la verificación manual de foco visible en navegador — capa: accesibilidad/componente.
- [ ] 7.3 Escribir en rojo y hacer verde `test_reservar_360_sin_overflow`, `test_cancelar_360_sin_overflow` (R10 S1-S2) y `test_acciones_tactiles_minimo_44` (R10 S3): replicar el enfoque de `shell.test.tsx` (scrollWidth), **escanear todos los `*.module.css`** para rechazar anchos fijos >360 y `min-height` <44px (no solo `styles.css`), y documentar la cobertura manual de solapamiento de acciones — capa: responsive.

## 8. Verificación final e integración

- [ ] 8.1 Correr `npm test` en `frontend/` y confirmar toda la suite verde (nuevos tests y shell sin regresiones) — capa: proceso.
- [ ] 8.2 Correr `npx tsc -b` en `frontend/` y confirmar cero errores de tipos; además verificar la ausencia de `any` con `rg -n "\bany\b" frontend/src --glob '!**/node_modules/**'` (o script equivalente que falle si aparece `any` en archivos nuevos), porque `tsc -b` solo no lo garantiza — capa: proceso.
- [ ] 8.3 Correr `npm run build` en `frontend/` y confirmar build exitoso — capa: proceso.
- [ ] 8.4 Revisar `git status --short` y `git diff --stat`: deben aparecer archivos bajo `frontend/src/`, `openspec/changes/c-09-frontend-reserva-publica/` y el delta backend mínimo (`backend/app/modules/turnos/service.py`, `backend/app/modules/turnos/cancellation_service.py`, `backend/tests/test_reserva_online.py`, `backend/tests/test_cancelacion_paciente.py`, `backend/tests/test_notificaciones_templates.py`, `backend/tests/test_notificaciones_integracion.py`, `backend/tests/test_turnos_staff.py`); sin cambios en `openspec/specs/`, `CHANGES.md`, `AGENTS.md` ni `CLAUDE.md` — capa: alcance.
- [ ] 8.5 Correr `openspec validate c-09-frontend-reserva-publica --strict` y `openspec status --change c-09-frontend-reserva-publica --json`; confirmar planificación completa — capa: proceso.
- [ ] 8.6 Objetivo de performance <2s de primera carga: **nota no funcional**; se mide manualmente en navegador y no bloquea CI (no hay Lighthouse/Playwright en el proyecto). Registrar la medición en el apply, sin agregar dependencias — capa: proceso.

## Trazabilidad escenario → tarea

| Requisito | Escenario | Tarea | Test propuesto | Capa |
|---|---|---|---|---|
| R1 | Landing muestra CTA de reserva | 4.5 | `test_landing_cta_navega_a_reservar` | integración |
| R1 | Landing no exige login | 4.5 | `test_landing_no_pide_login` | integración |
| R2 | Carga de profesionales activos | 2.1 | `test_selector_profesionales_lista_solo_activos` | unit/componente |
| R2 | Lista vacía de profesionales activos | 2.1 | `test_profesionales_vacio_muestra_mensaje_sin_formulario` | unit/componente |
| R2 | Profesionales paginados se acumulan | 1.6 | `test_get_profesionales_itera_next_cursor_dos_paginas` | unit/cliente |
| R2 | Consulta por profesional y fecha | 1.4, 2.2 | `test_disponibilidad_construye_rango_dia_utc_menos_3` | unit/cliente |
| R2 | Fecha sin horarios muestra estado vacío | 2.3 | `test_disponibilidad_sin_slots_muestra_estado_vacio` | unit/componente |
| R2 | Fallo de red al consultar disponibilidad | 2.2 | `test_disponibilidad_error_de_red_muestra_reintento` | unit/componente |
| R2 | 404 de profesional en disponibilidad | 2.2 | `test_disponibilidad_404_profesional_invita_recargar` | unit/componente |
| R3 | Solo se muestran slots libres | 2.4 | `test_slots_muestra_solo_libres_con_inicio_fin_duracion` | unit/componente |
| R3 | Datos visibles por slot | 2.4 | `test_slots_muestra_solo_libres_con_inicio_fin_duracion` | unit/componente |
| R3 | Selección de slot habilita la reserva | 2.5 | `test_seleccionar_slot_habilita_formulario` | unit/componente |
| R4 | Campos faltantes se validan en cliente | 3.1 | `test_formulario_campos_faltantes_no_envia` | unit/componente |
| R4 | Mail inválido se marca solo en email | 3.1 | `test_formulario_mail_invalido_marca_solo_email` | unit/componente |
| R4 | 400 del backend se muestra por campo | 1.2, 3.2 | `test_formulario_400_marca_campos_y_conserva_valores` | unit/componente |
| R4 | 400 de inicio o duracion_min se trata como error de slot | 3.2 | `test_formulario_400_inicio_duracion_es_error_slot` | unit/componente |
| R4 | Un 400 no muestra el resumen de éxito | 3.2 | `test_formulario_400_no_muestra_resumen` | unit/componente |
| R4 | 404 de profesional al reservar | 4.3 | `test_reserva_404_profesional_conserva_formulario` | integración |
| R5 | 201 muestra el resumen del turno | 3.3 | `test_resumen_201_muestra_turno_y_link` | unit/componente |
| R5 | Link de cancelación con token e id | 3.3 | `test_resumen_201_muestra_turno_y_link` | unit/componente |
| R5 | Notificaciones encoladas sin aviso de "sin mail" | 3.4 | `test_resumen_201_notificaciones_encoladas_parametrizado` (`true`) | unit/componente |
| R5 | Notificaciones no encoladas informa contactar al consultorio | 3.4 | `test_resumen_201_notificaciones_encoladas_parametrizado` (`false`) | unit/componente |
| R6 | 409 muestra los alternativos del mismo día | 1.2, 3.5 | `test_409_muestra_alternativos_y_conserva_datos` | unit/componente |
| R6 | Elegir alternativo reintenta con el nuevo slot | 3.5 | `test_409_muestra_alternativos_y_conserva_datos` | unit/componente |
| R6 | 409 sin alternativos invita a otra fecha | 3.5 | `test_409_muestra_alternativos_y_conserva_datos` | unit/componente |
| R7 | Token válido muestra confirmación genérica sin datos | 6.1, 6.10 | `test_cancelar_token_valido_muestra_confirmacion_generica_sin_datos` | integración |
| R7 | Cancelación exitosa muestra confirmación | 6.2, 6.10 | `test_cancelar_confirmacion_200_muestra_exito` | integración |
| R7 | Sin token no se ofrece cancelar | 6.3, 6.10 | `test_cancelar_sin_token_muestra_generico_sin_formulario_dni` | integración |
| R7 | La URL de cancelación solo lleva token e id opaco | 6.4, 6.10 | `test_cancelar_url_solo_token_e_id_sin_datos_paciente` | integración |
| R7 | id ausente o malformado muestra error genérico | 6.7, 6.10 | `test_cancelar_id_ausente_o_malformado_muestra_generico` | integración |
| R7 | Token que no corresponde al id responde 403 genérico | 6.8, 6.10 | `test_cancelar_token_no_corresponde_al_id_403_generico` | integración |
| R7 | La credencial fallida no expone datos del turno | 6.8, 6.10 | `test_cancelar_token_no_corresponde_al_id_403_generico` | integración |
| R8 | 422 fuera de plazo muestra el contacto | 1.2, 6.5 | `test_cancelar_422_fuera_de_plazo_muestra_contacto` | integración |
| R8 | Turno ya cancelado o no cancelable informa el estado | 6.5 | `test_cancelar_422_turno_ya_cancelado_sin_contacto_ni_reintento` | integración |
| R9 | Token inválido muestra mensaje genérico | 1.2, 6.6 | `test_cancelar_403_y_404_muestran_mismo_generico` | integración |
| R9 | Turno inexistente o malformado usa el mismo mensaje | 6.6 | `test_cancelar_403_y_404_muestran_mismo_generico` | integración |
| R10 | Reservar a 360px sin overflow | 7.3 | `test_reservar_360_sin_overflow` | responsive |
| R10 | Cancelar a 360px sin overflow | 7.3 | `test_cancelar_360_sin_overflow` | responsive |
| R10 | Acciones táctiles de tamaño mínimo | 7.3 | `test_acciones_tactiles_minimo_44` | responsive |
| R11 | Estado de carga durante la consulta | 2.2 | `test_disponibilidad_muestra_carga_y_deshabilita_acciones` | unit/componente |
| R11 | Error de red con reintento | 2.2, 4.3 | `test_reserva_error_de_red_con_reintento` | integración |
| R11 | Respuesta inesperada se trata como error | 1.1, 4.3 | `test_reserva_respuesta_inesperada_es_error` | integración |
| R12 | Reserva sin datos en la URL | 4.4 | `test_reserva_no_expone_datos_en_url` | integración |
| R12 | Cancelación solo con token e id opaco | 6.4 | `test_cancelar_url_solo_token_e_id_sin_datos_paciente` | integración |
| R12 | Recarga no recupera datos sensibles | 4.4 | `test_reserva_no_expone_datos_en_url` (caso remontaje) | integración |
| R13 | Campos con etiqueta asociada | 7.2 | `test_formulario_campos_con_etiqueta` | accesibilidad |
| R13 | Errores por campo anunciados | 7.2 | `test_formulario_errores_anunciados` | accesibilidad |
| R13 | Orden DOM y foco visible (manual `:focus-visible`) | 7.2 | `test_formulario_orden_dom_y_aria` | accesibilidad |
| R14 | 429 al cargar profesionales | 1.2, 2.2 | `test_error_429_expone_retry_after` / `test_disponibilidad_429_muestra_espera` | unit |
| R14 | 429 al consultar disponibilidad | 2.2 | `test_disponibilidad_429_muestra_espera` | unit/componente |
| R14 | 429 al crear el turno | 4.3 | `test_reserva_429_post_turnos_muestra_espera` | integración |
| R14 | 429 al cancelar | 6.9 | `test_cancelar_429_muestra_espera_retry_after` | integración |
| R15 | Slots se formatean en zona Buenos Aires con navegador en otra TZ | 3.6 | `test_slots_y_resumen_se_formatean_en_zona_buenos_aires` | unit/componente |
| R15 | Resumen se formatea en zona Buenos Aires con navegador en otra TZ | 3.6 | `test_slots_y_resumen_se_formatean_en_zona_buenos_aires` | unit/componente |
| reserva-online MODIFIED | Reserva devuelve token y link de cancelación normalizado | 0.1, 0.4 | `test_reserva_devuelve_token_y_cancel_url_normalizada` | backend |
| reserva-online MODIFIED | El id del link de cancelación coincide con el id del turno | 0.1 | `test_reserva_devuelve_token_y_cancel_url_normalizada` | backend |
| notificaciones-mail MODIFIED | Mail de recordatorio incluye link y hora local | 0.3 | `test_plantilla_recordatorio_incluye_profesional_y_link` (fixture `CANCEL_URL` con `&id=`) | backend |
| notificaciones-mail MODIFIED | Mail no incluye datos sensibles innecesarios | 0.3 | `test_plantilla_no_incluye_dni_telefono_ni_obra_social` | backend |
| notificaciones-mail MODIFIED | Payload de cancelación con `&id=` | 0.2 | `test_cancelacion_encola_mail_cancelacion_pendiente` | backend |
| notificaciones-mail MODIFIED | Payload generado por reserva/reprogramación con `&id=` | 0.3 | `test_notificaciones_integracion.py` / `test_turnos_staff.py` | backend |
| shell MODIFIED | Reservation route resolves to the reservation page | 5.1 | `test_ruta_reservar_renderiza_pagina` | routing |
| shell MODIFIED | Cancellation route resolves to the cancellation page | 5.1 | `test_ruta_cancelar_renderiza_pagina` | routing |
| shell S1-S4 | Landing con CTA / not-found / 360 / error tipado | 5.2 | `npm test -- shell` | regresión |

## Workflow follow-up

- Ejecutar `/opsx:apply c-09-frontend-reserva-publica` recién con una orden nueva; este propose no implementa código.
- D-10 resuelta (Opción A): el `cancel_url` incluye el `id` opaco del turno y el token sigue siendo la única credencial; implementar §0 (delta backend) antes de las tareas de la página `/cancelar` (6.x).
- La página `/cancelar` no muestra datos antes de cancelar (C-06 es DELETE-only) y el `200` solo devuelve estado/mensaje.
- Pasar `turno-spec-review` sobre los artefactos antes del apply.
- Después de que la suite esté verde, ejecutar `/opsx:archive c-09-frontend-reserva-publica` y marcar C-09 como completado en `CHANGES.md` (fuera de este paso).
- No commitear ni pushear hasta que el usuario lo pida explícitamente.
