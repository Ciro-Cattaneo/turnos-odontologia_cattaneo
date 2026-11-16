# Design — c-13-frontend-admin

## Context

Ver `proposal.md` (§Why) y `specs/frontend-admin/spec.md`. Estado relevante del repo:

- **Contratos backend ya implementados y archivados (C-11), no se tocan:**
  - `GET /api/profesionales?incluir_inactivos=true` → `{items, next_cursor}` con `ProfesionalAdminOut` (`id`, `nombre`, `matricula`, `especialidad`, `duracion_default_min`, `activo`, `ultima_actualizacion`); `POST` → `201`; `PUT /{id}` (parcial, `{"activo": true}` reactiva) → `200`; `DELETE /{id}` → `200` con `activo=false`. `400` por campo (`detail[]`), `401`, `403`, `404`.
  - `GET /api/usuarios-staff?limit=&cursor=` → `{items, next_cursor}` sin `password_hash`; `POST` → `201` (`email` 3–320, `password` 8–256, `rol`, `profesional_id` solo odontólogo); `PUT /{id}` (rol/vínculo/activo); `DELETE /{id}` → `200` `activo=false`. `409 detail.codigo="email_duplicado"`, `422 detail.codigo="ultimo_admin"`, `422` por campo en el vínculo, `400` por campo.
  - `GET /api/reportes/ocupacion?desde=&hasta=&profesional_id=` → `{desde, hasta, zona, items[], totales}`; `porcentaje_ocupacion: float | null`; rango ≤366 días, `400 detail.campo="hasta"`; sin `format`/export (PB-06).
- **Patrones frontend a reutilizar (C-09/C-10):** `shared/api/client.ts` (`request<T>`, `requestWithDetail<T>`, `ApiHttpError`, `isRecord`), `shared/api/errores.ts` (`mensajeDeError` → `StaffErrorInfo` con `kind`/`fieldErrors`/`codigo`), `shared/api/staff.ts` (endpoints staff tipados con `credentials: "include"` y guards), `features/staff/components/StaffLayout.tsx` (resuelve `GET /api/auth/me`, nav por rol, `StaffSesionProvider`), `features/staff/sesion.tsx` (`useStaffSesion`, `useExpirarSesion`), `shared/format.ts` (`formatearFechaCalendario`, `addDias`, `hoyEnConsultorio`), CSS modules por componente (`*.module.css`).
- **Tests existentes:** Vitest + Testing Library, `fetch` mockeado en el borde (`vi.stubGlobal("fetch", ...)`), router en memoria con `appRoutes`, tests de estructura CSS leyendo los `*.module.css` (`__tests__/estructura-360.test.ts`, `cssStaff.ts`). Sin MSW, sin `user-event`.
- **Restricciones:** regla dura 8 (sin `any`, sin componentes anidados, sin barrels, mobile-first 360), 9 (tests reales con mock solo en el borde), 11 (no commit), 12 (datos ficticios).

## Goals / Non-Goals

**Goals:**

- Servir tres pantallas admin bajo el shell existente reutilizando `StaffLayout`, la sesión acotada y el cliente HTTP tipado, sin crear un segundo layout ni un segundo sistema de estilos.
- Aislar la superficie admin en un módulo API propio (`shared/api/admin.ts`) con guards estrictos por contrato, sin engordar `staff.ts` con recursos que solo usa `admin`.
- Hacer que todo error de negocio del backend (`400` por campo, `409` email, `422 ultimo_admin`, `403`, `404`) tenga una representación de UI distinta y accionable, sin inventar mensajes para casos que no existen.
- Asegurar que la pantalla del reporte nunca ofrezca export y que la tabla sea usable a 360px.

**Non-Goals (design-level):**

- Componentes o primitivas compartidas nuevas de formulario/lista (se reutiliza el estilo de C-10 y se aceptan duplicaciones controladas de markup en cada pantalla; ver D-3).
- Estado global de administración (store, context nuevo, React Query). Cada pantalla resuelve su estado.
- Cambios en `shared/api/client.ts` más allá de nada: los helpers actuales alcanzan.
- Manejo de `ultima_actualizacion` de profesional como dato de frescura de agenda (no se muestra en admin; no aporta a US-010).

## Decisions

### D-1. Estructura de rutas y gating por rol en el shell

**Qué:**

