# Design — c-01-foundation-setup

## Context

See `proposal.md` (Why) for motivation. Current state: greenfield repo — no `backend/`, `frontend/`, compose, or tests. Constraints shaping the approach: KB-08 directory layout, KB-02 stack pins (Python 3.12, FastAPI ≥0.115, SQLAlchemy 2.x, Alembic ≥1.13, Postgres 16, React 18+, Vite 5+, React Router), and AGENTS.md hard rules (Pydantic `extra='forbid'` on API schemas, secrets only via env, `TZ=America/Argentina/Buenos_Aires` + UTC persistence, no commit without order, fictitious data only).

## Goals / Non-Goals

**Goals:**

- Ejecutable mínimo verificable: `docker compose up` levanta web + postgres y `GET /api/health` responde 200; `pytest` y `vitest` verdes en local y en CI-shape (ruff gate).
- Fronteras listas para C-02: layout `core/`, `db/`, `modules/<dominio>/` y `alembic/env.py` cableado al `Base.metadata`, de modo que C-02 solo añade modelos + migración `001`.
- Contrato env completo desde el día 1: las 13 vars de KB-08 + `REDIS_URL` opcional, con fail-fast al boot.

**Non-Goals:**

- Ninguna lógica de dominio, auth, mail, o worker (pertenecen a C-02…C-08; aquí solo stubs/vars).
- Ninguna decisión de stack CSS (diferida a C-09 per PB-07); el shell usa CSS plano mínimo.
- Ningún hardening de producción (TLS, backups, PaaS docs → C-12).

## Decisions

### D-1 — Backend layout: `backend/app/{main.py, core/, db/, modules/}` con routers placeholder registrados

`main.py` crea la app FastAPI, monta un `APIRouter` vacío por dominio futuro (`turnos`, `agenda`, `pacientes`, `profesionales`, `notificaciones`, `auth`, `reportes`) con su prefijo `/api/...` ya fijado, y expone `GET /api/health` directamente (no dentro de un módulo). Cada placeholder vive en `modules/<dominio>/router.py` como `router = APIRouter(prefix=..., tags=[...])` sin rutas.

- *Alternativa considerada*: no crear `modules/` hasta C-02. Rechazada: fijar prefijos ahora evita renombrar rutas públicas en cada change posterior.
- *Aplica*: backend-development (fronteras por router = monolito modular KB-08).

### D-2 — Config con `pydantic-settings`: validación estricta al boot, `extra='ignore'` solo en Settings

`core/config.py` define `Settings(BaseSettings)` con los 13 campos requeridos tipados (`PostgresDsn`/str validado, `int` para puertos/minutos) y `model_config = SettingsConfigDict(extra='ignore', env_file='.env')`. Al importar, campos faltantes lanzan `ValidationError`; `main.py` lo captura y sale con mensaje `Missing required env var(s): ...`.

- *Excepción deliberada a la regla dura 1*: la regla (`extra='forbid'`) aplica a **schemas de API** (todos los request/response de este y futuros changes la usan). En `Settings`, `forbid` rompería el boot ante cualquier variable ajena exportada por el host/CI; `ignore` es la práctica documentada de pydantic-settings. Queda registrado aquí para que ningún apply posterior lo "corrija".
- *Alternativa*: `os.environ` manual. Rechazada: sin tipos ni mensaje uniforme de faltantes.

### D-3 — DB: SQLAlchemy 2.x `DeclarativeBase` + session por request, pool chico

`db/base.py` (`Base`), `db/session.py` (`engine` con `pool_size=5, max_overflow=5` — single-instance PG16, evita agotar conexiones; `sessionmaker` + dependencia FastAPI `get_db` con `try/finally close`). Sin modelos todavía; `Base.metadata` vacío pero importado por `alembic/env.py`.

- *Aplica*: supabase-postgres-best-practices (solo disciplina conexión/migraciones — el proyecto usa SQLAlchemy, no Prisma).

### D-4 — Alembic inicializado sin migraciones de dominio

`alembic init` bajo `backend/alembic/`, `env.py` con `target_metadata = Base.metadata` y URL tomada de `Settings` (nunca hardcodeada). Sin revisiones de dominio; C-02 crea `001_core_models`.

### D-5 — Compose v1: `web` + `db`, stub comentado `worker`/`redis`

`postgres:16-alpine` con volumen nombrado + `healthcheck: pg_isready`; `web` con `build: ./backend`, `depends_on: db (condition: service_healthy)`, `env_file: .env`, `TZ` propagado. Bloque comentado `# worker:` (futura imagen = misma que web, comando scheduler APScheduler) y `# redis:` con nota "solo si se migra a ARQ/Celery (PB-03)".

- *Alternativa*: incluir redis corriendo día 1. Rechazada: viola la regla dura 6 (worker en-proceso en v1).

### D-6 — Frontend shell: Vite 5 + React 18 + `react-router-dom` v6, CSS plano

Scaffold Vite `react-ts`, `src/{features,shared,pages}`, `shared/api/client.ts` (wrapper tipado sobre `fetch`, errores tipados, sin `any`), `pages/{Home,NotFound}`, router con `/` y `*`. Sin framework CSS (decisión en C-09); una hoja de estilo mínima con media-query base 360px.

- *Alternativa*: react-router v7. Rechazada: v6 es la API estable y documentada que el equipo conoce; migrar luego es trivial en un shell.
- *Aplica*: vercel-react-best-practices (imports directos sin barrels, sin componentes anidados, tipado estricto).

### D-7 — Tests base + lint: `pytest`/`httpx`, `ruff`, `Vitest`

Backend: `backend/tests/test_health.py` contra `TestClient(app)` (sin DB — health es liveness puro), `conftest.py` con fixture de app; `ruff` (`lint + format --check`) como gate. Frontend: `src/pages/__tests__/shell.test.tsx` (render `/` y `*` con router en memoria; smoke 360px vía `window.innerWidth` override) — MSW se introduce en C-04/C-05 cuando haya frontera HTTP real (tdd-guide: mock solo en bordes).

- *Aplica*: tdd-guide (un criterio → ≥1 test, docstrings con `# AC-n`), test-guard (`test_<escenario>_<resultado>`, comportamiento no implementación).

## Risks / Trade-offs

- [Riesgo] `extra='ignore'` en Settings podría enmascarar typos en nombres de vars → Mitigación: test de completitud `.env.example` ↔ campos de `Settings` (T-06) falla si divergen.
- [Riesgo] `TestClient` sin DB oculta errores de cableado de engine/session → Mitigación: test de boot valida que `get_db` es importable y el engine se construye con `DATABASE_URL` dummy (sin conectar); la prueba real de conexión llega con C-02 (migración + test DB real).
- [Trade-off] Routers placeholder añaden archivos casi vacíos → aceptado: fijan el contrato de prefijos `/api/...` desde el día 1.
- [Riesgo] Deriva de versiones frontend (Vite/React/RR) → Mitigación: pines mínimos en `package.json` (`^18`, `^5`, `^6`) verificados en el apply con `npm install` limpio.

## Migration Plan

No hay nada que migrar (greenfield, sin datos ni consumidores). Rollback = borrar los directorios creados. Deploy real y docs de PaaS → C-12.

## Open Questions

Ninguna que bloquee el apply. (Stack CSS → C-09; estrategia de seed → C-02.)
