# Design — c-12-deploy-single-host

## Context

Ver `proposal.md` §Why. Estado real relevante al momento de diseñar:

- `backend/Dockerfile` es single-stage `python:3.12-slim`, copia `app/` + `alembic/` y corre uvicorn en `8000`; no compila ni sirve el frontend y no define `HEALTHCHECK`.
- `docker-compose.yml` define `db` + `web`; `web` publica `8000`, lee `.env` y espera `db` sano; los bloques `worker` (comando `app.worker.scheduler`, **módulo inexistente**) y `redis` están comentados.
- `backend/app/main.py` ya expone `GET /api/health` (liveness, sin auth ni DB) y `GET /` devuelve un JSON de servicio; no hay `CORSMiddleware`.
- `backend/app/core/config.py` ya hace fail-fast con `RuntimeError("Missing required env var(s): ...")` que `main.py` traduce a `SystemExit(1)`; no hay noción de entorno (`ENV`) ni rechazo de placeholders.
- `frontend/src/shared/api/client.ts` resuelve `API_BASE = import.meta.env.VITE_API_URL ?? ""`; con `""` todas las llamadas son relativas y funcionan same-origin. `frontend/package-lock.json` existe (permite `npm ci`).
- `backend/scripts/seed_demo.py` solo rechaza `ENV=prod`; con `ENV` ausente corre (fail-open).
- No existe `scripts/` en la raíz, ni guía de deploy, ni `.dockerignore`. `frontend/dist` está en `.gitignore`.
- La máquina de desarrollo actual **no tiene Docker instalado**: el smoke de compose será verificación manual documentada; todo lo demás debe poder testearse con pytest contra Postgres real y con tests de contrato sobre archivos.
- `service-health` no cambia: su contrato (200, sin auth, sin DB, `{"status":"ok"}`) se reutiliza tal cual. `service-config` cambia (delta incluido). Reglas duras aplicables: 6 (worker en-proceso, `REDIS_URL` solo documentada), 10 (secretos por env, TZ Buenos Aires y persistencia UTC), 11 (sin commit), 12 (datos ficticios).

## Goals / Non-Goals

**Goals**

- Un único artefacto desplegable (imagen) y un único origen HTTP: SPA + API, sin CORS en el camino productivo.
- Topología Compose de dos servicios con healthchecks reales, reinicio automático, datos en volumen y DB no expuesta.
- Arranque que falla fuerte y claro ante configuración incompleta o placeholder en producción.
- Backups diarios verificables, con retención de 7 días, restauración probada y sin credenciales en logs/argumentos.
- Guía operativa completa (Compose y PaaS single instance) con TLS, migraciones, rollback y declaración mínima Ley 25.326.
- Seed demo incapaz de correr fuera de staging.

**Non-Goals**

- Alta disponibilidad, réplicas, multi-instancia, balanceo, orquestación tipo Kubernetes.
- Worker como proceso separado o Redis activo (regla dura 6); solo se documenta el camino de migración.
- TLS terminado por la aplicación, HSTS/headers avanzados, WAF.
- Backups a object storage, WAL archiving, PITR.
- Pipeline CI/CD completo; solo se documenta el orden de pasos de deploy.
- Cambios de contrato en endpoints existentes (solo se agrega CORS, que no altera el contrato de las rutas).

## Decisions

### D-1 — Topología Compose: `web` + `db`, worker/redis comentados (elegida)

**Elegido**: dos servicios. `db` (postgres:16-alpine) con `pgdata` en volumen nombrado, healthcheck `pg_isready`, `restart: unless-stopped`, sin puertos publicados y en una red interna (`turnos-internal`) compartida con `web`. `web` con `restart: unless-stopped`, `depends_on: db: condition: service_healthy`, `env_file: .env`, healthcheck contra `/api/health`, y publicación explícita `${WEB_PORT:-8000}:8000`. Bloques `worker` y `redis` permanecen **comentados** con su comando real documentado.

