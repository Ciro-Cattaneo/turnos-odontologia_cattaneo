# frontend-shell Specification

## Purpose

Provides a minimal but real single-page application shell (build, router, base layout) on which all future public and staff screens are built, mobile-first starting at 360px width with a shared API client boundary.

## Requirements

### Requirement: Frontend shell builds and serves base routes

The system SHALL ship a frontend app that compiles without errors and serves the public routes `/`, `/reservar` and `/cancelar`, plus the staff routes `/staff/login`, `/staff/agenda` and `/staff/notificaciones` through React Router, with `features/`, `shared/`, and `pages/` directories in place. Staff screens SHALL live under a protected layout that resolves the session before rendering.

#### Scenario: Production build succeeds and landing renders

- **WHEN** the frontend production build runs and the app is served
- **THEN** the build exits zero and visiting `/` renders the landing with CTA without console-breaking errors

#### Scenario: Unknown route shows not-found instead of blank crash

- **WHEN** a user visits an undefined path such as `/no-existe-xyz`
- **THEN** the router renders a not-found state instead of a blank page or uncaught exception

#### Scenario: Reservation route resolves to the reservation page

- **DADO** que el usuario navega a `/reservar`
- **CUANDO** el router resuelve la ruta
- **ENTONCES** se renderiza la página de reserva y no el estado not-found

#### Scenario: Cancellation route resolves to the cancellation page

- **DADO** que el usuario navega a `/cancelar?token=<token>&id=<id>`
- **CUANDO** el router resuelve la ruta
- **ENTONCES** se renderiza la página de cancelación y no el estado not-found

#### Scenario: Login route resolves without the protected layout

- **DADO** que el usuario navega a `/staff/login`
- **CUANDO** el router resuelve la ruta
- **ENTONCES** se renderiza la página de login staff sin resolver sesión ni mostrar la navegación protegida

#### Scenario: Staff agenda route resolves under the protected layout

- **DADO** una sesión staff válida
- **CUANDO** el router resuelve `/staff/agenda`
- **ENTONCES** se renderiza la agenda staff dentro del layout protegido y no el estado not-found

#### Scenario: Staff notifications route resolves under the protected layout

- **DADO** una sesión staff válida de recepción o admin
- **CUANDO** el router resuelve `/staff/notificaciones`
- **ENTONCES** se renderiza el panel de notificaciones fallidas dentro del layout protegido y no el estado not-found (US-009 CA-3, RN-NO-02)

#### Scenario: EDGE — notifications route restricts the panel by role

- **DADO** una sesión staff válida de odontología
- **CUANDO** el router resuelve `/staff/notificaciones` por acceso directo
- **ENTONCES** la ruta se resuelve dentro del layout protegido pero el panel no muestra items ni llama al endpoint y se informa falta de permiso genérica (RN-AU-01, KB-03 RBAC)

#### Scenario: EDGE — staff route without session redirects to login

- **DADO** un usuario sin sesión staff
- **CUANDO** el router resuelve `/staff/agenda` o `/staff/notificaciones`
- **ENTONCES** redirige a `/staff/login` sin renderizar contenido protegido

#### Scenario: EDGE — public routes stay public

- **DADO** un usuario sin sesión staff
- **CUANDO** navega a `/`, `/reservar` o `/cancelar`
- **ENTONCES** las páginas públicas se renderizan sin pedir login ni redirigir a staff

### Requirement: Layout is mobile-first at 360px without horizontal scroll

The shell layout SHALL render at 360px viewport width with no horizontal scrolling and no overlapping interactive elements.

#### Scenario: 360px viewport has no horizontal overflow

- **WHEN** the landing route is rendered at 360×640 viewport
- **THEN** `document.documentElement.scrollWidth` is less than or equal to 360 and all primary actions remain tappable

### Requirement: API client boundary lives in shared layer with typed errors

The system SHALL place the HTTP client in `shared/` with strictly typed responses and errors (no `any`), so feature code never issues raw fetch calls with untyped payloads.

#### Scenario: Failed API call surfaces a typed error

- **WHEN** a feature calls the shared client against an unreachable backend
- **THEN** the caller receives a typed error object (never an untyped throw or `any`) that the UI can render
