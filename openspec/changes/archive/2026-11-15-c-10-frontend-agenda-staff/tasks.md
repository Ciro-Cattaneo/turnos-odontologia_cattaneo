# Tasks

## 1. Delta backend de agenda staff (solo lectura)

- [x] 1.1 Agregar `turno_id` y `duracion_min` a las franjas `ocupado` y `duracion_min` a las franjas `libre` en `_franjas_staff` (`backend/app/modules/profesionales/router.py`) y verificar con `pytest backend/tests/test_agenda_staff_vistas.py -k "turno_id or duracion"` que los campos aparecen con el turno y la granularidad correctos
- [x] 1.2 Agregar las entradas `tipo="cerrado"` del día (`atendido|ausente|cancelado`) con `turno_id`, `inicio`, `fin`, `duracion_min`, `estado` y paciente mínimo, sin alterar las franjas libres; verificar con un test nuevo en `test_agenda_staff_vistas.py` que un turno cancelado sigue ofreciendo su bloque como libre y aparece una sola vez como cerrado
- [x] 1.3 Verificar no-regresión pública con `pytest backend/tests/test_agenda_publica_solo_libres.py` que la rama sin sesión no devuelve `turno_id` ni entradas `cerrado`
- [x] 1.4 Actualizar el contrato documentado del endpoint en `design.md` solo si el shape final difiere de D-15 y re-ejecutar `pytest backend/tests/test_agenda_staff_vistas.py backend/tests/test_agenda_publica_solo_libres.py`

## 2. Formato compartido en zona del consultorio

- [x] 2.1 Mover `frontend/src/features/reserva/format.ts` a `frontend/src/shared/format.ts`, actualizar todos sus imports y verificar `npm test` en `frontend/` con los tests de reserva existentes en verde
- [x] 2.2 Agregar `formatearFechaHora`, `hoyEnConsultorio` y `addDias` con `ZONA_CONSULTORIO` y tests unitarios que fijen la TZ `America/Argentina/Buenos_Aires` con casos de borde de medianoche, verificados con `npm test -- format`

## 3. Cliente HTTP staff tipado

- [x] 3.1 Crear `frontend/src/shared/api/staff.ts` con `credentials: "include"`, endpoints de auth/agenda/turnos/ficha/fallidas y tipos estrictos (sin `any`, sin barrel), reutilizando `ApiHttpError` de `client.ts`; verificar con `npm run build` que `tsc -b` compila
- [x] 3.2 Implementar los guards (`isLoginOut`, `isMeOut`, `isAgendaResponse`, `isTurnoStaffOut`, `isReprogramacionOut`, `isEstadoOut`, `isFichaOut`, `isCorreccionOut`, `isCancelacionStaffOut`, `isFallidasPage`) y tests de payload válido, inválido y campos faltantes, verificados con `npm test -- staffapi`
- [x] 3.3 Agregar `mensajeDeError` para `400/401/403/404/409/422/429/red` según D-13 con tests parametrizados por código y `detalle`, verificados con `npm test -- errores`

## 4. Layout staff, login y sesión

- [x] 4.1 Crear `StaffLayout` con resolución de sesión vía `GET /api/auth/me`, contexto acotado (`email`, `rol`, `profesional_id`) y redirección a `/staff/login` ante `401`; verificar con tests que sin sesión la ruta protegida redirige y con sesión renderiza el `<Outlet/>`
- [x] 4.2 Agregar las rutas `/staff/login`, `/staff/agenda` y `/staff/notificaciones` en `frontend/src/App.tsx` sin romper `/`, `/reservar`, `/cancelar` y `*`; verificar con tests de router que cada ruta resuelve la página esperada
- [x] 4.3 Implementar la página de login (email+password, `400` por campo, `401` genérico, `429` con `Retry-After`) y el logout con manejo de error; verificar con tests de submit válido, inválido, rate-limit, logout exitoso y logout fallido
- [x] 4.4 Cubrir el caso de sesión expirada durante una operación (limpieza de estado + redirect) con un test de la agenda que recibe `401` al refrescar, verificado con `npm test -- sesion`

