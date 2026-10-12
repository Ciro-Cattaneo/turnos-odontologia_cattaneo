# Spec Delta

## Purpose

Provides a minimal but real single-page application shell (build, router, base layout) on which all future public and staff screens are built, mobile-first starting at 360px width with a shared API client boundary.

## ADDED Requirements

### Requirement: Frontend shell builds and serves base routes

The system SHALL ship a frontend app that compiles without errors and serves at least a landing route (`/`) through React Router, with `features/`, `shared/`, and `pages/` directories in place for future work.

#### Scenario: Production build succeeds and landing renders

- **WHEN** the frontend production build runs and the app is served
- **THEN** the build exits zero and visiting `/` renders the landing placeholder without console-breaking errors

#### Scenario: Unknown route shows not-found instead of blank crash

- **WHEN** a user visits an undefined path such as `/no-existe-xyz`
- **THEN** the router renders a not-found state instead of a blank page or uncaught exception

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