```
/staff                     → <StaffLayout />            (sin cambios)
  agenda                   → <AgendaPage />
  notificaciones           → <NotificacionesPage />
  admin/profesionales      → <AdminProfesionalesPage />
  admin/usuarios           → <AdminUsuariosPage />
  admin/reportes           → <AdminReportesPage />
/staff/login               → <LoginPage />               (sin cambios)
```

- `App.tsx` solo agrega tres `children` bajo el `path: "/staff"` existente. No se crea un layout `AdminLayout` ni una ruta índice `/staff/admin`.
- `StaffLayout` calcula `esAdmin = sesion.rol === "admin"` y renderiza el bloque de navegación admin **solo** si `esAdmin`. El mismo patrón ya usado por `NAVEGACION_NOTIFICACIONES`.
- La autorización real es del backend: las pantallas no ocultan la ruta, muestran un estado de "sin permiso" si la sesión no es admin o si el backend responde `403`. Ningún rol no admin puede alcanzar un formulario admin.
- Se agrega un helper de gating de pantalla local por página (`useSesionAdmin()` dentro de `features/staff/admin/` que devuelve `{esAdmin, expirarSesion}`) en lugar de repetir el chequeo tres veces; es una función, no un componente.

**Por qué:** el shell ya resuelve sesión y layout; agregar rutas hijas es el cambio mínimo y no reordena la navegación existente. Gatear en `StaffLayout` mantiene una única fuente de verdad de la nav.

**Alternativas descartadas:**

- Ruta de nivel superior `/admin/*` fuera de `/staff`: duplica la resolución de sesión y rompe el patrón `/staff/*` de C-10.
- `AdminLayout` con su propio `GET /api/auth/me`: segunda resolución de sesión, dos verdades de rol y un `401` duplicado.
- Redirigir a `/staff/agenda` cuando el rol no es admin: oculta el `403` real y hace que el usuario crea que se equivocó de ruta; la spec de `frontend-shell` exige resolver la ruta y mostrar falta de permiso.

### D-2. Módulo API: `shared/api/admin.ts` nuevo, no extender `staff.ts`

**Qué:**

- `shared/api/admin.ts` define tipos + guards + funciones:
  - `ProfesionalAdmin` / `isProfesionalAdmin`, `ProfesionalesAdminPage` / `isProfesionalesAdminPage`.
  - `UsuarioStaff` / `isUsuarioStaff`, `UsuariosStaffPage` / `isUsuariosStaffPage`.
  - `ReporteOcupacion` / `isReporteOcupacion`, `ReporteFila`, `ReporteTotales`.
  - `listarProfesionalesAdmin(incluirInactivos)`, `crearProfesional`, `actualizarProfesional`, `darDeBajaProfesional`.
  - `listarUsuariosStaff(limit, cursor?)`, `crearUsuarioStaff`, `actualizarUsuarioStaff`, `darDeBajaUsuarioStaff`.
  - `getReporteOcupacion(desde, hasta, profesionalId?)`.
- Todas usan `requestWithDetail<T>(url, guard, init)` con `credentials: "include"` y reutilizan `API_BASE`/`isRecord` de `client.ts`.
- `shared/api/errores.ts` se extiende **sin cambiar** la firma de `mensajeDeError`: se agregan `email_duplicado` (→ mensaje de email tomado + reactivar fila) y `ultimo_admin` (→ mensaje de admin mínimo) al mapa de códigos, y un mapa separado para `409` de admin (el actual `409` asume solape de turno). Se resuelve con un `contexto`/`recurso` opcional ya previsto por el parámetro `contexto` y un discriminante por `codigo`, sin tocar la firma pública.
- `staff.ts` no se toca (excepto nada): sus guards de `Profesional` público no conocen `activo` y no deben confundirse con la forma admin.

**Por qué:** el tipo `Profesional` público (sin `activo`) y el `ProfesionalAdmin` (con `activo`) son contratos distintos; mezclarlos en `staff.ts` obligaría a un guard que acepte ambos y debilitaría el tipado. Separar por audiencia (staff operativo vs admin) también evita que la agenda importe tipos de admin. No hay barrels: cada import apunta a `shared/api/admin`.

**Alternativas descartadas:** extender `staff.ts` con un `isProfesionalAdminLike` que tolere `activo` opcional (guard permisivo, viola duro 8 en la práctica); reutilizar el tipo público y castear el `activo` (mentira de tipos); crear un `adminClient.ts` que envuelva `fetch` (reimplementa `requestWithDetail`).

