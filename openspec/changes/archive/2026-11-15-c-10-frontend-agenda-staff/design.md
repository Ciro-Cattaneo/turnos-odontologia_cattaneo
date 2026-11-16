# Design — c-10-frontend-agenda-staff

## Context

Ver `proposal.md` — Why. El backend staff ya está completo y sin cambios de contrato (auth con cookie httpOnly, agenda, CRUD de turnos, fallidas, ficha con historial). El frontend actual (C-09) tiene shell, cliente HTTP tipado, formato de fechas en TZ del consultorio y pantallas públicas, pero ninguna ruta ni código staff.

Restricciones que condicionan el diseño:

- Sin dependencias nuevas: React 18, Vite 5, React Router 6.28, Vitest 2.1.8 + Testing Library 14 (sin `user-event`, sin MSW, sin React Query, sin librería UI).
- CSS modules (PB-07) y `styles.css` existente con tokens (`--color-*`, `--space-*`, `--touch-target: 44px`, `:focus-visible`).
- Duros: sin `any`, sin barrels, móvil-first 360px, sin datos de paciente en URL, 403 genérico, datos ficticios en tests.
- El backend no expone CORS: se asume same-origin (proxy Vite en dev, reverse proxy en C-12). La cookie `SameSite=lax` es same-site en `localhost`.
- `GET /api/profesionales` solo devuelve activos; la UI staff no puede alcanzar la agenda histórica de un profesional dado de baja. Se acepta como no-goal (ver Riesgos).

## Goals / Non-Goals

**Goals:**

- Un layout staff protegido que resuelve la sesión una sola vez y la comparte con las pantallas.
- Agenda día/semana por profesional con frescura visible y sin consultas cruzadas entre profesionales.
- Operar todo el ciclo del turno desde recepción sin salir de la agenda: alta, reprogramación, cancelación (normal/forzada), corrección de paciente, asistencia y ficha con historial.
- Errores del backend traducidos a mensajes accionables sin duplicar la lógica de negocio.
- Tests de comportamiento por escenario con `fetch` stubbeado solo en el borde.

**Non-Goals:**

- CRUD de disponibilidades y bloqueos desde la UI (US-002 CA-1/CA-2; no asignado a C-10 ni C-11).
- Administración de profesionales/usuarios y reportes (C-11).
- Reprogramación por el paciente (PB-08) y cualquier cambio a `staff-auth` backend.
- Caché de servidor, estado global persistente o sincronización en tiempo real (la frescura se resuelve con refresco explícito).
- Manejo de agenda de profesionales inactivos desde la UI.

## Decisions

### D-0 — Capabilities del change

Nueva `frontend-agenda-staff` con todo el comportamiento de UI. `frontend-shell` MODIFIED porque las rutas staff amplían el contrato del shell. `agenda-disponibilidad` MODIFIED por el delta mínimo de lectura (`turno_id`, `duracion_min`, lista `cerrado`). `staff-auth` no se toca: su contrato backend ya es suficiente. Alternativa descartada: crear una capability por pantalla (login, agenda, turnos, fallidas) — fragmenta escenarios que comparten sesión, errores y privacidad.

### D-1 — CSS modules sin dependencias

Se usa el patrón ya instalado: `*.module.css` por componente/feature, consumiendo los tokens de `styles.css`. Alternativas descartadas: Tailwind (cambio de stack, PB-07 cerrada) y CSS-in-JS (dependencia nueva).

### D-2 — Rutas y layout

Rutas planas existentes (`/`, `/reservar`, `/cancelar`, `*`) más `/staff/login`, `/staff/agenda` y `/staff/notificaciones`. Las páginas staff viven en `features/staff/pages/` (`LoginPage`, `AgendaPage`, `NotificacionesPage`), el layout protegido en `features/staff/components/StaffLayout.tsx` y los componentes/estado en `features/staff/components/` y `features/staff/agenda/`; `App.tsx` solo registra las rutas y anida `agenda`/`notificaciones` bajo `/staff`. El detalle de turno **no** es una ruta: se abre como panel de estado dentro de la agenda. Motivo: evita IDs y datos de paciente en la URL (duro 12) y evita un loader/refetch por navegación. Alternativa descartada: `/staff/turnos/:id` — expone identificadores y complica el retorno a la vista/fecha.

