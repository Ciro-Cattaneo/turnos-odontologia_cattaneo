# Spec Delta — despliegue-operacion

## Purpose

Define cómo se empaqueta, despliega, respalda y opera v1 en un único host: una imagen de aplicación que sirve SPA y API, una topología Compose mínima y segura, backups verificables con retención acotada, guía de deploy con TLS/migraciones/rollback y datos demo restringidos a staging.

## ADDED Requirements

### Requirement: Imagen de aplicación única que sirve SPA y API

The system SHALL build a single application image that serves the compiled frontend at `/`, keeps every API route under `/api`, runs as a non-root user and answers the platform liveness probe; the image SHALL NOT contain secrets or an API env file.

#### Scenario: FELIZ — La imagen arranca y sirve API y SPA

- **DADO** una imagen construida desde el repo y un contenedor arrancado con todas las variables de entorno requeridas
- **CUANDO** se consulta `GET /api/health` y `GET /` dentro del contenedor
- **ENTONCES** el health responde `200` con `{"status":"ok"}`, `/` responde `200` con `content-type: text/html` y el `index.html` del build, y el proceso corre con un UID distinto de 0

#### Scenario: BORDE — Una ruta profunda del cliente devuelve el index de la SPA

- **DADO** un contenedor en ejecución con el build del frontend
- **CUANDO** se pide una ruta del router del cliente como `GET /cancelar?token=ficticio` o `GET /agenda`
- **ENTONCES** responde `200` con el `index.html` de la SPA (el fallback solo aplica a rutas fuera de `/api`)

#### Scenario: ERROR — Una ruta desconocida bajo /api no cae en el fallback de la SPA

- **DADO** un contenedor en ejecución
- **CUANDO** se pide `GET /api/ruta-inexistente`
- **ENTONCES** responde `404` con cuerpo JSON de la API (nunca `text/html` ni el `index.html`)

#### Scenario: ERROR — La imagen no contiene secretos ni archivo .env

- **DADO** la imagen construida y su sistema de archivos inspeccionado
- **CUANDO** se buscan archivos `.env`, credenciales SMTP y claves de sesión dentro de la imagen
- **ENTONCES** no existe ningún `.env` ni valor secreto embebido, y toda credencial entra solo por variables de entorno en tiempo de ejecución (regla dura 10)

### Requirement: Topología Compose single-host con base de datos privada

The system SHALL start exactly one web service plus one Postgres service under Docker Compose, with restart policy `unless-stopped`, healthchecks on both, a named data volume, the database reachable only through the internal network, and no worker or Redis container in v1 (regla dura 6).

#### Scenario: FELIZ — Compose levanta web y db saludables con un solo puerto publicado

- **DADO** un `.env` con valores ficticios y el compose final
- **CUANDO** se ejecuta `docker compose config` y luego `docker compose up -d`
- **ENTONCES** el archivo valida, quedan exactamente dos contenedores (`web`, `db`) en estado `running`/`healthy`, y solo `web` publica un puerto en el host

#### Scenario: BORDE — La base de datos no se expone fuera de la red interna

- **DADO** el compose final en ejecución
- **CUANDO** se inspeccionan los puertos publicados y la red de `db`
- **ENTONCES** `db` no mapea ningún puerto al host y el `DATABASE_URL` usa el nombre de servicio interno (`db:5432`)

#### Scenario: ERROR — Web no arranca antes de que la base esté sana

- **DADO** el servicio `db` detenido o aún inicializando
- **CUANDO** se ejecuta `docker compose up web`
- **ENTONCES** `web` no queda sirviendo tráfico hasta que el healthcheck de `db` reporta `healthy` (`depends_on: condition: service_healthy`) y no entra en crash-loop por conexión rechazada

#### Scenario: ERROR — No hay worker ni Redis activos en v1

- **DADO** el compose final
- **CUANDO** se listan los servicios definidos y se inspecciona el bloque comentado de worker/redis
- **ENTONCES** solo `web` y `db` están activos, el worker aparece comentado citando su módulo real (no un entrypoint inexistente) y `REDIS_URL` figura únicamente como variable documentada (regla dura 6, PB-03)

### Requirement: Backup diario verificable con retención de 7 días

The system SHALL provide a versioned script that dumps Postgres in custom format to host disk, verifies the dump is listable, restricts file permissions, deletes dumps older than 7 days and exits non-zero without leaving partial dumps on failure (PB-05).

#### Scenario: FELIZ — El backup crea un dump verificable y con permisos restringidos

- **DADO** una base Postgres accesible y un `BACKUP_DIR` escribible
- **CUANDO** se ejecuta `scripts/backup_postgres.sh`
- **ENTONCES** crea `turnos_<timestamp UTC>.dump` con permisos `600`, `pg_restore --list` sobre el archivo termina con éxito y el script sale con código 0

#### Scenario: BORDE — Dos ejecuciones el mismo día no se pisan y la rotación respeta 7 días