### D-3. Formularios: estado local + mapeo `detail[]` → campo con `mensajeDeError`

**Qué:**

- Cada formulario (alta/edición de profesional, alta/edición de usuario) es un componente propio que recibe props planas (`valorInicial`, `onGuardar`, `onCancelar`, `enviando`) y devuelve un body tipado por callback. No hay componente `Form` genérico: los campos, labels y validaciones locales son de cada pantalla.
- Estado: `useState` de un record tipado por campo (`interface ErroresProfesional { nombre?: string; duracion_default_min?: string; ... }`), más `enviando: boolean`.
- Validación local **mínima y alineada al backend**: obligatorios y grilla de duración (5–240 múltiplo de 5) para no emitir requests que sabemos que fallarán; el resto se delega al backend.
- Mapeo de `400`: se usa `mensajeDeError(error, "el alta del profesional").fieldErrors`, que ya normaliza `body.` y `paciente.`; los nombres de campo admin (`nombre`, `duracion_default_min`, `email`, `password`, `rol`, `profesional_id`) coinciden tal cual, así que no hace falta traducción adicional. Se asigna el record de errores al estado y se enfoca el primer campo con error con un `ref` por campo (o `document.querySelector` acotado al formulario, evitando `any`).
- `409`/`422`: se leen por `codigo` desde `mensajeDeError(...).codigo` y se muestra como alerta de formulario (`role="alert"`), no como error de campo, salvo el `422` de `profesional_id` que trae `detail[]` y se mapea al campo.
- Éxito: se anuncia en una región `aria-live="polite"` persistente de la página (no del formulario, que se desmonta) y se invalida/refresca el listado.

**Por qué:** C-10 ya demostró que `mensajeDeError` + un record por campo cubre todos los `400` del backend sin duplicar la lógica de parseo. Un `Form` genérico requeriría un motor de schema (nueva dependencia o 200 líneas de código) para tres formularios pequeños.

**Alternativas descartadas:** `react-hook-form`/`zod` (dependencia nueva, PB/stack no la incluye); validación espejo completa en el cliente (doble fuente de verdad, se desincroniza del backend); un tipo `unknown` para el body del formulario (viola duro 8).

### D-4. Paginación keyset en la UI: solo donde existe

**Qué:**

- Profesionales admin: el listado **no pagina en UI**; se piden todas las páginas de forma secuencial con `next_cursor` hasta `null` al cargar/refrescar (el catálogo es chico y ya existe `getProfesionalesStaff()` con ese patrón en `staff.ts`; se replica en `admin.ts` para la forma admin).
- Usuarios staff: la UI pagina explícitamente con `limit=20` + botón "Cargar más" que usa el `next_cursor` opaco devuelto, deduplicando por `id` (mismo patrón que `NotificacionesPage`).
- Reporte: sin paginación (el backend no pagina y el rango está acotado a 366 días).

**Por qué:** respeta exactamente los contratos (profesionales admin devuelve keyset pero el conjunto es pequeño; usuarios staff puede crecer y la pantalla debe mostrar "Cargar más"). No se inventa `offset`, `page` ni filtros que el backend rechazaría por `extra='forbid'`.

**Alternativas descartadas:** paginar profesionales con `limit`/`cursor` visible (complejidad de UI sin beneficio: decenas de filas); cargar todas las páginas de usuarios de una (puede crecer sin límite y ya hay contrato keyset); paginación numérica (no hay total y violaría duro 7).

### D-5. Porcentaje: `null` → "—", `>100` visible

**Qué:**

- Helper local en `features/staff/admin/` (`formatearPorcentaje(valor: number | null): string`): `null → "—"`, número → `${valor} %` con el valor tal cual (sin `Math.min(100, ...)`).
- La celda expone el número crudo y un `aria-label` explícito ("Sin capacidad registrada" para `null`).
- Un valor `>100` se resalta visualmente (clase de aviso) pero **no** se trunca ni se oculta.

**Por qué:** el backend define `null` como "sin capacidad" (RE R2) y `>100` como señal de sobreasignación; recortar a 100 destruiría la información operativa que el admin necesita.

**Alternativas descartadas:** mostrar `0 %` para `null` (miente: confunde "sin capacidad" con "capacidad ociosa"); recortar a 100 (pierde la señal); mostrar el número sin "%" (menos claro).

