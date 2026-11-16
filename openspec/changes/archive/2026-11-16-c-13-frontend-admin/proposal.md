# Proposal — c-13-frontend-admin

## Why

C-11 implementó y archivó la API admin (`/api/profesionales`, `/api/usuarios-staff`, `/api/reportes/ocupacion`) pero dejó explícito en su propio `design.md` (Non-Goals) que la **UI admin no existe en v1**: hoy un admin no puede dar de alta un profesional, crear un usuario staff ni leer el reporte de ocupación desde el navegador, y solo puede llegar a esas operaciones con curl o soporte técnico. C-13 cierra ese gap declarado (D-15) como extensión post-roadmap, consumiendo contratos ya implementados y sin tocar backend.

## What Changes

- **Pantalla de profesionales** (`/staff/admin/profesionales`, admin-only): listado con toggle `incluir_inactivos`, alta (`nombre`, `matricula`, `especialidad`, `duracion_default_min` 5–240 múltiplo de 5), edición, baja lógica y reactivación, con estados de carga / vacío / error y feedback de éxito. Consume `GET/POST /api/profesionales` y `PUT/DELETE /api/profesionales/{id}`.
- **Pantalla de usuarios staff** (`/staff/admin/usuarios`, admin-only): listado keyset (`limit` + `next_cursor`, incluye inactivos), alta (`email`, `password`, `rol`, `profesional_id` obligatorio solo para odontólogo con selector de profesionales activos), edición de `rol`/`profesional_id`/`activo` (email y password **no editables**), baja lógica y reactivación; `409 email_duplicado` y `422 ultimo_admin` se muestran con mensaje accionable.
- **Pantalla de reporte de ocupación** (`/staff/admin/reportes`, admin-only): rango `desde`/`hasta` (default últimos 30 días, tope 366, error mapeado a `hasta`), filtro opcional por profesional, tabla por profesional + panel de totales, `zona` visible, `porcentaje_ocupacion` `null` → "—" y valores `>100` visibles sin recorte; **sin botón de exportar** y con aviso explícito de que v1 no exporta (PB-06).
- **Navegación admin y gating por rol en el shell**: entradas `/staff/admin/*` visibles solo para `rol=admin`; accesos directos por URL con otro rol muestran un mensaje genérico de falta de permiso (403) sin romper el layout, y `401` sigue redirigiendo a `/staff/login`.
- **Cliente API admin tipado** en `shared/api/admin.ts` (sin `any`, guards estrictos por contrato) reutilizando `requestWithDetail`/`ApiHttpError` y el mapeo `detail[]` → campo de `shared/api/errores.ts`, extendido para los códigos de negocio nuevos (`email_duplicado`, `ultimo_admin`).
- **Estilos y accesibilidad**: CSS modules por componente, mobile-first 360px (tablas del reporte → cards/scroll accesible sin overflow de página), etiquetas asociadas, `aria-live`/`role="alert"` para feedback y foco en el primer error de campo.

## Capabilities

### New Capabilities

- `frontend-admin`: comportamiento observable de las tres pantallas de administración (profesionales, usuarios staff, reporte de ocupación) y de su gating por rol — contratos HTTP emitidos, estados de carga/vacío/error, mapeo de errores de negocio, representación del porcentaje, ausencia de export y requisitos de 360px/a11y.

### Modified Capabilities

- `frontend-shell`: el shell pasa a servir además `/staff/admin/profesionales`, `/staff/admin/usuarios` y `/staff/admin/reportes` bajo el layout protegido, con entradas de navegación visibles solo para `admin` y resolución de acceso directo por URL sin romper el not-found ni las rutas existentes.

`admin-profesionales`, `staff-auth`, `reportes-ocupacion` y `frontend-agenda-staff` **no** se modifican: sus contratos backend y sus comportamientos de UI ya cubren lo consumido.

## Impact

- Frontend (solo lectura de contratos existentes):
  - `frontend/src/App.tsx` (tres rutas admin bajo `/staff`).
  - `frontend/src/features/staff/components/StaffLayout.tsx` (nav admin condicional por rol).
  - `frontend/src/features/staff/pages/` + `frontend/src/features/staff/admin/` (páginas, componentes y hooks de las tres pantallas, sin componentes anidados).
  - `frontend/src/shared/api/admin.ts` (nuevo módulo de endpoints admin) y `frontend/src/shared/api/errores.ts` (códigos de negocio admin).
  - `frontend/src/shared/format.ts` (porcentaje y rango de fechas, si hace falta un helper).
  - `*.module.css` nuevos.