**Por qué**: es el mínimo que cumple KB-02/DD-05 (single host, costo mínimo) y la regla dura 6. Publicar solo `web` reduce superficie; `depends_on: service_healthy` evita que uvicorn arranque contra una DB que todavía está inicializando (el crash-loop que hoy produce `Compose up` en frío).

**Alternativas descartadas**: tres servicios con worker dedicado (contradice regla dura 6, duplica el scheduler APScheduler y requiere estado de cola compartido que v1 no tiene); Redis activo (infra extra sin volumen que lo justifique, PB-03); publicar `5432` para administración (expone la DB al host/red sin necesidad).

**Deuda explícita**: el bloque comentado actual apunta a `app.worker.scheduler`, que **no existe**. C-12 reescribe el comentario para citar `app.modules.notificaciones.scheduler` y aclara que un proceso separado necesitaría un entrypoint nuevo y desactivar `NOTIF_WORKER_ENABLED` en `web` para no correr el ciclo dos veces. No se agrega el entrypoint (fuera de alcance).

### D-2 — Serving del frontend: un contenedor, FastAPI sirve la SPA (elegida)

**Elegido**: un solo contenedor. La imagen compila el frontend y FastAPI sirve `index.html` y los assets estáticos; las rutas de API siguen bajo `/api`. Fallback SPA implementado con una ruta catch-all registrada **después** de todos los routers y que solo devuelve `index.html` cuando el path no empieza con `api/`; `/api/*` desconocido conserva el 404 JSON de FastAPI.

**Por qué**:
- **Un origen** ⇒ `API_BASE=""` (URLs relativas) y CORS deja de ser un problema en producción: no hay preflight, no hay cookies cross-site, no hay `SameSite=None`.
- **Menos moving parts** (DD-05): no hay nginx que configurar, ni proxy con timeouts/headers propios, ni segundo Dockerfile.
- **Volumen real** (<500 turnos/día, un consultorio): uvicorn sirviendo ~1 MB de assets es irrelevante. La optimización de estáticos (brotli, caché de borde) la puede aportar el proxy del host o el CDN del PaaS sin tocar la app.
- El `GET /api/health` existente sirve como liveness del mismo contenedor que sirve la SPA: lo que el PaaS ve sano es exactamente lo que atiende usuarios.

**Alternativas descartadas**:
- **Contenedor nginx con estáticos + proxy `/api`**: mejor rendimiento de estáticos y control de caché, pero agrega un servicio, un Dockerfile/config extra, y dos orígenes a sincronizar (aunque se pueden unificar por proxy). El costo operativo supera el beneficio a este volumen.
- **Servir el frontend solo en build de desarrollo**: imposible en PaaS single instance sin servidor de estáticos.
- **Mantener dos orígenes (`web` y `frontend`) con CORS**: obliga a configurar CORS/cookies cross-site y duplica TLS/healthchecks; se descarta para v1.

### D-3 — Imagen multi-stage, no-root y con healthcheck (elegida)

**Elegido**: `backend/Dockerfile` en dos etapas:
1. `node:20-alpine` → `npm ci` + `npm run build` con `ARG VITE_API_URL=""` (mismo origen), produce `/fe/dist`.
2. `python:3.12-slim` → instala `requirements.txt`, copia `app/`, `alembic/`, `alembic.ini` y `COPY --from=build /fe/dist ./static`; crea usuario `app` (UID 10001), `USER app`, `EXPOSE 8000`, `HEALTHCHECK` con `python -c` + `urllib.request` contra `http://127.0.0.1:${PORT:-8000}/api/health`, y `CMD ["sh","-c","uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]` para que PaaS pueda inyectar `PORT`.

Nuevo `.dockerignore` que excluye `.git`, `.env`, `frontend/node_modules`, `frontend/dist`, `backend/__pycache__`, `.pytest_cache`, `.ruff_cache`, `docs/`, `openspec/` y `knowledge-base/`.

