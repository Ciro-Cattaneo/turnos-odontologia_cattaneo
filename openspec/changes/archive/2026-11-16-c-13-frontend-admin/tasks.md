# Tasks — c-13-frontend-admin

> Orden TDD: **primero el test en rojo**, después la implementación mínima, después refactor. Todos los tests son de **frontend** (`frontend/`) con Vitest + Testing Library, `fetch` mockeado en el borde (`vi.stubGlobal("fetch", ...)`) y router en memoria con `appRoutes`; no hay mocks internos (duro 9). Datos ficticios: emails `@cattaneo.test`, nombres "Ficticio", matrículas `MP-0001`, DNI sintéticos; nunca datos reales (duro 12). Sin `any`, sin componentes anidados, sin barrels, mobile-first 360px (duro 8). **NO commit, NO push, NO `git add`** (duro 11). Ninguna tarea está tildada en este propose.
>
> **Backend: sin cambios.** No hay endpoints, schemas, servicios, migraciones ni cambios en `openspec/specs/` (los deltas de `frontend-admin` y `frontend-shell` viven dentro de este change).
>
> Cada tarea funcional cita el escenario que cubre: `FA` = `specs/frontend-admin`, `FS` = `specs/frontend-shell`. La sección 8 es de verificación y cierre y no mapea a un escenario funcional.

## 1. Shell, rutas admin y gating por rol

- [x] 1.1 Escribir en rojo `test_ruta_admin_profesionales_con_admin_resuelve_en_layout`, `test_ruta_admin_usuarios_con_admin_resuelve_en_layout` y `test_ruta_admin_reportes_con_admin_resuelve_en_layout` en `frontend/src/features/staff/__tests__/rutas.test.tsx` (parametrizado por path y componente esperado); luego agregar los tres `children` bajo `path: "/staff"` en `frontend/src/App.tsx` y crear páginas placeholder mínimas hasta verde — cubre FS "FELIZ — La pantalla de profesionales/usuarios/reportes resuelve bajo el layout protegido" — capa: integración/router.
- [x] 1.2 Escribir en rojo `test_nav_admin_visible_solo_para_admin` (parametrizado `admin` → 3 entradas, `recepcion`/`odontologo` → 0 entradas) en `frontend/src/features/staff/__tests__/layout.test.tsx`; agregar al bloque de navegación de `StaffLayout.tsx` las entradas `Profesionales`, `Usuarios staff` y `Reportes` bajo `sesion.rol === "admin"` hasta verde — cubre FS "EDGE — La navegación admin se oculta a recepción y odontología" — capa: integración.
- [x] 1.3 Escribir en rojo `test_acceso_directo_admin_con_recepcion_muestra_403_sin_romper_layout` y `test_acceso_directo_admin_con_odontologo_muestra_403_sin_romper_layout` (parametrizado, verificando que la ruta no cae en not-found y que no se emite el `GET` de administración); implementar el gating por sesión en cada página admin hasta verde — cubre FS "EDGE — Un acceso directo admin de otro rol muestra falta de permiso sin romper el layout" y FA "ERROR — Un 403 muestra falta de permiso sin llamar a la API de escritura" — capa: integración.
- [x] 1.4 Escribir en rojo `test_ruta_admin_sin_sesion_redirige_a_login` (parametrizado por los tres paths; `GET /api/auth/me` → `401`); verificar que el redirect a `/staff/login` se mantiene y que las rutas públicas siguen públicas — cubre FS "EDGE — staff route without session redirects to login" (no regresión) — capa: integración.
- [x] 1.5 Crear `frontend/src/features/staff/admin/useSesionAdmin.ts` (helper de pantalla: `{ esAdmin, sesion, expirarSesion }`, sin componente) y refactorizar las tres páginas para usarlo; verificar con los tests de 1.1–1.4 en verde — cubre FS rutas admin y FA "Estados de carga, vacío y error" — capa: unit/integración.

## 2. Cliente API admin tipado

