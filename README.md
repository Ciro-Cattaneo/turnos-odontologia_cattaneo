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

## Demo local (1 comando)

Doble clic en `demo.cmd` (raíz del repo) o, desde PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\iniciar-demo.ps1
```

Qué hace el script: verifica Python y las dependencias del backend (instala
`backend/requirements.txt` solo si falta algo), crea `.env` desde `.env.example`
si no existe, reescribe `DATABASE_URL` al host `127.0.0.1` si venía con el host
`db` del compose (conserva usuario/password/base), fuerza
`NOTIF_WORKER_ENABLED=false` y `FRONTEND_URL=http://localhost:<puerto>`, aplica
migraciones Alembic, carga datos ficticios idempotentes (admin, 3 profesionales,
horarios y turnos), compila la SPA en `static/` si hace falta y arranca API + SPA
en el mismo origen.

- URL: `http://localhost:8000` (SPA y API en el mismo host/puerto).
- Credenciales staff: salen de `.env` (`ADMIN_EMAIL` / `ADMIN_PASSWORD`); el
  banner del script las muestra al iniciar. No las escribas en el repo.
- Opciones: `-Port 8010`, `-NoBrowser`, `-Rebuild`.
- Detener: `Ctrl+C` o cerrar la ventana.
- Todos los datos son ficticios (`@ficticio.test`, DNI sintéticos; Ley 25.326).

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

`.env` está ignorado por git y `.env.example` trae solo placeholders ficticios: completar los valores locales tras copiar (nunca commitear `.env`).

## API interactiva (Swagger)

La API expone su documentación OpenAPI generada por FastAPI, sin autenticación:

| Ruta | Qué es |
|------|--------|
| `/docs` | Swagger UI (probar los endpoints desde el navegador) |
| `/redoc` | ReDoc (lectura) |
| `/openapi.json` | Especificación OpenAPI 3.1 |

Con la demo o el compose levantados: <http://localhost:8000/docs>. Los endpoints
`/api/auth/*` y el resto de `/api/staff/*` requieren sesión: primero
`POST /api/auth/login` (cookie httpOnly) y después probar el resto desde el mismo
navegador. `/api/health` responde sin auth ni DB.

## Tests y checks

En este host las herramientas Python NO están en PATH: usar siempre `python -m`
(`ruff` y `alembic` directos fallan; verificado).

Backend (desde la raíz; requiere Postgres local corriendo y `.env` creado desde
`.env.example`; `pytest` usa la base real `turnos_test`, la crea/borra a partir
del `DATABASE_URL` de `.env` y aplica las migraciones):

```powershell
python -m pytest backend/tests/ -q          # 782 tests (incluye los de contrato de deploy y SPA)
python -m ruff check backend/               # lint (config en backend/pyproject.toml)
python -m ruff format --check backend/      # formato
python -m alembic -c backend/alembic.ini heads   # 002_agenda_meta (head)
```

Los tests de SPA/deploy no requieren Docker ni un build de la SPA: la suite fija
`STATIC_DIR` a un directorio inexistente y cada caso monta el suyo. Tampoco
dependen de que `static/` exista (si la demo lo generó, no afecta).

Secretos (sin herramienta dedicada en el repo): el test estático
`backend/tests/test_env_example.py` verifica que `.env.example` cubra las 13 vars
de KB-08 y no contenga secretos reales; además `.env` debe seguir ignorado:

```powershell
python -m pytest backend/tests/test_env_example.py
git check-ignore -v .env   # debe mostrar la línea de .gitignore que lo ignora
```

Frontend (desde `frontend/`; scripts exactos en `package.json`: `dev`, `build`,
`preview`, `test` — no existe script `lint`):

```powershell
npm test        # = npx vitest run: 313 tests en 38 archivos
npx tsc -b      # typecheck estricto (tsc -b), sin errores
npm run build   # = tsc -b + vite build
```