### D-6. Tabla del reporte responsive a 360px

**Qué:**

- La tabla semántica (`<table>`) se renderiza con `overflow-x: auto` **en un contenedor propio** (`tablaScroll`), de modo que el overflow no se propaga al `body`; la raíz del módulo declara `width: 100%` / `max-width: 100%`.
- A ≤ 640px (`@media`) cada fila se presenta como tarjeta (`display: block` sobre `thead`/`tbody`/`tr`/`td` con `::before` para el label), manteniendo el `<table>` en el DOM y las etiquetas accesibles.
- Los totales van en un panel separado de la tabla, no como `<tfoot>` (más simple de leer a 360px y de testear).

**Por qué:** el requisito de 360px prohíbe overflow de página; el scroll interno de un contenedor es aceptable y la degradación a tarjetas evita perder columnas. El test de estructura CSS (patrón C-10) puede verificar las declaraciones sin navegador real.

**Alternativas descartadas:** solo scroll horizontal (usable pero incómodo a 360px); solo tarjetas (pierde la semántica de tabla en desktop y complica el header); `div` grid sin `<table>` (peor accesibilidad de lector de pantalla).

### D-7. Estado por pantalla, sin store ni hooks de datos genéricos

**Qué:**

- Un hook por pantalla en `features/staff/admin/`: `useProfesionalesAdmin`, `useUsuariosStaffAdmin`, `useReporteOcupacion`. Cada uno expone `{estado, datos, error, refrescar, mutar...}` con `useState` + `useCallback`, y llama a `useExpirarSesion()` para traducir `401` a redirección.
- Las pantallas consumen su hook y solo componen JSX (lista + formulario). Los formularios son componentes con estado local propio.
- Mutación → `await` de la función API → éxito: `refrescar()` del hook; error: `mensajeDeError` en estado de la pantalla/formulario.
- Requests independientes se piden en paralelo cuando aplica: en usuarios, el listado y el catálogo de profesionales activos para el selector se cargan con `Promise.all` (no en cascada). En reportes, el catálogo para el filtro y el reporte se cargan en paralelo en la primera carga.

**Por qué:** tres pantallas con estados distintos no justifican un store; hooks locales siguen el patrón de `useAgenda`/`NotificacionesPage` de C-10 y mantienen el tipado estricto. `Promise.all` evita waterfalls (guía de performance React).

**Alternativas descartadas:** React Query/SWR (dependencia nueva); un `AdminContext` global (acopla tres pantallas que no comparten datos); extender `useAgenda` (concepto distinto).

### D-8. Reutilización de `StaffLayout` y de la sesión acotada

**Qué:** no se toca la resolución de sesión. `StaffLayout` ya provee `useStaffSesion()` (`email`, `rol`, `profesional_id`) y `useExpirarSesion()`. Las pantallas admin usan esos hooks; el layout suma las tres entradas de nav bajo `sesion.rol === "admin"`. Ningún token se lee ni se persiste en JS (se mantiene la cookie httpOnly).

**Por qué:** evita una segunda llamada a `/api/auth/me` y mantiene una sola política de expiración y logout.

**Alternativas descartadas:** pantallas admin fuera del layout protegido con su propio guard (duplica sesión y logout); leer `rol` de `localStorage` (rompe el modelo de sesión de C-03/C-10).

### D-9. Manejo de `403` en acceso directo por URL

**Qué:**

- La pantalla admin no asume que el rol es admin: si `useStaffSesion().rol !== "admin"`, renderiza el mismo bloque genérico de falta de permiso (`role="alert"`, sin formularios ni llamadas de escritura) y **no** emite el `GET` de administración.
- Si aun así el backend responde `403` (rol cambiado en la DB durante la sesión, o acceso con un rol que la UI no previó), `mensajeDeError` produce `kind="forbidden"` y la pantalla muestra el mensaje genérico, sin reintento automático y sin datos.
- No se redirige ni se muestra not-found: la spec de `frontend-shell` exige que la ruta se resuelva bajo el layout protegido.

**Por qué:** el backend es la autoridad (C-03) y el rol puede cambiar en caliente; gatear también por la sesión resuelta evita requests condenados y el `403` real queda cubierto como red de seguridad.