- [x] 2.1 Escribir en rojo `test_profesionales_admin_page_guard_acepta_items_con_activo`, `test_profesionales_admin_page_guard_rechaza_item_sin_activo` y `test_profesionales_admin_page_guard_rechaza_next_cursor_invalido` en `frontend/src/shared/api/__tests__/adminapi.test.ts`; crear `frontend/src/shared/api/admin.ts` con `ProfesionalAdmin`, `ProfesionalesAdminPage` e `isProfesionalesAdminPage` hasta verde — cubre FA "Listado admin de profesionales con inactivos" (contrato) — capa: unit/schemas.
- [x] 2.2 Escribir en rojo `test_usuarios_staff_page_guard_acepta_activo_e_inactivo` y `test_usuarios_staff_page_guard_rechaza_item_sin_rol`; agregar `UsuarioStaff`, `UsuariosStaffPage` e `isUsuariosStaffPage` (sin `password_hash`) — cubre FA "Listado y alta de usuarios staff" (contrato) — capa: unit/schemas.
- [x] 2.3 Escribir en rojo `test_reporte_ocupacion_guard_acepta_porcentaje_null` y `test_reporte_ocupacion_guard_rechaza_totales_incompletos`; agregar `ReporteOcupacion`, `ReporteFila`, `ReporteTotales` e `isReporteOcupacion` — cubre FA "Reporte de ocupación con rango, filas y totales" (contrato) y "Porcentaje nulo y mayor a cien" — capa: unit/schemas.
- [x] 2.4 Escribir en rojo `test_listar_profesionales_admin_envia_incluir_inactivos` y `test_listar_profesionales_admin_sin_flag_no_envia_parametro` (aserciones sobre la URL de `fetch`); implementar `listarProfesionalesAdmin`, `crearProfesional`, `actualizarProfesional` y `darDeBajaProfesional` con `requestWithDetail` y `credentials: "include"` — cubre FA "Listado admin de profesionales" y "Edición, baja lógica y reactivación" (requests emitidos) — capa: unit/cliente.
- [x] 2.5 Escribir en rojo `test_listar_usuarios_staff_envia_limit_y_cursor` y `test_crear_usuario_staff_omite_profesional_id_nulo`; implementar `listarUsuariosStaff`, `crearUsuarioStaff`, `actualizarUsuarioStaff` y `darDeBajaUsuarioStaff` — cubre FA "Listado y alta de usuarios staff" y "Edición, baja y reactivación" (requests emitidos) — capa: unit/cliente.
- [x] 2.6 Escribir en rojo `test_get_reporte_ocupacion_compone_query_con_profesional_id` y `test_get_reporte_ocupacion_sin_filtro_no_envia_profesional_id`; implementar `getReporteOcupacion` sin parámetro `format` — cubre FA "Reporte de ocupación" y "Reporte de solo lectura sin exportación" (`format` nunca se emite) — capa: unit/cliente.
- [x] 2.7 Escribir en rojo `test_mensaje_de_error_409_email_duplicado_especifico`, `test_mensaje_de_error_422_ultimo_admin_accionable` y `test_mensaje_de_error_422_profesional_id_mapea_campo` en `frontend/src/shared/api/__tests__/errores.test.ts`; extender `shared/api/errores.ts` con los códigos `email_duplicado` y `ultimo_admin` sin cambiar su firma pública, hasta verde — cubre FA "ERROR — Un 409 de email duplicado" y "ERROR — Un 422 ultimo_admin" — capa: unit.

## 3. Administración de profesionales

