# Tasks — c-12-deploy-single-host

> Orden TDD: **primero el test en rojo**, después la implementación mínima, después refactor. Los tests de backup/restore corren contra Postgres real (`BACKUP_MODE=direct` y `DATABASE_URL` del `conftest`); los tests de contrato leen archivos versionados (`docker-compose.yml`, `Dockerfile`, `.env.example`, `docs/deploy-single-host.md`, `scripts/*.sh`), que es exactamente el artefacto observable de este change. Mocks: ninguno; el único límite es el binario `pg_dump` (se usa el real). Datos ficticios `@ficticio.test` y DNI sintéticos (regla dura 12). Sin commit ni push (regla dura 11). **Ninguna tarea está tildada en este propose.**
>
> Códigos de escenario: `DO-R1…DO-R6` = `specs/despliegue-operacion`; `SC-R1…SC-R3` = `specs/service-config` (R1 y R2 son MODIFIED, R3 es ADDED).
>
> **Migración: no se requiere.** `alembic heads` debe seguir en `002_agenda_meta`; C-12 no toca `backend/alembic/versions/`.
>
> **Partición**: secciones 1–6 = automatizables en pytest/CI; sección 7 = verificaciones de proceso/manual con criterio observable (no automatizables sin Docker/PaaS); sección 8 = cierre.

## 1. Serving de la SPA e imagen única (DO-R1)

- [x] 1.1 Escribir en rojo `test_spa_root_sirve_index_html_200` y `test_spa_ruta_profunda_sin_api_200_html` en `backend/tests/test_deploy_spa.py` (hoy `GET /` devuelve JSON, así que el test falla); cubre DO-R1 "FELIZ — La imagen arranca y sirve API y SPA" y "BORDE — Una ruta profunda del cliente devuelve el index" — capa: API/TestClient.
- [x] 1.2 Escribir en rojo `test_api_inexistente_404_json` y `test_health_sigue_200_sin_auth` (no regresión de `service-health`); cubre DO-R1 "ERROR — Una ruta desconocida bajo /api no cae en el fallback" — capa: API/TestClient.
- [x] 1.3 Implementar el montaje de estáticos en `backend/app/main.py` (`Settings.STATIC_DIR` default `static`, assets con `StaticFiles`) y el catch-all registrado **después** de los routers, con guarda de prefijo `api/`, hasta verde 1.1–1.2; cubre DO-R1 — capa: API.
- [x] 1.4 Escribir `test_spa_sin_build_conserva_api_y_root_json` (borde: directorio de estáticos ausente en desarrollo ⇒ `/api/health` 200 y `/` sigue respondiendo el JSON de servicio); cubre DO-R1 "BORDE" y evita romper `backend/tests/test_health.py` — capa: API.
- [x] 1.5 Escribir `test_dockerfile_multistage_compila_frontend` (contrato: stage `node`, `npm ci`, `npm run build`, `COPY --from=` hacia `static`) y `test_dockerfile_usuario_no_root_y_healthcheck` (`USER` distinto de root y `HEALTHCHECK` contra `/api/health`); cubre DO-R1 "FELIZ" — capa: contrato/archivo.
- [x] 1.6 Escribir `test_dockerfile_no_copia_env_ni_secretos` (no `COPY .env`, no credenciales literales) y crear/implementar `backend/Dockerfile` multi-stage + `CMD` con `${PORT:-8000}` hasta verde 1.5–1.6; cubre DO-R1 "ERROR — La imagen no contiene secretos" — capa: contrato/archivo.
- [x] 1.7 Crear `.dockerignore` y escribir `test_dockerignore_excluye_env_node_modules_git` (`.env`, `frontend/node_modules`, `frontend/dist`, `.git`, `__pycache__`, `.pytest_cache`); cubre DO-R1 "ERROR — La imagen no contiene secretos" — capa: contrato/archivo.
- [x] 1.8 Escribir `test_repo_sin_secretos_reales_en_archivos_versionados` (`git ls-files` + patrones de password/clave excluyendo placeholders y tests): falla si aparece un secreto real versionado; cubre DO-R1 "ERROR" y SC-R1 "No secrets leak into the repository" — capa: contrato/repo.

## 2. Compose final single-host (DO-R2)