**Por qué**: build reproducible sin requerir Node en el host; imagen única con SPA incluida; no-root reduce impacto de un RCE; `HEALTHCHECK` permite que Docker/PaaS reinicie un proceso colgado; `PORT` configurable evita hardcodear el puerto del PaaS.

**Alternativas descartadas**: compilar el frontend en el host y copiar `dist/` (no reproducible, exige Node local, `dist/` está git-ignored); `python:3.12` full (imagen ~3x); instalar `curl` solo para el healthcheck (suma paquete y superficie).

**Nota**: el `HEALTHCHECK` no valida DB a propósito (liveness ≠ readiness). El PaaS no debe reiniciar la app porque Postgres esté lento; el readiness real es `depends_on` de Compose y, en PaaS, el propio arranque (que ya falla si no puede migrar/consultar al primer request).

### D-4 — Fail-fast de configuración: todas las faltantes, sin valores, y validación de producción (elegida)

**Elegido**: `Settings` incorpora `ENV: Literal["development","staging","prod"] = "development"`. `get_settings()` mantiene el patrón actual pero:
- agrupa y ordena **todas** las variables faltantes (`Missing required env var(s): A, B, C`), sin imprimir valores;
- valida formato/tipo y reporta todos los errores de validación juntos;
- si `ENV=prod`: rechaza `SECRET_KEY` con longitud < 32 caracteres o que contenga marcadores `changeme`/`ejemplo`/`ficticio`, y credenciales `ADMIN_PASSWORD`/`SMTP_PASS` con esos mismos marcadores;
- el mensaje nombra el campo (`SECRET_KEY`) y nunca el valor; `main.py` conserva `SystemExit(1)`.

**Por qué**: el boot silencioso con placeholders es el modo de falla más caro (sistema "funcionando" con secreto público). Fallar temprano, con lista completa y exit ≠ 0 hace que el orquestador no promueva la versión. Pydantic ya reporta `missing` por campo, así que solo hay que agregar la agregación y la regla de producción.

**Alternativas descartadas**: validar al primer uso (el contenedor queda "healthy" y falla en la primera request); abortar en la primera faltante (obliga a múltiples ciclos de deploy para descubrir todas); `extra="forbid"` en `Settings` (rompería el boot con variables del host, ver excepción D-2 ya documentada en `config.py`).

### D-5 — TZ y UTC: `TZ` solo para presentación/logs (elegida)

**Elegido**: `TZ=America/Argentina/Buenos_Aires` se fija en el contenedor (Dockerfile y compose) y se documenta en `.env.example`. La persistencia sigue en `timestamptz` UTC (ya implementado en C-02) y la conversión a hora local ocurre solo en serialización/render. No se configura `PGTZ` ni se altera `timezone` de la sesión.

**Por qué**: cumple regla dura 10 sin introducir doble conversión. Cambiar la zona de la sesión de Postgres haría que `now()` y los `timestamptz` se comporten distinto según el camino, con riesgo de desfasajes de 3 h justo en los bordes de cancelación (`CANCEL_HOURS_MIN=3`) y recordatorios.

**Alternativas descartadas**: `TZ=UTC` en el contenedor (logs en UTC, más difícil de leer para el consultorio); `PGTZ` con la zona local (doble conversión, rompe el contrato ya testeado de persistencia UTC).

### D-6 — CORS: una sola allowlist desde `FRONTEND_URL` (elegida)

**Elegido**: registrar `CORSMiddleware` con `allow_origins=[settings.FRONTEND_URL]`, `allow_credentials=True`, `allow_methods=["GET","POST","PUT","DELETE","OPTIONS"]`, `allow_headers=["Content-Type","Authorization"]`. En producción same-origin esto es inerte (el navegador no hace preflight para el mismo origen); en desarrollo (`FRONTEND_URL=http://localhost:5173`) habilita Vite con cookies.

**Por qué**: el contrato de auth staff usa cookie httpOnly, que requiere `allow_credentials` y un origen explícito (nunca `*`). Derivarlo de `FRONTEND_URL` evita una segunda variable que se desincronice de los links de mail.

