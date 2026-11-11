# Spec Delta

## MODIFIED Requirements

### Requirement: Frontend shell builds and serves base routes

The system SHALL ship a frontend app that compiles without errors and serves the routes `/`, `/reservar` and `/cancelar` through React Router, with `features/`, `shared/`, and `pages/` directories in place for future work.

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
