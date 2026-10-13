# Arquitectura Propuesta

Costo mínimo manda: un deployable, una DB, worker liviano, single host. Nada de microservicios, nada de réplicas en v1.

## Patrones aplicados

| Patrón | Dónde se usa | Por qué |
|--------|--------------|---------|
| Monolito modular | Backend FastAPI (routers `turnos`, `agenda`, `pacientes`, `profesionales`, `notificaciones`, `auth`) | Un deploy, fronteras claras; equipo chico sin DevOps |
| Transacción + lock pesimista / exclusión PG | Creación/reprogramación de turnos | Garantiza RN-TU-03 bajo concurrencia sin infra extra |
| Cola liviana + worker | Recordatorios mail (APScheduler default; ARQ/Celery+Redis solo si escala) | No bloquea la reserva; reintentos sin operador |
| Token opaco por turno | `token_cancelacion` para ver/cancelar sin login | Seguridad suficiente sin cuentas paciente en v1 |
| RBAC simple | Middleware por rol en routers staff | Suficiente para <50 personas; sin ABAC |
| Enum extensible | `canal_recordatorio`, `pago_estado` nullable | Puerta WA/MP sin sobrediseño ni código muerto |

## Estructura de directorios

```
turnos-odontologia_cattaneo/
├── backend/
│   ├── app/
│   │   ├── main.py (FastAPI, routers, health)
│   │   ├── core/ (config, seguridad, deps, rate-limit)
│   │   ├── modules/
│   │   │   ├── turnos/ (router, service, schemas)
│   │   │   ├── agenda/ (disponibilidad, bloqueos, slots)
│   │   │   ├── pacientes/ | profesionales/ | notificaciones/ (sender mail) | auth/ | reportes/
│   │   ├── db/ (base, session, models)
│   │   └── worker/ (scheduler, send_mail, retry)
│   ├── alembic/ (migraciones)
│   ├── tests/ (pytest: anti-solape, cancela 3h, recordatorios)
│   └── Dockerfile
├── frontend/
│   └── src/
│       ├── features/ (reserva, agenda, recepcion, admin)
│       ├── shared/ (api client, ui, hooks)
│       └── pages/ (publicas + staff)
├── docker-compose.yml (web + worker + postgres + [redis opcional])
└── knowledge-base/ openspec/ docs/discovery/
```

## Seguridad

- Autenticación: staff con email+password hasheado (bcrypt/argon2) + cookie httpOnly; paciente sin cuenta (token por turno). Sin OAuth en v1.
- Autorización: dependencia `require_role(...)` por router; odontólogo solo su `profesional_id`.
- Validación de input: schemas Pydantic estrictos (nombre/DNI/tel/OS/mail los 5 obligatorios — PB-02; mail formato válido); 400 con detalle por campo.
- Anti-abuso: rate-limit en `POST /api/turnos` y `GET /api/disponibilidad` (ej. 30 req/min/IP); mensaje de cancelación genérico para no enumerar turnos.
- Secrets management: todo secreto por env vars (nunca en repo); `.env.example` versionado, `.env` ignorado.
- Datos personales (Ley 25.326): declaración mínima en v1 (finalidad, conservación, no cesión); cifrado en tránsito (TLS del PaaS); backups diarios del Postgres a disco local del host con retención 7 días (Gmail + host-disk provisorios — PB-05).

## Variables de entorno

| Variable | Descripción | Ejemplo | Sensible |
|----------|-------------|---------|----------|
| `DATABASE_URL` | DSN Postgres | `postgresql+psycopg://user:pass@db:5432/turnos` | Y |
| `SECRET_KEY` | Firma de sesión/tokens | (openssl rand -hex 32) | Y |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Admin inicial (rotar al primer login) | `admin@cattaneo.com` / temporal | Y |
| `SMTP_HOST/PORT/USER/PASS/FROM` | Envío de mails (Gmail provisorio + app password — PB-05, migrable) | `smtp.gmail.com:587` | Y (pass) |
| `TZ` | Zona horaria operativa | `America/Argentina/Buenos_Aires` | N |
| `CANCEL_HOURS_MIN` | Anticipación mínima cancelación | `3` | N |
| `SLOT_DEFAULT_MIN` | Duración default | `30` | N |
| `FRONTEND_URL` | Origen permitido CORS + links de mail | `https://turnos.cattaneo.com` | N |
| `REDIS_URL` | Solo si worker pasa a ARQ/Celery | `redis://redis:6379/0` | Y |