`StaffLayout` con `<Outlet/>` provee navegación, encabezado y contexto de sesión. Guards implementados además de la redirección por `401`: estado `cargando` con `role="status"`, error de `/me` con reintento que no borra la sesión visible, logout fallido que conserva la sesión y muestra el error, y ocultamiento de la entrada de notificaciones para odontología. `main.tsx` no cambia (BrowserRouter + StrictMode). El encabezado muestra "Mi agenda" para odontología porque `MeOut` no trae nombre del profesional; no se agrega al backend. `AgendaPage` filtra el selector a la agenda propia cuando el rol es odontología y muestra estados explícitos de lista de profesionales vacía o fallida; `NotificacionesPage` corta el acceso de odontología sin llamar al endpoint (mensaje genérico) y redirige a login ante `401`.

### D-3 — Sesión por cookie httpOnly

La sesión no se lee ni se guarda en JS. `staffApi` usa `credentials: "include"`; `StaffLayout` dispara `GET /api/auth/me` al montar y guarda `{email, rol, profesional_id}` en un contexto acotado al layout. `401` en `/me` o en cualquier llamada staff ⇒ limpiar estado y navegar a `/staff/login` sin parámetro de retorno (evita abrir redirecciones arbitrarias). Logout es explícito, muestra el error si falla y no limpia la sesión local si el backend no revocó. Alternativa descartada: guardar el rol en `localStorage` — se desincroniza y no aporta seguridad.

### D-4 — Cliente staff tipado en `shared/api/staff.ts`

Se reutilizan `ApiError`, `ApiHttpError`, `requestWithDetail` e `isRecord` de `shared/api/client.ts`, que ya adjunta `detail` estructurado. `staff.ts` agrega tipos y guards estrictos por respuesta (`isLoginOut`, `isMeOut`, `isAgendaResponse`, `isTurnoStaffOut`, `isReprogramacionOut`, `isEstadoOut`, `isFichaOut`, `isCorreccionOut`, `isCancelacionStaffOut`, `isFallidasPage`), sin `any` y sin barrels. Cada guard valida campos discriminantes (`rol`, `tipo` de franja, `estado`) y se testea con payloads válidos e inválidos. Alternativa descartada: generar tipos desde OpenAPI — no hay toolchain instalada y sumaría dependencias.

### D-5 — Cache de agenda por clave y refresco explícito

`useAgenda` mantiene un `Map<clave, estado>` con clave `profesionalId|vista|fecha`; cambiar de profesional no consulta las agendas de los otros (escenario de la spec) y volver a una clave cacheada no re-consulta hasta pulsar "Actualizar" o mutar. Cada respuesta guarda `ultima_actualizacion`, que solo cambia cuando el trigger `002_agenda_meta` toca `disponibilidad` o `bloqueo`; una edición de turno refresca la agenda pero no mueve ese valor. No hay polling. Alternativa descartada: React Query — dependencia nueva; alternativa descartada: refetch en cada render — riesgo de bucles y de mostrar datos viejos.

Estado de agenda por clave: `idle | loading | success | error`, con `errorKind` (`network | http | invalid`). El error no borra la selección (profesional/vista/fecha).

### D-6 — Formato compartido en `shared/format.ts`

Se mueve `features/reserva/format.ts` a `shared/format.ts` y se actualizan sus imports, agregando `formatearFechaHora`, `hoyEnConsultorio` y `addDias` sobre `ZONA_CONSULTORIO`. El cambio de ubicación refleja que staff y público comparten reglas de TZ; no cambia comportamiento público (los tests de reserva cubren la regresión). Alternativa descartada: duplicar el módulo en `features/staff` — dos fuentes de verdad para TZ.

