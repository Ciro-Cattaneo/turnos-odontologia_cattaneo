# Design — c-02-core-models

## Context

See `proposal.md` (Why) for motivation. Current state (C-01 archive, verified on disk): `backend/app/{main.py, core/config.py, db/{base.py,session.py}}` with `Base` empty, `backend/alembic/` initialized with zero domain revisions and `env.py` wired to `Base.metadata` + `Settings.DATABASE_URL`, `backend/tests/` patterns (`test_health`, `test_config`, `test_db_wiring`, `test_env_example`, `conftest.py` with fictitious env), `.env.example` with `DATABASE_URL` (psycopg) etc. Constraint firms: this host has **no Docker and no local Postgres** (firmware virtualization off) — tasks DB-backed need a reachable PG16; design still targets real PG (`psycopg` driver, `tstzrange`, GiST) and never SQLite. Governance CRÍTICO: every retention behavior is an explicit AC in `paciente-privacidad`.

## Goals / Non-Goals

**Goals:**

- Persistencia tipada y migrada de las 8 entidades con anti-solape real a nivel DB + contrato app-level para C-05.
- Trail de auditoría no reescribible y privacidad PB-04 exigible por tests contra PG real.
- Seeds idempotentes y staging-only que no amenacen producción.

**Non-Goals:**

- Ningún endpoint, schema Pydantic de API, RBAC, worker o UI (C-03…C-11). `design` no define payloads JSONB de `Notificacion`/`AuditoriaTurno` más allá del tipo columna (los consumen C-07/C-08).
- Ninguna lógica sobre `pago_estado`/`lista_espera_pos` (columnas nulas reservadas).
- Ningún tuning de volumen realista (seed 20 turnos = smoke; follow-up con volumen documentado en Riesgos).

## Decisions

### D-1 — Layout: `backend/app/models/` central con un archivo por entidad

`backend/app/models/{paciente.py, profesional.py, disponibilidad.py, bloqueo.py, turno.py, notificacion.py, usuario_staff.py, auditoria.py}` + `__init__.py` que importa todo para `Base.metadata`; `alembic/env.py` añade `import app.models` (una línea). Los routers C-01 (`modules/*/router.py`) siguen vacíos; C-05/C-07 importan desde `app.models`.

- *Alternativa*: modelos bajo `modules/<dominio>/models.py`. Rechazada: `Turno` referencia `Paciente+Profesional` y `AuditoriaTurno` referencia `Turno+UsuarioStaff` — el layout por módulo crea ciclos de importación; el paquete central da un único punto de registro para Alembic.
- *Aplica*: backend-development (fronteras claras, monolito modular intacto a nivel router).

### D-2 — Mapeos tipados SQLAlchemy 2.x, UUID PK, `timestamptz` en todo tiempo

`Mapped[uuid.UUID] PK default=uuid4`, `Mapped[datetime]` con `DateTime(timezone=True)` para `inicio/fin/created_at/updated_at/enviada_at/desde/hasta`, `TIME` solo en `Disponibilidad.hora_desde/hasta`, `DATE` en vigencias. `created_at` con `server_default=now()`, `updated_at` con `onupdate=now()`. TZ: se persiste UTC, display local `America/Argentina/Buenos_Aires` (regla dura 10; llega a API en C-04/C-05, aquí solo el tipo).

- *Alternativa*: `BigInteger` PKs. Rechazada: KB-04 fija `UUID PK`; además el token ya es UUID y la simetría simplifica seeds/tests.
- *Aplica*: backend-development (typed mappings), supabase-postgres-best-practices (lowercase identifiers, timestamptz everywhere).

### D-3 — Enums PG nativos vía `sqlalchemy.Enum(native_enum=True)`

`turno_estado` (5), `turno_origen` (2), `canal` (`mail`), `notif_tipo` (4), `notif_estado` (3), `staff_rol` (3). Roles fijos como enum (sin tabla extra, per KB-04 "sin tabla extra o tabla roles"). Migración crea los tipos; `canal` queda extensible por migración posterior (añadir `whatsapp` = `ALTER TYPE ... ADD VALUE`, contrato RN-NO-03).

- *Alternativa*: `VARCHAR + CHECK`. Rechazada: el enum nativo da error temprano y documenta el vocabulario RN-TU-07/RN-NO en el catálogo.
- *Aplica*: supabase-postgres-best-practices (CHECK/enum ayudan al planner y a la legibilidad).

### D-4 — Anti-solape: `EXCLUDE USING gist` + predicado de estado + `btree_gist`

Migración `001` ejecuta `CREATE EXTENSION IF NOT EXISTS btree_gist` (igualdad sobre `profesional_id` UUID dentro de GiST lo exige) y crea:

```sql
ALTER TABLE turno ADD CONSTRAINT no_solape_prof
EXCLUDE USING gist (profesional_id WITH =, tstzrange(inicio, fin, '[)') WITH &&)
WHERE (estado IN ('reservado', 'confirmado'));
```

