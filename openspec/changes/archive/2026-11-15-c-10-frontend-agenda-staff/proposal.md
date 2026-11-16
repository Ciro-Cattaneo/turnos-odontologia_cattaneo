# Proposal — c-10-frontend-agenda-staff

## Why

El backend de staff ya está completo y archivado (C-03 login/RBAC, C-04 agenda, C-07 CRUD de recepción, C-08 panel de fallidas), pero el frontend solo tiene las pantallas públicas de C-09: recepción y odontología no pueden iniciar sesión ni operar la agenda desde el navegador. C-10 cierra ese hueco del camino near-critical de recepción (`C-05 → C-07 → C-10 → C-12`) consumiendo los contratos existentes, sin reabrirlos salvo un delta mínimo de lectura en la agenda.

## What Changes

- **Login staff y sesión**: `/staff/login` con email+password, cookie httpOnly (sin token en JS), `GET /api/auth/me` al montar, layout protegido para rutas `/staff/*`, logout explícito y redirección a login ante cualquier `401`.
- **Agenda multi-profesional día/semana**: `GET /api/profesionales/{id}/agenda`, selector de profesional que consulta solo la agenda elegida, navegación de fecha (±1 día / ±7 días), franjas tipificadas `libre` / `ocupado` (estado + paciente) / `bloqueado` (motivo) y "última actualización" por profesional (US-001, US-002 CA-3).
- **UI de CRUD de recepción**: alta con `origen=recepcion` desde un slot libre, reprogramación y cambio de duración (múltiplos de la granularidad), cancelación normal y **forzada `<3 h` exigiendo motivo**, corrección de DNI/teléfono/obra social con historial auditable, y marcado de `confirmado` / `atendido` / `ausente` mostrando solo las transiciones válidas de RN-TU-07.
- **Panel de notificaciones fallidas**: `/staff/notificaciones` para recepción/admin, con paginación keyset del endpoint de C-08, estado vacío y oculto para odontología.
- **Delta backend mínimo de lectura (sin DB ni endpoints nuevos)**: la agenda staff debe exponer `turno_id` y `duracion_min` en las franjas `ocupado`/`libre` y mostrar los turnos cerrados del día (`atendido`, `ausente`, `cancelado`) como franjas `cerrado`. Sin ese delta la UI no puede abrir la ficha ni marcar asistencia desde la agenda.
- **Reutilización, no reescritura**: cliente HTTP y errores tipados de `shared/api/client.ts`, CSS modules (PB-07), formateo en `America/Argentina/Buenos_Aires` (extraído a `shared/`) y tests Vitest con `fetch` mockeado en el borde. Sin dependencias nuevas.

## Capabilities

### New Capabilities

- `frontend-agenda-staff`: comportamiento de las pantallas staff — sesión y protección de rutas, agenda día/semana por profesional con franjas tipificadas y frescura, alta/reprogramación/cancelación (normal y forzada con motivo) de turnos, corrección de datos con historial, transiciones RN-TU-07 limitadas por rol, panel de fallidas, manejo de 401/403/404/409/422/429 y red, privacidad (sin datos de paciente en URL), fechas en zona del consultorio y mobile-first 360px accesible.

### Modified Capabilities

- `frontend-shell`: el shell pasa a servir también `/staff/login`, `/staff/agenda` y `/staff/notificaciones`, conservando `/`, `/reservar`, `/cancelar` y el not-found; las rutas staff viven bajo un layout protegido.
- `agenda-disponibilidad`: la respuesta staff de `GET /api/profesionales/{id}/agenda` agrega `turno_id` y `duracion_min` a las franjas y devuelve los turnos cerrados del día como `tipo="cerrado"`; la rama pública (solo libres, sin datos de paciente) no cambia.

`staff-auth` **no** se modifica: su contrato backend (login/logout/me, cookie, RBAC) ya cubre C-10; el consumo de esa sesión desde la UI se especifica en `frontend-agenda-staff`.

## Impact

- Frontend: `frontend/src/App.tsx` (registro de rutas staff y anidado bajo `/staff`), `frontend/src/features/staff/pages/` (login, agenda, fallidas), `frontend/src/features/staff/components/` y `frontend/src/features/staff/agenda/` (layout protegido, componentes, hooks y estado de agenda/turnos), `frontend/src/shared/api/staff.ts` (endpoints staff tipados + guards), `frontend/src/shared/session/` (contexto de sesión del layout), `frontend/src/shared/format.ts` (extraído de `features/reserva/format.ts`), `*.module.css` nuevos y `styles.css` (tokens existentes).
- Backend (delta mínimo de lectura, sin endpoints, DB ni migraciones): `backend/app/modules/profesionales/router.py` (`_franjas_staff` y mapeo de franjas `libre`) y los tests de agenda (`backend/tests/test_agenda_staff_vistas.py`, `backend/tests/test_agenda_publica_solo_libres.py` como no-regresión).
- Consumidos sin cambios: `POST /api/auth/login|logout`, `GET /api/auth/me`, `GET /api/profesionales`, `GET /api/profesionales/{id}/agenda`, `POST /api/turnos` (`origen=recepcion`), `PUT /api/turnos/{id}`, `PUT /api/turnos/{id}/paciente`, `PATCH /api/turnos/{id}/estado`, `DELETE /api/turnos/{id}`, `GET /api/turnos/{id}`, `GET /api/notificaciones/fallidas`.
- Dependencias: ninguna instalación nueva (React 18, Vite 5, React Router 6, Vitest y Testing Library ya presentes; sin React Query, sin librería UI, sin `user-event`, sin MSW).
- Fuera de alcance: CRUD de disponibilidades/bloqueos desde la UI (US-002 CA-1/CA-2; el backend existe pero no tiene change de UI asignado — ver Riesgos), admin de profesionales/usuarios y reportes (C-11), reprogramación por paciente (PB-08), Tailwind o cambio de stack CSS (PB-07 cerrada a CSS modules), envío de mails.
- Governance: **MEDIO**. Riesgo principal: ofrecer acciones que el backend rechaza (409 por solape, 422 por transición o motivo faltante) o mostrar una agenda desactualizada. Mitigación: solo se renderizan transiciones válidas por estado+rol, siempre se refresca la agenda tras mutar, la cancelación `<3 h` exige motivo en la UI y el `422 motivo_requerido` del backend reabre el campo como red de seguridad.