- [x] 2.1 Agregar `pyyaml>=6` a `backend/requirements.txt` (lo usan los tests de contrato del compose) y verificar `python -c "import yaml"` + suite sin errores de import.
- [x] 2.2 Escribir en rojo `test_compose_solo_web_y_db_activos` en `backend/tests/test_deploy_compose.py` (`services` = `{web, db}`) y `test_compose_restart_unless_stopped_y_volumen_pgdata`; cubre DO-R2 "FELIZ" y "ERROR — No hay worker ni Redis activos" — capa: contrato/YAML.
- [x] 2.3 Escribir `test_compose_db_sin_puertos_publicados` y `test_compose_publica_solo_puerto_web`; cubre DO-R2 "BORDE — La base de datos no se expone fuera de la red interna" — capa: contrato/YAML.
- [x] 2.4 Escribir `test_compose_web_depends_on_db_service_healthy` y `test_compose_healthchecks_web_y_db` (comando del web apunta a `/api/health`; `db` usa `pg_isready`); cubre DO-R2 "ERROR — Web no arranca antes de que la base esté sana" — capa: contrato/YAML.
- [x] 2.5 Escribir `test_compose_worker_comentado_cita_modulo_real` (aparece `app.modules.notificaciones.scheduler` y **no** `app.worker.scheduler`) y `test_compose_redis_comentado_y_redis_url_documentada_sin_servicio`; cubre DO-R2 "ERROR — No hay worker ni Redis activos en v1" (regla dura 6, PB-03) — capa: contrato/YAML.
- [x] 2.6 Escribir `test_compose_no_contiene_secretos_literales` (credenciales solo por `${VAR}`/`env_file`, sin `SMTP_PASS` ni passwords reales); cubre SC-R1 "No secrets leak" y DO-R2 — capa: contrato/YAML.
- [x] 2.7 Reescribir `docker-compose.yml` (web + db finales, red interna, healthchecks, `restart`, volumen, bloques comentados de worker/redis) hasta verde 2.2–2.6; cubre DO-R2 — capa: compose.

## 3. Configuración de producción: fail-fast, TZ y CORS (SC-R1, SC-R2, SC-R3)

- [x] 3.1 Escribir en rojo `test_config_lista_todas_las_faltantes_ordenadas` (sin `SECRET_KEY` ni `SMTP_PASS` ⇒ mensaje con ambas, ordenadas) y `test_config_mensaje_no_imprime_valores` (el valor configurado no aparece en stdout/stderr); cubre SC-R2 "ERROR — Faltan varias variables y se nombran todas" — capa: unit/config.
- [x] 3.2 Escribir `test_config_prod_rechaza_secret_key_placeholder` (parametrizado: `changeme-*`, `*-ejemplo`, 31 caracteres) y `test_config_prod_rechaza_admin_password_y_smtp_pass_placeholder`; cubre SC-R2 "ERROR — Un placeholder en producción bloquea el arranque" — capa: unit/config.
- [x] 3.3 Escribir `test_config_dev_y_staging_permiten_placeholders` y `test_config_env_invalido_falla_nombrando_env` (parametrizado `production`, `PROD`, cadena vacía); cubre SC-R2 "BORDE — En desarrollo sigue permitiendo placeholders locales" — capa: unit/config.
- [x] 3.4 Implementar en `backend/app/core/config.py`: `ENV` (`development|staging|prod`, default `development`), agregación ordenada de faltantes, mensaje sin valores y rechazo de placeholders en `prod`; ajustar `backend/app/main.py` si hace falta, hasta verde 3.1–3.3; cubre SC-R2 — capa: unit/config.
- [x] 3.5 Escribir en rojo `test_cors_preflight_origen_permitido_200_credenciales` (ACAO = `FRONTEND_URL`, `allow-credentials: true`) y `test_same_origin_sin_origin_200`; cubre SC-R3 "FELIZ" y "BORDE" — capa: API/TestClient.
- [x] 3.6 Escribir `test_cors_preflight_origen_ajeno_rechazado_sin_allow_origin` (parametrizado con dos orígenes distintos); cubre SC-R3 "ERROR" — capa: API/TestClient.
- [x] 3.7 Registrar `CORSMiddleware` en `backend/app/main.py` con allowlist única `FRONTEND_URL` y credenciales hasta verde 3.5–3.6; cubre SC-R3 — capa: API.
- [x] 3.8 Ampliar `backend/tests/test_env_example.py` con `test_env_example_incluye_env_vars_worker_y_placeholders_ficticios` y `test_env_example_secret_key_placeholder_reconocible_como_no_productivo`; cubre SC-R1 "FELIZ" y "BORDE" — capa: contrato/archivo.
- [x] 3.9 Actualizar `.env.example` (agregar `ENV`, comentarios de producción, `TZ`, defaults `CANCEL_HOURS_MIN=3`/`SLOT_DEFAULT_MIN=30`, marca `PROVISORIO/MIGRABLE` en SMTP) hasta verde 3.8 y confirmar que `test_env_example_cubre_las_13_vars_kb08` sigue pasando; cubre SC-R1 — capa: contrato/archivo.

