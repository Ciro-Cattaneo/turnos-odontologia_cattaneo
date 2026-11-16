# Proposal — c-12-deploy-single-host

## Why

C-01…C-11 dejaron API, worker de mail en-proceso, reserva pública, agenda staff y admin/reportes funcionando en desarrollo, pero el sistema todavía no es desplegable: `backend/Dockerfile` solo empaqueta el backend (el build de React no se sirve), `docker-compose.yml` expone `8000` sin healthcheck del `web`, no hay configuración de producción verificada (TZ, CORS con `FRONTEND_URL`, fail-fast endurecido), no existe ningún script de backup y `backend/scripts/seed_demo.py` puede ejecutarse fuera de staging. Sin este change el consultorio no puede salir de `docker compose up` en una máquina de desarrollo ni cumplir la declaración mínima de Ley 25.326 (PB-05: Gmail provisorio + backups host-disk 7 días, marcados PROVISORIO/MIGRABLE).

## What Changes

- **Imagen única de aplicación**: `backend/Dockerfile` multi-stage que compila el frontend (`npm ci && npm run build` con `VITE_API_URL=""`) y copia `frontend/dist` dentro de la imagen Python; FastAPI sirve la SPA desde `/` (fallback a `index.html` solo para rutas no-`/api`) y la API sigue en `/api`. Un solo contenedor `web`, sin segundo servicio nginx, usuario no-root y `HEALTHCHECK` contra `GET /api/health`.
- **`docker-compose.yml` final (v1)**: `web` + `db` con `restart: unless-stopped`, `depends_on: db: condition: service_healthy`, healthchecks en ambos, volumen nombrado `pgdata`, red interna para `db` y solo el puerto de `web` publicado. Bloque `worker` **comentado** apuntando al módulo real (`app.modules.notificaciones.scheduler`, hoy in-proceso) con la advertencia de que un proceso separado exigiría un entrypoint nuevo y duplicaría el scheduler; bloque `redis` comentado junto a `REDIS_URL` documentada. Nada de worker separado ni Redis activo en v1 (regla dura 6, PB-03/DD-05).
- **Configuración de producción**: `TZ=America/Argentina/Buenos_Aires` (persistencia UTC, display local), CORS con `allow_origins=[FRONTEND_URL]` y credenciales, `CANCEL_HOURS_MIN=3`, `SLOT_DEFAULT_MIN=30`, `NOTIF_WORKER_ENABLED` explícita, `SECRET_KEY` fuerte y `ADMIN_*` obligatorios. Fail-fast al boot: se listan **todas** las variables requeridas faltantes ordenadas, nunca se imprimen valores, y en modo producción se rechazan placeholders conocidos (`changeme-*`, `SECRET_KEY` corta). Exit code distinto de 0.
- **Documentación de deploy** (`docs/deploy-single-host.md`): pasos single host con Compose, pasos PaaS barato (Railway/Render/Fly single instance) con TLS gestionado por la plataforma, TLS self-host solo vía proxy inverso (la app nunca termina TLS), migraciones `alembic upgrade head` antes de recibir tráfico, rollback (tag de imagen anterior + revisión Alembic previa) y **declaración mínima Ley 25.326** (finalidad, conservación, no cesión). SMTP Gmail + app password y backups a disco local marcados **PROVISORIO/MIGRABLE**.
- **Backups**: `scripts/backup_postgres.sh` versionado que hace `pg_dump -Fc` a `<BACKUP_DIR>/turnos_<UTC timestamp>.dump` (temporal + rename atómico), verifica el dump con `pg_restore --list`, aplica permisos `600`, rota retención a **7 días** y nunca recibe credenciales por argumento. Incluye `scripts/restore_postgres.sh` y el procedimiento documentado para agendarlo (cron del host o servicio one-shot del compose).
- **Salud y datos demo**: `GET /api/health` se reutiliza sin cambios de contrato como liveness del contenedor y del PaaS (el compose solo lo consume). `backend/scripts/seed_demo.py` pasa a guarda **fail-closed**: solo corre con `ENV=staging` explícito; cualquier otro valor, incluido ausente, sale con código 2 sin tocar la DB y solo con datos ficticios `@ficticio.test`.
- **Verificaciones**: `docker compose config` válido, smoke de `compose up` + health 200 + SPA 200 con fallback correcto, boot sin variables requeridas ⇒ mensaje claro y exit ≠ 0, `backup`/`restore` verificables por tests y `.env.example` sin secretos reales (regla dura 10). Sin migraciones Alembic nuevas (`head` sigue en `002_agenda_meta`).

## Capabilities

### New Capabilities

- `despliegue-operacion`: imagen única reproducible (frontend compilado + API), topología Compose single-host con healthchecks/reinicio/volúmenes/puertos mínimos, backup y restore de Postgres con retención 7 días, documentación de deploy (Compose y PaaS, TLS, migraciones, rollback, Ley 25.326) y seed demo restringido a staging.

