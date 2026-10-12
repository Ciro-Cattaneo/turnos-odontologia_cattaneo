# service-config Specification

## Purpose

Guarantees that every deployment of the appointment system is configured exclusively through environment variables, with a versioned example file covering all required settings and a fast, explicit failure when any required value is missing at boot.

## Requirements

### Requirement: Versioned example env file covers all required variables

The system SHALL ship a versioned `.env.example` listing every required variable from KB-08 (`DATABASE_URL, SECRET_KEY, ADMIN_EMAIL, ADMIN_PASSWORD, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, TZ, CANCEL_HOURS_MIN, SLOT_DEFAULT_MIN, FRONTEND_URL`) with non-secret placeholder values, plus `REDIS_URL` documented as optional/commented; the real `.env` file SHALL be git-ignored and no secret SHALL appear in the repo.

#### Scenario: Completeness check of example env file

- **WHEN** a reviewer compares `.env.example` keys against the KB-08 variable table
- **THEN** every required variable is present with a placeholder value and no real secret, and `REDIS_URL` appears only as an optional commented entry

#### Scenario: No secrets leak into the repository

- **WHEN** the repo is scanned for secret patterns (passwords, SMTP credentials, session keys) outside `.env.example` placeholders and test fixtures
- **THEN** no real credential value is found in versioned files

### Requirement: Service fails fast on missing required configuration

The system SHALL validate required environment variables at boot and refuse to start with a clear error naming the missing variable (exit non-zero, message includes the variable name).

#### Scenario: Missing required variable blocks boot with a clear error

- **WHEN** the API starts without `SECRET_KEY` set
- **THEN** the process exits non-zero before serving traffic and logs an error naming `SECRET_KEY`

#### Scenario: Default operational values apply when documented

- **WHEN** the API starts with all required variables set and `TZ=America/Argentina/Buenos_Aires`
- **THEN** the process boots, reports the configured timezone, and applies documented defaults (`CANCEL_HOURS_MIN=3`, `SLOT_DEFAULT_MIN=30`) when those optional tunables are unset

### Requirement: Timestamps persist in UTC and display in local zone

The system SHALL persist all timestamps in UTC and convert to `America/Argentina/Buenos_Aires` only at display/API-serialization boundaries.

#### Scenario: Stored timestamp is UTC regardless of operating zone

- **WHEN** the service runs with `TZ=America/Argentina/Buenos_Aires` and records an event at local 10:00 (UTC-3)
- **THEN** the persisted value equals 13:00 UTC and API responses render it back as 10:00 local