- [x] 3.1 Escribir en rojo `test_profesionales_listado_muestra_activos_e_inactivos` (2 activos + 1 inactivo → 3 filas y etiqueta "Inactivo") en `frontend/src/features/staff/admin/__tests__/profesionales.test.tsx`; crear `hooks/useProfesionalesAdmin.ts`, la página y la lista hasta verde — cubre FA "FELIZ — El listado con inactivos muestra activos e inactivos distinguidos" — capa: integración.
- [x] 3.2 Escribir en rojo `test_toggle_incluir_inactivos_cambia_la_consulta` (on → `incluir_inactivos=true`, off → sin parámetro, sin recarga de página); implementar el control y el estado del flag — cubre FA "FELIZ — El control de inactivos alterna el flag de la consulta" — capa: integración.
- [x] 3.3 Escribir en rojo `test_profesionales_listado_vacio_informa_sin_error` (`items: []` → texto explícito, sin `role="alert"`); implementar el estado vacío — cubre FA "BORDE — Un listado vacío informa que no hay profesionales" — capa: integración.
- [x] 3.4 Escribir en rojo `test_profesionales_error_de_red_conserva_filtro_y_permite_reintentar`; implementar el estado de error con reintento conservando el flag — cubre FA "ERROR — Un fallo de red conserva el filtro y permite reintentar" — capa: integración.
- [x] 3.5 Escribir en rojo `test_alta_profesional_valida_emite_post_y_refresca_listado` (un único `POST` con `nombre`/`matricula`/`especialidad`/`duracion_default_min=45`, feedback en `aria-live` y `GET` posterior); crear `AltaProfesionalForm.tsx` y conectarlo hasta verde — cubre FA "FELIZ — Un alta válida crea el profesional y refresca el listado" — capa: integración.
- [x] 3.6 Escribir en rojo `test_alta_profesional_duracion_solo_ofrece_grilla_5_240` (select con múltiplos de 5, default 30, sin input libre); implementar el campo de duración desde la grilla — cubre FA "BORDE — La duración se elige solo dentro de la grilla 5–240" — capa: integración.
- [x] 3.7 Escribir en rojo `test_alta_profesional_400_marca_solo_duracion_y_conserva_valores` (incluye foco en el primer error y `aria-invalid`) y `test_alta_profesional_nombre_vacio_no_emite_post`; implementar el mapeo `detail[]` → campo y la validación local mínima — cubre FA "ERROR — Un 400 por campo marca solo el campo indicado" y "ERROR — Nombre vacío no emite la solicitud" — capa: integración.
- [x] 3.8 Escribir en rojo `test_alta_profesional_403_muestra_falta_de_permiso_sin_refrescar`; implementar el `403` genérico en el formulario — cubre FA "ERROR — Un 403 de alta muestra falta de permiso sin datos" — capa: integración.
- [x] 3.9 Escribir en rojo `test_edicion_profesional_envia_put_con_campos_modificados`; crear `EditarProfesionalForm.tsx` y el handler de edición que actualiza la fila — cubre FA "FELIZ — Editar nombre y duración actualiza la fila" — capa: integración.
- [x] 3.10 Escribir en rojo `test_baja_profesional_emite_delete_y_deja_fila_inactiva` (sin `?fisico`, fila sigue visible) y `test_reactivar_profesional_emite_put_activo_true`; implementar ambas acciones — cubre FA "FELIZ — La baja lógica deja la fila como inactiva" y "FELIZ — Reactivar devuelve la fila al estado activo" — capa: integración.
- [x] 3.11 Escribir en rojo `test_edicion_profesional_404_cierra_formulario_y_refresca` y `test_fila_inactiva_solo_ofrece_reactivar`; implementar el `404` y las acciones condicionadas por `activo` — cubre FA "ERROR — Un 404 al editar informa que el profesional no existe" y "BORDE — Repetir la baja de una fila inactiva no ofrece la acción" — capa: integración.

## 4. Administración de usuarios staff

- [x] 4.1 Escribir en rojo `test_usuarios_primera_pagina_pide_limit_20` y `test_usuarios_cargar_mas_usa_next_cursor_sin_duplicar` en `frontend/src/features/staff/admin/__tests__/usuarios.test.tsx`; crear `hooks/useUsuariosStaffAdmin.ts`, la página y la lista hasta verde — cubre FA "FELIZ — La primera página y «Cargar más» usan keyset sin duplicar" — capa: integración.
- [x] 4.2 Escribir en rojo `test_alta_usuario_odontologo_sin_profesional_no_emite_post` (selector obligatorio y mensaje de profesionales activos); crear `AltaUsuarioForm.tsx` con el selector alimentado por profesionales activos en paralelo al listado (`Promise.all`) — cubre FA "FELIZ — El rol odontólogo exige y envía el vínculo profesional" — capa: integración.
- [x] 4.3 Escribir en rojo `test_alta_usuario_cambiar_a_recepcion_oculta_y_limpia_profesional_id` (el `POST` no lleva `profesional_id` no nulo); implementar el reset del vínculo al cambiar de rol — cubre FA "BORDE — Cambiar a recepción oculta y limpia el vínculo" — capa: integración.
- [x] 4.4 Escribir en rojo `test_alta_usuario_409_email_duplicado_menciona_reactivar` (mensaje, no éxito, valores conservados); implementar el mapeo del `409` como alerta de formulario — cubre FA "ERROR — Un 409 de email duplicado explica cómo resolverlo" — capa: integración.
- [x] 4.5 Escribir en rojo `test_alta_usuario_400_profesional_id_marca_solo_ese_campo`; implementar el mapeo del `400` con `detail[]` en `profesional_id` — cubre FA "ERROR — Un 400 de vínculo inválido marca solo profesional_id" — capa: integración.
- [x] 4.6 Escribir en rojo `test_edicion_usuario_envia_solo_rol_y_profesional_id`; crear `EditarUsuarioForm.tsx` y el handler que actualiza la fila — cubre FA "FELIZ — Editar rol y vínculo envía solo esos campos" — capa: integración.
- [x] 4.7 Escribir en rojo `test_edicion_usuario_no_ofrece_inputs_de_email_ni_password`; implementar email/password en modo lectura — cubre FA "BORDE — Email y password no son editables en la UI" — capa: integración.
- [x] 4.8 Escribir en rojo `test_edicion_usuario_422_ultimo_admin_no_marca_exito` y `test_baja_usuario_422_ultimo_admin_conserva_la_fila` (parametrizado `PUT` sobre sí mismo y `DELETE`); implementar el mensaje accionable y la fila sin cambios — cubre FA "ERROR — Un 422 ultimo_admin impide dejar el sistema sin admin" — capa: integración.
- [x] 4.9 Escribir en rojo `test_baja_y_reactivacion_usuario_actualizan_etiqueta_sin_recarga`; implementar ambas acciones — cubre FA "FELIZ — La baja y la reactivación actualizan la fila" — capa: integración.
- [x] 4.10 Escribir en rojo `test_edicion_usuario_404_cierra_formulario_y_refresca`; implementar el `404` compartido con profesionales (helper de error de recurso) — cubre FA "ERROR — Un 404 al editar cierra el formulario y refresca" — capa: integración.