### D-7 — Mutaciones sin optimismo

Toda mutación (alta, reprogramación, cancelación, corrección, estado) espera la respuesta, deshabilita su acción con `pending` (anti doble submit) y luego invalida la clave de agenda afectada + refresca la ficha. No se aplican cambios optimistas: la agenda puede rechazar por solape y mostrar un estado que nunca existió confunde. Alternativa descartada: actualización optimista con rollback — mayor complejidad y peor mensaje de error.

### D-8 — Cancelación forzada con motivo

La UI calcula `inicio - ahora < 3 h` con la constante `CANCEL_HOURS_MIN` replicada en `shared/config` (documentada como espejo del env del backend) para exigir motivo **antes** de enviar; el `422 motivo_requerido` del backend sigue siendo la red de seguridad cuando los relojes o la config difieren, y reabre el campo. `DELETE /api/turnos/{id}` se envía con body JSON `{motivo}` cuando existe. Alternativa descartada: no calcular en cliente y esperar siempre el 422 — un viaje extra y peor UX.

### D-9 — Transiciones válidas derivadas del estado y el rol

`transicionesPermitidas(estado, rol)` replica la matriz cerrada `reservado→confirmado`, `confirmado→atendido`, `confirmado→ausente` (ausente solo recepción/admin) y devuelve las acciones visibles. No se ofrece ninguna acción fuera de la matriz. Un `422 transicion_invalida` se trata como estado desactualizado: mensaje + refetch de ficha. Alternativa descartada: mostrar todos los botones y dejar que el backend rechace — incumple la spec y genera errores evitables.

### D-10 — Reprogramación como selección de fecha + slot

El formulario de reprogramación pide fecha destino, consulta la agenda **staff** de ese día para el mismo profesional y ofrece solo franjas `libre`; la duración se elige entre múltiplos de la granularidad (`duracion_default_min`). El panel conserva la ficha anterior hasta el `200`. No se permite cambiar de profesional en la reprogramación (el backend lo rechazaría). Alternativa descartada: reprogramación por texto libre de fecha/hora — no valida disponibilidad.

### D-11 — Ficha con historial paginado por cursor

La ficha consume `GET /api/turnos/{id}` con historial por cursor opaco; "Ver más" agrega páginas sin duplicar. El render del historial lee `detalle.cambios` de forma defensiva (helper que mapea campos conocidos y muestra el resto como pares clave/valor), porque el backend no garantiza un shape fijo por acción. Un cursor inválido (`400`) reinicia el historial y avisa.

### D-12 — Panel de fallidas acotado

Lista con `limit=20` y "Cargar más" por `next_cursor`; se deduplican items por `id`. La entrada de navegación solo se renderiza para `recepcion|admin`; el acceso directo de odontología resuelve la ruta bajo el layout protegido pero muestra el mensaje genérico de falta de permiso sin llamar al endpoint. Alternativa descartada: scroll infinito automático — más difícil de testear y de anunciar en a11y.

### D-13 — Traducción uniforme de errores

Un helper `mensajeDeError(error, contexto)` mapea: `400` → detalle por campo, `401` → sesión expirada/redirección, `403` → "No tenés permiso para esta acción" genérico, `404` → "No encontrado", `409` → mensaje del `codigo` conocido (`slot_no_disponible` usa alternativos; `dni_duplicado`), `422` → `motivo_requerido`/`turno_no_editable`/`turno_ya_cancelado`/`turno_no_cancelable`/`transicion_invalida`, `429` → espera con `Retry-After` cuando la respuesta lo trae (agenda y panel) y mensaje genérico de espera cuando no (login, porque `POST /api/auth/login` no emite el header en v1), red/timeout → "No pudimos conectar". Nunca se muestra el `detail` crudo del servidor ni datos de otro recurso. Alternativa descartada: mensajes ad hoc por pantalla — inconsistencia y riesgo de filtrar datos.