**Alternativas descartadas**: `allow_origins=["*"]` (incompatible con credenciales y demasiado permisivo); no registrar CORS y exigir proxy en desarrollo (fricción innecesaria).

### D-7 — TLS: terminado por el PaaS o por un proxy del host, nunca por la app (elegida)

**Elegido**: la app escucha HTTP en `8000`. En PaaS (Railway/Render/Fly single instance) el certificado y el dominio los gestiona la plataforma. En self-host, el compose publica `127.0.0.1:8000` y delante se documenta un proxy inverso (Caddy o Traefik) que termina TLS; uvicorn corre con `--proxy-headers` y `FORWARDED_ALLOW_IPS` acotado a la IP del proxy. Los links de mail usan `FRONTEND_URL` con `https://`.

**Por qué**: montar TLS en la app (certificados, renovación, ACME dentro del contenedor) es más superficie y más modos de falla para un equipo sin DevOps (KB-02). Delegar TLS al borde mantiene la imagen simple y portable entre PaaS y self-host.

**Alternativas descartadas**: nginx+certbot en el compose (un servicio más, renovaciones que hay que monitorear); TLS dentro de uvicorn (no es un terminador TLS pensado para producción).

**Documentación**: la guía explica que sin proxy/TLS no se debe exponer `8000` a Internet (cookies de sesión viajarían en claro).

### D-8 — Backups: `pg_dump -Fc` a disco del host, verificación y retención 7 días (elegida)

**Elegido**: `scripts/backup_postgres.sh` (bash, `set -euo pipefail`):
- Config por env: `BACKUP_DIR` (default `./backups`), `BACKUP_RETENTION_DAYS` (default `7`), `BACKUP_MODE` (`direct` default | `compose`), y credenciales por variables `PG*`/`DATABASE_URL` (nunca por argumento).
- `BACKUP_MODE=direct`: `pg_dump -Fc --no-owner --no-acl` usando libpq env. `BACKUP_MODE=compose`: `docker compose exec -T db pg_dump -Fc -U ... "$PGDATABASE"` (sin instalar cliente en el host).
- Escribe a `$BACKUP_DIR/.turnos_<YYYYmmddTHHMMSSZ>.dump.tmp` y renombra atómicamente a `turnos_<timestamp>.dump` solo después de verificar con `pg_restore --list` (vía stdin en modo compose).
- `chmod 600` y `umask 077`; logs con nombre de archivo y tamaño, nunca el DSN ni la password.
- Rotación: elimina `turnos_*.dump` con `-mtime +7` (o `BACKUP_RETENTION_DAYS`), reportando qué borró.
- Exit ≠ 0 ante cualquier fallo y limpieza del `.tmp`.

`scripts/restore_postgres.sh <dump> <target-db-url>`: rechaza un target no vacío salvo `--force`, corre `pg_restore --clean --if-exists --no-owner --no-acl` y verifica conteos mínimos.

Agendado: cron del host (`17 3 * * *`, TZ del host en Buenos Aires) o, alternativamente documentada, un servicio one-shot del compose con `profiles: ["backup"]` y `BACKUP_DIR` montado. Se elige cron del host como canónico porque el backup debe sobrevivir a la recreación del stack y quedar en disco del host (PB-05).

**Por qué**: formato custom (`-Fc`) permite restaurar selectivamente y comprimir; verificar con `pg_restore --list` detecta dumps truncados antes de que sea tarde; rename atómico evita que la rotación borre el único dump bueno por un archivo parcial; 7 días es la decisión del gate PB-05.

**Alternativas descartadas**: `pg_dump` en SQL plano (más grande, restore más frágil); backup dentro del contenedor `db` con `cron` interno (se pierde al recrear el contenedor y acopla el ciclo de vida de la DB al backup); `pg_basebackup`/WAL (PITR, overkill v1); object storage (costo/credenciales extra, marcado como migración futura).