## 4. Backup y restore de Postgres (DO-R3)

- [x] 4.1 Escribir en rojo `test_backup_crea_dump_verificable_permisos_600` en `backend/tests/test_deploy_backup.py` (nombre `turnos_<timestamp>.dump`, `pg_restore --list` exit 0, modo `600`, script exit 0); cubre DO-R3 "FELIZ — El backup crea un dump verificable" — capa: proceso/Postgres real.
- [x] 4.2 Escribir `test_backup_dos_corridas_timestamps_unicos_sin_sobrescribir` y `test_backup_rota_dumps_mayores_a_7_dias` (parametrizado retención 7 y 1 día; archivo de 8 días se borra, el reciente queda); cubre DO-R3 "BORDE — Dos ejecuciones el mismo día…" — capa: proceso/archivo.
- [x] 4.3 Escribir `test_backup_falla_db_inalcanzable_exit_no_cero_sin_dump_parcial` y `test_backup_error_no_expone_password_ni_dsn`; cubre DO-R3 "ERROR — Un fallo de pg_dump no deja dump parcial" — capa: proceso.
- [x] 4.4 Implementar `scripts/backup_postgres.sh` (`set -euo pipefail`, `BACKUP_MODE=direct|compose`, `PG*`/`DATABASE_URL` por env, tmp + rename atómico, `pg_restore --list`, `umask 077`/`chmod 600`, rotación por `-mtime`) hasta verde 4.1–4.3; cubre DO-R3 — capa: script.
- [x] 4.5 Escribir en rojo `test_restore_reproduce_conteos_de_turnos_y_revision` (restore en base scratch ⇒ mismos `count(turno)` y revisión de `alembic_version`) y `test_restore_rechaza_target_no_vacio_sin_force`; cubre DO-R3 "FELIZ — El restore documentado reproduce los datos" — capa: proceso/Postgres real.
- [x] 4.6 Implementar `scripts/restore_postgres.sh` (guarda de target no vacío, `--force`, `pg_restore --clean --if-exists --no-owner --no-acl`, verificación de conteos) hasta verde 4.5; cubre DO-R3 — capa: script.
- [x] 4.7 Escribir `test_backup_no_deja_archivos_tmp_y_es_idempotente_en_nombres` (borde: tras dos corridas no queda ningún `.tmp` y no se reutiliza un nombre existente); cubre DO-R3 "BORDE" — capa: proceso/archivo.

## 5. Guía de deploy, TLS y Ley 25.326 (DO-R4, DO-R5)

- [x] 5.1 Escribir en rojo `test_docs_deploy_cubre_compose_paas_tls_migraciones_rollback` en `backend/tests/test_deploy_docs.py` (secciones presentes en `docs/deploy-single-host.md`: Compose, Railway/Render/Fly single instance, TLS, `alembic upgrade head`, rollback); cubre DO-R4 "FELIZ" — capa: contrato/documento.
- [x] 5.2 Escribir `test_docs_deploy_tls_fuera_de_la_app_y_proxy_headers` (TLS en PaaS/proxy, app HTTP interna, `FORWARDED_ALLOW_IPS`) y `test_docs_deploy_rollback_criterio_observable` (imagen + revisión previas o restore; criterio `/api/health` 200 y `alembic current`); cubre DO-R4 "BORDE" y "ERROR — El rollback tiene criterio observable" — capa: contrato/documento.
- [x] 5.3 Escribir `test_docs_privacidad_finalidad_conservacion_no_cesion` y `test_docs_provisorio_migrable_smtp_y_backups` (ambos ítems marcados `PROVISORIO/MIGRABLE` con su ruta de reemplazo); cubre DO-R5 "FELIZ" y "BORDE" — capa: contrato/documento.
- [x] 5.4 Escribir `test_docs_sin_datos_reales_de_pacientes` (los ejemplos usan `@ficticio.test` y DNI sintéticos; ningún email fuera de dominios ficticios) y `test_docs_backup_cron_y_restore_documentados` (línea de cron + comando de restore); cubre DO-R5 "ERROR" y DO-R3 "FELIZ" (operación) — capa: contrato/documento.
- [x] 5.5 Escribir `docs/deploy-single-host.md` hasta verde 5.1–5.4, incluyendo orden de deploy (backup → `alembic upgrade head` → arranque → health), `PORT` del PaaS, bind loopback con proxy, retención 7 días y declaración mínima Ley 25.326; cubre DO-R4 y DO-R5 — capa: documento.

