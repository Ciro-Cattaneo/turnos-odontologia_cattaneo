# Descripción General

## Stack tecnológico

Decisión Ronda 1 (P4 = c) + prioridad costo mínimo (P5 = d). Monolito modular, single host / PaaS barato, Postgres single-instance.

| Capa | Tecnologías | Versión mínima |
|------|--------------|----------------|
| Backend API | Python + FastAPI (monolito modular, routers por dominio) | Python 3.12, FastAPI ≥0.115 |
| ORM / migraciones | SQLAlchemy 2.x + Alembic | 2.0 / 1.13 |
| Base de datos | Postgres single-instance (sin réplica en v1) | Postgres 16 |
| Workers / colas | APScheduler en-proceso, loop single-process 5–10 min (PB-03; `REDIS_URL` solo documentada); escalar a ARQ/Celery + Redis solo si el volumen lo exige | APScheduler en-proceso |
| Envío de mail | SMTP Gmail provisorio + app password (migrable — PB-05) vía cola con reintentos | — |
| Frontend | React + Vite + React Router, responsive mobile-first, sin framework UI pesado (CSS modules o Tailwind a confirmar) | React 18+, Vite 5+ |
| Auth staff | Sesión por token (JWT httpOnly o session cookie) para recepción/odontólogo/admin; paciente sin login en v1 | — |
| Deploy v1 | Single host (Docker Compose: web + worker + Postgres) o PaaS barato (ej. Railway/Render/Fly single instance) | Docker 24+ |
| Tests / lint | pytest + httpx (backend), Vitest (frontend), ruff | — |

**Suposición:** equipo chico sin DevOps dedicado; por eso single host + Compose antes que Kubernetes o multi-servicio.

## Arquitectura general

```
Paciente (móvil web) ─┐
                       ├─→ React SPA ─→ FastAPI monolito modular ─→ Postgres
Staff (recepción/     ─┘         │                │
odontólogo, web)                 │                └─→ Worker/cola (recordatorios mail, reintentos)
                                 └─→ SMTP transaccional
```

- Monolito modular: un deployable, módulos `pacientes`, `profesionales`, `agenda/disponibilidad`, `turnos`, `notificaciones`, `auth/usuarios`. Puerta a WA/MP como nuevos módulos + columnas `canal_preferido` / `estado_pago` reservadas, sin implementar la lógica en v1.
- Sincrónico para reserva/cancelación (validación de solapamiento en transacción DB con lock por profesional+slot). Asincrónico solo para mails (encolado fire-and-forget con reintento).
- Single tenant: sin `tenant_id` en v1 (una DB = un consultorio). Si multi-consultorio llega, se migra a `tenant_id` o DB por tenant — decisión post-v1 documentada en 09.

## Integraciones externas

| Servicio | Propósito | Tipo |
|----------|-----------|------|
| SMTP transaccional | Recordatorios y confirmaciones por mail (v1) | SMTP / REST según proveedor |
| (Reservado) WhatsApp Business API | Recordatorios con confirmar/cancelar — POST-v1, solo interfaz/puerta | REST webhook (futuro) |
| (Reservado) Mercado Pago | Seña / cobro anticipado — POST-v1, solo interfaz/puerta | REST + webhook (futuro) |
| (Reservado) Padrón OS (PUCO u otro) | Validación de cobertura — POST-v1 | REST (futuro) |

v1 no integra nada salvo mail. Las filas "reservado" existen para no sobrediseñar pero tampoco bloquear: se dejan puntos de extensión (`NotificationChannel` enum extensible, `pago_estado` nullable) sin código muerto.

## API REST (resumen v1)

Agrupada por recurso (detalle de contratos en 07_flujos_principales.md; OpenAPI autogenerada por FastAPI):

- `GET /api/disponibilidad?profesional_id=&desde=&hasta=` — slots libres (público, rate-limited).
- `POST /api/turnos` (público) — reserva con nombre+DNI+teléfono+OS+mail obligatorios (mail OBLIGATORIO — PB-02); valida solapamiento en transacción.
- `DELETE /api/turnos/{id}?token=` — cancela paciente si ≥3h (única credencial `token_cancelacion` — PB-01; 403 genérico).
- `GET /api/profesionales` + `GET /api/profesionales/{id}/agenda?dia|semana=` — agenda por profesional.
- Staff (auth): `POST /api/auth/login`, `GET/POST/PUT/DELETE /api/turnos` (CRUD + forzar), `PUT /api/disponibilidad` (mantener horarios), `GET /api/reportes/ocupacion` básico.
- `GET /api/health` — liveness para PaaS.