**Riesgo aceptado**: si el host muere, el backup muere con él (mismo disco). Queda marcado PROVISORIO/MIGRABLE en la guía; la mitigación v1.1 es copiar el directorio a storage externo.

### D-9 — Sin worker separado ni Redis en v1 (elegida, regla dura 6)

**Elegido**: el worker sigue siendo el `BackgroundScheduler` in-proceso que arranca en `lifespan` cuando `NOTIF_WORKER_ENABLED=true`. El compose no define servicios `worker` ni `redis`. `REDIS_URL` queda documentada y comentada como camino de migración.

**Por qué**: PB-03/DD-05/SU-03; un scheduler adicional contra la misma cola duplicaría envíos (no hay locking distribuido en v1).

**Alternativas descartadas**: activar el worker comentado (módulo inexistente y doble scheduler); ARQ/Celery+Redis (fuera de v1).

### D-10 — Seed demo fail-closed en `ENV=staging` (elegida)

**Elegido**: `seed_demo.py` exige `ENV=staging` **explícito**. Cualquier otro valor, incluido ausente, imprime rechazo por stderr y sale con código 2 sin abrir conexión. Con `ENV=staging`, mantiene los datos ficticios actuales (`@ficticio.test`).

**Por qué**: hoy `ENV` ausente habilita el seed; un operador que olvide la variable en producción sembraría la base real. Fail-closed es el único comportamiento seguro para una herramienta de datos.

**Alternativas descartadas**: mantener `ENV != prod` (fail-open); detectar producción por host de `DATABASE_URL` (heurística frágil).

### D-11 — Red, puertos y healthchecks concretos (elegida)

**Elegido**:
- `web` healthcheck: `["CMD","python","-c","import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).status == 200 else sys.exit(1)"]`, `interval: 30s`, `timeout: 5s`, `retries: 3`, `start_period: 20s`.
- `db` healthcheck existente (`pg_isready`) con `start_period: 10s`.
- `web` publica `${WEB_PORT:-8000}:8000`; la guía recomienda `WEB_PORT=127.0.0.1:8000` (bind loopback) cuando hay proxy.
- `db` en `turnos-internal` (`internal: false`, necesita salida solo `web` hacia SMTP; `db` no requiere egress pero no se aísla para no romper extensiones de mantenimiento).
- Migraciones **no** automáticas en el `CMD`: se ejecutan como paso previo de deploy (`docker compose run --rm web alembic upgrade head` o release command del PaaS).

**Por qué**: el healthcheck con `python` evita instalar `curl`; el `start_period` cubre el arranque del scheduler y la carga del módulo; migrar fuera del arranque evita carreras y que un contenedor que no debería tocar el esquema lo haga.

**Alternativas descartadas**: `entrypoint.sh` que migra y luego arranca (riesgo de dos instancias migrando a la vez y de "arrancar igual" tras una migración fallida); exponer `db` al host (superficie innecesaria).

### D-12 — Migraciones y rollback documentados, sin Alembic nuevo (elegida)

**Elegido**: `head` sigue en `002_agenda_meta`; no hay migración nueva. La guía documenta: (1) backup previo, (2) `alembic upgrade head`, (3) arranque de la nueva imagen, (4) verificación `GET /api/health` + revisión con `alembic current`. Rollback: volver al tag de imagen anterior y, si la migración fue destructiva, restaurar el backup (no se asume `downgrade` reversible). Criterio observable: health 200 y `alembic current` en la revisión esperada.

**Por qué**: C-12 no cambia el modelo; documentar el procedimiento con criterio medible evita "rollback a ojo".

**Alternativas descartadas**: asumir que toda migración tiene `downgrade` (FALSO en migraciones con `EXCLUDE`/datos); rollback automático desde la app (fuera de alcance v1).

### D-13 — Ley 25.326, secretos y estado PROVISORIO/MIGRABLE (elegida)

