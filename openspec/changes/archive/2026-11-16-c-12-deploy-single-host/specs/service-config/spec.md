# Spec Delta — service-config

## MODIFIED Requirements

### Requirement: Versioned example env file covers all required variables

The system SHALL ship a versioned `.env.example` listing every required variable from KB-08 (`DATABASE_URL, SECRET_KEY, ADMIN_EMAIL, ADMIN_PASSWORD, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, TZ, CANCEL_HOURS_MIN, SLOT_DEFAULT_MIN, FRONTEND_URL`), the operational variables (`SMTP_TIMEOUT_S`, `NOTIF_WORKER_ENABLED`, `NOTIF_WORKER_INTERVAL_MIN`, `NOTIF_WORKER_BATCH_SIZE`, `CONSULTORIO_CONTACTO`), and `REDIS_URL` documented as optional/commented; every value SHALL be a fictitious placeholder, the real env file SHALL be git-ignored and no secret SHALL appear in the repo.

#### Scenario: Completeness check of example env file

- **WHEN** a reviewer compares `.env.example` keys against the KB-08 variable table
- **THEN** every required variable is present with a placeholder value and no real secret, and `REDIS_URL` appears only as an optional commented entry

#### Scenario: No secrets leak into the repository

- **WHEN** the repo is scanned for secret patterns (passwords, SMTP credentials, session keys) outside `.env.example` placeholders and test fixtures
- **THEN** no real credential value is found in versioned files

#### Scenario: FELIZ — Las variables operativas de producción están documentadas

- **DADO** el `.env.example` versionado y la tabla de variables de la KB-08
- **CUANDO** se comparan las claves del archivo con las variables requeridas y las del worker
- **ENTONCES** están todas presentes, `TZ` documenta `America/Argentina/Buenos_Aires`, `CANCEL_HOURS_MIN=3` y `SLOT_DEFAULT_MIN=30`, y cada valor es un placeholder obviamente ficticio (regla dura 10)

#### Scenario: BORDE — El placeholder de SECRET_KEY es reconocible como no productivo

- **DADO** el `.env.example` versionado
- **CUANDO** se inspecciona el valor de `SECRET_KEY` y las credenciales de `ADMIN_*`/`SMTP_*`
- **ENTONCES** los valores tienen un marcador de placeholder (`changeme-*`, `*-ejemplo`) que el arranque en producción rechaza, y `DATABASE_URL` usa un host interno de ejemplo (`db`)

### Requirement: Service fails fast on missing required configuration

The system SHALL validate required environment variables at boot and refuse to start with a clear error naming every missing variable (exit non-zero, no secret values printed), and in production SHALL also reject known placeholder credentials and a weak `SECRET_KEY`.

#### Scenario: Missing required variable blocks boot with a clear error

- **WHEN** the API starts without `SECRET_KEY` set
- **THEN** the process exits non-zero before serving traffic and logs an error naming `SECRET_KEY`

#### Scenario: Default operational values apply when documented

- **WHEN** the API starts with all required variables set and `TZ=America/Argentina/Buenos_Aires`
- **THEN** the process boots, reports the configured timezone, and applies documented defaults (`CANCEL_HOURS_MIN=3`, `SLOT_DEFAULT_MIN=30`) when those optional tunables are unset

#### Scenario: ERROR — Faltan varias variables y se nombran todas

- **DADO** un entorno sin `SECRET_KEY` ni `SMTP_PASS`
- **CUANDO** se importa la aplicación
- **ENTONCES** el proceso termina con código distinto de 0 y el mensaje nombra ambas variables faltantes, ordenadas, sin imprimir ningún valor (regla dura 10)

#### Scenario: ERROR — Un placeholder en producción bloquea el arranque

- **DADO** `ENV=prod` y `SECRET_KEY` con un placeholder conocido (`changeme-*`) o de longitud débil
- **CUANDO** se importa la aplicación
- **ENTONCES** el proceso termina con código distinto de 0 nombrando `SECRET_KEY`, sin exponer el valor configurado

#### Scenario: BORDE — En desarrollo sigue permitiendo placeholders locales

- **DADO** `ENV=development` (o ausente) y variables requeridas presentes con placeholders locales
- **CUANDO** se importa la aplicación
- **ENTONCES** el proceso arranca normalmente, porque la validación de placeholders solo aplica a producción

## ADDED Requirements

### Requirement: API restricts CORS to the configured frontend origin

The API SHALL allow cross-origin requests only from the origin configured in `FRONTEND_URL`, echoing that origin with credentials allowed, and SHALL NOT grant cross-origin access to any other origin.

#### Scenario: FELIZ — Un preflight desde FRONTEND_URL es aceptado

- **DADO** la API configurada con `FRONTEND_URL=https://turnos.ficticio.test`
- **CUANDO** se envía `OPTIONS /api/turnos` con `Origin: https://turnos.ficticio.test`
- **ENTONCES** responde con éxito y las cabeceras `access-control-allow-origin` igual a ese origen y `access-control-allow-credentials: true`

#### Scenario: ERROR — Un origen ajeno no recibe permiso CORS

- **DADO** la API configurada con `FRONTEND_URL=https://turnos.ficticio.test`
- **CUANDO** un preflight llega con `Origin: https://malicioso.test`
- **ENTONCES** la respuesta no incluye `access-control-allow-origin` para ese origen (el navegador bloquea la lectura) y el preflight es rechazado

#### Scenario: BORDE — Una request same-origin sin cabecera Origin no se ve afectada

- **DADO** la SPA servida por la misma aplicación (sin CORS en juego)
- **CUANDO** se hace `GET /api/health` sin cabecera `Origin`
- **ENTONCES** responde `200` normalmente, igual que antes de configurar CORS