Semántica half-open `[)` explícita: el borde exacto (`fin = inicio` del siguiente) NO colisiona — es el AC EDGE. Hijos cancelados/atendidos/ausentes quedan fuera del predicado y no bloquean. Además `CHECK (fin > inicio)` y `CHECK (duracion_min = EXTRACT ...)`: se implementa como `CHECK (fin > inicio)` + validación app de duración (el cálculo exacto en minutos sobre `tstzrange` en CHECK es frágil con DST; el modelo Python valida `duracion_min == round((fin-inicio).total_seconds()/60)` y la DB garantiza lo esencial).

Contrato app-level (declarado aquí, implementado en C-05): el service de reserva valida solape antes de insertar y traduce la violación de exclusión a `409 + alternativos del mismo día`; la disciplina `SELECT FOR UPDATE` del path de reserva se implementa en C-05 sobre este constraint como red de seguridad.

- *Alternativa*: solo validación app sin EXCLUDE. Rechazada: viola la regla dura 2 (solape también en DB) y pierde contra colisiones concurrentes.
- *Aplica*: supabase-postgres-best-practices (EXCLUDE gist para no-overlap), regla dura 2, RN-TU-03.

### D-5 — Índices: compuestos en orden de filtro + parciales + FK

- `ix_turno_prof_inicio (profesional_id, inicio)` — orden = filtro de agenda/reserva (supabase + sql-optimization: orden compuesto = orden de filtro).
- `ix_turno_estado_inicio` parcial `WHERE estado IN ('reservado','confirmado')` — cómputo slots y worker solo miran activos.
- `ux_turno_token (token_cancelacion)`, `ux_paciente_dni (dni)`, `ix_paciente_telefono`, `ix_profesional_activo WHERE activo`, `ix_disponibilidad_prof_dia (profesional_id, dia_semana)`, `ix_notif_estado WHERE estado='pendiente'` (worker C-08), índice propio en cada FK (`turno.profesional_id/paciente_id`, `notificacion.turno_id`, `auditoria.turno_id`, `bloqueo.profesional_id`, `disponibilidad.profesional_id`, `usuario_staff.profesional_id`).
- Emails: `UsuarioStaff.email CITEXT UNIQUE` (KB-04) requiere `CREATE EXTENSION IF NOT EXISTS citext`; `Paciente.email VARCHAR(160) NOT NULL` con CHECK de formato laxo a nivel modelo (el 400 por campo llega en C-05 con Pydantic `extra='forbid'`; aquí la DB solo exige presencia).
- *Aplica*: supabase-postgres-best-practices (partial indexes, FK indexes), sql-optimization (nunca `SELECT *`, columnas explícitas — los repos futuros seleccionan columnas, no entidades completas, en agenda/reportes).

### D-6 — Alembic `001_core_models`: autogenerate revisado a mano, upgrade+downgrade testeados

Flujo: `alembic revision --autogenerate -m "001_core_models"` y luego revisión manual obligatoria (orden de `CREATE TYPE`/`EXTENSION`, EXCLUDE textual exacto, `server_default` UTC). Downgrade elimina constraint, tablas y tipos en orden inverso. Tests de migración (upgrade head + downgrade -1 + upgrade) contra PG real en tasks.

- *Alternativa*: SQL escrito a mano sin autogenerate. Rechazada: autogenerate acelera y la revisión manual (backend-development: never blind) captura lo que aquel omite (EXCLUDE, extensiones).
- *Aplica*: backend-development, tdd-guide (migración real vía fixtures, no SQLite).

### D-7 — Seeds idempotentes, staging-only para demo, rotación fuera de scope

- Seed base (corre en toda DB migrada vacía): `INSERT ... ON CONFLICT DO NOTHING` del admin desde `ADMIN_EMAIL`/`ADMIN_PASSWORD` (hash bcrypt/argon2 — el hash se produce aquí; la **rotación al primer login es C-03**, aquí solo creación + test de existencia/idempotencia).
- `backend/scripts/seed_demo.py`: solo staging, 2 profesionales + 20 turnos ficticios (nombres/DNI/tel/mail sintéticos, p. ej. dominio `.test`), guarda `if os.getenv("ENV") == "prod": sys.exit("refuse")`. Nunca en prod (regla dura 12 + C-12 lo reitera).
- *Aplica*: backend-development (seeds idempotentes, staging-only).

### D-8 — `AuditoriaTurno` append-only con trigger DB + disciplina app

Migración añade trigger `auditoria_no_update_delete` (`BEFORE UPDATE OR DELETE ... RAISE EXCEPTION`) de modo que el rechazo es observable desde cualquier cliente, no solo del ORM. La app además no expone ningún path de update/delete de auditoría. Tests intentan `UPDATE`/`DELETE` y esperan excepción.

- *Alternativa*: solo disciplina app ("no escribimos esos paths"). Rechazada: governance CRÍTICO exige garantía, no promesa; el trigger es barato y permanente.
- *Aplica*: RN-AU-02, supabase-postgres-best-practices (triggers para invariantes).

### D-9 — PB-04: soft-delete + guarda de DELETE + anonimización como script documentado