## 5. Reporte de ocupación

- [x] 5.1 Escribir en rojo `test_reporte_carga_inicial_pide_ultimos_30_dias_del_consultorio` (`desde` = hoy − 29 d en `America/Argentina/Buenos_Aires`); crear `hooks/useReporteOcupacion.ts`, `pages/AdminReportesPage.tsx` y el rango por defecto hasta verde — cubre FA "FELIZ — La carga inicial pide los últimos 30 días del consultorio" — capa: integración.
- [x] 5.2 Escribir en rojo `test_reporte_filtro_por_profesional_acota_la_consulta`; implementar el selector opcional de profesional y el `GET` con `profesional_id` — cubre FA "FELIZ — El filtro por profesional acota el reporte a una fila" — capa: integración.
- [x] 5.3 Escribir en rojo `test_reporte_muestra_totales_y_zona_visible`; implementar la tabla por fila y el panel de totales con la `zona` del backend — cubre FA "FELIZ — Los totales y la zona quedan visibles" — capa: integración.
- [x] 5.4 Escribir en rojo `test_reporte_rango_367_no_emite_get_y_marca_hasta` y `test_reporte_rango_invertido_no_emite_get`; implementar la validación local del rango con foco en `hasta` — cubre FA "ERROR — Un rango de 367 días no se consulta y se marca en hasta" — capa: integración.
- [x] 5.5 Escribir en rojo `test_reporte_400_hasta_del_backend_marca_el_campo`; implementar el mapeo del `400 detail[]` en `hasta` — cubre FA "ERROR — Un rango de 367 días…" (red de seguridad del backend) — capa: integración.
- [x] 5.6 Escribir en rojo `test_reporte_profesional_inexistente_tabla_vacia_sin_error`; implementar el estado vacío con totales en cero — cubre FA "BORDE — Un profesional_id inexistente deja la tabla vacía sin error" — capa: integración.
- [x] 5.7 Escribir en rojo `test_reporte_porcentaje_null_se_muestra_como_guion`, `test_reporte_porcentaje_mayor_a_cien_no_se_recorta` y `test_reporte_fila_sin_turnos_muestra_ceros` (parametrizado); crear `formatearPorcentaje` y el render de la celda hasta verde — cubre FA "Porcentaje de ocupación nulo y mayor a cien en la tabla" (3 escenarios) — capa: unit/integración.
- [x] 5.8 Escribir en rojo `test_reporte_no_ofrece_controles_de_exportacion` (sin textos "Exportar"/"CSV"/"Excel"/"Descargar" y sin `format` en URL), `test_reporte_muestra_aviso_de_sin_exportacion` y `test_reporte_no_crea_descarga`; implementar el aviso fijo y verificar la ausencia de controles — cubre FA "Reporte de solo lectura sin exportación en v1" (3 escenarios) — capa: integración.