Arranque local sin Docker (opcional, desde `backend/` con `.env` cargado):

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000  # salud: GET /api/health -> {"status": "ok"}, sin auth ni DB
```

## Estado del proyecto

Cierre del roadmap v1: **13 changes archivados** en `openspec/changes/archive/`
(C-01…C-13), 18 specs sincronizadas y 0 changes activos (`openspec list`).

| Estado | Changes | Nota |
|--------|---------|------|
| **Completo, probado y archivado** (12) | C-01 foundation · C-02 core-models · C-03 auth-staff-rbac · C-04 agenda · C-05 reserva online · C-06 cancelación por token · C-07 recepción · C-08 notificaciones mail · C-09 frontend reserva · C-10 frontend agenda staff · C-11 admin + reportes · C-13 frontend admin | Cada uno con proposal, design, specs, tasks 100% y tests ejecutados antes de archivar |
| **Implementado, verificación operativa pendiente** (1) | C-12 deploy-single-host | Tareas 7.1–7.8 (`docker compose up`, health en contenedor, PaaS, TLS, backup/restore, cron) **no ejecutadas**: este host no tiene Docker. El código, la imagen, el compose y los tests de contrato están completos |
| **QA manual pendiente** | C-13 (tarea 8.6) | Checklist a 360 px en navegador real con lector de pantalla; el resto de C-13 está probado (313 tests Vitest) |

Limitaciones aceptadas de v1 (documentadas en `knowledge-base/10_preguntas_abiertas.md`):
recordatorios solo por mail (IN-01), obra social como texto libre (IN-02), worker
en proceso con APScheduler sin Redis (PB-03) y reportes sin export (PB-06).

Fuera del alcance de este repo: video de presentación y archivo TXT de entrega.

## MCP: Context7 (documentación del stack)

Context7 es un servidor MCP remoto de solo lectura con documentación vigente y acotada de librerías. Acá se usa para consultar las APIs reales de FastAPI, Pydantic, SQLAlchemy y Alembic por versión antes de escribir código que dependa de ellas; por ejemplo, al preparar e implementar C-05 (`reserva-online-backend`).

### Capacidades que se usan
- `resolve-library-id`: resuelve el identificador de una librería a partir del nombre.
- `query-docs`: consulta documentación acotada a una pregunta concreta sobre esa librería.
- Solo lectura: no modifican el repo ni el entorno.

### Cuándo usarlo
- Antes de escribir código que dependa de APIs de FastAPI, Pydantic, SQLAlchemy o Alembic.
- Al preparar un change del backend (C-05 en adelante) para validar firmas y comportamiento.
- Para confirmar cambios de versión que la memoria del modelo pueda no reflejar.

### Límites
- No enviar datos de pacientes, secretos ni contenido de `.env`; solo datos ficticios (Ley 25.326).
- No reemplaza la KB (`knowledge-base/`) ni las 12 reglas duras.
- Una respuesta del MCP se contrasta antes de decidir; no es fuente de verdad por sí sola.

### Requisitos y configuración
Cliente opencode con soporte MCP remoto, HTTPS a `mcp.context7.com` y sin
credenciales obligatorias (API key gratuita opcional). La config vive **en el
repo**, versionada y sin secretos, en `opencode.json` (raíz):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "context7": {
      "type": "remote",
      "url": "https://mcp.context7.com/mcp",
      "enabled": true
    }
  }
}
```

Para reproducirlo: clonar el repo y abrir opencode en él (`opencode mcp list`
debe mostrar `context7 connected`). No hace falta configurar nada más; si ya
tenés una config global, opencode combina ambas. `opencode.jsonc` no se usa
para esta config. `engram` (memoria local) queda como integración opcional del
entorno del autor: es un MCP local (`command: ["engram", "mcp"]`) y no se
versiona porque no aporta al alcance evaluado.

### Verificación
`opencode mcp list` muestra `context7` como `connected` en una sesión nueva
(evidencia en `docs/skills-mcp/evidencias/05-invocacion-sesion-nueva.md`).
Prueba de herramienta (2026-11-02): resolver `FastAPI` devuelve
`/websites/fastapi_tiangolo` y `query-docs` sobre ese id responde con
documentación de `EmailStr` y errores de validación de Pydantic; las dos
consultas que cambiaron decisiones de diseño están en
`docs/skills-mcp/evidencias/01-context7-consultas.md`.

### Problemas conocidos
- `NativeCommandError` en PowerShell 5.1: el shim `opencode.ps1` escribe parte de la salida por stderr y PowerShell lo marca en rojo aunque el comando termine bien; no es un fallo de conexión. Invocar `opencode.exe` directamente o ignorar ese stream.
- 429 por límite sin API key: definir `CONTEXT7_API_KEY` como variable de entorno y referenciarla en `headers` como `{env:CONTEXT7_API_KEY}`.
- Si el servidor no aparece, confirmar que la entrada está en `opencode.json` y reiniciar la sesión del agente.

El MCP se documenta como integración; no se registra como skill en `.atl/skill-registry.md`. La config vive en `opencode.json` (raíz, sin secretos); `engram` es una integración local opcional del entorno del autor y no es parte del alcance.