## 5. Agenda día/semana por profesional

- [x] 5.1 Crear `useAgenda` con cache `Map<profesionalId|vista|fecha, estado>`, estados `idle/loading/success/error` y `errorKind`, y botón Actualizar; verificar con tests que cambiar de profesional consulta solo la clave elegida (URLs de `fetch`) y que volver a una clave cacheada no re-consulta
- [x] 5.2 Implementar el selector de profesional (solo activos, paginado por `next_cursor` si aplica), la navegación de fecha ±1 día / ±7 días y las vistas día/semana; verificar con tests de cambio de vista y de fecha que las consultas usan la fecha del consultorio
- [x] 5.3 Renderizar franjas `libre`, `ocupado` (estado + paciente), `bloqueado` (motivo) y la lista de cerrados del día, más `ultima_actualizacion` (con `null` → "sin datos cargados"); verificar con tests de cada tipo de franja y del estado vacío
- [x] 5.4 Cubrir errores de agenda: `404` con opción de recargar profesionales, `403` genérico para agenda ajena, `429` con espera y error de red conservando selección; verificar con tests parametrizados y `npm test -- agenda`

## 6. Ficha de turno y alta de recepción

- [x] 6.1 Implementar el panel de detalle de turno (desde franja ocupada/cerrada) con estado, origen, horario, duración, profesional y paciente, abierto en estado de la página sin datos en la URL; verificar con test de que la `location` no cambia al abrirlo
- [x] 6.2 Implementar el alta desde una franja libre con `origen=recepcion`, los cinco datos y duración en múltiplos de la granularidad; verificar con tests de alta válida (`201` refresca agenda) y de validación local que no envía
- [x] 6.3 Manejar `409 slot_no_disponible` con alternativos conservando los datos y `201` con `notificaciones_encoladas=false`; verificar con tests de ambos casos y de que no se muestra error cuando el turno sí se creó
- [x] 6.4 Ocultar la acción de alta para odontología y cubrir el `403` defensivo; verificar con tests por rol y `npm test -- alta`

## 7. Reprogramación y cancelación

- [x] 7.1 Implementar la reprogramación (fecha + slots libres del día destino + duración múltiplo) solo para `reservado`/`confirmado`; verificar con tests de éxito (ficha y agenda actualizadas), `409` con alternativos sin mover el turno y ausencia de la acción en estados terminales
- [x] 7.2 Implementar la cancelación normal y la forzada `<3 h` con motivo obligatorio antes de enviar y `DELETE` con body JSON; verificar con tests de ≥3 h sin motivo, <3 h sin motivo (no envía) y <3 h con motivo
- [x] 7.3 Cubrir `422 motivo_requerido`, `turno_ya_cancelado` y `turno_no_cancelable` (sin éxito, sin reintento) y el `403` de odontología; verificar con tests parametrizados y `npm test -- cancelacion`

## 8. Corrección de paciente, historial y asistencia

- [x] 8.1 Renderizar el historial paginado por cursor con "Ver más", deduplicando páginas y leyendo `detalle.cambios` de forma defensiva; verificar con tests de dos páginas, cursor inválido (`400`) y payload de cambio desconocido
- [x] 8.2 Implementar la corrección de DNI/teléfono/obra social (sin nombre ni email) con refresco de ficha e historial; verificar con tests de éxito, `400` por campo y `409 dni_duplicado`
- [x] 8.3 Implementar `transicionesPermitidas(estado, rol)` y las acciones de estado (`reservado→confirmado`, `confirmado→atendido`, `confirmado→ausente` solo recepción/admin); verificar con tests por estado y por rol, incluido el `422 transicion_invalida` que refresca
- [x] 8.4 Cubrir la ficha para odontología (sin edición ni ausente) y el `403` de turno ajeno; verificar con `npm test -- ficha`

## 9. Panel de notificaciones fallidas