- `Paciente.activo BOOL DEFAULT true`; listados futuros filtran `activo=true` (C-07/C-10; aquí el modelo + índice parcial/implícito).
- `Turno.paciente_id FK ... ON DELETE RESTRICT`: el DELETE físico con turnos falla a nivel DB además del chequeo app (`SELECT count == 0`). Sin hard-delete con turnos (regla dura 3).
- Anonimización: `docs/anonimizacion-ley-25326.md` (o `backend/scripts/anonimizar_paciente.py --paciente-id`) documenta `UPDATE paciente SET nombre='Eliminado #id', dni=NULL, telefono=NULL, email=NULL, obra_social='(eliminado)'...` — nota: `dni/tel/mail` son `NOT NULL` en KB-04, por lo que el script requiere `ALTER COLUMN DROP NOT NULL` previo o columnas ya nulables: **decisión D-9a**: la migración 001 hace `dni/telefono/email/obra_social/nombre` nulables a nivel DB y la obligatoriedad RN-TU-01 se exige a nivel app/Pydantic (C-05 `extra='forbid'` + 400 por campo), de modo que la anonimización a NULL es posible sin segunda migración. Los turnos se conservan como estadística; se escribe fila de auditoría del acto (actor admin). Sin UI v1.
- *Alternativa*: columnas `NOT NULL` + borrado físico como "olvido". Rechazada: destruiría reportes/ausentismo y violaría Excepciones globales KB-05.

### D-10 — Estrategia de tests: unit puro primero, PG real después, borde `<` vs `<=` con mutación

`conftest.db_session` (PG real, migraciones aplicadas, rollback por test), nombres `test_<escenario>_<resultado>`, docstrings con `# AC <capability>/S<n>`, parametrización en bordes. El borde half-open se marca como objetivo de mutación 85%+ en el apply. Sin mocks de DTOs/engines (test-guard); mocks solo en bordes (ninguno en este change — todo es PG real o asserts puros de modelo).

## Risks / Trade-offs

- [Riesgo] Sin PG16 en este host no hay verde DB-backed local → Mitigación: tasks.md tarea 0 exige "Postgres 16 alcanzable (instalador EDB local documentado en README como fallback) antes de tareas DB"; tareas puras (modelos importables, naming, migración offline `--sql`) van primero.
- [Riesgo] `citext`/`btree_gist` ausentes en un PG gestionado con extensiones restringidas → Mitigación: `CREATE EXTENSION IF NOT EXISTS` + fallo claro al migrar; fallback documentado (funcional `lower(email)` + GiST sobre expresión) solo si el proveedor lo exige — no se diseña por defecto.
- [Riesgo] `Paciente.email NOT NULL` vs anonimización a NULL → Mitigación: D-9a (nulable en DB, obligatorio en app) resuelto en este design; queda como AC explícito.
- [Trade-off] Trigger append-only impide correcciones manuales legítimas (p. ej. GDPR mal escrito) → aceptado: toda corrección es nueva fila compensatoria, nunca UPDATE; documentado.
- [Riesgo] Seed 20 turnos no prueba EXPLAIN bajo volumen → Mitigación: follow-up anotado (verificación `EXPLAIN` sobre `ix_turno_prof_inicio` con volumen realista en C-04/C-11, no en este change).
- [Riesgo] `duracion_min` vs `fin-inicio` con DST America/Argentina (sin DST desde 2008, pero timestamptz) → Mitigación: validación app en minutos + CHECK DB mínimo; display local fuera de scope aquí.

## Migration Plan

1. Merge: solo añade archivos (`models/`, `001_*`, `scripts/seed_demo.py`, doc anonimización); `alembic/env.py` +1 import. Sin datos previos (C-01 sin tablas) → nada que migrar.
2. Deploy: `alembic upgrade head` crea extensiones → tipos → tablas → EXCLUDE → trigger → seed admin. Rollback: `alembic downgrade -1` revierte en orden inverso (testeado).
3. Verificación: `pytest` PG-backed verde + `openspec validate --change c-02-core-models`.

## Open Questions

- KB-04 fija `Paciente.email VARCHAR` pero `UsuarioStaff.email CITEXT`: ¿la asimetría es deliberada (login case-insensitive vs dato paciente)? Asumido sí; si el consultorio quiere CITEXT también en paciente, es migración menor post-C-02 (no bloquea).
- Forma exacta de `Notificacion.payload` / `AuditoriaTurno.detalle` JSONB: la definen C-08/C-07 respectivamente; aquí solo el tipo columna (no bloquea).
- `Profesional.matricula UNIQUE`? KB-04 no lo exige; asumido nullable no-único en v1 (no bloquea; C-11 puede endurecerlo).
- `Bloqueo.creado_por` nullable cuando lo crea un seed/sistema? Asumido nullable FK (no bloquea; C-04 lo precisa).
- `Disponibilidad` sin solape mismo profesional+día es "validación app + test" (KB-04) sin EXCLUDE — asumido así; si se quiere EXCLUDE temporal se propone en C-04 (no bloquea este change).