## Docker

Ruta primaria para correr el sistema (servicios `web` + `db` Postgres 16;
`worker`/`redis` solo stubs comentados por regla dura 6):

```powershell
docker compose config
Copy-Item .env.example .env                    # si todavía no hay .env
Copy-Item .env.docker.example .env.docker      # overrides de Docker (gitignored)
docker compose build web
docker compose up -d db                                    # esperar healthy
docker compose run --rm web alembic upgrade head           # migraciones
docker compose run --rm web python scripts/seed_admin.py   # admin inicial
docker compose up -d
curl.exe -f http://localhost:8000/api/health
docker compose down              # conserva el volumen pgdata
```

Detalle de variables (`.env` vs `.env.docker`), TLS y backups en
`docs/deploy-single-host.md` §5. Los scripts de `backend/scripts/` ya viajan
dentro de la imagen, por eso el seed corre con `python scripts/...`.
Requiere Compose ≥ 2.24 (`env_file` con `required`).

### Verificación del camino Docker

El host de desarrollo de este repo **no tiene virtualización habilitada**, así
que Docker no se puede ejecutar localmente. Para que la verificación no dependa
de una máquina puntual, el workflow `.github/workflows/docker-smoke.yml` corre
en un runner con Docker y deja evidencia versionada y repetible (pestaña
**Actions** → `docker-smoke`):

| Paso del workflow | Qué verifica | C-12 |
|---|---|---|
| `config --quiet` con y sin `.env.docker` | compose válido y `required: false` | 7.1 |
| `docker build` + `docker run --entrypoint id` | build OK y UID 10001 (no-root) | 7.2 |
| `compose up --wait` + `compose port db 5432` | `web`/`db` healthy y DB no publicada | 7.3 |
| `curl` a `/api/health`, `/`, `/staff/agenda`, `/api/inexistente`, `/docs` | SPA same-origin y 404 JSON | 7.4 |
| `alembic upgrade head` + `scripts/seed_admin.py` | migraciones y scripts en la imagen | — |
| `docker run` sin variables | fail-fast nombrando las faltantes | 7.5 |

Sin daemon también se puede validar el compose con el binario standalone de
Compose v2 (no requiere WSL ni Hyper-V):

```powershell
Invoke-WebRequest -Uri "https://github.com/docker/compose/releases/latest/download/docker-compose-windows-x86_64.exe" -OutFile "$env:USERPROFILE\docker-compose.exe"
& "$env:USERPROFILE\docker-compose.exe" -f docker-compose.yml config --quiet
```

PENDING (requiere host/PaaS, no un runner): tareas 7.6–7.8 de C-12 —backup y
restore reales con cliente Postgres, deploy en PaaS single instance y TLS con
proxy inverso—. Los 782 pytest, ruff y los 313 vitest siguen verdes; detalle en
`openspec/changes/archive/2026-11-16-c-12-deploy-single-host/tasks.md`.

## Estructura del repo

```text
backend/            # FastAPI: app/ (main, core, db, modules/*), alembic/, tests/, Dockerfile, requirements.txt
frontend/           # React 18 + Vite 5 + React Router: src/{features,shared,pages}, package.json
docker-compose.yml  # web (8000) + db (Postgres 16); worker/redis comentados
opencode.json       # MCP Context7 reproducible (sin secretos)
.env.example        # 13 vars KB-08 + REDIS_URL opcional comentada (placeholders ficticios)
.env.docker.example # overrides de compose (host `db` + password), versionado
.github/workflows/  # docker-smoke: build + compose up + health + fail-fast en CI
docs/discovery/     # informe de discovery previo
docs/skills-mcp/    # ficha de investigación, aplicación y evidencias (skill propia + MCP)
.opencode/skills/   # skills propias versionadas (turno-spec-review)
knowledge-base/     # fuente de verdad del dominio (01-10 + README)
openspec/           # 18 specs + changes/archive/ con los 13 changes cerrados
CHANGES.md          # índice canónico de changes C-01..C-13
AGENTS.md           # instrucciones para agentes (contrato)
```

## Reglas para agentes

Leer `AGENTS.md` antes de tocar código: 12 reglas duras (contrato, prevalecen
sobre la KB) + flujo `/opsx:propose` → implementar → `/opsx:archive`.

## Datos

Solo datos ficticios en repo, ejemplos, tests y capturas (Ley 25.326, regla 12).
Prohibido commitear secretos o datos reales de pacientes (reglas 10 y 12).