## 6. Seed demo restringido a staging (DO-R6)

- [x] 6.1 Escribir en rojo `test_seed_demo_env_ausente_exit_2_sin_escribir` y `test_seed_demo_env_desconocido_exit_2` (parametrizado `production`, `PROD`, `demo`); hoy `ENV` ausente ejecuta el seed ⇒ rojo; cubre DO-R6 "BORDE — Sin ENV explícito falla cerrado" — capa: proceso/Postgres real.
- [x] 6.2 Escribir `test_seed_demo_env_prod_exit_2_sin_escribir` y `test_seed_demo_env_staging_exit_0_datos_ficticios` (`backend/tests/test_seed_demo_staging.py`; verifica `@ficticio.test` y conteos); cubre DO-R6 "ERROR" y "FELIZ" — capa: proceso/Postgres real.
- [x] 6.3 Implementar la guarda fail-closed en `backend/scripts/seed_demo.py` (solo `ENV=staging`; resto exit 2 sin conexión) hasta verde 6.1–6.2 y confirmar que `backend/tests/test_seed_demo.py` sigue pasando (ajustándolo si asumía el comportamiento fail-open); cubre DO-R6 — capa: script.

## 7. Verificaciones manuales con criterio observable (requieren Docker / host / PaaS)

- [ ] 7.1 Ejecutar `docker compose config` y verificar exit 0, dos servicios (`web`, `db`) y ausencia de `worker`/`redis` en la salida expandida; criterio: exit code 0 y servicios exactos — cubre DO-R2 "FELIZ".
- [ ] 7.2 Ejecutar `docker compose build web` y `docker run --rm --entrypoint id <imagen>`; criterio: build exit 0 y UID ≠ 0 (10001) — cubre DO-R1 "FELIZ".
- [ ] 7.3 Ejecutar `docker compose up -d`, luego `docker compose ps`; criterio: `web` y `db` en `running`/`healthy`, y `Test-NetConnection localhost -Port 5432` falla (DB no publicada) — cubre DO-R2 "FELIZ" y "BORDE".
- [ ] 7.4 Con el stack arriba, `curl http://localhost:8000/api/health` y `curl -i http://localhost:8000/`; criterio: 200 con `{"status":"ok"}`, `/` con `content-type: text/html` y `curl -i http://localhost:8000/api/ruta-inexistente` 404 JSON; una ruta profunda (`/agenda`) devuelve el HTML del SPA — cubre DO-R1.
- [ ] 7.5 Correr la imagen sin variables requeridas (`docker run --rm <imagen>`) y verificar el código de salida (`echo $?`); criterio: exit ≠ 0 y mensaje que nombra las variables faltantes sin imprimir valores — cubre SC-R2 "ERROR — Faltan varias variables".
- [ ] 7.6 Correr `BACKUP_MODE=compose BACKUP_DIR=./backups scripts/backup_postgres.sh` y luego `scripts/restore_postgres.sh` contra una base scratch; criterio: dump con `pg_restore --list` OK, permisos `600`, restore con conteos iguales, ningún `.tmp`; instalar la línea de cron y verificar con `crontab -l` — cubre DO-R3.
- [ ] 7.7 Desplegar la imagen en el PaaS single instance elegido (Railway/Render/Fly) siguiendo la guía; criterio: `https://<host>/api/health` 200 con certificado válido, `/` sirve la SPA y la variable `PORT` es respetada — cubre DO-R4 "BORDE" y D-7.
- [ ] 7.8 Si el deploy es self-host con proxy, verificar `curl -I https://<host>` con certificado válido y que `8000` **no** responde desde fuera del host; criterio: TLS válido en el proxy y puerto interno inaccesible externamente — cubre DO-R4 "BORDE".
- [x] 7.9 Revisar en el host que el directorio `backups/` no está versionado (`git status --ignored`) y agregar `backups/` a `.gitignore` si falta; criterio: ningún dump aparece como archivo rastreado — cubre DO-R3 y regla dura 12.

## 8. Cierre