### D-14 — Accesibilidad y 360px

Etiquetas `<label for>`, `aria-invalid` + `aria-describedby` en campos con error, `role="alert"` en el resumen de errores, foco manual al primer campo inválido o al panel abierto, `--touch-target` en acciones, y layouts de una columna que colapsan la vista semana en una lista de días. `:focus-visible` ya está en `styles.css`. Los tests verifican la estructura del CSS fuente (raíz `width/max-width: 100%`, `box-sizing: border-box`, `overflow-x: clip` y ningún ancho fijo en px > 360), `aria-*` y labels; jsdom no calcula layout (`scrollWidth` siempre es 0), así que la ausencia real de scroll horizontal a 360px, el foco visible, el orden de tabulación y los anuncios de lector de pantalla quedan como QA manual documentada.

### D-15 — Delta backend mínimo (solo lectura)

`_franjas_staff` en `backend/app/modules/profesionales/router.py` agrega `turno_id` y `duracion_min` a `ocupado`, `duracion_min` a `libre`, y una lista de entradas `tipo="cerrado"` para `atendido|ausente|cancelado` del día. Sin migraciones, sin endpoints, sin cambios en `compute_slots` ni en `staff_opcional`; la rama pública sigue devolviendo solo libres sin esas claves. Tests: extender `test_agenda_staff_vistas.py` y mantener `test_agenda_publica_solo_libres.py` como no-regresión. Alternativa descartada: resolver la ficha y la asistencia con endpoints nuevos de historial por día — más superficie y no pedido.

### D-16 — Same-origin asumido

`staffApi` usa rutas relativas (`API_BASE` ya configurable) y `credentials: "include"`. En dev se requiere el proxy de Vite hacia el backend para que la cookie sea same-site; en C-12 el reverse proxy sirve web y API bajo el mismo origen. Se documenta como precondición de despliegue; no se agrega el proxy en este change (no es parte del alcance de C-10). Alternativa descartada: habilitar CORS con credenciales en el backend — tocaría `main.py` y otra capability.

## Risks / Trade-offs

- **[Delta backend sin cambios de contrato público]** → la rama pública no cambia y se cubre con el test existente; el `tipo="cerrado"` es aditivo y solo staff.
- **[UI replica la regla de 3 h y la matriz de transiciones]** → el backend sigue siendo autoritativo; la UI solo evita errores y el `422` es la red de seguridad.
- **[Sin sincronización en tiempo real]** → la agenda puede quedar vieja; se muestra `ultima_actualizacion`, hay botón Actualizar y toda mutación refresca.
- **[Profesionales inactivos no alcanzables desde la UI]** → no afecta la operación diaria; la agenda histórica por API sigue disponible para C-11.
- **[CRUD de disponibilidades/bloqueos sin UI]** → gap declarado (US-002 CA-1/CA-2); el backend existe y queda para un change futuro. C-10 solo muestra bloqueos y frescura.
- **[Reprogramación sin cambio de profesional]** → limitación aceptada: el backend lo rechaza y el flujo real es cancelar + crear (o reasignar en C-11).
- **[Same-origin no garantizado en dev]** → se documenta la precondición del proxy; sin él las cookies no viajan y el login falla de forma visible.
- **[Cookie httpOnly + rol en memoria]** → recargar la página revalida con `/me`; costo aceptado de una llamada extra por carga.
- **[Sin `user-event`]** → los tests usan `fireEvent`; cubre el comportamiento, no la secuencia real de teclado (se valida a mano en a11y).

## Migration Plan

No hay migración de datos. Despliegue: primero el delta backend (aditivo, retrocompatible), luego el frontend. Rollback: el frontend staff puede retirarse sin afectar público; el delta backend es aditivo y puede quedarse (los consumidores de C-09 no leen las claves nuevas).

## Open Questions

Ninguna que bloquee: el proxy de desarrollo se configura en un change de tooling o en C-12, y el reasignado de profesional entra en C-11.
