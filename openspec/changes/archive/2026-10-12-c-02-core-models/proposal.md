# Proposal — c-02-core-models (C-02 per CHANGES.md)

## Why

Sin modelos de dominio persistidos no existe ningún flujo de turnos: hoy `Base.metadata` está vacío (C-01) y ninguna reserva, agenda o auditoría puede escribirse. C-02 es la base de dominio del cambio MVP "crear turno sin solapamientos" (PDF Etapa 6.1): aquí viven el constraint anti-solape y el modelo `Turno` que lo hace cumplir; el comportamiento de reserva que lo usa llega en C-04 (cómputo de slots) y C-05 (transacción `POST /api/turnos`). Sin este change, el camino crítico `C-01 → C-02 → C-04 → C-05 → C-08 → C-09 → C-12` no avanza.

## What Changes

- Modelos SQLAlchemy 2.x tipados (`Mapped`/`mapped_column`) para `Paciente, Profesional, Disponibilidad, Bloqueo, Turno, Notificacion, UsuarioStaff, AuditoriaTurno` con atributos/constraints/índices según KB-04 (sin endpoints ni lógica de negocio — solo persistencia + constraints).
- `Turno`: enum `estado` (`reservado, confirmado, cancelado, atendido, ausente`), enum `origen` (`online, recepcion`), `token_cancelacion UUID UNIQUE NOT NULL`, `fin > inicio`, columnas reservadas post-v1 `pago_estado NULL, lista_espera_pos NULL` (sin lógica), `canal_recordatorio ENUM(mail)` extensible.
- Anti-solape a dos niveles: constraint Postgres `EXCLUDE USING gist (profesional_id WITH =, tstzrange(inicio, fin) WITH &&) WHERE (estado IN ('reservado','confirmado'))` + contrato de validación app-level en service (implementada en C-05; aquí se declara el contrato y el mensaje 409).
- Migración Alembic `001_core_models` (autogenerate revisado a mano) + seed: roles enum, admin inicial desde env (`ADMIN_EMAIL`/`ADMIN_PASSWORD`, rotación al primer login = scope C-03, aquí solo creación) + script `seed_demo.py` solo staging (2 profesionales + 20 turnos, datos ficticios).
- GATE PB-04 HÍBRIDO (binding): soft-delete default (`activo=false`, UI dice "desactivar"); `DELETE` físico permitido SOLO con cero turnos; procedimiento manual documentado de anonimización Ley 25.326 (nombre→"Eliminado #id", dni/tel/mail→NULL, turnos conservados como estadística; sin UI v1, script/endpoint admin documentado).
- `AuditoriaTurno` append-only (sin UPDATE/DELETE por app).
- Tests: creación de entidades, `UNIQUE(dni)`, exclusión anti-solape concurrente, append-only auditoría — todos contra Postgres 16 real (SQLite no sustituye: `tstzrange`/gist/colisión concurrente/migraciones reales).
- Explícitamente FUERA de scope: endpoints REST (C-04/C-05/C-07), auth/RBAC y rotación de password (C-03), worker mail (C-08), frontend (C-09/C-10), reportes (C-11), deploy/backups (C-12), lógica de `pago_estado`/`lista_espera_pos` (post-v1), reprogramación paciente (v1.1, PB-08).

## Capabilities

### New Capabilities

- `core-models`: entidades persistidas + constraints + índices (las 8 tablas, EXCLUDE anti-solape, UNIQUE/CHECK/FK, migración `001`, seed admin/demo). Es el contrato de persistencia que C-03…C-08 consumen.
- `turno-lifecycle`: invariantes del ciclo de vida de `Turno` a nivel modelo (enum `estado` + `origen` + `token_cancelacion` obligatorio y único + `fin > inicio` + `canal_recordatorio=mail` default + columnas reservadas post-v1 nulas). La máquina de transiciones (RN-TU-07) se implementa en C-07; aquí solo los valores y la obligatoriedad que el modelo garantiza.
- `paciente-privacidad`: retención de datos de salud (PB-04 HÍBRIDO + Ley 25.326): soft-delete default, DELETE físico solo con cero turnos, anonimización manual documentada, `AuditoriaTurno` append-only como trail.

### Modified Capabilities

(none — C-01 deja `service-health|service-config|frontend-shell` intactos; este change no altera sus REQUIREMENTS)

## Impact

- Crea `backend/app/models/*.py` (o `backend/app/modules/*/models.py` según layout C-01 — decide design), revisión `001_core_models`, `backend/scripts/seed_demo.py` + doc de anonimización; toca `backend/requirements.txt` solo si falta driver (`psycopg` ya pineado en C-01) y `alembic/env.py` solo para importar modelos.
- Desbloquea C-03 (FK a `UsuarioStaff`/roles) y C-04 (lee `Disponibilidad/Bloqueo/Turno`); sin breaking changes (sin consumidores de dominio previos).
- Governance CRÍTICO (datos de salud, Ley 25.326, audit trail): cada comportamiento de retención es un AC explícito en `paciente-privacidad`; datos ficticios obligatorios en tests/seed (regla dura 12).
- Precondición de entorno: este change REQUIERE Postgres 16 alcanzable para tareas DB-backed (este host no tiene Docker ni PG local — ver design/tasks tarea 0); sin PG no hay verde real.