- [x] 8.1 Ejecutar `ruff check backend` y `ruff format --check backend`; criterio: sin hallazgos.
- [x] 8.2 Ejecutar la suite backend completa (`pytest backend`) incluyendo los tests nuevos `test_deploy_*` y `test_seed_demo_staging.py`; criterio: todo verde contra Postgres real.
- [x] 8.3 Ejecutar `npx tsc -b`, `npm run test` y `npm run build` en `frontend/`; criterio: sin errores de tipos, Vitest verde y `dist/` generado (el build se embebe en la imagen).
- [x] 8.4 Ejecutar `openspec validate c-12-deploy-single-host --strict`; criterio: `Change 'c-12-deploy-single-host' is valid`.
- [x] 8.5 Verificar `alembic heads` en `backend/`; criterio: única cabeza `002_agenda_meta` (sin migración nueva).
- [x] 8.6 Revisar `git status --short` y `git diff`; criterio: solo archivos previstos (`Dockerfile`, `.dockerignore`, `docker-compose.yml`, `config.py`, `main.py`, `.env.example`, `requirements.txt`, `scripts/*.sh`, `docs/deploy-single-host.md`, `backend/scripts/seed_demo.py`, tests nuevos/ajustados y artefactos del change), sin `.env`, sin dumps.
- [x] 8.7 Confirmar que `CHANGES.md` **no** cambió de estado para C-12 (los proposes previos de C-09/C-10/C-11 dejaron la fila en `[ ]` pendiente hasta el archivado) y que no se ejecutó `git add`, `git commit` ni `git push` (regla dura 11).

## Workflow follow-up

- Ejecutar `/opsx:apply c-12-deploy-single-host` recién con una orden nueva; este propose no implementa código ni toca compose/Dockerfile/scripts/config/tests.
- Al archivar, actualizar la fila `[C-12]` de `CHANGES.md` con el resumen real (tareas, tests, `head`, capabilities sincronizadas) y archivar el change en `openspec/changes/archive/<fecha>-c-12-deploy-single-host/`.
- No commitear ni pushear hasta que el usuario lo pida explícitamente.
- Verificación manual 7.7/7.8 queda pendiente si no hay cuenta PaaS ni proxy disponibles al momento del apply; debe registrarse como deuda operativa explícita, no como tarea completada.

## Deuda operativa (post-deploy, no ejecutada en apply)

> Las tareas **7.1–7.8** quedan sin tildar a propósito y **no** son fallos de implementación: todo lo automatizable está en verde (suite backend, ruff, `tsc -b`, Vitest, build, `openspec validate`, `alembic heads`, cero secretos). Son verificaciones de proceso que requieren **Docker, un host real o una cuenta PaaS**, no disponibles en el entorno de apply (Docker no instalado). Deben ejecutarse en el host/PaaS al poner en producción y registrarse allí; hasta entonces son deuda operativa explícita del deploy, no tareas completadas.

- **7.1** `docker compose config`: verifica que el compose final expande a exactamente `web` + `db`, sin `worker` ni `redis`; requiere Docker CLI con el plugin Compose; éxito = exit 0 y esos dos servicios únicamente.
- **7.2** `docker compose build web` y `docker run --rm --entrypoint id <imagen>`: verifica el build multi-stage y el usuario no root; requiere Docker con acceso a las imágenes base; éxito = build exit 0 y UID `10001` (≠ 0).
- **7.3** `docker compose up -d` y `docker compose ps`: verifica arranque real y DB no publicada; requiere Docker daemon y el puerto libre; éxito = `web`/`db` en `running`/`healthy` y conexión a `localhost:5432` rechazada.
- **7.4** `curl` a `/api/health`, `/`, `/api/ruta-inexistente` y una ruta profunda (`/agenda`): verifica el serving de SPA/API desde la imagen; requiere el stack arriba (7.3); éxito = health 200 `{"status":"ok"}`, `/` 200 `text/html`, ruta API inexistente 404 JSON y ruta profunda con el `index.html`.
- **7.5** `docker run --rm <imagen>` sin variables requeridas: verifica el fail-fast en arranque real; requiere imagen construida (7.2) y entorno sin variables; éxito = exit ≠ 0 nombrando las variables faltantes sin imprimir valores.
- **7.6** `BACKUP_MODE=compose BACKUP_DIR=./backups scripts/backup_postgres.sh`, luego `scripts/restore_postgres.sh` contra una base scratch, más la línea de cron: verifica backup/restore dentro de los contenedores y la programación diaria; requiere Docker Compose y `crontab` del host; éxito = dump listable con permisos `600`, restore con conteos iguales, sin `.tmp` y cron visible en `crontab -l`.
- **7.7** Deploy en el PaaS single instance elegido (Railway/Render/Fly) siguiendo la guía: verifica `PORT`, TLS y serving en producción; requiere cuenta PaaS y dominio; éxito = `https://<host>/api/health` 200 con certificado válido, `/` sirviendo la SPA y `PORT` respetado.
- **7.8** Deploy self-host con proxy inverso: verifica TLS en el proxy y el puerto interno cerrado; requiere host con proxy y DNS; éxito = `curl -I https://<host>` con certificado válido y `8000` inaccesible desde fuera del host.
