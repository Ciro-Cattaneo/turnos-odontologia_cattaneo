# Deploy single host — Turnos Odontología (Cattaneo)

> Documento operativo de C-12. Cubre el orden de deploy, Docker Compose en un
> host único, PaaS single instance (Railway / Render / Fly), TLS en el borde,
> migraciones y rollback, backup/restore y la declaración mínima Ley 25.326.
> Todos los ejemplos usan **datos ficticios** (`@ficticio.test`, DNI sintéticos
> `33999xxx`): nunca datos reales de pacientes (Ley 25.326, regla dura 12).

## 1. Arquitectura de despliegue

- **Una imagen, un origen**: la imagen compila el frontend y FastAPI sirve la
  SPA en `/` y la API bajo `/api`. En producción no hay CORS cross-origin: el
  navegador habla con el mismo host.
- **TLS lo termina** el PaaS o un proxy inverso del host. La app escucha HTTP
  en el puerto interno `8000` y no monta certificados.
- **Postgres es privado**: sólo el servicio `web` publica un puerto; `db` vive
  en la red interna `turnos-internal` y no se expone al host.
- **Worker de mail en-proceso** (APScheduler dentro de `web`): no hay
  contenedor `worker` ni Redis en v1 (regla dura 6, PB-03).

## 2. Requisitos

- Docker 24+ con Compose v2 (self-host) **o** una cuenta en un PaaS single
  instance.
- Cliente PostgreSQL 16+ (`pg_dump`, `pg_restore`, `psql`) en el host para los
  backups; el script también soporta `BACKUP_MODE=compose` sin cliente local.
- Un `.env` real derivado de `.env.example` (nunca versionado).

## 3. Variables de entorno

Copiar `.env.example` a `.env` y reemplazar todos los placeholders:

| Variable | Nota |
|----------|------|
| `ENV` | `prod` en producción: rechaza placeholders y `SECRET_KEY` < 32 caracteres. |
| `DATABASE_URL` | `postgresql+psycopg://usuario:password@db:5432/turnos` en Compose. |
| `POSTGRES_PASSWORD` | Sólo la consume el servicio `db`. |
| `SECRET_KEY` | 32+ caracteres aleatorios; distinto por entorno. |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Admin inicial; password fuerte. |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` / `SMTP_FROM` | Mail transaccional (hoy **PROVISORIO/MIGRABLE**, ver §12). |
| `TZ` | `America/Argentina/Buenos_Aires` para logs; la persistencia es UTC. |
| `FRONTEND_URL` | `https://turnos.ficticio.test` en producción; allowlist de CORS. |
| `WEB_PORT` | `127.0.0.1:8000` con proxy (bind loopback). |
| `FORWARDED_ALLOW_IPS` | IP del proxy que puede reenviar `X-Forwarded-*`. |

El arranque falla con exit code distinto de 0 si falta una variable requerida:
el mensaje nombra **todas** las faltantes sin imprimir sus valores.

## 4. Orden de deploy (obligatorio)

1. **Backup** de la base actual (`scripts/backup_postgres.sh`).
2. **Migraciones**: `alembic upgrade head` como paso previo al tráfico.
3. **Arranque** de la nueva imagen (`docker compose up -d` o deploy del PaaS).
4. **Verificación**: `GET /api/health` responde 200 y la SPA carga en `/`.

Nunca migrar desde el `CMD` del contenedor: dos instancias podrían migrar a la
vez o la app arrancaría igual tras una migración fallida.

```bash
# 1) backup (datos ficticios en el ejemplo)
DATABASE_URL="postgresql+psycopg://turnos:changeme@localhost:5432/turnos" \
  scripts/backup_postgres.sh

# 2) migración
docker compose run --rm web alembic upgrade head

# 3) arranque
docker compose up -d --build

# 4) verificación
curl -fsS http://127.0.0.1:8000/api/health
curl -fsSI http://127.0.0.1:8000/
```

La revisión esperada es `002_agenda_meta` (`alembic current`).

## 5. Docker Compose self-host

```bash
docker compose config          # valida el compose
docker compose build web
docker compose up -d
docker compose ps              # web y db en running/healthy
```

Sólo `web` publica `WEB_PORT`. La base no mapea `5432` al host.

### 5.1 TLS en un proxy del host

Con un proxy inverso (Caddy o Traefik) delante del compose:

```caddyfile
turnos.ficticio.test {
    reverse_proxy 127.0.0.1:8000
}
```

- `WEB_PORT=127.0.0.1:8000` para que `8000` **no** quede accesible desde fuera
  del host.
- `FORWARDED_ALLOW_IPS=<ip-del-proxy>` para que uvicorn sólo confíe en
  `X-Forwarded-Proto`/`X-Forwarded-For` de ese proxy (por defecto confía sólo
  en `127.0.0.1`).
- **Sin TLS no expongas `8000` a Internet**: las cookies de sesión staff
  viajarían en claro.

## 6. PaaS single instance (Railway / Render / Fly)