- **DADO** un `BACKUP_DIR` con un dump de hace 8 días y ejecuciones repetidas del script
- **CUANDO** se ejecuta el backup dos veces y luego la rotación
- **ENTONCES** existen dos archivos distintos con timestamps únicos, ninguno se sobrescribe, el dump de 8 días se elimina y el backup más reciente se conserva

#### Scenario: ERROR — Un fallo de pg_dump no deja dump parcial ni filtra credenciales

- **DADO** una base inalcanzable o credenciales inválidas
- **CUANDO** se ejecuta `scripts/backup_postgres.sh`
- **ENTONCES** sale con código distinto de 0, no queda un `.dump` nuevo o incompleto en `BACKUP_DIR`, y la salida de error no imprime la contraseña ni el DSN completo

#### Scenario: FELIZ — El restore documentado reproduce los datos del dump

- **DADO** un dump generado por el script y una base scratch vacía
- **CUANDO** se ejecuta `scripts/restore_postgres.sh <dump> <database-url-scratch>`
- **ENTONCES** el restore termina con éxito y los conteos de `turno` y la revisión de `alembic_version` coinciden con los del origen

### Requirement: Guía de deploy con migraciones, TLS y rollback

The repo SHALL include a versioned deployment guide covering Docker Compose single host and one single-instance PaaS option, TLS terminated outside the application, `alembic upgrade head` before receiving traffic, and rollback to the previous image and database state.

#### Scenario: FELIZ — La guía cubre Compose, PaaS, TLS, migraciones y rollback

- **DADO** el repositorio versionado
- **CUANDO** se revisa la guía de deploy
- **ENTONCES** contiene secciones explícitas para deploy single host con Compose, deploy en PaaS single instance (Railway/Render/Fly), TLS, `alembic upgrade head` previo al tráfico y rollback

#### Scenario: BORDE — TLS se termina fuera de la aplicación

- **DADO** la guía de deploy y la configuración del contenedor
- **CUANDO** se revisa cómo se sirve HTTPS
- **ENTONCES** el TLS lo termina el PaaS o un proxy inverso del host, la app escucha HTTP en el puerto interno y solo confía en cabeceras de proxy reenviadas por ese proxy

#### Scenario: ERROR — El rollback tiene criterio observable

- **DADO** un deploy que falla tras migrar o tras cambiar de imagen
- **CUANDO** se sigue el procedimiento de rollback documentado
- **ENTONCES** la guía indica cómo volver a la imagen y revisión Alembic previas (o restaurar el último backup si la migración no es reversible) y el criterio de éxito es `/api/health` en 200 con la revisión esperada

### Requirement: Declaración mínima de privacidad y estado provisorio visible

The deployment guide SHALL include a minimal Ley 25.326 declaration (purpose, retention and no transfer of patient data) and SHALL mark the Gmail SMTP and host-disk backups as PROVISORIO/MIGRABLE with their migration path.

#### Scenario: FELIZ — La declaración menciona finalidad, conservación y no cesión

- **DADO** la guía de deploy versionada
- **CUANDO** se revisa su sección de privacidad
- **ENTONCES** declara la finalidad del tratamiento de datos de pacientes, la política de conservación y que los datos no se ceden a terceros

#### Scenario: BORDE — Los componentes provisorios están marcados con su reemplazo

- **DADO** la guía de deploy y `.env.example`
- **CUANDO** se revisan SMTP y backups
- **ENTONCES** ambos figuran como PROVISORIO/MIGRABLE con la ruta de migración indicada (proveedor SMTP transaccional y almacenamiento de backups fuera del host)

#### Scenario: ERROR — La documentación no contiene datos reales de pacientes

- **DADO** la guía de deploy y sus ejemplos
- **CUANDO** se buscan datos personales reales
- **ENTONCES** todos los ejemplos usan datos ficticios (`@ficticio.test`, DNI sintéticos) y no aparece ningún dato real (Ley 25.326, regla dura 12)

### Requirement: Seed de datos demo restringido a staging

The demo seed SHALL run only when `ENV=staging` is set explicitly, exit non-zero without touching the database in any other environment, and insert only fictitious data (regla dura 12).

#### Scenario: FELIZ — En staging inserta solo datos ficticios

- **DADO** `ENV=staging` y un `DATABASE_URL` de staging alcanzable
- **CUANDO** se ejecuta `python scripts/seed_demo.py`
- **ENTONCES** sale con código 0, crea profesionales y turnos de ejemplo, y todos los contactos usan el dominio `@ficticio.test`

#### Scenario: ERROR — En producción se rechaza sin escribir

- **DADO** `ENV=prod` y una base alcanzable
- **CUANDO** se ejecuta el seed
- **ENTONCES** sale con código 2, imprime un mensaje de rechazo y no inserta ni modifica ninguna fila

#### Scenario: BORDE — Sin ENV explícito falla cerrado

- **DADO** un entorno sin `ENV` o con un valor distinto de `staging`
- **CUANDO** se ejecuta el seed
- **ENTONCES** sale con código 2 sin conectarse a escribir en la base (comportamiento fail-closed)