- Backend: **sin cambios**. No hay migraciones, endpoints, schemas ni `openspec/specs/` tocados.
- Dependencias: ninguna instalación nueva (React 18, Vite 5, React Router 6, Vitest, Testing Library y Testing Library `fireEvent`/`render` ya presentes; sin MSW, sin librería UI, sin `user-event`, sin React Query).
- Fuera de alcance: cualquier endpoint o validación backend nueva; export CSV/Excel (PB-06); cambiar o reemplazar la UI de agenda/recepción de C-10; edición de `email`/`password` de usuarios staff (reset de password no existe en v1); CRUD de disponibilidades y bloqueos; reportes por obra social o facturación; reprogramación por paciente (PB-08); auditoría genérica de administración (RN-AU-02 solo cubre turnos).
- Governance: **MEDIO**. El riesgo principal es ofrecer acciones que el backend rechaza (400 por campo, 409 de email, 422 `ultimo_admin`, 403 por rol) o mostrar un reporte desactualizado; se mitiga mapeando cada código a un mensaje accionable, deshabilitando acciones en curso, refrescando el listado tras cada mutación y refrescando el reporte solo con `GET` explícito.

## Criterios de aceptación medibles (por pantalla)

**Profesionales** — se considera aceptada cuando:

1. Con `GET /api/profesionales?incluir_inactivos=true` respondiendo 2 activos + 1 inactivo, la pantalla renderiza 3 filas y la inactiva se distingue con la etiqueta "Inactivo".
2. Un alta con `nombre` vacío **no** emite `POST /api/profesionales` y marca el campo `nombre` con `aria-invalid`; un alta válida emite exactamente un `POST` con `duracion_default_min` numérico y, al recibir `201`, muestra confirmación en región `aria-live` y refresca el listado con una llamada `GET`.
3. `POST` con `400 detail[].campo="duracion_default_min"` marca solo ese campo y conserva el resto de lo ingresado.
4. `DELETE /api/profesionales/{id}` emite `DELETE` (sin body de borrado físico), y al `200` la fila pasa a "Inactivo" sin desaparecer del listado con inactivos; "Reactivar" emite `PUT {"activo": true}` y la fila vuelve a "Activo".
5. El toggle `incluir_inactivos` emite `GET` con `incluir_inactivos=true` / sin el flag, y el listado vacío muestra un texto explícito, no una tabla vacía ni un error.
6. `403` por acceso directo de un rol no admin muestra "No tenés permiso para esta acción." sin datos y sin llamar al endpoint de escritura.

**Usuarios staff** — se considera aceptada cuando:

1. La primera carga emite exactamente un `GET /api/usuarios-staff?limit=20`; con `next_cursor` no nulo aparece "Cargar más" y el click emite un `GET` con ese cursor y agrega ítems sin duplicar por `id`.
2. Elegir `rol=odontologo` hace obligatorio el selector `profesional_id` (alimentado por profesionales **activos**); elegir `recepcion`/`admin` limpia y oculta el selector, y el body emitido **no** incluye `profesional_id` no nulo.
3. `409 detail.codigo="email_duplicado"` muestra un mensaje que menciona que el email ya está tomado y que hay que reactivar la fila existente, sin mostrar éxito y conservando los campos.
4. `422 detail.codigo="ultimo_admin"` muestra un mensaje que explica que debe quedar al menos un admin activo, sin mostrar éxito y conservando la fila; el `PUT`/`DELETE` se deshabilitó mientras estaba en curso.
5. La edición no ofrece inputs de `email` ni `password`, y el body emitido contiene solo `rol`, `profesional_id` y/o `activo`.
6. Baja lógica (`DELETE`) y reactivación (`PUT {"activo": true}`) actualizan la fila del listado sin recargar la página completa.

**Reporte de ocupación** — se considera aceptada cuando:

1. La carga inicial emite un `GET /api/reportes/ocupacion` con `desde` = hoy − 29 días y `hasta` = hoy, ambos `YYYY-MM-DD` de `America/Argentina/Buenos_Aires`.
2. La tabla renderiza una fila por `items[]` con `turnos`, `atendidos`, `ausentes`, `cancelados`, `pendientes`, `minutos_ocupados` y el porcentaje; `porcentaje_ocupacion=null` se muestra como "—" y `150.0` se muestra como "150 %" (sin recorte a 100).
3. El panel de totales reproduce `totales` del backend y la `zona` (`America/Argentina/Buenos_Aires`) es visible en la pantalla.
4. El rango invertido o de 367 días se previene en la UI (no emite `GET`) y, si el backend responde `400 detail[].campo="hasta"`, el error se marca en el campo `hasta`.
5. **No existe** ningún botón, link ni control de descarga/export en la pantalla; la pantalla muestra el aviso "En v1 el reporte es solo tabla: no hay exportación a CSV ni Excel."
6. Con `items: []` se muestra un estado vacío explícito y los totales en cero, sin tratarlo como error; `403`/`401` se manejan como en el resto del staff.