**Alternativas descartadas:** confiar solo en el `403` del backend (haría un `GET` por pantalla siempre, incluidos roles sin permiso); ocultar la ruta con un redirect (rompe el requisito de "resuelve la ruta"); mostrar el error del backend literal (puede filtrar detalles internos; se usa el mensaje genérico de `errores.ts`).

### D-10. Sin exportación: por qué y cómo se garantiza

**Qué:** no se renderiza ningún control de exportación ni se envía `format`. La pantalla muestra un aviso fijo con el texto de v1 (solo tabla). El test de pantalla verifica ausencia de controles con texto de export y ausencia de `format` en la URL emitida.

**Por qué:** PB-06 y RE R5 son contractuales: el backend rechaza `format` con `400` por `extra='forbid'`. Ofrecer un botón que solo puede fallar es un defecto de UI.

**Alternativas descartadas:** exportar en el cliente (crearía un CSV que el backend no autoriza y evade la decisión PB-06); dejar el botón deshabilitado "próximamente" (promete una función fuera de v1 y confunde).

### D-11. Nombres y ubicación de archivos

**Qué:** `features/staff/admin/pages/{AdminProfesionalesPage,AdminUsuariosPage,AdminReportesPage}.tsx` + `*.module.css`; `features/staff/admin/components/` para formularios y sub-bloques de cada pantalla; `features/staff/admin/hooks/` para los tres hooks y helpers puros (`porcentaje.ts`, `rango.ts`). Sin `index.ts` (sin barrels), imports directos.

**Por qué:** mantiene el feature `staff` como dueño de todo lo que vive bajo `/staff` y evita una carpeta `features/admin` que fragmentaría el dominio. No hay componentes anidados: cada archivo exporta un componente de nivel superior.

**Alternativas descartadas:** `features/admin/*` (dos features para una sola ruta `/staff/*`); un único `AdminPage.tsx` con las tres pantallas (anidaría componentes y mezclaría tres ciclos de datos).

## Risks / Trade-offs

- **La UI no puede garantizar la consistencia del invariante `rol=odontologo ⇔ profesional_id`:** la valida el backend y la UI la previene; un `400`/`422` en `profesional_id` se muestra en el campo. → Mitigación: el selector solo lista profesionales activos y se limpia al cambiar de rol.
- **El catálogo de profesionales activos para el selector puede quedar viejo** si se da de baja un profesional en otra pestaña. → Mitigación: un `422`/`400` en `profesional_id` se muestra en el campo y el formulario permite re-elegir; no se cachea el catálogo entre pantallas.
- **El reporte se calcula con la configuración vigente (RE R2)** y puede cambiar si el admin edita duraciones/disponibilidad entre consultas. → Mitigación: el reporte se refresca solo con la acción explícita "Consultar"; no hay polling ni auto-refresh que confunda.
- **Duplicación de markup entre formularios admin y de C-10:** se acepta para no introducir un motor de formularios. → Mitigación: helpers puros compartidos para validaciones y formateo, sin componentes genéricos.
- **La tabla degradada a tarjetas depende de CSS y `@media`:** jsdom no evalúa media queries. → Mitigación: test de estructura CSS (como `estructura-360.test.ts`) + checklist manual de 360px documentado en `tasks.md`.
- **`403` tras un cambio de rol en caliente:** el usuario sigue viendo el layout pero no los datos. → Mitigación: mensaje genérico, sin reintento; el logout/login re-resuelve la sesión.
- **`aria-live` y foco del primer error** no son verificables completamente en jsdom. → Mitigación: se testea la presencia de `role="alert"`/`aria-live`/`aria-invalid` y el foco del primer campo; la verificación con lector de pantalla queda como QA manual documentado.

## Migration Plan

- Sin migraciones de datos ni cambios de esquema.
- Deploy: el frontend se reconstruye (`npm run build`) y se sirve con el mismo mecanismo de C-12; las rutas nuevas son estáticas del SPA y no requieren rewrites adicionales (el fallback a `index.html` ya existe para `/staff/*`).
- Rollback: revertir el commit del frontend. No hay estado persistido creado por C-13 (solo requests a endpoints existentes), así que el rollback no deja datos huérfanos.

## Open Questions

Ninguna que cambie spec, enfoque o desglose de tareas. Las decisiones sobre textos exactos de los avisos y el umbral de la media query quedan a criterio de implementación, dentro de las restricciones de las specs.
