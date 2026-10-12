# Spec Delta

## Purpose

Exposes a stable liveness endpoint so PaaS platforms, docker-compose smoke checks, and future monitoring can verify the API process is alive without authentication or database access.

## ADDED Requirements

### Requirement: Health endpoint returns liveness status

The system SHALL expose unauthenticated `GET /api/health` returning HTTP 200 with a JSON body containing at least a status field signalling the process is alive.

#### Scenario: Healthy process answers liveness probe

- **WHEN** a client sends `GET /api/health` with no credentials
- **THEN** the system responds HTTP 200 with a JSON body where `status` equals `"ok"`

#### Scenario: Health check does not require authentication

- **WHEN** a client sends `GET /api/health` without any session cookie or token
- **THEN** the system responds HTTP 200 (never 401/403)

#### Scenario: Health check works without database connectivity

- **WHEN** the API process is running but the database is unreachable
- **THEN** `GET /api/health` still responds HTTP 200 (liveness only; readiness/deep checks are out of scope)
