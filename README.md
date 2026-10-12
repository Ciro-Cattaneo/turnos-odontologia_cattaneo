# Turnos Odontología Cattaneo

Sistema de gestión de turnos para consultorio odontológico (Metodología I).
Estado: `C-01 foundation-setup` archivado; resto del plan en `CHANGES.md`.

> Nota de layout: el enunciado mínimo pide `src/` + `tests/`, pero este proyecto usa
> `backend/` (app, alembic, tests, Dockerfile, requirements) + `frontend/` (src,
> package.json) según `knowledge-base/08_arquitectura_propuesta.md` §Estructura y
> `CHANGES.md` C-01. `backend/tests/` equivale a `tests/` del backend;
> `frontend/src/pages/__tests__/` a `tests/` del frontend.

## Prerrequisitos

| Herramienta | Versión | Notas |
|---|---|---|
| Python | 3.12 (Docker fija `python:3.12-slim`; local 3.12+ funciona) | Backend + tests |
| Node + npm | Node 18+, npm 9+ | Frontend + Vitest |
| Docker Desktop | Opcional por ahora | Solo para Postgres/compose; ver §Docker |

TZ: `America/Argentina/Buenos_Aires`; en DB se persiste UTC.

## Instalación

Backend (desde la raíz del repo, PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
```

Frontend (desde `frontend/`):

```powershell
npm install
```

`.env` está gitigneado y `.env.example` trae solo placeholders ficticios: completar los valores locales tras copiar (nunca commitear `.env`).

## Tests y checks

En este host las herramientas Python NO están en PATH: usar siempre `python -m`
(`ruff` y `alembic` directos fallan; verificado).

Backend (desde la raíz):

```powershell
python -m pytest backend/tests/              # 29 tests
python -m ruff check backend/                # lint (config en backend/pyproject.toml)
python -m ruff format --check backend/       # formato
python -m alembic -c backend/alembic.ini heads  # sin salida + exit 0 = ok (aún sin migraciones de dominio)
```

Secretos (sin herramienta dedicada en el repo): el test estático
`backend/tests/test_env_example.py` verifica que `.env.example` cubra las 13 vars
de KB-08 y no contenga secretos reales; además `.env` debe seguir ignorado:

```powershell
python -m pytest backend/tests/test_env_example.py
git check-ignore -v .env   # debe mostrar .gitignore:3:.env
```

Frontend (desde `frontend/`; scripts exactos en `package.json`: `dev`, `build`,
`preview`, `test` — no existe script `lint`):

```powershell
npm test        # = npx vitest run, 5 tests
npm run build   # tsc -b + vite build
```

Arranque local sin Docker (opcional, desde `backend/` con `.env` cargado):

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000  # salud: GET /api/health -> {"status": "ok"}, sin auth ni DB
```

## Docker (PENDING en este host)

Ruta primaria cuando haya Docker Desktop (servicios `web`+`db` Postgres 16;
`worker`/`redis` solo stubs comentados por regla dura 6):

```powershell
docker compose config
Copy-Item .env.example .env
docker compose up -d
curl.exe -f http://localhost:8000/api/health
docker compose down
```

PENDING: en este host Docker no está instalado (virtualización de firmware
desactivada, sin acceso a BIOS). El YAML solo se validó estructuralmente; los
29 pytest + ruff + 5 vitest + `npm run build` sí están verdes. Re-ejecutar el
smoke Docker en máquina con Docker antes de darlo por verde. Detalle en
`openspec/changes/archive/2026-10-12-c-01-foundation-setup/tasks.md`.

## Estructura del repo

```text
backend/            # FastAPI: app/ (main, core, db, modules/*), alembic/, tests/, Dockerfile, requirements.txt
frontend/           # React 18 + Vite 5 + React Router: src/{features,shared,pages}, package.json
docker-compose.yml  # web (8000) + db (Postgres 16); worker/redis comentados
.env.example        # 13 vars KB-08 + REDIS_URL opcional comentada (placeholders ficticios)
docs/discovery/     # informe de discovery previo
knowledge-base/     # fuente de verdad del dominio (01-10 + README)
openspec/           # changes (activos + archive/2026-10-12-c-01-foundation-setup)
CHANGES.md          # índice canónico de changes C-01..C-12
AGENTS.md           # instrucciones para agentes (contrato)
```

## Reglas para agentes

Leer `AGENTS.md` antes de tocar código: 12 reglas duras (contrato, prevalecen
sobre la KB) + flujo `/opsx:propose` → implementar → `/opsx:archive`.

## Datos

Solo datos ficticios en repo, ejemplos, tests y capturas (Ley 25.326, regla 12).
Prohibido commitear secretos o datos reales de pacientes (reglas 10 y 12).
