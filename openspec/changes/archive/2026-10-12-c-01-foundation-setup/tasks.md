# Tasks — c-01-foundation-setup

> Ciclo TDD estricto en TODAS las tareas con código: RED (test que falla) → GREEN (mínimo para pasar) → TRIANGULATE (2º ejemplo que rompa la solución ingenua) → REFACTOR (en verde). Referenciar el AC del spec en el docstring del test (ej. `# AC service-health/S1`).

## 1. Backend core: config + app + health

- [x] 1.1 Crear `backend/app/core/config.py` (`Settings` con las 13 vars KB-08 + `REDIS_URL` opcional, fail-fast nombrando la faltante) con TDD — test: `backend/tests/test_config.py` (capa: unit) — verificar: `pytest backend/tests/test_config.py` verde incl. `# AC service-config/S3` (falta `SECRET_KEY` → error que la nombra) y `# AC service-config/S4` (defaults `CANCEL_HOURS_MIN=3`, `SLOT_DEFAULT_MIN=30`).
- [x] 1.2 Crear `backend/app/main.py` (app FastAPI, `GET /api/health` → `{"status": "ok"}`, routers placeholder `modules/*/router.py` registrados con prefijos `/api/...`) con TDD — test: `backend/tests/test_health.py` (capa: API/contract, `httpx` sin DB) — verificar: `pytest backend/tests/test_health.py` verde incl. `# AC service-health/S1` (200 + `status=ok`), `# AC service-health/S2` (sin auth) y `# AC service-health/S3` (sin DB).
- [x] 1.3 Añadir `backend/requirements.txt` (pines: Python 3.12, FastAPI ≥0.115, pydantic-settings, sqlalchemy 2.x, alembic ≥1.13, pytest+httpx, ruff) + config `ruff` — verificar: `pip install -r backend/requirements.txt` limpio y `ruff check backend/ && ruff format --check backend/` verde.

## 2. DB + Alembic (sin modelos de dominio)

- [x] 2.1 Crear `backend/app/db/{base.py,session.py}` (`Base`, engine `pool_size=5`, `get_db` con cierre) + inicializar `backend/alembic/` (`env.py` con `target_metadata=Base.metadata` y URL desde `Settings`) — test: `backend/tests/test_db_wiring.py` (capa: wiring/integration, sin conectar: engine se construye con `DATABASE_URL` dummy, `get_db` importable, `env.py` importa `Base`) — verificar: `pytest backend/tests/` verde y `alembic -c backend/alembic.ini heads` corre sin error.

## 3. Compose + env + Dockerfile

- [x] 3.1 Escribir `.env.example` (13 vars KB-08 con placeholders no-secretos + `REDIS_URL` opcional comentada), añadir `.env` a `.gitignore`, escribir `backend/Dockerfile` (python:3.12-slim, instala requirements, `uvicorn app.main:app`) — test: `backend/tests/test_env_example.py` (capa: static/contract — parsea `.env.example` y lo compara contra los campos de `Settings`) — verificar: `pytest` verde incl. `# AC service-config/S1` (completitud) y `# AC service-config/S2` (sin secretos reales), más `docker build ./backend` exitoso.
- [x] 3.2 Escribir `docker-compose.yml` (`web` + `db` postgres:16-alpine con volumen nombrado y `healthcheck pg_isready`, `depends_on` healthy, `env_file: .env`; bloques comentados `worker`/`redis` con nota PB-03) — verificar: `docker compose config` válido y `docker compose up -d && curl -f http://localhost:8000/api/health` → 200 (smoke `# AC service-health/S1` E2E), luego `docker compose down`.

## 4. Frontend shell

- [x] 4.1 Scaffold Vite react-ts en `frontend/` (`package.json` pines React ^18, Vite ^5, react-router-dom ^6), estructura `src/{features,shared,pages}`, `shared/api/client.ts` (wrapper `fetch` tipado, errores tipados, sin `any`), `pages/{Home,NotFound}`, router `/` + `*`, CSS plano mínimo 360px — tests: `frontend/src/pages/__tests__/shell.test.tsx` (Vitest, router en memoria; capa: component) — verificar: `npm run build` exit 0 y `npx vitest run` verde incl. `# AC frontend-shell/S1` (landing render), `# AC frontend-shell/S2` (not-found), `# AC frontend-shell/S3` (sin overflow a 360px) y `# AC frontend-shell/S4` (error tipado con backend caído).

## 5. Verificación integrada del change

- [x] 5.1 Corrida verde completa + validación OpenSpec — verificar: `pytest backend/tests/`, `ruff check backend/`, `npx vitest run`, `docker compose up` smoke health 200, y `openspec validate --change c-01-foundation-setup` sin errores; dejar constancia del reporte (qué AC cubre cada test) en el resumen del apply.

## Workflow follow-up

- Archivar el change (`/opsx:archive`) tras la revisión humana y marcar `[x] C-01` en CHANGES.md.
- C-02 (`core-models`) queda desbloqueado: consume `db/base`, `alembic/env.py` y prefijos de routers fijados aquí.

## Archive note — pending Docker verification (2026-10-12)

> PENDING (NOT verified green): Docker Desktop could NOT be installed on this
> host — firmware virtualization (AMD-V/SVM) is disabled and the user cannot
> access BIOS (both `shutdown /r /fw` and Recovery→UEFI paths failed).
> Therefore these verifications were NOT run: `docker build ./backend`
> (tasks 3.1/5.1), `docker compose config` + smoke
> `docker compose up -d && curl -f http://localhost:8000/api/health → 200 && docker compose down`
> (tasks 3.2/5.1). The compose YAML was validated structurally (PyYAML) only;
> all other verifications passed (29 pytest, ruff clean, 5 vitest, `npm run build`
> exit 0, `openspec validate` valid). RE-RUN the Docker verifications in C-12
> (deploy-single-host) or on a Docker-capable machine before treating tasks
> 3.1/3.2/5.1 Docker items as green. Do NOT mark them verified-green from this archive.