### Modified Capabilities

- `service-config`: el archivo `.env.example` versionado incorpora las variables de producción documentadas (incluidas las del worker y `REDIS_URL` opcional) marcando que sus placeholders son ficticios; el fail-fast pasa a listar todas las faltantes sin exponer valores y a rechazar placeholders/`SECRET_KEY` débil en producción; se agrega el requisito de CORS restringido al origen `FRONTEND_URL`.

### Not Modified

- `service-health`: `GET /api/health` conserva exactamente su contrato actual (200 sin auth ni DB, `{"status":"ok"}`). C-12 solo lo consume desde el `HEALTHCHECK` del contenedor y el PaaS, así que **no se toca** su spec.

## Impact

- **Build/empaquetado**: `backend/Dockerfile` (multi-stage Node + Python), nuevo `.dockerignore`; el build de `frontend/` se ejecuta dentro de la imagen (no se versiona `frontend/dist`).
- **Compose**: `docker-compose.yml` final (healthchecks, `restart`, red interna, volúmenes, bloques comentados de worker/redis); `postgres` deja de publicar puerto.
- **Backend**: `backend/app/main.py` (montaje de la SPA y CORS con `FRONTEND_URL`), `backend/app/core/config.py` (fail-fast endurecido y validaciones de producción), `backend/scripts/seed_demo.py` (guarda fail-closed).
- **Docs/scripts nuevos**: `docs/deploy-single-host.md`, `scripts/backup_postgres.sh`, `scripts/restore_postgres.sh`; `.env.example` ampliado con comentarios de producción.
- **Tests nuevos**: `backend/tests/test_deploy_config.py` (contrato de compose/Dockerfile/docs), `backend/tests/test_deploy_boot.py` (fail-fast y exit codes), `backend/tests/test_deploy_backup.py` (script de backup/restore con Postgres real), `backend/tests/test_deploy_spa.py` (montaje de estáticos/fallback), `backend/tests/test_seed_demo_staging.py` (guarda fail-closed). Smoke real de `docker compose up` queda como verificación manual documentada (requiere Docker y puertos libres).
- **Fuera de alcance**: worker como proceso separado y Redis activo (regla dura 6/PB-03), HA/réplicas/multi-instancia, TLS terminado por la app, backups a object storage o WAL archiving, observabilidad/métricas más allá de liveness, alta disponibilidad de Postgres, CI/CD pipeline completo (solo se documenta el orden de deploy), y cualquier dato real de pacientes (Ley 25.326/regla dura 12).
- **Gobernanza: BAJO** por roadmap. Riesgos principales y mitigación: (a) SPA fallback que tape rutas `/api` ⇒ fallback excluye el prefijo `/api` y test dedicado; (b) `SMTP_PASS`/`SECRET_KEY` filtrados en compose o imagen ⇒ solo por `env_file`/variables de entorno, `.dockerignore` y test de escaneo de archivos versionados; (c) backup que falla en silencio ⇒ exit code ≠ 0, dump temporal + rename atómico y verificación `pg_restore --list`; (d) seed demo ejecutado contra producción ⇒ guarda fail-closed con `ENV=staging` y exit 2.
- **Sin commit ni push**: este propose es solo planificación (regla dura 11); no se modifica `docker-compose.yml`, `Dockerfile`, scripts, configuración ni tests.

## Criterios de aceptación

1. `docker compose config` valida el compose final y la topología arranca `web` + `db` saludables, sin contenedores `worker`/`redis` activos, con un único puerto publicado y `db` sin puerto en el host.
2. `GET /api/health` responde 200 `{"status":"ok"}` desde el contenedor y `GET /` devuelve el `index.html` del build; una ruta desconocida fuera de `/api` devuelve la SPA y una ruta `/api/*` desconocida devuelve 404 JSON (nunca HTML).
3. El proceso arranca sin variables requeridas ⇒ termina con exit code ≠ 0 y un mensaje que nombra todas las faltantes, sin imprimir valores; con `SECRET_KEY` placeholder en producción también falla.
4. Preflight CORS desde `FRONTEND_URL` devuelve el origen permitido con credenciales y desde otro origen no lo devuelve.
5. `scripts/backup_postgres.sh` genera un `.dump` verificable, con permisos `600`, retención de 7 días por timestamp y exit ≠ 0 sin dejar dump parcial cuando falla; `scripts/restore_postgres.sh` restaura ese dump en una base scratch con los mismos conteos.
6. `docs/deploy-single-host.md` cubre Compose, PaaS single instance, TLS, `alembic upgrade head`, rollback y la declaración mínima Ley 25.326, con SMTP Gmail y backups marcados PROVISORIO/MIGRABLE.
7. `seed_demo.py` con `ENV=staging` inserta datos ficticios y con `ENV` ausente o `prod` sale con código 2 sin escribir.
8. Ningún secreto real aparece en archivos versionados y `.env.example` solo contiene placeholders.