- [x] 9.1 Implementar `/staff/notificaciones` con `limit=20`, "Cargar más" por cursor y deduplicación por `id`, mostrando tipo, intentos, error, fecha de envío, paciente y horario en TZ del consultorio; verificar con tests de primera página, paginación y deduplicación
- [x] 9.2 Implementar el estado vacío explícito y los errores `400` (cursor inválido reinicia), `401` (redirect), `403` y `429`; verificar con tests parametrizados
- [x] 9.3 Ocultar la entrada de navegación para odontología y verificar el acceso directo con `403` genérico; test por rol y `npm test -- fallidas`

## 10. Integración, estilos y accesibilidad

- [x] 10.1 Verificar que todos los estilos staff viven en `*.module.css` con los tokens existentes (`--touch-target`, `--space-*`), y que el tipado no usa `any` (`tsc -b` y búsqueda de `: any` en `frontend/src`), con un test de CSS que falla si un `*.module.css` staff declara anchos fijos >360px o acciones sin altura táctil de 44px — Evidencia: `estilos.test.ts` (4 tests: anchos fijos, acciones detectadas desde JSX con `min-height`, estilo solo en módulos, sin `any`); `npm run build` ejecuta `tsc -b` en verde; búsqueda de `any` sin coincidencias en `frontend/src`.
- [x] 10.2 Verificar mobile-first 360px en login, agenda, ficha y fallidas con tests de `scrollWidth <= 360`, y revisar manualmente el foco visible y el orden de tabulación — Evidencia: `estructura-360.test.ts` (7 tests estructurales sobre raíces `.pagina`/`.panel` con `width:100%`/`max-width:100%`, `box-sizing:border-box` + `overflow-x:clip` global, sin anchos px >360, `:focus-visible` y sin `tabIndex` positivo). Limitación: jsdom siempre reporta `scrollWidth = 0`, por eso el chequeo es estructural sobre el CSS fuentes; la revisión manual de tabulación/lector de pantalla queda como checklist de QA previo a producción.
- [x] 10.3 Verificar a11y de formularios y paneles (labels asociados, `aria-invalid`/`aria-describedby`, `role="alert"`, foco al primer error); tests de atributos y verificación manual de lectores de pantalla — Evidencia: `a11y.test.tsx` (7 tests: login 400, alta vacía, corrección 400, cancelación 422 `motivo_requerido`, reprogramación 400, regiones ficha/historial con foco en título, región/lista de fallidas). Correcciones de producción: foco a `alta-<campo>` en `AltaTurnoForm`, efectos de foco al primer campo con error en `CorregirPacienteForm`, `CancelarTurnoForm` (motivo 422) y `ReprogramarTurnoForm`. Verificación manual con lector de pantalla pendiente de QA.
- [x] 10.4 Correr la suite completa y el build: `npm test` y `npm run build` en `frontend/` en verde, `pytest backend/tests/test_agenda_staff_vistas.py backend/tests/test_agenda_publica_solo_libres.py` en verde y `ruff check backend/app/modules/profesionales/router.py` — Evidencia (2026-11-15): `npm test` = 30 archivos / 229 tests passed; `npm run build` = `tsc -b` + `vite build` OK; `python -m pytest ...` = 11 passed; `python -m ruff check backend` = All checks passed.
- [x] 10.5 Verificar privacidad en tests: ninguna pantalla staff agrega nombre, DNI, teléfono, obra social ni email a la URL en agenda, alta, reprogramación, cancelación, corrección y recarga — Evidencia: `privacidad.test.tsx` (3 tests con datos ficticios únicos: ficha+alta, reprogramación+cancelación+corrección, recarga; URL y URLs de `fetch` libres de datos y de su forma `encodeURIComponent`, más `POST /api/turnos` sin query).

## Workflow follow-up

- Ejecutar `openspec validate c-10-frontend-agenda-staff --strict` y `openspec status --change c-10-frontend-agenda-staff --json` antes de archivar.
- Aplicar `turno-spec-review` a los artefactos y resolver hallazgos bloqueantes/mayores.
- Archivar el change y marcar `C-10` en `CHANGES.md` cuando la implementación esté revisada.