## 6. Estilos, 360px, accesibilidad y privacidad

- [x] 6.1 Escribir en rojo `test_modulos_admin_declaran_layout_fluido` (raíz `width: 100%`/`max-width: 100%`, sin anchos px > 360) reutilizando `cssStaff.ts`/`fuentesDe` en `frontend/src/features/staff/admin/__tests__/estilos.test.ts`; crear los `*.module.css` de las tres páginas y sus componentes hasta verde — cubre FA "FELIZ — Los módulos CSS declaran layout fluido" — capa: estructura CSS.
- [x] 6.2 Escribir en rojo `test_reporte_tabla_no_fuerza_overflow_de_pagina` (contenedor con scroll propio o degradación a tarjetas y raíz sin ancho fijo > 360); implementar `@media` de tarjetas y `tablaScroll` — cubre FA "BORDE — La tabla del reporte no fuerza overflow de página" — capa: estructura CSS.
- [x] 6.3 Escribir en rojo `test_formularios_admin_asocian_labels_y_anuncian_errores` (label por campo, `aria-invalid`, `aria-describedby`, `role="alert"`/`aria-live`); ajustar los formularios hasta verde — cubre FA "FELIZ — Errores y éxito se anuncian y el foco va al primer error" — capa: integración/a11y.
- [x] 6.4 Escribir en rojo `test_acciones_admin_declaran_alto_minimo_44` en los `*.module.css` admin; ajustar las reglas de botones — cubre FA "BORDE — Las acciones principales son táctiles" — capa: estructura CSS.
- [x] 6.5 Escribir en rojo `test_pantallas_admin_no_ponen_datos_en_la_url` (navegar, abrir/cerrar formularios y consultar el reporte sin que `location.search`/`pathname` incorporen nombres, emails ni el profesional elegido más allá del filtro explícito); ajustar cualquier estado que hoy viaje por URL (duro 12, Ley 25.326) — cubre FA estados y privacidad de las pantallas admin — capa: integración.
- [x] 6.6 Escribir en rojo `test_pantallas_admin_401_redirigen_a_login_sin_datos` y `test_pantallas_admin_429_muestran_espera_sin_reintento_automatico` (parametrizado por las tres pantallas); implementar el manejo común de `401`/`429` — cubre FA "Estados de carga, vacío y error" (`401` y `429`) — capa: integración.
- [x] 6.7 Documentar el checklist de QA manual de 360px (sin scroll horizontal, foco visible, orden de tabulación, lector de pantalla) en la sección de cierre de este archivo, sin automatizarlo en jsdom — cubre FA "Mobile-first 360 y accesibilidad" (verificación manual) — capa: proceso.

## 7. Integración, no regresión y revisión de specs

- [x] 7.1 Correr `npm test` en `frontend/` y verificar que los tests de C-09/C-10 (`rutas`, `layout`, `sesion`, `agenda`, `fallidas`, `privacidad`, `estructura-360`, `shell`) siguen verdes sin cambios de comportamiento — cubre FS no regresión de rutas y nav existentes — capa: proceso/regresión.
- [x] 7.2 Escribir en rojo y hacer verde `test_nav_staff_existente_no_se_reordena_ni_duplica` (agenda y notificaciones conservan su entrada y su gating para recepción/odontología) — cubre FS no regresión de `NAVEGACION_NOTIFICACIONES` — capa: integración.
- [x] 7.3 Revisar los deltas con `openspec validate c-13-frontend-admin --strict` y confirmar que `frontend-admin` (10 requirements / 45 escenarios) y `frontend-shell` (1 requirement MODIFIED / 15 escenarios) no pierden escenarios previos — cubre contrato de specs — capa: proceso.
- [x] 7.4 Verificar que no se tocó `backend/`, `openspec/specs/` ni otros changes con `git status --short` y `git diff --stat`, y que el único archivo fuera del change es la entrada de C-13 en `CHANGES.md` — cubre duro 11 y alcance — capa: proceso.

## 8. Cierre

