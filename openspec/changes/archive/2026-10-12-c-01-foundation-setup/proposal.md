# Proposal — c-01-foundation-setup (C-01 per CHANGES.md)

## Why

El repo está en estado greenfield: no existen `backend/`, `frontend/`, `docker-compose.yml`, ni tests. Sin un esqueleto ejecutable y verificable, ningún change de dominio (C-02 en adelante) puede construirse ni testearse. C-01 es el enabler GATE 0 del plan: un solo change chico del MVP que desbloquea todo el camino crítico `C-01 → C-02 → C-04 → C-05 → C-08 → C-09 → C-12`.

## What Changes

- Scaffolding backend `backend/app/main.py` (FastAPI, routers vacíos por dominio, `GET /api/health`), `core/` (config por env + rate-limit base), `db/` (base + session).
- Scaffolding frontend `frontend/` (React 18+ + Vite 5 + React Router; carpetas `features/`, `shared/`, `pages/` creadas, vacías o con placeholder mínimo).
- `docker-compose.yml` (servicios `web` + `postgres`; `worker`/`redis` solo como bloque comentado — NO hay worker en C-01).
- `.env.example` versionado con las 13 vars de KB-08 (`DATABASE_URL, SECRET_KEY, ADMIN_EMAIL, ADMIN_PASSWORD, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, TZ, CANCEL_HOURS_MIN, SLOT_DEFAULT_MIN, FRONTEND_URL` + `REDIS_URL` opcional comentada); `.env` agregado a `.gitignore`.
- Alembic inicializado (estructura + `env.py` cableado a `db/`, sin migraciones de dominio); `backend/Dockerfile` (Python 3.12 slim, instala deps, corre uvicorn).
- Tests base verdes: `pytest + httpx` (health 200), `ruff` configurado, `Vitest` configurado con smoke test del shell.
- Explícitamente FUERA de scope: modelos de dominio (C-02), auth/RBAC (C-03), lógica de agenda/reserva (C-04/C-05), envío real de mail (solo vars SMTP), worker APScheduler (solo stub comentado), CSS stack final (se decide en C-09 per PB-07).

Nota de explore: repo greenfield verificado — no hay `src/`, `tests/`, ni `README.md`; `openspec list` vacío (sin changes ni specs previos). No se genera doc de explore separado; este hallazgo queda registrado aquí.

## Capabilities

### New Capabilities

- `service-health`: contrato del endpoint liveness `GET /api/health` (200 + forma JSON estable) que los deploys PaaS y el smoke de compose usan como señal de vida.
- `service-config`: contrato de configuración por variables de entorno — completitud de `.env.example` contra KB-08, `TZ=America/Argentina/Buenos_Aires` con persistencia UTC, y fallo rápido y claro al boot si falta una requerida.
- `frontend-shell`: shell SPA mínimo — la app frontend compila, el router monta las rutas base, y el layout cumple mobile-first 360px sin scroll horizontal.

### Modified Capabilities

(none — repo greenfield, sin specs previas)

## Impact

- Crea `backend/`, `frontend/`, `docker-compose.yml`, `.env.example`, `backend/Dockerfile`, `backend/alembic/` — todo nuevo, sin breaking changes (no hay consumidores previos).
- Desbloquea C-02 (`core-models`): Alembic + session + layout de módulos listos para recibir modelos.
- Riesgo bajo (governance BAJO): solo scaffolding; las reglas duras 1 (Pydantic `extra='forbid'`), 10 (secretos solo por env) y 12 (datos ficticios) aplican desde este change y quedan fijadas en design/specs.