1. Crear el servicio apuntando al `Dockerfile` del repo (build desde la raíz).
2. Añadir Postgres gestionado y copiar su URL a `DATABASE_URL`.
3. Cargar las variables de §3 con `ENV=prod` y `FRONTEND_URL=https://<host>`.
4. Configurar el **release command** o pre-deploy: `alembic upgrade head`.
5. Deployar **una sola instancia**: el worker de mail corre en-proceso; dos
   réplicas duplicarían recordatorios (regla dura 6).
6. TLS y dominio los gestiona la plataforma; la app respeta `PORT` inyectado.

Verificación: `https://<host>/api/health` responde 200 con certificado válido,
`/` sirve la SPA y `PORT` fue respetado.

## 7. Migraciones

- Self-host: `docker compose run --rm web alembic upgrade head`.
- PaaS: comando de release/pre-deploy antes de promover la versión.
- Criterio: `alembic current` muestra `002_agenda_meta` (C-12 no agrega
  migraciones). Si el `head` no coincide, **no** promover el deploy.

## 8. Rollback

Criterio observable de éxito: `/api/health` responde 200 **y** `alembic
current` muestra la revisión esperada.

1. Volver a la **imagen** anterior (tag o revisión previa del PaaS).
2. Si la migración no es reversible (p. ej. cambios destructivos), restaurar el
   último backup con `scripts/restore_postgres.sh` y luego dejar la **revisión**
   Alembic previa.
3. Verificar `/api/health` y `alembic current` antes de reabrir el tráfico.

No se asume que toda migración tenga `downgrade` reversible.

## 9. Backup y restore

El backup diario usa formato custom de Postgres, verifica con `pg_restore
--list`, deja permisos `600` y rota a **7 días**:

```bash
BACKUP_DIR=/var/backups/turnos BACKUP_RETENTION_DAYS=7 \
  DATABASE_URL="postgresql+psycopg://turnos:changeme@localhost:5432/turnos" \
  scripts/backup_postgres.sh
```

Cron del host (TZ America/Argentina/Buenos_Aires, 03:17 local):

```cron
17 3 * * * cd /srv/turnos && BACKUP_DIR=/var/backups/turnos ./scripts/backup_postgres.sh >> /var/log/turnos-backup.log 2>&1
```

Restore sobre una base scratch (nunca sobre `turnos` en caliente):

```bash
# target vacío: sin guarda. Target con tablas: requiere --force explícito.
scripts/restore_postgres.sh \
  /var/backups/turnos/turnos_20261116T031700Z.dump \
  "postgresql+psycopg://turnos:changeme@localhost:5432/turnos_scratch" --force
```

El script rechaza un target no vacío sin `--force`, restaura con
`pg_restore --clean --if-exists --no-owner --no-acl` y reporta los conteos de
`turno` y la revisión de `alembic_version`. Con `EXPECTED_TURNO_COUNT` falla si
el conteo no coincide.

## 10. Salud y verificación

```bash
curl -fsS http://127.0.0.1:8000/api/health        # {"status":"ok"}
curl -fsSI http://127.0.0.1:8000/                 # text/html (SPA)
curl -fsSI http://127.0.0.1:8000/agenda           # text/html (fallback SPA)
curl -s  http://127.0.0.1:8000/api/ruta-inexistente  # 404 JSON
```

## 11. Declaración mínima Ley 25.326

- **Finalidad**: los datos personales de pacientes (nombre, DNI, teléfono,
  email) se tratan únicamente para gestionar turnos, recordatorios y el
  historial clínico-administrativo del consultorio.
- **Conservación**: se conservan mientras el turno y su historial sean
  necesarios para la atención; la eliminación se hace por anonimización manual
  documentada en `docs/anonimizacion-ley-25326.md`.
- **No cesión**: los datos **no se ceden a terceros**. Sólo el proveedor SMTP
  recibe el email del recordatorio, con la finalidad exclusiva de enviarlo.
- **Seguridad en tránsito**: todo el tráfico externo viaja por TLS terminado en
  el borde; la base no se expone fuera de la red interna.

## 12. Componentes PROVISORIO/MIGRABLE

| Componente | Estado | Ruta de migración |
|------------|--------|-------------------|
| SMTP Gmail + app password | **PROVISORIO/MIGRABLE** | Contratar un **proveedor transaccional** (API key, DKIM/SPF propio) y cambiar sólo las variables `SMTP_*`. |
| Backups a disco local (7 días) | **PROVISORIO/MIGRABLE** | Copiar `BACKUP_DIR` a **storage externo** (object storage) fuera del host; el host y su disco mueren juntos. |

Ambos están marcados igual en `.env.example` y no cambian el contrato de la
aplicación: son configuración operativa.

## 13. Ejemplos con datos ficticios

- Paciente demo: `Paciente Ficticio`, **DNI 33999001**,
  `paciente.ficticio@ficticio.test`.
- Admin demo: `admin@ficticio.test`.
- Remitente: `turnos@ficticio.test`.
- Host de ejemplo: `turnos.ficticio.test`.

Cualquier valor real de paciente, credencial o dominio productivo queda fuera
del repositorio (regla dura 10 y 12).
