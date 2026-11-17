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
si no existe, fuerza `NOTIF_WORKER_ENABLED=false` y
`FRONTEND_URL=http://localhost:<puerto>`, aplica migraciones Alembic, carga datos
ficticios idempotentes (admin, 3 profesionales, horarios y turnos), compila la SPA
en `static/` si hace falta y arranca API + SPA en el mismo origen.

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
Cliente opencode con soporte MCP remoto, HTTPS a `mcp.context7.com` y sin credenciales obligatorias (API key gratuita opcional). La configuración es **global y externa al repo**, en `C:\Users\ciroc\.config\opencode\opencode.json`:

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

Se puede llevar a un `opencode.json` en la raíz del repo para hacerla reproducible por proyecto; `opencode.jsonc` no se usa para esta config.

### Verificación
`opencode mcp list` debe mostrar dos servidores `connected` (`context7` y `engram`). Prueba de herramienta (2026-11-02): resolver `FastAPI` devuelve `/websites/fastapi_tiangolo` y `query-docs` sobre ese id responde con documentación de `EmailStr` y errores de validación de Pydantic.

### Problemas conocidos
- `NativeCommandError` en PowerShell 5.1: el shim `opencode.ps1` escribe parte de la salida por stderr y PowerShell lo marca en rojo aunque el comando termine bien; no es un fallo de conexión. Invocar `opencode.exe` directamente o ignorar ese stream.
- 429 por límite sin API key: definir `CONTEXT7_API_KEY` como variable de entorno y referenciarla en `headers` como `{env:CONTEXT7_API_KEY}`.
- Si el servidor no aparece, confirmar que la entrada está en `opencode.json` y reiniciar la sesión del agente.

El MCP se documenta como integración; no se registra como skill en `.atl/skill-registry.md`. Engram también está configurado (memoria persistente), pero la integración documentada para este TP es Context7.

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
docs/skills-mcp/    # ficha de investigación e informe del TP (skill propia + MCP)
.opencode/skills/   # skills propias versionadas (turno-spec-review)
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