- [x] 8.1 `cd frontend; npm test` → toda la suite Vitest en verde (incluidos los tests nuevos y los de C-09/C-10/C-11 sin regresiones).
- [x] 8.2 `cd frontend; npx tsc -b` → sin errores ni `any` implícitos.
- [x] 8.3 `cd frontend; npm run build` → build de producción OK.
- [x] 8.4 `openspec validate c-13-frontend-admin --strict` → `Change 'c-13-frontend-admin' is valid`.
- [x] 8.5 `git status --short` → reportar el árbol; confirmar explícitamente que **no** se ejecutó `git add`, `git commit` ni `git push`.
- [ ] 8.6 Checklist manual de 360px documentado: abrir las tres pantallas a 360×640 en navegador real, recorrer formularios y reporte, verificar ausencia de scroll horizontal, foco visible, orden de tabulación y lectura de errores con lector de pantalla; registrar el resultado junto a este archivo al archivar el change.

## 9. QA manual 360px (6.7 y 8.6)

### Checklist (6.7)

Para cada pantalla (`/staff/admin/profesionales`, `/staff/admin/usuarios`, `/staff/admin/reportes`):

- Viewport 360×640 sin zoom: no aparece scroll horizontal del `body`; la tabla del reporte degrada a tarjetas a ≤640px o scrollea dentro de `tablaScroll`.
- Foco visible en botones, links, inputs y selects (outline de 3px con contraste AA sobre los tokens `--color-primary`/`--color-text`).
- Orden de tabulación lógico: navegación → encabezado/acciones → formulario (campos en orden del DOM) → lista → totales; sin `tabindex` positivo.
- Acciones principales con área táctil ≥44px y descubribles sin hover.
- Alta y edición se abren/cierran con teclado (Enter/Space); "Confirmar baja" recibe el foco al entrar en confirmación.
- Con lector de pantalla: carga y éxito se anuncian por `aria-live`/`role="status"`, los errores por `role="alert"` y el foco va al primer campo inválido (`aria-invalid` + `aria-describedby`).
- URL limpia: navegar y operar no incorpora nombres, emails ni el profesional elegido; solo el filtro explícito del reporte viaja en la query del `GET`.

Criterio observable: a 360×640 no debe existir desplazamiento horizontal de la página, y un error de validación debe anunciarse y enfocarse sin usar el mouse.

### Resultado (8.6)

- **Estado: NO EJECUTADA.** El entorno de apply no dispone de navegador ni de lector de pantalla: no hay Playwright/Puppeteer en `frontend/package.json` y no se encontró Chrome/Edge/Firefox en las rutas estándar de instalación. No se marca como verde.
- Cobertura automatizada sustituta: `admin/__tests__/estilos.test.ts` verifica raíces fluidas, ausencia de anchos >360px, `tablaScroll` con `overflow-x: auto`, `@media (max-width: 640px)` con degradación a tarjetas y alto táctil de 44px; `estructura-360.test.ts` cubre el reset global (`overflow-x: clip`) y el foco visible; `admin/__tests__/a11y.test.tsx` cubre labels, `aria-invalid`/`aria-describedby`, `role="alert"`/`aria-live` y foco al primer error.
- Pendiente al archivar: ejecutar este checklist en navegador real y registrar el resultado. El apply queda en **57/58** con esta única tarea manual no ejecutable en el entorno.

## QA manual pendiente (8.6, no ejecutada en apply)

> Esta tarea **no es un fallo de implementación**: la cobertura estática ya existe en tests (`admin/__tests__/estilos.test.ts`, `estructura-360.test.ts`, `admin/__tests__/a11y.test.tsx`). Queda pendiente la verificación visual e interactiva en un entorno con navegador real, que no está disponible en el apply. El change se archiva con 8.6 abierta por decisión explícita del usuario.

En las tres pantallas admin (`/staff/admin/profesionales`, `/staff/admin/usuarios`, `/staff/admin/reportes`), a viewport 360×640 sin zoom:

- Sin overflow horizontal del `body` (`document.documentElement.scrollWidth ≤ 360`) en carga, formularios abiertos, errores y listado largo.
- Tabla del reporte degradada a tarjetas a ≤640px (o scroll contenido en `tablaScroll`, nunca en la página).
- Targets táctiles de las acciones principales ≥44px y descubribles sin hover.
- Foco visible, labels asociados, `aria-invalid`/`aria-describedby` en errores y anuncios por `aria-live`/`role="alert"`.

**Entorno requerido**: navegador real (Chrome, Edge o Firefox) con devtools responsive a 360×640; opcional lector de pantalla para el anuncio de errores.

**Criterio observable de éxito**: a 360×640 no existe desplazamiento horizontal de la página y un error de validación se anuncia y enfoca sin usar el mouse, en las tres pantallas.