**Elegido**: `docs/deploy-single-host.md` incluye una sección de privacidad con: finalidad (gestión de turnos y recordatorios), conservación (mientras el turno y su historial sean necesarios; anonimización manual documentada en `docs/anonimizacion-ley-25326.md`), no cesión a terceros (solo el proveedor SMTP recibe el mail del recordatorio), y cifrado en tránsito por TLS del borde. SMTP Gmail + app password y backups en disco del host quedan marcados `PROVISORIO/MIGRABLE` con la ruta de reemplazo (proveedor transaccional / storage externo). `.env.example` conserva solo placeholders y el `.env` real está git-ignored.

**Por qué**: PB-05 y KB-08 exigen la declaración mínima; marcar lo provisorio evita que se confunda con la arquitectura objetivo. Regla dura 10 y 12.

**Alternativas descartadas**: declaración completa de política de privacidad (fuera de alcance v1); documentar solo en la KB (el operador necesita el dato junto al runbook de deploy).

## Risks / Trade-offs

- **Fallback SPA que tape `/api`** → catch-all registrado al final y con guarda explícita de prefijo `api/`; tests `test_spa_ruta_profunda_200_html` y `test_api_inexistente_404_json`.
- **CORS mal configurado que rompa dev o habilite orígenes de más** → allowlist única derivada de `FRONTEND_URL` (nunca `*`) y test de preflight permitido/rechazado; en producción same-origin es inerte.
- **Secretos en la imagen o en compose** → credenciales solo por `env_file`/env del runtime, `.dockerignore` excluye `.env`, test de contrato que escanea archivos versionados y falla si encuentra patrones reales.
- **Backup que falla en silencio o deja archivo parcial** → `set -euo pipefail`, tmp + rename atómico, verificación `pg_restore --list`, exit ≠ 0, test con DB inalcanzable.
- **Retención que borra el único backup bueno** → rotación solo sobre `turnos_*.dump` ya verificados con nombre por timestamp, nunca sobre `.tmp`.
- **Backup en el mismo host que la DB** → riesgo aceptado y marcado PROVISORIO/MIGRABLE; v1.1 replica a storage externo.
- **Imagen más grande por incluir Node build** → el stage de Node no llega a la imagen final (`--from`), solo los assets; el costo es tiempo de build.
- **Docker no disponible en el entorno de desarrollo actual** → el smoke de `compose up`/`build` queda como verificación manual documentada con criterios observables; todo lo verificable sin Docker (contratos de archivos, config fail-fast, backup en modo `direct` contra Postgres real, SPA en TestClient) se automatiza en pytest.
- **`npm ci` en build** → depende de `package-lock.json` versionado (existe); si se desactualiza, el build falla temprano (deseado).
- **Fail-fast de producción demasiado estricto** → solo se activa con `ENV=prod`; desarrollo y staging conservan placeholders locales para no bloquear tests ni demos.
- **Migraciones manuales** → si el operador olvida `alembic upgrade head`, la app arranca contra un esquema viejo; la guía lo pone como paso obligatorio y el criterio de verificación incluye `alembic current`.

## Migration Plan

1. Backup del Postgres actual (`scripts/backup_postgres.sh`) antes de tocar nada.
2. Construir la imagen nueva y ejecutar `alembic upgrade head` como paso de deploy (sin migración nueva en C-12, debe reportar `002_agenda_meta`).
3. Levantar `web` + `db` con el compose final; verificar `docker compose ps` (dos servicios sanos) y `GET /api/health` (200).
4. Verificar SPA en `/`, fallback de ruta profunda y 404 JSON en `/api/*` inexistente.
5. Configurar cron diario de backup y ejecutar una corrida manual verificando dump + `pg_restore --list`.
6. Rollback si falla: volver al tag de imagen anterior; si el esquema cambió, restaurar el backup del paso 1 y dejar `alembic current` en la revisión previa. Criterio: health 200 y revisión esperada.

## Open Questions

- Ninguna que cambie specs, enfoque o tareas. El dominio definitivo y el proveedor SMTP transaccional quedan para v1.1 (marcados PROVISORIO/MIGRABLE) y no afectan el contrato de este change.
