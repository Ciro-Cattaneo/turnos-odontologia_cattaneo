# Proposal — c-09-frontend-reserva-publica

## Why

El backend de reserva (C-05), cancelación por token (C-06) y disponibilidad (C-04) ya está implementado y archivado, pero el frontend solo tiene un shell con landing y not-found: el paciente todavía no puede ver horarios, reservar ni cancelar desde el celular. C-09 cierra ese hueco del camino crítico con las pantallas públicas de reserva y cancelación, consumiendo los contratos existentes sin reabrirlos.

## What Changes

- `GET /` landing con CTA de reserva (el shell actual ya tiene el enlace; se completa la experiencia mobile-first).
- `GET /reservar`: buscador por profesional y fecha; lista de slots **solo libres** (sin ocupados ni bloqueados), con estado de carga y error de red.
- Formulario de reserva con los cinco campos obligatorios del paciente (nombre, DNI, teléfono, obra social, email) validados en cliente y con el detalle 400 por campo del backend; mail obligatorio con formato válido.
- Reserva exitosa: resumen del turno + link de cancelación; se informa que la confirmación y los recordatorios quedan encolados (sin aviso de "sin mail", PB-02).
- `GET /cancelar?token=<token>&id=<id>` como **única** vía de cancelación (PB-01): sin sección "mis turnos" ni DNI+teléfono; confirmación genérica sin datos del turno (C-06 es DELETE-only, no hay GET público); error `<3 h` (422) con mensaje y contacto del consultorio; `turno_ya_cancelado`/`turno_no_cancelable` informan el estado sin contacto ni reintento; token inválido/inexistente/malformado (403, y 404 de ruta tratado igual) con mensaje genérico. El `token` es la única credencial; el `id` es un localizador opaco (UUID) que no autentica. **PB-01 se interpreta como credencial única; `id` es localizador opaco no credencial (D-10 A); el DELETE conserva solo `?token=`.**
- Delta backend mínimo de contrato para habilitar `/cancelar` (D-10, Opción A): `cancel_url` pasa a `{FRONTEND_URL sin barra final}/cancelar?token=<token>&id=<turno_id>`, sin cambios de endpoints, DB ni migraciones; se actualizan `_cancel_url` y sus 3 call sites y los tests que congelan el formato.
- Cliente API tipado en `shared/`: extiende el `ApiError` y `request<T>` existentes sin romper `getHealth`; guards de respuesta por contrato y sin `any`.
- Manejo de `429` por endpoint (`GET /api/profesionales`, `GET /api/disponibilidad`, `POST /api/turnos`, `DELETE /api/turnos/{id}`) con mensaje de demasiados intentos y espera según `Retry-After`; `404` de profesional inexistente/inactivo con recarga de profesionales; fechas visibles formateadas en `America/Argentina/Buenos_Aires`.
- Estilos con **CSS modules** por componente/página (PB-07 cerrada), manteniendo `styles.css` global para reset y tokens; mobile-first 360px sin zoom ni overflow horizontal, con todos los `*.module.css` verificados (anchos fijos >360 y `min-height:44px`).
- Rutas `/reservar` y `/cancelar` registradas en el shell sin romper S1–S4 de `frontend-shell`.
- Tests Vitest + Testing Library: unit de componentes y de validación, integración de flujos con `fetch` mockeado en el borde, smoke responsive 360px; datos ficticios `.test` y DNI sintéticos.

## Capabilities

### New Capabilities

- `frontend-reserva-publica`: comportamiento de las pantallas públicas de reserva y cancelación — landing con CTA, búsqueda profesional/fecha (con paginación y lista vacía), slots libres, formulario y validación por campo, reserva feliz con resumen y link (`token` + `id` opaco), 400/404/409/422/429, cancelación por token con id localizador, formateo de fechas en `America/Argentina/Buenos_Aires`, estados de carga/error de red, responsive 360px y no exposición de datos sensibles en URL.

### Modified Capabilities

- `frontend-shell`: se agregan las rutas `/reservar` y `/cancelar` al router y se extiende el cliente HTTP compartido, conservando intactos los requisitos S1–S4 del shell (landing, not-found, 360px sin overflow, error tipado).
- `reserva-online`: delta mínimo de contrato (D-10 Opción A) — el `cancel_url` del `201` incluye el `id` opaco del turno (`/cancelar?token=<token>&id=<turno_id>`); el token sigue siendo la única credencial y no cambian el resto de los requisitos.
- `notificaciones-mail`: delta mínimo de contrato (D-10 Opción A) — el link de cancelación del cuerpo del mail es `/cancelar?token=<token>&id=<id>`; se mantienen las 11 claves del payload y el resto de los requisitos.

## Impact

- Frontend: `frontend/src/App.tsx` (rutas), `frontend/src/pages/` (páginas Reservar y Cancelar), `frontend/src/features/reserva/` (componentes y hooks de la reserva), `frontend/src/shared/api/client.ts` (tipos y funciones de reserva/cancelación), estilos `.module.css` nuevos y `styles.css` global (tokens).
- Backend (delta mínimo de contrato, sin endpoints ni DB nuevos): `backend/app/modules/turnos/service.py` (`_cancel_url(token, turno_id)` y sus call sites en `reservar()` y `reprogramar()`), `backend/app/modules/turnos/cancellation_service.py` (payload de cancelación con el nuevo `cancel_url`) y los tests que congelan el formato (`test_reserva_online.py`, `test_cancelacion_paciente.py`). Se consumen sin cambios `GET /api/profesionales`, `GET /api/disponibilidad`, `POST /api/turnos`, `DELETE /api/turnos/{id}?token=`. Sin migraciones.
- Dependencias: ninguna instalación nueva; se usan React 18, Vite 5, React Router 6, Vitest y Testing Library ya presentes.
- Fuera de alcance: reprogramación por paciente (PB-08, v1.1), "mis turnos" por DNI+teléfono (PB-01), login/agenda/recepción staff (C-10), admin y reportes (C-11), Tailwind o librería UI (PB-07 cerrada a CSS modules).
- Governance: **MEDIO**. Riesgo principal: que la UI ofrezca slots que dejan de estar libres (409) o que un error del backend se muestre de forma ambigua. Mitigación: revalidar siempre al reservar, manejar 409 con alternativos del mismo día y 400 por campo, y cubrir los bordes con tests de integración con `fetch` mockeado.
